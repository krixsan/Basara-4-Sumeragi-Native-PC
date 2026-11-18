"""Discover, inspect, validate, and batch-install Basara 4 Sumeragi (CUSA01159) DLC sources."""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
try:
    import content_profile as _cp_mod
    _CP_EMBEDDED = True
except ImportError:
    _CP_EMBEDDED = False
import sys
import zipfile

EXPECTED_TITLE_ID = "CUSA01159"
MAX_ENTRIES = 4096
PKG_MAGIC = b"\x7fCNT"

_CATEGORY_PREFIXES = (
    ("PLCOS", "Kostum"),
    ("DLCXBGM", "BGM"),
    ("DLCXUNLOCK", "Unlock"),
)


def _parse_sfo(data):
    if len(data) < 20:
        raise ValueError("param.sfo is truncated")
    magic, _version, key_offset, data_offset, count = struct.unpack_from("<4sIIII", data)
    if magic != b"\0PSF" or count > MAX_ENTRIES:
        raise ValueError("invalid param.sfo")
    index_end = 20 + count * 16
    if not index_end <= key_offset <= data_offset <= len(data):
        raise ValueError("invalid param.sfo offsets")

    values = {}
    for index in range(count):
        key_at, _format, length, _maximum, value_at = struct.unpack_from(
            "<HHIII", data, 20 + index * 16)
        key_start = key_offset + key_at
        key_end = data.find(b"\0", key_start, data_offset)
        value_start = data_offset + value_at
        value_end = value_start + length
        if key_start >= data_offset or key_end < 0 or value_end > len(data):
            raise ValueError("param.sfo entry is out of bounds")
        key = data[key_start:key_end].decode("utf-8", "replace")
        value = data[value_start:value_end].split(b"\0", 1)[0].decode("utf-8", "replace")
        values[key] = value
    return values


def _validate_addon_sfo(values):
    """Validate parsed param.sfo values for CUSA01159 add-on metadata."""
    content_id = values.get("CONTENT_ID", "")
    title_id = values.get("TITLE_ID", "")
    category = values.get("CATEGORY", "")
    if title_id != EXPECTED_TITLE_ID:
        raise ValueError(f"folder is for {title_id or 'an unknown title'}, not {EXPECTED_TITLE_ID}")
    if category != "ac" or len(content_id) <= 20:
        raise ValueError("metadata does not identify a Basara 4 add-on")
    label = content_id[20:]
    try:
        encoded_label = label.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("DLC entitlement label is not ASCII") from error
    if len(encoded_label) != 16 or any(
            not (char.isalnum() or char == "_") for char in label):
        raise ValueError("invalid DLC entitlement label in CONTENT_ID")
    return {
        "title": values.get("TITLE") or label,
        "content_id": content_id,
        "title_id": title_id,
        "label": label,
    }


def categorize_dlc(label, content_id="", title=""):
    """Classify an add-on entitlement into a readable UI category."""
    probe = (label or content_id or title or "").upper()
    for prefix, cat in _CATEGORY_PREFIXES:
        if probe.startswith(prefix):
            return cat
    return "Unlock" if "UNLOCK" in probe else "Add-on"


def read_extracted_dlc(path):
    """Return user-visible metadata for a valid extracted add-on directory."""
    path = Path(path)
    if not path.is_dir():
        raise ValueError("not a DLC folder")
    values = _parse_sfo((path / "sce_sys" / "param.sfo").read_bytes())
    return _validate_addon_sfo(values)


def _read_pkg_sfo_stream(stream):
    """Parse unencrypted entry 0x1000 (param.sfo) from a binary PS4 PKG stream."""
    header = stream.read(0x4000)
    if len(header) < 0x20 or header[:4] != PKG_MAGIC:
        raise ValueError("not a PS4 package")
    count, = struct.unpack_from(">I", header, 0x10)
    table, = struct.unpack_from(">I", header, 0x18)
    need_end = table + count * 32
    if count > MAX_ENTRIES or table < 0x20 or need_end > 0x200000:
        raise ValueError("invalid PS4 PKG entry table")
    if need_end > len(header):
        header += stream.read(need_end - len(header))
    entries = header[table:need_end]
    for i in range(count):
        eid, _name, flags1, _flags2, offset, size = struct.unpack_from(">IIIIII", entries, i * 32)
        if eid == 0x1000:
            if flags1 & 0x80000000:
                raise ValueError("param.sfo is encrypted")
            end = offset + size
            if end > len(header):
                if end > 0x400000:
                    raise ValueError("param.sfo offset exceeds limit")
                header += stream.read(end - len(header))
            return _validate_addon_sfo(_parse_sfo(header[offset:end]))
    raise ValueError("no param.sfo in package")


def read_pkg_dlc(path):
    """Return metadata from an unencrypted param.sfo inside a PS4 .pkg file."""
    with open(path, "rb") as f:
        return _read_pkg_sfo_stream(f)


def scan_extracted_dlc(folder, recursive=False):
    """Return sorted (path, metadata, error) records for extracted DLC folders."""
    if folder is None or not str(folder).strip():
        return []
    folder = Path(folder)
    if not folder.is_dir():
        return [(folder, None, "DLC folder does not exist")]
    candidates = []
    if recursive:
        visited = set()
        for dirpath, dirnames, _ in os.walk(folder, followlinks=True):
            cur = Path(dirpath)
            real = os.path.normcase(os.path.realpath(cur))
            if real in visited:
                dirnames[:] = []
                continue
            visited.add(real)
            dirnames.sort(key=str.casefold)
            if (cur / "sce_sys" / "param.sfo").is_file():
                candidates.append(cur)
    else:
        candidates = sorted(
            (p for p in folder.iterdir() if p.is_dir() and (p / "sce_sys" / "param.sfo").is_file()),
            key=lambda item: item.name.casefold(),
        )
    records = []
    for path in candidates:
        try:
            records.append((path, read_extracted_dlc(path), ""))
        except (OSError, ValueError, struct.error) as error:
            records.append((path, None, str(error)))
    return records


