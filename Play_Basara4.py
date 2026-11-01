"""
Sengoku Basara 4 Sumeragi — Smart Game Launcher & Professional Crash Reporter
Auto-detects crashes, generates diagnostic crash bundles, and presents a user-friendly UI.
"""

import os
import sys
import re
import glob
import shutil
import platform
import subprocess
import webbrowser
import urllib.parse
import ctypes
from ctypes import wintypes
from datetime import datetime

# Optional psutil support
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# GUI imports (CustomTkinter primary, Tkinter standard fallback)
try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False


# GitHub repository configuration
GITHUB_REPO = "krixsan/Basara-4-Sumeragi-Native-PC"

# Critical crash keywords to detect in logs
CRASH_KEYWORDS = [
    "STOP: guest stack protector",
    "STOP: GPU library assertion failed",
    "Unhandled immediate argument",
    "Access Violation",
    "0xC0000005",
]

# Context scan keywords (extract 5 lines before and after)
CONTEXT_KEYWORDS = [
    "STOP:",
    "STOP",
    "Fatal",
    "Exception",
    "Join",
    "Wait",
    "1455",
    "Error",
    "Critical",
    "Unhandled",
    "Access Violation",
    "0xC0000005",
]


def get_game_version():
    """Reads game version from VERSION.txt or returns default."""
    for path in ["VERSION.txt", "version.txt"]:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    v = f.read().strip()
                    if v:
                        return v
            except Exception:
                pass
    return "v2.1.0"


