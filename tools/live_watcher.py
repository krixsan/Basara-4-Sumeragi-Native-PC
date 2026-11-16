#!/usr/bin/env python3
"""Live Memory Watcher & Runtime Cheat Injector for Sengoku Basara 4 Sumeragi PC.

Monitors target cheat addresses in basara4_pc.exe / basara_pc.exe every 2 seconds.
Provides real-time verification of patch status in live game memory.
Supports --inject to force-apply patches directly into the running process via WriteProcessMemory.
"""

import argparse
import ctypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROCESS_ALL_ACCESS = 0x1F0FFF
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
TH32CS_SNAPPROCESS = 0x00000002
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
PAGE_EXECUTE_READWRITE = 0x40

ELF_SEG0_MAGIC = b"/libexec/ld-elf.so.1\0"

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

kernel32 = ctypes.windll.kernel32

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
kernel32.WriteProcessMemory.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.restype = ctypes.c_int
kernel32.VirtualProtectEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong),
]
kernel32.VirtualProtectEx.restype = ctypes.c_int

TARGET_WATCHES = [
    {
        "vaddr": 0x529A86,
        "name": "Gold 9,999,999 (Shop)",
        "expected_patch": bytes.fromhex("b97f9698009090"),
        "original": bytes.fromhex("412b8e70070000"),
    },
    {
        "vaddr": 0x56950A,
        "name": "Gold Free Upgrade (Weapon)",
        "expected_patch": bytes.fromhex("909090909090"),
        "original": bytes.fromhex("2b8b4c080000"),
    },
    {
        "vaddr": 0x4EFDCC,
        "name": "Gold Won't Decrease (General)",
        "expected_patch": bytes.fromhex("9090"),
        "original": bytes.fromhex("29d6"),
    },
    {
        "vaddr": 0x582B0,
        "name": "Special Coin x999,999 (Battle)",
        "expected_patch": bytes.fromhex("e94b7301019090"),
        "original": bytes.fromhex("f001b7e8020000"),
    },
    {
        "vaddr": 0x5028D4,
        "name": "Growth Points (Level Up)",
        "expected_patch": bytes.fromhex("90909090909090"),
        "original": bytes.fromhex("412985b4060000"),
    },
    {
        "vaddr": 0x560FC6,
        "name": "Weapon Points Max (629k)",
        "expected_patch": bytes.fromhex("e955e6b00090"),
        "original": bytes.fromhex("8981e4000000"),
    },
    {
        "vaddr": 0x55E6A1,
        "name": "Weapon Rank Max (153)",
        "expected_patch": bytes.fromhex("e99a0fb10090"),
        "original": bytes.fromhex("8990e8000000"),
    },
    {
        "vaddr": 0x27D64A,
        "name": "Infinite Health (Cave Hook)",
        "expected_patch": bytes.fromhex("e91120df009090909090909090"),
        "original": bytes.fromhex("c5ea5cd0c4c17a119760250000"),
    },
    {
        "vaddr": 0x2875D0,
        "name": "Infinite Health (Sec 1)",
        "expected_patch": bytes.fromhex("9090909090"),
        "original": bytes.fromhex("c5fa5c4328"),
    },
]

# Cave payloads for direct injection if needed
CAVE_WRITES = [
    (0x106F600, bytes.fromhex("c787e80200003f420f00e9a88cfefe")),
    (0x106F620, bytes.fromhex("b8999909008981e4000000e99c194fff")),
    (0x106F640, bytes.fromhex("ba990000008990e8000000e957f04eff")),
    (0x106F660, bytes.fromhex("c5f857c0c5ea5cd0c4c17a119760250000e9e1df20ff")),
]

def find_target_process(names=("basara4_pc.exe", "basara_pc.exe")):
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
                pname = pe.szExeFile
                kernel32.CloseHandle(snap)
                return pid, pname
        success = kernel32.Process32NextW(snap, ctypes.byref(pe))
    kernel32.CloseHandle(snap)
    return None, None

def find_guest_base(handle):
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION64()
    mbi_size = ctypes.sizeof(mbi)
    buf = ctypes.create_string_buffer(len(ELF_SEG0_MAGIC))
    bytes_read = ctypes.c_size_t(0)

    while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_size):
        if mbi.State == MEM_COMMIT and not (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)):
            ok = kernel32.ReadProcessMemory(
                handle, ctypes.c_void_p(mbi.BaseAddress), buf, len(ELF_SEG0_MAGIC), ctypes.byref(bytes_read)
            )
            if ok and bytes_read.value >= len(ELF_SEG0_MAGIC):
                if buf.raw[:len(ELF_SEG0_MAGIC)] == ELF_SEG0_MAGIC:
                    return mbi.BaseAddress
        addr = mbi.BaseAddress + mbi.RegionSize
    return None

