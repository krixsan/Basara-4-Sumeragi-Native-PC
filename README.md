# Sengoku Basara 4 Sumeragi — PC Native Port (`basara_pc`)

> ⚠️ **BARU DI SINI?** Baca [Panduan Instalasi (INSTALL.md)](./INSTALL.md) dulu agar tidak gagal paham soal file `eboot.bin` dan `sce_module`!
>
> **NEW HERE?** Read the [Installation Guide](./INSTALL.md) first. You must select the **whole PS4 game folder** (`eboot.bin` + `sce_module` + `sce_sys` + game data), not just `eboot.bin`.

<p align="center">
  <img src="packaging/windows/icons/basara4.ico" alt="Sengoku Basara 4 Logo" width="128" height="128" />
</p>

<p align="center">
  <a href="https://microsoft.com/windows"><img src="https://img.shields.io/badge/Platform-Windows%2010%201809+%20/%2011%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" /></a>
  <a href="https://www.vulkan.org"><img src="https://img.shields.io/badge/API-Vulkan%201.3+-E42528?style=for-the-badge&logo=vulkan&logoColor=white" alt="Vulkan API" /></a>
  <a href="https://en.wikipedia.org/wiki/X86-64"><img src="https://img.shields.io/badge/Architecture-x86__64%20Native%20Runtime-4B32C3?style=for-the-badge" alt="Architecture" /></a>
  <a href="https://visualstudio.microsoft.com"><img src="https://img.shields.io/badge/Dependency-VC++%202015--2022%20x64-5C2D91?style=for-the-badge" alt="VC++ Redist" /></a>
  <a href="../../releases"><img src="https://img.shields.io/badge/Release-v2.0-10B981?style=for-the-badge" alt="Release" /></a>
</p>

<p align="center">
  <b>Native x86_64 PC Execution & Vulkan 1.3 Presentation Engine</b><br>
  <i>Read in: <a href="README.id.md">Bahasa Indonesia</a></i>
</p>

A high-performance native PC runtime and Vulkan presentation engine for **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)**, bringing Capcom's legendary stylish action hack-and-slash experience natively to modern PC hardware with ultra-low latency, unlocked framerates, high-resolution rendering, and modern gamepad ergonomics.

---

## Key Features

- **Native x86_64 Performance**: Direct binary execution on modern 64-bit Windows PCs without emulator overhead.
- **Modern Vulkan Rendering**: Smooth graphics pipeline designed for low latency and high stability.
- **Framerate Unlocking (120+ FPS)**: High-refresh display support that completely unbinds the 60 FPS lock, with smooth frame pacing for fixed targets (60, 90, 120, 144 FPS).
- **High-Definition Visuals**: Built-in render scale supersampling (1.0x to 2.0x), AMD RCAS contrast-adaptive sharpening, and 16x Anisotropic Filtering for crystal-clear textures.
- **Single-Window Samurai Launcher**: Unified Crimson & Gold launcher with integrated graphics controls, native tooltips, and automatic dependency verification.
- **Seamless Local 2-Player Co-op**: Optimized thread scheduling eliminates micro-stutters and frame drops during intense split-screen battles.
- **Cutscene Stall Recovery**: Integrated watchdog timer automatically recovers from frozen cutscenes without interrupting your game session.

---

## Quick Start (5 Steps — Under 10 Minutes)

### 1. Download & Extract

Get **v2.0 or newer** from the [Releases](../../releases) tab:
- **Portable ZIP:** `Basara4_Sumeragi_PC_v2.0.zip` (Extract to a standard directory such as `D:\Games\Basara4_Sumeragi_PC`; do not run inside the ZIP or in `Program Files`).

### 2. Open the Launcher

Run **`Basara4_Launcher.exe`**.
- The built-in dependency engine verifies **Vulkan 1.3 loader**, **VC++ Redist 2015–2022 x64**, **Windows version**, and **Storage**.
- If any required library is missing, one-click official download links are provided.

### 3. Click Setup Wizard

Open the **5-Step Setup Wizard** (⚡ wand icon), read the fair-use notice, and accept the legal checkboxes.

### 4. Select the PS4 Game Folder (Not `eboot.bin`)

Select the folder that directly contains:
- `eboot.bin`
- `sce_module` (audio/system modules — **required**)
- `sce_sys` (`param.sfo`, icons)
- `nativePS4` (or `data`) — the game assets

Do **not** select `eboot.bin` itself. The wizard rejects folders without `sce_module` because missing modules cause crackling audio and crashes.

