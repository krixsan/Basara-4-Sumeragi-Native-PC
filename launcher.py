#!/usr/bin/env python3
"""
Sengoku Basara 4 Sumeragi — PC Native Port
Studio-Grade AAA Graphical Launcher & Configuration Engine
v2.1.0 Release — Performance Mode, Auto-Updater & Enhanced UI
"""

import os
import sys
import ctypes
from ctypes import wintypes
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox, filedialog, ttk
import zipfile
import re
import glob
import time
import json
import winreg
import webbrowser
import urllib.parse
import shutil
import platform
import math
from datetime import datetime

# ==============================================================================
# BASE DIRECTORY & PATH RESOLUTION (Enterprise Path Resolver)
# ==============================================================================
if getattr(sys, "frozen", False):
    # Running inside PyInstaller onefile/onedir bundle
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running directly as Python script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Always switch working directory to BASE_DIR so relative paths and DLLs resolve correctly
try:
    os.chdir(BASE_DIR)
except Exception:
    pass

def base_path(*paths) -> str:
    """Resolves paths strictly relative to BASE_DIR (executable location)."""
    return os.path.normpath(os.path.join(BASE_DIR, *paths))

# Ensure standard runtime folders exist relative to executable
os.makedirs(base_path("crashes"), exist_ok=True)
os.makedirs(base_path("user", "logs"), exist_ok=True)
os.makedirs(base_path("user", "crashes"), exist_ok=True)

# --- Auto-Dependency Verification & Installation (customtkinter, psutil, minidump) ---
def ensure_dependencies():
    """Ensures required GUI, diagnostic, and crash analysis dependencies are available."""
    required = ["customtkinter", "psutil", "minidump"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"[LAUNCHER] Installing missing dependencies: {', '.join(missing)}...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", *missing],
                check=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            print("[LAUNCHER] Dependencies installed successfully.")
        except Exception as e:
            print(f"[LAUNCHER] Warning: Automatic pip install failed: {e}")

ensure_dependencies()

try:
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import minidump
    from minidump.minidumpfile import MinidumpFile
    HAS_MINIDUMP = True
except ImportError:
    HAS_MINIDUMP = False

from PIL import Image, ImageDraw, ImageTk, ImageFilter, ImageChops

# Enable Windows High-DPI Awareness and Custom Taskbar App ID
try:
    if sys.platform == "win32":
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("basara4.sumeragi.pc.launcher.2")
except Exception:
    pass

# Dynamic Auto-Builder import
HAS_AUTO_BUILDER = False
auto_builder = None
try:
    import auto_builder
    HAS_AUTO_BUILDER = True
except ImportError:
    try:
        from scripts import auto_builder
        HAS_AUTO_BUILDER = True
    except ImportError:
        HAS_AUTO_BUILDER = False

# --- Theme Configuration ---
WIDTH = 960
HEIGHT = 660

COLOR_BG_DARK = "#0a0c12"
COLOR_GOLD = "#FFD700"
COLOR_GOLD_BRIGHT = "#E5C158"
COLOR_AMBER = "#F1C40F"
COLOR_CRIMSON = "#8B0000"
COLOR_CRIMSON_DARK = "#660D12"
COLOR_CRIMSON_LIGHT = "#A81E26"
COLOR_CRIMSON_HOVER = "#A0121A"
COLOR_TEXT_WHITE = "#FFFFFF"
COLOR_TEXT_MUTED = "#A9B7C6"
COLOR_TEXT_SUB = "#A9A9A9"
COLOR_SUCCESS = "#2ECC71"
COLOR_ERROR = "#E74C3C"

FONT_FAMILY = "Segoe UI"
FONT_TITLE = "Segoe UI Black"
FONT_SUBTITLE = "Segoe UI Semibold"

INI_FILE = base_path("basara.ini")
FALLBACK_INI = base_path("basara.ini")


def read_ini():
    settings = {
        "output_res": "1920x1080",
        "render_res": "1080",
        "fullscreen": "1",
        "fps_limit": "144",
        "anisotropy": "16",
        "anti_aliasing": "0",
        "render_scale": "1.0",
        "fsr1": "1",
        "rcas": "1",
        "rcas_strength": "75",
        "skip_intro": "0",
        "show_fps": "1",
        "performance_mode": "0",
        "safe_mode": "0",
        "async_pipelines": "1",
        "process_priority": "above_normal",
        "telemetry_upload": "ask",
        "telemetry_endpoint": "https://api.github.com/repos/krixsan/Basara-4-Sumeragi-Native-PC/telemetry",
        "log_level": "info",
        "first_run_done": "0",
        "legal_acknowledged": "0",
    }
    path = INI_FILE if os.path.exists(INI_FILE) else (FALLBACK_INI if os.path.exists(FALLBACK_INI) else None)
    if path:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#") and "=" in s:
                        k, v = s.split("=", 1)
                        settings[k.strip()] = v.strip()
        except Exception:
            pass
    return settings


def write_ini(data):
    target = INI_FILE
    lines = []
    written = set()

    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    if not lines:
        lines = [
            "# ===========================================================\n",
            "# Sengoku Basara 4 Sumeragi PC Engine Configuration\n",
            "# Native x86_64 Runtime & Vulkan 1.3 Engine\n",
            "# ===========================================================\n",
        ]

    new_lines = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, _ = s.split("=", 1)
            k = k.strip()
            if k in data:
                new_lines.append(f"{k}={data[k]}\n")
                written.add(k)
                continue
        new_lines.append(line)

    for k, v in data.items():
        if k not in written:
            new_lines.append(f"{k}={v}\n")

    try:
        with open(target, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"Warning: unable to save {target}: {e}")


def check_game_integrity(boot_bin=None):
    """
    Checks the integrity of boot-linked.bin and link.json.
    Verifies:
    1. boot-linked.bin exists and size is >= 29,000,000 bytes (smaller size indicates missing audio/threading SPRX modules).
    2. out/link.json contains at least 7 modules, including libSceNgs2.sprx and libSceAjm.sprx.
    Returns (is_valid: bool, issue_description: str | None).
    """
    if not boot_bin:
        for cand in ["boot-linked.bin", os.path.join("out", "boot-linked.bin")]:
            if os.path.isfile(cand):
                boot_bin = cand
                break

    if not boot_bin or not os.path.isfile(boot_bin):
        return False, "boot-linked.bin not found"

    # 1. Size check: must be at least 29,000,000 bytes
    try:
        size = os.path.getsize(boot_bin)
        if size < 29000000:
            return False, f"Game files incomplete (Audio modules missing) — boot-linked.bin size {size:,} bytes < 29,000,000 bytes"
    except Exception as e:
        return False, f"Cannot verify boot-linked.bin size: {e}"

    # 2. link.json check: must contain >= 7 modules including libSceNgs2.sprx and libSceAjm.sprx
    link_json = None
    cands = []
    if boot_bin:
        cands.append(os.path.join(os.path.dirname(boot_bin), "link.json"))
    cands.extend([os.path.join("out", "link.json"), "link.json"])
    for cand in cands:
        if os.path.isfile(cand):
            link_json = cand
            break

    if link_json:
        try:
            with open(link_json, "r", encoding="utf-8") as f:
                data = json.load(f)
            mods = data.get("modules", [])
            files = [m.get("file", "") for m in mods if isinstance(m, dict)]
            if len(mods) < 7 or "libSceNgs2.sprx" not in files or "libSceAjm.sprx" not in files:
                return False, (
                    f"Incomplete module linking ({len(mods)}/7 modules linked). "
                    f"Missing native audio modules (libSceNgs2/libSceAjm)."
                )
        except Exception:
            pass

    return True, None


def check_link_health(boot_bin=None):
    """Backward compatibility alias for check_game_integrity."""
    return check_game_integrity(boot_bin)


def verify_game_installation():
    missing = []
    exe = base_path("basara_pc.exe")
    if not os.path.isfile(exe):
        missing.append("basara_pc.exe")

    boot_bin = None
    for cand in [base_path("boot-linked.bin"), base_path("out", "boot-linked.bin")]:
        if os.path.isfile(cand):
            boot_bin = cand
            break

    app0 = None
    for cand in [base_path("extracted_game", "app0"), base_path("app0")]:
        if os.path.isdir(cand):
            app0 = cand
            break

    eboot_found = False
    if app0:
        if os.path.isfile(os.path.join(app0, "eboot.bin")):
            eboot_found = True
        else:
            missing.append(f"{app0}/eboot.bin")
    else:
        missing.append("Game folder ('extracted_game/app0' or 'app0')")

    link_warning = None
    if boot_bin:
        is_healthy, warning = check_link_health(boot_bin)
        if not is_healthy:
            link_warning = warning

    return missing, exe, boot_bin, app0, eboot_found, link_warning


def check_dependencies(show_dialogs=True):
    """
    Evaluates system dependencies:
    - Vulkan 1.3 loader (vulkan-1.dll in PATH, System32, or Khronos registry)
    - Microsoft Visual C++ 2015-2022 Redistributable (x64) via registry
    - Windows Version >= 10.0.17763 (Build 17763, Version 1809)
    - Free Disk Space >= 500 MB
    Returns a status dict and optionally prompts the user with download links if missing.
    """
    results = {
        "vulkan": False,
        "vcredist": False,
        "winver": True,
        "disk": True,
        "disk_mb": 0,
        "build": 0
    }

    # 1. Vulkan Loader Check
    vk_found = False
    try:
        import ctypes.util
        if ctypes.util.find_library("vulkan-1"):
            vk_found = True
    except Exception:
        pass
    if not vk_found:
        system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "vulkan-1.dll")
        if os.path.isfile(system32):
            vk_found = True
    if not vk_found:
        for reg_path in [r"SOFTWARE\Khronos\Vulkan\Drivers", r"SOFTWARE\WOW6432Node\Khronos\Vulkan\Drivers"]:
            try:
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                vk_found = True
                winreg.CloseKey(k)
                break
            except Exception:
                pass
    results["vulkan"] = vk_found

    # 2. VC++ Redist 2015-2022 x64 Check
    vc_found = False
    for subkey in [
        r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"
    ]:
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey)
            val, _ = winreg.QueryValueEx(k, "Installed")
            if val == 1:
                vc_found = True
            winreg.CloseKey(k)
            if vc_found:
                break
        except Exception:
            pass
    if not vc_found:
        sys32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
        if os.path.isfile(os.path.join(sys32, "vcruntime140.dll")) and os.path.isfile(os.path.join(sys32, "msvcp140.dll")):
            vc_found = True
    results["vcredist"] = vc_found

    # 3. Windows Version Check (>= Build 17763)
    try:
        v_parts = platform.version().split(".")
        build_num = int(v_parts[2]) if len(v_parts) >= 3 else 0
        results["build"] = build_num
        if build_num > 0 and build_num < 17763:
            results["winver"] = False
    except Exception:
        results["winver"] = True

    # 4. Disk Space Check (>= 500 MB)
    try:
        free_mb = shutil.disk_usage(BASE_DIR).free // (1024 * 1024)
        results["disk_mb"] = free_mb
        results["disk"] = (free_mb >= 500)
    except Exception:
        results["disk"] = True
        results["disk_mb"] = 1024

    if show_dialogs:
        MB_YESNO = 0x04
        MB_ICONWARNING = 0x30
        IDYES = 6

        # Missing Vulkan prompt
        if not results["vulkan"]:
            try:
                res = ctypes.windll.user32.MessageBoxW(
                    0,
                    "Vulkan Loader (vulkan-1.dll) was not found on your system!\n\n"
                    "Sengoku Basara 4 PC requires a Vulkan 1.3 capable GPU and the Vulkan Runtime.\n\n"
                    "Would you like to open the official LunarG Vulkan Runtime download page?\n"
                    "(https://vulkan.lunarg.com/sdk/home#windows)",
                    "Basara 4 PC — Vulkan Runtime Required",
                    MB_YESNO | MB_ICONWARNING
                )
                if res == IDYES:
                    webbrowser.open("https://vulkan.lunarg.com/sdk/home#windows")
            except Exception:
                pass

        # Missing VC++ Redist prompt
        if not results["vcredist"]:
            try:
                res = ctypes.windll.user32.MessageBoxW(
                    0,
                    "Microsoft Visual C++ 2015-2022 Redistributable (x64) is missing!\n\n"
                    "The native PC engine requires this component to launch.\n\n"
                    "Would you like to download it directly from Microsoft now?\n"
                    "(https://aka.ms/vs/17/release/vc_redist.x64.exe)",
                    "Basara 4 PC — VC++ Redistributable Required",
                    MB_YESNO | MB_ICONWARNING
                )
                if res == IDYES:
                    webbrowser.open("https://aka.ms/vs/17/release/vc_redist.x64.exe")
            except Exception:
                pass

        # Old Windows version warning
        if not results["winver"]:
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Notice: Your Windows version build ({results['build']}) is older than Build 17763 (Windows 10 1809).\n\n"
                    "The engine will continue on a best-effort basis, but you may experience reduced stability or scheduling issues.",
                    "Basara 4 PC — OS Version Notice",
                    0x40
                )
            except Exception:
                pass

        # Low disk space warning
        if not results["disk"]:
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Warning: Low disk space detected ({results['disk_mb']} MB available).\n\n"
                    "At least 500 MB free space is recommended for shader caches and temporary link data.",
                    "Basara 4 PC — Low Storage Warning",
                    MB_ICONWARNING
                )
            except Exception:
                pass

    return results


def validate_eboot_file(path: str):
    """
    Validates magic bytes and minimum file size (>10 MB) of eboot.bin.
    Supports BOTH decrypted SELF and standard ELF formats:
    - ELF magic: b'\\x7fELF' (little-endian x86-64)
    - SELF magic: b'SCE\\x00' or b'\\x4f\\x15=\\x1d' (0x1D3D154F) or 0x1F153017
    """
    if not os.path.isfile(path):
        return False, "File does not exist."

    size = os.path.getsize(path)
    if size < 10 * 1024 * 1024:
        return False, f"File size ({size / (1024*1024):.1f} MB) is under 10 MB. Expected complete eboot.bin."

    try:
        with open(path, "rb") as f:
            header = f.read(16)
        if len(header) < 4:
            return False, "File is truncated or unreadable."

        # ELF check
        if header[:4] == b"\x7fELF":
            return True, "Standard x86-64 ELF executable"

        # SELF formats (Sony decrypted executable container)
        if header[:4] in (b"SCE\x00", b"\x4f\x15\x3d\x1d", b"\x1f\x15\x30\x17", b"\x17\x30\x15\x1f"):
            return True, "Decrypted PlayStation 4 SELF binary"
        if header[:3] == b"SCE":
            return True, "PlayStation 4 SELF binary"

        return False, f"Unrecognized header magic (got {header[:4]!r}). Expected decrypted PS4 SELF or ELF."
    except Exception as e:
        return False, f"Unable to read file: {e}"