def _inspect_zip_archive(zip_path):
    """Inspect a .zip archive cleanly without loading large binaries into RAM."""
    results = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            sfo_members = [n for n in names if n.lower().endswith("/sce_sys/param.sfo") or n.lower() == "sce_sys/param.sfo"]
            dlcp_members = [n for n in names if n.lower().endswith(".dlcp")]
            pkg_members = [n for n in names if n.lower().endswith(".pkg")]
            save_members = [n for n in names if Path(n).name.upper() == "BSR4_SUMERAGI.DAT"]

            if save_members:
                results.append({
                    "key": f"save:{zip_path.name}",
                    "label": "SAVEDATA",
                    "title": f"Save Data / Weapon Pack ({zip_path.name})",
                    "category": "Save Data",
                    "kind": "zip_save",
                    "source": zip_path,
                    "parent_dir": zip_path.parent,
                    "dlcp_files": [],
                    "zip_members": save_members,
                    "has_payload": True,
                    "priority": 2,
                    "error": "",
                })

            for sfo_m in sorted(sfo_members):
                prefix = sfo_m[:-len("sce_sys/param.sfo")]
                folder_prefix = prefix.rstrip("/")
                sibling_save = any(m.startswith(prefix) and m.upper().endswith("BSR4_SUMERAGI.DAT") for m in names)
                if sibling_save:
                    continue
                try:
                    info = _validate_addon_sfo(_parse_sfo(zf.read(sfo_m)))
                except (KeyError, ValueError, struct.error):
                    continue
                matched_dlcps = [m for m in dlcp_members if m.startswith(prefix)]
                results.append({
                    "key": info["label"],
                    "label": info["label"],
                    "title": info["title"],
                    "category": categorize_dlc(info["label"], info["content_id"], info["title"]),
                    "kind": "zip_addon",
                    "source": zip_path,
                    "parent_dir": zip_path.parent,
                    "dlcp_files": matched_dlcps,
                    "zip_members": [m for m in names if m.startswith(prefix)],
                    "zip_prefix": prefix,
                    "folder_name": Path(folder_prefix).name if folder_prefix else f"JP0102-{EXPECTED_TITLE_ID}_00-{info['label']}",
                    "has_payload": True,
                    "priority": 2,
                    "error": "",
                })

            if not sfo_members and dlcp_members:
                for dm in sorted(dlcp_members):
                    stem = Path(dm).name
                    results.append({
                        "key": f"dlcp:{stem.lower()}",
                        "label": "",
                        "title": stem,
                        "category": "Arsip",
                        "kind": "zip_dlcp",
                        "source": zip_path,
                        "parent_dir": zip_path.parent,
                        "dlcp_files": [dm],
                        "zip_members": [dm],
                        "has_payload": True,
                        "priority": 2,
                        "error": "",
                    })

            for pm in sorted(pkg_members):
                try:
                    with zf.open(pm, "r") as zstream:
                        info = _read_pkg_sfo_stream(zstream)
                    is_unlock = info["label"].upper().startswith("DLCXUNLOCK")
                    results.append({
                        "key": info["label"],
                        "label": info["label"],
                        "title": info["title"],
                        "category": categorize_dlc(info["label"], info["content_id"], info["title"]),
                        "kind": "zip_pkg",
                        "source": zip_path,
                        "parent_dir": zip_path.parent,
                        "dlcp_files": [],
                        "zip_members": [pm],
                        "has_payload": is_unlock,
                        "priority": 1,
                        "error": "" if is_unlock else ".pkg di dalam ZIP belum diekstrak ke .dlcp",
                    })
                except (OSError, KeyError, ValueError, struct.error):
                    continue
    except (OSError, zipfile.BadZipFile) as err:
        results.append({
            "key": f"err:{zip_path.name}",
            "label": "",
            "title": zip_path.name,
            "category": "Error",
            "kind": "invalid",
            "source": zip_path,
            "parent_dir": zip_path.parent,
            "dlcp_files": [],
            "has_payload": False,
            "priority": 0,
            "error": str(err),
        })
    return results


def scan_dlc_sources(sources):
    """Scan mixed folders (recursively), .dlcp files, .zip archives, and .pkg packages.

    Deduplicates entries by entitlement label (or filename for standalone .dlcp), keeping the
    highest-priority actionable item (extracted folder > zip addon > loose dlcp > raw .pkg).
    """
    if not sources:
        return []
    candidates = []
    claimed_dlcps = set()
    visited_dirs = set()

    def _register_dir(addon_dir):
        if (addon_dir / "BSR4_SUMERAGI.DAT").is_file():
            return
        dlcps = sorted(p for p in addon_dir.iterdir() if p.is_file() and p.suffix.lower() == ".dlcp")
        try:
            info = read_extracted_dlc(addon_dir)
            for p in dlcps:
                claimed_dlcps.add(os.path.normcase(os.path.abspath(str(p))))
            is_unlock = info["label"].upper().startswith("DLCXUNLOCK")
            has_data = bool(dlcps) or is_unlock
            candidates.append({
                "key": info["label"],
                "label": info["label"],
                "title": info["title"],
                "category": categorize_dlc(info["label"], info["content_id"], info["title"]),
                "kind": "addon_dir",
                "source": addon_dir,
                "parent_dir": addon_dir.parent,
                "dlcp_files": dlcps,
                "folder_name": addon_dir.name,
                "has_payload": has_data,
                "priority": 4 if has_data else 3,
                "error": "" if has_data else "Folder add-on tidak berisi file .dlcp",
            })
        except (OSError, ValueError, struct.error) as error:
            if dlcps:
                for p in dlcps:
                    claimed_dlcps.add(os.path.normcase(os.path.abspath(str(p))))
                candidates.append({
                    "key": f"dir:{addon_dir.name.lower()}",
                    "label": "",
                    "title": f"{addon_dir.name} ({error})",
                    "category": "Arsip",
                    "kind": "addon_dir_no_label",
                    "source": addon_dir,
                    "parent_dir": addon_dir.parent,
                    "dlcp_files": dlcps,
                    "folder_name": addon_dir.name,
                    "has_payload": True,
                    "priority": 2,
                    "error": str(error),
                })

    loose_dlcps = []
    pkg_files = []
    zip_files = []

    for raw in sources:
        if not raw:
            continue
        p = Path(raw)
        if p.is_file():
            ext = p.suffix.lower()
            if ext == ".dlcp":
                loose_dlcps.append(p)
            elif ext == ".pkg":
                pkg_files.append(p)
            elif ext == ".zip":
                zip_files.append(p)
            continue
        if not p.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(p, followlinks=True):
            cur = Path(dirpath)
            real = os.path.normcase(os.path.realpath(cur))
            if real in visited_dirs:
                dirnames[:] = []
                continue
            visited_dirs.add(real)
            dirnames.sort(key=str.casefold)
            if (cur / "sce_sys" / "param.sfo").is_file():
                _register_dir(cur)
            for fname in sorted(filenames, key=str.casefold):
                fpath = cur / fname
                ext = fpath.suffix.lower()
                if ext == ".dlcp":
                    loose_dlcps.append(fpath)
                elif ext == ".pkg":
                    pkg_files.append(fpath)
                elif ext == ".zip":
                    zip_files.append(fpath)

    for p in pkg_files:
        try:
            info = read_pkg_dlc(p)
            is_unlock = info["label"].upper().startswith("DLCXUNLOCK")
            candidates.append({
                "key": info["label"],
                "label": info["label"],
                "title": info["title"],
                "category": categorize_dlc(info["label"], info["content_id"], info["title"]),
                "kind": "pkg",
                "source": p,
                "parent_dir": p.parent,
                "dlcp_files": [],
                "has_payload": is_unlock,
                "priority": 1,
                "error": "" if is_unlock else ".pkg mentah (ekstrak ke folder/.dlcp agar aset terbaca)",
            })
        except (OSError, ValueError, struct.error):
            continue

    for zp in zip_files:
        candidates.extend(_inspect_zip_archive(zp))

    for dp in loose_dlcps:
        norm = os.path.normcase(os.path.abspath(str(dp)))
        if norm in claimed_dlcps:
            continue
        candidates.append({
            "key": f"dlcp:{dp.name.lower()}",
            "label": "",
            "title": dp.name,
            "category": "Arsip",
            "kind": "dlcp_file",
            "source": dp,
            "parent_dir": dp.parent,
            "dlcp_files": [dp],
            "has_payload": True,
            "priority": 2,
            "error": "",
        })

    dedup = {}
    for entry in candidates:
        k = entry["key"]
        prev = dedup.get(k)
        if prev is None or entry["priority"] > prev["priority"]:
            dedup[k] = entry

    order = {"Kostum": 0, "BGM": 1, "Unlock": 2, "Arsip": 3, "Add-on": 4, "Save Data": 5, "Error": 6}
    return sorted(
        dedup.values(),
        key=lambda e: (order.get(e["category"], 9), (e["label"] or e["title"]).casefold()),
    )


