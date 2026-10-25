#!/usr/bin/env python3
"""
Sengoku Basara 4 Sumeragi — Native PC Port
Automated Game Binary Linker & Image Builder

Native x86_64 Runtime & Vulkan 1.3 Engine
"""

import os
import sys
import json
from pathlib import Path

# Safe stdout reconfiguration to prevent Windows cp1252 UnicodeEncodeError
for s in (sys.stdout, sys.stderr):
    if hasattr(s, 'reconfigure'):
        try:
            s.reconfigure(errors='replace')
        except Exception:
            pass

# Ensure scripts and tools directories are available in sys.path
def _setup_paths():
    base_dir = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path(os.getcwd())
    if hasattr(sys, '_MEIPASS'):
        meipass = Path(sys._MEIPASS)
        for p in [meipass, meipass / 'scripts', meipass / 'tools']:
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))
    for p in [base_dir / 'scripts', base_dir / 'tools', base_dir]:
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))

_setup_paths()

import prepare
import link_modules
import content_profile
try:
    import gen_import_names
except ImportError:
    gen_import_names = None


REQUIRED_MODULES = (
    'libc.prx',
    'libSceFios2.prx',
    'ulobjmgr.sprx',
    'libSceFiber.sprx',
    'libSceUlt.sprx',
    'libSceAjm.sprx',
    'libSceNgs2.sprx',
)


def sync_and_verify_modules(game_dir: Path, source_hint_dir=None, status_callback=None):
    """
    Ensures all 7 required PS4 system modules (.prx / .sprx) exist before linking.
    Scans game_dir/sce_module, user/sys_modules, source_hint_dir, and sys_modules zip archives.
    Automatically extracts and synchronizes modules between directories.
    Raises RuntimeError if critical modules (specifically libSceNgs2.sprx and libSceAjm.sprx) are missing.
    """
    import zipfile
    import shutil

    target_sce = (game_dir / 'sce_module').resolve()
    target_sys = (Path.cwd() / 'user' / 'sys_modules').resolve()
    target_sce.mkdir(parents=True, exist_ok=True)
    target_sys.mkdir(parents=True, exist_ok=True)

    scan_dirs = [target_sce, target_sys, game_dir, Path.cwd(), Path.cwd() / 'user']
    if source_hint_dir:
        try:
            shd = Path(source_hint_dir).resolve()
            scan_dirs.extend([
                shd,
                shd / 'sce_module',
                shd / 'sys_modules',
                shd / 'user' / 'sys_modules',
                shd.parent / 'sce_module',
                shd.parent / 'sys_modules',
                shd.parent / 'user' / 'sys_modules',
            ])
        except Exception:
            pass

    scan_dirs.extend([
        Path.cwd() / 'extracted_game' / 'app0' / 'sce_module',
        Path.cwd() / 'app0' / 'sce_module',
    ])

    # 1. Look for zip archives containing system modules
    found_zips = set()
    for sdir in scan_dirs:
        if sdir.is_dir():
            for zfile in sdir.glob("*.zip"):
                found_zips.add(zfile.resolve())

    for zp in found_zips:
        try:
            with zipfile.ZipFile(zp, 'r') as zf:
                names = zf.namelist()
                matching = [n for n in names if any(n.endswith('/' + rm) or n.endswith('\\' + rm) or n == rm for rm in REQUIRED_MODULES)]
                if matching:
                    if status_callback:
                        status_callback(f"Extracting PS4 system modules from {zp.name}...")
                    for member in matching:
                        fname = os.path.basename(member)
                        for dest in (target_sce, target_sys):
                            dest_path = dest / fname
                            if not dest_path.is_file() or dest_path.stat().st_size == 0:
                                with zf.open(member) as zsrc, open(dest_path, 'wb') as zdst:
                                    shutil.copyfileobj(zsrc, zdst)
        except Exception:
            pass

    # 2. Copy modules from any scan_dirs to both target_sce and target_sys
    for sdir in scan_dirs:
        if sdir.is_dir() and sdir != target_sce and sdir != target_sys:
            for rm in REQUIRED_MODULES:
                src_file = sdir / rm
                if src_file.is_file():
                    for dest in (target_sce, target_sys):
                        dst_file = dest / rm
                        if not dst_file.is_file():
                            try:
                                shutil.copy2(src_file, dst_file)
                            except Exception:
                                pass

    # 3. Bi-directional sync between target_sce and target_sys
    for rm in REQUIRED_MODULES:
        f_sce = target_sce / rm
        f_sys = target_sys / rm
        if f_sce.is_file() and not f_sys.is_file():
            try:
                shutil.copy2(f_sce, f_sys)
            except Exception:
                pass
        elif f_sys.is_file() and not f_sce.is_file():
            try:
                shutil.copy2(f_sys, f_sce)
            except Exception:
                pass

    # 4. Validate that all 7 required modules exist
    missing = []
    for rm in REQUIRED_MODULES:
        if not ((target_sce / rm).is_file() or (target_sys / rm).is_file()):
            missing.append(rm)

    if missing:
        err = (
            "Modul PS4 tidak lengkap, pastikan Anda meng-copy seluruh folder game, bukan hanya eboot.bin.\n\n"
            f"Missing required PS4 system modules: {', '.join(missing)}.\n"
            f"Native audio mixing and threading require native modules (specifically libSceNgs2.sprx and libSceAjm.sprx) "
            f"to prevent severe audio stuttering and buffer underrun.\n\n"
            f"Please place these modules into '{target_sce}' or '{target_sys}' (or provide 11.00_sys_modules.zip) "
            f"before running Auto-Build."
        )
        raise RuntimeError(err)