class FirstRunWizard(tk.Toplevel):
    """
    5-Step Interactive First-Run Setup & Compliance Wizard:
    Step 1: Welcome & Legal Dump Information
    Step 2: Legal Checkboxes (Fair Use & Personal Ownership)
    Step 3: Locate eboot.bin & Magic Byte / Size Validation (SELF & ELF)
    Step 4: Auto-Build binary image via auto_builder with streaming log
    Step 5: Completion & Launch Direct / Back to Launcher
    """
    def __init__(self, parent=None, on_complete=None, on_play=None):
        super().__init__(parent)
        self.parent = parent
        self.on_complete = on_complete
        self.on_play = on_play
        self.title("Sengoku Basara 4 Sumeragi — Setup Wizard")
        self.geometry("640x500")
        self.resizable(False, False)
        self.configure(bg="#0c0e14")

        if parent:
            self.transient(parent)
            self.grab_set()

        self.apply_dark_title_bar()
        self.center_window()

        self.current_step = 1
        self.selected_eboot = ""
        self.build_framework()
        self.show_step(1)

    def apply_dark_title_bar(self):
        if sys.platform != "win32":
            return
        try:
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id()) or self.winfo_id()
            value = ctypes.c_int(2)
            for attr in (20, 19):
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                    break
        except Exception:
            pass

    def center_window(self):
        self.update_idletasks()
        w, h = 640, 500
        if self.parent:
            x = self.parent.winfo_x() + (self.parent.winfo_width() - w) // 2
            y = self.parent.winfo_y() + (self.parent.winfo_height() - h) // 2
        else:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            x = (sw - w) // 2
            y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def build_framework(self):
        # 1. Header Frame
        self.header_frame = tk.Frame(self, bg="#141822", height=76)
        self.header_frame.pack(fill="x", side="top")
        self.header_frame.pack_propagate(False)

        self.lbl_head_title = tk.Label(
            self.header_frame,
            text="SENGOKU BASARA 4 SUMERAGI PC",
            font=(FONT_TITLE, 13, "bold"),
            fg=COLOR_GOLD_BRIGHT,
            bg="#141822"
        )
        self.lbl_head_title.pack(anchor="w", padx=24, pady=(12, 2))

        self.lbl_head_sub = tk.Label(
            self.header_frame,
            text="First-Run Setup & Compliance Wizard",
            font=(FONT_FAMILY, 8),
            fg=COLOR_TEXT_MUTED,
            bg="#141822"
        )
        self.lbl_head_sub.pack(anchor="w", padx=24)

        # 2. Main Body Container
        self.body_container = tk.Frame(self, bg="#0c0e14")
        self.body_container.pack(fill="both", expand=True, padx=28, pady=16)

        # 3. Bottom Navigation Bar
        self.nav_frame = tk.Frame(self, bg="#141822", height=58)
        self.nav_frame.pack(fill="x", side="bottom")
        self.nav_frame.pack_propagate(False)

        self.btn_skip = tk.Button(
            self.nav_frame,
            text="Skip Wizard",
            font=(FONT_FAMILY, 8),
            fg=COLOR_TEXT_MUTED,
            bg="#1c2230",
            activeforeground="#ffffff",
            activebackground="#2b3448",
            relief="flat",
            padx=14,
            pady=4,
            command=self.skip_wizard
        )
        self.btn_skip.pack(side="left", padx=20, pady=12)

        self.btn_next = tk.Button(
            self.nav_frame,
            text="Get Started >",
            font=(FONT_FAMILY, 9, "bold"),
            fg="#ffffff",
            bg=COLOR_CRIMSON,
            activeforeground="#ffffff",
            activebackground=COLOR_CRIMSON_HOVER,
            relief="flat",
            padx=18,
            pady=4,
            command=self.go_next
        )
        self.btn_next.pack(side="right", padx=20, pady=12)

        self.btn_back = tk.Button(
            self.nav_frame,
            text="< Back",
            font=(FONT_FAMILY, 8),
            fg=COLOR_TEXT_WHITE,
            bg="#1c2230",
            activeforeground="#ffffff",
            activebackground="#2b3448",
            relief="flat",
            padx=14,
            pady=4,
            command=self.go_back
        )
        self.btn_back.pack(side="right", padx=(0, 10), pady=12)

    def clear_body(self):
        for widget in self.body_container.winfo_children():
            widget.destroy()

    def show_step(self, step):
        self.current_step = step
        self.clear_body()

        if step == 1:
            self.render_step1()
        elif step == 2:
            self.render_step2()
        elif step == 3:
            self.render_step3()
        elif step == 4:
            self.render_step4()
        elif step == 5:
            self.render_step5()

    def render_step1(self):
        self.lbl_head_sub.config(text="Step 1 of 5: Welcome & Legal Asset Notice")
        self.btn_back.pack_forget()
        self.btn_skip.pack(side="left", padx=20, pady=12)
        self.btn_next.config(text="Get Started >", state="normal", command=self.go_next)

        lbl_welcome = tk.Label(
            self.body_container,
            text="Welcome to the PC Port of Sengoku Basara 4 Sumeragi!",
            font=(FONT_SUBTITLE, 11, "bold"),
            fg=COLOR_TEXT_WHITE,
            bg="#0c0e14"
        )
        lbl_welcome.pack(anchor="w", pady=(10, 8))

        desc = (
            "This software is an open-source native PC runtime wrapper and Vulkan presentation engine.\n\n"
            "To experience the game on PC, you must provide your own legally obtained game executable\n"
            "(eboot.bin) dumped from your legally purchased PlayStation 4 disc or digital copy.\n\n"
            "• Zero Piracy Guarantee: No copyrighted game assets or binaries are bundled.\n"
            "• First-Run Automation: This wizard will guide you to locate your eboot.bin and\n"
            "  automatically build out/boot-linked.bin in under 2 minutes.\n\n"
            "Click 'Get Started' to proceed, or 'Skip Wizard' if you prefer manual configuration."
        )
        lbl_desc = tk.Label(
            self.body_container,
            text=desc,
            font=(FONT_FAMILY, 9),
            fg=COLOR_TEXT_MUTED,
            bg="#0c0e14",
            justify="left"
        )
        lbl_desc.pack(anchor="w", pady=4)

    def render_step2(self):
        self.lbl_head_sub.config(text="Step 2 of 5: Legal & Fair-Use Acknowledgment")
        self.btn_skip.pack(side="left", padx=20, pady=12)
        self.btn_back.pack(side="right", padx=(0, 10), pady=12)
        self.btn_next.config(text="Next >", state="disabled", command=self.go_next)

        lbl_title = tk.Label(
            self.body_container,
            text="Legal Compliance & Fair-Use Terms",
            font=(FONT_SUBTITLE, 11, "bold"),
            fg=COLOR_TEXT_WHITE,
            bg="#0c0e14"
        )
        lbl_title.pack(anchor="w", pady=(8, 8))

        lbl_desc = tk.Label(
            self.body_container,
            text="Please read and confirm the following compliance statements to continue:",
            font=(FONT_FAMILY, 9),
            fg=COLOR_TEXT_MUTED,
            bg="#0c0e14"
        )
        lbl_desc.pack(anchor="w", pady=(0, 16))

        self.var_own_copy = tk.BooleanVar(value=False)
        self.var_dump_self = tk.BooleanVar(value=False)

        def on_toggle():
            if self.var_own_copy.get() and self.var_dump_self.get():
                self.btn_next.config(state="normal")
            else:
                self.btn_next.config(state="disabled")

        frame_cb = tk.Frame(self.body_container, bg="#121620", padx=16, pady=16, highlightthickness=1, highlightbackground="#222a3a")
        frame_cb.pack(fill="x", pady=8)

        cb1 = tk.Checkbutton(
            frame_cb,
            text="I confirm that I own a legally purchased copy of Sengoku Basara 4 Sumeragi for PS4.",
            variable=self.var_own_copy,
            command=on_toggle,
            font=(FONT_FAMILY, 9, "bold"),
            fg=COLOR_TEXT_WHITE,
            bg="#121620",
            activeforeground=COLOR_GOLD,
            activebackground="#121620",
            selectcolor="#1c2230"
        )
        cb1.pack(anchor="w", pady=(0, 12))

        cb2 = tk.Checkbutton(
            frame_cb,
            text="I confirm that I have dumped / will dump eboot.bin myself from my legally owned PS4 console.",
            variable=self.var_dump_self,
            command=on_toggle,
            font=(FONT_FAMILY, 9, "bold"),
            fg=COLOR_TEXT_WHITE,
            bg="#121620",
            activeforeground=COLOR_GOLD,
            activebackground="#121620",
            selectcolor="#1c2230"
        )
        cb2.pack(anchor="w")

        lbl_note = tk.Label(
            self.body_container,
            text="Note: Searching PS4 homebrew community forums will provide guides on dumping your disc.",
            font=(FONT_FAMILY, 8, "italic"),
            fg=COLOR_TEXT_SUB,
            bg="#0c0e14"
        )
        lbl_note.pack(anchor="w", pady=(14, 0))

    def render_step3(self):
        self.lbl_head_sub.config(text="Step 3 of 5: Locate Game Executable (eboot.bin)")
        self.btn_skip.pack(side="left", padx=20, pady=12)
        self.btn_back.pack(side="right", padx=(0, 10), pady=12)
        self.btn_next.config(text="Next >", state="disabled", command=self.go_next)

        lbl_title = tk.Label(
            self.body_container,
            text="Select Your Decrypted eboot.bin",
            font=(FONT_SUBTITLE, 11, "bold"),
            fg=COLOR_TEXT_WHITE,
            bg="#0c0e14"
        )
        lbl_title.pack(anchor="w", pady=(8, 4))

        lbl_desc = tk.Label(
            self.body_container,
            text="Both decrypted PlayStation 4 SELF and standard x86-64 ELF executables (>10MB) are supported.",
            font=(FONT_FAMILY, 9),
            fg=COLOR_TEXT_MUTED,
            bg="#0c0e14"
        )
        lbl_desc.pack(anchor="w", pady=(0, 14))

        frame_input = tk.Frame(self.body_container, bg="#0c0e14")
        frame_input.pack(fill="x", pady=6)

        self.eboot_entry_var = tk.StringVar(value=self.selected_eboot)
        self.entry_eboot = tk.Entry(
            frame_input,
            textvariable=self.eboot_entry_var,
            font=(FONT_FAMILY, 9),
            bg="#161b24",
            fg=COLOR_TEXT_WHITE,
            insertbackground="#ffffff",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#2b3448"
        )
        self.entry_eboot.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        btn_browse = tk.Button(
            frame_input,
            text="Browse...",
            font=(FONT_FAMILY, 9, "bold"),
            bg="#212838",
            fg=COLOR_GOLD_BRIGHT,
            activebackground="#2e384e",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=4,
            command=self.browse_eboot
        )
        btn_browse.pack(side="right")

        self.lbl_val_status = tk.Label(
            self.body_container,
            text="Please select an eboot.bin file to validate.",
            font=(FONT_FAMILY, 8),
            fg=COLOR_TEXT_SUB,
            bg="#0c0e14"
        )
        self.lbl_val_status.pack(anchor="w", pady=10)

        # Check existing candidates
        for cand in [
            os.path.join("extracted_game", "app0", "eboot.bin"),
            os.path.join("app0", "eboot.bin")
        ]:
            if os.path.isfile(cand):
                self.eboot_entry_var.set(os.path.abspath(cand))
                self.validate_selected_path(os.path.abspath(cand))
                break

        self.eboot_entry_var.trace_add("write", lambda *args: self.validate_selected_path(self.eboot_entry_var.get()))

    def browse_eboot(self):
        f = filedialog.askopenfilename(
            title="Select PS4 Game Executable (eboot.bin)",
            filetypes=[("PS4 Executables (*.bin;*.elf)", "*.bin;*.elf;eboot*"), ("All Files (*.*)", "*.*")]
        )
        if f:
            self.eboot_entry_var.set(f)
            self.validate_selected_path(f)

    def validate_selected_path(self, path):
        path = path.strip().strip('"')
        if not path:
            self.lbl_val_status.config(text="Please select an eboot.bin file.", fg=COLOR_TEXT_SUB)
            self.btn_next.config(state="disabled")
            return

        valid, msg = validate_eboot_file(path)
        if valid:
            size_mb = os.path.getsize(path) / (1024 * 1024)
            self.lbl_val_status.config(
                text=f"[OK] Valid: {msg} ({size_mb:.1f} MB)",
                fg=COLOR_SUCCESS
            )
            self.selected_eboot = path
            self.btn_next.config(state="normal")
        else:
            self.lbl_val_status.config(
                text=f"[ERROR] {msg}",
                fg=COLOR_ERROR
            )
            self.btn_next.config(state="disabled")

    def render_step4(self):
        self.lbl_head_sub.config(text="Step 4 of 5: Generating Native PC Binary Image")
        self.btn_skip.pack_forget()
        self.btn_back.pack_forget()
        self.btn_next.config(text="Building...", state="disabled")

        lbl_title = tk.Label(
            self.body_container,
            text="Automated Linking & Patching in Progress",
            font=(FONT_SUBTITLE, 11, "bold"),
            fg=COLOR_TEXT_WHITE,
            bg="#0c0e14"
        )
        lbl_title.pack(anchor="w", pady=(8, 4))

        lbl_desc = tk.Label(
            self.body_container,
            text="Linking eboot.bin with Orbis PRX modules and generating out/boot-linked.bin...",
            font=(FONT_FAMILY, 9),
            fg=COLOR_TEXT_MUTED,
            bg="#0c0e14"
        )
        lbl_desc.pack(anchor="w", pady=(0, 16))

        self.prog_bar = ttk.Progressbar(self.body_container, mode="indeterminate", length=580)
        self.prog_bar.pack(fill="x", pady=(0, 12))
        self.prog_bar.start(10)

        self.lbl_build_status = tk.Label(
            self.body_container,
            text="Preparing environment...",
            font=(FONT_FAMILY, 9, "bold"),
            fg=COLOR_GOLD,
            bg="#0c0e14",
            anchor="w"
        )
        self.lbl_build_status.pack(fill="x", pady=4)

        self.txt_log = tk.Text(
            self.body_container,
            height=8,
            bg="#080a0e",
            fg="#95a5a6",
            font=("Consolas", 8),
            relief="flat",
            highlightthickness=1,
            highlightbackground="#222a3a"
        )
        self.txt_log.pack(fill="both", expand=True, pady=(6, 0))

        threading.Thread(target=self.run_auto_build, daemon=True).start()

    def run_auto_build(self):
        try:
            free_mb = shutil.disk_usage(os.getcwd()).free // (1024 * 1024)
            if free_mb < 500:
                self.after(0, lambda: self.on_build_error(f"Insufficient disk space ({free_mb} MB free). At least 500 MB is required!"))
                return

            dest_dir = os.path.join("extracted_game", "app0")
            os.makedirs(dest_dir, exist_ok=True)
            dest_eboot = os.path.join(dest_dir, "eboot.bin")
            source_dir = os.path.dirname(os.path.abspath(self.selected_eboot))

            # Step 1.a: Validasi file eboot.bin
            self.append_log("Validating eboot.bin...")
            if not os.path.isfile(self.selected_eboot):
                raise FileNotFoundError(f"File eboot.bin not found: '{self.selected_eboot}'")

            if os.path.abspath(self.selected_eboot) != os.path.abspath(dest_eboot):
                self.append_log(f"Copying {self.selected_eboot} -> {dest_eboot}...")
                shutil.copy2(self.selected_eboot, dest_eboot)

            # Step 1.b: COPY/EKSTRAK semua modul .sprx dari folder game PS4 user
            # ke folder user/sys_modules/ atau extracted_game/app0/sce_module/
            self.append_log("Scanning and extracting PS4 system modules (.sprx / .prx)...")
            dest_sce_mod = os.path.join(dest_dir, "sce_module")
            os.makedirs(dest_sce_mod, exist_ok=True)
            user_sys_mod = os.path.join(os.getcwd(), "user", "sys_modules")
            os.makedirs(user_sys_mod, exist_ok=True)

            required_sprx = (
                "libSceNgs2.sprx",
                "libSceAjm.sprx",
                "libSceFiber.sprx",
                "libSceUlt.sprx",
                "ulobjmgr.sprx"
            )

            cand_dirs = [
                os.path.join(source_dir, "sce_module"),
                source_dir,
                os.path.join(os.path.dirname(source_dir), "sce_module"),
                os.path.join(os.path.dirname(source_dir), "sys_modules"),
                os.path.join(os.path.dirname(source_dir), "user", "sys_modules"),
                user_sys_mod,
                dest_sce_mod,
                os.getcwd(),
                os.path.join(os.getcwd(), "user")
            ]

            # 1. Search for any .zip archives containing modules (e.g. 11.00_sys_modules.zip)
            found_zips = set()
            for cdir in cand_dirs:
                if os.path.isdir(cdir):
                    for zfile in glob.glob(os.path.join(cdir, "*.zip")):
                        found_zips.add(os.path.abspath(zfile))

            for zp in found_zips:
                try:
                    with zipfile.ZipFile(zp, "r") as zf:
                        names = zf.namelist()
                        for name in names:
                            fname = os.path.basename(name)
                            if fname.endswith((".sprx", ".prx")):
                                for out_target in (dest_sce_mod, user_sys_mod):
                                    tgt = os.path.join(out_target, fname)
                                    if not os.path.isfile(tgt) or os.path.getsize(tgt) == 0:
                                        with zf.open(name) as s, open(tgt, "wb") as d:
                                            shutil.copyfileobj(s, d)
                except Exception:
                    pass

            # 2. Copy file modules from candidate source directories
            for cdir in cand_dirs:
                if os.path.isdir(cdir) and cdir not in (dest_sce_mod, user_sys_mod):
                    try:
                        for item in os.listdir(cdir):
                            if item.endswith((".sprx", ".prx")):
                                s_file = os.path.join(cdir, item)
                                if os.path.isfile(s_file):
                                    for out_target in (dest_sce_mod, user_sys_mod):
                                        d_file = os.path.join(out_target, item)
                                        if not os.path.exists(d_file):
                                            try:
                                                shutil.copy2(s_file, d_file)
                                            except Exception:
                                                pass
                    except Exception:
                        pass

            # 3. Bi-directional sync between dest_sce_mod and user_sys_mod
            for s_mod in os.listdir(dest_sce_mod):
                if s_mod.endswith((".sprx", ".prx")):
                    u_file = os.path.join(user_sys_mod, s_mod)
                    if not os.path.exists(u_file):
                        try:
                            shutil.copy2(os.path.join(dest_sce_mod, s_mod), u_file)
                        except Exception:
                            pass
            for u_mod in os.listdir(user_sys_mod):
                if u_mod.endswith((".sprx", ".prx")):
                    d_file = os.path.join(dest_sce_mod, u_mod)
                    if not os.path.exists(d_file):
                        try:
                            shutil.copy2(os.path.join(user_sys_mod, u_mod), d_file)
                        except Exception:
                            pass

            # Step 1.3: Jika file .sprx tidak ditemukan di folder user, tampilkan error yang jelas
            missing_sprx = [
                m for m in required_sprx
                if not (os.path.isfile(os.path.join(dest_sce_mod, m)) or os.path.isfile(os.path.join(user_sys_mod, m)))
            ]
            if missing_sprx:
                raise RuntimeError(
                    "Modul PS4 tidak lengkap, pastikan Anda meng-copy seluruh folder game, bukan hanya eboot.bin.\n\n"
                    f"Missing audio/system modules: {', '.join(missing_sprx)}"
                )

            # Step 1.c: BARU KEMUDIAN jalankan link_modules.py dan link_libc.py
            out_dir = os.path.join(os.getcwd(), "out")
            os.makedirs(out_dir, exist_ok=True)

            self.append_log("Starting auto_builder auto_prepare pipeline...")
            if not HAS_AUTO_BUILDER or auto_builder is None:
                raise RuntimeError("auto_builder module could not be imported!")

            def status_cb(msg):
                self.after(0, lambda m=msg: self.append_log(m))

            auto_builder.auto_prepare(dest_dir, out_dir, source_hint_dir=source_dir, status_callback=status_cb)

            boot_linked = os.path.join(out_dir, "boot-linked.bin")
            if not os.path.isfile(boot_linked) or os.path.getsize(boot_linked) == 0:
                raise RuntimeError("out/boot-linked.bin was not created or is empty!")

            # Verify game integrity
            is_valid, msg = check_game_integrity(boot_linked)
            if not is_valid:
                raise RuntimeError(f"Build verification failed: {msg}")

            self.after(0, self.on_build_success)

        except Exception as e:
            self.after(0, lambda err=str(e): self.on_build_error(err))

    def append_log(self, text):
        try:
            self.lbl_build_status.config(text=text)
            self.txt_log.insert("end", text + "\n")
            self.txt_log.see("end")
        except Exception:
            pass

    def on_build_success(self):
        self.prog_bar.stop()
        self.show_step(5)

    def on_build_error(self, err_msg):
        self.prog_bar.stop()
        self.lbl_build_status.config(text="Build Failed!", fg=COLOR_ERROR)
        self.append_log(f"\n[ERROR] {err_msg}")
        self.btn_back.config(state="normal", text="< Back to Retry", command=lambda: self.show_step(3))
        self.btn_back.pack(side="right", padx=20, pady=12)

    def render_step5(self):
        self.lbl_head_sub.config(text="Step 5 of 5: Setup Complete!")
        self.btn_skip.pack_forget()
        self.btn_back.pack_forget()

        write_ini({
            "first_run_done": "1",
            "legal_acknowledged": "1"
        })

        lbl_title = tk.Label(
            self.body_container,
            text="🎉 Setup Completed Successfully!",
            font=(FONT_SUBTITLE, 13, "bold"),
            fg=COLOR_SUCCESS,
            bg="#0c0e14"
        )
        lbl_title.pack(anchor="w", pady=(10, 8))

        desc = (
            "The native PC runtime image and support profiles have been built and verified:\n\n"
            "  ✔ out/boot-linked.bin      (Native entry point & PRX modules linked)\n"
            "  ✔ out/content.bin          (AppContent offline profile active)\n"
            "  ✔ out/import_names.txt     (Symbol map table ready)\n"
            "  ✔ High-FPS patch engine    (Capcom MT Framework limiter unlocked)\n\n"
            "You are ready to launch Sengoku Basara 4 Sumeragi PC with ultra-low latency,\n"
            "modern gamepad support, and high-framerate Vulkan 1.3 presentation!"
        )
        lbl_desc = tk.Label(
            self.body_container,
            text=desc,
            font=(FONT_FAMILY, 9),
            fg=COLOR_TEXT_WHITE,
            bg="#0c0e14",
            justify="left"
        )
        lbl_desc.pack(anchor="w", pady=(0, 16))

        self.btn_next.config(
            text="⚔️ Play Now",
            bg=COLOR_GOLD,
            fg="#0c0e14",
            activebackground=COLOR_GOLD_BRIGHT,
            activeforeground="#000000",
            state="normal",
            command=self.finish_and_play
        )
        self.btn_next.pack(side="right", padx=20, pady=12)

        self.btn_launcher = tk.Button(
            self.nav_frame,
            text="Back to Launcher",
            font=(FONT_FAMILY, 9),
            fg=COLOR_TEXT_WHITE,
            bg="#21262d",
            activeforeground="#ffffff",
            activebackground="#30363d",
            relief="flat",
            padx=14,
            pady=4,
            command=self.finish_to_launcher
        )
        self.btn_launcher.pack(side="right", padx=(0, 10), pady=12)

    def go_next(self):
        if self.current_step < 5:
            self.show_step(self.current_step + 1)

    def go_back(self):
        if self.current_step > 1:
            self.show_step(self.current_step - 1)

    def skip_wizard(self):
        write_ini({"first_run_done": "1"})
        self.destroy()

    def finish_and_play(self):
        self.destroy()
        if self.on_play:
            self.on_play()

    def finish_to_launcher(self):
        self.destroy()
        if self.on_complete:
            self.on_complete()


