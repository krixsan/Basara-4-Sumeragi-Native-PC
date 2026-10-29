# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2026-10-29

### Fixed
- **UI Overlap & Slider Bug**: Fixed the RCAS Sharpness slider jumping vertically when dragged. Realigned all Y-coordinates for a clean, premium layout.
- **Performance Mode Logic**: Performance Mode now correctly disables RCAS sharpening (via `BB_RCAS=0`) to ensure maximum FPS on low-end hardware.
- **Fullscreen Resolution**: Verified Exclusive Fullscreen correctly overrides the monitor's native resolution with the user's selected `output_res`.

---

## [2.0.0] - 2026-10-28

### Added
- **Render Scale Multiplier (1.0x to 2.0x)**: Added internal rendering resolution scaling for high-quality supersampling downscaled to display resolution.
- **AMD RCAS Sharpening Slider (0-100)**: Added granular control for AMD Robust Contrast Adaptive Sharpening.
- **Anisotropic Filtering**: Forced texture filtering up to 16x for surface texture clarity at oblique viewing angles.
- **Dynamic Present Mode Uncapper**: Enabled `VK_PRESENT_MODE_IMMEDIATE_KHR` and `VK_PRESENT_MODE_MAILBOX_KHR` when `fps_limit=0`, allowing framerates beyond 120 FPS on high-refresh displays.
- **Cutscene Stall Watchdog**: Integrated a 3-second watchdog timer to automatically detect frozen audio decoders and skip to the next game state without softlocking.
- **Async Shader Compilation**: Enabled asynchronous pipeline compilation by default on systems with more than 4 CPU cores to reduce first-time shader hitching.
- **Interactive Tooltips**: Added native hover tooltips across all launcher controls explaining functions and recommended values.

### Changed
- **Unified Single-Window Launcher**: Consolidated all graphics settings into the primary Crimson & Gold "Premium Samurai" interface, removing the separate popup dialog.
- **Thread Scheduling Optimization**: Elevated guest render and audio worker threads to `THREAD_PRIORITY_HIGHEST` for stable frame delivery in 2-Player Local Co-op.
- **Background Worker De-prioritization**: Set asset loading and decompression worker queues to `THREAD_PRIORITY_BELOW_NORMAL` to eliminate draw-thread contention.
- **FSR 1.0 Mutual Exclusion**: Configured the launcher to automatically disable FSR 1.0 when Render Scale is above 1.0x to prevent downscaling and upscaling conflicts.

### Fixed
- Fixed an issue where selecting "Max FPS" kept `VK_PRESENT_MODE_FIFO_KHR` active, incorrectly locking the framerate to 60 Hz.
- Resolved UI button overlapping on the bottom action bar of the launcher.
- Cleaned and removed obsolete legacy references across all source files and documentation.

### Known Issues
- FXAA checkbox is temporarily disabled in this build while descriptor set binding is updated for Vulkan 1.3 pipelines. Use Render Scale 1.5x or 2.0x for supersampling anti-aliasing.
- Render Scale 2.0x combined with 4K output requires a GPU with 12 GB or more VRAM.

---

## [1.8.0] - 2026-10-25

### Added
- **Local 2-Player Co-op Support**: Up to 4 controllers supported simultaneously with separate input assignment.
- **Press to Join Controller Routing**: Automatic assignment to prevent ghost devices and virtual controller conflicts.
- **Instance ID SDL3 Routing**: Direct hardware instance binding for gamepads.

### Fixed
- Fixed Controller 2 input hijacking Player 1 controls during gameplay.
- Resolved multiple XInput device enumerations under Windows.

---

## [1.5.0] - 2026-10-25

### Added
- **Hybrid CPU Scheduling**: Configurable process scheduling priorities (`normal`, `above_normal`, `high`) via `basara.ini`.
- **MMCSS Pro Audio Integration**: Audio feeder thread prioritization via dynamic `avrt.dll` integration with Wine/LTSC graceful fallback.
- **Minidump Crash Reporter**: Built-in 5-second minidump generation, 1000-line thread-safe log buffer, and privacy-first PII redaction.
- **Dependency Verifier**: Pre-launch checker for Vulkan 1.3, VC++ Redist 2015-2022 x64, Windows version, and disk space.
- **5-Step Setup Wizard**: Automated setup and module linker with legal fair-use verification.

### Changed
- Changed default process scheduling priority to `above_normal` to prevent thermal throttling stutters on laptops.
- Redesigned launcher with frosted glass styling and dependency status badges.

### Fixed
- Fixed audio crackling underrun issues through MMCSS Pro Audio scheduling.
- Fixed premature crash handling by allowing game SEH to handle benign hardware exceptions.
- Resolved logger deadlock conditions during fatal crash handler paths.

---

## [1.0.0] - 2026-10-24

### Added
- Initial native x86_64 PC runtime and Vulkan 1.3 renderer implementation for Sengoku Basara 4 Sumeragi.