def _is_reparse_point(path):
    """True if path is a symlink or Windows directory junction."""
    if path.is_symlink():
        return True
    if hasattr(path, "is_junction") and path.is_junction():
        return True
    try:
        attrs = getattr(os.lstat(path), "st_file_attributes", 0)
        return bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return False


def _remove_dir_or_junction_safe(path):
    """Remove a junction/symlink or folder without descending through junction targets."""
    path = Path(path)
    if not path.exists() and not _is_reparse_point(path):
        return
    if _is_reparse_point(path):
        try:
            os.rmdir(path)
        except OSError:
            os.unlink(path)
        return
    if path.is_dir():
        for child in list(path.iterdir()):
            _remove_dir_or_junction_safe(child)
        path.rmdir()
    else:
        path.unlink()


def _link_or_copy_file(src, dst):
    """Create an NTFS hardlink (fallback copy) from src to dst."""
    src_p = Path(src)
    dst_p = Path(dst)
    if os.path.abspath(src_p) == os.path.abspath(dst_p):
        return True
    if dst_p.exists():
        try:
            dst_p.unlink()
        except OSError:
            pass
    try:
        os.link(src_p, dst_p)
        return True
    except OSError:
        pass
    if os.name == "nt":
        try:
            res = subprocess.run(
                ["cmd", "/c", "mklink", "/H", str(dst_p), str(src_p)],
                capture_output=True, text=True,
            )
            if res.returncode == 0:
                return True
        except OSError:
            pass
    try:
        shutil.copy2(src_p, dst_p)
        return True
    except OSError:
        return False


def _junction_or_copy_dir(src, dst):
    """Link a directory via Windows junction/symlink (fallback copytree)."""
    src_p = Path(src)
    dst_p = Path(dst)
    if _is_reparse_point(dst_p) or dst_p.exists():
        _remove_dir_or_junction_safe(dst_p)
    try:
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(src_p.resolve()), str(dst_p))
        else:
            dst_p.symlink_to(src_p.resolve(), target_is_directory=True)
        return True
    except OSError:
        pass
    if os.name == "nt":
        try:
            res = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(dst_p), str(src_p.resolve())],
                capture_output=True, text=True,
            )
            if res.returncode == 0:
                return True
        except OSError:
            pass
    try:
        shutil.copytree(src_p, dst_p)
        return True
    except OSError:
        return False


def _safe_extract_zip_members(zip_path, members, dest_dir, strip_prefix=""):
    """Safely extract selected zip members under dest_dir, preventing path traversal."""
    dest_root = Path(dest_dir).resolve()
    dest_root.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in members:
            if member.endswith("/"):
                continue
            rel_name = member[len(strip_prefix):] if strip_prefix and member.startswith(strip_prefix) else member
            rel_parts = [p for p in Path(rel_name).parts if p not in ("", ".", "..")]
            if not rel_parts:
                continue
            target = (dest_root / Path(*rel_parts)).resolve()
            if not target.is_relative_to(dest_root):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, "r") as src_f, open(target, "wb") as out_f:
                shutil.copyfileobj(src_f, out_f)
            extracted.append(target)
    return extracted


