@echo off
setlocal enabledelayedexpansion
title Sengoku Basara 4 Sumeragi - PC Launcher

echo =======================================================
echo     Sengoku Basara 4 Sumeragi - PC Native Port
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

rem Locate boot binary
set "BOOT_BIN="
if exist "%~dp0boot-linked.bin" (
    set "BOOT_BIN=%~dp0boot-linked.bin"
) else if exist "%~dp0out\boot-linked.bin" (
    set "BOOT_BIN=%~dp0out\boot-linked.bin"
)

if "!BOOT_BIN!"=="" (
    echo [ERROR] boot-linked.bin not found!
    echo Expected in current directory or out\boot-linked.bin.
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

echo Starting Sengoku Basara 4 Sumeragi...
echo.

cd /d "%~dp0"
start "" "%~dp0basara_pc.exe" "!BOOT_BIN!" --app0 "!APP0_DIR!"

exit /b 0
