@echo off
setlocal enabledelayedexpansion
title Sengoku Basara 4 Sumeragi - PC Launcher
cd /d "%~dp0"

echo =======================================================
echo     Sengoku Basara 4 Sumeragi - PC Native Port
echo     High-Performance Vulkan 1.3 Execution Engine
echo =======================================================
echo.

rem Check executable
if not exist "%~dp0basara_pc.exe" (
    echo [ERROR] basara_pc.exe not found!
    echo Please make sure this launcher is placed in the game directory.
    echo.
    pause
    exit /b 1
)

rem Locate boot binary or auto-generate on first run
set "BOOT_BIN="
if exist "%~dp0boot-linked.bin" (
    set "BOOT_BIN=%~dp0boot-linked.bin"
) else if exist "%~dp0out\boot-linked.bin" (
    set "BOOT_BIN=%~dp0out\boot-linked.bin"
)

if "!BOOT_BIN!"=="" (
    echo [INFO] First run detected. Generating out\boot-linked.bin from game assets...
    echo Please wait ~15-30 seconds...
    echo.
    if exist "%~dp0Basara4_Launcher.exe" (
        start /wait "" "%~dp0Basara4_Launcher.exe" --prepare-only
    ) else if exist "%~dp0launcher.py" (
        python "%~dp0launcher.py" --prepare-only
    )

    if exist "%~dp0boot-linked.bin" (
        set "BOOT_BIN=%~dp0boot-linked.bin"
    ) else if exist "%~dp0out\boot-linked.bin" (
        set "BOOT_BIN=%~dp0out\boot-linked.bin"
    )
)

if "!BOOT_BIN!"=="" (
    echo [ERROR] boot-linked.bin not found and could not be generated automatically!
    echo Please ensure 'extracted_game\app0\eboot.bin' exists.
    echo.
    pause
    exit /b 1
)

rem Locate game data (app0)
set "APP0_DIR="
if exist "%~dp0extracted_game\app0\eboot.bin" (
    set "APP0_DIR=%~dp0extracted_game\app0"
) else if exist "%~dp0app0\eboot.bin" (
    set "APP0_DIR=%~dp0app0"
) else if exist "%~dp0extracted_game\app0" (
    set "APP0_DIR=%~dp0extracted_game\app0"
) else if exist "%~dp0app0" (
    set "APP0_DIR=%~dp0app0"
)

if "!APP0_DIR!"=="" (
    echo [WARNING] Game data folder (app0) not automatically detected.
    echo Defaulting to 'extracted_game/app0'...
    set "APP0_DIR=%~dp0extracted_game\app0"
)

rem Extra profile and import args if available
set "EXTRA_ARGS="
if exist "%~dp0out\import_names.txt" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --import-names "%~dp0out\import_names.txt""
)
if exist "%~dp0out\content.bin" (
    set "EXTRA_ARGS=!EXTRA_ARGS! --content-profile "%~dp0out\content.bin""
)

echo Starting Sengoku Basara 4 Sumeragi...
echo.

start "" "%~dp0basara_pc.exe" "!BOOT_BIN!" !EXTRA_ARGS! --app0 "!APP0_DIR!" --user "%~dp0user"

exit /b 0
