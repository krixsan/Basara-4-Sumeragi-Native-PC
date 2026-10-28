# Sengoku Basara 4 Sumeragi PC — Release v2.0

Published: 2026-10-28

## v2.0 Release Highlights

### UI/UX
- **Premium Samurai Theme**: Complete Crimson & Gold aesthetic redesign with native tooltips, modern typography, responsive button states, and smooth layout.
- **Consolidated Control Panel**: Integrated graphics settings directly into the main launcher, eliminating popup confusion.

### Graphics
- **Render Scale**: Dynamic render resolution scaling (1.0x - 2.0x) for crisp supersampling on high-end displays.
- **RCAS Sharpening**: Granular sharpness slider (0 - 100) using AMD Robust Contrast Adaptive Sharpening.
- **Texture Filtering**: Native Anisotropic Filtering support up to 16x for enhanced surface clarity.

### Performance & FPS Unlocker
- **Dynamic Present Mode Logic**:
  - **Unlimited FPS (`fps_limit=0`)**: Automatically switches Vulkan swapchain present mode to `eImmediate` or `eMailbox`, completely eliminating V-Sync bottlenecks and allowing high-end systems to reach 120+ FPS.
  - **Capped FPS (`fps_limit=60/90/120/144`)**: Uses Vulkan `eFifo` (V-Sync) for perfectly stable frame pacing and zero micro-stutter.
- **Multi-Threading Optimization**:
  - Guest render and audio threads elevated to `THREAD_PRIORITY_HIGHEST` for zero frame drops during intense combat and 2-Player Co-op.
  - Background asset loading and worker threads set to `THREAD_PRIORITY_BELOW_NORMAL` to prevent main-thread contention.
  - Host GPU submit threads set to `High` priority with optimized Vulkan command buffer submission splits.

### Stability & Fixes
- **Cutscene Watchdog**: Enhanced watchdog auto-skips frozen video cutscenes after 3 seconds, ensuring the game loop seamlessly proceeds to gameplay without softlocks.
- **Shader Pipeline Optimization**: Default asynchronous shader compilation enabled on systems with >4 CPU cores to eliminate first-time shader compilation stutter.

### Known Issues
- **FXAA Anti-Aliasing**: Disabled in the UI ("Coming in v2.1") to prevent Vulkan driver crashes on select hardware. All other graphics features are fully operational and stable.

---

### Package Contents
- `basara_pc.exe`: High-performance native x86_64 game executable with Vulkan 1.3 rendering backend.
- `Basara4_Launcher.exe`: Premium Samurai graphical launcher and settings configurator.
- `basara.ini`: Comprehensive engine configuration file.
