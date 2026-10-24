#!/usr/bin/env python3
"""
Sengoku Basara 4 Sumeragi - PC Edition Graphical Launcher
Native PC Port Launcher & Configuration Utility
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# --- Theme Configuration ---
COLOR_BG = "#121214"
COLOR_CARD = "#1c1c22"
COLOR_CARD_BORDER = "#2d2d38"
COLOR_PRIMARY = "#dc2626"       # Crimson Red
COLOR_PRIMARY_HOVER = "#ef4444"
COLOR_ACCENT = "#f59e0b"        # Gold
COLOR_TEXT = "#f3f4f6"
COLOR_MUTED = "#9ca3af"
COLOR_SUCCESS = "#22c55e"
COLOR_ERROR = "#ef4444"

FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_SUBTITLE = ("Segoe UI", 9, "bold")
FONT_SECTION = ("Segoe UI", 11, "bold")
FONT_LABEL = ("Segoe UI", 10)
FONT_BUTTON = ("Segoe UI", 13, "bold")
FONT_SMALL = ("Segoe UI", 8)

INI_FILE = "basara.ini"
FALLBACK_INI = "bbport.ini"


def read_ini_settings():
    settings = {
        "output_res": "1920x1080",
        "render_res": "1080",
        "fullscreen": "1",
        "fps_limit": "144",
        "skip_intro": "0",
        "show_fps": "1",
    }
    ini_path = INI_FILE if os.path.exists(INI_FILE) else (FALLBACK_INI if os.path.exists(FALLBACK_INI) else None)
    if ini_path:
        try:
            with open(ini_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    settings[k.strip()] = v.strip()
        except Exception:
            pass
    return settings


def save_ini_settings(new_values):
    target = INI_FILE
    lines = []
    keys_written = set()

    if os.path.exists(target):
        try:
            with open(target, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    if not lines:
        lines = ["# Sengoku Basara 4 Sumeragi PC settings (in-game menu: Insert / L3+R3)\n"]

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in new_values:
                new_lines.append(f"{k}={new_values[k]}\n")
                keys_written.add(k)
                continue
        new_lines.append(line)

    for k, v in new_values.items():
        if k not in keys_written:
            new_lines.append(f"{k}={v}\n")

    try:
        with open(target, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"Warning: could not save {target}: {e}")


def check_prerequisites():
    missing = []

    # Check executable
    exe = "basara_pc.exe"
    if not os.path.isfile(exe):
        missing.append("basara_pc.exe")

    # Check boot binary
    boot_bin = None
    for candidate in ["boot-linked.bin", os.path.join("out", "boot-linked.bin")]:
        if os.path.isfile(candidate):
            boot_bin = candidate
            break
    if not boot_bin:
        missing.append("boot-linked.bin (in root or out/)")

    # Check game directory
    app0 = None
    for candidate in [os.path.join("extracted_game", "app0"), "app0"]:
        if os.path.isdir(candidate):
            app0 = candidate
            break
    if not app0:
        missing.append("game data folder (extracted_game/app0 or app0)")

    return missing, exe, boot_bin, app0


class BasaraLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sengoku Basara 4 Sumeragi — PC Edition")
        self.geometry("640x550")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG)

        # Set Window Icon if available
        icon_path = os.path.join("packaging", "windows", "icons", "basara4.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.center_window()
        self.init_state()
        self.build_ui()
        self.refresh_status()

    def center_window(self):
        self.update_idletasks()
        w = 640
        h = 550
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def init_state(self):
        ini = read_ini_settings()

        # Resolution map
        self.res_var = tk.StringVar(value=ini.get("output_res", "1920x1080"))
        self.fullscreen_var = tk.BooleanVar(value=ini.get("fullscreen", "1") == "1")
        self.fps_var = tk.StringVar(value=ini.get("fps_limit", "144"))
        self.skip_intro_var = tk.BooleanVar(value=ini.get("skip_intro", "0") == "1")
        self.show_fps_var = tk.BooleanVar(value=ini.get("show_fps", "1") == "1")

        self.game_process = None

    def build_ui(self):
        # --- Header Banner ---
        header_frame = tk.Frame(self, bg="#0d0d10", pady=14)
        header_frame.pack(fill="x")

        title_lbl = tk.Label(
            header_frame,
            text="戦国BASARA4 皇 — SENGOKU BASARA 4 SUMERAGI",
            font=FONT_TITLE,
            fg=COLOR_ACCENT,
            bg="#0d0d10"
        )
        title_lbl.pack()

        subtitle_lbl = tk.Label(
            header_frame,
            text="PC NATIVE PORT  •  VULKAN RENDERER  •  UPDATE 1",
            font=FONT_SUBTITLE,
            fg=COLOR_TEXT,
            bg="#0d0d10"
        )
        subtitle_lbl.pack(pady=(2, 0))

        # Thin gold separator
        gold_sep = tk.Frame(self, bg=COLOR_ACCENT, height=2)
        gold_sep.pack(fill="x")

        # --- Content Container ---
        content = tk.Frame(self, bg=COLOR_BG, padx=25, pady=15)
        content.pack(fill="both", expand=True)

        # --- Status Box ---
        self.status_card = tk.Frame(content, bg=COLOR_CARD, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER, padx=14, pady=10)
        self.status_card.pack(fill="x", pady=(0, 14))

        self.status_icon = tk.Label(self.status_card, text="●", font=("Segoe UI", 12), fg=COLOR_SUCCESS, bg=COLOR_CARD)
        self.status_icon.pack(side="left", padx=(0, 8))

        self.status_lbl = tk.Label(self.status_card, text="Checking game files...", font=FONT_LABEL, fg=COLOR_TEXT, bg=COLOR_CARD, justify="left", wraplength=520)
        self.status_lbl.pack(side="left")

        # --- Settings Card ---
        settings_card = tk.Frame(content, bg=COLOR_CARD, highlightthickness=1, highlightbackground=COLOR_CARD_BORDER, padx=18, pady=14)
        settings_card.pack(fill="x", pady=(0, 16))

        sec_title = tk.Label(settings_card, text="GRAPHICS & GAMEPLAY PREFERENCES", font=FONT_SECTION, fg=COLOR_ACCENT, bg=COLOR_CARD)
        sec_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        # Resolution
        res_lbl = tk.Label(settings_card, text="Display Resolution:", font=FONT_LABEL, fg=COLOR_TEXT, bg=COLOR_CARD)
        res_lbl.grid(row=1, column=0, sticky="w", pady=6)

        res_combo = ttk.Combobox(
            settings_card,
            textvariable=self.res_var,
            values=["1280x720", "1920x1080", "2560x1440", "3840x2160"],
            state="readonly",
            width=18
        )
        res_combo.grid(row=1, column=1, sticky="e", pady=6)

        # FPS Limit
        fps_lbl = tk.Label(settings_card, text="Target Framerate:", font=FONT_LABEL, fg=COLOR_TEXT, bg=COLOR_CARD)
        fps_lbl.grid(row=2, column=0, sticky="w", pady=6)

        fps_combo = ttk.Combobox(
            settings_card,
            textvariable=self.fps_var,
            values=["60", "120", "144", "0"],
            state="readonly",
            width=18
        )
        fps_combo.grid(row=2, column=1, sticky="e", pady=6)

        # Toggles Row 1
        fs_chk = tk.Checkbutton(
            settings_card,
            text="Fullscreen Mode",
            variable=self.fullscreen_var,
            font=FONT_LABEL,
            fg=COLOR_TEXT,
            bg=COLOR_CARD,
            selectcolor="#2a2a35",
            activebackground=COLOR_CARD,
            activeforeground=COLOR_TEXT
        )
        fs_chk.grid(row=3, column=0, sticky="w", pady=(8, 4))

        intro_chk = tk.Checkbutton(
            settings_card,
            text="Skip Opening Movie",
            variable=self.skip_intro_var,
            font=FONT_LABEL,
            fg=COLOR_TEXT,
            bg=COLOR_CARD,
            selectcolor="#2a2a35",
            activebackground=COLOR_CARD,
            activeforeground=COLOR_TEXT
        )
        intro_chk.grid(row=3, column=1, sticky="w", pady=(8, 4))

        # Toggles Row 2
        hud_chk = tk.Checkbutton(
            settings_card,
            text="Show In-Game FPS Counter",
            variable=self.show_fps_var,
            font=FONT_LABEL,
            fg=COLOR_TEXT,
            bg=COLOR_CARD,
            selectcolor="#2a2a35",
            activebackground=COLOR_CARD,
            activeforeground=COLOR_TEXT
        )
        hud_chk.grid(row=4, column=0, sticky="w", pady=(4, 4))

        overlay_hint = tk.Label(
            settings_card,
            text="(In-game menu shortcut: Insert or L3+R3)",
            font=FONT_SMALL,
            fg=COLOR_MUTED,
            bg=COLOR_CARD
        )
        overlay_hint.grid(row=4, column=1, sticky="w", pady=(4, 4))

        # --- Launch Button ---
        self.btn_launch = tk.Button(
            content,
            text="⚔   LAUNCH GAME   ⚔",
            font=FONT_BUTTON,
            fg="#ffffff",
            bg=COLOR_PRIMARY,
            activebackground=COLOR_PRIMARY_HOVER,
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=15,
            pady=12,
            command=self.launch_game
        )
        self.btn_launch.pack(fill="x", pady=(4, 8))

        # Footer note
        footer_lbl = tk.Label(
            content,
            text="Settings are automatically synchronized to basara.ini before launching.",
            font=FONT_SMALL,
            fg=COLOR_MUTED,
            bg=COLOR_BG
        )
        footer_lbl.pack()

    def refresh_status(self):
        missing, exe, boot_bin, app0 = check_prerequisites()
        if missing:
            self.status_icon.config(fg=COLOR_ERROR)
            self.status_lbl.config(
                text="Game files missing:\n• " + "\n• ".join(missing),
                fg=COLOR_ERROR
            )
            self.btn_launch.config(state="disabled", bg="#374151", cursor="arrow")
        else:
            self.status_icon.config(fg=COLOR_SUCCESS)
            self.status_lbl.config(
                text=f"All components verified! ({exe} + {boot_bin} + {app0})",
                fg=COLOR_SUCCESS
            )
            self.btn_launch.config(state="normal", bg=COLOR_PRIMARY, cursor="hand2")

    def launch_game(self):
        missing, exe, boot_bin, app0 = check_prerequisites()
        if missing:
            messagebox.showerror("Cannot Launch", "Missing required components:\n" + "\n".join(missing))
            return

        # 1. Update basara.ini
        new_settings = {
            "output_res": self.res_var.get(),
            "fullscreen": "1" if self.fullscreen_var.get() else "0",
            "fps_limit": self.fps_var.get(),
            "skip_intro": "1" if self.skip_intro_var.get() else "0",
            "show_fps": "1" if self.show_fps_var.get() else "0"
        }
        res_height = self.res_var.get().split("x")[-1] if "x" in self.res_var.get() else "1080"
        new_settings["render_res"] = res_height
        save_ini_settings(new_settings)

        # 2. Build argument command
        cmd = [os.path.abspath(exe), os.path.abspath(boot_bin)]

        import_names = os.path.join("out", "import_names.txt")
        if os.path.isfile(import_names):
            cmd.extend(["--import-names", os.path.abspath(import_names)])

        content_bin = os.path.join("out", "content.bin")
        if os.path.isfile(content_bin):
            cmd.extend(["--content-profile", os.path.abspath(content_bin)])

        cmd.extend(["--app0", os.path.abspath(app0), "--user", "user"])

        # 3. Launch process and hide launcher
        self.withdraw()

        def run_thread():
            try:
                proc = subprocess.Popen(cmd, cwd=os.getcwd())
                proc.wait()
            except Exception as ex:
                print(f"Error launching game: {ex}")
            finally:
                self.after(200, self.on_game_exit)

        threading.Thread(target=run_thread, daemon=True).start()

    def on_game_exit(self):
        self.deiconify()
        self.refresh_status()


if __name__ == "__main__":
    app = BasaraLauncher()
    app.mainloop()
