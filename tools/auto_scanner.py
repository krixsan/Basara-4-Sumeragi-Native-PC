#!/usr/bin/env python3
"""Automated Cheat Scanner & AOB Engine for Sengoku Basara 4 Sumeragi PC.

Capable of:
1. Attaching to live basara4_pc.exe / basara_pc.exe process via ctypes Win32 API.
2. Automatically detecting the guest memory image base (using ELF interpreter marker).
3. Scanning Array of Bytes (AOB) with wildcards (??).
4. Translating process addresses directly to Guest VADDR and ELF File Offsets.
5. Providing preset scans for Health, Basara Gauge, Gold, Coins, and Weapon Points.
6. Falling back to offline scanning of out/eboot.elf if game is not running.
7. Generating ready-to-use Python dictionary entries for basara4_cheats.py.
"""

import argparse
import ctypes
import os
import re
import struct
import sys
from pathlib import Path

# Optional Capstone disassembler
try:
    import capstone
    CS_AVAILABLE = True
except ImportError:
    CS_AVAILABLE = False

# Win32 Constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x00000002
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
ELF_SEG0_MAGIC = b"/libexec/ld-elf.so.1\0"

# Win32 Structures
class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_wchar * 260),
    ]

class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", ctypes.c_ulong),
        ("__alignment1", ctypes.c_ulong),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
        ("__alignment2", ctypes.c_ulong),
    ]

# Win32 Functions
kernel32 = ctypes.windll.kernel32 if os.name == "nt" else None

if kernel32:
    kernel32.CreateToolhelp32Snapshot.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p

    kernel32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32FirstW.restype = ctypes.c_int

    kernel32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.restype = ctypes.c_int

    kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel32.OpenProcess.restype = ctypes.c_void_p

    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int

    kernel32.VirtualQueryEx.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(MEMORY_BASIC_INFORMATION64),
        ctypes.c_size_t,
    ]
    kernel32.VirtualQueryEx.restype = ctypes.c_size_t

    kernel32.ReadProcessMemory.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.ReadProcessMemory.restype = ctypes.c_int


# Predefined Target Signatures for Sengoku Basara 4 Sumeragi (CUSA01159 v1.02)
PRESET_SIGNATURES = {
    "gold_shop": {
        "name": "Gold Won't Decrease (Item Shop)",
        "aob": "41 2B 8E 70 07 00 00 41 0F 48 CF 89 88 DC 00 00",
        "description": "Pengurangan Gold saat membeli item/senjata di Basara Ya",
        "patch_offset": 0,
        "patch_type": "nop",
        "patch_len": 7,
    },
    "gold_weapon_upgrade": {
        "name": "Gold Won't Decrease (Weapon Upgrade)",
        "aob": "2B 8B 4C 08 00 00 49 89 DC BA 00 00 00 00 0F 48",
        "description": "Pengurangan Gold saat upgrade atau sintesis senjata",
        "patch_offset": 0,
        "patch_type": "nop",
        "patch_len": 6,
    },
    "special_coin": {
        "name": "Special Coin x99999 (Battle)",
        "aob": "7C 0E 48 81 C7 E8 02 00 00 B8 3F 42 0F 00",
        "description": "Bypass batas koin battle dan langsung max 999.999",
        "patch_offset": 0,
        "patch_type": "nop",
        "patch_len": 2,
    },
    "growth_points": {
        "name": "Growth Points Won't Decrease",
        "aob": "41 29 85 B4 06 00 00",
        "description": "Pengurangan poin pertumbuhan karakter",
        "patch_offset": 0,
        "patch_type": "nop",
        "patch_len": 7,
    },
    "weapon_points": {
        "name": "Weapon Points Upgrade Hook",
        "aob": "89 81 E4 00 00 00 41 8B B6 20 06 00 00",
        "description": "Pemberian poin senjata saat upgrade di menu",
        "patch_offset": 0,
        "patch_type": "hook",
        "patch_len": 6,
    },
    "weapon_rank_points": {
        "name": "Weapon Rank Points Upgrade Hook",
        "aob": "89 90 E8 00 00 00 C4 C1 7A 10 8E C4 07 00 00",
        "description": "Pemberian rank senjata saat upgrade di menu",
        "patch_offset": 0,
        "patch_type": "hook",
        "patch_len": 6,
    },
    "fps_limiter": {
        "name": "FPS Limiter Bypass",
        "aob": "C5 E2 5C D0 C5 F2 59 CA C5 F8 2E 0D ?? ?? ?? ?? 72 20",
        "description": "Bypass frame sleep limiter bawaan Capcom MT Framework",
        "patch_offset": 16,
        "patch_type": "jmp",
        "patch_len": 2,
    },
    "canary_guard": {
        "name": "Font Stack Canary Guard",
        "aob": "0F 85 38 FF FF FF 48 8B ?? ?? ?? ?? ?? 8B ?? ??",
        "description": "Hook canary pencegah stack overflow glyph Jepang",
        "patch_offset": 0,
        "patch_type": "hook",
        "patch_len": 6,
    },
    "damage_hook_candidate": {
        "name": "Actor Damage / Life Reduction Candidate",
        "aob": "C5 F8 2E D1 72 ?? C5 EA 5C D0",
        "description": "Rutin floating-point damage / pengurangan HP actor (vucomiss + vsubss)",
        "patch_offset": 6,
        "patch_type": "nop",
        "patch_len": 4,
    },
}


