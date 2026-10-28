//  SPDX-FileCopyrightText: Copyright 2026 shadPS4 Emulator Project
//  SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"

#include <vk_mem_alloc.h>

namespace Vulkan {
class Frame;
}

namespace Vulkan::HostPasses {

class FxaaPass {
public:
    struct Settings {
        float subpix_quality = 0.75f;
        float edge_threshold = 0.166f;
        float edge_threshold_min = 0.0833f;
        u32 _pad = 0;
    };

    void Create(vk::Device device, VmaAllocator allocator, vk::Format surface_format);

    void Render(vk::CommandBuffer cmdbuf, vk::ImageView input, vk::Extent2D input_size,
                Frame& output, Settings settings);

private:
    vk::UniquePipeline pipeline{};
    vk::UniquePipelineLayout pipeline_layout{};
    vk::UniqueDescriptorSetLayout desc_set_layout{};
    vk::UniqueSampler sampler{};
    vk::Image m_temp_image{};
    vk::UniqueImageView m_temp_view{};
    VmaAllocation m_temp_allocation{};
    vk::Extent2D m_temp_extent{vk::Extent2D{0, 0}};
    vk::Device m_device{};
    vk::Format m_format{};
    VmaAllocator m_allocator{};
};

} // namespace Vulkan::HostPasses
