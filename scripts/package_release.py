#!/usr/bin/env python3
"""
Sengoku Basara 4 Sumeragi — Release Packaging Pipeline
Builds a clean, distribution-ready portable ZIP archive and SHA256 checksums.
"""

import os
import sys
import argparse
import hashlib
import zipfile
import subprocess
from pathlib import Path

def get_git_version():
    try:
        res = subprocess.run(["git", "describe", "--tags", "--always"], capture_output=True, text=True, check=True)
        ver = res.stdout.strip()
        if ver.startswith("v"):
            ver = ver[1:]
        return ver
    except Exception:
        return "1.0-update3"

def generate_changelog(version):
    """Generates CHANGELOG.md grouped by conventional commit type from git log."""
    root = Path(__file__).resolve().parent.parent
    changelog_path = root / "CHANGELOG.md"
    try:
        res = subprocess.run(["git", "log", "--pretty=format:%s", "-n", "40"], capture_output=True, text=True, check=True)
        commits = res.stdout.strip().splitlines()
        
        feats, fixes, perfs, docs = [], [], [], []
        others = []
        for c in commits:
            c = c.strip()
            if not c:
                continue
            lower = c.lower()
            if lower.startswith("feat"):
                feats.append(c)
            elif lower.startswith("fix"):
                fixes.append(c)
            elif lower.startswith("perf"):
                perfs.append(c)
            elif lower.startswith("docs"):
                docs.append(c)
            else:
                others.append(c)
        
        lines = [
            f"# Sengoku Basara 4 Sumeragi PC — Release v{version}",
            f"\nPublished: {subprocess.run(['git', 'log', '-1', '--format=%cs'], capture_output=True, text=True).stdout.strip() or 'Latest'}\n"
        ]
        if feats:
            lines.append("### New Features & Enhancements")
            for item in feats:
                lines.append(f"- {item}")
            lines.append("")
        if fixes:
            lines.append("### Stability & Bug Fixes")
            for item in fixes:
                lines.append(f"- {item}")
            lines.append("")
        if perfs:
            lines.append("### Performance & Hybrid Core Optimizations")
            for item in perfs:
                lines.append(f"- {item}")
            lines.append("")
        if docs:
            lines.append("### Documentation & Packaging")
            for item in docs:
                lines.append(f"- {item}")
            lines.append("")
        if others and not (feats or fixes or perfs):
            lines.append("### Changes")
            for item in others[:15]:
                lines.append(f"- {item}")
            lines.append("")

        changelog_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Generated CHANGELOG.md from git log ({len(commits)} commits inspected).")
    except Exception as e:
        if not changelog_path.exists():
            changelog_path.write_text(f"# Release v{version}\n\n- Production release\n", encoding="utf-8")

SYSTEM_DLL_PREFIXES = (
    "api-ms-win-", "ext-ms-win-", "kernel32", "user32", "gdi32", "shell32",
    "advapi32", "ole32", "oleaut32", "comctl32", "comdlg32", "shlwapi",
    "ws2_32", "winhttp", "wininet", "crypt32", "bcrypt", "ntdll", "dxgi",
    "d3d11", "d3d12", "d3d9", "d3dcompiler", "dwmapi", "uxtheme", "imm32",
    "version", "setupapi", "cfgmgr32", "hid", "winmm", "avrt", "dbghelp",
    "iphlpapi", "netapi32", "secur32", "wtsapi32", "userenv", "sensapi",
    "opengl32", "glu32", "vulkan-1", "msvcrt", "ucrtbase",
    "ncrypt", "dnsapi", "usp10", "wsock32", "msimg32", "dwrite", "rpcrt4", "gdiplus"
)

MANDATORY_DLLS = [
    "SDL3.dll",
    "libwinpthread-1.dll",
    "libc++.dll",
    "libunwind.dll",
    "libxxhash.dll",
    "libZydis.dll",
    "avcodec-63.dll",
    "avformat-63.dll",
    "avutil-61.dll",
    "swresample-7.dll",
    "swscale-10.dll",
]

def is_system_dll(name: str) -> bool:
    n = name.lower()
    stem = n[:-4] if n.endswith(".dll") else n
    return stem.startswith(SYSTEM_DLL_PREFIXES) or stem in SYSTEM_DLL_PREFIXES

