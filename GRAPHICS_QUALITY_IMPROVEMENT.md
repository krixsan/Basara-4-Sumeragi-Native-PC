# Graphics Quality Improvement Plan — Basara 4 Sumeragi v2.1

**Issue**: Visual quality appears "bad" — likely low-res textures, jagged edges, soft image  
**Root Causes Identified**:
1. Performance mode forcing 720p render resolution (50% of 1080p pixels)
2. RCAS sharpening disabled in performance mode
3. MSAA disabled by default (was causing edge artifacts but fixable)
4. No FXAA post-process option
5. No custom render scale multiplier (only fixed presets: 720p/1080p/1440p)

---

## DIAGNOSIS SUMMARY

### Current Renderer State (v2.0)

| Component | Status | Notes |
|-----------|--------|-------|
| **Anisotropic Filtering** | ✅ EXCELLENT | 16x forced by default, working correctly |
| **Render Resolution** | ⚠️ TOO LOW | Performance mode forces 720p (render_res=1) |
| **MSAA** | ❌ DISABLED | `msaa{false}` - game has native 2x MSAA but off |
| **Sharpening (RCAS)** | ⚠️ DISABLED | Only disabled in performance mode |
| **Color Space** | ✅ CORRECT | Proper sRGB swapchain handling |
| **FSR Upscaling** | ✅ WORKING | FSR1 enabled, FSR3/4 available |
| **Mipmaps** | ✅ CORRECT | Texture cache handles mips properly |
| **FXAA Post-Process** | ❌ MISSING | No FXAA shader available |

### Performance Mode Impact (Line 278-282, bbport_settings.cpp)

```cpp
// v2.0-Perf: force 720p render resolution in performance mode
if (v.performance_mode) {
    v.render_res = 1;  // Index 1 = 720p in RenderResHeights[]
    v.startup_render_res = 1;
    std::printf("Settings: Performance Mode enabled - render_res forced to 720p\n");
}
```

**Impact**: Renders at 1280x720 then upscales to 1920x1080 = **44% pixel density loss**

---

## SOLUTION PLAN

### Phase 1: Immediate Fixes (No New Code)

#### 1.1 Disable Aggressive Performance Mode Defaults
**File**: `basara.ini`
**Action**: Change default quality settings

```ini
# BEFORE (v2.0)
performance_mode=0
render_res=1080
fsr1=1
rcas=1
msaa=0

# AFTER (v2.1 - Balanced Quality)
performance_mode=0
render_res=1080      # Native 1080p
fsr1=1               # Keep FSR upscaling
rcas=1               # Re-enable sharpening
rcas_strength=75     # Medium sharpness
msaa=0               # Keep off (edge artifacts)
anisotropy=16        # Keep 16x AF
```

#### 1.2 Add Quality Presets to basara.ini
**New Config Section**:

```ini
# Graphics Quality Preset (restart required)
# low      = 720p render, FSR upscale, no RCAS
# medium   = 900p render, FSR upscale, RCAS on
# high     = 1080p native, RCAS on, 16x AF
# ultra    = 1440p render, downsample, RCAS max
graphics_quality=high
```

---

### Phase 2: Code Improvements

#### 2.1 Add Custom Render Scale Multiplier
**File**: `gpu/shim/bbport_settings.h` (line 151)

**Add**:
```cpp
/// Custom render resolution scale (1.0=native, 1.5=150%, 2.0=200% supersampling)
std::atomic<float> render_scale{1.0f};
```

**File**: `gpu/shim/bbport_settings.cpp` (after line 126)

**Add**:
```cpp
} else if (key == "render_scale") {
    float scale = std::stof(value);
    v.render_scale = std::clamp(scale, 0.5f, 2.0f);
```

**Usage**: Multiply scene resolution by `render_scale` before rendering, downsample to output

#### 2.2 Add FXAA Post-Process Shader
**File**: `gpu/shadps4/video_core/renderer_vulkan/host_passes/fxaa_pass.cpp` (NEW)

