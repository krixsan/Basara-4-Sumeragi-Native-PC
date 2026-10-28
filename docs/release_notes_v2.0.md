# Sengoku Basara 4 Sumeragi PC — v2.0

This major update delivers a **studio-grade user experience**, **zero-stutter performance**, and a **massive visual quality overhaul**. We have completely rebuilt the Launcher and rewritten the frame-pacing engine to eliminate micro-stutters.

---

## 🌟 What's New in v2.0

### 1. 🖥️ Graphics & Visual Quality Overhaul
The engine now handles textures and rendering significantly better:
- **Render Scale Multiplier (1.0x to 2.0x)**: Render the game at a higher internal resolution (up to 4K) and downscale it to your monitor for incredibly crisp character models and UI.
- **RCAS Sharpening Slider (0-100)**: A dedicated slider for AMD's Robust Contrast Adaptive Sharpening. Dial it to 100% to make textures pop.
- **Anisotropic Filtering (Up to 16x)**: Textures on angled surfaces (floors, walls) remain perfectly sharp from a distance.
- **Smart FSR 1.0 Integration**: FSR 1.0 and Render Scale are now mutually exclusive to prevent rendering conflicts and performance drops.

### 2. 🎨 Premium Samurai UI Redesign
- **Single-Window Launcher**: We eliminated the secondary popup window. 
- **Crimson & Gold Theme**: A brand-new aesthetic with native tooltips, smooth layout, and zero overlapping text.
- **Integrated Hub**: Change Resolution, FPS limits, and Graphics settings directly from the main screen.

### 3. 🚀 Display and Framerate Uncapping (Zero-Stutter)
- **Max FPS (`fps_limit = 0`)**: The Vulkan swapchain now uses `Immediate` or `Mailbox` presentation to bypass V-Sync, allowing 120+ FPS.
- **Locked Frametimes**: Capping at 60/90/120/144 FPS now forces hardware V-Sync (`FIFO`), locking frametimes to 16.6ms or 8.3ms for perfectly smooth gameplay.
- **Optimized Co-op**: Thread priorities have been tuned. Render threads always take priority over background loading to prevent stutters in 2-Player Local Co-op.

### 4. 🛡️ Cutscene Stall Recovery & Async Pipelines
- **Watchdog Timer**: If a cutscene freezes due to audio desync, a 3-second watchdog safely skips to the next game state.
- **Async Shader Pipelines**: CPUs with 4+ cores compile Vulkan pipelines in the background, removing the hitch when triggering Basara moves for the first time.

---

## ⚠️ Known Quirks
- **FXAA is Temporarily Disabled**: The FXAA checkbox is greyed out in this build (marked "Coming in v2.1") to prevent driver crashes. Use Render Scale 1.5x or 2.0x for excellent anti-aliasing in the meantime.
- **High VRAM Requirement**: Running 2.0x Render Scale at 4K output requires a high-end GPU (12 GB+ VRAM recommended).

---

## 📦 Installation (Same as v1.8)
1. Extract `Basara4_Sumeragi_PC_v2.0.zip` into your game directory.
2. Overwrite files when prompted.
3. Ensure you have your legal PS4 dump (`eboot.bin`, `app0/`, `sce_module/`).
4. Launch `Basara4_Launcher.exe` and click **INITIALIZE & PLAY**.
