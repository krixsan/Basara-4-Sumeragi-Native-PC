#!/usr/bin/env python3
"""
Sengoku Basara 4 Sumeragi — PC Native Port
High-End AAA Style Graphical Launcher & Configuration Engine

Ported & Customized by krixsan
"""

import os
import sys
import ctypes
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# --- Enable Windows High-DPI Awareness ---
try:
    if sys.platform == "win32":
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- Theme Palette (Obsidian, Samurai Crimson & Emperor Gold) ---
THEME_BG = "#090a0f"           # Deep obsidian void
THEME_CARD = "#12141c"         # Dark graphite card
THEME_CARD_HOVER = "#171924"
THEME_BORDER = "#222638"       # Subtle structural line
THEME_CRIMSON = "#d90429"      # Samurai Blood Red
THEME_CRIMSON_HOVER = "#ef233c"# Vibrant Fire Red
THEME_CRIMSON_DARK = "#7a0018"
THEME_GOLD = "#d4af37"         # Authentic Imperial Gold
THEME_GOLD_BRIGHT = "#f6c445"
THEME_GOLD_MUTED = "#997b28"
THEME_TEXT_WHITE = "#f8fafc"   # Pure crisp typography
THEME_TEXT_MUTED = "#8e95a5"
THEME_SUCCESS = "#10b981"      # Emerald readiness
THEME_ERROR = "#f43f5e"        # Rose warning

FONT_FAMILY = "Segoe UI"
FONT_JAPANESE = "MS Gothic" if sys.platform == "win32" else "Segoe UI"

INI_FILE = "basara.ini"
FALLBACK_INI = "bbport.ini"


