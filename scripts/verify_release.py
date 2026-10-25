#!/usr/bin/env python3
"""
Sengoku Basara 4 Sumeragi — Release Verification Pipeline
Validates file integrity, checksums, and size constraints for distribution builds.
"""

import os
import sys
import argparse
import hashlib
import zipfile
from pathlib import Path

def verify_release(dist_dir="dist"):
    root = Path(__file__).resolve().parent.parent
    dist = root / dist_dir

    if not dist.is_dir():
        print(f"[FAIL] Distribution directory not found: {dist}")
        return 1

    zip_files = list(dist.glob("Basara4_Sumeragi_PC_v*.zip"))
    if not zip_files:
        print("[FAIL] No Basara4_Sumeragi_PC_v*.zip archive found in dist/!")
        return 1

    target_zip = sorted(zip_files, key=os.path.getmtime, reverse=True)[0]
    print(f"=== Verifying Release Archive: {target_zip.name} ===")

    # 1. Size Constraints
    size_mb = target_zip.stat().st_size / (1024 * 1024)
    print(f"Archive Size: {size_mb:.2f} MB")
    if size_mb > 150:
        print(f"[FAIL] Archive size {size_mb:.2f} MB exceeds maximum hard limit (150 MB)!")
        return 1
    elif size_mb > 100:
        print(f"[WARN] Archive size {size_mb:.2f} MB exceeds target budget (100 MB).")

    # 2. Inspect ZIP Content and verify CHECKSUMS.txt
    failures = 0
    with zipfile.ZipFile(target_zip, "r") as zf:
        namelist = zf.namelist()
        root_prefix = namelist[0].split("/")[0]

        # Extract CHECKSUMS.txt
        checksum_rel = f"{root_prefix}/CHECKSUMS.txt"
        if checksum_rel not in namelist:
            print("[FAIL] CHECKSUMS.txt is missing from archive!")
            return 1

        checksum_data = zf.read(checksum_rel).decode("utf-8")
        expected_hashes = {}
        for line in checksum_data.splitlines():
            line = line.strip()
            if line and "  " in line:
                sha, fpath = line.split("  ", 1)
                expected_hashes[fpath.strip()] = sha.strip()

        print(f"Validating {len(expected_hashes)} checksummed entries...")
        for rel_path, expected_sha in expected_hashes.items():
            if rel_path == "CHECKSUMS.txt":
                continue
            entry_name = f"{root_prefix}/{rel_path}"
            if entry_name not in namelist:
                print(f"[FAIL] Missing file in ZIP: {entry_name}")
                failures += 1
                continue

            file_bytes = zf.read(entry_name)
            computed_sha = hashlib.sha256(file_bytes).hexdigest()
            if computed_sha.lower() != expected_sha.lower():
                print(f"[FAIL] Hash mismatch for {rel_path}!\n  Expected: {expected_sha}\n  Got:      {computed_sha}")
                failures += 1
            else:
                print(f"  [PASS] {rel_path}")

        # Check mandatory runtime DLLs
        mandatory_dlls = [
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
        print("\nValidating mandatory runtime DLLs in archive...")
        zip_basenames = {entry.split("/")[-1].lower(): entry for entry in namelist}
        for mand_dll in mandatory_dlls:
            if mand_dll.lower() not in zip_basenames:
                print(f"[FAIL] Missing mandatory runtime DLL in release ZIP: {mand_dll}")
                failures += 1
            else:
                print(f"  [PASS] Found mandatory DLL: {mand_dll}")

        # Check forbidden Windows system DLLs
        system_dll_leak_checks = [
            "kernel32.dll", "user32.dll", "dbghelp.dll", "dxgi.dll", "winhttp.dll", "avrt.dll"
        ]
        for sys_dll in system_dll_leak_checks:
            if sys_dll.lower() in zip_basenames:
                print(f"[FAIL] Windows system DLL erroneously bundled in ZIP: {sys_dll}")
                failures += 1

        # Check for banned paths
        banned_stems = ["extracted_game", "boot-linked.bin", "eboot.bin", "crashes/pending"]
        for item in namelist:
            parts = item.replace("\\", "/").split("/")
            if ".git" in parts or any(b in item for b in banned_stems):
                print(f"[CRITICAL FAIL] Copyrighted / build cache leak detected: {item}")
                failures += 1

    # 3. Verify Setup Installer if exists
    setup_files = list(dist.glob("Basara4_Sumeragi_PC_Setup_*.exe"))
    if setup_files:
        setup_exe = setup_files[0]
        setup_mb = setup_exe.stat().st_size / (1024 * 1024)
        print(f"Installer Executable: {setup_exe.name} ({setup_mb:.2f} MB)")
        if setup_mb < 10:
            print(f"[FAIL] Installer size ({setup_mb:.2f} MB) is suspiciously small (<10 MB)!")
            failures += 1
        elif setup_mb > 80:
            print(f"[WARN] Installer size ({setup_mb:.2f} MB) exceeds 80 MB limit.")
        else:
            print("  [PASS] Installer size verified.")
    else:
        print("[INFO] No Inno Setup EXE found (local or CI installer build step optional).")

    if failures == 0:
        print("\n=== RELEASE VERIFICATION PASSED: 100% READY FOR DEPLOYMENT ===")
        return 0
    else:
        print(f"\n[FAILED] Verification completed with {failures} error(s)!")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify distribution release package")
    parser.add_argument("--dist-dir", default="dist", help="Path to distribution directory")
    args = parser.parse_args()

    sys.exit(verify_release(dist_dir=args.dist_dir))
