# Sengoku Basara 4 Sumeragi — PC Native Port (`basara_pc`)

[![Release](https://img.shields.io/badge/Release-Update%201-blue.svg)](../../releases)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-0078D6.svg)](https://microsoft.com/windows)
[![Renderer](https://img.shields.io/badge/Renderer-Vulkan%201.3-red.svg)](https://www.vulkan.org)

A high-performance native PC port for **Sengoku Basara 4 Sumeragi (戦国BASARA4 皇)**, bringing Capcom's legendary stylish action hack-and-slash experience to modern PC hardware.

---

## Key Features

- **High Framerate Action**: Smooth 60 FPS and uncapped framerate options.
- **Modern Display Resolutions**: Crisp native rendering with support for 1080p, 1440p, 4K, and Ultrawide (21:9) monitors.
- **Real-Time Graphics Customization**: Built-in in-game settings overlay (`Insert` key or `L3 + R3` on gamepad).
- **Extensive Controller Support**: Seamless integration for DualSense, DualShock 4, Xbox, and Nintendo Switch Pro controllers via SDL3.
- **Split-Screen Multiplayer**: Native multi-controller routing supporting up to 4 players.

---

## Update 1 Changelog

- **Audio & Cutscene Synchronization**: Fixed opening movie and in-game cutscene audio playback and synchronization; eliminated dual soundtrack overlap.
- **Shadow & Lighting Fidelity**: Enhanced dynamic shadow rendering quality and stability across all battle stages and character models.
- **Combat & Stability Improvements**: Fixed crashes during intensive combat encounters, character switching, and heavy alpha particle effects.
- **In-Game Settings Overlay**: Added on-the-fly configuration overlay accessible via `Insert` or `L3 + R3` on gamepad.
- **Refined Branding & Defaults**: Integrated authentic Sengoku Basara 4 application icon, updated executable metadata, and consolidated configuration via `basara.ini`.

---

## How to Play

### Requirements
- **OS**: Windows 10 or Windows 11 (64-bit)
- **Processor**: 4-core / 8-thread x86_64 CPU (6-core recommended)
- **Memory**: 8 GB RAM minimum (16 GB recommended)
- **Graphics**: Vulkan 1.3 compatible GPU (NVIDIA GeForce GTX 1060 / AMD Radeon RX 580 or higher)

### Setup Instructions
1. Download **`Basara4_Sumeragi_PC_Update1.zip`** from the [GitHub Releases](../../releases) page.
2. Extract all contents of the zip file into your game installation directory.
3. Place your legally dumped game data (`app0` or `extracted_game/app0`) and boot image alongside the executable.
4. *(Optional)* Customize graphics and display preferences via the GUI Launcher or in `basara.ini`.
5. Double-click **`Basara4_Launcher.exe`** (or **`Play_Basara4.bat`**) to start the game!

### Controls & Overlay Shortcut
- **Settings Overlay**: Press **`Insert`** on your keyboard or press **`L3 + R3`** simultaneously on your gamepad.
- **Menu Navigation**: Use D-Pad or Mouse to adjust settings in real time.

---

## Configuration (`basara.ini`)

All graphics and display preferences are automatically saved to `basara.ini`. You can also configure them beforehand:

| Parameter | Default | Description |
|---|---|---|
| `fullscreen` | `1` | `1` for Fullscreen, `0` for Windowed |
| `fps_limit` | `144` | Target framerate cap (`60`, `120`, `144`, etc.) |
| `show_fps` | `1` | Shows in-game FPS counter in the corner |
| `output_res` | `1920x1080` | Window and display presentation resolution |
| `render_res` | `1080` | Internal rendering target resolution |

---

## Disclaimer & Legal Notice

This project is a non-commercial fan-developed port created for preservation and research purposes.
- **Sengoku Basara (戦国BASARA)** is a registered trademark of **CAPCOM Co., Ltd.**
- This repository and its releases **do not distribute any copyrighted game assets, audio files, textures, videos, or game executables**.
- Users must dump and provide their own legally purchased copy of the original PlayStation 4 game disc or digital purchase.
