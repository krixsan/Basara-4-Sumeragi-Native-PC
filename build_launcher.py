#!/usr/bin/env python3
"""Build script for compiling launcher.py into Basara4_Launcher.exe using PyInstaller."""
import os
import shutil
import subprocess
import sys

def convert_icon():
    src_icon = os.path.join("extracted_game", "app0", "sce_sys", "icon0.png")
    ico_dest = os.path.join("packaging", "windows", "icons", "basara4.ico")
    if os.path.isfile(src_icon):
        try:
            from PIL import Image
            img = Image.open(src_icon).convert("RGBA")
            sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
            resized = [img.resize(s, Image.Resampling.LANCZOS) for s in sizes]
            os.makedirs(os.path.dirname(ico_dest), exist_ok=True)
            resized[0].save(ico_dest, format="ICO", append_images=resized[1:])
            print(f"[ICON] Successfully converted {src_icon} -> {ico_dest} (LANCZOS multi-res)")
        except Exception as e:
            print(f"[ICON ERROR] Failed converting icon: {e}")

def build():
    print("Building Basara4_Launcher.exe with embedded auto-builder...")
    convert_icon()
    icon = os.path.join("packaging", "windows", "icons", "basara4.ico")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "Basara4_Launcher",
        "--paths", "scripts",
        "--paths", "tools",
        "--hidden-import", "auto_builder",
        "--hidden-import", "prepare",
        "--hidden-import", "link_modules",
        "--hidden-import", "link_libc",
        "--hidden-import", "content_profile",
        "--hidden-import", "game_check",
        "--hidden-import", "gen_import_names",
        "launcher.py"
    ]
    if os.path.isfile(icon):
        cmd.extend(["--icon", icon])
    
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print("PyInstaller build failed!")
        sys.exit(res.returncode)

    dist_exe = os.path.join("dist", "Basara4_Launcher.exe")
    if os.path.isfile(dist_exe):
        shutil.copy2(dist_exe, "Basara4_Launcher.exe")
        print("Successfully generated dist/Basara4_Launcher.exe and copied to root directory!")
    
    # Cleanup temp build artifacts but PRESERVE dist directory
    if os.path.isdir("build"):
        shutil.rmtree("build", ignore_errors=True)
    if os.path.isfile("Basara4_Launcher.spec"):
        os.remove("Basara4_Launcher.spec")

if __name__ == "__main__":
    build()