def read_ini():
    settings = {
        "output_res": "1920x1080",
        "render_res": "1080",
        "fullscreen": "1",
        "fps_limit": "144",
        "skip_intro": "0",
        "show_fps": "1",
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
            "# Ported & Customized by krixsan\n",
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


def verify_game_installation():
    missing = []
    exe = "basara_pc.exe"
    if not os.path.isfile(exe):
        missing.append("basara_pc.exe (Game Runtime)")

    boot_bin = None
    for cand in ["boot-linked.bin", os.path.join("out", "boot-linked.bin")]:
        if os.path.isfile(cand):
            boot_bin = cand
            break
    if not boot_bin:
        missing.append("boot-linked.bin (PS4 Boot Binary in root or out/)")

    app0 = None
    for cand in [os.path.join("extracted_game", "app0"), "app0"]:
        if os.path.isdir(cand):
            app0 = cand
            break
    if not app0:
        missing.append("Game Assets folder ('extracted_game/app0' or 'app0')")

    return missing, exe, boot_bin, app0


class ModernSwitch(tk.Canvas):
    """Sleek minimalist iOS/AAA game style toggle switch."""
    def __init__(self, parent, variable, text="", command=None, width=44, height=22, bg=THEME_CARD):
        super().__init__(parent, width=width + 120, height=height + 4, bg=bg, highlightthickness=0, cursor="hand2")
        self.var = variable
        self.label_text = text
        self.cmd = command
        self.sw_w = width
        self.sw_h = height
        self.bg_color = bg

        self.bind("<Button-1>", self.toggle)
        self.var.trace_add("write", lambda *args: self.redraw())
        self.redraw()

    def toggle(self, event=None):
        self.var.set(not self.var.get())
        if self.cmd:
            self.cmd()

    def redraw(self):
        self.delete("all")
        val = self.var.get()
        w, h = self.sw_w, self.sw_h

        # Draw rounded track
        track_color = THEME_CRIMSON if val else "#2a2e40"
        border_color = THEME_GOLD if val else "#383d54"
        r = h // 2

        self.create_arc((0, 2, h, h + 2), start=90, extent=180, fill=track_color, outline=border_color)
        self.create_arc((w - h, 2, w, h + 2), start=270, extent=180, fill=track_color, outline=border_color)
        self.create_rectangle((r, 2, w - r, h + 2), fill=track_color, outline=track_color)
        self.create_line((r, 2, w - r, 2), fill=border_color)
        self.create_line((r, h + 2, w - r, h + 2), fill=border_color)

        # Draw thumb knob
        knob_x = (w - r - 2) if val else (r + 2)
        knob_color = "#ffffff" if val else "#9ca3af"
        self.create_oval(
            knob_x - r + 3, 5,
            knob_x + r - 3, h - 1,
            fill=knob_color, outline=""
        )

        # Draw text label
        self.create_text(
            w + 12, h // 2 + 2,
            text=self.label_text,
            fill=THEME_TEXT_WHITE if val else THEME_TEXT_MUTED,
            font=(FONT_FAMILY, 9, "bold" if val else "normal"),
            anchor="w"
        )


class BasaraAaaLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sengoku Basara 4 Sumeragi — PC Native Port")
        self.geometry("700x610")
        self.resizable(False, False)
        self.configure(bg=THEME_BG)

        # Apply icon
        icon_path = os.path.join("packaging", "windows", "icons", "basara4.ico")
        if os.path.isfile(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        self.center_on_screen()
        self.load_configuration()
        self.build_gui()
        self.evaluate_system_readiness()

    def center_on_screen(self):
        self.update_idletasks()
        w, h = 700, 610
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    def load_configuration(self):
        ini = read_ini()
        self.res_var = tk.StringVar(value=ini.get("output_res", "1920x1080"))
        self.fullscreen_var = tk.BooleanVar(value=ini.get("fullscreen", "1") == "1")
        self.fps_var = tk.StringVar(value=ini.get("fps_limit", "144"))
        self.skip_intro_var = tk.BooleanVar(value=ini.get("skip_intro", "0") == "1")
        self.show_fps_var = tk.BooleanVar(value=ini.get("show_fps", "1") == "1")

    def build_gui(self):
        # =====================================================================
        # TOP HEADER: BRANDING & KRIXSAN CREDITS
        # =====================================================================
        header = tk.Frame(self, bg="#07070a", padx=30, pady=16)
        header.pack(fill="x")

        # Top Bar: Version tag (Left) & Creator signature (Right)
        top_meta = tk.Frame(header, bg="#07070a")
        top_meta.pack(fill="x", pady=(0, 4))

        tag_badge = tk.Label(
            top_meta,
            text="UPDATE 1  •  VULKAN 1.3 NATIVE",
            font=(FONT_FAMILY, 8, "bold"),
            fg="#71717a",
            bg="#18181b",
            padx=8,
            pady=2
        )
        tag_badge.pack(side="left")

        # Ported & Customized by krixsan (Requested Mandatory Signature)
        credit_lbl = tk.Label(
            top_meta,
            text="✦  Ported & Customized by krixsan  ✦",
            font=(FONT_FAMILY, 9, "bold italic"),
            fg=THEME_GOLD,
            bg="#07070a"
        )
        credit_lbl.pack(side="right")

        # Japanese Traditional Logo Mark
        jp_title = tk.Label(
            header,
            text="戦 国 B A S A R A 4   皇",
            font=(FONT_JAPANESE, 10, "bold"),
            fg=THEME_CRIMSON,
            bg="#07070a"
        )
        jp_title.pack(anchor="w", pady=(6, 0))

        # Main Majestic Title
        main_title = tk.Label(
            header,
            text="SENGOKU BASARA 4 SUMERAGI",
            font=(FONT_FAMILY, 19, "bold"),
            fg=THEME_TEXT_WHITE,
            bg="#07070a",
            letter_spacing=1 if sys.platform != "win32" else 0
        )
        main_title.pack(anchor="w")

        sub_desc = tk.Label(
            header,
            text="PC DEFINITIVE EDITION  —  HIGH PERFORMANCE RECONSTRUCTION",
            font=(FONT_FAMILY, 8, "bold"),
            fg=THEME_GOLD_MUTED,
            bg="#07070a"
        )
        sub_desc.pack(anchor="w", pady=(1, 0))

        # Dual-tone Samurai Blade Divider
        divider = tk.Canvas(self, height=3, bg=THEME_BG, highlightthickness=0)
        divider.pack(fill="x")
        divider.create_line(0, 1, 350, 1, fill=THEME_CRIMSON, width=2)
        divider.create_line(350, 1, 700, 1, fill=THEME_GOLD, width=2)

        # =====================================================================
        # MAIN BODY CONTAINER
        # =====================================================================
        body = tk.Frame(self, bg=THEME_BG, padx=28, pady=16)
        body.pack(fill="both", expand=True)

        # ---------------------------------------------------------------------
        # 1. System Readiness Card
        # ---------------------------------------------------------------------
        self.status_card = tk.Frame(body, bg=THEME_CARD, highlightthickness=1, highlightbackground=THEME_BORDER, padx=16, pady=10)
        self.status_card.pack(fill="x", pady=(0, 14))

        self.status_dot = tk.Label(self.status_card, text="●", font=(FONT_FAMILY, 11), fg=THEME_SUCCESS, bg=THEME_CARD)
        self.status_dot.pack(side="left", padx=(0, 10))

        self.status_text = tk.Label(
            self.status_card,
            text="Checking game environment...",
            font=(FONT_FAMILY, 9),
            fg=THEME_TEXT_WHITE,
            bg=THEME_CARD,
            justify="left"
        )
        self.status_text.pack(side="left")

        # ---------------------------------------------------------------------
        # 2. Settings Grid (Display & Gameplay Cards)
        # ---------------------------------------------------------------------
        settings_frame = tk.Frame(body, bg=THEME_BG)
        settings_frame.pack(fill="x", pady=(0, 14))

        # Card A: Video & Graphics
        card_a = tk.Frame(settings_frame, bg=THEME_CARD, highlightthickness=1, highlightbackground=THEME_BORDER, padx=16, pady=14)
        card_a.pack(side="left", fill="both", expand=True, padx=(0, 8))

        sec_a_lbl = tk.Label(card_a, text="DISPLAY & RESOLUTION", font=(FONT_FAMILY, 10, "bold"), fg=THEME_GOLD, bg=THEME_CARD)
        sec_a_lbl.pack(anchor="w", pady=(0, 10))

        # Resolution Dropdown
        res_row = tk.Frame(card_a, bg=THEME_CARD)
        res_row.pack(fill="x", pady=4)
        tk.Label(res_row, text="Target Display:", font=(FONT_FAMILY, 9), fg=THEME_TEXT_MUTED, bg=THEME_CARD).pack(side="left")

        # Styled combobox
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground="#1c1f2e",
            background="#252a3d",
            foreground="#f8fafc",
            arrowcolor=THEME_GOLD,
            bordercolor=THEME_BORDER,
            darkcolor="#1c1f2e",
            lightcolor="#1c1f2e"
        )

        res_cb = ttk.Combobox(
            res_row,
            textvariable=self.res_var,
            values=["1280x720", "1920x1080", "2560x1440", "3840x2160"],
            state="readonly",
            width=13,
            style="TCombobox"
        )
        res_cb.pack(side="right")

        # FPS Limit Dropdown
        fps_row = tk.Frame(card_a, bg=THEME_CARD)
        fps_row.pack(fill="x", pady=6)
        tk.Label(fps_row, text="Frame Pacing:", font=(FONT_FAMILY, 9), fg=THEME_TEXT_MUTED, bg=THEME_CARD).pack(side="left")

        fps_cb = ttk.Combobox(
            fps_row,
            textvariable=self.fps_var,
            values=["60", "120", "144", "0"],
            state="readonly",
            width=13,
            style="TCombobox"
        )
        fps_cb.pack(side="right")

        # Fullscreen Toggle Switch
        fs_switch = ModernSwitch(card_a, self.fullscreen_var, text="Fullscreen Display", bg=THEME_CARD)
        fs_switch.pack(anchor="w", pady=(8, 2))

        # Card B: Experience & Tweaks
        card_b = tk.Frame(settings_frame, bg=THEME_CARD, highlightthickness=1, highlightbackground=THEME_BORDER, padx=16, pady=14)
        card_b.pack(side="right", fill="both", expand=True, padx=(8, 0))

        sec_b_lbl = tk.Label(card_b, text="ENGINE & EXPERIENCE", font=(FONT_FAMILY, 10, "bold"), fg=THEME_GOLD, bg=THEME_CARD)
        sec_b_lbl.pack(anchor="w", pady=(0, 10))

        intro_switch = ModernSwitch(card_b, self.skip_intro_var, text="Fast Boot (Skip Movie)", bg=THEME_CARD)
        intro_switch.pack(anchor="w", pady=(4, 6))

        fps_switch = ModernSwitch(card_b, self.show_fps_var, text="On-Screen FPS Counter", bg=THEME_CARD)
        fps_switch.pack(anchor="w", pady=(4, 6))

        hint_box = tk.Frame(card_b, bg="#181a24", padx=8, pady=5)
        hint_box.pack(fill="x", pady=(10, 0))
        tk.Label(
            hint_box,
            text="In-Game Menu Shortcut: [Insert] or [L3 + R3]",
            font=(FONT_FAMILY, 8),
            fg=THEME_TEXT_MUTED,
            bg="#181a24"
        ).pack(anchor="w")

        # ---------------------------------------------------------------------
        # 3. Action Zone: Majestic Samurai Blade Launch Button
        # ---------------------------------------------------------------------
        self.btn_canvas = tk.Canvas(body, height=58, bg=THEME_BG, highlightthickness=0, cursor="hand2")
        self.btn_canvas.pack(fill="x", pady=(8, 12))

        self.btn_canvas.bind("<Enter>", self.on_btn_hover)
        self.btn_canvas.bind("<Leave>", self.on_btn_leave)
        self.btn_canvas.bind("<Button-1>", self.on_btn_click)

        self.is_ready = False
        self.draw_launch_button(hover=False)

        # ---------------------------------------------------------------------
        # 4. Footer Branding & Legal Note
        # ---------------------------------------------------------------------
        footer = tk.Frame(body, bg=THEME_BG)
        footer.pack(fill="x", side="bottom")

        legal_lbl = tk.Label(
            footer,
            text="CAPCOM CO., LTD. ALL RIGHTS RESERVED  •  FAN EMULATION & PRESERVATION PROJECT",
            font=(FONT_FAMILY, 7),
            fg="#52525b",
            bg=THEME_BG
        )
        legal_lbl.pack(side="left")

        sign_lbl = tk.Label(
            footer,
            text="ENGINEERED BY KRIXSAN",
            font=(FONT_FAMILY, 7, "bold"),
            fg=THEME_GOLD_MUTED,
            bg=THEME_BG
        )
        sign_lbl.pack(side="right")

    def draw_launch_button(self, hover=False):
        self.btn_canvas.delete("all")
        w = 644
        h = 56
        r = 12

        if not self.is_ready:
            fill_color = "#1f222e"
            border_color = "#2d3244"
            text_color = "#555b6e"
            btn_text = "🔒   GAME ASSETS OR BINARY MISSING"
        else:
            fill_color = THEME_CRIMSON_HOVER if hover else THEME_CRIMSON
            border_color = THEME_GOLD if hover else THEME_CRIMSON_DARK
            text_color = "#ffffff"
            btn_text = "⚔     LAUNCH SENGOKU BASARA 4     ⚔"

        # Rounded button polygon
        points = [
            r, 2,  w - r, 2,
            w - 2, 2,  w - 2, r,
            w - 2, h - r,  w - 2, h - 2,
            w - r, h - 2,  r, h - 2,
            2, h - 2,  2, h - r,
            2, r,  2, 2
        ]
        self.btn_canvas.create_polygon(points, fill=fill_color, outline=border_color, width=2, smooth=True)

        # Accent Gold Corner Notches for Samurai AAA Aesthetic
        if self.is_ready:
            # Top-left & Bottom-right gold accents
            self.btn_canvas.create_line(14, 8, 30, 8, fill=THEME_GOLD, width=2)
            self.btn_canvas.create_line(14, 8, 14, 20, fill=THEME_GOLD, width=2)
            self.btn_canvas.create_line(w - 14, h - 8, w - 30, h - 8, fill=THEME_GOLD, width=2)
            self.btn_canvas.create_line(w - 14, h - 8, w - 14, h - 20, fill=THEME_GOLD, width=2)

        self.btn_canvas.create_text(
            w // 2, h // 2,
            text=btn_text,
            fill=text_color,
            font=(FONT_FAMILY, 12, "bold")
        )

    def on_btn_hover(self, event):
        if self.is_ready:
            self.draw_launch_button(hover=True)

    def on_btn_leave(self, event):
        self.draw_launch_button(hover=False)

    def on_btn_click(self, event):
        if self.is_ready:
            self.launch_game()

    def evaluate_system_readiness(self):
        missing, exe, boot_bin, app0 = verify_game_installation()
        if missing:
            self.is_ready = False
            self.status_dot.config(fg=THEME_ERROR)
            detail = "  •  ".join(missing)
            self.status_text.config(
                text=f"Setup Required: {detail}",
                fg=THEME_ERROR
            )
            self.status_card.config(highlightbackground=THEME_ERROR)
            self.btn_canvas.config(cursor="arrow")
        else:
            self.is_ready = True
            self.status_dot.config(fg=THEME_SUCCESS)
            self.status_text.config(
                text="System Verified  —  Ready to engage in battlefield combat!",
                fg=THEME_SUCCESS
            )
            self.status_card.config(highlightbackground=THEME_BORDER)
            self.btn_canvas.config(cursor="hand2")

        self.draw_launch_button(hover=False)

    def launch_game(self):
        missing, exe, boot_bin, app0 = verify_game_installation()
        if missing:
            messagebox.showerror("Engine Warning", "Cannot launch. Missing components:\n\n" + "\n".join(missing))
            return

        # 1. Update basara.ini
        res_str = self.res_var.get()
        height = res_str.split("x")[-1] if "x" in res_str else "1080"
        cfg_payload = {
            "output_res": res_str,
            "render_res": height,
            "fullscreen": "1" if self.fullscreen_var.get() else "0",
            "fps_limit": self.fps_var.get(),
            "skip_intro": "1" if self.skip_intro_var.get() else "0",
            "show_fps": "1" if self.show_fps_var.get() else "0",
        }
        write_ini(cfg_payload)

        # 2. Build full launch command
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

        cmd.extend(["--app0", os.path.abspath(app0), "--user", "user"])

        # 3. Minimize / Hide Launcher and Run
        self.withdraw()

        def process_watcher():
            try:
                proc = subprocess.Popen(cmd, cwd=os.getcwd())
                proc.wait()
            except Exception as err:
                print(f"Execution error: {err}")
            finally:
                self.after(300, self.on_game_finish)

        threading.Thread(target=process_watcher, daemon=True).start()

    def on_game_finish(self):
        self.deiconify()
        self.evaluate_system_readiness()


if __name__ == "__main__":
    app = BasaraAaaLauncher()
    app.mainloop()