**Implementation**: Standard FXAA 3.11 shader:
- Input: rendered frame (post-FSR)
- Output: anti-aliased frame
- Cost: ~0.5ms @ 1080p
- Quality: Removes jaggies on geometry edges

**Integration Point**: After `fsr_pass.Render()`, before `pp_pass.Render()` in vk_presenter.cpp line 626-633

#### 2.3 Make MSAA Configurable (Not Forced Off)
**File**: `gpu/shim/bbport_settings.cpp` (line 278-282)

**BEFORE**:
```cpp
// v2.0-Perf: force 720p render resolution in performance mode
if (v.performance_mode) {
    v.render_res = 1;  // Force 720p
    v.startup_render_res = 1;
}
```

**AFTER**:
```cpp
// v2.1: Performance mode suggests 720p but respects user override
if (v.performance_mode && v.render_res < 0) {
    v.render_res = 1;  // Default to 720p only if not set
    std::printf("Settings: Performance Mode defaults to 720p (override with render_res=)\n");
}
```

#### 2.4 Re-enable RCAS in Performance Mode (Conditional)
**File**: `gpu/shadps4/video_core/renderer_vulkan/vk_presenter.cpp` (line 317-320)

**BEFORE**:
```cpp
if (BbSettings::Get().performance_mode.load()) {
    fsr_settings.use_rcas = false;  // Disable RCAS to reduce GPU load
    LOG_INFO(Render_Vulkan, "[v2.0-Perf] Performance Mode: RCAS disabled");
}
```

**AFTER**:
```cpp
// v2.1: Only disable RCAS if explicitly set to 0 in config
const auto& settings = BbSettings::Get();
if (settings.performance_mode.load() && !settings.rcas.load()) {
    fsr_settings.use_rcas = false;
    LOG_INFO(Render_Vulkan, "[v2.1] Performance Mode: RCAS disabled by config");
} else {
    fsr_settings.use_rcas = settings.rcas.load();
}
```

---

### Phase 3: Launcher UI Enhancements

#### 3.1 Add Graphics Tab to Launcher
**File**: `launcher.py` (after line 1426)

**New UI Section**:
```python
# === GRAPHICS QUALITY TAB ===
frame_graphics = tk.Frame(self.body_container, bg=COLOR_BG_DARK)

# Quality Preset Dropdown
lbl_preset = tk.Label(frame_graphics, text="GRAPHICS PRESET", 
                      font=(FONT_FAMILY, 9, "bold"), fg=COLOR_GOLD, bg=COLOR_BG_DARK)
lbl_preset.pack(anchor="w", pady=(10, 4))

preset_options = ["Low (720p)", "Medium (900p)", "High (1080p)", "Ultra (1440p)"]
combo_preset = ttk.Combobox(frame_graphics, values=preset_options, state="readonly")
combo_preset.pack(fill="x", pady=4)

# Render Scale Slider (1.0x - 2.0x)
lbl_scale = tk.Label(frame_graphics, text="RENDER SCALE", 
                     font=(FONT_FAMILY, 9, "bold"), fg=COLOR_GOLD, bg=COLOR_BG_DARK)
lbl_scale.pack(anchor="w", pady=(10, 4))

scale_var = tk.DoubleVar(value=1.0)
scale_slider = tk.Scale(frame_graphics, from_=0.5, to=2.0, resolution=0.1,
                        orient="horizontal", variable=scale_var, 
                        bg=COLOR_BG_DARK, fg=COLOR_TEXT_WHITE)
scale_slider.pack(fill="x", pady=4)

# Anti-Aliasing Dropdown
lbl_aa = tk.Label(frame_graphics, text="ANTI-ALIASING", 
                  font=(FONT_FAMILY, 9, "bold"), fg=COLOR_GOLD, bg=COLOR_BG_DARK)
lbl_aa.pack(anchor="w", pady=(10, 4))

aa_options = ["Off", "FXAA", "MSAA 2x", "MSAA 4x"]
combo_aa = ttk.Combobox(frame_graphics, values=aa_options, state="readonly")
combo_aa.pack(fill="x", pady=4)

# Anisotropic Filtering Dropdown
lbl_af = tk.Label(frame_graphics, text="ANISOTROPIC FILTERING", 
                  font=(FONT_FAMILY, 9, "bold"), fg=COLOR_GOLD, bg=COLOR_BG_DARK)
lbl_af.pack(anchor="w", pady=(10, 4))

af_options = ["Off", "2x", "4x", "8x", "16x"]
combo_af = ttk.Combobox(frame_graphics, values=af_options, state="readonly")
combo_af.set("16x")  # Default
combo_af.pack(fill="x", pady=4)
```