def install_dlc_batch(
    base_dir,
    app0_dir,
    selected_entries,
    all_entries=None,
    script_path=None,
    progress_cb=None,
    lang="id",
):
    """Install multiple DLC folders, loose .dlcp files, .zip archives, and .pkg entries at once.

    Returns dict with addon_count, links_created, active_dlc_dir, disabled_labels,
    savedata_updated, warnings, and error.
    """
    base = Path(base_dir)
    app0 = Path(app0_dir)
    entries = list(selected_entries or [])
    known = list(all_entries if all_entries is not None else entries)

    target_dirs = [
        base / "extracted_game" / "addcont",
        base / "extracted_game" / "app0" / "addcont",
        base / "extracted_game" / "app0" / "dlc",
    ]
    for d in target_dirs:
        d.mkdir(parents=True, exist_ok=True)

    warnings = []
    imported_root = base / "DLC" / "Imported"
    addon_dirs = []
    dlcp_sources = []
    pkg_sources = []
    savedata_updated = False

    def _step(msg):
        if progress_cb:
            progress_cb(msg)

    for idx, entry in enumerate(entries, start=1):
        kind = entry.get("kind", "")
        title = entry.get("title") or entry.get("label") or ""
        if idx == 1 or idx % 10 == 0 or idx == len(entries):
            _step(get_dlc_ui_text("step_pkg", lang, idx=idx, total=len(entries), title=title))

        if kind == "addon_dir":
            src_dir = Path(entry["source"])
            addon_dirs.append(src_dir)
            dlcp_sources.extend(Path(p) for p in entry.get("dlcp_files", []))
        elif kind in ("addon_dir_no_label", "dlcp_file"):
            dlcp_sources.extend(Path(p) for p in entry.get("dlcp_files", []))
        elif kind == "zip_addon":
            folder_name = entry.get("folder_name") or f"JP0102-{EXPECTED_TITLE_ID}_00-{entry['label']}"
            dest = imported_root / folder_name
            _safe_extract_zip_members(
                entry["source"], entry.get("zip_members", []), dest, entry.get("zip_prefix", "")
            )
            addon_dirs.append(dest)
            dlcp_sources.extend(sorted(p for p in dest.iterdir() if p.is_file() and p.suffix.lower() == ".dlcp"))
        elif kind == "zip_dlcp":
            dest = imported_root / "_LooseDLCP"
            extracted = _safe_extract_zip_members(entry["source"], entry.get("zip_members", []), dest)
            dlcp_sources.extend(p for p in extracted if p.suffix.lower() == ".dlcp")
        elif kind == "zip_save":
            save_dest = base / "user" / "savedata" / "1" / EXPECTED_TITLE_ID / f"{EXPECTED_TITLE_ID}0000"
            save_dest.mkdir(parents=True, exist_ok=True)
            dat_path = save_dest / "BSR4_SUMERAGI.DAT"
            if dat_path.is_file():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(dat_path, save_dest / f"BSR4_SUMERAGI.DAT.bak_{ts}")
            with zipfile.ZipFile(entry["source"], "r") as zf:
                for member in entry.get("zip_members", []):
                    if Path(member).name.upper() == "BSR4_SUMERAGI.DAT":
                        with zf.open(member, "r") as src_f, open(dat_path, "wb") as out_f:
                            shutil.copyfileobj(src_f, out_f)
                        savedata_updated = True
        elif kind == "pkg":
            pkg_sources.append(Path(entry["source"]))
            if not entry.get("has_payload", False):
                warnings.append(f"{entry.get('label') or Path(entry['source']).name}: .pkg mentah tanpa .dlcp")
        elif kind == "zip_pkg":
            warnings.append(f"{entry.get('label')}: .pkg di ZIP belum diekstrak ke .dlcp")

    # Deduplicate .dlcp paths preserving order
    unique_dlcps = []
    seen_dlcp = set()
    for dp in dlcp_sources:
        norm = os.path.normcase(os.path.abspath(str(dp)))
        if norm not in seen_dlcp and dp.is_file():
            seen_dlcp.add(norm)
            unique_dlcps.append(dp)

    _step(get_dlc_ui_text("step_link", lang, n=len(unique_dlcps)))
    links_created = 0
    for src in unique_dlcps:
        for tdir in target_dirs:
            if _link_or_copy_file(src, tdir / src.name):
                links_created += 1

    # Remove hardlinks of explicitly unchecked .dlcp items so unchecking actually deactivates them
    selected_keys = {e.get("key") for e in entries}
    for entry in known:
        if entry.get("key") in selected_keys:
            continue
        for dp in entry.get("dlcp_files", []):
            fname = Path(dp).name
            if not fname.lower().endswith(".dlcp"):
                continue
            for tdir in target_dirs:
                victim = tdir / fname
                if victim.is_file():
                    try:
                        victim.unlink()
                    except OSError:
                        pass

    selected_labels = {e.get("label") for e in entries if e.get("label") and e.get("label") != "SAVEDATA"}
    disabled_labels = sorted({
        e.get("label") for e in known
        if e.get("label") and e.get("label") != "SAVEDATA" and e.get("label") not in selected_labels
    })

    # Choose canonical flat DLC folder for C runtime compatibility
    active_dlc_dir = None
    unique_addons = []
    seen_dirs = set()
    for ad in addon_dirs:
        norm = os.path.normcase(os.path.realpath(str(ad)))
        if norm not in seen_dirs and ad.is_dir():
            seen_dirs.add(norm)
            unique_addons.append(ad)

    parent_dirs = {os.path.normcase(os.path.realpath(str(ad.parent))): ad.parent for ad in unique_addons}
    if len(parent_dirs) == 1:
        only_parent = next(iter(parent_dirs.values()))
        # Only use parent directly if it doesn't contain unrelated unmounted sibling folders
        siblings = {
            os.path.normcase(os.path.realpath(str(p)))
            for p in only_parent.iterdir()
            if p.is_dir() and (p / "sce_sys" / "param.sfo").is_file()
        }
        if siblings == seen_dirs or (len(siblings) >= len(seen_dirs) and not disabled_labels):
            active_dlc_dir = only_parent

    out_dir = base / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    if active_dlc_dir is None and unique_addons:
        staging = out_dir / "dlc_active"
        if staging.exists() or _is_reparse_point(staging):
            _remove_dir_or_junction_safe(staging)
        staging.mkdir(parents=True, exist_ok=True)
        for ad in unique_addons:
            _junction_or_copy_dir(ad, staging / ad.name)
        active_dlc_dir = staging

    profile_roots = []
    if active_dlc_dir:
        profile_roots.append(active_dlc_dir)
    for pk in pkg_sources:
        profile_roots.append(pk)

    addon_count = len(unique_addons)

    if profile_roots or not entries:
        _step(get_dlc_ui_text("step_bin", lang))
        # --- Direct import (embedded in .exe, no external Python needed) ---
        if _CP_EMBEDDED:
            try:
                _env_bak = {}
                def _setenv(k, v):
                    _env_bak[k] = os.environ.get(k)
                    os.environ[k] = v
                def _delenv(k):
                    _env_bak[k] = os.environ.pop(k, None)

                if not entries:
                    _setenv("BB_DLC", "0")
                    _delenv("BB_DLC_DISABLED")
                else:
                    _delenv("BB_DLC")
                    if disabled_labels:
                        _setenv("BB_DLC_DISABLED", ",".join(disabled_labels))
                    else:
                        _delenv("BB_DLC_DISABLED")

                _cp_mod.prepare(app0, out_dir, "full", [str(r) for r in profile_roots] or None)

                # Restore env
                for k, v in _env_bak.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            except Exception as _cp_err:
                return {
                    "addon_count": 0,
                    "links_created": links_created,
                    "active_dlc_dir": active_dlc_dir,
                    "disabled_labels": disabled_labels,
                    "savedata_updated": savedata_updated,
                    "warnings": warnings,
                    "error": f"Gagal men-generate profil DLC: {_cp_err}",
                }
        else:
            # Fallback: subprocess (butuh Python terinstall + file .py di disk)
            if script_path is None:
                cand = base / "tools" / "content_profile.py"
                if not cand.is_file():
                    cand = base / "scripts" / "content_profile.py"
                script_path = cand
            script_path = Path(script_path)
            if not script_path.is_file():
                return {
                    "addon_count": 0,
                    "links_created": links_created,
                    "active_dlc_dir": active_dlc_dir,
                    "disabled_labels": disabled_labels,
                    "savedata_updated": savedata_updated,
                    "warnings": warnings,
                    "error": "DLC profile generator tidak tersedia. Jalankan via Basara4_Launcher.exe.",
                }
            cmd = [sys.executable, str(script_path), str(app0), "--out", str(out_dir)]
            for root_arg in profile_roots:
                cmd.extend(["--dlc-dir", str(root_arg)])
            env = os.environ.copy()
            scripts_path = str(base / "scripts")
            env["PYTHONPATH"] = scripts_path + os.pathsep + env.get("PYTHONPATH", "")
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            if not entries:
                env["BB_DLC"] = "0"
                env.pop("BB_DLC_DISABLED", None)
            else:
                env.pop("BB_DLC", None)
                if disabled_labels:
                    env["BB_DLC_DISABLED"] = ",".join(disabled_labels)
                else:
                    env.pop("BB_DLC_DISABLED", None)
            proc = subprocess.run(
                cmd,
                cwd=str(base),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode != 0:
                err_output = proc.stderr.strip() or proc.stdout.strip()
                return {
                    "addon_count": 0,
                    "links_created": links_created,
                    "active_dlc_dir": active_dlc_dir,
                    "disabled_labels": disabled_labels,
                    "savedata_updated": savedata_updated,
                    "warnings": warnings,
                    "error": f"Gagal men-generate profil DLC:\n{err_output}",
                }
        out_content = out_dir / "content.bin"
        if out_content.is_file():
            shutil.copy2(out_content, base / "content.bin")
        profile_json = out_dir / "content-profile.json"
        if profile_json.is_file():
            try:
                pdata = json.loads(profile_json.read_text(encoding="utf-8"))
                addon_count = len(pdata.get("mounted_addons", []))
            except (OSError, json.JSONDecodeError):
                pass

    return {
        "addon_count": addon_count,
        "links_created": links_created,
        "active_dlc_dir": active_dlc_dir,
        "disabled_labels": disabled_labels,
        "savedata_updated": savedata_updated,
        "warnings": warnings,
        "error": None,
    }


# ==============================================================================
# Multi-Language DLC UI & Category Localization (ID, EN, JA, ZH, ES, PT, RU)
# ==============================================================================

def _norm_dlc_lang(lang):
    s = (lang or "id").strip().lower()
    for code in ("id", "en", "ja", "zh", "es", "pt", "ru"):
        if s.startswith(code):
            return code
    if s.startswith("in"):
        return "id"
    if s.startswith("jp"):
        return "ja"
    if s.startswith("cn"):
        return "zh"
    if s.startswith("br"):
        return "pt"
    return "en"


DLC_CATEGORY_I18N = {
    "Kostum": {
        "id": "Kostum", "en": "Costume", "ja": "特別衣装", "zh": "服装",
        "es": "Traje", "pt": "Traje", "ru": "Костюм",
    },
    "BGM": {
        "id": "BGM", "en": "BGM", "ja": "BGM", "zh": "音乐",
        "es": "BGM", "pt": "BGM", "ru": "Музыка",
    },
    "Unlock": {
        "id": "Unlock", "en": "Unlock", "ja": "全開放", "zh": "解锁",
        "es": "Desbloq.", "pt": "Desbloq.", "ru": "Разблок.",
    },
    "Add-on": {
        "id": "Add-on", "en": "Add-on", "ja": "追加要素", "zh": "追加内容",
        "es": "Complemento", "pt": "Add-on", "ru": "Дополнение",
    },
    "Arsip": {
        "id": "Arsip", "en": "Archive", "ja": "アーカイブ", "zh": "档案",
        "es": "Archivo", "pt": "Arquivo", "ru": "Архив",
    },
    "Save Data": {
        "id": "Save Data", "en": "Save Data", "ja": "セーブ", "zh": "存档",
        "es": "Guardado", "pt": "Save", "ru": "Сохранение",
    },
    "Error": {
        "id": "Error", "en": "Error", "ja": "エラー", "zh": "错误",
        "es": "Error", "pt": "Erro", "ru": "Ошибка",
    },
}


def translate_dlc_category(cat, lang="id"):
    code = _norm_dlc_lang(lang)
    entry = DLC_CATEGORY_I18N.get(cat)
    if entry:
        return entry.get(code, entry.get("en", cat))
    return cat


DLC_UI_I18N = {
    "id": {
        "win_title": "Sengoku Basara 4 — Pengelola & Pemasang DLC Massal",
        "header": "📦 Pemasang DLC Massal · CUSA01159 (Pasang Sekaligus)",
        "subtitle": "Tambahkan folder (scan seluruh subfolder otomatis) atau pilih banyak file (.zip / .dlcp / .pkg) sekaligus, centang yang diinginkan, lalu klik Pasang.",
        "add_dir": "📁 + Tambah Folder",
        "add_files": "📄 + Pilih Banyak File (.zip/.dlcp/.pkg)",
        "rescan": "🔄 Scan Ulang",
        "default": "↺ Default",
        "col_chk": "Pilih",
        "col_name": "Nama DLC",
        "col_cat": "Kategori",
        "col_id": "Entitlement ID",
        "col_status": "Status",
        "col_src": "Sumber",
        "st_save": "💾 Save Weapon Pack",
        "st_need_dlcp": "⚠ Butuh .dlcp",
        "st_need_link": "⏳ Perlu Link .dlcp",
        "st_installed": "✓ Terinstal",
        "st_dlcp_ok": "✓ .dlcp Terpasang",
        "st_ready": "⏳ Siap Dipasang",
        "scanning": "⏳ Memindai folder & arsip DLC...",
        "summary": "{sel} dari {total} item dicentang ({ready} paket DLC siap pasang) · Sumber aktif: {src} · Klik baris / Spasi untuk ubah centang.",
        "sel_all": "☑ Pilih Semua",
        "sel_none": "☐ Lepas Semua",
        "open_dir": "🔍 Buka Folder",
        "install_btn": "🚀 Pasang Semua Terpilih",
        "close": "Tutup",
        "pick_dir": "Tambah Folder DLC (Scan semua subfolder & arsip di dalamnya)",
        "pick_files": "Pilih Banyak File DLC sekaligus (.zip / .dlcp / .pkg)",
        "ft_dlc": "Paket DLC PS4",
        "ft_all": "Semua File",
        "warn_empty_t": "Pasang DLC",
        "warn_empty_b": "Belum ada paket DLC yang ditemukan atau dipilih.",
        "save_conf_t": "Konfirmasi Save Weapon DLC",
        "save_conf_b": "Kamu ikut mencentang Save Data (BSR4_SUMERAGI.DAT).\nSave lama di user/savedata akan di-backup otomatis (.bak) lalu diganti.\n\nLanjutkan?",
        "err_title": "Gagal Memasang DLC",
        "err_app0": "Folder game (app0) tidak ditemukan di 'extracted_game/app0' atau 'app0'.",
        "err_open": "Tidak dapat membuka folder:\n{err}",
        "err_install": "Gagal memasang DLC:\n\n{err}",
        "err_mod": "Modul basara4_dlc.py tidak ditemukan!",
        "installing_btn": "⏳ Memasang...",
        "installing_sum": "⏳ Memasang {n} paket DLC sekaligus...",
        "step_pkg": "⏳ Memproses paket {idx}/{total}: {title}...",
        "step_link": "⏳ Menautkan {n} file .dlcp ke folder VFS game...",
        "step_bin": "⏳ Membuat lisensi offline content.bin...",
        "ok_title": "Pemasangan DLC Berhasil",
        "ok_head": "✓ Berhasil memasang {n} Paket DLC sekaligus!",
        "ok_links": "• {links} file arsip kostum & BGM (.dlcp) telah dipetakan ke VFS game.",
        "ok_bin": "• Lisensi content.bin diperbarui ({size} bytes).",
        "ok_save": "• Save Weapon DLC (BSR4_SUMERAGI.DAT) berhasil dipasang (save lama di-backup).",
        "ok_warn": "• Catatan ({n} item): {first}",
        "ok_foot": "\nSilakan klik MAINKAN GAME untuk memainkan semua DLC terpilih!",
    },
    "en": {
        "win_title": "Sengoku Basara 4 — Batch DLC Installer & Manager",
        "header": "📦 Batch DLC Installer · CUSA01159 (Install All at Once)",
        "subtitle": "Add folders (scans all subfolders recursively) or select multiple files (.zip / .dlcp / .pkg), check the add-ons you want, then click Install.",
        "add_dir": "📁 + Add Folder",
        "add_files": "📄 + Select Files (.zip/.dlcp/.pkg)",
        "rescan": "🔄 Rescan",
        "default": "↺ Default",
        "col_chk": "Pick",
        "col_name": "DLC Title",
        "col_cat": "Category",
        "col_id": "Entitlement ID",
        "col_status": "Status",
        "col_src": "Source",
        "st_save": "💾 Save Weapon Pack",
        "st_need_dlcp": "⚠ Missing .dlcp",
        "st_need_link": "⏳ Needs .dlcp Link",
        "st_installed": "✓ Installed",
        "st_dlcp_ok": "✓ .dlcp Linked",
        "st_ready": "⏳ Ready to Install",
        "scanning": "⏳ Scanning DLC folders & archives...",
        "summary": "{sel} of {total} items checked ({ready} DLC packages ready) · Active sources: {src} · Click row / press Space to toggle.",
        "sel_all": "☑ Select All",
        "sel_none": "☐ Clear All",
        "open_dir": "🔍 Open Folder",
        "install_btn": "🚀 Install Selected",
        "close": "Close",
        "pick_dir": "Add DLC Folder (Recursively scans all subfolders & archives)",
        "pick_files": "Select Multiple DLC Files (.zip / .dlcp / .pkg)",
        "ft_dlc": "PS4 DLC Packages",
        "ft_all": "All Files",
        "warn_empty_t": "Batch DLC Install",
        "warn_empty_b": "No DLC packages were found or selected.",
        "save_conf_t": "Confirm DLC Weapon Save Data",
        "save_conf_b": "You checked the Save Data item (BSR4_SUMERAGI.DAT).\nYour existing save in user/savedata will be backed up (.bak) automatically before replacing.\n\nContinue?",
        "err_title": "DLC Install Error",
        "err_app0": "Game folder (app0) was not found in 'extracted_game/app0' or 'app0'.",
        "err_open": "Could not open folder:\n{err}",
        "err_install": "Failed to install DLC:\n\n{err}",
        "err_mod": "Module basara4_dlc.py was not found!",
        "installing_btn": "⏳ Installing...",
        "installing_sum": "⏳ Installing {n} DLC packages...",
        "step_pkg": "⏳ Processing package {idx}/{total}: {title}...",
        "step_link": "⏳ Linking {n} .dlcp archives into game VFS...",
        "step_bin": "⏳ Generating offline license content.bin...",
        "ok_title": "DLC Installation Complete",
        "ok_head": "✓ Successfully installed {n} DLC packages!",
        "ok_links": "• {links} costume & BGM archive files (.dlcp) linked into game VFS.",
        "ok_bin": "• Offline license content.bin updated ({size} bytes).",
        "ok_save": "• Weapon DLC Save (BSR4_SUMERAGI.DAT) installed (previous save backed up).",
        "ok_warn": "• Note ({n} items): {first}",
        "ok_foot": "\nClick PLAY GAME to enjoy all selected DLC!",
    },
    "ja": {
        "win_title": "戦国BASARA4 皇 — DLC 一括インストーラー＆管理",
        "header": "📦 DLC 一括インストーラー · CUSA01159",
        "subtitle": "フォルダの追加（全サブフォルダを自動検索）または複数ファイル（.zip / .dlcp / .pkg）を選択し、導入したいDLCにチェックを入れてインストールしてください。",
        "add_dir": "📁 + フォルダ追加",
        "add_files": "📄 + ファイル選択 (.zip/.dlcp/.pkg)",
        "rescan": "🔄 再スキャン",
        "default": "↺ 初期設定",
        "col_chk": "選択",
        "col_name": "DLC 名称",
        "col_cat": "種類",
        "col_id": "コンテンツID",
        "col_status": "状態",
        "col_src": "ソース",
        "st_save": "💾 武器セーブパック",
        "st_need_dlcp": "⚠ .dlcp 不足",
        "st_need_link": "⏳ リンク未作成",
        "st_installed": "✓ 導入済み",
        "st_dlcp_ok": "✓ .dlcp 配置済",
        "st_ready": "⏳ 導入可能",
        "scanning": "⏳ DLCフォルダとアーカイブを検索中...",
        "summary": "{total} 件中 {sel} 件選択中（導入可能DLC: {ready} 件）· 参照元: {src} · 行クリックまたはスペースキーで切替",
        "sel_all": "☑ すべて選択",
        "sel_none": "☐ すべて解除",
        "open_dir": "🔍 フォルダを開く",
        "install_btn": "🚀 選択したDLCを一括導入",
        "close": "閉じる",
        "pick_dir": "DLCフォルダを選択（サブフォルダも自動検索されます）",
        "pick_files": "DLCファイルを複数選択 (.zip / .dlcp / .pkg)",
        "ft_dlc": "PS4 DLC パッケージ",
        "ft_all": "すべてのファイル",
        "warn_empty_t": "DLC 一括導入",
        "warn_empty_b": "DLCパッケージが見つからないか、選択されていません。",
        "save_conf_t": "DLC武器セーブデータの確認",
        "save_conf_b": "セーブデータ (BSR4_SUMERAGI.DAT) が選択されています。\n既存の user/savedata 内のデータは自動でバックアップ (.bak) されてから上書きされます。\n\n続行しますか？",
        "err_title": "DLC インストールエラー",
        "err_app0": "ゲームフォルダ (app0) が見つかりません。",
        "err_open": "フォルダを開けませんでした:\n{err}",
        "err_install": "DLCの導入に失敗しました:\n\n{err}",
        "err_mod": "basara4_dlc.py モジュールが見つかりません！",
        "installing_btn": "⏳ 導入中...",
        "installing_sum": "⏳ {n} 個のDLCパッケージを一括導入中...",
        "step_pkg": "⏳ パッケージ処理中 ({idx}/{total}): {title}...",
        "step_link": "⏳ {n} 個の .dlcp ファイルをゲームVFSへリンク中...",
        "step_bin": "⏳ オフラインライセンス content.bin を生成中...",
        "ok_title": "DLC インストール完了",
        "ok_head": "✓ {n} 個のDLCパッケージを一括導入しました！",
        "ok_links": "• {links} 個の衣装・BGMアーカイブ (.dlcp) をVFSにリンクしました。",
        "ok_bin": "• content.bin ライセンスを更新しました（{size} バイト）。",
        "ok_save": "• 特典武器セーブデータ (BSR4_SUMERAGI.DAT) を導入しました（旧データはバックアップ済）。",
        "ok_warn": "• 備考 ({n} 件): {first}",
        "ok_foot": "\n「ゲーム開始」をクリックすると選択した全DLCが反映されます！",
    },
    "zh": {
        "win_title": "战国BASARA4 皇 — DLC 批量安装与管理器",
        "header": "📦 DLC 批量安装器 · CUSA01159（一键全部安装）",
        "subtitle": "添加文件夹（自动扫描所有子目录）或多选文件（.zip / .dlcp / .pkg），勾选需要的 DLC 后点击安装。",
        "add_dir": "📁 + 添加文件夹",
        "add_files": "📄 + 选择多个文件 (.zip/.dlcp/.pkg)",
        "rescan": "🔄 重新扫描",
        "default": "↺ 恢复默认",
        "col_chk": "选择",
        "col_name": "DLC 名称",
        "col_cat": "分类",
        "col_id": "授权 ID",
        "col_status": "状态",
        "col_src": "来源",
        "st_save": "💾 特典武器存档",
        "st_need_dlcp": "⚠ 缺少 .dlcp",
        "st_need_link": "⏳ 需链接 .dlcp",
        "st_installed": "✓ 已安装",
        "st_dlcp_ok": "✓ .dlcp 已挂载",
        "st_ready": "⏳ 可安装",
        "scanning": "⏳ 正在扫描 DLC 文件夹与压缩包...",
        "summary": "已勾选 {sel} / {total} 项（{ready} 个可用 DLC 包）· 活动目录: {src} · 点击行或按空格键切换勾选",
        "sel_all": "☑ 全选",
        "sel_none": "☐ 全不选",
        "open_dir": "🔍 打开目录",
        "install_btn": "🚀 批量安装已选项",
        "close": "关闭",
        "pick_dir": "选择 DLC 文件夹（自动递归扫描所有子目录）",
        "pick_files": "多选 DLC 文件 (.zip / .dlcp / .pkg)",
        "ft_dlc": "PS4 DLC 数据包",
        "ft_all": "所有文件",
        "warn_empty_t": "批量安装 DLC",
        "warn_empty_b": "未找到或未勾选任何 DLC 数据包。",
        "save_conf_t": "确认覆盖特典武器存档",
        "save_conf_b": "您勾选了存档文件 (BSR4_SUMERAGI.DAT)。\nuser/savedata 中的旧存档将自动备份为 .bak 后替换。\n\n是否继续？",
        "err_title": "DLC 安装错误",
        "err_app0": "未在 'extracted_game/app0' 或 'app0' 找到游戏目录。",
        "err_open": "无法打开文件夹:\n{err}",
        "err_install": "安装 DLC 失败:\n\n{err}",
        "err_mod": "未找到 basara4_dlc.py 模块！",
        "installing_btn": "⏳ 安装中...",
        "installing_sum": "⏳ 正在批量安装 {n} 个 DLC 数据包...",
        "step_pkg": "⏳ 正在处理第 {idx}/{total} 项: {title}...",
        "step_link": "⏳ 正在将 {n} 个 .dlcp 文件映射至游戏目录...",
        "step_bin": "⏳ 正在生成离线授权文件 content.bin...",
        "ok_title": "DLC 安装成功",
        "ok_head": "✓ 已成功批量安装 {n} 个 DLC 数据包！",
        "ok_links": "• 已映射 {links} 个服装与音乐档案 (.dlcp) 到游戏虚拟文件系统。",
        "ok_bin": "• 已更新离线许可证 content.bin（{size} 字节）。",
        "ok_save": "• 特典武器存档 (BSR4_SUMERAGI.DAT) 已安装（原存档已备份）。",
        "ok_warn": "• 提示 ({n} 项): {first}",
        "ok_foot": "\n点击「开始游戏」即可畅玩所有已安装的 DLC！",
    },
    "es": {
        "win_title": "Sengoku Basara 4 — Instalador y Gestor de DLC por Lotes",
        "header": "📦 Instalador de DLC por Lotes · CUSA01159",
        "subtitle": "Añade carpetas (escanea subcarpetas automáticamente) o elige varios archivos (.zip / .dlcp / .pkg), marca los deseados y pulsa Instalar.",
        "add_dir": "📁 + Añadir Carpeta",
        "add_files": "📄 + Elegir Archivos (.zip/.dlcp/.pkg)",
        "rescan": "🔄 Re-escanear",
        "default": "↺ Predeterminado",
        "col_chk": "Sel.",
        "col_name": "Nombre del DLC",
        "col_cat": "Categoría",
        "col_id": "Entitlement ID",
        "col_status": "Estado",
        "col_src": "Origen",
        "st_save": "💾 Pack Partida Armas",
        "st_need_dlcp": "⚠ Falta .dlcp",
        "st_need_link": "⏳ Enlazar .dlcp",
        "st_installed": "✓ Instalado",
        "st_dlcp_ok": "✓ .dlcp Enlazado",
        "st_ready": "⏳ Listo",
        "scanning": "⏳ Escaneando carpetas y archivos DLC...",
        "summary": "{sel} de {total} marcados ({ready} paquetes DLC listos) · Orígenes: {src} · Clic o Espacio para marcar.",
        "sel_all": "☑ Marcar todo",
        "sel_none": "☐ Desmarcar todo",
        "open_dir": "🔍 Abrir Carpeta",
        "install_btn": "🚀 Instalar Seleccionados",
        "close": "Cerrar",
        "pick_dir": "Añadir carpeta DLC (escaneo recursivo)",
        "pick_files": "Seleccionar archivos DLC (.zip / .dlcp / .pkg)",
        "ft_dlc": "Paquetes DLC PS4",
        "ft_all": "Todos los archivos",
        "warn_empty_t": "Instalación de DLC",
        "warn_empty_b": "No se encontraron ni seleccionaron paquetes DLC.",
        "save_conf_t": "Confirmar Partida Guardada de Armas DLC",
        "save_conf_b": "Has marcado los datos de guardado (BSR4_SUMERAGI.DAT).\nTu partida actual en user/savedata se respaldará (.bak) antes de reemplazarse.\n\n¿Continuar?",
        "err_title": "Error al Instalar DLC",
        "err_app0": "No se encontró la carpeta del juego (app0).",
        "err_open": "No se pudo abrir la carpeta:\n{err}",
        "err_install": "Error al instalar el DLC:\n\n{err}",
        "err_mod": "¡No se encontró basara4_dlc.py!",
        "installing_btn": "⏳ Instalando...",
        "installing_sum": "⏳ Instalando {n} paquetes DLC...",
        "step_pkg": "⏳ Procesando paquete {idx}/{total}: {title}...",
        "step_link": "⏳ Enlazando {n} archivos .dlcp al VFS del juego...",
        "step_bin": "⏳ Generando licencia offline content.bin...",
        "ok_title": "DLC Instalado con Éxito",
        "ok_head": "✓ ¡Se instalaron {n} paquetes DLC correctamente!",
        "ok_links": "• {links} archivos de trajes y BGM (.dlcp) vinculados al VFS.",
        "ok_bin": "• Licencia content.bin actualizada ({size} bytes).",
        "ok_save": "• Partida de armas DLC (BSR4_SUMERAGI.DAT) instalada (copia .bak creada).",
        "ok_warn": "• Nota ({n}): {first}",
        "ok_foot": "\n¡Pulsa JUGAR para disfrutar de todos los DLC seleccionados!",
    },
    "pt": {
        "win_title": "Sengoku Basara 4 — Instalador e Gerenciador de DLC em Lote",
        "header": "📦 Instalador de DLC em Lote · CUSA01159",
        "subtitle": "Adicione pastas (verifica todas as subpastas) ou selecione vários arquivos (.zip / .dlcp / .pkg), marque os desejados e clique em Instalar.",
        "add_dir": "📁 + Adicionar Pasta",
        "add_files": "📄 + Selecionar Arquivos (.zip/.dlcp/.pkg)",
        "rescan": "🔄 Verificar",
        "default": "↺ Padrão",
        "col_chk": "Sel.",
        "col_name": "Nome da DLC",
        "col_cat": "Categoria",
        "col_id": "Entitlement ID",
        "col_status": "Status",
        "col_src": "Origem",
        "st_save": "💾 Save de Armas DLC",
        "st_need_dlcp": "⚠ Falta .dlcp",
        "st_need_link": "⏳ Vincular .dlcp",
        "st_installed": "✓ Instalado",
        "st_dlcp_ok": "✓ .dlcp Vinculado",
        "st_ready": "⏳ Pronto",
        "scanning": "⏳ Verificando pastas e pacotes de DLC...",
        "summary": "{sel} de {total} itens marcados ({ready} pacotes DLC prontos) · Fontes ativas: {src} · Clique ou Espaço para alternar.",
        "sel_all": "☑ Marcar tudo",
        "sel_none": "☐ Desmarcar tudo",
        "open_dir": "🔍 Abrir Pasta",
        "install_btn": "🚀 Instalar Selecionados",
        "close": "Fechar",
        "pick_dir": "Adicionar pasta de DLC (varredura recursiva)",
        "pick_files": "Selecionar arquivos de DLC (.zip / .dlcp / .pkg)",
        "ft_dlc": "Pacotes DLC PS4",
        "ft_all": "Todos os arquivos",
        "warn_empty_t": "Instalação de DLC",
        "warn_empty_b": "Nenhum pacote DLC encontrado ou selecionado.",
        "save_conf_t": "Confirmar Save de Armas DLC",
        "save_conf_b": "Você marcou o Save Data (BSR4_SUMERAGI.DAT).\nO save antigo em user/savedata terá backup (.bak) automático antes da substituição.\n\nContinuar?",
        "err_title": "Erro na Instalação de DLC",
        "err_app0": "Pasta do jogo (app0) não encontrada.",
        "err_open": "Não foi possível abrir a pasta:\n{err}",
        "err_install": "Falha ao instalar DLC:\n\n{err}",
        "err_mod": "Módulo basara4_dlc.py não encontrado!",
        "installing_btn": "⏳ Instalando...",
        "installing_sum": "⏳ Instalando {n} pacotes de DLC...",
        "step_pkg": "⏳ Processando pacote {idx}/{total}: {title}...",
        "step_link": "⏳ Vinculando {n} arquivos .dlcp ao VFS do jogo...",
        "step_bin": "⏳ Gerando licença offline content.bin...",
        "ok_title": "Instalação de DLC Concluída",
        "ok_head": "✓ {n} pacotes de DLC instalados com sucesso!",
        "ok_links": "• {links} arquivos de trajes e BGM (.dlcp) vinculados ao VFS.",
        "ok_bin": "• Licença content.bin atualizada ({size} bytes).",
        "ok_save": "• Save de armas DLC (BSR4_SUMERAGI.DAT) instalado (backup .bak criado).",
        "ok_warn": "• Nota ({n}): {first}",
        "ok_foot": "\nClique em JOGAR para aproveitar todas as DLCs selecionadas!",
    },
    "ru": {
        "win_title": "Sengoku Basara 4 — Пакетная установка и менеджер DLC",
        "header": "📦 Пакетная установка DLC · CUSA01159",
        "subtitle": "Добавьте папки (сканируются все подпапки) или выберите несколько файлов (.zip / .dlcp / .pkg), отметьте нужные DLC и нажмите Установить.",
        "add_dir": "📁 + Добавить папку",
        "add_files": "📄 + Выбрать файлы (.zip/.dlcp/.pkg)",
        "rescan": "🔄 Обновить",
        "default": "↺ Сброс",
        "col_chk": "Выб.",
        "col_name": "Название DLC",
        "col_cat": "Категория",
        "col_id": "Entitlement ID",
        "col_status": "Статус",
        "col_src": "Источник",
        "st_save": "💾 Сохранение оружия",
        "st_need_dlcp": "⚠ Нужен .dlcp",
        "st_need_link": "⏳ Нужна ссылка",
        "st_installed": "✓ Установлено",
        "st_dlcp_ok": "✓ .dlcp подключён",
        "st_ready": "⏳ Готово к установке",
        "scanning": "⏳ Сканирование папок и архивов DLC...",
        "summary": "Отмечено {sel} из {total} ({ready} пакетов DLC готово) · Источников: {src} · Клик или Пробел для выбора.",
        "sel_all": "☑ Выбрать все",
        "sel_none": "☐ Снять все",
        "open_dir": "🔍 Открыть папку",
        "install_btn": "🚀 Установить выбранные",
        "close": "Закрыть",
        "pick_dir": "Добавить папку с DLC (поиск по всем подпапкам)",
        "pick_files": "Выбрать файлы DLC (.zip / .dlcp / .pkg)",
        "ft_dlc": "Пакеты DLC PS4",
        "ft_all": "Все файлы",
        "warn_empty_t": "Установка DLC",
        "warn_empty_b": "Пакеты DLC не найдены или не выбраны.",
        "save_conf_t": "Подтверждение замены сохранения",
        "save_conf_b": "Вы отметили файл сохранения (BSR4_SUMERAGI.DAT).\nСтарое сохранение в user/savedata будет автоматически сохранено (.bak) перед заменой.\n\nПродолжить?",
        "err_title": "Ошибка установки DLC",
        "err_app0": "Папка игры (app0) не найдена.",
        "err_open": "Не удалось открыть папку:\n{err}",
        "err_install": "Не удалось установить DLC:\n\n{err}",
        "err_mod": "Модуль basara4_dlc.py не найден!",
        "installing_btn": "⏳ Установка...",
        "installing_sum": "⏳ Установка {n} пакетов DLC...",
        "step_pkg": "⏳ Обработка пакета {idx}/{total}: {title}...",
        "step_link": "⏳ Привязка {n} файлов .dlcp к VFS игры...",
        "step_bin": "⏳ Создание офлайн-лицензии content.bin...",
        "ok_title": "Установка DLC завершена",
        "ok_head": "✓ Успешно установлено пакетов DLC: {n}!",
        "ok_links": "• Привязано архивов костюмов и музыки (.dlcp) к VFS: {links}.",
        "ok_bin": "• Лицензия content.bin обновлена ({size} байт).",
        "ok_save": "• Сохранение с DLC-оружием (BSR4_SUMERAGI.DAT) установлено (создан .bak).",
        "ok_warn": "• Примечание ({n}): {first}",
        "ok_foot": "\nНажмите ИГРАТЬ, чтобы запустить игру со всеми выбранными DLC!",
    },
}


def get_dlc_ui_text(key, lang="id", **kwargs):
    code = _norm_dlc_lang(lang)
    tbl = DLC_UI_I18N.get(code, DLC_UI_I18N["en"])
    txt = tbl.get(key) or DLC_UI_I18N["en"].get(key, key)
    if kwargs:
        try:
            return txt.format(**kwargs)
        except Exception:
            return txt
    return txt
