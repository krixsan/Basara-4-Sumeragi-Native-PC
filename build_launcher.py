#!/usr/bin/env python3
"""Build script for compiling launcher.py into Basara4_Launcher.exe using PyInstaller."""
import os
import shutil
import subprocess
import sys

def build():
    print("Building Basara4_Launcher.exe with embedded auto-builder...")
    icon = os.path.join("packaging", "windows", "icons", "basara4.ico")
    cmd = [
        sys.executable, "-m", "PyInstaller",
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