# ==============================================================================
# CRASH REPORTING & SYSTEM DIAGNOSTICS SUITE (CustomTkinter)
# ==============================================================================

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
    for path in [base_path("VERSION.txt"), base_path("version.txt")]:
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
        base_path("crashes"),
        base_path("user", "crashes"),
        base_path("user", "crash"),
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


def parse_minidump(dmp_path: str):
    """
    Parses a Windows minidump (.dmp) file using the 'minidump' library.
    Extracts Exception Address (RIP), Exception Code, and Module Name (+ offset).
    Safe against malformed dumps and never crashes.
    Returns: dict with diagnostic fields or warning summary.
    """
    if not dmp_path or not os.path.isfile(dmp_path):
        return None

    try:
        import logging
        # Suppress minidump internal root logger warnings (e.g. PEB parsing in partial dumps)
        logging.getLogger("minidump").setLevel(logging.CRITICAL)
        logging.getLogger().setLevel(logging.CRITICAL)

        from minidump.minidumpfile import MinidumpFile
        mf = MinidumpFile.parse(dmp_path)

        rip = None
        exc_code_val = None

        if mf.exception and hasattr(mf.exception, "exception_records") and mf.exception.exception_records:
            rec = mf.exception.exception_records[0]
            if hasattr(rec, "ExceptionRecord"):
                rip = getattr(rec.ExceptionRecord, "ExceptionAddress", None)
                code_obj = getattr(rec.ExceptionRecord, "ExceptionCode", None)
                exc_code_val = getattr(code_obj, "value", code_obj)

        if rip is None:
            return {
                "rip": "N/A",
                "module": "Unknown",
                "offset": "0x0",
                "exception_code": "N/A",
                "summary": "Crash RIP: N/A | Module: Unknown"
            }

        mod_name = "Unknown"
        offset = 0
        if mf.modules and hasattr(mf.modules, "modules"):
            for m in mf.modules.modules:
                if m.baseaddress <= rip < m.baseaddress + m.size:
                    mod_name = os.path.basename(m.name)
                    offset = rip - m.baseaddress
                    break

        rip_str = f"0x{rip:016X}"
        offset_str = f"0x{offset:X}"
        exc_str = f"0x{exc_code_val:08X}" if isinstance(exc_code_val, int) else str(exc_code_val)

        return {
            "rip": rip_str,
            "module": mod_name,
            "offset": offset_str,
            "exception_code": exc_str,
            "summary": f"Crash RIP: {rip_str} | Module: {mod_name} (+{offset_str})"
        }
    except Exception as e:
        print(f"[LAUNCHER] Warning: Gagal membaca minidump ({dmp_path}): {e}")
        return {
            "rip": "Gagal membaca minidump",
            "module": "Unknown",
            "offset": "0x0",
            "exception_code": "N/A",
            "summary": "Crash RIP: (Gagal membaca minidump) | Module: Unknown"
        }