def get_gpu_info():
    """Detects GPU name using PowerShell or WMIC without external dependencies."""
    # Method 1: PowerShell Get-CimInstance (Windows 10/11)
    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
        if res.returncode == 0 and res.stdout.strip():
            gpus = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
            if gpus:
                return ", ".join(gpus)
    except Exception:
        pass

    # Method 2: WMIC fallback
    try:
        cmd = ["wmic", "path", "win32_VideoController", "get", "name"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
        if res.returncode == 0:
            lines = [l.strip() for l in res.stdout.splitlines() if l.strip() and l.strip().lower() != "name"]
            if lines:
                return ", ".join(lines)
    except Exception:
        pass

    # Method 3: Optional wmi module if installed
    try:
        import wmi
        c = wmi.WMI()
        gpus = [gpu.Name for gpu in c.Win32_VideoController() if gpu.Name]
        if gpus:
            return ", ".join(gpus)
    except Exception:
        pass

    return "Unknown GPU / Standard Display Adapter"


def get_memory_info():
    """
    Retrieves system memory diagnostics including Total RAM, Free RAM,
    and Commit Charge (Page File) using ctypes (GlobalMemoryStatusEx) or psutil.
    """
    # Method 1: ctypes Windows API (Native standard library, 0 external dependencies)
    if sys.platform == "win32":
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_ram_gb = stat.ullTotalPhys / (1024 ** 3)
                free_ram_gb = stat.ullAvailPhys / (1024 ** 3)
                total_commit_gb = stat.ullTotalPageFile / (1024 ** 3)
                avail_commit_gb = stat.ullAvailPageFile / (1024 ** 3)
                used_commit_gb = total_commit_gb - avail_commit_gb
                mem_load = stat.dwMemoryLoad
                return {
                    "total_ram": f"{total_ram_gb:.2f} GB",
                    "free_ram": f"{free_ram_gb:.2f} GB",
                    "commit_charge": f"{used_commit_gb:.2f} GB / {total_commit_gb:.2f} GB ({mem_load}% load)",
                    "summary": f"RAM: {total_ram_gb:.1f}GB ({free_ram_gb:.1f}GB Free) | Commit: {used_commit_gb:.1f}/{total_commit_gb:.1f}GB"
                }
        except Exception:
            pass

    # Method 2: psutil fallback
    if HAS_PSUTIL:
        try:
            v = psutil.virtual_memory()
            s = psutil.swap_memory()
            total_ram_gb = v.total / (1024 ** 3)
            free_ram_gb = v.available / (1024 ** 3)
            used_commit_gb = (v.used + s.used) / (1024 ** 3)
            total_commit_gb = (v.total + s.total) / (1024 ** 3)
            return {
                "total_ram": f"{total_ram_gb:.2f} GB",
                "free_ram": f"{free_ram_gb:.2f} GB",
                "commit_charge": f"{used_commit_gb:.2f} GB / {total_commit_gb:.2f} GB",
                "summary": f"RAM: {total_ram_gb:.1f}GB ({free_ram_gb:.1f}GB Free) | Commit: {used_commit_gb:.1f}/{total_commit_gb:.1f}GB"
            }
        except Exception:
            pass

    return {
        "total_ram": "N/A",
        "free_ram": "N/A",
        "commit_charge": "N/A",
        "summary": "Memory info unavailable"
    }


def check_dump_file(max_age_seconds=7200):
    """
    Checks for newly created .dmp files in crashes/ or user/crashes/.
    Returns: (found: bool, status_str: str, dmp_path: str or None)
    """
    search_dirs = [
        "crashes",
        os.path.join("user", "crashes"),
        os.path.join("user", "crash"),
    ]
    dmps = []
    now = datetime.now().timestamp()
    for d in search_dirs:
        if os.path.isdir(d):
            try:
                for fname in os.listdir(d):
                    if fname.lower().endswith(".dmp"):
                        fpath = os.path.join(d, fname)
                        try:
                            mtime = os.path.getmtime(fpath)
                            dmps.append((fpath, fname, mtime))
                        except Exception:
                            pass
            except Exception:
                pass

    if not dmps:
        return False, "NOT FOUND", None

    dmps.sort(key=lambda x: x[2], reverse=True)
    newest_path, newest_name, newest_mtime = dmps[0]
    age = now - newest_mtime

    # Return FOUND if created recently (within max_age_seconds or during simulation)
    if age <= max_age_seconds or "--test-crash" in sys.argv:
        return True, f"FOUND ({newest_name})", newest_path
    else:
        return False, "NOT FOUND", None


def get_guest_faults_breadcrumb():
    """Reads user/crashes/guest_faults.log if present."""
    candidates = [
        os.path.join("user", "crashes", "guest_faults.log"),
        os.path.join("crashes", "guest_faults.log"),
        "guest_faults.log",
    ]
    for p in candidates:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().strip()
                if content:
                    return content
            except Exception as e:
                return f"(Gagal membaca {p}: {e})"
    return None


def find_latest_log():
    """Locates the latest log file across standard paths."""
    candidates = [
        os.path.join("user", "logs", "last_run.log"),
        "last_run.log",
        os.path.join("user", "logs", "basara.log"),
        "basara.log",
    ]
    existing = [p for p in candidates if os.path.isfile(p)]
    if not existing:
        return None
    # Pick the most recently modified log
    return max(existing, key=os.path.getmtime)


def scan_log_for_crash(exit_code: int, log_path: str):
    """
    Scans the log file to determine if a crash occurred.
    Returns: (is_crash: bool, reason: str, matched_keywords: list)
    """
    matched = []
    lines = []
    
    if log_path and os.path.isfile(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[CRASH_SCANNER] Error reading log file: {e}")

    # Check last 100 lines for critical crash signatures
    tail_100 = lines[-100:] if len(lines) > 100 else lines
    tail_text = "".join(tail_100)

    for kw in CRASH_KEYWORDS:
        if kw.lower() in tail_text.lower():
            matched.append(kw)

    is_crash = False
    reason_parts = []

    if exit_code != 0:
        is_crash = True
        # Format exit code nicely
        if exit_code == -1073741819 or exit_code == 3221225477 or exit_code == 0xC0000005:
            reason_parts.append("Exit Code 0xC0000005 (Access Violation / Null Pointer)")
        elif exit_code == 22:
            reason_parts.append("Exit Code 22 (Stack Protector / Canary Corruption)")
        elif exit_code == 3:
            reason_parts.append("Exit Code 3 (Engine Fatal Exception / Unhandled Fault)")
        else:
            reason_parts.append(f"Exit Code {exit_code} (0x{exit_code & 0xFFFFFFFF:08X})")

    if matched:
        is_crash = True
        reason_parts.append(f"Critical Signature Detected in Log: {', '.join(matched)}")

    return is_crash, " | ".join(reason_parts) if reason_parts else "Normal Termination", matched


def extract_context_sections(lines: list, context_lines=5):
    """
    Extracts sections containing critical keywords with 5 lines of context before and after.
    Searches for: STOP:, Fatal, Exception, Join, Wait, 1455, Error, Critical, Access Violation, etc.
    Merges overlapping ranges.
    """
    if not lines:
        return "(no log data available for context extraction)"

    hits = []
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw.lower() in line_lower for kw in CONTEXT_KEYWORDS):
            hits.append(i)

    if not hits:
        return "(no specific critical lines found in log body)"

    # Merge overlapping ranges (5 lines before and 5 lines after)
    ranges = []
    for h in hits:
        start = max(0, h - context_lines)
        end = min(len(lines), h + context_lines + 1)
        if ranges and start <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
        else:
            ranges.append((start, end))

    output = []
    for start, end in ranges:
        output.append(f"=== [Log Lines {start + 1} to {end}] ===")
        output.extend([lines[j].rstrip() for j in range(start, end)])
        output.append("")

    return "\n".join(output)


def generate_crash_report(exit_code: int, log_path: str, trigger_reason: str, matched_keywords: list):
    """
    Generates a structured crash report file and saves a timestamped log copy.
    Includes memory diagnostics, dump file detection, and guest faults breadcrumb.
    Returns: (report_path, log_copy_path, report_content)
    """
    crashes_dir = os.path.abspath("crashes")
    os.makedirs(crashes_dir, exist_ok=True)

    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    file_ts = now.strftime("%Y%m%d_%H%M%S")

    report_filename = f"crash_{file_ts}.txt"
    log_copy_filename = f"log_{file_ts}.txt"

    report_path = os.path.join(crashes_dir, report_filename)
    log_copy_path = os.path.join(crashes_dir, log_copy_filename)

    # Copy raw log if available
    lines = []
    if log_path and os.path.isfile(log_path):
        try:
            shutil.copyfile(log_path, log_copy_path)
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as e:
            print(f"[CRASH_REPORTER] Log copy error: {e}")

    # Format exit code string
    if exit_code == -1073741819 or exit_code == 3221225477 or exit_code == 0xC0000005:
        exit_str = "0xC0000005 (STATUS_ACCESS_VIOLATION)"
    else:
        exit_str = f"{exit_code} (0x{exit_code & 0xFFFFFFFF:08X})"

    # Diagnostics Data
    mem_info = get_memory_info()
    dmp_found, dmp_status, dmp_file_path = check_dump_file()
    guest_faults = get_guest_faults_breadcrumb()

    last_50 = "".join(lines[-50:]).strip() if lines else "(log is empty or missing)"
    context_scan = extract_context_sections(lines, context_lines=5)

    # Build report text
    report = []
    report.append("================================================================================")
    report.append("             SENGOKU BASARA 4 SUMERAGI PC — CRASH REPORT")
    report.append("================================================================================")
    report.append(f"Timestamp    : {timestamp_str}")
    report.append(f"Game Version : {get_game_version()}")
    report.append(f"Exit Code    : {exit_str}")
    report.append(f"Trigger      : {trigger_reason}")
    if matched_keywords:
        report.append(f"Keywords     : {', '.join(matched_keywords)}")
    report.append("")
    report.append("----------------------------- SYSTEM INFORMATION -------------------------------")
    report.append(f"Operating System : {platform.system()} {platform.release()} (Build {platform.version()})")
    report.append(f"Architecture     : {platform.machine()}")
    report.append(f"Processor        : {platform.processor()}")
    report.append(f"Graphics Device  : {get_gpu_info()}")
    report.append(f"Total RAM        : {mem_info['total_ram']}")
    report.append(f"Free RAM         : {mem_info['free_ram']}")
    report.append(f"Commit Charge    : {mem_info['commit_charge']}")
    report.append(f"Dump File        : {dmp_status}")
    report.append(f"Python Runtime   : {sys.version.split()[0]}")
    report.append("")

    if guest_faults:
        report.append("--------------------------- GUEST FAULTS DETECTED ------------------------------")
        report.append("(Captured from user/crashes/guest_faults.log):")
        report.append("")
        report.append(guest_faults)
        report.append("")

    report.append("----------------------------- CRITICAL CONTEXT SCAN ----------------------------")
    report.append("(Captured 5 lines of context surrounding STOP:, Fatal, Exception, Join, Wait, 1455 markers):")
    report.append("")
    report.append(context_scan)
    report.append("")
    report.append("---------------------------- LAST 50 LINES OF LOG ------------------------------")
    report.append(last_50)
    report.append("")
    report.append("================================================================================")
    report.append(f"Original Log Copy : {log_copy_path}")
    report.append("================================================================================")

    content = "\n".join(report)

    with open(report_path, "w", encoding="utf-8", errors="replace") as f:
        f.write(content)

    return report_path, log_copy_path, content



class CrashDialog:
    """
    Studio-Grade Crash & Diagnostic Dialog built for Sengoku Basara 4 Sumeragi Native Port.
    Crafted with CustomTkinter modern dark aesthetic, real-time hardware telemetry ribbon,
    line-by-line syntax highlighting, and fluid feedback micro-interactions.
    """

    def __init__(self, report_path: str, crashes_dir: str, content: str, exit_code: int, reason: str):
        self.report_path = os.path.abspath(report_path)
        self.crashes_dir = os.path.abspath(crashes_dir)
        self.content = content
        self.exit_code = exit_code
        self.reason = reason

        # Diagnostics snapshot
        self.mem_info = get_memory_info()
        self.dmp_found, self.dmp_status, self.dmp_path = check_dump_file()

        # Design Token System (Obsidian & Sengoku Crimson)
        self.C_BG = "#080B10"           # Pure deep obsidian canvas
        self.C_CARD = "#121622"         # Elevated surface card
        self.C_CARD_INNER = "#171D2A"   # Telemetry & inner ribbon surface
        self.C_BORDER = "#1E2738"       # Crisp slate hairline border
        self.C_BORDER_SUBTLE = "#28354A" # Hover/accent border
        self.C_CODE_BG = "#06080D"       # Pitch-black console viewport

        # Action & Accent Colors
        self.C_CRIMSON = "#F43F5E"      # Battle crimson (Crash alert & close outline)
        self.C_CRIMSON_BG = "#291118"   # Soft crimson pill background
        self.C_CRIMSON_BORDER = "#4C1D26"

        self.C_BLUE = "#2563EB"         # Royal Cobalt (GitHub Primary Hero)
        self.C_BLUE_HOVER = "#1D4ED8"

        self.C_BTN_SEC = "#1C2331"      # Secondary neutral surface
        self.C_BTN_SEC_HOVER = "#263044"

        self.C_EMERALD = "#10B981"      # Emerald green (Success / copied)
        self.C_AMBER = "#F59E0B"        # Amber warning
        self.C_CYAN = "#38BDF8"         # Subsystem cyan telemetry

        self.C_TEXT_WHITE = "#F8FAFC"
        self.C_TEXT_MUTED = "#94A3B8"
        self.C_TEXT_DIM = "#64748B"

        if HAS_CTK:
            self._build_customtkinter_ui()
        else:
            self._build_fallback_ui()

    def _build_customtkinter_ui(self):
        self.root = ctk.CTk()
        self.root.title("Sengoku Basara 4 Sumeragi — Diagnostic & Crash Reporter")
        self.root.configure(fg_color=self.C_BG)

        # Window geometry and responsive centering
        win_w, win_h = 880, 700
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pos_x = max(0, (screen_w - win_w) // 2)
        pos_y = max(0, (screen_h - win_h) // 2)
        self.root.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        self.root.minsize(820, 620)

        # Smooth 60 FPS fade-in
        self.root.attributes("-alpha", 0.0)
        self._fade_in_step(0.0)

        # Main layout grid
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=0) # Header & Telemetry Card
        self.root.grid_rowconfigure(1, weight=0) # Path Box Card
        self.root.grid_rowconfigure(2, weight=1) # Log Preview Card (stretches)
        self.root.grid_rowconfigure(3, weight=0) # Action Dock

        # ----------------------------------------------------------------------
        # 1. HEADER & TELEMETRY CARD (Signature Component)
        # ----------------------------------------------------------------------
        header_card = ctk.CTkFrame(
            self.root, fg_color=self.C_CARD, corner_radius=12,
            border_width=1, border_color=self.C_BORDER
        )
        header_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))

        # Top Bar: Badge + Title + Code Chips
        top_bar = ctk.CTkFrame(header_card, fg_color="transparent")
        top_bar.pack(fill="x", padx=18, pady=(14, 6))

        badge = ctk.CTkLabel(
            top_bar, text="  ⚡ CRASH DETECTED  ", fg_color=self.C_CRIMSON,
            text_color="#FFFFFF", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            corner_radius=6
        )
        badge.pack(side="left", padx=(0, 10))

        title_lbl = ctk.CTkLabel(
            top_bar, text="SENGOKU BASARA 4 // CRASH REPORTER",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color=self.C_TEXT_WHITE
        )
        title_lbl.pack(side="left")

        # Right Chips: Version & Exit Code
        version_chip = ctk.CTkLabel(
            top_bar, text=f" Build: {get_game_version()} ", fg_color=self.C_CARD_INNER,
            text_color=self.C_TEXT_MUTED, font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            corner_radius=6
        )
        version_chip.pack(side="right", padx=(8, 0))

        code_hex = f"0x{self.exit_code & 0xFFFFFFFF:08X}" if self.exit_code else "0x00000000"
        code_lbl_text = f" Exit: {code_hex} "
        code_chip = ctk.CTkLabel(
            top_bar, text=code_lbl_text, fg_color=self.C_CRIMSON_BG,
            text_color="#FB7185", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            corner_radius=6
        )
        code_chip.pack(side="right")

        # Subtitle Explanation
        sub_lbl = ctk.CTkLabel(
            header_card,
            text="Game terhenti mendadak selama proses emulasi/rekompilasi. Tenang, bundle diagnostik lengkap telah dibuat otomatis.\n"
                 "Kirimkan laporan ini ke pengembang atau buat issue di GitHub agar bug dapat segera diinvestigasi dan diperbaiki.",
            font=ctk.CTkFont(family="Segoe UI", size=12), text_color=self.C_TEXT_MUTED, justify="left"
        )
        sub_lbl.pack(anchor="w", padx=18, pady=(0, 10))

        # Telemetry Ribbon Strip
        telemetry_strip = ctk.CTkFrame(
            header_card, fg_color=self.C_CARD_INNER, corner_radius=8,
            border_width=1, border_color=self.C_BORDER
        )
        telemetry_strip.pack(fill="x", padx=18, pady=(0, 14))

        gpu_name = get_gpu_info()
        if len(gpu_name) > 30:
            gpu_name = gpu_name[:28] + "..."

        t_gpu = ctk.CTkLabel(
            telemetry_strip, text=f"🎮 GPU: {gpu_name}",
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=self.C_TEXT_WHITE
        )
        t_gpu.pack(side="left", padx=10, pady=6)

        t_sep1 = ctk.CTkLabel(telemetry_strip, text="•", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=self.C_TEXT_DIM)
        t_sep1.pack(side="left", padx=2)

        t_ram = ctk.CTkLabel(
            telemetry_strip, text=f"🧠 RAM: {self.mem_info['free_ram']} Free",
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=self.C_TEXT_WHITE
        )
        t_ram.pack(side="left", padx=2)

        t_sep2 = ctk.CTkLabel(telemetry_strip, text="•", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=self.C_TEXT_DIM)
        t_sep2.pack(side="left", padx=2)

        dmp_color = self.C_EMERALD if self.dmp_found else self.C_TEXT_DIM
        t_dmp = ctk.CTkLabel(
            telemetry_strip, text=f"📦 Dump: {self.dmp_status}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=dmp_color
        )
        t_dmp.pack(side="left", padx=2)

        t_sep3 = ctk.CTkLabel(telemetry_strip, text="•", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=self.C_TEXT_DIM)
        t_sep3.pack(side="left", padx=2)

        reason_short = self.reason if len(self.reason) <= 35 else self.reason[:32] + "..."
        t_reason = ctk.CTkLabel(
            telemetry_strip, text=f"🔍 {reason_short}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#FBBF24"
        )
        t_reason.pack(side="left", padx=2)

        # ----------------------------------------------------------------------
        # 2. PATH BOX CARD (Laporan Crash Dump)
        # ----------------------------------------------------------------------
        path_card = ctk.CTkFrame(
            self.root, fg_color=self.C_CARD, corner_radius=10,
            border_width=1, border_color=self.C_BORDER
        )
        path_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        path_title = ctk.CTkLabel(
            path_card, text="LOKASI FILE LAPORAN LENGKAP (CRASH DUMP):",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self.C_TEXT_DIM
        )
        path_title.pack(anchor="w", padx=16, pady=(10, 4))

        path_row = ctk.CTkFrame(path_card, fg_color="transparent")
        path_row.pack(fill="x", padx=16, pady=(0, 12))

        self.path_entry = ctk.CTkEntry(
            path_row, fg_color=self.C_CODE_BG, border_color=self.C_BORDER,
            text_color="#34D399", font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8, height=36
        )
        self.path_entry.insert(0, self.report_path)
        self.path_entry.configure(state="readonly")
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_copy = ctk.CTkButton(
            path_row, text="📋 Salin Path", fg_color=self.C_BTN_SEC,
            hover_color=self.C_BTN_SEC_HOVER, text_color=self.C_TEXT_WHITE,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=8, width=125, height=36, command=self.copy_path
        )
        self.btn_copy.pack(side="right")

        # ----------------------------------------------------------------------
        # 3. LOG PREVIEW CARD (Studio Terminal Viewport)
        # ----------------------------------------------------------------------
        preview_card = ctk.CTkFrame(
            self.root, fg_color=self.C_CARD, corner_radius=10,
            border_width=1, border_color=self.C_BORDER
        )
        preview_card.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        preview_card.grid_columnconfigure(0, weight=1)
        preview_card.grid_rowconfigure(1, weight=1)

        # Header Bar for Log Box: Title on left, quick copy on right
        log_header_bar = ctk.CTkFrame(preview_card, fg_color="transparent")
        log_header_bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(8, 4))

        preview_title = ctk.CTkLabel(
            log_header_bar, text="RINGKASAN DIAGNOSTIK & LOG TERAKHIR (TAIL & CRITICAL SCAN):",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self.C_TEXT_DIM
        )
        preview_title.pack(side="left")

        self.btn_copy_log = ctk.CTkButton(
            log_header_bar, text="📋 Salin Teks Log", fg_color=self.C_CARD_INNER,
            hover_color=self.C_BTN_SEC_HOVER, text_color=self.C_TEXT_MUTED,
            border_width=1, border_color=self.C_BORDER,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=6, height=26, width=125, command=self.copy_log
        )
        self.btn_copy_log.pack(side="right")

        # Container Text + Scrollbar
        text_container = ctk.CTkFrame(
            preview_card, fg_color=self.C_CODE_BG, corner_radius=8,
            border_width=1, border_color=self.C_BORDER
        )
        text_container.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))

        scrollbar = ctk.CTkScrollbar(text_container)
        scrollbar.pack(side="right", fill="y", padx=2, pady=2)

        self.preview_text = tk.Text(
            text_container, bg=self.C_CODE_BG, fg=self.C_TEXT_WHITE,
            font=("Consolas", 10), wrap=tk.NONE, yscrollcommand=scrollbar.set,
            relief=tk.FLAT, bd=0, padx=14, pady=12,
            spacing1=3, spacing3=3,
            selectbackground=self.C_BLUE, selectforeground="#FFFFFF",
            insertbackground="#F8FAFC"
        )
        self.preview_text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.preview_text.yview)

        # Apply Syntax Highlighting
        self._apply_syntax_highlighting(self.preview_text)

        # ----------------------------------------------------------------------
        # 4. ACTION BAR (Bottom Command Dock)
        # ----------------------------------------------------------------------
        action_bar = ctk.CTkFrame(self.root, fg_color="transparent")
        action_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))

        btn_folder = ctk.CTkButton(
            action_bar, text="📁 Buka Folder Laporan", fg_color=self.C_BTN_SEC,
            hover_color=self.C_BTN_SEC_HOVER, text_color=self.C_TEXT_WHITE,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=8, height=38, command=self.open_folder
        )
        btn_folder.pack(side="left", padx=(0, 12), anchor="n")

        # GitHub Column: Tombol GitHub + Label Peringatan Lampirkan .dmp
        github_col = ctk.CTkFrame(action_bar, fg_color="transparent")
        github_col.pack(side="left", anchor="n")

        btn_github = ctk.CTkButton(
            github_col, text="🌐 Laporkan ke GitHub", fg_color=self.C_BLUE,
            hover_color=self.C_BLUE_HOVER, text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=8, height=38, command=self.open_github_issue
        )
        btn_github.pack(anchor="w")

        lbl_dmp_warn = ctk.CTkLabel(
            github_col,
            text="Jangan lupa lampirkan file .dmp (jika ada) saat membuat Issue di GitHub!",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#F59E0B"
        )
        lbl_dmp_warn.pack(anchor="w", pady=(3, 0))

        self.copy_feedback_lbl = ctk.CTkLabel(
            action_bar, text="", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self.C_EMERALD
        )
        self.copy_feedback_lbl.pack(side="left", padx=14, anchor="n", pady=8)

        # Tutup Aplikasi with crisp Sengoku Crimson outline
        btn_close = ctk.CTkButton(
            action_bar, text="✕ Tutup Aplikasi", fg_color="transparent",
            border_width=1, border_color=self.C_CRIMSON, text_color=self.C_CRIMSON,
            hover_color=self.C_CRIMSON_BG, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=8, height=38, width=135, command=self.root.destroy
        )
        btn_close.pack(side="right", anchor="n")

    def _fade_in_step(self, alpha: float):
        """Menaikkan transparansi alpha secara bertahap hingga 1.0 (smooth fade-in)."""
        if alpha < 1.0:
            alpha = min(1.0, alpha + 0.08)
            self.root.attributes("-alpha", alpha)
            self.root.after(16, lambda: self._fade_in_step(alpha))
        else:
            self.root.attributes("-alpha", 1.0)

    def _apply_syntax_highlighting(self, text_widget: tk.Text):
        """Penyorotan sintaks multi-layer untuk diagnostik log game."""
        text_widget.tag_config("err_line", foreground=self.C_CRIMSON)   # Merah: STOP, Error, Crash, Segfault
        text_widget.tag_config("warn_line", foreground=self.C_AMBER)     # Kuning/Amber: Warn, Warning, Fallback
        text_widget.tag_config("sys_line", foreground=self.C_CYAN)       # Cyan: Subsystem bbgpu, avplayer, memory
        text_widget.tag_config("ok_line", foreground="#34D399")          # Hijau: Success, Initialized, Free, Exit
        text_widget.tag_config("hdr_line", foreground="#818CF8")         # Indigo: Header separator
        text_widget.tag_config("meta_line", foreground=self.C_TEXT_DIM)  # Abu: Timestamps & line numbers
        text_widget.tag_config("norm_line", foreground="#CBD5E1")        # Slate: Teks biasa

        pattern_err = re.compile(r'(STOP:|STOP\b|Error|CRASH|FATAL|CRITICAL|0xC0000005|Access Violation|\bFAILED\b|ASSERTION)', re.IGNORECASE)
        pattern_warn = re.compile(r'(\bWARN\b|\bWARNING\b|fallback|unhandled|not found)', re.IGNORECASE)
        pattern_sys = re.compile(r'(\[bbgpu\]|\[audio\]|\[avplayer\]|\[vulkan\]|\[runtime_memory\]|\[kernel\])', re.IGNORECASE)
        pattern_ok = re.compile(r'(\bsuccessfully\b|\bFREE\b|\bEXIT\b|\bSUCCESS\b|\bOK\b|Initialized)', re.IGNORECASE)

        for line in self.content.splitlines():
            line_str = line + "\n"
            if line.startswith("===") or line.startswith("---") or line.startswith("###"):
                tag = "hdr_line"
            elif pattern_err.search(line):
                tag = "err_line"
            elif pattern_warn.search(line):
                tag = "warn_line"
            elif pattern_sys.search(line):
                tag = "sys_line"
            elif pattern_ok.search(line):
                tag = "ok_line"
            elif line.startswith("[2026-") or "Timestamp:" in line:
                tag = "meta_line"
            else:
                tag = "norm_line"

            text_widget.insert("end", line_str, tag)

        text_widget.configure(state="disabled")

    def copy_path(self):
        """Menyalin path file laporan ke clipboard dengan feedback visual dinamis."""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.report_path)
        self.root.update()

        if HAS_CTK:
            self.btn_copy.configure(text="✓ Tersalin!", fg_color="#059669")
            self.root.after(2500, lambda: self.btn_copy.configure(text="📋 Salin Path", fg_color=self.C_BTN_SEC))
        self.copy_feedback_lbl.configure(text="✓ Path laporan berhasil disalin!")
        self.root.after(3000, lambda: self.copy_feedback_lbl.configure(text=""))

    def copy_log(self):
        """Menyalin seluruh isi cuplikan log ke clipboard."""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.content)
        self.root.update()

        if HAS_CTK:
            self.btn_copy_log.configure(text="✓ Log Tersalin!", fg_color="#059669")
            self.root.after(2500, lambda: self.btn_copy_log.configure(text="📋 Salin Teks Log", fg_color=self.C_CARD_INNER))
        self.copy_feedback_lbl.configure(text="✓ Cuplikan log berhasil disalin!")
        self.root.after(3000, lambda: self.copy_feedback_lbl.configure(text=""))

    def open_folder(self):
        """Membuka folder crashes di Windows Explorer."""
        try:
            if os.path.isdir(self.crashes_dir):
                if sys.platform == "win32":
                    os.startfile(self.crashes_dir)
                else:
                    subprocess.Popen(["xdg-open", self.crashes_dir])
            else:
                messagebox.showerror("Error", f"Folder tidak ditemukan:\n{self.crashes_dir}")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka folder:\n{e}")

    def open_github_issue(self):
        """Membuka browser ke GitHub New Issue dengan template laporan otomatis."""
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            title = f"[CRASH] {ts} - {self.reason}"
            snippet = "\n".join(self.content.splitlines()[:60])
            body = (
                f"### Deskripsi Crash\n"
                f"Game crash otomatis terdeteksi oleh Sengoku Basara 4 PC Launcher.\n\n"
                f"**Trigger Reason**: `{self.reason}`\n"
                f"**Game Version**: `{get_game_version()}`\n"
                f"**GPU**: `{get_gpu_info()}`\n"
                f"**Memory**: `{self.mem_info['summary']}`\n"
                f"**Dump File**: `{self.dmp_status}`\n"
                f"**OS**: `{platform.system()} {platform.release()} ({platform.version()})`\n\n"
                f"### Cuplikan Log Terakhir:\n"
                f"```text\n{snippet}\n```\n\n"
                f"*Laporan lengkap tersimpan di: `{os.path.basename(self.report_path)}`*\n"
                f"*Catatan: Mohon lampirkan file .dmp (jika ada) saat membuat Issue ini!*"
            )

            title_enc = urllib.parse.quote(title)
            body_enc = urllib.parse.quote(body)
            url = f"https://github.com/{GITHUB_REPO}/issues/new?title={title_enc}&body={body_enc}"

            webbrowser.open(url)
            self.copy_feedback_lbl.configure(text="✓ Membuka browser GitHub...")
            self.root.after(3000, lambda: self.copy_feedback_lbl.configure(text=""))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka browser GitHub:\n{e}")

    def show(self):
        """Menampilkan dialog dan menangani interupsi bersih."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            try:
                self.root.destroy()
            except Exception:
                pass

    def _build_fallback_ui(self):
        """Cadangan Tkinter jika CustomTkinter tidak tersedia."""
        self.root = tk.Tk()
        self.root.title("Sengoku Basara 4 Sumeragi — Diagnostic & Crash Reporter")
        self.root.configure(bg=self.C_BG)
        self.root.geometry("880x680")
        self.root.minsize(800, 600)

        self.root.attributes("-alpha", 0.0)
        self._fade_in_step(0.0)

        container = tk.Frame(self.root, bg=self.C_BG, padx=20, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        hdr = tk.Frame(container, bg=self.C_CARD, highlightthickness=1, highlightbackground=self.C_BORDER, padx=16, pady=12)
        hdr.pack(fill=tk.X, pady=(0, 12))

        top = tk.Frame(hdr, bg=self.C_CARD)
        top.pack(fill=tk.X)
        badge = tk.Label(top, text=" ⚡ CRASH DETECTED ", bg=self.C_CRIMSON, fg="#FFF", font=("Segoe UI", 10, "bold"), padx=6, pady=2)
        badge.pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(top, text="Sengoku Basara 4 // Crash Reporter", bg=self.C_CARD, fg=self.C_TEXT_WHITE, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)

        sub_msg = "Game terdeteksi crash. Jangan panik! Laporan diagnostik otomatis telah dibuat.\nKirimkan file ini ke developer agar bug segera diperbaiki."
        tk.Label(hdr, text=sub_msg, bg=self.C_CARD, fg=self.C_TEXT_MUTED, font=("Segoe UI", 10), justify=tk.LEFT).pack(anchor="w", pady=(8, 0))

        pcard = tk.Frame(container, bg=self.C_CARD, highlightthickness=1, highlightbackground=self.C_BORDER, padx=14, pady=10)
        pcard.pack(fill=tk.X, pady=(0, 12))
        tk.Label(pcard, text="LOKASI FILE LAPORAN LENGKAP:", bg=self.C_CARD, fg=self.C_TEXT_DIM, font=("Segoe UI", 8, "bold")).pack(anchor="w")

        prow = tk.Frame(pcard, bg=self.C_CARD)
        prow.pack(fill=tk.X, pady=(4, 0))
        pentry = tk.Entry(prow, bg=self.C_CODE_BG, fg="#34D399", font=("Consolas", 10), relief=tk.FLAT, highlightthickness=1, highlightbackground=self.C_BORDER)
        pentry.insert(0, self.report_path)
        pentry.config(state="readonly")
        pentry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 8))

        self.btn_copy = tk.Button(prow, text="Salin Path", bg=self.C_BTN_SEC, fg=self.C_TEXT_WHITE, font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12, pady=4, cursor="hand2", command=self.copy_path)
        self.btn_copy.pack(side=tk.RIGHT)

        tcard = tk.Frame(container, bg=self.C_CODE_BG, highlightthickness=1, highlightbackground=self.C_BORDER)
        tcard.pack(fill=tk.BOTH, expand=True, pady=(0, 14))

        sb = tk.Scrollbar(tcard)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        text_w = tk.Text(tcard, bg=self.C_CODE_BG, fg=self.C_TEXT_WHITE, font=("Consolas", 10), wrap=tk.NONE, yscrollcommand=sb.set, relief=tk.FLAT, bd=0, padx=12, pady=10, spacing1=3, spacing3=3)
        text_w.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=text_w.yview)

        self._apply_syntax_highlighting(text_w)

        bar = tk.Frame(container, bg=self.C_BG)
        bar.pack(fill=tk.X)

        tk.Button(bar, text="📁 Buka Folder Laporan", bg=self.C_BTN_SEC, fg=self.C_TEXT_WHITE, font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=14, pady=6, cursor="hand2", command=self.open_folder).pack(side=tk.LEFT, padx=(0, 8), anchor="n")

        gh_col = tk.Frame(bar, bg=self.C_BG)
        gh_col.pack(side=tk.LEFT, padx=(0, 8), anchor="n")
        tk.Button(gh_col, text="🌐 Kirim ke GitHub", bg=self.C_BLUE, fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=14, pady=6, cursor="hand2", command=self.open_github_issue).pack(anchor="w")
        tk.Label(gh_col, text="Jangan lupa lampirkan file .dmp (jika ada) saat membuat Issue di GitHub!", bg=self.C_BG, fg="#F59E0B", font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))

        self.copy_feedback_lbl = tk.Label(bar, text="", bg=self.C_BG, fg=self.C_EMERALD, font=("Segoe UI", 9, "bold"))
        self.copy_feedback_lbl.pack(side=tk.LEFT, padx=6, anchor="n", pady=4)

        tk.Button(bar, text="✕ Tutup Aplikasi", bg=self.C_CRIMSON_BG, fg=self.C_CRIMSON, font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=14, pady=6, cursor="hand2", command=self.root.destroy).pack(side=tk.RIGHT, anchor="n")


def launch_game():
    """Main game launcher execution workflow."""
    print("================================================================")
    print("       Sengoku Basara 4 Sumeragi — Native PC Launcher")
    print("================================================================")

    # 1. Check executable
    exe = "basara_pc.exe"
    if not os.path.isfile(exe):
        msg = f"Executable '{exe}' tidak ditemukan di direktori saat ini!"
        print(f"[ERROR] {msg}")
        if HAS_TK:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Launcher Error", msg)
        sys.exit(1)

    # 2. Check boot binary
    boot_bin = None
    for cand in ["boot-linked.bin", os.path.join("out", "boot-linked.bin")]:
        if os.path.isfile(cand):
            boot_bin = cand
            break

    if not boot_bin:
        msg = "File boot (boot-linked.bin / out/boot-linked.bin) belum dibuat!\nSilakan jalankan Basara4_Launcher.exe untuk auto-prepare."
        print(f"[ERROR] {msg}")
        if HAS_TK:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Launcher Error", msg)
        sys.exit(1)

    # 3. Check game data (app0)
    app0 = None
    for cand in [os.path.join("extracted_game", "app0"), "app0"]:
        if os.path.isdir(cand):
            app0 = cand
            break

    if not app0:
        app0 = os.path.join("extracted_game", "app0")
        print(f"[WARNING] Direktori game app0 tidak ditemukan, default ke '{app0}'")

    # 4. Construct command line
    cmd = [os.path.abspath(exe), os.path.abspath(boot_bin)]

    import_names = os.path.join("out", "import_names.txt")
    if os.path.isfile(import_names):
        cmd.extend(["--import-names", os.path.abspath(import_names)])

    content_bin = os.path.join("out", "content.bin")
    if os.path.isfile(content_bin):
        cmd.extend(["--content-profile", os.path.abspath(content_bin)])

    patches_bin = os.path.join("out", "patches.bin")
    if os.path.isfile(patches_bin):
        cmd.extend(["--patches", os.path.abspath(patches_bin)])

    cmd.extend(["--app0", os.path.abspath(app0), "--user", os.path.abspath("user")])

    # 5. Environment configuration
    env = os.environ.copy()
    os.makedirs(os.path.join("user", "logs"), exist_ok=True)
    log_file_path = os.path.abspath(os.path.join("user", "logs", "last_run.log"))

    # Gamepad mappings if present
    for map_path in [os.path.join("user", "gamepad_mapping.txt"), "gamepad_mapping.txt"]:
        if os.path.isfile(map_path):
            env["SDL_GAMECONTROLLERCONFIG_FILE"] = os.path.abspath(map_path)
            break

    print(f"[LAUNCHER] Menjalankan: {' '.join(cmd)}")
    print(f"[LAUNCHER] Logging output ke: {log_file_path}")
    print("[LAUNCHER] Game sedang berjalan. Jangan tutup jendela terminal ini...")

    # 6. Execute subprocess and redirect output to log
    exit_code = 0
    with open(log_file_path, "w", encoding="utf-8", errors="replace") as log_file:
        try:
            proc = subprocess.Popen(cmd, cwd=os.getcwd(), env=env, stdout=log_file, stderr=subprocess.STDOUT)
            proc.wait()
            exit_code = proc.returncode
        except Exception as e:
            print(f"[LAUNCHER] Fatal error menjalankan game: {e}")
            exit_code = -1

    print(f"[LAUNCHER] Game proses selesai dengan Exit Code: {exit_code}")

    # 7. Smart Crash Detection
    is_crash, reason, matched = scan_log_for_crash(exit_code, log_file_path)

    if is_crash:
        print(f"\n[CRASH DETECTED] Alasan: {reason}")
        print("[CRASH DETECTED] Membuat file laporan crash...")
        report_path, log_copy, content = generate_crash_report(exit_code, log_file_path, reason, matched)
        print(f"[CRASH DETECTED] Laporan berhasil dibuat: {report_path}")

        if HAS_TK:
            crashes_dir = os.path.abspath("crashes")
            dialog = CrashDialog(report_path, crashes_dir, content, exit_code, reason)
            dialog.show()
        else:
            print("================================================================")
            print("                LAPORAN CRASH BERHASIL DISIMPAN")
            print("================================================================")
            print(f"File laporan: {report_path}")
            print(f"Salinan log : {log_copy}")
            print("Silakan kirimkan file ini ke developer.")
            print("================================================================")
    else:
        print("[LAUNCHER] Sesi game berakhir normal tanpa crash.")


if __name__ == "__main__":
    # Test simulation flag for verifying the dialog without launching the game
    if "--test-crash" in sys.argv:
        print("[TEST] Menjalankan simulasi crash dialog...")
        sim_log = find_latest_log()
        dummy_code = -1073741819 # 0xC0000005
        is_crash, reason, matched = scan_log_for_crash(dummy_code, sim_log)
        report_path, log_copy, content = generate_crash_report(dummy_code, sim_log, "TEST SIMULATION (--test-crash), not a real crash: " + reason, matched)
        if HAS_TK:
            dialog = CrashDialog(report_path, os.path.abspath("crashes"), content, dummy_code, reason)
            dialog.show()
        else:
            print(f"Report generated: {report_path}")
        sys.exit(0)

    launch_game()