def read_mem(handle, address, size):
    buf = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(bytes_read))
    if ok and bytes_read.value > 0:
        return bytes(buf.raw[:bytes_read.value])
    return b""

def write_mem(handle, address, data):
    old_protect = ctypes.c_ulong(0)
    kernel32.VirtualProtectEx(
        handle, ctypes.c_void_p(address), len(data), PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect)
    )
    written = ctypes.c_size_t(0)
    ok = kernel32.WriteProcessMemory(
        handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
    )
    temp = ctypes.c_ulong(0)
    kernel32.VirtualProtectEx(
        handle, ctypes.c_void_p(address), len(data), old_protect.value, ctypes.byref(temp)
    )
    return ok and written.value == len(data)

def inject_all_cheats(handle, guest_base, log):
    log("[*] Injecting code caves...")
    for off, data in CAVE_WRITES:
        ok = write_mem(handle, guest_base + off, data)
        log(f"    Cave at 0x{off:06X} ({len(data)} bytes): {'SUCCESS' if ok else 'FAILED'}")

    log("[*] Injecting cheat hooks and patches...")
    for w in TARGET_WATCHES:
        ok = write_mem(handle, guest_base + w["vaddr"], w["expected_patch"])
        log(f"    Patch at 0x{w['vaddr']:06X} ({w['name']}): {'SUCCESS' if ok else 'FAILED'}")

def main():
    parser = argparse.ArgumentParser(description="Live Memory Watcher & Cheat Injector")
    parser.add_argument("--inject", action="store_true", help="Force inject cheats directly into live memory")
    parser.add_argument("--auto-inject", action="store_true", help="Auto-inject cheats if original bytes detected")
    args = parser.parse_args()

    log_file = Path("user/logs/watcher.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    out_f = log_file.open("a", encoding="utf-8")

    def log(msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {msg}"
        print(line)
        out_f.write(line + "\n")
        out_f.flush()

    log("=" * 70)
    log("  SENGOKU BASARA 4 SUMERAGI - LIVE MEMORY WATCHER & TRAINER")
    log("=" * 70)
    log("[i] Waiting for basara4_pc.exe / basara_pc.exe...")

    handle = None
    pid = None
    guest_base = None

    try:
        while True:
            pid, pname = find_target_process()
            if pid:
                log(f"[+] Found process: {pname} (PID: {pid})")
                handle = kernel32.OpenProcess(
                    PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION,
                    False,
                    pid
                )
                if handle:
                    break
            time.sleep(1)

        log("[i] Locating guest memory image base...")
        while True:
            guest_base = find_guest_base(handle)
            if guest_base:
                log(f"[+] Guest Image Base mapped at: 0x{guest_base:016X}")
                break
            time.sleep(0.5)

        if args.inject:
            inject_all_cheats(handle, guest_base, log)

        log("[+] Live monitoring active. Polling every 2.0s...")
        log("-" * 70)

        loop_count = 0
        injected = args.inject

        while True:
            exit_code = ctypes.c_ulong(0)
            kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            if exit_code.value != 259:
                log(f"[-] Target process exited with code {exit_code.value}. Stopping watcher.")
                break

            loop_count += 1
            status_lines = []
            all_active = True

            for watch in TARGET_WATCHES:
                vaddr = watch["vaddr"]
                host_addr = guest_base + vaddr
                patch_len = len(watch["expected_patch"])
                actual = read_mem(handle, host_addr, patch_len)

                if actual == watch["expected_patch"]:
                    tag = "OK (PATCH ACTIVE)"
                elif actual == watch["original"]:
                    tag = "UNPATCHED (ORIGINAL CODE)"
                    all_active = False
                else:
                    tag = f"MODIFIED ({actual.hex()})"
                    all_active = False

                status_lines.append(f"  VADDR 0x{vaddr:06X} [{watch['name'][:22]:22s}]: {actual.hex()} -> {tag}")

            if args.auto_inject and not all_active and not injected:
                log("[!] Incomplete patches detected. Auto-injecting...")
                inject_all_cheats(handle, guest_base, log)
                injected = True
                continue

            log(f"Cycle #{loop_count:04d} status (All active: {all_active}):")
            for line in status_lines:
                log(line)

            time.sleep(2.0)

    except KeyboardInterrupt:
        log("[i] Watcher stopped by user (Ctrl+C).")
    finally:
        if handle:
            kernel32.CloseHandle(handle)
        out_f.close()

if __name__ == "__main__":
    main()