def pattern_to_regex(pat_str: str) -> re.Pattern:
    tokens = pat_str.strip().split()
    parts = []
    for t in tokens:
        if t in ("??", "?", "*"):
            parts.append(b".")
        else:
            parts.append(re.escape(bytes([int(t, 16)])))
    return re.compile(b"".join(parts), re.DOTALL)


def find_process(names=("basara4_pc.exe", "basara_pc.exe")):
    if not kernel32:
        return None, None
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == ctypes.c_void_p(-1).value:
        return None, None

    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    success = kernel32.Process32FirstW(snap, ctypes.byref(pe))
    while success:
        for name in names:
            if pe.szExeFile.lower() == name.lower():
                pid = pe.th32ProcessID
                proc_name = pe.szExeFile
                kernel32.CloseHandle(snap)
                return pid, proc_name
        success = kernel32.Process32NextW(snap, ctypes.byref(pe))

    kernel32.CloseHandle(snap)
    return None, None


class LiveProcessScanner:
    def __init__(self, pid):
        self.pid = pid
        self.handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not self.handle:
            raise PermissionError(f"Could not open process {pid}. Run as Administrator.")
        self.guest_base = None
        self.regions = []
        self._find_guest_base()

    def close(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _find_guest_base(self):
        """Enumerate memory blocks to locate the guest image (Segment 0 starts with /libexec/ld-elf.so.1)."""
        addr = 0
        mbi = MEMORY_BASIC_INFORMATION64()
        mbi_size = ctypes.sizeof(mbi)

        while kernel32.VirtualQueryEx(self.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_size):
            if mbi.State == MEM_COMMIT and not (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)):
                self.regions.append((mbi.BaseAddress, mbi.RegionSize, mbi.Protect))
                # Check header magic for guest image
                if self.guest_base is None:
                    hdr = self.read_bytes(mbi.BaseAddress, len(ELF_SEG0_MAGIC))
                    if hdr == ELF_SEG0_MAGIC:
                        self.guest_base = mbi.BaseAddress
            addr = mbi.BaseAddress + mbi.RegionSize

    def read_bytes(self, address, size):
        buf = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buf, size, ctypes.byref(bytes_read))
        if ok and bytes_read.value > 0:
            return bytes(buf.raw[:bytes_read.value])
        return b""

    def scan_aob(self, pat_regex, max_results=10):
        results = []
        for base, size, protect in self.regions:
            # Optimize: read memory in chunks of up to 4MB
            chunk_size = min(size, 4 * 1024 * 1024)
            offset = 0
            while offset < size:
                read_sz = min(chunk_size, size - offset)
                data = self.read_bytes(base + offset, read_sz)
                if data:
                    for m in pat_regex.finditer(data):
                        match_addr = base + offset + m.start()
                        results.append(match_addr)
                        if len(results) >= max_results:
                            return results
                offset += chunk_size
        return results


class OfflineELFScanner:
    def __init__(self, elf_path):
        self.path = Path(elf_path)
        if not self.path.is_file():
            raise FileNotFoundError(f"ELF file not found at {self.path}")
        self.data = self.path.read_bytes()
        self.guest_base = 0  # VADDR starts at 0 for Segment 0

    def scan_aob(self, pat_regex, max_results=10):
        results = []
        # In eboot.elf, Segment 0 starts at file offset 0x4000
        for m in pat_regex.finditer(self.data):
            file_off = m.start()
            if file_off >= 0x4000:
                vaddr = file_off - 0x4000
                results.append((file_off, vaddr))
                if len(results) >= max_results:
                    break
        return results

    def read_bytes_vaddr(self, vaddr, size):
        file_off = vaddr + 0x4000
        return self.data[file_off:file_off + size]


def format_disassembly(code_bytes, vaddr, count=4):
    if not CS_AVAILABLE:
        return "  " + code_bytes[:16].hex()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    lines = []
    for i, insn in enumerate(md.disasm(code_bytes, vaddr)):
        if i >= count:
            break
        lines.append(f"  0x{insn.address:06x}: {insn.bytes.hex():18s} {insn.mnemonic:8s} {insn.op_str}")
    return "\n".join(lines)


