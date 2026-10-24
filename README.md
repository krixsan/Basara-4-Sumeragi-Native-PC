# Sengoku Basara 4 Sumeragi — PC Native Port (`basara_pc`)

<p align="center">
  <img src="packaging/windows/icons/basara4.ico" alt="Sengoku Basara 4 Logo" width="128" height="128" />
</p>

<p align="center">
  <a href="https://microsoft.com/windows"><img src="https://img.shields.io/badge/Platform-Windows%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" /></a>
  <a href="https://www.vulkan.org"><img src="https://img.shields.io/badge/API-Vulkan%201.3-E42528?style=for-the-badge&logo=vulkan&logoColor=white" alt="Vulkan API" /></a>
  <a href="https://en.wikipedia.org/wiki/X86-64"><img src="https://img.shields.io/badge/Architecture-x86__64%20Native%20Runtime-4B32C3?style=for-the-badge" alt="Architecture" /></a>
  <a href="https://github.com/krixsan"><img src="https://img.shields.io/badge/Author-krixsan-D4AF37?style=for-the-badge" alt="Author" /></a>
  <a href="../../releases"><img src="https://img.shields.io/badge/Release-Update%201-10B981?style=for-the-badge" alt="Release" /></a>
</p>

<p align="center">
  <b>Developed, Ported & Maintained by <a href="https://github.com/krixsan">krixsan</a></b>
</p>

A high-performance native PC runtime and Vulkan presentation engine for **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)**, bringing Capcom's legendary stylish action hack-and-slash experience natively to modern PC hardware with ultra-low latency, unlocked framerates, high-resolution rendering, and full modern gamepad ergonomics.

---

## Architecture Overview

This project provides an open-source, decoupled engine architecture designed for native binary execution without full OS virtualization overhead:

```
├── src/                  # Native OS & Platform Translation Layer
│   ├── runtime.c         # Process lifecycle, dynamic symbol dispatch & linking
│   ├── runtime_audio.c   # Multichannel ATRAC9 & PCM audio sub-engine
│   ├── runtime_pad.c     # Multi-device gamepad routing via SDL3 / XInput
│   ├── runtime_memory.c  # Direct memory mapping & virtual address space management
│   ├── runtime_thread.c  # POSIX / Orbis threading & synchronization bridge
│   └── compat_win.c      # Windows Win32 API abstraction & high-resolution timers
│
├── gpu/                  # Vulkan 1.3 High-Performance Rendering Subsystem
│   ├── shadps4/          # Graphics command processor & memory management
│   ├── shader_recompiler # Dynamic GPU shader bytecode to SPIR-V translation
│   └── shim/             # In-game telemetry overlay, configuration & menu hooks
│
├── packaging/            # Icons, manifests, and compilation resources
├── launcher.py           # Studio-grade desktop GUI launcher (PIL glassmorphism)
└── CMakeLists.txt        # Modular build configuration
```

- **`src/` (Native Execution Layer):** Bridges the game's x86_64 ELF binary calls directly to Windows Win32 / POSIX APIs, mapping memory, filesystem paths, threading primitives, and controller inputs with zero virtualization overhead.
- **`gpu/` (Vulkan 1.3 Engine):** Recompiles proprietary GPU shader bytecode into high-efficiency SPIR-V shaders, driving hardware-accelerated Vulkan pipelines with low CPU overhead and tear-free presentation.
- **`launcher.py` (Desktop Launcher):** Built from the ground up with single-canvas PIL alpha-composited glassmorphism, Windows 11 immersive dark mode title bar integration, segmented pill selectors, and instant INI configuration synchronization.

---

## Update 1 — Key Improvements

- **Audio Cutscene & BGM Synchronization:** Refactored ATRAC9 audio decoding pipelines for sample-accurate stream synchronization across opening movies and in-game dialogues, eliminating dual-track overlaps.
- **MT Framework Cascade Shadow Fix:** Stabilized cascade shadow mapping matrices across multi-tiered battlefield geometry and intense particle-heavy scenarios.
- **Shader Pipeline Stability:** Optimized SPIR-V shader compiler caching to eliminate micro-stutter during complex Musou special skill combinations.
- **Resilient VRAM Allocation:** Streamlined Vulkan memory heap management with dynamic fallback buffers, preventing memory exhaustion on high-resolution displays (1440p / 4K).
- **Studio-Grade GUI Launcher:** Completely overhauled `launcher.py` featuring authentic game hero artwork showcase, custom segmented controls, high-DPI scaling, and in-game overlay integration (`Insert` or `L3 + R3`).