def get_guest_faults_breadcrumb():
    """Reads user/crashes/guest_faults.log if present."""
    candidates = [
        base_path("user", "crashes", "guest_faults.log"),
        base_path("crashes", "guest_faults.log"),
        base_path("guest_faults.log"),
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
        base_path("user", "logs", "last_run.log"),
        base_path("last_run.log"),
        base_path("user", "logs", "basara.log"),
        base_path("basara.log"),
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


def create_crash_bundle(report_path: str, log_copy_path: str = None, dmp_path: str = None) -> str:
    """
    Enterprise Crash Bundle (Auto-Zip):
    Collects into crashes/crash_bundle_YYYYMMDD_HHMMSS.zip:
      - crash_report.txt (generated structured report)
      - last_run.log (emulator stdout/stderr log)
      - basara.log (C++ engine log)
      - guest_faults.log (guest CPU/GPU faults breadcrumb, if present)
      - *.dmp (Windows minidump, if present)
    Returns: absolute path to the generated ZIP file, or None on error.
    """
    try:
        crashes_dir = base_path("crashes")
        os.makedirs(crashes_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bundle_path = os.path.join(crashes_dir, f"crash_bundle_{ts}.zip")

        collected_files = []

        # 1. crash_report.txt
        if report_path and os.path.isfile(report_path):
            collected_files.append((report_path, "crash_report.txt"))

        # 2. last_run.log
        last_run_candidates = [
            log_copy_path,
            base_path("user", "logs", "last_run.log"),
            base_path("crashes", "last_run.log"),
            base_path("last_run.log")
        ]
        for p in last_run_candidates:
            if p and os.path.isfile(p):
                collected_files.append((p, "last_run.log"))
                break

        # 3. basara.log
        basara_candidates = [
            base_path("user", "logs", "basara.log"),
            base_path("crashes", "basara.log"),
            base_path("basara.log")
        ]
        for p in basara_candidates:
            if p and os.path.isfile(p):
                collected_files.append((p, "basara.log"))
                break

        # 4. guest_faults.log
        faults_candidates = [
            base_path("user", "crashes", "guest_faults.log"),
            base_path("crashes", "guest_faults.log"),
            base_path("guest_faults.log")
        ]
        for p in faults_candidates:
            if p and os.path.isfile(p):
                collected_files.append((p, "guest_faults.log"))
                break

        # 5. *.dmp
        dmp_target = dmp_path
        if not (dmp_target and os.path.isfile(dmp_target)):
            dmp_found, _, detected_dmp = check_dump_file()
            if dmp_found and detected_dmp and os.path.isfile(detected_dmp):
                dmp_target = detected_dmp

        if dmp_target and os.path.isfile(dmp_target):
            collected_files.append((dmp_target, os.path.basename(dmp_target)))

        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path, arcname in collected_files:
                try:
                    zf.write(file_path, arcname=arcname)
                except Exception as fe:
                    print(f"[CRASH_BUNDLE] Warning: failed adding {arcname}: {fe}")

        print(f"[CRASH_BUNDLE] Created crash package: {bundle_path} ({len(collected_files)} files)")
        return bundle_path
    except Exception as e:
        print(f"[CRASH_BUNDLE] Error creating crash bundle: {e}")
        return None


def generate_crash_report(exit_code: int, log_path: str, trigger_reason: str, matched_keywords: list):
    """
    Generates a structured crash report file, parses minidump (if available),
    and creates a unified crash bundle ZIP.
    Returns: (report_path, log_copy_path, report_content, bundle_path)
    """
    crashes_dir = base_path("crashes")
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

    # Parse Minidump if available
    dmp_parsed = None
    if dmp_found and dmp_file_path:
        dmp_parsed = parse_minidump(dmp_file_path)

    last_50 = "".join(lines[-50:]).strip() if lines else "(log is empty or missing)"
    context_scan = extract_context_sections(lines, context_lines=5)

    # Build report text
    report = []
    report.append("================================================================================")
    report.append("             SENGOKU BASARA 4 SUMERAGI PC — CRASH REPORT")
    report.append("================================================================================")
    if dmp_parsed and dmp_parsed.get("summary"):
        report.append(f"{dmp_parsed['summary']}")
    elif dmp_found:
        report.append("Crash RIP: (Gagal membaca minidump) | Module: Unknown")
    else:
        report.append("Crash RIP: N/A (No minidump generated)")

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
    if dmp_parsed and dmp_parsed.get("rip") not in (None, "N/A", "Gagal membaca minidump"):
        report.append(f"Minidump Fault   : RIP {dmp_parsed['rip']} -> {dmp_parsed['module']} (+{dmp_parsed['offset']})")
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

    # Auto-generate Crash Bundle ZIP
    bundle_path = create_crash_bundle(report_path, log_copy_path, dmp_file_path)

    return report_path, log_copy_path, content, bundle_path


def check_wer_status():
    """
    Checks Windows Error Reporting (WER) LocalDumps configuration.
    Ensures crashes generate a .dmp minidump / fulldump for debugging.
    Returns: (is_enabled: bool, dump_folder: str or None)
    """
    if sys.platform != "win32":
        return False, None

    targets = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\basara_pc.exe"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\Windows Error Reporting\LocalDumps\basara_pc.exe"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\Windows Error Reporting\LocalDumps"),
    ]

    for hive, subkey in targets:
        try:
            with winreg.OpenKey(hive, subkey) as k:
                try:
                    dump_folder, _ = winreg.QueryValueEx(k, "DumpFolder")
                    return True, dump_folder
                except Exception:
                    return True, os.path.expandvars(r"%LOCALAPPDATA%\CrashDumps")
        except FileNotFoundError:
            continue
        except Exception:
            continue

    return False, None


class CrashDialog:
    """
    Studio-Grade Crash & Diagnostic Dialog built for Sengoku Basara 4 Sumeragi Native Port.
    Crafted with CustomTkinter modern dark aesthetic, real-time hardware telemetry ribbon,
    line-by-line syntax highlighting, and fluid feedback micro-interactions.
    Supports both standalone execution and integration with BasaraLauncher (parent window).
    """

    def __init__(self, report_path: str, crashes_dir: str, content: str, exit_code: int, reason: str, parent=None, bundle_path: str = None):
        self.parent = parent
        self.report_path = os.path.normpath(report_path) if report_path else ""
        self.crashes_dir = base_path(crashes_dir) if crashes_dir else base_path("crashes")
        self.content = content
        self.exit_code = exit_code
        self.reason = reason

        # Diagnostics snapshot
        self.mem_info = get_memory_info()
        self.dmp_found, self.dmp_status, self.dmp_path = check_dump_file()

        # Parse Minidump if available
        self.minidump_info = parse_minidump(self.dmp_path) if (self.dmp_found and self.dmp_path) else None

        # Resolve Crash Bundle ZIP path
        if bundle_path and os.path.isfile(bundle_path):
            self.bundle_path = os.path.normpath(bundle_path)
        else:
            zips = glob.glob(os.path.join(self.crashes_dir, "crash_bundle_*.zip"))
            if zips:
                zips.sort(key=os.path.getmtime, reverse=True)
                self.bundle_path = os.path.normpath(zips[0])
            else:
                self.bundle_path = None

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
        if self.parent is not None:
            self.root = ctk.CTkToplevel(self.parent)
        else:
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

        if self.parent is not None:
            self.root.lift()
            self.root.focus_force()

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

        if self.minidump_info and self.minidump_info.get("rip") not in (None, "N/A", "Gagal membaca minidump"):
            t_sep4 = ctk.CTkLabel(telemetry_strip, text="•", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=self.C_TEXT_DIM)
            t_sep4.pack(side="left", padx=2)
            t_rip = ctk.CTkLabel(
                telemetry_strip, text=f"🎯 RIP: {self.minidump_info['module']} (+{self.minidump_info['offset']})",
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color="#38BDF8"
            )
            t_rip.pack(side="left", padx=2)

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

        # Tombol Buka Folder ZIP (📦 Buka Folder ZIP)
        if self.bundle_path and os.path.isfile(self.bundle_path):
            btn_zip = ctk.CTkButton(
                action_bar, text="📦 Buka Folder ZIP", fg_color="#1E293B",
                hover_color="#334155", border_width=1, border_color="#38BDF8",
                text_color="#38BDF8", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                corner_radius=8, height=38, command=self.open_zip_folder
            )
            btn_zip.pack(side="left", padx=(0, 12), anchor="n")

        # GitHub Column: Tombol GitHub + Label Peringatan Lampirkan ZIP / .dmp
        github_col = ctk.CTkFrame(action_bar, fg_color="transparent")
        github_col.pack(side="left", anchor="n")

        btn_github = ctk.CTkButton(
            github_col, text="🌐 Laporkan ke GitHub", fg_color=self.C_BLUE,
            hover_color=self.C_BLUE_HOVER, text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=8, height=38, command=self.open_github_issue
        )
        btn_github.pack(anchor="w")

        zip_name = os.path.basename(self.bundle_path) if (self.bundle_path and os.path.isfile(self.bundle_path)) else None
        if zip_name:
            warn_text = f"Silakan lampirkan file ZIP berikut ke GitHub Issue: {zip_name}"
        else:
            warn_text = "Jangan lupa lampirkan file .dmp (jika ada) saat membuat Issue di GitHub!"

        lbl_dmp_warn = ctk.CTkLabel(
            github_col,
            text=warn_text,
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

    def open_zip_folder(self):
        """Membuka Windows Explorer dan langsung menyorot (highlight) file ZIP crash bundle."""
        if self.bundle_path and os.path.isfile(self.bundle_path):
            target = os.path.normpath(self.bundle_path)
            try:
                if sys.platform == "win32":
                    subprocess.Popen(f'explorer.exe /select,"{target}"')
                else:
                    subprocess.Popen(["xdg-open", os.path.dirname(target)])
                self.copy_feedback_lbl.configure(text=f"✓ Menyorot {os.path.basename(target)}")
                self.root.after(3000, lambda: self.copy_feedback_lbl.configure(text=""))
            except Exception as e:
                messagebox.showerror("Error", f"Gagal membuka folder ZIP:\n{e}")
        else:
            self.open_folder()

    def open_github_issue(self):
        """Membuka browser ke GitHub New Issue dengan template laporan otomatis."""
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            title = f"[CRASH] {ts} - {self.reason}"
            snippet = "\n".join(self.content.splitlines()[:60])

            zip_name = os.path.basename(self.bundle_path) if (self.bundle_path and os.path.isfile(self.bundle_path)) else None
            if zip_name:
                zip_section = f"\n\n**📦 Crash Bundle**: Silakan lampirkan file ZIP berikut ke GitHub Issue: `{zip_name}`\n"
            else:
                zip_section = f"\n\n*Catatan: Mohon lampirkan file .dmp atau log (jika ada) saat membuat Issue ini!*\n"

            minidump_line = ""
            if self.minidump_info and self.minidump_info.get("summary"):
                minidump_line = f"**Crash RIP**: `{self.minidump_info['summary']}`\n"

            body = (
                f"### Deskripsi Crash\n"
                f"Game crash otomatis terdeteksi oleh Sengoku Basara 4 PC Launcher.\n\n"
                f"**Trigger Reason**: `{self.reason}`\n"
                f"**Game Version**: `{get_game_version()}`\n"
                f"{minidump_line}"
                f"**GPU**: `{get_gpu_info()}`\n"
                f"**Memory**: `{self.mem_info['summary']}`\n"
                f"**Dump File**: `{self.dmp_status}`\n"
                f"**OS**: `{platform.system()} {platform.release()} ({platform.version()})`\n"
                f"{zip_section}\n"
                f"### Cuplikan Log Terakhir:\n"
                f"```text\n{snippet}\n```\n\n"
                f"*Laporan lengkap tersimpan di: `{os.path.basename(self.report_path)}`*"
            )

            title_enc = urllib.parse.quote(title)
            body_enc = urllib.parse.quote(body)
            url = f"https://github.com/{GITHUB_REPO}/issues/new?title={title_enc}&body={body_enc}"

            webbrowser.open(url)
            if zip_name:
                self.copy_feedback_lbl.configure(text=f"📦 Silakan lampirkan file ZIP berikut ke GitHub Issue: {zip_name}")
            else:
                self.copy_feedback_lbl.configure(text="✓ Membuka browser GitHub...")
            self.root.after(5000, lambda: self.copy_feedback_lbl.configure(text=""))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membuka browser GitHub:\n{e}")

    def show(self):
        """Menampilkan dialog dan menangani interupsi bersih."""
        try:
            if self.parent is not None:
                self.root.grab_set()
                self.root.focus_force()
                self.root.wait_window()
            else:
                self.root.mainloop()
        except KeyboardInterrupt:
            try:
                self.root.destroy()
            except Exception:
                pass

    def _build_fallback_ui(self):
        """Cadangan Tkinter jika CustomTkinter tidak tersedia."""
        if self.parent is not None:
            self.root = tk.Toplevel(self.parent)
        else:
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

        if self.bundle_path and os.path.isfile(self.bundle_path):
            tk.Button(bar, text="📦 Buka Folder ZIP", bg="#1E293B", fg="#38BDF8", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=14, pady=6, cursor="hand2", command=self.open_zip_folder).pack(side=tk.LEFT, padx=(0, 8), anchor="n")

        gh_col = tk.Frame(bar, bg=self.C_BG)
        gh_col.pack(side=tk.LEFT, padx=(0, 8), anchor="n")
        tk.Button(gh_col, text="🌐 Kirim ke GitHub", bg=self.C_BLUE, fg="#FFFFFF", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=14, pady=6, cursor="hand2", command=self.open_github_issue).pack(anchor="w")
        zip_hint = os.path.basename(self.bundle_path) if (self.bundle_path and os.path.isfile(self.bundle_path)) else None
        hint_str = f"Silakan lampirkan file ZIP berikut ke GitHub Issue: {zip_hint}" if zip_hint else "Jangan lupa lampirkan file .dmp (jika ada) saat membuat Issue di GitHub!"
        tk.Label(gh_col, text=hint_str, bg=self.C_BG, fg="#F59E0B", font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))

        self.copy_feedback_lbl = tk.Label(bar, text="", bg=self.C_BG, fg=self.C_EMERALD, font=("Segoe UI", 9, "bold"))
        self.copy_feedback_lbl.pack(side=tk.LEFT, padx=6, anchor="n", pady=4)

        tk.Button(bar, text="✕ Tutup Aplikasi", bg=self.C_CRIMSON_BG, fg=self.C_CRIMSON, font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=14, pady=6, cursor="hand2", command=self.root.destroy).pack(side=tk.RIGHT, anchor="n")


class BasaraLauncher(tk.Tk):
    def __init__(self, dep_status=None):
        super().__init__()
        self.title("Sengoku Basara 4 Sumeragi — PC Native Port (v2.1.0)")
        self.geometry(f"{WIDTH}x{HEIGHT}")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG_DARK)

        self.dep_status = dep_status if dep_status is not None else check_dependencies(show_dialogs=False)

        self.apply_native_dark_title_bar()
        self.apply_window_icon()
        self.center_on_screen()

        self.state = "INITIALIZING"
        self._init_tooltips()
        self.load_configuration()
        self.generate_textures()
        self.build_canvas()
        self.evaluate_system_readiness()
        self.after(120, self.check_first_run_wizard)

    def apply_native_dark_title_bar(self):
        if sys.platform != "win32":
            return
        try:
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if not hwnd:
                hwnd = self.winfo_id()
            value = ctypes.c_int(2)  # 2 = DWMWA_USE_IMMERSIVE_DARK_MODE
            for attr in (20, 19):
                res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attr,
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
                if res == 0:
                    break
        except Exception:
            pass

    def apply_window_icon(self):
        # Try game's extracted PNG icon first
        icon_png = base_path("extracted_game", "app0", "sce_sys", "icon0.png")
        if os.path.isfile(icon_png):
            try:
                img = Image.open(icon_png).convert("RGBA")
                self.iconphoto(True, ImageTk.PhotoImage(img))
                return
            except Exception:
                pass
        # Fallback to .ico file
        icon_ico = base_path("packaging", "windows", "icons", "basara4.ico")
        if os.path.isfile(icon_ico):
            try:
                self.iconbitmap(icon_ico)
            except Exception:
                pass

    def center_on_screen(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{WIDTH}x{HEIGHT}+{(sw - WIDTH)//2}+{(sh - HEIGHT)//2}")

    def load_configuration(self):
        ini = read_ini()
        self.res_val = ini.get("output_res", "1920x1080")
        self.fps_val = ini.get("fps_limit", "144")
        self.aniso_val = ini.get("anisotropy", "16")
        self.fsr_val = (ini.get("fsr1", "1") == "1")
        self.fullscreen_val = (ini.get("fullscreen", "1") == "1")
        self.skip_intro_val = (ini.get("skip_intro", "0") == "1")
        self.show_fps_val = (ini.get("show_fps", "1") == "1")
        self.perf_mode_val = (ini.get("performance_mode", "0") == "1")
        self.safe_mode_val = (ini.get("safe_mode", "0") == "1")
        self.async_pipelines_val = ini.get("async_pipelines", "1")
        self.scale_val = ini.get("render_scale", "1.0")
        if self.scale_val not in ("1.0", "1.5", "2.0"):
            try:
                flt = float(self.scale_val)
                if abs(flt - 1.0) < 0.05:
                    self.scale_val = "1.0"
                elif abs(flt - 1.5) < 0.05:
                    self.scale_val = "1.5"
                elif abs(flt - 2.0) < 0.05:
                    self.scale_val = "2.0"
                else:
                    self.scale_val = "1.0"
            except Exception:
                self.scale_val = "1.0"
        # Enforce mutual exclusivity on configuration load: Render Scale > 1.0 disables FSR
        if self.scale_val in ("1.5", "2.0") and self.fsr_val:
            self.fsr_val = False
        try:
            self.sharp_val = int(ini.get("rcas_strength", "75"))
            self.sharp_val = max(0, min(100, self.sharp_val))
        except Exception:
            self.sharp_val = 75
        self.prio_val = ini.get("process_priority", "above_normal")
        if self.prio_val not in ("normal", "above_normal", "high"):
            self.prio_val = "above_normal"
        self.telem_val = ini.get("telemetry_upload", "ask").lower()
        if self.telem_val not in ("ask", "never", "always"):
            self.telem_val = "ask"
        self.first_run_done = ini.get("first_run_done", "0")
        self.legal_acknowledged = ini.get("legal_acknowledged", "0")

    def sync_ini(self):
        height = self.res_val.split("x")[-1] if "x" in self.res_val else "1080"
        cfg_payload = {
            "output_res": self.res_val,
            "render_res": height,
            "render_scale": self.scale_val,
            "fullscreen": "1" if self.fullscreen_val else "0",
            "fps_limit": self.fps_val,
            "anisotropy": self.aniso_val,
            "fsr1": "1" if self.fsr_val else "0",
            "rcas": "1" if self.fsr_val else "0",
            "rcas_strength": str(self.sharp_val),
            "skip_intro": "1" if self.skip_intro_val else "0",
            "show_fps": "1" if self.show_fps_val else "0",
            "performance_mode": "1" if self.perf_mode_val else "0",
            "safe_mode": "1" if self.safe_mode_val else "0",
            "async_pipelines": self.async_pipelines_val,
            "process_priority": self.prio_val,
            "telemetry_upload": self.telem_val,
            "first_run_done": self.first_run_done,
            "legal_acknowledged": self.legal_acknowledged,
            "patch_60fps": "1",
        }
        write_ini(cfg_payload)

    apply_settings = sync_ini

    def _create_pill_set(self, w, h):
        # Deep Crimson Red for active, Slate Grey for inactive, Slate Hover
        act = self._create_pill_texture(w, h, (139, 0, 0, 255), (218, 165, 32, 255), radius=6, width=1)
        inact = self._create_pill_texture(w, h, (36, 44, 53, 225), (60, 74, 88, 255), radius=6, width=1)
        hov = self._create_pill_texture(w, h, (50, 62, 75, 240), (90, 110, 130, 255), radius=6, width=1)
        return act, inact, hov

    def generate_textures(self):
        # 1. Background image composition
        candidates = [
            os.path.join("extracted_game", "app0", "sce_sys", "pic1.png"),
            os.path.join("extracted_game", "app0", "sce_sys", "pic0.png"),
            os.path.join("app0", "sce_sys", "pic1.png"),
            os.path.join("app0", "sce_sys", "pic0.png"),
        ]
        found_art = None
        for p in candidates:
            if os.path.isfile(p):
                found_art = p
                break

        if found_art:
            base = Image.open(found_art).convert("RGBA")
            target_ratio = WIDTH / HEIGHT
            new_w = int(base.height * target_ratio)
            left = int((base.width - new_w) * 0.62)
            base = base.crop((left, 0, left + new_w, base.height)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        else:
            base = Image.new("RGBA", (WIDTH, HEIGHT), (16, 18, 26, 255))
            d = ImageDraw.Draw(base)
            for y in range(HEIGHT):
                r = int(28 + (10 - 28) * (y / HEIGHT))
                g = int(12 + (14 - 12) * (y / HEIGHT))
                b = int(16 + (24 - 16) * (y / HEIGHT))
                d.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))

        # Frosted glass blur on the left panel
        blurred = base.filter(ImageFilter.GaussianBlur(radius=8))
        grad_blur = Image.new("L", (WIDTH, 1))
        d_b = ImageDraw.Draw(grad_blur)
        for x in range(WIDTH):
            if x <= 470:
                val = 255
            elif x <= 580:
                val = int(255 * (1.0 - (x - 470) / 110.0))
            else:
                val = 0
            d_b.point((x, 0), fill=val)
        mask_blur = grad_blur.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
        comp = Image.composite(blurred, base, mask_blur)

        # Smooth dark gradient vignette mask with cosine curve for seamless character art blending
        grad_x = Image.new("L", (WIDTH, 1))
        d_x = ImageDraw.Draw(grad_x)
        for x in range(WIDTH):
            if x <= 460:
                val = 246
            elif x <= 640:
                ratio = (x - 460) / 180.0
                cos_factor = 0.5 * (1.0 + math.cos(ratio * math.pi))
                val = int(246 * cos_factor)
            else:
                val = 0
            d_x.point((x, 0), fill=val)
        mask_x = grad_x.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)

        grad_y = Image.new("L", (1, HEIGHT))
        d_y = ImageDraw.Draw(grad_y)
        vignette_start = int(HEIGHT * 0.76)
        vignette_range = float(HEIGHT - vignette_start)
        for y in range(HEIGHT):
            if y >= vignette_start:
                val = int(195 * ((y - vignette_start) / vignette_range))
            elif y <= 45:
                val = int(70 * (1.0 - y / 45.0))
            else:
                val = 0
            d_y.point((0, y), fill=val)
        mask_y = grad_y.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)

        final_mask = ImageChops.lighter(mask_x, mask_y)
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (10, 12, 18, 0))
        overlay.putalpha(final_mask)
        final_bg = Image.alpha_composite(comp, overlay)
        self.photo_bg = ImageTk.PhotoImage(final_bg)

        # 2. Game Icon (50x50)
        icon0_cand = [
            base_path("extracted_game", "app0", "sce_sys", "icon0.png"),
            base_path("app0", "sce_sys", "icon0.png"),
        ]
        self.photo_icon0 = None
        for p in icon0_cand:
            if os.path.isfile(p):
                try:
                    ic = Image.open(p).convert("RGBA").resize((50, 50), Image.Resampling.LANCZOS)
                    mask = Image.new("L", (50, 50), 0)
                    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 49, 49], radius=8, fill=255)
                    rounded_ic = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
                    rounded_ic.paste(ic, (0, 0), mask)
                    ImageDraw.Draw(rounded_ic).rounded_rectangle([0, 0, 49, 49], radius=8, outline=(229, 193, 88, 200), width=1)
                    self.photo_icon0 = ImageTk.PhotoImage(rounded_ic)
                    break
                except Exception:
                    pass

        # 3. Pill sets for different widths
        self.pills_res = self._create_pill_set(98, 26)     # Resolution (4 items)
        self.pills_fps = self._create_pill_set(65, 26)     # FPS (6 items)
        self.pills_aniso = self._create_pill_set(78, 26)   # Anisotropy (5 items)
        self.pills_scale = self._create_pill_set(62, 26)   # Render Scale (3 items: 1.0x, 1.5x, 2.0x)
        self.pills_prio = self._create_pill_set(44, 24)    # Priority (3 items)
        self.pills_telem = self._create_pill_set(44, 24)   # Telemetry (3 items)

        # Tool button textures
        self.btn_tool_norm = self._create_pill_texture(110, 26, (36, 44, 53, 225), (218, 165, 32, 200), radius=6, width=1)
        self.btn_tool_hov = self._create_pill_texture(110, 26, (50, 62, 75, 240), (255, 215, 0, 255), radius=6, width=1)
        self.btn_wiz_norm = self._create_pill_texture(120, 26, (36, 44, 53, 225), (218, 165, 32, 200), radius=6, width=1)
        self.btn_wiz_hov = self._create_pill_texture(120, 26, (50, 62, 75, 240), (255, 215, 0, 255), radius=6, width=1)
        self.btn_reb_norm = self._create_pill_texture(120, 26, (36, 44, 53, 225), (218, 165, 32, 200), radius=6, width=1)
        self.btn_reb_hov = self._create_pill_texture(120, 26, (50, 62, 75, 240), (255, 215, 0, 255), radius=6, width=1)
        self.btn_logs_norm = self._create_pill_texture(80, 26, (36, 44, 53, 225), (218, 165, 32, 200), radius=6, width=1)
        self.btn_logs_hov = self._create_pill_texture(80, 26, (50, 62, 75, 240), (255, 215, 0, 255), radius=6, width=1)

        # 4. Modern Toggle Switches (40 x 20)
        self.switch_on = self._create_switch_texture(True)
        self.switch_off = self._create_switch_texture(False)
        self.switch_disabled = self._create_disabled_switch_texture()

        # 5. Play Button Textures (270 x 50)
        self.btn_play_normal = self._create_gradient_btn(270, 50, (155, 18, 24), (105, 10, 14), (229, 193, 88))
        self.btn_play_hover = self._create_gradient_btn(270, 50, (185, 24, 30), (125, 12, 17), (255, 215, 0))
        self.btn_init_normal = self._create_gradient_btn(270, 50, (255, 215, 0), (195, 150, 15), (255, 240, 140), border_width=2)
        self.btn_init_hover = self._create_gradient_btn(270, 50, (255, 230, 50), (220, 170, 20), (255, 255, 255), border_width=2)
        self.btn_repair_normal = self._create_gradient_btn(270, 50, (212, 90, 24), (142, 45, 12), (246, 170, 69), border_width=2)
        self.btn_repair_hover = self._create_gradient_btn(270, 50, (235, 105, 30), (170, 60, 18), (255, 210, 100), border_width=2)
        self.btn_play_disabled = self._create_gradient_btn(270, 50, (36, 42, 52), (24, 28, 36), (55, 64, 78))

    def _create_pill_texture(self, w, h, fill, outline, radius=6, width=1):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill, outline=outline, width=width)
        return ImageTk.PhotoImage(img)

    def _create_switch_texture(self, val):
        w, h = 40, 20
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if val:
            # Active: Deep Crimson Red with Gold border and bright white knob
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(139, 0, 0, 255), outline=(255, 215, 0, 255), width=1)
            d.ellipse([w - 17, 3, w - 5, 15], fill=(255, 255, 255, 255))
        else:
            # Inactive: Slate Grey with Slate border and Slate knob
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(36, 44, 53, 230), outline=(60, 74, 88, 255), width=1)
            d.ellipse([5, 3, 17, 15], fill=(160, 174, 192, 255))
        return ImageTk.PhotoImage(img)

    def _create_disabled_switch_texture(self):
        w, h = 40, 20
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # Dimmed/disabled switch appearance
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(24, 28, 35, 180), outline=(45, 52, 62, 255), width=1)
        d.ellipse([5, 3, 17, 15], fill=(70, 80, 95, 255))
        return ImageTk.PhotoImage(img)

    def _create_gradient_btn(self, w, h, top_col, bot_col, border_col, border_width=1):
        grad_1d = Image.new("RGBA", (1, h))
        for y in range(h):
            r = int(top_col[0] + (bot_col[0] - top_col[0]) * (y / h))
            g = int(top_col[1] + (bot_col[1] - top_col[1]) * (y / h))
            b = int(top_col[2] + (bot_col[2] - top_col[2]) * (y / h))
            grad_1d.putpixel((0, y), (r, g, b, 255))
        grad = grad_1d.resize((w, h), Image.Resampling.BILINEAR)

        mask = Image.new("L", (w, h), 0)
        d_mask = ImageDraw.Draw(mask)
        d_mask.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=255)

        btn = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        btn.paste(grad, (0, 0), mask)
        d_btn = ImageDraw.Draw(btn)
        d_btn.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, outline=border_col, width=border_width)
        return ImageTk.PhotoImage(btn)

    # --- Tooltip System ---
    def _init_tooltips(self):
        self._tooltip_items = []
        self._tooltip_timer = None

    def _show_tooltip(self, text, x, y):
        self._hide_tooltip()
        font_tt = (FONT_FAMILY, 9)
        dummy = self.canvas.create_text(0, 0, text=text, font=font_tt, anchor="nw")
        bbox = self.canvas.bbox(dummy)
        self.canvas.delete(dummy)

        tw = (bbox[2] - bbox[0]) if bbox else len(text) * 7
        th = (bbox[3] - bbox[1]) if bbox else 18
        pad_x, pad_y = 10, 6

        bx = x + 14
        by = y + 18
        if bx + tw + pad_x * 2 > WIDTH - 16:
            bx = WIDTH - 16 - tw - pad_x * 2
        if by + th + pad_y * 2 > HEIGHT - 16:
            by = y - th - pad_y * 2 - 8
        if bx < 10:
            bx = 10

        bg = self.canvas.create_rectangle(
            bx, by, bx + tw + pad_x * 2, by + th + pad_y * 2,
            fill="#121620", outline=COLOR_GOLD, width=1, tags=("canvas_tooltip",)
        )
        tx = self.canvas.create_text(
            bx + pad_x, by + pad_y,
            text=text, font=font_tt, fill=COLOR_TEXT_WHITE, anchor="nw", tags=("canvas_tooltip",)
        )
        self._tooltip_items = [bg, tx]
        self.canvas.tag_raise(bg)
        self.canvas.tag_raise(tx)

    def _hide_tooltip(self, *args):
        if self._tooltip_timer:
            self.after_cancel(self._tooltip_timer)
            self._tooltip_timer = None
        if self._tooltip_items:
            for item in self._tooltip_items:
                self.canvas.delete(item)
            self._tooltip_items = []

    def bind_tooltip(self, tag_or_id, text):
        def on_enter(e):
            self._hide_tooltip()
            self._tooltip_timer = self.after(250, lambda: self._show_tooltip(text, e.x, e.y))
        def on_leave(e):
            self._hide_tooltip()
        self.canvas.tag_bind(tag_or_id, "<Enter>", on_enter, add="+")
        self.canvas.tag_bind(tag_or_id, "<Leave>", on_leave, add="+")

    def build_canvas(self):
        self.canvas = tk.Canvas(self, width=WIDTH, height=HEIGHT, highlightthickness=0, bg=COLOR_BG_DARK)
        self.canvas.pack(fill="both", expand=True)

        # 1. Main Background
        self.canvas.create_image(0, 0, image=self.photo_bg, anchor="nw")

        # 2. Header & Branding
        text_x = 36
        if self.photo_icon0:
            self.canvas.create_image(36, 26, image=self.photo_icon0, anchor="nw")
            text_x = 98

        # Badge
        self.canvas.create_text(
            text_x, 26,
            text="VULKAN 1.3 NATIVE PORT • v2.1.0",
            font=(FONT_SUBTITLE, 8, "bold"),
            fill=COLOR_GOLD,
            anchor="nw"
        )

        # What's New / Changelog Button
        self.changelog_btn = self.canvas.create_text(
            text_x + 205, 26,
            text="v2.1.0 Changelog",
            font=(FONT_SUBTITLE, 8, "bold", "underline"),
            fill="#00ADB5",
            anchor="nw"
        )
        self.canvas.tag_bind(self.changelog_btn, "<Enter>", lambda e: (self.canvas.config(cursor="hand2"), self.canvas.itemconfig(self.changelog_btn, fill="#FFFFFF")))
        self.canvas.tag_bind(self.changelog_btn, "<Leave>", lambda e: (self.canvas.config(cursor="arrow"), self.canvas.itemconfig(self.changelog_btn, fill="#00ADB5")))
        self.canvas.tag_bind(self.changelog_btn, "<Button-1>", lambda e: self.open_changelog())

        # Title Line 1 (Shadow + Crisp White)
        self.canvas.create_text(
            text_x + 1, 43,
            text="SENGOKU BASARA 4",
            font=(FONT_TITLE, 19, "bold"),
            fill="#000000",
            anchor="nw"
        )
        self.canvas.create_text(
            text_x, 42,
            text="SENGOKU BASARA 4",
            font=(FONT_TITLE, 19, "bold"),
            fill=COLOR_TEXT_WHITE,
            anchor="nw"
        )

        # Title Line 2
        self.canvas.create_text(
            text_x, 70,
            text="S U M E R A G I",
            font=(FONT_SUBTITLE, 10, "bold"),
            fill=COLOR_GOLD_BRIGHT,
            anchor="nw"
        )

        # Exclusive description
        self.canvas.create_text(
            text_x, 88,
            text="Native x86_64 Runtime & Vulkan 1.3 Engine",
            font=(FONT_FAMILY, 8),
            fill=COLOR_TEXT_SUB,
            anchor="nw"
        )

        # Divider Line
        self.canvas.create_line(36, 110, 480, 110, fill="#232938", width=1)

        # =====================================================================
        # 3. RESOLUTION SELECTOR
        # =====================================================================
        self.canvas.create_text(
            36, 122,
            text="DISPLAY RESOLUTION",
            font=(FONT_FAMILY, 10, "bold"),
            fill="#D6DEE8",
            anchor="nw"
        )

        self.res_options = [
            ("1280×720", "1280x720"),
            ("1920×1080", "1920x1080"),
            ("2560×1440", "2560x1440"),
            ("3840×2160", "3840x2160"),
        ]
        self.res_items = []
        for i, (label, val) in enumerate(self.res_options):
            x = 36 + i * 106
            y = 142
            act, inact, hov = self.pills_res
            img_id = self.canvas.create_image(x, y, image=inact, anchor="nw")
            txt_id = self.canvas.create_text(x + 49, y + 13, text=label, font=(FONT_FAMILY, 8, "bold"), fill=COLOR_TEXT_MUTED)

            tag = f"btn_res_{i}"
            self.canvas.itemconfig(img_id, tags=(tag,))
            self.canvas.itemconfig(txt_id, tags=(tag,))

            self.canvas.tag_bind(tag, "<Enter>", lambda e, idx=i: self._on_res_enter(idx))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, idx=i: self._on_res_leave(idx))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, v=val: self._select_res(v))

            self.res_items.append((img_id, txt_id, val))

        # =====================================================================
        # 4. FRAMERATE TARGET SELECTOR (TRUE INTERNAL LIMITER BYPASS)
        # =====================================================================
        self.canvas.create_text(
            36, 180,
            text="FRAME RATE TARGET (INTERNAL LIMITER UNLOCK)",
            font=(FONT_FAMILY, 10, "bold"),
            fill="#D6DEE8",
            anchor="nw"
        )

        self.fps_options = [
            ("60 FPS", "60"),
            ("90 FPS", "90"),
            ("120 FPS", "120"),
            ("144 FPS", "144"),
            ("240 FPS", "240"),
            ("Max FPS", "0"),
        ]
        self.fps_items = []
        for i, (label, val) in enumerate(self.fps_options):
            x = 36 + i * 72
            y = 200
            act, inact, hov = self.pills_fps
            img_id = self.canvas.create_image(x, y, image=inact, anchor="nw")
            txt_id = self.canvas.create_text(x + 32, y + 13, text=label, font=(FONT_FAMILY, 8, "bold"), fill=COLOR_TEXT_MUTED)

            tag = f"btn_fps_{i}"
            self.canvas.itemconfig(img_id, tags=(tag,))
            self.canvas.itemconfig(txt_id, tags=(tag,))

            self.canvas.tag_bind(tag, "<Enter>", lambda e, idx=i: self._on_fps_enter(idx))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, idx=i: self._on_fps_leave(idx))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, v=val: self._select_fps(v))

            self.fps_items.append((img_id, txt_id, val))

        # =====================================================================
        # 5. ANISOTROPIC FILTERING (TEXTURE QUALITY)
        # =====================================================================
        self.canvas.create_text(
            36, 238,
            text="ANISOTROPIC FILTERING (TEXTURE CLARITY)",
            font=(FONT_FAMILY, 10, "bold"),
            fill="#D6DEE8",
            anchor="nw"
        )

        self.aniso_options = [
            ("Off", "0"),
            ("2x AF", "2"),
            ("4x AF", "4"),
            ("8x AF", "8"),
            ("16x AF", "16"),
        ]
        self.aniso_items = []
        for i, (label, val) in enumerate(self.aniso_options):
            x = 36 + i * 86
            y = 258
            act, inact, hov = self.pills_aniso
            img_id = self.canvas.create_image(x, y, image=inact, anchor="nw")
            txt_id = self.canvas.create_text(x + 39, y + 13, text=label, font=(FONT_FAMILY, 8, "bold"), fill=COLOR_TEXT_MUTED)

            tag = f"btn_aniso_{i}"
            self.canvas.itemconfig(img_id, tags=(tag,))
            self.canvas.itemconfig(txt_id, tags=(tag,))

            self.canvas.tag_bind(tag, "<Enter>", lambda e, idx=i: self._on_aniso_enter(idx))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, idx=i: self._on_aniso_leave(idx))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, v=val: self._select_aniso(v))

            self.aniso_items.append((img_id, txt_id, val))

        # =====================================================================
        # 6. GRAPHICS QUALITY: RENDER SCALE & RCAS SHARPNESS
        # =====================================================================
        self.canvas.create_text(
            36, 292,
            text="RENDER SCALE",
            font=(FONT_FAMILY, 10, "bold"),
            fill="#D6DEE8",
            anchor="nw",
            tags=("tooltip_scale",)
        )

        self.scale_options = [
            ("1.0x", "1.0"),
            ("1.5x", "1.5"),
            ("2.0x", "2.0"),
        ]
        self.scale_items = []
        for i, (label, val) in enumerate(self.scale_options):
            x = 36 + i * 68
            y = 312
            act, inact, hov = self.pills_scale
            img_id = self.canvas.create_image(x, y, image=inact, anchor="nw")
            txt_id = self.canvas.create_text(x + 31, y + 13, text=label, font=(FONT_FAMILY, 8, "bold"), fill=COLOR_TEXT_MUTED)

            tag = f"btn_scale_{i}"
            self.canvas.itemconfig(img_id, tags=(tag, "tooltip_scale"))
            self.canvas.itemconfig(txt_id, tags=(tag, "tooltip_scale"))

            self.canvas.tag_bind(tag, "<Enter>", lambda e, idx=i: self._on_scale_enter(idx))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, idx=i: self._on_scale_leave(idx))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, v=val: self._select_scale(v))

            self.scale_items.append((img_id, txt_id, val))

        # RCAS Sharpness Interactive Slider
        self.lbl_sharp_title = self.canvas.create_text(
            256, 292,
            text=f"RCAS SHARPNESS: {self.sharp_val}%",
            font=(FONT_FAMILY, 10, "bold"),
            fill="#D6DEE8",
            anchor="nw",
            tags=("slider_sharp",)
        )

        val_pct = max(0, min(100, int(self.sharp_val)))
        handle_init_x = 256 + int((val_pct / 100.0) * 200)

        # Track background
        self.slider_bg = self.canvas.create_line(256, 325, 456, 325, fill="#1C2330", width=6, capstyle="round", tags=("slider_sharp",))
        # Track active fill
        self.slider_fill = self.canvas.create_line(256, 325, handle_init_x, 325, fill=COLOR_CRIMSON, width=6, capstyle="round", tags=("slider_sharp",))
        # Draggable handle
        self.slider_handle = self.canvas.create_oval(handle_init_x - 8, 325 - 8, handle_init_x + 8, 325 + 8, fill=COLOR_GOLD, outline="#FFFFFF", width=1.5, tags=("slider_sharp",))
        # Hit area for easy clicking & dragging
        self.slider_hit = self.canvas.create_rectangle(246, 310, 466, 340, fill="", outline="", tags=("slider_sharp",))

        self.canvas.tag_bind("slider_sharp", "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind("slider_sharp", "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind("slider_sharp", "<Button-1>", self._on_slider_click)
        self.canvas.tag_bind("slider_sharp", "<B1-Motion>", self._on_slider_drag)
        self.canvas.tag_bind("slider_sharp", "<ButtonRelease-1>", self._on_slider_release)

        # =====================================================================
        # 7. ENGINE PREFERENCES (2x2 Modern Grid)
        # =====================================================================
        self.canvas.create_text(
            36, 352,
            text="ENGINE PREFERENCES",
            font=(FONT_FAMILY, 10, "bold"),
            fill="#D6DEE8",
            anchor="nw"
        )

        # Toggle 1: Borderless Fullscreen (Col 1, Row 1)
        self.sw1_img = self.canvas.create_image(36, 372, image=self.switch_off, anchor="nw")
        t1_title = self.canvas.create_text(84, 371, text="Borderless Fullscreen", font=(FONT_FAMILY, 9, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        t1_sub = self.canvas.create_text(84, 387, text="Borderless display", font=(FONT_FAMILY, 9), fill=COLOR_TEXT_SUB, anchor="nw")
        tag1 = "toggle_fullscreen"
        for item in (self.sw1_img, t1_title, t1_sub):
            self.canvas.itemconfig(item, tags=(tag1,))
        self.canvas.tag_bind(tag1, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag1, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag1, "<Button-1>", lambda e: self._toggle_setting("fullscreen"))

        # Toggle 2: AMD FSR 1 + RCAS (Col 2, Row 1)
        self.sw2_img = self.canvas.create_image(256, 372, image=self.switch_off, anchor="nw")
        self.t2_title = self.canvas.create_text(304, 371, text="AMD FSR 1 + RCAS", font=(FONT_FAMILY, 9, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        self.t2_sub = self.canvas.create_text(304, 387, text="Edge & contrast sharpening", font=(FONT_FAMILY, 9), fill=COLOR_TEXT_SUB, anchor="nw")
        tag2 = "toggle_fsr"
        for item in (self.sw2_img, self.t2_title, self.t2_sub):
            self.canvas.itemconfig(item, tags=(tag2,))
        self.canvas.tag_bind(tag2, "<Enter>", lambda e: self.canvas.config(cursor="hand2" if self.scale_val == "1.0" else "arrow"))
        self.canvas.tag_bind(tag2, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag2, "<Button-1>", lambda e: self._toggle_setting("fsr"))

        # Toggle 3: Skip Opening Movie (Col 1, Row 2)
        self.sw3_img = self.canvas.create_image(36, 410, image=self.switch_off, anchor="nw")
        t3_title = self.canvas.create_text(84, 409, text="Skip Opening Movie", font=(FONT_FAMILY, 9, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        t3_sub = self.canvas.create_text(84, 425, text="Direct to title screen", font=(FONT_FAMILY, 9), fill=COLOR_TEXT_SUB, anchor="nw")
        tag3 = "toggle_skip_intro"
        for item in (self.sw3_img, t3_title, t3_sub):
            self.canvas.itemconfig(item, tags=(tag3,))
        self.canvas.tag_bind(tag3, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag3, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag3, "<Button-1>", lambda e: self._toggle_setting("skip_intro"))

        # Toggle 4: In-Game FPS Overlay (Col 2, Row 2)
        self.sw4_img = self.canvas.create_image(256, 410, image=self.switch_off, anchor="nw")
        t4_title = self.canvas.create_text(304, 409, text="In-Game FPS Overlay", font=(FONT_FAMILY, 9, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        t4_sub = self.canvas.create_text(304, 425, text="Metrics overlay (Insert)", font=(FONT_FAMILY, 9), fill=COLOR_TEXT_SUB, anchor="nw")
        tag4 = "toggle_show_fps"
        for item in (self.sw4_img, t4_title, t4_sub):
            self.canvas.itemconfig(item, tags=(tag4,))
        self.canvas.tag_bind(tag4, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag4, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag4, "<Button-1>", lambda e: self._toggle_setting("show_fps"))

        # Toggle 5: Performance Mode (Col 1, Row 3)
        self.sw5_img = self.canvas.create_image(36, 448, image=self.switch_off, anchor="nw")
        t5_title = self.canvas.create_text(84, 447, text="Performance Mode", font=(FONT_FAMILY, 9, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        t5_sub = self.canvas.create_text(84, 463, text="720p - no RCAS", font=(FONT_FAMILY, 9), fill=COLOR_TEXT_SUB, anchor="nw")
        tag5 = "toggle_perf_mode"
        for item in (self.sw5_img, t5_title, t5_sub):
            self.canvas.itemconfig(item, tags=(tag5,))
        self.canvas.tag_bind(tag5, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag5, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag5, "<Button-1>", lambda e: self._toggle_setting("perf_mode"))

        # =====================================================================
        # 8. SELECTORS: PROCESS PRIORITY & CRASH TELEMETRY (Row 4)
        # =====================================================================
        # Process Priority Selector
        self.canvas.create_text(
            36, 498,
            text="PRIORITY",
            font=(FONT_FAMILY, 10, "bold"),
            fill=COLOR_GOLD_BRIGHT,
            anchor="w"
        )
        self.prio_options = [
            ("Normal", "normal"),
            ("Above", "above_normal"),
            ("High", "high"),
        ]
        self.prio_items = []
        for i, (label, val) in enumerate(self.prio_options):
            x = 112 + i * 46
            y = 486
            act, inact, hov = self.pills_prio
            img_id = self.canvas.create_image(x, y, image=inact, anchor="nw")
            txt_id = self.canvas.create_text(x + 22, y + 12, text=label, font=(FONT_FAMILY, 7, "bold"), fill=COLOR_TEXT_MUTED)

            tag = f"btn_prio_{i}"
            self.canvas.itemconfig(img_id, tags=(tag,))
            self.canvas.itemconfig(txt_id, tags=(tag,))

            self.canvas.tag_bind(tag, "<Enter>", lambda e, idx=i: self._on_prio_enter(idx))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, idx=i: self._on_prio_leave(idx))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, v=val: self._select_prio(v))

            self.prio_items.append((img_id, txt_id, val))

        # Crash Telemetry Selector
        lbl_telem = self.canvas.create_text(
            276, 498,
            text="TELEMETRY",
            font=(FONT_FAMILY, 10, "bold"),
            fill=COLOR_GOLD_BRIGHT,
            anchor="w",
            tags=("tooltip_telem",)
        )
        self.telem_options = [
            ("Ask", "ask"),
            ("Never", "never"),
            ("Always", "always"),
        ]
        self.telem_items = []
        for i, (label, val) in enumerate(self.telem_options):
            x = 368 + i * 46
            y = 486
            act, inact, hov = self.pills_telem
            img_id = self.canvas.create_image(x, y, image=inact, anchor="nw")
            txt_id = self.canvas.create_text(x + 22, y + 12, text=label, font=(FONT_FAMILY, 7, "bold"), fill=COLOR_TEXT_MUTED)

            tag = f"btn_telem_{i}"
            self.canvas.itemconfig(img_id, tags=(tag, "tooltip_telem"))
            self.canvas.itemconfig(txt_id, tags=(tag, "tooltip_telem"))

            self.canvas.tag_bind(tag, "<Enter>", lambda e, idx=i: self._on_telem_enter(idx))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, idx=i: self._on_telem_leave(idx))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, v=val: self._select_telem(v))

            self.telem_items.append((img_id, txt_id, val))

        # =====================================================================
        # 9. TOOLBAR: CONTROLLER MAPPER, SETUP WIZARD & REBUILD FILES (Row 5)
        # =====================================================================
        # Gamepad Button (110 x 26)
        self.tool_img = self.canvas.create_image(36, 524, image=self.btn_tool_norm, anchor="nw")
        self.tool_txt = self.canvas.create_text(36 + 55, 524 + 13, text="🎮 Gamepad", font=(FONT_FAMILY, 8, "bold"), fill=COLOR_GOLD)
        tag_tool = "btn_map_controller"
        for item in (self.tool_img, self.tool_txt):
            self.canvas.itemconfig(item, tags=(tag_tool,))
        self.canvas.tag_bind(tag_tool, "<Enter>", self._on_tool_enter)
        self.canvas.tag_bind(tag_tool, "<Leave>", self._on_tool_leave)
        self.canvas.tag_bind(tag_tool, "<Button-1>", lambda e: self.open_gamepad_mapper())

        # Setup Wizard Button (120 x 26)
        self.wiz_img = self.canvas.create_image(156, 524, image=self.btn_wiz_norm, anchor="nw")
        self.wiz_txt = self.canvas.create_text(156 + 60, 524 + 13, text="⚡ Setup Wizard", font=(FONT_FAMILY, 8, "bold"), fill=COLOR_GOLD_BRIGHT)
        tag_wiz = "btn_setup_wizard"
        for item in (self.wiz_img, self.wiz_txt):
            self.canvas.itemconfig(item, tags=(tag_wiz,))
        self.canvas.tag_bind(tag_wiz, "<Enter>", self._on_wiz_enter)
        self.canvas.tag_bind(tag_wiz, "<Leave>", self._on_wiz_leave)
        self.canvas.tag_bind(tag_wiz, "<Button-1>", lambda e: self.open_setup_wizard(force=True))

        # Rebuild Files Button (120 x 26)
        self.reb_img = self.canvas.create_image(286, 524, image=self.btn_reb_norm, anchor="nw")
        self.reb_txt = self.canvas.create_text(286 + 60, 524 + 13, text="🔧 Rebuild Files", font=(FONT_FAMILY, 8, "bold"), fill=COLOR_GOLD)
        tag_reb = "btn_rebuild_files"
        for item in (self.reb_img, self.reb_txt):
            self.canvas.itemconfig(item, tags=(tag_reb,))
        self.canvas.tag_bind(tag_reb, "<Enter>", self._on_reb_enter)
        self.canvas.tag_bind(tag_reb, "<Leave>", self._on_reb_leave)
        self.canvas.tag_bind(tag_reb, "<Button-1>", lambda e: self.on_manual_rebuild())

        # Safe Mode Toggle (switch + label)
        self.sw_safe_img = self.canvas.create_image(420, 527, image=self.switch_off, anchor="nw")
        self.safe_txt = self.canvas.create_text(470, 537, text="🛡️ Safe Mode", font=(FONT_FAMILY, 8, "bold"), fill=COLOR_GOLD, anchor="w")
        tag_safe = "toggle_safe_mode"
        for item in (self.sw_safe_img, self.safe_txt):
            self.canvas.itemconfig(item, tags=(tag_safe,))
        self.canvas.tag_bind(tag_safe, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag_safe, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag_safe, "<Button-1>", lambda e: self._toggle_setting("safe_mode"))

        # Logs Button (80 x 26)
        self.logs_img = self.canvas.create_image(580, 524, image=self.btn_logs_norm, anchor="nw")
        self.logs_txt = self.canvas.create_text(580 + 40, 524 + 13, text="📁 Logs", font=(FONT_FAMILY, 8, "bold"), fill=COLOR_GOLD)
        tag_logs = "btn_open_logs"
        for item in (self.logs_img, self.logs_txt):
            self.canvas.itemconfig(item, tags=(tag_logs,))
        self.canvas.tag_bind(tag_logs, "<Enter>", self._on_logs_enter)
        self.canvas.tag_bind(tag_logs, "<Leave>", self._on_logs_leave)
        self.canvas.tag_bind(tag_logs, "<Button-1>", lambda e: self.open_logs_folder())

        # =====================================================================
        # 10. BOTTOM ACTION BAR (Status, Updates & Action Button)
        # =====================================================================
        self.canvas.create_line(36, 566, WIDTH - 36, 566, fill="#232938", width=1)

        # Footer Status Text
        self.footer_status = self.canvas.create_text(38, 607, text="Vulkan: OK  |  VC++: OK  |  Win10+: OK  |  Storage: OK", font=(FONT_FAMILY, 8), fill="#A0A5B5", anchor="w")

        # Check for Updates Button
        self.update_btn = self.canvas.create_text(420, 607, text="Check for Updates", font=(FONT_FAMILY, 8, "underline"), fill="#00ADB5", anchor="w")
        self.canvas.tag_bind(self.update_btn, "<Enter>", lambda e: (self.canvas.config(cursor="hand2"), self.canvas.itemconfig(self.update_btn, fill="#FFFFFF")))
        self.canvas.tag_bind(self.update_btn, "<Leave>", lambda e: (self.canvas.config(cursor="arrow"), self.canvas.itemconfig(self.update_btn, fill="#00ADB5")))
        self.canvas.tag_bind(self.update_btn, "<Button-1>", lambda e: self.check_for_updates())

        self.status_dot = None
        self.status_title = None
        self.status_sub = None

        # Action Button (Right, 270 x 50)
        self.play_img_id = self.canvas.create_image(WIDTH - 36 - 270, 582, image=self.btn_play_normal, anchor="nw")
        self.play_txt_id = self.canvas.create_text(
            WIDTH - 36 - 135, 607,
            text="PLAY GAME",
            font=(FONT_TITLE, 13, "bold"),
            fill=COLOR_TEXT_WHITE
        )

        tag_play = "btn_play_game"
        self.canvas.itemconfig(self.play_img_id, tags=(tag_play,))
        self.canvas.itemconfig(self.play_txt_id, tags=(tag_play,))
        self.canvas.tag_bind(tag_play, "<Enter>", self._on_play_enter)
        self.canvas.tag_bind(tag_play, "<Leave>", self._on_play_leave)
        self.canvas.tag_bind(tag_play, "<Button-1>", self._on_play_click)

        # Tooltips (Hover Info)
        self.bind_tooltip("btn_fps_5", "Internal limiter unlocked. May increase GPU temperature and power draw.")
        self.bind_tooltip("tooltip_scale", "Internal rendering resolution multiplier (1.0x native, 1.5x / 2.0x supersampling).")
        self.bind_tooltip("slider_sharp", "AMD FidelityFX RCAS Sharpness filter strength (0-100%). Default: 75%.")
        self.bind_tooltip("toggle_fsr", "Upscales lower resolutions and sharpens textures for better performance.")
        self.bind_tooltip("toggle_perf_mode", "Forces 720p resolution and disables RCAS sharpening. Ideal for low-end PCs (GTX 1050).")
        self.bind_tooltip("toggle_safe_mode", "Enable this if the game crashes on startup or during combat. Disables all advanced graphics for maximum stability.")
        self.bind_tooltip("tooltip_telem", "Sends anonymous crash reports. No personal data is collected.")

        # Initial GUI Refresh
        self.refresh_controls()

    def refresh_controls(self):
        act_res, inact_res, _ = self.pills_res
        for img_id, txt_id, val in self.res_items:
            if val == self.res_val:
                self.canvas.itemconfig(img_id, image=act_res)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)
            else:
                self.canvas.itemconfig(img_id, image=inact_res)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

        act_fps, inact_fps, _ = self.pills_fps
        for img_id, txt_id, val in self.fps_items:
            if val == self.fps_val:
                self.canvas.itemconfig(img_id, image=act_fps)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)
            else:
                self.canvas.itemconfig(img_id, image=inact_fps)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

        act_aniso, inact_aniso, _ = self.pills_aniso
        for img_id, txt_id, val in self.aniso_items:
            if val == self.aniso_val:
                self.canvas.itemconfig(img_id, image=act_aniso)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)
            else:
                self.canvas.itemconfig(img_id, image=inact_aniso)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

        act_scale, inact_scale, _ = self.pills_scale
        for img_id, txt_id, val in self.scale_items:
            if val == self.scale_val:
                self.canvas.itemconfig(img_id, image=act_scale)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)
            else:
                self.canvas.itemconfig(img_id, image=inact_scale)
                if self.fsr_val and val in ("1.5", "2.0"):
                    self.canvas.itemconfig(txt_id, fill="#444C56")
                else:
                    self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

        self._update_slider_ui()

        self.canvas.itemconfig(self.sw1_img, image=self.switch_on if self.fullscreen_val else self.switch_off)
        if self.scale_val in ("1.5", "2.0"):
            self.canvas.itemconfig(self.sw2_img, image=self.switch_disabled)
            self.canvas.itemconfig(self.t2_title, fill="#555E6D")
            self.canvas.itemconfig(self.t2_sub, text="Disabled (Render Scale > 1.0x)", fill="#444C56")
            self.bind_tooltip("toggle_fsr", "FSR is disabled when Render Scale > 1.0 to prevent scaling conflicts.")
        else:
            self.canvas.itemconfig(self.sw2_img, image=self.switch_on if self.fsr_val else self.switch_off)
            self.canvas.itemconfig(self.t2_title, fill=COLOR_TEXT_WHITE)
            self.canvas.itemconfig(self.t2_sub, text="Edge & contrast sharpening", fill=COLOR_TEXT_SUB)
            self.bind_tooltip("toggle_fsr", "Upscales lower resolutions and sharpens textures for better performance.")

        if self.fsr_val:
            self.bind_tooltip("tooltip_scale", "Render Scale is locked to 1.0x while AMD FSR 1 is enabled.")
        else:
            self.bind_tooltip("tooltip_scale", "Internal rendering resolution multiplier (1.0x native, 1.5x / 2.0x supersampling).")

        self.canvas.itemconfig(self.sw3_img, image=self.switch_on if self.skip_intro_val else self.switch_off)
        self.canvas.itemconfig(self.sw4_img, image=self.switch_on if self.show_fps_val else self.switch_off)
        self.canvas.itemconfig(self.sw5_img, image=self.switch_on if self.perf_mode_val else self.switch_off)
        if hasattr(self, "sw_safe_img"):
            self.canvas.itemconfig(self.sw_safe_img, image=self.switch_on if self.safe_mode_val else self.switch_off)
            self.canvas.itemconfig(self.safe_txt, text="🛡️ Safe Mode 🔒" if self.safe_mode_val else "🛡️ Safe Mode")

        act_prio, inact_prio, _ = self.pills_prio
        for img_id, txt_id, val in self.prio_items:
            if val == self.prio_val:
                self.canvas.itemconfig(img_id, image=act_prio)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)
            else:
                self.canvas.itemconfig(img_id, image=inact_prio)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

        act_telem, inact_telem, _ = self.pills_telem
        for img_id, txt_id, val in self.telem_items:
            if val == self.telem_val:
                self.canvas.itemconfig(img_id, image=act_telem)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)
            else:
                self.canvas.itemconfig(img_id, image=inact_telem)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

    def _on_res_enter(self, idx):
        self.canvas.config(cursor="hand2")
        img_id, txt_id, val = self.res_items[idx]
        if val != self.res_val:
            _, _, hov = self.pills_res
            self.canvas.itemconfig(img_id, image=hov)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)

    def _on_res_leave(self, idx):
        self.canvas.config(cursor="arrow")
        img_id, txt_id, val = self.res_items[idx]
        if val != self.res_val:
            _, inact, _ = self.pills_res
            self.canvas.itemconfig(img_id, image=inact)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

    def _select_res(self, val):
        self.res_val = val
        self.refresh_controls()
        self.sync_ini()

    def _on_fps_enter(self, idx):
        self.canvas.config(cursor="hand2")
        img_id, txt_id, val = self.fps_items[idx]
        if val != self.fps_val:
            _, _, hov = self.pills_fps
            self.canvas.itemconfig(img_id, image=hov)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)

    def _on_fps_leave(self, idx):
        self.canvas.config(cursor="arrow")
        img_id, txt_id, val = self.fps_items[idx]
        if val != self.fps_val:
            _, inact, _ = self.pills_fps
            self.canvas.itemconfig(img_id, image=inact)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

    def _select_fps(self, val):
        if self.safe_mode_val:
            self._show_safe_mode_warning()
            return
        self.fps_val = val
        self.refresh_controls()
        self.sync_ini()

    def _on_aniso_enter(self, idx):
        self.canvas.config(cursor="hand2")
        img_id, txt_id, val = self.aniso_items[idx]
        if val != self.aniso_val:
            _, _, hov = self.pills_aniso
            self.canvas.itemconfig(img_id, image=hov)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)

    def _on_aniso_leave(self, idx):
        self.canvas.config(cursor="arrow")
        img_id, txt_id, val = self.aniso_items[idx]
        if val != self.aniso_val:
            _, inact, _ = self.pills_aniso
            self.canvas.itemconfig(img_id, image=inact)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

    def _select_aniso(self, val):
        if self.safe_mode_val:
            self._show_safe_mode_warning()
            return
        self.aniso_val = val
        self.refresh_controls()
        self.sync_ini()

    def _on_prio_enter(self, idx):
        self.canvas.config(cursor="hand2")
        img_id, txt_id, val = self.prio_items[idx]
        if val != self.prio_val:
            _, _, hov = self.pills_prio
            self.canvas.itemconfig(img_id, image=hov)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)

    def _on_prio_leave(self, idx):
        self.canvas.config(cursor="arrow")
        img_id, txt_id, val = self.prio_items[idx]
        if val != self.prio_val:
            _, inact, _ = self.pills_prio
            self.canvas.itemconfig(img_id, image=inact)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

    def _select_prio(self, val):
        self.prio_val = val
        self.refresh_controls()
        self.sync_ini()

    def _on_telem_enter(self, idx):
        self.canvas.config(cursor="hand2")
        img_id, txt_id, val = self.telem_items[idx]
        if val != self.telem_val:
            _, _, hov = self.pills_telem
            self.canvas.itemconfig(img_id, image=hov)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)

    def _on_telem_leave(self, idx):
        self.canvas.config(cursor="arrow")
        img_id, txt_id, val = self.telem_items[idx]
        if val != self.telem_val:
            _, inact, _ = self.pills_telem
            self.canvas.itemconfig(img_id, image=inact)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

    def _select_telem(self, val):
        self.telem_val = val
        self.refresh_controls()
        self.sync_ini()

    def _on_tool_enter(self, e):
        self.canvas.config(cursor="hand2")
        self.canvas.itemconfig(self.tool_img, image=self.btn_tool_hov)

    def _on_tool_leave(self, e):
        self.canvas.config(cursor="arrow")
        self.canvas.itemconfig(self.tool_img, image=self.btn_tool_norm)

    def _on_wiz_enter(self, e):
        self.canvas.config(cursor="hand2")
        self.canvas.itemconfig(self.wiz_img, image=self.btn_wiz_hov)

    def _on_wiz_leave(self, e):
        self.canvas.config(cursor="arrow")
        self.canvas.itemconfig(self.wiz_img, image=self.btn_wiz_norm)

    def _on_reb_enter(self, e):
        self.canvas.config(cursor="hand2")
        self.canvas.itemconfig(self.reb_img, image=self.btn_reb_hov)

    def _on_reb_leave(self, e):
        self.canvas.config(cursor="arrow")
        self.canvas.itemconfig(self.reb_img, image=self.btn_reb_norm)

    def _on_logs_enter(self, e):
        self.canvas.config(cursor="hand2")
        self.canvas.itemconfig(self.logs_img, image=self.btn_logs_hov)

    def _on_logs_leave(self, e):
        self.canvas.config(cursor="arrow")
        self.canvas.itemconfig(self.logs_img, image=self.btn_logs_norm)

    def _on_scale_enter(self, idx):
        img_id, txt_id, val = self.scale_items[idx]
        if self.fsr_val and val in ("1.5", "2.0"):
            self.canvas.config(cursor="arrow")
            return
        self.canvas.config(cursor="hand2")
        if val != self.scale_val:
            _, _, hov = self.pills_scale
            self.canvas.itemconfig(img_id, image=hov)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)

    def _on_scale_leave(self, idx):
        self.canvas.config(cursor="arrow")
        img_id, txt_id, val = self.scale_items[idx]
        if val != self.scale_val:
            _, inact, _ = self.pills_scale
            self.canvas.itemconfig(img_id, image=inact)
            if self.fsr_val and val in ("1.5", "2.0"):
                self.canvas.itemconfig(txt_id, fill="#444C56")
            else:
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

    def _select_scale(self, val):
        if self.safe_mode_val:
            self._show_safe_mode_warning()
            return
        self.scale_val = val
        if val in ("1.5", "2.0"):
            self.fsr_val = False
        self.refresh_controls()
        self.sync_ini()

    def _on_slider_click(self, event):
        self._is_dragging_slider = True
        self._update_slider_from_event(event)

    def _on_slider_drag(self, event):
        if getattr(self, "_is_dragging_slider", False):
            self._update_slider_from_event(event)

    def _on_slider_release(self, event):
        if getattr(self, "_is_dragging_slider", False):
            self._is_dragging_slider = False
            self._update_slider_from_event(event)
            self.sync_ini()

    def _update_slider_from_event(self, event):
        x = max(256, min(456, event.x))
        val = int(round(((x - 256) / 200.0) * 100))
        self.sharp_val = val
        self._update_slider_ui()

    def _update_slider_ui(self):
        val = max(0, min(100, int(getattr(self, "sharp_val", 75))))
        handle_x = 256 + int((val / 100.0) * 200)
        if hasattr(self, "slider_fill"):
            self.canvas.coords(self.slider_fill, 256, 325, handle_x, 325)
        if hasattr(self, "slider_handle"):
            self.canvas.coords(self.slider_handle, handle_x - 8, 325 - 8, handle_x + 8, 325 + 8)
        if hasattr(self, "lbl_sharp_title"):
            self.canvas.itemconfig(self.lbl_sharp_title, text=f"RCAS SHARPNESS: {val}%")

    def open_changelog(self):
        candidates = [
            base_path("CHANGELOG.md"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "CHANGELOG.md"),
        ]
        changelog_path = next((p for p in candidates if os.path.exists(p)), None)
        if changelog_path:
            def _open():
                try:
                    os.startfile(changelog_path)
                except Exception:
                    webbrowser.open(changelog_path)
            threading.Thread(target=_open, daemon=True).start()
        else:
            messagebox.showinfo("v2.1.0 Changelog", "CHANGELOG.md not found in the game directory.")

    def check_for_updates(self):
        import urllib.request
        import json

        try:
            # Get current local version
            local_ver = "v2.1.0"
            if os.path.isfile("VERSION.txt"):
                with open("VERSION.txt", "r") as f:
                    local_ver = f.read().strip()

            # Fetch latest from GitHub API
            url = "https://api.github.com/repos/krixsan/Basara-4-Sumeragi-Native-PC/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Basara4-Launcher'})

            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_ver = data.get("tag_name", "")
                html_url = data.get("html_url", "https://github.com/krixsan/Basara-4-Sumeragi-Native-PC/releases")

                if latest_ver and latest_ver != local_ver:
                    ans = messagebox.askyesno(
                        "Update Available!",
                        f"A new version is available!\n\nLocal: {local_ver}\nLatest: {latest_ver}\n\nWould you like to download it now?"
                    )
                    if ans:
                        webbrowser.open(html_url)
                else:
                    messagebox.showinfo("Up to Date", f"You are running the latest version ({local_ver}).")

        except Exception as e:
            messagebox.showerror("Update Error", f"Could not check for updates. Check your internet connection.\n\nError: {e}")

    def on_manual_rebuild(self):
        confirm = messagebox.askyesno(
            "Rebuild Game Files",
            "Are you sure? This will re-extract and link game files.",
            icon="question"
        )
        if not confirm:
            return
        self.canvas.config(cursor="watch")
        self.config(cursor="watch")
        self.start_repair_flow(launch_after=False)

    on_rebuild_files = on_manual_rebuild

    def open_setup_wizard(self, force=True):
        FirstRunWizard(
            parent=self,
            on_complete=self.on_wizard_complete,
            on_play=self.on_wizard_play
        )

    def check_first_run_wizard(self):
        missing, exe, boot_bin, app0, eboot_found, *extra = verify_game_installation()
        if not boot_bin and not eboot_found and self.first_run_done not in ("1", "true"):
            self.open_setup_wizard(force=False)

    def on_wizard_complete(self):
        self.first_run_done = "1"
        self.legal_acknowledged = "1"
        self.sync_ini()
        self.evaluate_system_readiness()

    def on_wizard_play(self):
        self.first_run_done = "1"
        self.legal_acknowledged = "1"
        self.sync_ini()
        self.evaluate_system_readiness()
        self.launch_game()

    def open_logs_folder(self):
        log_dir = base_path("user", "logs")
        os.makedirs(log_dir, exist_ok=True)
        try:
            os.startfile(log_dir)
        except Exception as err:
            messagebox.showerror("Logs", f"Could not open log folder:\n\n{err}")

    def _show_safe_mode_warning(self):
        messagebox.showwarning(
            "Safe Mode Active",
            "Cannot change graphics settings while Safe Mode is active.\n\n"
            "Safe Mode forces the game to 60 FPS, 1.0x Render Scale, 4x AF, and disables FSR to prevent crashes.\n\n"
            "Please turn off Safe Mode to customize your graphics."
        )

    def show_crash_dialog(self, exit_code, log_file_path, reason=None, matched=None):
        try:
            if reason is None:
                is_crash, reason, matched = scan_log_for_crash(exit_code, log_file_path)
            res = generate_crash_report(exit_code, log_file_path, reason, matched)
            if len(res) == 4:
                report_path, log_copy, content, bundle_path = res
            else:
                report_path, log_copy, content = res[:3]
                bundle_path = None
            self.deiconify()
            dialog = CrashDialog(report_path, base_path("crashes"), content, exit_code, reason, parent=self, bundle_path=bundle_path)
            dialog.show()
            return
        except Exception as err:
            print(f"[LAUNCHER] Fallback crash dialog due to: {err}")

        try:
            with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
                last_15_lines = "".join(f.readlines()[-15:]).strip()
        except Exception:
            last_15_lines = "(log file not available)"
        if not last_15_lines:
            last_15_lines = "(no log output)"
        self.deiconify()
        messagebox.showerror(
            "Game Crashed",
            f"The game process exited unexpectedly (Code: {exit_code}).\n\n"
            "This is usually caused by missing game files, low RAM, or incompatible GPU drivers.\n\n"
            f"Last log output:\n{last_15_lines}\n\n"
            "Try enabling 'Safe Mode' or check your Vulkan drivers."
        )

    def open_gamepad_mapper(self):
        mapper_exe = "basara4-pad-mapper.exe"
        if os.path.isfile(mapper_exe):
            os.makedirs("user", exist_ok=True)
            subprocess.Popen([os.path.abspath(mapper_exe), "user/gamepad_mapping.txt"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            messagebox.showinfo("Controller Mapping", "Standard XInput (Xbox/PlayStation) pads work natively!\nIf using a generic DInput controller, basara4-pad-mapper.exe will calibrate it.")

    def _toggle_setting(self, name):
        if getattr(self, "safe_mode_val", False) and name in ("fullscreen", "fsr", "perf_mode"):
            self._show_safe_mode_warning()
            return
        if name == "fullscreen":
            self.fullscreen_val = not self.fullscreen_val
        elif name == "fsr":
            if self.scale_val in ("1.5", "2.0"):
                # Mutual exclusivity: FSR is disabled when Render Scale > 1.0 to prevent scaling conflicts
                return
            self.fsr_val = not self.fsr_val
            if self.fsr_val:
                self.scale_val = "1.0"
        elif name == "skip_intro":
            self.skip_intro_val = not self.skip_intro_val
        elif name == "show_fps":
            self.show_fps_val = not self.show_fps_val
        elif name == "perf_mode":
            self.perf_mode_val = not self.perf_mode_val
        elif name == "safe_mode":
            self.safe_mode_val = not self.safe_mode_val
            if self.safe_mode_val:
                self.fullscreen_val = False
                self.scale_val = "1.0"
                self.fps_val = "60"
                self.aniso_val = "4"
                self.async_pipelines_val = "0"
                self.fsr_val = False
        self.refresh_controls()
        self.sync_ini()

    def _on_play_enter(self, event):
        if self.state == "READY_TO_PLAY":
            self.canvas.config(cursor="hand2")
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_hover)
        elif self.state == "READY_TO_INIT":
            self.canvas.config(cursor="hand2")
            self.canvas.itemconfig(self.play_img_id, image=self.btn_init_hover)
        elif self.state == "REPAIR_REQUIRED":
            self.canvas.config(cursor="hand2")
            self.canvas.itemconfig(self.play_img_id, image=self.btn_repair_hover)

    def _on_play_leave(self, event):
        self.canvas.config(cursor="arrow")
        if self.state == "READY_TO_PLAY":
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_normal)
        elif self.state == "READY_TO_INIT":
            self.canvas.itemconfig(self.play_img_id, image=self.btn_init_normal)
        elif self.state == "REPAIR_REQUIRED":
            self.canvas.itemconfig(self.play_img_id, image=self.btn_repair_normal)

    def _on_play_click(self, event):
        if getattr(self, "_is_launching", False) or self.state == "LAUNCHING":
            return

        if self.state == "READY_TO_PLAY":
            self.state = "LAUNCHING"
            self._is_launching = True
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_disabled)
            self.canvas.itemconfig(self.play_txt_id, text="LAUNCHING...", fill="#A0A8B8")
            self.canvas.config(cursor="watch")
            self.config(cursor="watch")
            self.update_idletasks()
            threading.Thread(target=self._launch_worker, daemon=True).start()

        elif self.state == "READY_TO_INIT":
            self.state = "LAUNCHING"
            self._is_launching = True
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_disabled)
            self.canvas.itemconfig(self.play_txt_id, text="LAUNCHING...", fill="#A0A8B8")
            self.canvas.config(cursor="watch")
            self.config(cursor="watch")
            self.update_idletasks()

            def init_check():
                missing, exe, boot_bin, app0, eboot_found, *extra = verify_game_installation()
                if app0 and eboot_found:
                    self.after(0, lambda: self.start_initialization_flow(app0))
                else:
                    self.after(0, self.evaluate_system_readiness)

            threading.Thread(target=init_check, daemon=True).start()

        elif self.state == "REPAIR_REQUIRED":
            self.state = "LAUNCHING"
            self._is_launching = True
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_disabled)
            self.canvas.itemconfig(self.play_txt_id, text="LAUNCHING...", fill="#A0A8B8")
            self.canvas.config(cursor="watch")
            self.config(cursor="watch")
            self.update_idletasks()
            self.start_repair_flow(launch_after=True)

    def evaluate_system_readiness(self):
        missing, exe, boot_bin, app0, eboot_found, *extra = verify_game_installation()
        link_warning = extra[0] if extra else None

        if boot_bin:
            if link_warning:
                self.state = "REPAIR_REQUIRED"
                self.canvas.itemconfig(self.play_img_id, image=self.btn_repair_normal)
                self.canvas.itemconfig(self.play_txt_id, text="REPAIR & PLAY", fill=COLOR_TEXT_WHITE)
                self.canvas.config(cursor="arrow")
                self.config(cursor="arrow")
            else:
                self.state = "READY_TO_PLAY"
                self.canvas.itemconfig(self.play_img_id, image=self.btn_play_normal)
                self.canvas.itemconfig(self.play_txt_id, text="PLAY GAME", fill=COLOR_TEXT_WHITE)
                self.canvas.config(cursor="arrow")
                self.config(cursor="arrow")
        elif eboot_found and HAS_AUTO_BUILDER:
            self.state = "READY_TO_INIT"
            self.canvas.itemconfig(self.play_img_id, image=self.btn_init_normal)
            self.canvas.itemconfig(self.play_txt_id, text="INITIALIZE & PLAY", fill="#0A0C12")
            self.canvas.config(cursor="arrow")
            self.config(cursor="arrow")
        else:
            self.state = "MISSING"
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_disabled)
            self.canvas.itemconfig(self.play_txt_id, text="SETUP REQUIRED", fill="#6E7A8E")
            self.canvas.config(cursor="arrow")
            self.config(cursor="arrow")

    def start_initialization_flow(self, app0_path):
        self.state = "BUILDING"
        self.canvas.config(cursor="watch")
        if self.status_dot:
            self.canvas.itemconfig(self.status_dot, fill=COLOR_AMBER)
        if self.status_title:
            self.canvas.itemconfig(self.status_title, text="Building native binary image (out/boot-linked.bin)...", fill=COLOR_AMBER)
        if self.status_sub:
            self.canvas.itemconfig(self.status_sub, text="Linking eboot.bin + PRX modules. Please wait ~15-30s...", fill=COLOR_GOLD)
        self.canvas.itemconfig(self.play_img_id, image=self.btn_play_disabled)
        self.canvas.itemconfig(self.play_txt_id, text="INITIALIZING...", fill="#A0A8B8")

        def init_worker():
            try:
                out_dir = os.path.join(os.getcwd(), "out")
                auto_builder.auto_prepare(
                    app0_path,
                    out_dir,
                    source_hint_dir=app0_path,
                    status_callback=lambda msg: self.after(0, lambda m=msg: self.update_init_status(m))
                )
                self.after(300, self.on_init_success)
            except Exception as err:
                self.after(300, lambda e=str(err): self.on_init_failure(e))

        threading.Thread(target=init_worker, daemon=True).start()

    def update_init_status(self, message):
        if self.state == "BUILDING" and self.status_sub:
            self.canvas.itemconfig(self.status_sub, text=message)

    def on_init_success(self):
        self.evaluate_system_readiness()
        self.launch_game()

    def on_init_failure(self, error_msg):
        self.evaluate_system_readiness()
        messagebox.showerror("Setup Error", f"Failed to auto-generate boot-linked.bin:\n\n{error_msg}")

    def start_repair_flow(self, launch_after=True):
        if getattr(self, "state", None) == "BUILDING":
            return

        missing, exe, boot_bin, app0, eboot_found, *extra = verify_game_installation()
        if not app0 or not eboot_found:
            for cand in [os.path.join("extracted_game", "app0"), "app0"]:
                if os.path.isfile(os.path.join(cand, "eboot.bin")):
                    app0 = cand
                    eboot_found = True
                    break

        if not app0 or not eboot_found:
            resp = messagebox.askyesno(
                "Setup Required",
                "Game files (eboot.bin) not found in extracted_game/app0.\n\n"
                "Would you like to open Setup Wizard to locate your game directory?",
                icon="question"
            )
            if resp:
                self.open_setup_wizard(force=True)
            return

        self.state = "BUILDING"
        self.canvas.config(cursor="watch")
        if self.status_dot:
            self.canvas.itemconfig(self.status_dot, fill=COLOR_AMBER)
        if self.status_title:
            self.canvas.itemconfig(self.status_title, text="Repairing & re-linking native PS4 modules...", fill=COLOR_AMBER)
        if self.status_sub:
            self.canvas.itemconfig(self.status_sub, text="Scanning .sprx modules & rebuilding boot-linked.bin...", fill=COLOR_GOLD)
        self.canvas.itemconfig(self.play_img_id, image=self.btn_play_disabled)
        self.canvas.itemconfig(self.play_txt_id, text="REPAIRING...", fill="#A0A8B8")

        def repair_worker():
            try:
                out_dir = os.path.join(os.getcwd(), "out")
                os.makedirs(out_dir, exist_ok=True)

                if not HAS_AUTO_BUILDER or auto_builder is None:
                    raise RuntimeError("auto_builder module could not be imported!")

                def status_cb(msg):
                    self.after(0, lambda m=msg: self.update_init_status(m))

                # Re-extract .sprx and re-link all modules
                auto_builder.auto_prepare(
                    app0,
                    out_dir,
                    source_hint_dir=app0,
                    status_callback=status_cb
                )

                # Check game integrity
                boot_linked = os.path.join(out_dir, "boot-linked.bin")
                is_valid, msg = check_game_integrity(boot_linked)
                if not is_valid:
                    raise RuntimeError(f"Repair verification failed: {msg}")

                self.after(300, lambda: self.on_repair_success(launch_after=launch_after))
            except Exception as err:
                self.after(300, lambda e=str(err): self.on_repair_failure(e))

        threading.Thread(target=repair_worker, daemon=True).start()

    def on_repair_success(self, launch_after=True):
        self.evaluate_system_readiness()
        if launch_after:
            self.launch_game()
        else:
            messagebox.showinfo(
                "Repair Complete",
                "Game files repaired successfully!\n\n"
                "All 7 native PS4 modules (including audio libSceNgs2 and libSceAjm) are properly linked."
            )

    def on_repair_failure(self, error_msg):
        self.evaluate_system_readiness()
        messagebox.showerror(
            "Repair Error",
            f"Failed to repair/rebuild game files:\n\n{error_msg}\n\n"
            "Please ensure you have copied the entire PS4 game directory or provide 11.00_sys_modules.zip."
        )

    def launch_game(self):
        self.state = "LAUNCHING"
        self._is_launching = True
        self.canvas.itemconfig(self.play_img_id, image=self.btn_play_disabled)
        self.canvas.itemconfig(self.play_txt_id, text="LAUNCHING...", fill="#A0A8B8")
        self.canvas.config(cursor="watch")
        self.config(cursor="watch")
        self.update_idletasks()
        threading.Thread(target=self._launch_worker, daemon=True).start()

    def _launch_worker(self):
        try:
            missing, exe, boot_bin, app0, eboot_found, *extra = verify_game_installation()
            link_warning = extra[0] if extra else None
            if not boot_bin:
                def show_missing():
                    self.evaluate_system_readiness()
                    messagebox.showerror("Engine Warning", "Cannot launch. Missing components:\n\n" + "\n".join(missing))
                self.after(0, show_missing)
                return

            if link_warning:
                repair_choice = [False, False]
                evt = threading.Event()

                def ask_user():
                    do_repair = messagebox.askyesno(
                        "Audio Modules Missing",
                        f"⚠️ Game files incomplete (Audio modules missing):\n\n"
                        f"{link_warning}\n\n"
                        f"Audio will stutter or cut out because native audio modules (libSceNgs2/libSceAjm) are missing.\n\n"
                        f"Would you like to automatically repair your game files now?",
                        icon="warning"
                    )
                    if do_repair:
                        repair_choice[0] = True
                    else:
                        proceed = messagebox.askyesno(
                            "Launch Degraded",
                            "Do you still want to launch with degraded audio?",
                            icon="warning"
                        )
                        repair_choice[1] = proceed
                    evt.set()

                self.after(0, ask_user)
                evt.wait()

                if repair_choice[0]:
                    self.after(0, lambda: self.start_repair_flow(launch_after=True))
                    return
                if not repair_choice[1]:
                    self.after(0, self.evaluate_system_readiness)
                    return

            self.sync_ini()

            # True Internal Limiter Bypass & Frame Rate setup in background thread
            out_dir = os.path.join(os.getcwd(), "out")
            ini_patch_60 = (read_ini().get("patch_60fps", "1") == "1")
            if HAS_AUTO_BUILDER and auto_builder and eboot_found:
                if self.fps_val != "60" or ini_patch_60:
                    try:
                        auto_builder.apply_fps_patches(
                            app0, out_dir, unlimited_fps=ini_patch_60
                        )
                    except Exception as e:
                        print(f"Warning: could not apply FPS patches: {e}")
                else:
                    patch_file = os.path.join(out_dir, "patches.bin")
                    if os.path.isfile(patch_file):
                        try:
                            os.remove(patch_file)
                        except Exception:
                            pass

            # Environment variables for uncapped vblank / limiter
            env = os.environ.copy()
            if self.fps_val != "60":
                env["BB_VBLANK_HZ"] = "0"
                env["BB_FPS_LIMIT"] = str(self.fps_val)
            else:
                env["BB_VBLANK_HZ"] = "0" if ini_patch_60 else "60"
                env["BB_FPS_LIMIT"] = "60"

            if hasattr(self, "prio_val") and self.prio_val:
                env["BB_PRIORITY"] = self.prio_val

            # Gamepad mapping support
            for map_path in [base_path("user", "gamepad_mapping.txt"), base_path("gamepad_mapping.txt")]:
                if os.path.isfile(map_path):
                    env["SDL_GAMECONTROLLERCONFIG_FILE"] = base_path(map_path)
                    break

            cmd = [
                base_path(exe),
                base_path(boot_bin)
            ]
            import_names = base_path("out", "import_names.txt")
            if not os.path.isfile(import_names) and os.path.isfile(base_path("import_names.txt")):
                import_names = base_path("import_names.txt")
            if os.path.isfile(import_names):
                cmd.extend(["--import-names", base_path(import_names)])

            # 4. Pre-Launch WER Status & Patches Validation
            try:
                wer_ok, wer_msg = check_wer_status()
                print(f"[LAUNCHER] Windows Error Reporting (WER): {wer_msg}")
            except Exception as e:
                print(f"[LAUNCHER] WER check notice: {e}")

            content_bin = base_path("out", "content.bin")
            if not os.path.isfile(content_bin) and os.path.isfile(base_path("content.bin")):
                content_bin = base_path("content.bin")
            if os.path.isfile(content_bin):
                cmd.extend(["--content-profile", base_path(content_bin)])

            patches_bin = base_path("out", "patches.bin")
            if not os.path.isfile(patches_bin) and os.path.isfile(base_path("patches.bin")):
                patches_bin = base_path("patches.bin")

            if os.path.isfile(patches_bin):
                cmd.extend(["--patches", base_path(patches_bin)])
                print(f"[LAUNCHER] Active guest runtime patches verified: {patches_bin} ({os.path.getsize(patches_bin)} bytes)")
            else:
                print("[LAUNCHER] Warning: patches.bin not found! Dynamic guest hooks will not be applied.")

            cmd.extend(["--app0", base_path(app0), "--user", base_path("user")])

            # Seamless minimize/hide on main thread
            self.after(0, self.withdraw)

            os.makedirs(base_path("user", "logs"), exist_ok=True)
            log_file_path = base_path("user", "logs", "last_run.log")
            with open(log_file_path, "w", encoding="utf-8", errors="replace") as log_file:
                proc = subprocess.Popen(cmd, cwd=BASE_DIR, env=env, stdout=log_file, stderr=subprocess.STDOUT)
                proc.wait()

            # 3. Post-execution Crash Detection & Dialog Integration
            is_crash, reason, matched = scan_log_for_crash(proc.returncode, log_file_path)
            if is_crash:
                exit_code = proc.returncode
                self.after(0, lambda ec=exit_code, lfp=log_file_path, r=reason, m=matched: self.show_crash_dialog(ec, lfp, r, m))

        except Exception as err:
            print(f"Game runtime error: {err}")
            self.after(0, lambda e=str(err): messagebox.showerror("Launch Error", f"Error launching game:\n\n{e}"))
        finally:
            self._is_launching = False
            self.after(100, self.on_game_finish)

    def on_game_finish(self):
        self._is_launching = False
        self.deiconify()
        self.evaluate_system_readiness()