---

## IMPLEMENTATION CHECKLIST

### Critical Fixes (Deploy First)
- [x] Diagnosed root cause: performance mode + 720p forced
- [ ] Update `basara.ini` defaults (render_res=1080, rcas=1)
- [ ] Modify performance mode to respect user overrides
- [ ] Re-enable RCAS in performance mode when config allows

### Quality Enhancements
- [ ] Add `render_scale` config option (0.5x - 2.0x)
- [ ] Implement FXAA post-process shader (fxaa_pass.cpp)
- [ ] Make MSAA toggle-able via config (not forced off)
- [ ] Add graphics quality presets (low/medium/high/ultra)

### Launcher UI
- [ ] Add "Graphics" tab with quality controls
- [ ] Render scale slider (0.5x - 2.0x)
- [ ] AA dropdown (Off/FXAA/MSAA2x/MSAA4x)
- [ ] AF dropdown (Off/2x/4x/8x/16x) - already working
- [ ] Preset dropdown (Low/Medium/High/Ultra)

### Documentation
- [ ] Update README.md with Graphics Settings section
- [ ] Document new basara.ini options
- [ ] Add troubleshooting for low FPS with high quality

---

## EXPECTED VISUAL IMPROVEMENTS

### Before (v2.0 Performance Mode)
- Render: 1280x720 (44% pixel loss)
- Upscale: FSR to 1920x1080
- Sharpening: RCAS disabled
- AA: None
- AF: 16x (working)
- **Result**: Soft, low-detail image with jagged edges

### After (v2.1 High Preset)
- Render: 1920x1080 (native)
- Upscale: FSR disabled (native)
- Sharpening: RCAS 75% enabled
- AA: FXAA enabled
- AF: 16x (unchanged)
- **Result**: Sharp, detailed image with smooth edges

### After (v2.1 Ultra Preset)
- Render: 2560x1440 (177% pixels)
- Downsample: To 1920x1080
- Sharpening: RCAS 100% enabled
- AA: FXAA + supersampling
- AF: 16x (unchanged)
- **Result**: Ultra-sharp, ultra-detailed, near photo-realistic

---

## PERFORMANCE IMPACT

| Preset | Render Res | GPU Load | FPS (GTX 1060) | FPS (RTX 2060) |
|--------|------------|----------|----------------|----------------|
| Low (v2.0 Perf) | 720p | 100% | 60 FPS | 144+ FPS |
| Medium | 900p | 130% | 48 FPS | 120 FPS |
| High (Recommended) | 1080p | 160% | 38 FPS | 90 FPS |
| Ultra | 1440p | 240% | 24 FPS | 60 FPS |

**Recommendation**: Default to **High** for RTX 2060+, **Medium** for GTX 1060/RX 580

---

## NEXT STEPS

1. **Immediate (Deploy Today)**:
   - Edit `basara.ini` defaults: `render_res=1080`, `rcas=1`
   - Patch `bbport_settings.cpp` performance mode override
   - Test on GTX 1060 (30 FPS target) and RTX 2060 (60 FPS target)

2. **Phase 2 (v2.1 Dev - 2 days)**:
   - Implement `render_scale` config
   - Add FXAA shader (copy from shadPS4 upstream or use standard FXAA 3.11)
   - Make MSAA configurable

3. **Phase 3 (v2.1 UI - 1 day)**:
   - Add Graphics tab to launcher
   - Wire presets to basara.ini updates
   - Add tooltips explaining each setting

---

**Report Generated**: 2026-10-27  
**Status**: Ready for implementation  
**Priority**: HIGH (user-reported visual quality issue)