---

## Key Features

- **High Framerate Presentation:** Native 60 FPS, 120 FPS, 144 FPS, and uncapped refresh rate targets.
- **Modern Display Resolutions:** Full support for 1080p, 1440p, 4K, and Ultrawide (21:9) aspect ratios.
- **In-Game Settings Overlay:** Real-time on-the-fly configuration menu accessible via `Insert` key or `L3 + R3` gamepad shortcut.
- **Comprehensive Gamepad Support:** Native plug-and-play compatibility with PlayStation DualSense, DualShock 4, Xbox Wireless Controllers, and Nintendo Switch Pro Controllers via SDL3.
- **Local Multiplayer:** Built-in multi-controller routing supporting up to 4 players simultaneously on a single PC.

---

## Quick Start for Players

### System Requirements
| Component | Minimum | Recommended |
|---|---|---|
| **OS** | Windows 10 (64-bit) | Windows 11 (64-bit) |
| **Processor** | 4-Core / 8-Thread x86_64 CPU | 6-Core / 12-Thread x86_64 CPU (Zen 3 / Intel 12th Gen+) |
| **Memory** | 8 GB RAM | 16 GB Dual-Channel RAM |
| **Graphics** | Vulkan 1.3 GPU (GTX 1060 6GB / RX 580) | RTX 2060 / RX 6600 or higher |
| **Storage** | 25 GB available space | NVMe / SATA SSD |

### Installation Steps
1. Download **`Basara4_Sumeragi_PC_Update1.zip`** from the [Releases](../../releases) tab.
2. Extract all contents of the ZIP package into your desired game installation folder.
3. Place your legally dumped game assets (`app0` or `extracted_game/app0`) and boot binary alongside `basara_pc.exe`.
4. Run **`launcher.py`** (or **`Basara4_Launcher.exe`** / **`Play_Basara4.bat`**).
5. Click **PLAY GAME** and dive straight into the battlefield!

---

## Configuration (`basara.ini`)

All preferences configured via the GUI Launcher or in-game overlay are automatically saved to `basara.ini`:

| Key | Default | Description |
|---|---|---|
| `output_res` | `1920x1080` | Window and display presentation resolution |
| `render_res` | `1080` | Internal rendering target resolution (`720`, `1080`, `1440`, `2160`) |
| `fullscreen` | `1` | `1` for borderless/exclusive fullscreen, `0` for windowed mode |
| `fps_limit` | `144` | Target framerate limit (`60`, `120`, `144`, `240`) |
| `skip_intro` | `0` | `1` to bypass opening logo/movie directly to title menu |
| `show_fps` | `1` | `1` to display on-screen FPS and performance metrics |

---

## Building from Source

To compile the runtime and Vulkan renderer from source on Windows:

```powershell
# Prerequisites: CMake 3.24+, Visual Studio 2022 (MSVC v143), Vulkan SDK 1.3+
git clone https://github.com/krixsan/Basara-4-Sumeragi-Native-PC.git
cd Basara-4-Sumeragi-Native-PC

# Configure and generate build files
cmake -B build -G "Visual Studio 17 2022" -A x64

# Compile Release binary
cmake --build build --config Release --target basara_pc
```

---

## Disclaimer & Legal Notice

This project is an independent, non-commercial fan-developed compatibility and preservation initiative.
- **Sengoku Basara (戦国BASARA)** and **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)** are registered trademarks of **CAPCOM Co., Ltd.**
- This repository and its release binaries **do not distribute any copyrighted game assets, audio tracks, cinematic video streams, textures, or proprietary game binaries**.
- Users must dump and provide their own legally obtained copy of the original PlayStation 4 game disc or digital purchase.
- All code contributed to this repository is licensed for research, interoperability, and personal preservation purposes.
