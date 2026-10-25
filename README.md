# Sengoku Basara 4 Sumeragi — PC Native Port (`basara_pc`)

<p align="center">
  <img src="packaging/windows/icons/basara4.ico" alt="Sengoku Basara 4 Logo" width="128" height="128" />
</p>

<p align="center">
  <a href="https://microsoft.com/windows"><img src="https://img.shields.io/badge/Platform-Windows%2010%201809+%20/%2011%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" /></a>
  <a href="https://www.vulkan.org"><img src="https://img.shields.io/badge/API-Vulkan%201.3+-E42528?style=for-the-badge&logo=vulkan&logoColor=white" alt="Vulkan API" /></a>
  <a href="https://en.wikipedia.org/wiki/X86-64"><img src="https://img.shields.io/badge/Architecture-x86__64%20Native%20Runtime-4B32C3?style=for-the-badge" alt="Architecture" /></a>
  <a href="https://visualstudio.microsoft.com"><img src="https://img.shields.io/badge/Dependency-VC++%202015--2022%20x64-5C2D91?style=for-the-badge" alt="VC++ Redist" /></a>
  <a href="../../releases"><img src="https://img.shields.io/badge/Release-Update%203-10B981?style=for-the-badge" alt="Release" /></a>
</p>

<p align="center">
  <b>Native x86_64 PC Execution & Vulkan 1.3 Presentation Engine</b><br>
  <i>Read in: <a href="README.id.md">Bahasa Indonesia</a></i>
</p>

A high-performance native PC runtime and Vulkan presentation engine for **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)**, bringing Capcom's legendary stylish action hack-and-slash experience natively to modern PC hardware with ultra-low latency, unlocked framerates, high-resolution rendering, and modern gamepad ergonomics.

---

## Quick Start (3 Steps — Under 5 Minutes)

### 1. Download
Get the latest build from the [Releases](../../releases) tab:
- **Installer (Recommended):** `Basara4_Sumeragi_PC_Setup_v<version>.exe` (Per-user non-admin installation, creates Start Menu & Desktop shortcuts, preserves user data on uninstall).
- **Portable ZIP:** `Basara4_Sumeragi_PC_v<version>.zip` (Extract anywhere).

### 2. Launch
Run **`Basara4_Launcher.exe`**.
- The built-in dependency engine verifies **Vulkan 1.3 loader**, **VC++ Redist 2015–2022 x64**, **Windows version**, and **Storage**.
- If any required library is missing, one-click official download links are provided.

### 3. Setup & Play
On a fresh installation, the **5-Step Setup Wizard** will guide you:
1. Accept the fair-use legal disclaimer.
2. Select your legally dumped `eboot.bin` (both decrypted SELF and standard ELF formats are supported).
3. The wizard automatically links modules and creates `out/boot-linked.bin` in seconds.
4. Click **PLAY GAME**!

---

## Legal Dump Notice

> [!IMPORTANT]
> **No copyrighted Capcom assets, disc images, binaries, or encryption keys are bundled with this software.**
> 
> You need to dump `eboot.bin` from your legally owned PS4. Search the PS4 homebrew community for dumping tutorials.

---

## System Requirements

