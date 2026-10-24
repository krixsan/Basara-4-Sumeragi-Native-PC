// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <chrono>
#include <deque>

#include <condition_variable>
#include <mutex>

#include "core/libraries/videoout/buffer.h"
#include "video_core/renderer_vulkan/host_passes/fsr_pass.h"
#include "video_core/renderer_vulkan/host_passes/pp_pass.h"
#include "video_core/renderer_vulkan/vk_ctr_framegen.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_runtime.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/renderer_vulkan/vk_swapchain.h"
#include "video_core/texture_cache/texture_cache.h"

namespace Frontend {
class WindowSDL;
}

namespace AmdGpu {
struct Liverpool;
}

namespace Vulkan {

struct Frame {
    u32 width;
    u32 height;
    VmaAllocation allocation;
    vk::Image image;
    vk::ImageView image_view;
    vk::Fence present_done;
    vk::Semaphore ready_semaphore;
    u64 ready_tick;
    bool is_hdr{false};
    u8 id{};
    /// SacredFire: frame generation recorded a generated frame to show before this one
    /// (CtrFrameGen::OutputImage(id)); set while preparing, read when presenting.
    bool fg_ready{false};
    bool fg_hudless{false}; ///< it had a HUD-less frame (BB_FG_DUMP_TRIGGER dumps)
    /// The smoothed time between game frames when it was prepared (frame pacing).
    float fg_interval_ms{16.6f};

};

enum SchedulerType {
    Draw,
    Present,
    CpuFlip,
};

class Rasterizer;

class Presenter {
public:
    Presenter(Frontend::WindowSDL& window, AmdGpu::Liverpool* liverpool);
    ~Presenter();

    HostPasses::PostProcessingPass::Settings& GetPPSettingsRef() {
        return pp_settings;
    }

    HostPasses::FsrPass::Settings& GetFsrSettingsRef() {
        return fsr_settings;
    }

    Frontend::WindowSDL& GetWindow() const {
        return window;
    }

    Rasterizer& GetRasterizer() const {
        return *rasterizer.get();
    }

    bool IsHDRSupported() const {
        return swapchain.HasHDR();
    }

    void SetHDR(bool enable) {
        if (!IsHDRSupported()) {
            return;
        }
        swapchain.SetHDR(enable);
        pp_settings.hdr = enable ? 1 : 0;
    }

    VideoCore::Image& RegisterVideoOutSurface(
        const Libraries::VideoOut::BufferAttributeGroup& attribute, VAddr cpu_address) {
        vo_buffers_addr.emplace_back(cpu_address);
        auto desc = VideoCore::TextureCache::ImageDesc{attribute, cpu_address};
        const auto image_id = texture_cache.FindImage(desc);
        auto& image = texture_cache.GetImage(image_id);
        image.usage.vo_surface = 1u;
        return image;
    }

    bool IsVideoOutSurface(const AmdGpu::ColorBuffer& color_buffer) const;

    Frame* PrepareFrame(const Libraries::VideoOut::BufferAttributeGroup& attribute,
                        VAddr cpu_address);

    Frame* PrepareBlankFrame(bool present_thread);

    void Present(Frame* frame, bool is_reusing_frame = false, bool is_game_frame = true);
    Frame* PrepareLastFrame();

private:
    Frame* GetRenderFrame();

    void RecreateFrame(Frame* frame, u32 width, u32 height);

    void SetExpectedGameSize(s32 width, s32 height);

    /// SacredFire: frame generation for the frame being prepared (after post-processing).
    void GenerateFrame(Frame* frame, vk::Image hudless);
    /// SacredFire: the HUD-less display buffer copy (Rasterizer::GetHudless) through the same
    /// post-processing as the frame, into a frame-sized image; null when there is none.
    vk::Image PrepareHudless(Frame* frame, VAddr cpu_address, vk::Extent2D image_size,
                             vk::Format view_format);
    /// SacredFire: presents the generated frame recorded for `frame` (the half-way image
    /// between the previous game frame and this one), before the frame itself. False when it
    /// could not be presented (the frame then goes out alone).
    bool PresentGenerated(Frame* frame);

private:
    float expected_ratio{1920.0 / 1080.0f};
    u32 expected_frame_width{1920};
    u32 expected_frame_height{1080};

    Frontend::WindowSDL& window;
    Instance instance;
    HostPasses::FsrPass fsr_pass;
    HostPasses::FsrPass::Settings fsr_settings{};
    HostPasses::PostProcessingPass::Settings pp_settings{};
    HostPasses::PostProcessingPass pp_pass;
    std::mutex passes_mutex; ///< bbport: the passes are recorded on the recording threads
    AmdGpu::Liverpool* liverpool;
    Scheduler draw_scheduler;
    std::deque<u64> recent_frame_ticks; ///< bbport: BB_FRAMES_AHEAD bound (PrepareFrame)
    Scheduler present_scheduler;
    Scheduler flip_scheduler;
    Swapchain swapchain;
    Runtime runtime;
    std::unique_ptr<Rasterizer> rasterizer;
    VideoCore::TextureCache& texture_cache;
    vk::UniqueCommandPool command_pool;
    std::vector<Frame> present_frames;
    std::queue<Frame*> free_queue;
    Frame* last_submit_frame;
    std::mutex free_mutex;
    std::condition_variable free_cv;
    std::condition_variable_any frame_cv;
    std::vector<VAddr> vo_buffers_addr;

    /// SacredFire: FSR 3.1.6 frame generation (bbport.ini framegen; docs/sacredfire/16-framegen.md).
    CtrFrameGen framegen;
    std::chrono::steady_clock::time_point fg_last_prepare{};
    float fg_interval_ms = 16.6f; ///< smoothed time between game frames
    u64 fg_vector_sequence = 0;   ///< the upscaler's last vectors handed to frame generation
    u64 fg_hudless_serial = 0;    ///< the rasterizer's last HUD-less copy used
    VideoCore::UniqueImage fg_hudless_image; ///< the HUD-less frame after post-processing
    vk::ImageView fg_hudless_view{};
    u32 fg_hudless_width = 0, fg_hudless_height = 0;
    vk::Format fg_hudless_format{};
    u64 fg_flips = 0, fg_presented = 0, fg_skipped = 0;
    std::chrono::steady_clock::time_point fg_stats_since{};
};

} // namespace Vulkan
