#!/usr/bin/env python3
"""
Sengoku Basara 4 Sumeragi — PC Native Port
Studio-Grade AAA Graphical Launcher & Configuration Engine

Engine Port & Custom Runtime by krixsan
"""

import os
import sys
import ctypes
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk, ImageFilter, ImageChops

# Enable Windows High-DPI Awareness
try:
    if sys.platform == "win32":
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- Theme Configuration ---
WIDTH = 960
HEIGHT = 560

COLOR_BG_DARK = "#0a0c12"
COLOR_GOLD = "#D4AF37"
COLOR_GOLD_BRIGHT = "#E5C158"
COLOR_CRIMSON = "#B81D24"
COLOR_CRIMSON_DARK = "#8E1118"
COLOR_CRIMSON_LIGHT = "#C81E2B"
COLOR_CRIMSON_HOVER = "#DC2626"
COLOR_TEXT_WHITE = "#FFFFFF"
COLOR_TEXT_MUTED = "#8F9CAE"
COLOR_TEXT_SUB = "#7E8B9B"
COLOR_SUCCESS = "#2ECC71"
COLOR_ERROR = "#E74C3C"

FONT_FAMILY = "Segoe UI"
FONT_TITLE = "Segoe UI Black"
FONT_SUBTITLE = "Segoe UI Semibold"

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
            "# Engine Port & Custom Runtime by krixsan\n",
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
        missing.append("basara_pc.exe")

    boot_bin = None
    for cand in ["boot-linked.bin", os.path.join("out", "boot-linked.bin")]:
        if os.path.isfile(cand):
            boot_bin = cand
            break
    if not boot_bin:
        missing.append("boot-linked.bin")

    app0 = None
    for cand in [os.path.join("extracted_game", "app0"), "app0"]:
        if os.path.isdir(cand):
            app0 = cand
            break
    if not app0:
        missing.append("extracted_game/app0")

    return missing, exe, boot_bin, app0


class BasaraLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sengoku Basara 4 Sumeragi — PC Native Port")
        self.geometry(f"{WIDTH}x{HEIGHT}")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG_DARK)

        self.apply_native_dark_title_bar()
        self.apply_window_icon()
        self.center_on_screen()

        self.load_configuration()
        self.generate_textures()
        self.build_canvas()
        self.evaluate_system_readiness()

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
        self.fullscreen_val = (ini.get("fullscreen", "1") == "1")
        self.skip_intro_val = (ini.get("skip_intro", "0") == "1")
        self.show_fps_val = (ini.get("show_fps", "1") == "1")
        self.is_ready = False

    def sync_ini(self):
        height = self.res_val.split("x")[-1] if "x" in self.res_val else "1080"
        cfg_payload = {
            "output_res": self.res_val,
            "render_res": height,
            "fullscreen": "1" if self.fullscreen_val else "0",
            "fps_limit": self.fps_val,
            "skip_intro": "1" if self.skip_intro_val else "0",
            "show_fps": "1" if self.show_fps_val else "0",
        }
        write_ini(cfg_payload)

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
        blurred = base.filter(ImageFilter.GaussianBlur(radius=7))
        grad_blur = Image.new("L", (WIDTH, 1))
        d_b = ImageDraw.Draw(grad_blur)
        for x in range(WIDTH):
            if x <= 360:
                val = 255
            elif x <= 500:
                val = int(255 * (1.0 - (x - 360) / 140.0))
            else:
                val = 0
            d_b.point((x, 0), fill=val)
        mask_blur = grad_blur.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
        comp = Image.composite(blurred, base, mask_blur)

        # Dark gradient vignette mask (Left: heavy dark tint, Right: crystal clear)
        grad_x = Image.new("L", (WIDTH, 1))
        d_x = ImageDraw.Draw(grad_x)
        for x in range(WIDTH):
            if x <= 380:
                val = 238
            elif x <= 580:
                val = int(238 * (1.0 - (x - 380) / 200.0))
            else:
                val = 0
            d_x.point((x, 0), fill=val)
        mask_x = grad_x.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)

        # Bottom bar & top edge vignette
        grad_y = Image.new("L", (1, HEIGHT))
        d_y = ImageDraw.Draw(grad_y)
        for y in range(HEIGHT):
            if y >= 435:
                val = int(195 * ((y - 435) / 125.0))
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

        # 2. Game Icon (54x54)
        icon0_cand = [
            os.path.join("extracted_game", "app0", "sce_sys", "icon0.png"),
            os.path.join("app0", "sce_sys", "icon0.png"),
        ]
        self.photo_icon0 = None
        for p in icon0_cand:
            if os.path.isfile(p):
                try:
                    ic = Image.open(p).convert("RGBA").resize((54, 54), Image.Resampling.LANCZOS)
                    mask = Image.new("L", (54, 54), 0)
                    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 53, 53], radius=8, fill=255)
                    rounded_ic = Image.new("RGBA", (54, 54), (0, 0, 0, 0))
                    rounded_ic.paste(ic, (0, 0), mask)
                    ImageDraw.Draw(rounded_ic).rounded_rectangle([0, 0, 53, 53], radius=8, outline=(229, 193, 88, 200), width=1)
                    self.photo_icon0 = ImageTk.PhotoImage(rounded_ic)
                    break
                except Exception:
                    pass

        # 3. Custom Segmented Pill Button Textures (96 x 28)
        self.pill_active = self._create_pill_texture(96, 28, (184, 29, 36, 255), (229, 193, 88, 255), radius=6, width=1)
        self.pill_inactive = self._create_pill_texture(96, 28, (20, 24, 32, 215), (48, 56, 72, 255), radius=6, width=1)
        self.pill_hover = self._create_pill_texture(96, 28, (32, 38, 52, 240), (70, 82, 106, 255), radius=6, width=1)

        # 4. Modern Toggle Switches (44 x 22)
        self.switch_on = self._create_switch_texture(True)
        self.switch_off = self._create_switch_texture(False)

        # 5. Play Button Textures (280 x 54)
        self.btn_play_normal = self._create_play_btn_texture(hover=False, enabled=True)
        self.btn_play_hover = self._create_play_btn_texture(hover=True, enabled=True)
        self.btn_play_disabled = self._create_play_btn_texture(hover=False, enabled=False)

    def _create_pill_texture(self, w, h, fill, outline, radius=6, width=1):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill, outline=outline, width=width)
        return ImageTk.PhotoImage(img)

    def _create_switch_texture(self, val):
        w, h = 44, 22
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if val:
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(184, 29, 36, 255), outline=(229, 193, 88, 255), width=1)
            d.ellipse([w - 18, 4, w - 6, 16], fill=(255, 255, 255, 255))
        else:
            d.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, fill=(28, 33, 44, 230), outline=(52, 60, 76, 255), width=1)
            d.ellipse([6, 4, 18, 16], fill=(126, 139, 155, 255))
        return ImageTk.PhotoImage(img)

    def _create_play_btn_texture(self, hover=False, enabled=True):
        w, h = 280, 54
        if not enabled:
            top_col = (42, 48, 60, 255)
            bot_col = (28, 32, 42, 255)
            border_col = (59, 68, 85, 255)
        elif hover:
            top_col = (220, 38, 38, 255)
            bot_col = (163, 18, 25, 255)
            border_col = (246, 196, 69, 255)
        else:
            top_col = (200, 30, 43, 255)
            bot_col = (142, 17, 24, 255)
            border_col = (229, 193, 88, 255)

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
        d_btn.rounded_rectangle([0, 0, w - 1, h - 1], radius=10, outline=border_col, width=1)
        return ImageTk.PhotoImage(btn)

    def build_canvas(self):
        self.canvas = tk.Canvas(self, width=WIDTH, height=HEIGHT, highlightthickness=0, bg=COLOR_BG_DARK)
        self.canvas.pack(fill="both", expand=True)

        # 1. Main Background
        self.canvas.create_image(0, 0, image=self.photo_bg, anchor="nw")

        # 2. Header & Branding
        text_x = 36
        if self.photo_icon0:
            self.canvas.create_image(36, 32, image=self.photo_icon0, anchor="nw")
            text_x = 104

        # Badge
        self.canvas.create_text(
            text_x, 34,
            text="VULKAN 1.3 NATIVE PORT  •  UPDATE 1",
            font=(FONT_SUBTITLE, 9, "bold"),
            fill=COLOR_GOLD,
            anchor="nw"
        )

        # Title Line 1 (Shadow + Crisp White)
        self.canvas.create_text(
            text_x + 1, 53,
            text="SENGOKU BASARA 4",
            font=(FONT_TITLE, 21, "bold"),
            fill="#000000",
            anchor="nw"
        )
        self.canvas.create_text(
            text_x, 52,
            text="SENGOKU BASARA 4",
            font=(FONT_TITLE, 21, "bold"),
            fill=COLOR_TEXT_WHITE,
            anchor="nw"
        )

        # Title Line 2
        self.canvas.create_text(
            text_x, 82,
            text="S U M E R A G I",
            font=(FONT_SUBTITLE, 11, "bold"),
            fill=COLOR_GOLD_BRIGHT,
            anchor="nw"
        )

        # Single exclusive credit line
        self.canvas.create_text(
            text_x, 102,
            text="Engine Port & Custom Runtime by krixsan",
            font=(FONT_FAMILY, 9),
            fill=COLOR_TEXT_MUTED,
            anchor="nw"
        )

        # Divider Line
        self.canvas.create_line(36, 128, 444, 128, fill="#232938", width=1)

        # =====================================================================
        # 3. RESOLUTION SELECTOR (Segmented Pill Buttons)
        # =====================================================================
        self.canvas.create_text(
            36, 142,
            text="DISPLAY RESOLUTION",
            font=(FONT_FAMILY, 8, "bold"),
            fill=COLOR_TEXT_MUTED,
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
            x = 36 + i * 104
            y = 162
            img_id = self.canvas.create_image(x, y, image=self.pill_inactive, anchor="nw")
            txt_id = self.canvas.create_text(x + 48, y + 14, text=label, font=(FONT_FAMILY, 8, "bold"), fill=COLOR_TEXT_MUTED)

            tag = f"btn_res_{i}"
            self.canvas.itemconfig(img_id, tags=(tag,))
            self.canvas.itemconfig(txt_id, tags=(tag,))

            self.canvas.tag_bind(tag, "<Enter>", lambda e, idx=i: self._on_res_enter(idx))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, idx=i: self._on_res_leave(idx))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, v=val: self._select_res(v))

            self.res_items.append((img_id, txt_id, val))

        # =====================================================================
        # 4. FRAMERATE TARGET SELECTOR (Segmented Pill Buttons)
        # =====================================================================
        self.canvas.create_text(
            36, 206,
            text="FRAME RATE TARGET",
            font=(FONT_FAMILY, 8, "bold"),
            fill=COLOR_TEXT_MUTED,
            anchor="nw"
        )

        self.fps_options = [
            ("60 FPS", "60"),
            ("120 FPS", "120"),
            ("144 FPS", "144"),
            ("240 FPS", "240"),
        ]
        self.fps_items = []
        for i, (label, val) in enumerate(self.fps_options):
            x = 36 + i * 104
            y = 226
            img_id = self.canvas.create_image(x, y, image=self.pill_inactive, anchor="nw")
            txt_id = self.canvas.create_text(x + 48, y + 14, text=label, font=(FONT_FAMILY, 8, "bold"), fill=COLOR_TEXT_MUTED)

            tag = f"btn_fps_{i}"
            self.canvas.itemconfig(img_id, tags=(tag,))
            self.canvas.itemconfig(txt_id, tags=(tag,))

            self.canvas.tag_bind(tag, "<Enter>", lambda e, idx=i: self._on_fps_enter(idx))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, idx=i: self._on_fps_leave(idx))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, v=val: self._select_fps(v))

            self.fps_items.append((img_id, txt_id, val))

        # =====================================================================
        # 5. ENGINE PREFERENCES (3 Modern Toggle Switches)
        # =====================================================================
        self.canvas.create_text(
            36, 270,
            text="ENGINE PREFERENCES",
            font=(FONT_FAMILY, 8, "bold"),
            fill=COLOR_TEXT_MUTED,
            anchor="nw"
        )

        # Toggle 1: Fullscreen Mode
        self.sw1_img = self.canvas.create_image(36, 294, image=self.switch_off, anchor="nw")
        t1_title = self.canvas.create_text(92, 295, text="Fullscreen Mode", font=(FONT_FAMILY, 9, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        t1_sub = self.canvas.create_text(92, 312, text="Run in borderless or exclusive fullscreen display", font=(FONT_FAMILY, 8), fill=COLOR_TEXT_SUB, anchor="nw")
        tag1 = "toggle_fullscreen"
        for item in (self.sw1_img, t1_title, t1_sub):
            self.canvas.itemconfig(item, tags=(tag1,))
        self.canvas.tag_bind(tag1, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag1, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag1, "<Button-1>", lambda e: self._toggle_setting("fullscreen"))

        # Toggle 2: Skip Opening Movie
        self.sw2_img = self.canvas.create_image(36, 337, image=self.switch_off, anchor="nw")
        t2_title = self.canvas.create_text(92, 338, text="Skip Opening Movie", font=(FONT_FAMILY, 9, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        t2_sub = self.canvas.create_text(92, 355, text="Bypass intro video on startup and load title screen", font=(FONT_FAMILY, 8), fill=COLOR_TEXT_SUB, anchor="nw")
        tag2 = "toggle_skip_intro"
        for item in (self.sw2_img, t2_title, t2_sub):
            self.canvas.itemconfig(item, tags=(tag2,))
        self.canvas.tag_bind(tag2, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag2, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag2, "<Button-1>", lambda e: self._toggle_setting("skip_intro"))

        # Toggle 3: In-Game FPS Overlay
        self.sw3_img = self.canvas.create_image(36, 380, image=self.switch_off, anchor="nw")
        t3_title = self.canvas.create_text(92, 381, text="In-Game FPS Overlay", font=(FONT_FAMILY, 9, "bold"), fill=COLOR_TEXT_WHITE, anchor="nw")
        t3_sub = self.canvas.create_text(92, 398, text="Show performance metrics in-game (Insert / L3+R3)", font=(FONT_FAMILY, 8), fill=COLOR_TEXT_SUB, anchor="nw")
        tag3 = "toggle_show_fps"
        for item in (self.sw3_img, t3_title, t3_sub):
            self.canvas.itemconfig(item, tags=(tag3,))
        self.canvas.tag_bind(tag3, "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag3, "<Leave>", lambda e: self.canvas.config(cursor="arrow"))
        self.canvas.tag_bind(tag3, "<Button-1>", lambda e: self._toggle_setting("show_fps"))

        # =====================================================================
        # 6. BOTTOM ACTION BAR (Status & PLAY GAME)
        # =====================================================================
        self.canvas.create_line(36, 444, WIDTH - 36, 444, fill="#232938", width=1)

        # Status Indicator (Left)
        self.status_dot = self.canvas.create_oval(38, 490, 48, 500, fill=COLOR_SUCCESS, outline="")
        self.status_title = self.canvas.create_text(
            58, 483,
            text="Game files verified & ready",
            font=(FONT_FAMILY, 9, "bold"),
            fill=COLOR_SUCCESS,
            anchor="nw"
        )
        self.status_sub = self.canvas.create_text(
            58, 501,
            text="Vulkan runtime, boot binary, and asset archives active",
            font=(FONT_FAMILY, 8),
            fill=COLOR_TEXT_SUB,
            anchor="nw"
        )

        # Play Button (Right, 280 x 54)
        self.play_img_id = self.canvas.create_image(WIDTH - 36 - 280, 468, image=self.btn_play_normal, anchor="nw")
        self.play_txt_id = self.canvas.create_text(
            WIDTH - 36 - 140, 495,
            text="PLAY GAME",
            font=(FONT_TITLE, 14, "bold"),
            fill=COLOR_TEXT_WHITE
        )

        tag_play = "btn_play_game"
        self.canvas.itemconfig(self.play_img_id, tags=(tag_play,))
        self.canvas.itemconfig(self.play_txt_id, tags=(tag_play,))
        self.canvas.tag_bind(tag_play, "<Enter>", self._on_play_enter)
        self.canvas.tag_bind(tag_play, "<Leave>", self._on_play_leave)
        self.canvas.tag_bind(tag_play, "<Button-1>", self._on_play_click)

        # Initial GUI Refresh
        self.refresh_controls()

    def refresh_controls(self):
        # Refresh Resolution buttons
        for img_id, txt_id, val in self.res_items:
            if val == self.res_val:
                self.canvas.itemconfig(img_id, image=self.pill_active)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)
            else:
                self.canvas.itemconfig(img_id, image=self.pill_inactive)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

        # Refresh FPS buttons
        for img_id, txt_id, val in self.fps_items:
            if val == self.fps_val:
                self.canvas.itemconfig(img_id, image=self.pill_active)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)
            else:
                self.canvas.itemconfig(img_id, image=self.pill_inactive)
                self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

        # Refresh Switches
        self.canvas.itemconfig(self.sw1_img, image=self.switch_on if self.fullscreen_val else self.switch_off)
        self.canvas.itemconfig(self.sw2_img, image=self.switch_on if self.skip_intro_val else self.switch_off)
        self.canvas.itemconfig(self.sw3_img, image=self.switch_on if self.show_fps_val else self.switch_off)

    def _on_res_enter(self, idx):
        self.canvas.config(cursor="hand2")
        img_id, txt_id, val = self.res_items[idx]
        if val != self.res_val:
            self.canvas.itemconfig(img_id, image=self.pill_hover)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)

    def _on_res_leave(self, idx):
        self.canvas.config(cursor="arrow")
        img_id, txt_id, val = self.res_items[idx]
        if val != self.res_val:
            self.canvas.itemconfig(img_id, image=self.pill_inactive)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

    def _select_res(self, val):
        self.res_val = val
        self.refresh_controls()
        self.sync_ini()

    def _on_fps_enter(self, idx):
        self.canvas.config(cursor="hand2")
        img_id, txt_id, val = self.fps_items[idx]
        if val != self.fps_val:
            self.canvas.itemconfig(img_id, image=self.pill_hover)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_WHITE)

    def _on_fps_leave(self, idx):
        self.canvas.config(cursor="arrow")
        img_id, txt_id, val = self.fps_items[idx]
        if val != self.fps_val:
            self.canvas.itemconfig(img_id, image=self.pill_inactive)
            self.canvas.itemconfig(txt_id, fill=COLOR_TEXT_MUTED)

    def _select_fps(self, val):
        self.fps_val = val
        self.refresh_controls()
        self.sync_ini()

    def _toggle_setting(self, name):
        if name == "fullscreen":
            self.fullscreen_val = not self.fullscreen_val
        elif name == "skip_intro":
            self.skip_intro_val = not self.skip_intro_val
        elif name == "show_fps":
            self.show_fps_val = not self.show_fps_val
        self.refresh_controls()
        self.sync_ini()

    def _on_play_enter(self, event):
        if self.is_ready:
            self.canvas.config(cursor="hand2")
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_hover)

    def _on_play_leave(self, event):
        self.canvas.config(cursor="arrow")
        if self.is_ready:
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_normal)

    def _on_play_click(self, event):
        if self.is_ready:
            self.launch_game()

    def evaluate_system_readiness(self):
        missing, exe, boot_bin, app0 = verify_game_installation()
        if missing:
            self.is_ready = False
            self.canvas.itemconfig(self.status_dot, fill=COLOR_ERROR)
            self.canvas.itemconfig(self.status_title, text="Setup Required — Missing components", fill=COLOR_ERROR)
            self.canvas.itemconfig(self.status_sub, text="Missing: " + ", ".join(missing), fill=COLOR_ERROR)
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_disabled)
            self.canvas.itemconfig(self.play_txt_id, text="SETUP REQUIRED", fill="#6E7A8E")
        else:
            self.is_ready = True
            self.canvas.itemconfig(self.status_dot, fill=COLOR_SUCCESS)
            self.canvas.itemconfig(self.status_title, text="Game files verified & ready", fill=COLOR_SUCCESS)
            self.canvas.itemconfig(self.status_sub, text="Vulkan runtime, boot binary, and asset archives active", fill=COLOR_TEXT_SUB)
            self.canvas.itemconfig(self.play_img_id, image=self.btn_play_normal)
            self.canvas.itemconfig(self.play_txt_id, text="PLAY GAME", fill=COLOR_TEXT_WHITE)

    def launch_game(self):
        missing, exe, boot_bin, app0 = verify_game_installation()
        if missing:
            messagebox.showerror("Engine Warning", "Cannot launch. Missing components:\n\n" + "\n".join(missing))
            return

        self.sync_ini()

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

        # Seamless minimize/hide
        self.withdraw()

        def process_watcher():
            try:
                proc = subprocess.Popen(cmd, cwd=os.getcwd())
                proc.wait()
            except Exception as err:
                print(f"Game runtime error: {err}")
            finally:
                self.after(300, self.on_game_finish)

        threading.Thread(target=process_watcher, daemon=True).start()

    def on_game_finish(self):
        self.deiconify()
        self.evaluate_system_readiness()


if __name__ == "__main__":
    app = BasaraLauncher()
    app.mainloop()
