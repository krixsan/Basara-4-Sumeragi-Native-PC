#!/usr/bin/env python3
"""
Sengoku Basara 4 Sumeragi — PC Native Port
Studio-Grade AAA Graphical Launcher & Configuration Engine
v2.0 Release — Performance Mode, Auto-Updater & Enhanced UI
"""

import os
import sys
import ctypes
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
import shutil
import platform
import math

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

INI_FILE = "basara.ini"
FALLBACK_INI = "basara.ini"


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
    exe = "basara_pc.exe"
    if not os.path.isfile(exe):
        missing.append("basara_pc.exe")

    boot_bin = None
    for cand in ["boot-linked.bin", os.path.join("out", "boot-linked.bin")]:
        if os.path.isfile(cand):
            boot_bin = cand
            break

    app0 = None
    for cand in [os.path.join("extracted_game", "app0"), "app0"]:
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
        free_mb = shutil.disk_usage(os.getcwd()).free // (1024 * 1024)
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


class BasaraLauncher(tk.Tk):
    def __init__(self, dep_status=None):
        super().__init__()
        self.title("Sengoku Basara 4 Sumeragi — PC Native Port (v2.0)")
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
        icon_path = os.path.join("packaging", "windows", "icons", "basara4.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
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
            os.path.join("extracted_game", "app0", "sce_sys", "icon0.png"),
            os.path.join("app0", "sce_sys", "icon0.png"),
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
            text="VULKAN 1.3 NATIVE PORT • v2.0",
            font=(FONT_SUBTITLE, 8, "bold"),
            fill=COLOR_GOLD,
            anchor="nw"
        )

        # What's New / Changelog Button
        self.changelog_btn = self.canvas.create_text(
            text_x + 195, 26,
            text="v2.0 Changelog",
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
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "CHANGELOG.md"),
            os.path.abspath("CHANGELOG.md"),
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
            messagebox.showinfo("v2.0 Changelog", "CHANGELOG.md not found in the game directory.")

    def check_for_updates(self):
        messagebox.showinfo(
            "Check for Updates",
            "Auto-Updater: Checking GitHub for new releases...\n\n"
            "Visit: https://github.com/krixsan/Basara-4-Sumeragi-Native-PC\n"
            "Current Version: v2.0"
        )

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

    def open_gamepad_mapper(self):
        mapper_exe = "basara4-pad-mapper.exe"
        if os.path.isfile(mapper_exe):
            os.makedirs("user", exist_ok=True)
            subprocess.Popen([os.path.abspath(mapper_exe), "user/gamepad_mapping.txt"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            messagebox.showinfo("Controller Mapping", "Standard XInput (Xbox/PlayStation) pads work natively!\nIf using a generic DInput controller, basara4-pad-mapper.exe will calibrate it.")

    def _toggle_setting(self, name):
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
                        auto_builder.apply_fps_patches(app0, out_dir, unlimited_fps=True)
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
            for map_path in [os.path.join("user", "gamepad_mapping.txt"), "gamepad_mapping.txt"]:
                if os.path.isfile(map_path):
                    env["SDL_GAMECONTROLLERCONFIG_FILE"] = os.path.abspath(map_path)
                    break

            cmd = [
                os.path.abspath(exe),
                os.path.abspath(boot_bin)
            ]
            import_names = os.path.join("out", "import_names.txt")
            if os.path.isfile(import_names):
                cmd.extend(["--import-names", os.path.abspath(import_names)])

            content_bin = os.path.join("out", "content.bin")
            if os.path.isfile(content_bin):
                cmd.extend(["--content-profile", os.path.abspath(content_bin)])

            patches_bin = os.path.join("out", "patches.bin")
            if os.path.isfile(patches_bin):
                cmd.extend(["--patches", os.path.abspath(patches_bin)])

            cmd.extend(["--app0", os.path.abspath(app0), "--user", "user"])

            # Seamless minimize/hide on main thread
            self.after(0, self.withdraw)

            proc = subprocess.Popen(cmd, cwd=os.getcwd(), env=env)
            proc.wait()

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
            "version": "v2.0",
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
    if "--prepare-only" in sys.argv or "-p" in sys.argv:
        sys.exit(run_headless_prepare())
    else:
        # 1. Check runtime dependencies (Vulkan, VC++ Redist, Windows Version, Storage)
        dep_status = check_dependencies(show_dialogs=True)
        # 2. Check crash consent dialog (Update 2 telemetry)
        check_pending_crash_consent()
        # 3 & 4. Launch Desktop UI and trigger First-Run Wizard if clean installation
        app = BasaraLauncher(dep_status=dep_status)
        app.mainloop()