| Component | Minimum | Recommended |
|---|---|---|
| **OS** | Windows 10 64-bit (Build 17763 / Version 1809+) | Windows 11 64-bit |
| **Processor** | 4-Core / 8-Thread x86_64 CPU | 6-Core / 12-Thread x86_64 CPU (Zen 3 / Intel 12th Gen+) |
| **Memory** | 8 GB RAM | 16 GB Dual-Channel RAM |
| **Graphics** | Vulkan 1.3 capable GPU (GTX 1060 6GB / RX 580) | RTX 2060 / RX 6600 or higher |
| **Storage** | 500 MB free (for engine & cache) + Game assets | NVMe / SATA SSD |
| **Runtimes** | [Vulkan Runtime 1.3+](https://vulkan.lunarg.com/sdk/home#windows) & [VC++ 2015–2022 x64](https://aka.ms/vs/17/release/vc_redist.x64.exe) | Updated GPU drivers |

---

## Troubleshooting

### 1. "Vulkan Loader (vulkan-1.dll) Missing"
- **Cause:** Your system does not have the Khronos Vulkan loader installed.
- **Solution:** Download and install the official runtime from [LunarG Vulkan SDK / Runtime](https://vulkan.lunarg.com/sdk/home#windows), or update your NVIDIA / AMD / Intel GPU drivers to the latest version.

### 2. "Microsoft Visual C++ Redistributable Missing"
- **Cause:** Missing MSVC 14.0 x64 runtime libraries (`vcruntime140.dll` / `msvcp140.dll`).
- **Solution:** Download and install [Microsoft Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe).

### 3. Crash on Startup or Map Load
- Check `user/logs/basara.log` and `user/crashes/` for raw crash dumps (`crash_raw_*.log`).
- Telemetry & crash minidumps follow strict privacy-by-design standards with personal identifiers redacted (see [PRIVACY.md](PRIVACY.md)).

### 4. Controller Not Recognized
- XInput controllers (Xbox, PS4/PS5 via DS4Windows/Steam) work natively.
- For generic DirectInput controllers, click **🎮 Gamepad** in the launcher toolbar to open `basara4-pad-mapper.exe` and generate `user/gamepad_mapping.txt`.

---

## Configuration (`basara.ini`)

Settings are synchronized between the graphical launcher, in-game overlay (`Insert` or `L3+R3`), and `basara.ini`:

| Key | Default | Description |
|---|---|---|
| `output_res` | `1920x1080` | Window and display presentation resolution |
| `render_res` | `1080` | Internal rendering target resolution (`720`, `1080`, `1440`, `2160`) |
| `fullscreen` | `1` | `1` for borderless/exclusive fullscreen, `0` for windowed mode |
| `fps_limit` | `144` | Target framerate limit (`60`, `90`, `120`, `144`, `240`, `0` for unlimited) |
| `anisotropy` | `16` | Forced Anisotropic Filtering level (`0`, `2`, `4`, `8`, `16`) |
| `fsr1` | `1` | `1` to enable AMD FSR 1.0 spatial upscaling |
| `rcas` | `1` | `1` to enable Robust Contrast Adaptive Sharpening |
| `process_priority` | `above_normal` | Windows CPU scheduling priority (`normal`, `above_normal`, `high`) |
| `telemetry_upload` | `ask` | Crash reporter behavior (`ask`, `never`, `always`) |
| `first_run_done` | `0` | Setup wizard completion state flag |
| `legal_acknowledged`| `0` | Fair-use legal acknowledgement flag |

---

## Building from Source

### Prerequisites
- Windows 10 1809+ / 11 x64
- [MSYS2](https://www.msys2.org/) with `CLANG64` environment
- Python 3.10+ (with `pillow` and `pyinstaller`)
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (optional, for installer builds)

### 1. Compile Native Engine (`basara_pc.exe`)
```bash
# In MSYS2 CLANG64 shell:
pacman -S --needed git ninja mingw-w64-clang-x86_64-clang mingw-w64-clang-x86_64-cmake \
  mingw-w64-clang-x86_64-vulkan-headers mingw-w64-clang-x86_64-vulkan-loader \
  mingw-w64-clang-x86_64-sdl3 mingw-w64-clang-x86_64-ffmpeg mingw-w64-clang-x86_64-zydis

./win_build.sh
```

### 2. Build Graphical Launcher
```powershell
python -m pip install pillow pyinstaller
python build_launcher.py
```

### 3. Package Portable Release & Installer
```powershell
# Create portable ZIP & SHA256 checksums
python scripts/package_release.py --version 1.0-update3

# Verify package integrity
python scripts/verify_release.py
```

---

## Open Source Licenses & Compliance

- **Project License:** [MIT License](LICENSE.txt)
- **Third-Party Components:** [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) (covers shadps4 GPL-2.0, LibAtrac9 MIT, SDL3 Zlib, Vulkan SDK Apache-2.0, AMD FidelityFX MIT, miniz MIT, Sirit BSD-2, xbyak BSD-3, Boost BSL-1.0).
- **Privacy & Telemetry Policy:** [PRIVACY.md](PRIVACY.md)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

---

## Disclaimer

*Sengoku Basara (戦国BASARA)* and *Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)* are registered trademarks of **CAPCOM CO., LTD.** This project is an independent open-source preservation initiative. No copyright infringement is intended.