def run_headless_prepare():
    """Headless CLI preparation invoked via --prepare-only."""
    if sys.stdout is None:
        try:
            ctypes.windll.kernel32.AttachConsole(-1)
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
            sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("============================================================")
    print("  Sengoku Basara 4 Sumeragi — Native Binary Auto-Builder")
    print("============================================================")

    # Check if already built
    target_boot = os.path.join("out", "boot-linked.bin")
    if os.path.isfile("boot-linked.bin") or os.path.isfile(target_boot):
        print(f"[INFO] Boot binary already exists: {target_boot}")
        return 0

    if not HAS_AUTO_BUILDER:
        print("[ERROR] Auto-builder module not available in this environment.")
        return 1

    app0 = None
    for cand in [os.path.join("extracted_game", "app0"), "app0"]:
        if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "eboot.bin")):
            app0 = cand
            break

    if not app0:
        print("[ERROR] Could not find eboot.bin in 'extracted_game/app0' or 'app0'.")
        return 1

    out_dir = os.path.join(os.getcwd(), "out")
    print(f"[INFO] Building native binary from {app0} into {out_dir}...")
    try:
        auto_builder.auto_prepare(app0, out_dir, source_hint_dir=app0, status_callback=lambda msg: print(f"  -> {msg}"))
        print("[SUCCESS] out/boot-linked.bin and metadata generated successfully!")
        return 0
    except Exception as err:
        print(f"[FATAL] Preparation failed: {err}")
        return 1