def collect_runtime_dlls(root_dir: Path) -> list:
    """
    Detects and gathers all required open-source runtime DLLs.
    Scans dependencies of primary executables, copies missing DLLs from MSYS2 Clang64,
    and returns a list of DLL filenames to include in the release.
    """
    import shutil
    search_dirs = [root_dir]
    msystem_prefix = os.environ.get("MSYSTEM_PREFIX")
    if msystem_prefix:
        search_dirs.append(Path(msystem_prefix) / "bin")

    # Common MSYS2 clang64 installation paths
    for candidate in ["F:/msys64/clang64/bin", "C:/msys64/clang64/bin", "D:/msys64/clang64/bin"]:
        p = Path(candidate)
        if p.is_dir() and p not in search_dirs:
            search_dirs.append(p)

    target_exes = ["basara_pc.exe", "basara4-pad-mapper.exe"]
    discovered_dlls = set()

    # Deep dependency resolution using pefile if available
    try:
        import pefile
        queue = [exe for exe in target_exes if (root_dir / exe).is_file()]
        visited = set(x.lower() for x in queue)

        while queue:
            curr = queue.pop(0)
            found_path = None
            for d in search_dirs:
                candidate = d / curr
                if candidate.is_file():
                    found_path = candidate
                    break

            if not found_path:
                continue

            if curr.lower().endswith(".dll"):
                dest_file = root_dir / found_path.name
                if not dest_file.is_file():
                    shutil.copy2(found_path, dest_file)
                    print(f"  [STAGING] Copied {found_path.name} from {found_path.parent}")
                discovered_dlls.add(dest_file.name)

            try:
                pe = pefile.PE(str(found_path), fast_load=True)
                pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
                if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
                    for entry in pe.DIRECTORY_ENTRY_IMPORT:
                        dll_name = entry.dll.decode("utf-8", errors="ignore").strip()
                        if not is_system_dll(dll_name) and dll_name.lower() not in visited:
                            visited.add(dll_name.lower())
                            queue.append(dll_name)
            except Exception:
                pass
    except ImportError:
        print("[WARN] pefile module not available; falling back to mandatory list and root directory scan.")

    # Guarantee all mandatory DLLs are present
    for mand in MANDATORY_DLLS:
        target = root_dir / mand
        if not target.is_file():
            for d in search_dirs:
                candidate = d / mand
                if candidate.is_file():
                    shutil.copy2(candidate, target)
                    print(f"  [STAGING] Copied mandatory {mand} from {d}")
                    break
        if target.is_file():
            discovered_dlls.add(target.name)

    # Include all non-system DLLs present in root_dir
    for f in root_dir.glob("*.dll"):
        if not is_system_dll(f.name):
            discovered_dlls.add(f.name)

    dll_list = sorted(list(discovered_dlls), key=lambda s: s.lower())
    print(f"Collected {len(dll_list)} runtime DLL(s) for release.")
    return dll_list

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def package_release(version=None, out_dir="dist"):
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)

    if not version:
        version = get_git_version()

    print(f"=== Packaging Basara 4 Sumeragi PC (v{version}) ===")

    out_path = root / out_dir
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Generate VERSION.txt & CHANGELOG.md
    version_file = root / "VERSION.txt"
    version_file.write_text(f"v{version}\n", encoding="utf-8")
    generate_changelog(version)

    # 2. File Manifest (Strict Whitelist, NO copyrighted assets or build caches)
    manifest = [
        "basara_pc.exe",
        "Basara4_Launcher.exe",
        "basara4-pad-mapper.exe",
        "launcher.py",
        "Play_Basara4.bat",
        "basara.ini",
        "README.md",
        "README.id.md",
        "LICENSE.txt",
        "THIRD_PARTY_LICENSES.md",
        "PRIVACY.md",
        "CHANGELOG.md",
        "VERSION.txt",
        os.path.join("packaging", "windows", "icons", "basara4.ico"),
        os.path.join("packaging", "windows", "basara.manifest"),
        os.path.join("packaging", "windows", "launcher.manifest"),
    ]

    existing_files = []
    for rel_path in manifest:
        full_path = root / rel_path
        if full_path.is_file():
            existing_files.append(rel_path)
        else:
            if rel_path in ("basara_pc.exe", "launcher.py", "basara.ini"):
                raise FileNotFoundError(f"Critical release artifact missing: {rel_path}")
            print(f"[WARN] Optional file omitted: {rel_path}")

    # 3. Collect Runtime DLLs
    runtime_dlls = collect_runtime_dlls(root)
    existing_files.extend(runtime_dlls)

    # 4. Compute Checksums
    checksum_lines = []
    for rel_path in existing_files:
        sha = compute_sha256(root / rel_path)
        checksum_lines.append(f"{sha}  {rel_path.replace(os.sep, '/')}\n")

    checksum_file = root / "CHECKSUMS.txt"
    checksum_file.write_text("".join(checksum_lines), encoding="utf-8")
    existing_files.append("CHECKSUMS.txt")

    # 5. Create Portable ZIP
    zip_filename = f"Basara4_Sumeragi_PC_v{version}.zip"
    zip_dest = out_path / zip_filename
    root_folder = f"Basara4_Sumeragi_PC_v{version}"

    print(f"Building ZIP archive: {zip_dest}")
    with zipfile.ZipFile(zip_dest, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for rel_path in existing_files:
            archive_name = f"{root_folder}/{rel_path.replace(os.sep, '/')}"
            zf.write(root / rel_path, arcname=archive_name)

        # Include empty user/ directory with placeholder
        zf.writestr(f"{root_folder}/user/.gitkeep", "")

    size_mb = zip_dest.stat().st_size / (1024 * 1024)
    print(f"SUCCESS: Package created -> {zip_dest} ({size_mb:.2f} MB)")
    if size_mb > 100:
        print(f"[WARNING] Archive size ({size_mb:.2f} MB) exceeds recommended 100 MB budget!")

    return zip_dest

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Package Sengoku Basara 4 Sumeragi PC release")
    parser.add_argument("--version", type=str, help="Release version (e.g. 1.0-update3)")
    parser.add_argument("--out-dir", type=str, default="dist", help="Output directory")
    args = parser.parse_args()

    package_release(version=args.version, out_dir=args.out_dir)
