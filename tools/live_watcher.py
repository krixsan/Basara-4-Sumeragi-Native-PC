#!/usr/bin/env python3
"""Live Memory Watcher for Sengoku Basara 4 Sumeragi PC.

Monitors target cheat addresses in basara4_pc.exe / basara_pc.exe every 2 seconds
to detect whether patches stay active (0x90) or are reverted by game runtime / anti-tamper.
"""

import ctypes
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x00000002
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
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

TARGET_WATCHES = [
    {
        "vaddr": 0x27D64A,
        "name": "Infinite Health (Damage Sub)",
        "expected_patch": bytes.fromhex("90909090"),
        "original": bytes.fromhex("c5ea5cd0"),
    },
    {
        "vaddr": 0x529A86,
        "name": "Gold Won't Decrease (Shop)",
        "expected_patch": bytes.fromhex("90909090909090"),
        "original": bytes.fromhex("412b8e70070000"),
    },
    {
        "vaddr": 0x56950A,
        "name": "Gold Won't Decrease (Weapon Upgrade)",
        "expected_patch": bytes.fromhex("909090909090"),
        "original": bytes.fromhex("2b8b4c080000"),
    },
    {
        "vaddr": 0x0582C1,
        "name": "Special Coin x99999 (Battle)",
        "expected_patch": bytes.fromhex("9090"),
        "original": bytes.fromhex("7c0e"),
    },
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

def main():
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
    log("  SENGOKU BASARA 4 SUMERAGI - LIVE MEMORY WATCHER STARTING")
    log("=" * 70)
    log("[i] Waiting for basara4_pc.exe / basara_pc.exe...")

    handle = None
    pid = None
    guest_base = None

    try:
        # Wait for process
        while True:
            pid, pname = find_target_process()
            if pid:
                log(f"[+] Found process: {pname} (PID: {pid})")
                handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
                if handle:
                    break
            time.sleep(1)

        # Wait for guest image to be mapped
        log("[i] Locating guest memory image base...")
        while True:
            guest_base = find_guest_base(handle)
            if guest_base:
                log(f"[+] Guest Image Base mapped at: 0x{guest_base:016X}")
                break
            time.sleep(0.5)

        log("[+] Live monitoring active. Polling every 2.0s...")
        log("-" * 70)

        loop_count = 0
        while True:
            # Check if process is still alive
            exit_code = ctypes.c_ulong(0)
            kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            if exit_code.value != 259: # STILL_ACTIVE
                log(f"[-] Target process exited with code {exit_code.value}. Stopping watcher.")
                break

            loop_count += 1
            status_lines = []

            for watch in TARGET_WATCHES:
                vaddr = watch["vaddr"]
                host_addr = guest_base + vaddr
                patch_len = len(watch["expected_patch"])
                actual = read_mem(handle, host_addr, patch_len)

                if actual == watch["expected_patch"]:
                    tag = "OK (NOP PATCH ACTIVE)"
                elif actual == watch["original"]:
                    tag = "!! REVERTED (ORIGINAL CODE ACTIVE) !!"
                else:
                    tag = f"?? MODIFIED ({actual.hex()}) ??"

                status_lines.append(f"  VADDR 0x{vaddr:06X} [{watch['name'][:18]:18s}]: {actual.hex()} -> {tag}")

            # Print every 2 seconds, but log full details
            log(f"Cycle #{loop_count:04d} status:")
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
