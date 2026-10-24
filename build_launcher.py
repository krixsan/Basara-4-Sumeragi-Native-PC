#!/usr/bin/env python3
"""Build script for compiling launcher.py into Basara4_Launcher.exe using PyInstaller."""
import os
import shutil
import subprocess
import sys

def build():
    print("Building Basara4_Launcher.exe...")
    icon = os.path.join("packaging", "windows", "icons", "basara4.ico")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "Basara4_Launcher",
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
        print("Successfully generated Basara4_Launcher.exe in root directory!")
    
    # Cleanup temp build dirs
    for d in ["dist", "build"]:
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
    if os.path.isfile("Basara4_Launcher.spec"):
        os.remove("Basara4_Launcher.spec")

if __name__ == "__main__":
    build()