### 5. Wait for Auto-Build, Then Play

The wizard links the modules and creates `out/boot-linked.bin` in 15–30 seconds. When it displays **Setup Completed**, click **⚔️ Play Now** (or **Back to Launcher** → **INITIALIZE & PLAY**).

> 📖 Need pictures, folder examples, and fixes? Read the full **[Panduan Instalasi (INSTALL.md)](./INSTALL.md)**.

---

## Legal Dump Notice

> [!IMPORTANT]
> **No copyrighted Capcom assets, disc images, binaries, or encryption keys are bundled with this software.**
> 
> You must dump the **complete game folder** from your legally owned PS4: `eboot.bin`, `sce_module`, `sce_sys`, and the game data (`nativePS4` or `data`). Dumping only `eboot.bin` will cause missing audio modules, crackling sound, or crashes. Search the PS4 homebrew community for dumping tutorials.

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

### 3. Crackling / Stuttering Audio or Missing `sce_module`
- **Cause:** The selected game folder is missing `sce_module`, so native audio modules such as `libSceNgs2.sprx` and `libSceAjm.sprx` are not linked.
- **Solution:** Click **🔧 REPAIR & PLAY** in the launcher and select the **full PS4 game folder** (not `eboot.bin`). See [INSTALL.md](INSTALL.md).

### 4. Crash on Startup or Map Load
- Check `user/logs/basara.log` and `user/crashes/` for raw crash dumps (`crash_raw_*.log`).
- Telemetry & crash minidumps follow strict privacy-by-design standards with personal identifiers redacted (see [PRIVACY.md](PRIVACY.md)).
- If you only copied `eboot.bin`, re-run Setup Wizard and select the full game folder (`eboot.bin` + `sce_module` + `sce_sys` + game data).

### 5. Controller Not Recognized
- XInput controllers (Xbox, PS4/PS5 via DS4Windows/Steam) work natively.
- For generic DirectInput controllers, click **🎮 Gamepad** in the launcher toolbar to open `basara4-pad-mapper.exe` and generate `user/gamepad_mapping.txt`.

---

## Graphics & Performance Settings (`basara.ini`)

Settings can be configured directly inside the graphical launcher or by editing `basara.ini`:

```ini
# Window and display presentation resolution
output_res=1920x1080         # 1280x720 | 1920x1080 | 2560x1440 | 3840x2160

# Internal render scale multiplier (supersampling)
render_scale=1.0             # 1.0 (native) | 1.5 (supersampling) | 2.0 (ultra-sharp)

# Texture filtering quality
anisotropy=16                # 0 (off) | 2 | 4 | 8 | 16 (recommended)

# AMD RCAS sharpness strength
rcas=1                       # 0 (off) | 1 (on)
rcas_strength=75             # 0 (subtle) to 100 (aggressive)

# Framerate limit
fps_limit=144                # 60 | 90 | 120 | 144 | 240 | 0 (unlimited)

# Process CPU priority
process_priority=above_normal # normal | above_normal | high
```

### Recommended Presets

| GPU Tier | Target Resolution | Render Scale | Anisotropy | RCAS | Expected FPS |
|---|---|---|---|---|---|
| **Entry-Level** (GTX 1050, RX 560) | 1280x720 / 1080p | 1.0x | 4x | Off | 60 FPS |
| **Mid-Range** (GTX 1060, RX 580) | 1920x1080 | 1.0x | 16x | 50% | 60–90 FPS |
| **High-End** (RTX 2060, RX 6600) | 1920x1080 / 1440p | 1.5x | 16x | 75% | 90–120+ FPS |
| **Enthusiast** (RTX 3070+, RX 6800+) | 1440p / 4K | 2.0x | 16x | 75% | 120+ FPS |

---

## Open Source Licenses & Compliance

- **Project License:** [MIT License](LICENSE.txt)
- **Third-Party Components:** [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) (covers shadps4 GPL-2.0, LibAtrac9 MIT, SDL3 Zlib, Vulkan SDK Apache-2.0, AMD FidelityFX MIT, miniz MIT, Sirit BSD-2, xbyak BSD-3, Boost BSL-1.0).
- **Privacy & Telemetry Policy:** [PRIVACY.md](PRIVACY.md)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

---

## Disclaimer

*Sengoku Basara (戦国BASARA)* and *Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)* are registered trademarks of **CAPCOM CO., LTD.** This project is an independent open-source preservation initiative. No copyright infringement is intended.
