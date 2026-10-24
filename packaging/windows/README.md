# Sengoku Basara 4 Sumeragi — Windows Compilation & Packaging

This directory contains compilation manifests, resource files, and packaging scripts for the native Windows port of **Sengoku Basara 4 Sumeragi**.

## Building on Windows (MSYS2 CLANG64)

The runtime and Vulkan presentation engine compile natively on 64-bit Windows 10 and 11 using the MSYS2 CLANG64 toolchain.

### Prerequisites

1. Install [MSYS2](https://www.msys2.org) into `C:\msys64` (or `F:\msys64`).
2. Open the **MSYS2 CLANG64** shell and install dependencies:

```bash
pacman -S --needed git patch \
  mingw-w64-clang-x86_64-{toolchain,cmake,ninja,pkgconf,python} \
  mingw-w64-clang-x86_64-{vulkan-headers,vulkan-loader,vulkan-memory-allocator,glslang} \
  mingw-w64-clang-x86_64-{sdl3,fmt,boost,robin-map,xxhash,ffmpeg,zydis} \
  mingw-w64-clang-x86_64-{spirv-tools,spirv-headers,spirv-cross}
```

### Build Commands

```bash
# Run root compilation script
./win_build.sh
```

This compiles:
- `basara_pc.exe`: High-performance native x86_64 execution engine & Vulkan 1.3 renderer.

## Packaging

The desktop launcher `Basara4_Launcher.exe` is compiled using PyInstaller:

```bash
python build_launcher.py
```

The resulting package contains:
- `basara_pc.exe`
- `Basara4_Launcher.exe`
- `basara4-pad-mapper.exe`
- `basara.ini`
- `Play_Basara4.bat`
- `README.md` & `README.id.md`