def auto_prepare(game_path, out_path, source_hint_dir=None, status_callback=None):
    """
    Auto-builds out/boot-linked.bin, out/content.bin, and out/import_names.txt
    directly from the user's extracted_game/app0 folder.
    """
    game_dir = Path(game_path).resolve()
    out_dir = Path(out_path).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    eboot = game_dir / 'eboot.bin'
    if not eboot.is_file():
        raise FileNotFoundError(f"eboot.bin not found in {game_dir}")

    # 0. Sync and verify all critical PRX/SPRX modules
    if status_callback:
        status_callback("Checking & syncing required PS4 system modules...")
    sync_and_verify_modules(game_dir, source_hint_dir=source_hint_dir, status_callback=status_callback)

    # 1. Parse ELF/SELF and generate initial probe structures
    if status_callback:
        status_callback("Analyzing PS4 executable (eboot.bin)...")
    prepare.prepare(game_dir, out_dir)

    # 2. Link runtime PRX modules
    if status_callback:
        status_callback("Linking runtime modules (libc, fios2, ngs2, etc.)...")
    link_modules.link(game_dir, out_dir)

    # Validate output link.json
    link_json = out_dir / 'link.json'
    if not link_json.is_file():
        raise RuntimeError("Linking failed: out/link.json was not generated!")
    link_data = json.loads(link_json.read_text(encoding='utf-8'))
    mods = link_data.get('modules', [])
    mod_files = [m.get('file', '') for m in mods if isinstance(m, dict)]
    if len(mods) < 7 or "libSceNgs2.sprx" not in mod_files or "libSceAjm.sprx" not in mod_files:
        raise RuntimeError(
            f"Incomplete module linking detected ({len(mods)}/7 modules linked: {mod_files}). "
            f"Missing native audio/threading modules (libSceNgs2/libSceAjm). "
            f"Build aborted to prevent generating a degraded binary."
        )

    # 3. Create offline AppContent profile
    if status_callback:
        status_callback("Configuring AppContent offline profile...")
    content_profile.prepare(game_dir, out_dir, sku='full')

    # 4. Generate import names table
    if status_callback:
        status_callback("Mapping import symbol table...")
    target_names = out_dir / 'import_names.txt'
    if not target_names.exists() or target_names.stat().st_size == 0:
        link_json = out_dir / 'link.json'
        if link_json.exists() and gen_import_names:
            try:
                link_data = json.loads(link_json.read_text(encoding='utf-8'))
                aerolib = out_dir / 'aerolib.inl'
                if not aerolib.exists():
                    # check root out/
                    cand = Path(os.getcwd()) / 'out' / 'aerolib.inl'
                    if cand.exists():
                        aerolib = cand
                names_dict = gen_import_names.aerolib_names(aerolib)
                lines = gen_import_names.generate(link_data.get('unresolved_imports', []), names_dict)
                target_names.write_text('# NID library symbol\n' + '\n'.join(lines) + '\n', encoding='utf-8')
            except Exception as e:
                print(f"Notice: could not generate import_names.txt: {e}")

    final_boot = out_dir / 'boot-linked.bin'
    if not final_boot.exists() or final_boot.stat().st_size == 0:
        raise RuntimeError("Failed to generate out/boot-linked.bin")

    # 5. Build FPS limiter bypass patches (G3PATCH2)
    if status_callback:
        status_callback("Applying high-framerate engine patches...")
    apply_fps_patches(game_dir, out_dir, unlimited_fps=True)

    return True


