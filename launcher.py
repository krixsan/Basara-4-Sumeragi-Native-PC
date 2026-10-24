#!/usr/bin/env python3
"""
Sengoku Basara 4 Sumeragi — PC Native Port
AAA Cinematic Graphical Launcher & Configuration Engine

Ported & Customized by krixsan
"""

import os
import sys
import ctypes
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# Try importing PIL for high-fidelity background image processing
try:
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Enable Windows High-DPI Awareness
try:
    if sys.platform == "win32":
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- Theme Configuration ---
WIDTH = 820
HEIGHT = 600

THEME_BG = "#08090d"
THEME_CARD = "#0f1118"
THEME_CARD_BORDER = "#232838"
THEME_CRIMSON = "#d90429"
THEME_CRIMSON_HOVER = "#ef233c"
THEME_CRIMSON_DARK = "#660014"
THEME_GOLD = "#d4af37"
THEME_GOLD_BRIGHT = "#f6c445"
THEME_GOLD_MUTED = "#91762c"
THEME_TEXT_WHITE = "#ffffff"
THEME_TEXT_MUTED = "#94a3b8"
THEME_SUCCESS = "#10b981"
THEME_ERROR = "#f43f5e"

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
    """Sleek minimalist toggle switch."""
    def __init__(self, parent, variable, text="", command=None, width=42, height=20, bg=THEME_CARD):
        super().__init__(parent, width=width + 150, height=height + 4, bg=bg, highlightthickness=0, cursor="hand2")
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

        track_color = THEME_CRIMSON if val else "#242838"
        border_color = THEME_GOLD if val else "#383f56"
        r = h // 2

        self.create_arc((0, 2, h, h + 2), start=90, extent=180, fill=track_color, outline=border_color)
        self.create_arc((w - h, 2, w, h + 2), start=270, extent=180, fill=track_color, outline=border_color)
        self.create_rectangle((r, 2, w - r, h + 2), fill=track_color, outline=track_color)
        self.create_line((r, 2, w - r, 2), fill=border_color)
        self.create_line((r, h + 2, w - r, h + 2), fill=border_color)

        knob_x = (w - r - 2) if val else (r + 2)
        knob_color = "#ffffff" if val else "#9ca3af"
        self.create_oval(
            knob_x - r + 3, 5,
            knob_x + r - 3, h - 1,
            fill=knob_color, outline=""
        )

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
        self.geometry(f"{WIDTH}x{HEIGHT}")
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
        self.prepare_background()
        self.build_gui()
        self.evaluate_system_readiness()

    def center_on_screen(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{WIDTH}x{HEIGHT}+{(sw - WIDTH)//2}+{(sh - HEIGHT)//2}")

    def load_configuration(self):
        ini = read_ini()
        self.res_var = tk.StringVar(value=ini.get("output_res", "1920x1080"))
        self.fullscreen_var = tk.BooleanVar(value=ini.get("fullscreen", "1") == "1")
        self.fps_var = tk.StringVar(value=ini.get("fps_limit", "144"))
        self.skip_intro_var = tk.BooleanVar(value=ini.get("skip_intro", "0") == "1")
        self.show_fps_var = tk.BooleanVar(value=ini.get("show_fps", "1") == "1")
        self.is_ready = False

    def prepare_background(self):
        self.bg_photo = None
        if not HAS_PIL:
            return

        candidates = [
            os.path.join("extracted_game", "app0", "sce_sys", "pic1.png"),
            os.path.join("extracted_game", "app0", "sce_sys", "pic0.png"),
            os.path.join("app0", "sce_sys", "pic1.png"),
            os.path.join("app0", "sce_sys", "pic0.png"),
        ]

        found_path = None
        for p in candidates:
            if os.path.isfile(p):
                found_path = p
                break

        try:
            if found_path:
                img = Image.open(found_path).convert("RGBA")
                # Scale and center crop to fit WIDTH x HEIGHT
                target_ratio = WIDTH / HEIGHT
                img_ratio = img.width / img.height
                if img_ratio > target_ratio:
                    new_w = int(img.height * target_ratio)
                    left = (img.width - new_w) // 2
                    img = img.crop((left, 0, left + new_w, img.height))
                else:
                    new_h = int(img.width / target_ratio)
                    top = (img.height - new_h) // 2
                    img = img.crop((0, top, img.width, top + new_h))
                img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            else:
                # Fallback samurai dark aesthetic gradient
                img = Image.new("RGBA", (WIDTH, HEIGHT), (12, 14, 20, 255))
                draw = ImageDraw.Draw(img)
                for y in range(HEIGHT):
                    r = int(18 + (35 - 18) * (1.0 - y / HEIGHT))
                    g = int(8 + (12 - 8) * (1.0 - y / HEIGHT))
                    b = int(14 + (24 - 14) * (y / HEIGHT))
                    draw.line([(0, y), (WIDTH, y)], fill=(r, g, b, 255))

            # Composite dark vignette overlay so UI controls are perfectly legible
            overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            for y in range(HEIGHT):
                # Darker top header, semi-transparent artwork mid, darker bottom controls
                if y < 130:
                    alpha = int(150 + (130 - y) * 0.45)
                elif y < 270:
                    alpha = 115
                else:
                    alpha = int(115 + (y - 270) * 0.45)
                alpha = min(235, max(100, alpha))
                draw.line([(0, y), (WIDTH, y)], fill=(6, 7, 12, alpha))

            final_img = Image.alpha_composite(img, overlay)
            self.bg_photo = ImageTk.PhotoImage(final_img)
        except Exception as e:
            print(f"Background image generation notice: {e}")
            self.bg_photo = None

    def build_gui(self):
        # Master Canvas for Background
        self.canvas = tk.Canvas(self, width=WIDTH, height=HEIGHT, bg=THEME_BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        if self.bg_photo:
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw")

        # =====================================================================
        # HEADER SECTION (TITLES, BADGES, AND KRIXSAN WATERMARK)
        # =====================================================================
        # Header background bar overlay
        self.canvas.create_rectangle(0, 0, WIDTH, 120, fill="#040508", outline="", stipple="" if not self.bg_photo else "")

        # Top Meta Info
        self.canvas.create_text(
            35, 24,
            text="UPDATE 1  •  VULKAN 1.3 NATIVE RENDERER",
            font=(FONT_FAMILY, 8, "bold"),
            fill="#71717a",
            anchor="w"
        )

        # Mandatory Credit at Top Right
        self.canvas.create_text(
            WIDTH - 35, 24,
            text="✦  Ported & Customized by krixsan  ✦",
            font=(FONT_FAMILY, 9, "bold italic"),
            fill=THEME_GOLD,
            anchor="e"
        )

        # Japanese Logo Title
        self.canvas.create_text(
            35, 48,
            text="戦 国 B A S A R A 4   皇",
            font=(FONT_JAPANESE, 10, "bold"),
            fill=THEME_CRIMSON,
            anchor="w"
        )

        # Main Majestic Title with Shadow
        self.canvas.create_text(
            36, 76,
            text="SENGOKU BASARA 4 SUMERAGI",
            font=(FONT_FAMILY, 21, "bold"),
            fill="#000000",
            anchor="w"
        )
        self.canvas.create_text(
            35, 75,
            text="SENGOKU BASARA 4 SUMERAGI",
            font=(FONT_FAMILY, 21, "bold"),
            fill=THEME_TEXT_WHITE,
            anchor="w"
        )

        self.canvas.create_text(
            35, 100,
            text="PC DEFINITIVE EDITION  —  HIGH PERFORMANCE EMULATION & ENGINE RECONSTRUCTION",
            font=(FONT_FAMILY, 8, "bold"),
            fill=THEME_GOLD_MUTED,
            anchor="w"
        )

        # Samurai Katana Blade Accent Line
        self.canvas.create_line(0, 120, WIDTH // 2, 120, fill=THEME_CRIMSON, width=2)
        self.canvas.create_line(WIDTH // 2, 120, WIDTH, 120, fill=THEME_GOLD, width=2)

        # =====================================================================
        # SYSTEM READINESS CARD
        # =====================================================================
        self.status_card = tk.Frame(self, bg=THEME_CARD, highlightthickness=1, highlightbackground=THEME_CARD_BORDER, padx=16, pady=9)
        self.canvas.create_window(WIDTH // 2, 155, window=self.status_card, width=WIDTH - 70, height=44)

        self.status_dot = tk.Label(self.status_card, text="●", font=(FONT_FAMILY, 11), fg=THEME_SUCCESS, bg=THEME_CARD)
        self.status_dot.pack(side="left", padx=(0, 10))

        self.status_text = tk.Label(
            self.status_card,
            text="Verifying game environment...",
            font=(FONT_FAMILY, 9),
            fg=THEME_TEXT_WHITE,
            bg=THEME_CARD,
            justify="left"
        )
        self.status_text.pack(side="left")

        # =====================================================================
        # SETTINGS CONTROL PANEL (SEMI-TRANSPARENT CARD STYLE)
        # =====================================================================
        settings_box = tk.Frame(self, bg=THEME_CARD, highlightthickness=1, highlightbackground=THEME_CARD_BORDER, padx=24, pady=16)
        self.canvas.create_window(WIDTH // 2, 310, window=settings_box, width=WIDTH - 70, height=220)

        # Section Header
        sec_header = tk.Frame(settings_box, bg=THEME_CARD)
        sec_header.pack(fill="x", pady=(0, 12))

        tk.Label(
            sec_header,
            text="ENGINE PREFERENCES & DISPLAY CONFIGURATION",
            font=(FONT_FAMILY, 10, "bold"),
            fg=THEME_GOLD,
            bg=THEME_CARD
        ).pack(side="left")

        tk.Label(
            sec_header,
            text="In-game overlay: [Insert] or [L3 + R3]",
            font=(FONT_FAMILY, 8),
            fg=THEME_TEXT_MUTED,
            bg=THEME_CARD
        ).pack(side="right")

        # Two-column grid inside card
        cols_frame = tk.Frame(settings_box, bg=THEME_CARD)
        cols_frame.pack(fill="both", expand=True)

        col_left = tk.Frame(cols_frame, bg=THEME_CARD)
        col_left.pack(side="left", fill="both", expand=True, padx=(0, 15))

        col_right = tk.Frame(cols_frame, bg=THEME_CARD)
        col_right.pack(side="right", fill="both", expand=True, padx=(15, 0))

        # Combobox styling
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground="#161924",
            background="#202434",
            foreground="#f8fafc",
            arrowcolor=THEME_GOLD,
            bordercolor=THEME_CARD_BORDER,
            darkcolor="#161924",
            lightcolor="#161924"
        )

        # Resolution
        res_row = tk.Frame(col_left, bg=THEME_CARD)
        res_row.pack(fill="x", pady=4)
        tk.Label(res_row, text="Target Resolution:", font=(FONT_FAMILY, 9), fg=THEME_TEXT_MUTED, bg=THEME_CARD).pack(side="left")
        res_cb = ttk.Combobox(
            res_row,
            textvariable=self.res_var,
            values=["1280x720", "1920x1080", "2560x1440", "3840x2160"],
            state="readonly",
            width=14,
            style="TCombobox"
        )
        res_cb.pack(side="right")

        # Framerate
        fps_row = tk.Frame(col_left, bg=THEME_CARD)
        fps_row.pack(fill="x", pady=4)
        tk.Label(fps_row, text="Frame Pacing:", font=(FONT_FAMILY, 9), fg=THEME_TEXT_MUTED, bg=THEME_CARD).pack(side="left")
        fps_cb = ttk.Combobox(
            fps_row,
            textvariable=self.fps_var,
            values=["60", "120", "144", "0"],
            state="readonly",
            width=14,
            style="TCombobox"
        )
        fps_cb.pack(side="right")

        # Fullscreen Switch
        fs_switch = ModernSwitch(col_left, self.fullscreen_var, text="Fullscreen Display", bg=THEME_CARD)
        fs_switch.pack(anchor="w", pady=(8, 0))

        # Skip Intro Switch
        intro_switch = ModernSwitch(col_right, self.skip_intro_var, text="Fast Boot (Skip Opening Movie)", bg=THEME_CARD)
        intro_switch.pack(anchor="w", pady=4)

        # FPS Counter Switch
        fps_switch = ModernSwitch(col_right, self.show_fps_var, text="On-Screen FPS Counter", bg=THEME_CARD)
        fps_switch.pack(anchor="w", pady=4)

        # Sub-hint
        sync_hint = tk.Label(
            col_right,
            text="Preferences auto-sync to basara.ini on launch.",
            font=(FONT_FAMILY, 8),
            fg="#64748b",
            bg=THEME_CARD
        )
        sync_hint.pack(anchor="w", pady=(8, 0))

        # =====================================================================
        # LAUNCH ACTION BUTTON (GLOWING CRIMSON WITH KATANA EMBLEM)
        # =====================================================================
        self.btn_canvas = tk.Canvas(self, width=WIDTH - 70, height=62, bg=THEME_BG, highlightthickness=0, cursor="hand2")
        self.canvas.create_window(WIDTH // 2, 475, window=self.btn_canvas)

        self.btn_canvas.bind("<Enter>", self.on_btn_hover)
        self.btn_canvas.bind("<Leave>", self.on_btn_leave)
        self.btn_canvas.bind("<Button-1>", self.on_btn_click)

        self.draw_launch_button(hover=False)

        # =====================================================================
        # BOTTOM FOOTER (LEGAL & KRIXSAN WATERMARK)
        # =====================================================================
        self.canvas.create_line(35, 545, WIDTH - 35, 545, fill="#1c202e", width=1)

        # Legal Note (Left)
        self.canvas.create_text(
            35, 570,
            text="CAPCOM CO., LTD.  •  SENGOKU BASARA IS A REGISTERED TRADEMARK  •  NON-COMMERCIAL RESEARCH PORT",
            font=(FONT_FAMILY, 7),
            fill="#52525b",
            anchor="w"
        )

        # Mandatory Footer Watermark (Right)
        self.canvas.create_text(
            WIDTH - 35, 570,
            text="Ported & Customized by krixsan",
            font=(FONT_FAMILY, 9, "bold italic"),
            fill=THEME_GOLD_BRIGHT,
            anchor="e"
        )

    def draw_launch_button(self, hover=False):
        self.btn_canvas.delete("all")
        w = WIDTH - 70
        h = 60
        r = 12

        if not self.is_ready:
            fill_color = "#171a24"
            border_color = "#272d3f"
            text_color = "#555f75"
            btn_text = "🔒   SETUP REQUIRED — MISSING GAME COMPONENTS"
        else:
            fill_color = THEME_CRIMSON_HOVER if hover else THEME_CRIMSON
            border_color = THEME_GOLD if hover else THEME_CRIMSON_DARK
            text_color = "#ffffff"
            btn_text = "⚔      LAUNCH SENGOKU BASARA 4 SUMERAGI      ⚔"

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

        # Samurai Gold Edge Corner Accents
        if self.is_ready:
            self.btn_canvas.create_line(16, 9, 36, 9, fill=THEME_GOLD, width=2)
            self.btn_canvas.create_line(16, 9, 16, 23, fill=THEME_GOLD, width=2)
            self.btn_canvas.create_line(w - 16, h - 9, w - 36, h - 9, fill=THEME_GOLD, width=2)
            self.btn_canvas.create_line(w - 16, h - 9, w - 16, h - 23, fill=THEME_GOLD, width=2)

        # Text with shadow
        self.btn_canvas.create_text(
            w // 2 + 1, h // 2 + 1,
            text=btn_text,
            fill="#000000",
            font=(FONT_FAMILY, 12, "bold")
        )
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
                text=f"System Verified  —  Core files intact ({exe} + {boot_bin} + {app0}). Ready for battle!",
                fg=THEME_SUCCESS
            )
            self.status_card.config(highlightbackground=THEME_CARD_BORDER)
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