def run_scanner(args):
    print("=" * 70)
    print("  SENGOKU BASARA 4 SUMERAGI (CUSA01159 v1.02) - AUTOMATED CHEAT SCANNER")
    print("=" * 70)

    # Detect targets
    targets_to_scan = {}
    if args.aob:
        targets_to_scan["custom_aob"] = {
            "name": f"Custom AOB Pattern ({args.aob})",
            "aob": args.aob,
            "description": "User custom pattern",
            "patch_offset": 0,
            "patch_type": "nop",
            "patch_len": len(args.aob.split()),
        }
    else:
        targets_to_scan = PRESET_SIGNATURES

    # Check for live process
    pid, proc_name = find_process()
    use_live = (pid is not None) and not args.offline

    if use_live:
        print(f"[+] Found active game process: '{proc_name}' (PID: {pid})")
        print("[+] Attaching via ctypes kernel32 API...")
        try:
            scanner = LiveProcessScanner(pid)
        except Exception as e:
            print(f"[-] Failed to attach to process: {e}")
            print("[i] Falling back to offline scanner on 'out/eboot.elf'...")
            use_live = False

    if use_live:
        if scanner.guest_base:
            print(f"[+] Guest Image Base detected at: 0x{scanner.guest_base:016X}")
        else:
            print("[-] Warning: Guest base marker not found immediately. Scanning all committed regions.")
    else:
        elf_path = Path("out/eboot.elf")
        if not elf_path.is_file():
            elf_path = Path("extracted_game/app0/eboot.bin")
        if not elf_path.is_file():
            print("[-] Error: Neither active game process nor eboot.elf found!")
            print("    Please run the game first OR place eboot.elf in 'out/eboot.elf'.")
            return 1
        print(f"[i] Mode: OFFLINE binary scanner targeting '{elf_path}'")
        scanner = OfflineELFScanner(elf_path)

    print("-" * 70)

    discovered_cheats = []

    for key, spec in targets_to_scan.items():
        rx = pattern_to_regex(spec["aob"])
        print(f"\n[*] Scanning for: {spec['name']}")
        print(f"    Pattern: {spec['aob']}")

        if use_live:
            matches = scanner.scan_aob(rx, max_results=3)
            for m_addr in matches:
                vaddr = m_addr - scanner.guest_base if scanner.guest_base else m_addr
                file_off = vaddr + 0x4000
                code = scanner.read_bytes(m_addr, 24)
                print(f"    [MATCH FOUND]")
                print(f"      Host Memory Address : 0x{m_addr:016X}")
                print(f"      Guest VADDR         : 0x{vaddr:06X}")
                print(f"      eboot.elf File Offset: 0x{file_off:06X}")
                print(f"      Hex Dump (16 bytes) : {code[:16].hex()}")
                disasm = format_disassembly(code, vaddr)
                print(f"      Disassembly:\n{disasm}")
                discovered_cheats.append({
                    "id": key,
                    "name": spec["name"],
                    "vaddr": vaddr,
                    "expected": code[:spec["patch_len"]].hex(),
                    "patch_len": spec["patch_len"],
                    "patch_type": spec["patch_type"],
                })
        else:
            matches = scanner.scan_aob(rx, max_results=3)
            for file_off, vaddr in matches:
                code = scanner.read_bytes_vaddr(vaddr, 24)
                print(f"    [MATCH FOUND]")
                print(f"      Guest VADDR         : 0x{vaddr:06X}")
                print(f"      eboot.elf File Offset: 0x{file_off:06X}")
                print(f"      Hex Dump (16 bytes) : {code[:16].hex()}")
                disasm = format_disassembly(code, vaddr)
                print(f"      Disassembly:\n{disasm}")
                discovered_cheats.append({
                    "id": key,
                    "name": spec["name"],
                    "vaddr": vaddr,
                    "expected": code[:spec["patch_len"]].hex(),
                    "patch_len": spec["patch_len"],
                    "patch_type": spec["patch_type"],
                })

    if use_live:
        scanner.close()

    print("\n" + "=" * 70)
    print("  SCAN COMPLETE! READY FOR INTEGRATION INTO basara4_cheats.py")
    print("=" * 70)

    if discovered_cheats:
        print("\n[i] Generated cheat dictionary entries (Python format):\n")
        for item in discovered_cheats:
            nop_hex = "90" * item["patch_len"]
            print(f"    \"{item['id']}\": {{")
            print(f"        \"name\": \"{item['name']}\",")
            print(f"        \"writes\": (")
            print(f"            (0x{item['vaddr']:06X}, \"{nop_hex}\", \"{item['expected'].upper()}\"),")
            print(f"        ),")
            print(f"    }},")
    print()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Cheat Scanner for Sengoku Basara 4 Sumeragi")
    parser.add_argument("--aob", type=str, help="Custom AOB pattern with hex bytes and wildcards (e.g. '41 2B ?? ?? 00')")
    parser.add_argument("--offline", action="store_true", help="Force offline scanning of out/eboot.elf without attaching to game process")
    args = parser.parse_args()
    sys.exit(run_scanner(args))