def apply_fps_patches(game_path, out_path, unlimited_fps=True):
    """
    Generates out/patches.bin to remove the internal 60 FPS limiter in Capcom MT Framework.
    """
    import struct
    game_dir = Path(game_path).resolve()
    out_dir = Path(out_path).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    patches_file = out_dir / 'patches.bin'

    if not unlimited_fps:
        if patches_file.exists():
            try:
                patches_file.unlink()
            except Exception:
                pass
        return []

    eboot = game_dir / 'eboot.bin'
    if not eboot.is_file():
        return []

    try:
        data = eboot.read_bytes()
        elf, _, ph, _, _ = prepare.parse_self(data)
        loads = []
        for p in ph:
            if p['type'] == 1:
                loads.append((p['vaddr'], p['offset'], p['filesz']))
        image = bytearray(max(v + f for v, _, f in loads))
        for vaddr, offset, filesz in loads:
            image[vaddr:vaddr + filesz] = elf[offset:offset + filesz]

        LIMITER = ("c5 e2 5c d0 c5 f2 59 ca c5 f8 2e 0d ?? ?? ?? ?? 72 20 c4 e1 fa 2c c1 69 f8 e8 03 00 00 "
                   "81 c7 18 fc ff ff e8 ?? ?? ?? ?? c5 fa 10 5d cc c5 fa 10 43 60 c5 f8 2e d8 "
                   "c5 fb 10 4d d0 0f 86 ?? ?? ?? ??")
        SLEEP_JB, SPIN_JBE = 16, 59

        pattern = [None if b == '??' else int(b, 16) for b in LIMITER.split()]
        best, run_start = (0, 0), None
        for i, b in enumerate(pattern + [None]):
            if b is not None and run_start is None:
                run_start = i
            if b is None and run_start is not None:
                if i - run_start > best[1] - best[0]:
                    best = (run_start, i)
                run_start = None
        a, b = best
        anchor = bytes(pattern[a:b])
        found = []
        at = image.find(anchor)
        while at >= 0:
            s = at - a
            if s >= 0 and s + len(pattern) <= len(image) and all(
                    p is None or image[s + i] == p for i, p in enumerate(pattern)):
                found.append(s)
            at = image.find(anchor, at + 1)

        if len(found) != 1:
            return []

        base = found[0]
        jbe = base + SPIN_JBE
        disp, = struct.unpack_from('<i', image, jbe + 2)
        writes = [
            (base + SLEEP_JB, b'\xeb\x20'),
            (jbe, b'\xe9' + struct.pack('<i', disp + 1) + b'\x90')
        ]

        EBOOT_BASE = 0x400000
        blob = struct.pack('<8sQQ', b'BBPATCH2', EBOOT_BASE, len(writes))
        for offset, patch_data in writes:
            blob += struct.pack('<QQ', offset, len(patch_data)) + patch_data
        patches_file.write_bytes(blob)
        return writes
    except Exception as e:
        print(f"Notice: could not build patches.bin: {e}")
        return []


if __name__ == '__main__':
    g = sys.argv[1] if len(sys.argv) > 1 else 'extracted_game/app0'
    o = sys.argv[2] if len(sys.argv) > 2 else 'out'
    print(f"Auto-preparing game from {g} into {o}...")
    auto_prepare(g, o, status_callback=print)
    print("Auto-prepare completed successfully!")