def scrub_pii(text: str) -> str:
    """Scrub personal identifiable information (usernames, local IPs, MACs) from log text."""
    if not text:
        return ""
    # Scrub Windows usernames in paths C:\Users\<username>\ or C:/Users/<username>/
    text = re.sub(r'([A-Za-z]:[/\\]Users[/\\])[^/\\ \r\n\t]+', r'\1[USER]', text, flags=re.IGNORECASE)
    # Scrub Linux/Unix usernames /home/<username>/
    text = re.sub(r'(/home/)[^/\\ \r\n\t]+', r'\1[USER]', text)
    # Scrub private IPv4 addresses (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    text = re.sub(r'\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b', '[REDACTED_IP]', text)
    # Scrub MAC addresses (e.g. 00:1A:2B:3C:4D:5E or 00-1A-2B-3C-4D-5E)
    text = re.sub(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b', '[REDACTED_MAC]', text)
    return text


def upload_crash_package(zip_path: str, endpoint: str) -> bool:
    """
    Diagnostic telemetry uploader.
    In Update 2/3, packages are organized into user/crashes/pending/.
    Update 4 will wire HTTPS POST transmission to the telemetry server.
    """
    try:
        if not os.path.isfile(zip_path):
            return False
        print(f"[TELEMETRY] Package queued: {zip_path}")
        # TODO (Update 4): HTTP POST payload to endpoint via winhttp/urllib
        return True
    except Exception as e:
        print(f"[TELEMETRY] Upload error: {e}")
        return False


def check_pending_crash_consent():
    """Checks for .need_consent flag and packages crash minidump + scrubbed logs."""
    flag_file = os.path.join("user", "crashes", ".need_consent")
    if not os.path.isfile(flag_file):
        return

    ini = read_ini()
    upload_pref = ini.get("telemetry_upload", "ask").lower()
    endpoint = ini.get("telemetry_endpoint", "https://api.github.com/repos/krixsan/Basara-4-Sumeragi-Native-PC/telemetry")

    if upload_pref == "never":
        try:
            os.remove(flag_file)
        except Exception:
            pass
        return

    if upload_pref == "ask":
        MB_YESNO = 0x04
        MB_ICONQUESTION = 0x20
        IDYES = 6
        try:
            res = ctypes.windll.user32.MessageBoxW(
                0,
                "Sengoku Basara 4 Sumeragi encountered an unexpected error during the last session.\n\n"
                "Would you like to package and save diagnostic crash data (crash minidump and anonymized log)?\n\n"
                "Personal files, passwords, and private identifiers are scrubbed and will NEVER be collected.",
                "Sengoku Basara 4 Sumeragi — Crash Diagnostic",
                MB_YESNO | MB_ICONQUESTION
            )
            if res != IDYES:
                try:
                    os.remove(flag_file)
                except Exception:
                    pass
                return
        except Exception:
            pass

    # Package crash dump and scrubbed logs
    try:
        crashes_dir = os.path.join("user", "crashes")
        pending_dir = os.path.join(crashes_dir, "pending")
        os.makedirs(pending_dir, exist_ok=True)

        # Find newest .dmp
        dmp_files = sorted(glob.glob(os.path.join(crashes_dir, "*.dmp")), key=os.path.getmtime, reverse=True)
        newest_dmp = dmp_files[0] if dmp_files else None

        # Find newest log (last_run.log or basara.log)
        log_cand = [
            os.path.join(crashes_dir, "last_run.log"),
            os.path.join("user", "logs", "basara.log")
        ]
        log_content = ""
        for lp in log_cand:
            if os.path.isfile(lp):
                try:
                    with open(lp, "r", encoding="utf-8", errors="replace") as lf:
                        log_content = lf.read()
                    break
                except Exception:
                    pass

        scrubbed_log = scrub_pii(log_content)

        ts = time.strftime("%Y%m%d_%H%M%S")
        pkg_path = os.path.join(pending_dir, f"crash_package_{ts}.zip")

        manifest = {
            "version": "v2.1.0",
            "timestamp": ts,
            "platform": sys.platform,
            "has_minidump": bool(newest_dmp)
        }

        with zipfile.ZipFile(pkg_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            if newest_dmp and os.path.isfile(newest_dmp):
                zf.write(newest_dmp, arcname=os.path.basename(newest_dmp))
            if scrubbed_log:
                zf.writestr("basara_anonymized.log", scrubbed_log)
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        upload_crash_package(pkg_path, endpoint)

    except Exception as e:
        print(f"[CRASH_REPORTER] Packaging exception: {e}")
    finally:
        try:
            if os.path.isfile(flag_file):
                os.remove(flag_file)
        except Exception:
            pass


if __name__ == "__main__":
    if "--test-crash" in sys.argv:
        sim_log = find_latest_log()
        dummy_code = -1073741819  # 0xC0000005 (Access Violation)
        is_crash, reason, matched = scan_log_for_crash(dummy_code, sim_log)
        res = generate_crash_report(
            dummy_code, sim_log, "TEST SIMULATION (--test-crash): " + reason, matched
        )
        if len(res) == 4:
            report_path, log_copy, content, bundle_path = res
        else:
            report_path, log_copy, content = res[:3]
            bundle_path = None
        print(f"[TEST-CRASH] Generated report: {report_path}")
        if bundle_path:
            print(f"[TEST-CRASH] Generated crash bundle ZIP: {bundle_path}")
        dialog = CrashDialog(report_path, base_path("crashes"), content, dummy_code, reason, bundle_path=bundle_path)
        dialog.show()
        sys.exit(0)
    elif "--prepare-only" in sys.argv or "-p" in sys.argv:
        sys.exit(run_headless_prepare())
    else:
        # 1. Check runtime dependencies (Vulkan, VC++ Redist, Windows Version, Storage)
        dep_status = check_dependencies(show_dialogs=True)
        # 2. Check crash consent dialog (Update 2 telemetry)
        check_pending_crash_consent()
        # 3 & 4. Launch Desktop UI and trigger First-Run Wizard if clean installation
        app = BasaraLauncher(dep_status=dep_status)
        app.mainloop()
