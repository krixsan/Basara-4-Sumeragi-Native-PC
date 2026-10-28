# Sengoku Basara 4 Sumeragi PC — v2.0

This release focuses on delivering a **studio-grade user experience**, **zero-stutter performance**, and a **massive visual quality overhaul**. We've completely rebuilt the Launcher, unlocked the framerate, and exposed deep graphics customization to make the game look as sharp as possible.

## What Changed

### 1. 🖥️ Graphics & Visual Quality Overhaul
The way the engine handles textures and rendering has been significantly upgraded:
- **Render Scale Multiplier (1.0x to 2.0x)**: You can now render the game at a higher internal resolution (up to 4K) and downscale it to your monitor. This acts as a high-quality supersampling anti-aliasing, making character models and UI incredibly crisp.
- **AMD RCAS Sharpening Slider (0-100)**: A dedicated slider to control AMD's Robust Contrast Adaptive Sharpening. Dial it up to 100% to make textures pop, or lower it for a softer, more cinematic look.
- **Anisotropic Filtering (Up to 16x)**: Textures on angled surfaces (like the ground and walls) now remain perfectly sharp from a distance, eliminating blurriness.
- **Smart FSR 1.0 Integration**: FSR 1.0 upscaling is now mutually exclusive with Render Scale. The Launcher automatically disables FSR if you are using Render Scale (and vice versa) to prevent rendering conflicts and performance drops.

### 2. 🎨 Premium Samurai UI Redesign (Single-Window Launcher)
We eliminated the secondary popup window. The Launcher now features a brand-new **Crimson & Gold "Premium Samurai" theme**.
- **Integrated Graphics Hub**: All configuration controls (Render Scale, RCAS Sharpness, AF, CPU Priority) are now directly inside the main interface.
- **Native Tooltips**: Hover over any setting to see a clear explanation of what it does.
- **Clean Layout**: No more overlapping text or duplicate files.

### 3. 🚀 Display and Framerate Uncapping (Zero-Stutter)
In v1.8, selecting "Max FPS" still locked output to 60 Hz because `VK_PRESENT_MODE_FIFO_KHR` remained forced.
- **Unlimited FPS (`fps_limit = 0`)**: The Vulkan swapchain builder now requests `VK_PRESENT_MODE_IMMEDIATE_KHR` or `VK_PRESENT_MODE_MAILBOX_KHR`. High-refresh displays can now run at 120+ FPS without an engine-level cap.
- **Fixed Targets (60, 90, 120, 144 FPS)**: The swapchain uses `FIFO` presentation, maintaining a locked **16.6ms or 8.3ms frametime cadence** to eliminate micro-stutters.

### 4. ⚙️ Thread Priority Tuning (Optimized for Co-op)
Local co-op previously suffered from micro-stutter when asset decompression interrupted the render worker.
- Render and audio guest worker threads are now set to `THREAD_PRIORITY_HIGHEST`.
- Background file loaders and worker queues drop to `THREAD_PRIORITY_BELOW_NORMAL`.
- Host GPU submission runs on an isolated worker thread to prevent main-thread stalls.

### 5. 🛡️ Cutscene Stall Recovery (Watchdog)
Video playback hangs caused by audio timestamp drift now hit a **3-second watchdog timer**. If frames fail to reach the presenter within 3 seconds, the playback loop safely skips to the next game state rather than freezing the process.

### 6. ⚡ Async Shader Pipelines
CPUs with more than 4 cores now compile Vulkan pipelines asynchronously in the background. This removes the noticeable hitch when characters trigger Basara special moves for the first time in a stage.

## Known Quirks
- **FXAA is Temporarily Disabled**: The FXAA checkbox is greyed out in this build while we restructure its descriptor set pass in the Vulkan presenter. It will return in v2.1. The game runs flawlessly without it, but you can use Render Scale 1.5x or 2.0x for excellent anti-aliasing in the meantime.
- **4K + 2.0x Render Scale**: Running 2.0x render scale at 4K output is extremely GPU-intensive. It requires a high-end GPU with **12 GB or more VRAM** to avoid running out of memory.

## Chore
- **Zero External References**: Scoured the entire codebase and documentation to remove all legacy references to external projects, ensuring a 100% clean, self-contained release.

## Installation (Same as v1.8)
1. Extract `Basara4_Sumeragi_PC_v2.0.zip` into your game directory.
2. Overwrite files when prompted.
3. Launch `Basara4_Launcher.exe` and click **INITIALIZE & PLAY**.
