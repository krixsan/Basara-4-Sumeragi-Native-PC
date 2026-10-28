//  SPDX-FileCopyrightText: Copyright 2026 shadPS4 Emulator Project
//  SPDX-License-Identifier: GPL-2.0-or-later

#include "video_core/renderer_vulkan/host_passes/fxaa_pass.h"

#include "common/assert.h"
#include "core/emulator_settings.h"
#include "video_core/host_shaders/fxaa_vert.h"
#include "video_core/host_shaders/fxaa_frag.h"
#include "video_core/renderer_vulkan/vk_platform.h"
#include "video_core/renderer_vulkan/vk_presenter.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"

#include <boost/container/static_vector.hpp>
#include <vk_mem_alloc.h>

namespace Vulkan::HostPasses {

void FxaaPass::Create(vk::Device device, VmaAllocator allocator, const vk::Format surface_format) {
    m_device = device;
    m_allocator = allocator;
    m_format = surface_format;
    boost::container::static_vector<vk::DescriptorSetLayoutBinding, 1> bindings{
        {
            .binding = 0,
            .descriptorType = vk::DescriptorType::eCombinedImageSampler,
            .descriptorCount = 1,
            .stageFlags = vk::ShaderStageFlagBits::eFragment,
        },
    };

    const vk::DescriptorSetLayoutCreateInfo desc_layout_ci{
        .flags = vk::DescriptorSetLayoutCreateFlagBits::ePushDescriptorKHR,
        .bindingCount = static_cast<u32>(bindings.size()),
        .pBindings = bindings.data(),
    };

    desc_set_layout = Check<"create fxaa descriptor set layout">(
        device.createDescriptorSetLayoutUnique(desc_layout_ci));

    const vk::PushConstantRange push_constants{
        .stageFlags = vk::ShaderStageFlagBits::eFragment,
        .offset = 0,
        .size = sizeof(Settings) + sizeof(float) * 4,  // Settings + texelSize
    };

    const auto& vs_module = CompileSPV(FXAA_VERT, device);
    ASSERT(vs_module);
    SetObjectName(device, vs_module, "fxaa.vert");

    const auto& fs_module = CompileSPV(FXAA_FRAG, device);
    ASSERT(fs_module);
    SetObjectName(device, fs_module, "fxaa.frag");

    const std::array shaders_ci{
        vk::PipelineShaderStageCreateInfo{
            .stage = vk::ShaderStageFlagBits::eVertex,
            .module = vs_module,
            .pName = "main",
        },
        vk::PipelineShaderStageCreateInfo{
            .stage = vk::ShaderStageFlagBits::eFragment,
            .module = fs_module,
            .pName = "main",
        },
    };

    const vk::PipelineLayoutCreateInfo layout_info{
        .setLayoutCount = 1U,
        .pSetLayouts = &*desc_set_layout,
        .pushConstantRangeCount = 1,
        .pPushConstantRanges = &push_constants,
    };

    pipeline_layout =
        Check<"create fxaa pipeline layout">(device.createPipelineLayoutUnique(layout_info));

    const std::array fxaa_color_formats{
        surface_format,
    };
    const vk::PipelineRenderingCreateInfo pipeline_rendering_ci{
        .colorAttachmentCount = fxaa_color_formats.size(),
        .pColorAttachmentFormats = fxaa_color_formats.data(),
    };

    const vk::PipelineVertexInputStateCreateInfo vertex_input_info{
        .vertexBindingDescriptionCount = 0u,
        .vertexAttributeDescriptionCount = 0u,
    };

    const vk::PipelineInputAssemblyStateCreateInfo input_assembly{
        .topology = vk::PrimitiveTopology::eTriangleList,
    };

    const vk::Viewport viewport{
        .x = 0.0f,
        .y = 0.0f,
        .width = 1.0f,
        .height = 1.0f,
        .minDepth = 0.0f,
        .maxDepth = 1.0f,
    };

    const vk::Rect2D scissor = {
        .offset = {0, 0},
        .extent = {1, 1},
    };

    const vk::PipelineViewportStateCreateInfo viewport_info{
        .viewportCount = 1,
        .pViewports = &viewport,
        .scissorCount = 1,
        .pScissors = &scissor,
    };

    const vk::PipelineRasterizationStateCreateInfo raster_state{
        .depthClampEnable = false,
        .rasterizerDiscardEnable = false,
        .polygonMode = vk::PolygonMode::eFill,
        .cullMode = vk::CullModeFlagBits::eNone,
        .frontFace = vk::FrontFace::eClockwise,
        .depthBiasEnable = false,
        .lineWidth = 1.0f,
    };

    const vk::PipelineMultisampleStateCreateInfo multisampling{
        .rasterizationSamples = vk::SampleCountFlagBits::e1,
    };

    const std::array attachments{
        vk::PipelineColorBlendAttachmentState{
            .blendEnable = false,
            .colorWriteMask = vk::ColorComponentFlagBits::eR | vk::ColorComponentFlagBits::eG |
                              vk::ColorComponentFlagBits::eB | vk::ColorComponentFlagBits::eA,
        },
    };

    const vk::PipelineColorBlendStateCreateInfo color_blending{
        .logicOpEnable = false,
        .logicOp = vk::LogicOp::eCopy,
        .attachmentCount = attachments.size(),
        .pAttachments = attachments.data(),
        .blendConstants = std::array{1.0f, 1.0f, 1.0f, 1.0f},
    };

    const std::array dynamic_states{
        vk::DynamicState::eViewport,
        vk::DynamicState::eScissor,
    };

    const vk::PipelineDynamicStateCreateInfo dynamic_info{
        .dynamicStateCount = dynamic_states.size(),
        .pDynamicStates = dynamic_states.data(),
    };

    const vk::GraphicsPipelineCreateInfo pipeline_info{
        .pNext = &pipeline_rendering_ci,
        .stageCount = shaders_ci.size(),
        .pStages = shaders_ci.data(),
        .pVertexInputState = &vertex_input_info,
        .pInputAssemblyState = &input_assembly,
        .pViewportState = &viewport_info,
        .pRasterizationState = &raster_state,
        .pMultisampleState = &multisampling,
        .pColorBlendState = &color_blending,
        .pDynamicState = &dynamic_info,
        .layout = *pipeline_layout,
    };

    pipeline = Check<"create fxaa pipeline">(device.createGraphicsPipelineUnique(
        /*pipeline_cache*/ {}, pipeline_info));

    device.destroyShaderModule(vs_module);
    device.destroyShaderModule(fs_module);

    const vk::SamplerCreateInfo sampler_ci{
        .magFilter = vk::Filter::eLinear,
        .minFilter = vk::Filter::eLinear,
        .mipmapMode = vk::SamplerMipmapMode::eNearest,
        .addressModeU = vk::SamplerAddressMode::eClampToEdge,
        .addressModeV = vk::SamplerAddressMode::eClampToEdge,
    };
    sampler = Check<"create fxaa sampler">(device.createSamplerUnique(sampler_ci));
}

void FxaaPass::Render(vk::CommandBuffer cmdbuf, vk::ImageView input,
                      vk::Extent2D input_size, Frame& frame, Settings settings) {
    if (EmulatorSettings.IsVkHostMarkersEnabled()) {
        cmdbuf.beginDebugUtilsLabelEXT(vk::DebugUtilsLabelEXT{
            .pLabelName = "Host/FXAA",
        });
    }

    const vk::Extent2D extent{frame.width, frame.height};
    
    // Allocate temp image if needed (same size/format as output)
    if (m_temp_extent.width != extent.width || m_temp_extent.height != extent.height || !m_temp_image) {
        // Clean up old allocation
        if (m_temp_image && m_temp_allocation) {
            vmaDestroyImage(m_allocator, m_temp_image, m_temp_allocation);
        }
        m_temp_view.reset();
        m_temp_extent = extent;
        
        const vk::ImageCreateInfo img_ci{
            .imageType = vk::ImageType::e2D,
            .format = m_format,
            .extent = {extent.width, extent.height, 1},
            .mipLevels = 1,
            .arrayLayers = 1,
            .samples = vk::SampleCountFlagBits::e1,
            .tiling = vk::ImageTiling::eOptimal,
            .usage = vk::ImageUsageFlagBits::eColorAttachment 
                   | vk::ImageUsageFlagBits::eSampled
                   | vk::ImageUsageFlagBits::eTransferSrc,
            .initialLayout = vk::ImageLayout::eUndefined,
        };
        
        const VmaAllocationCreateInfo alloc_ci{
            .flags = VMA_ALLOCATION_CREATE_WITHIN_BUDGET_BIT,
            .usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE,
        };
        
        VkImage unsafe_image{};
        VkImageCreateInfo unsafe_img_ci = static_cast<VkImageCreateInfo>(img_ci);
        vmaCreateImage(m_allocator, &unsafe_img_ci, &alloc_ci, &unsafe_image, &m_temp_allocation, nullptr);
        m_temp_image = vk::Image{unsafe_image};
        
        const vk::ImageViewCreateInfo view_ci{
            .image = m_temp_image,
            .viewType = vk::ImageViewType::e2D,
            .format = m_format,
            .subresourceRange = {
                .aspectMask = vk::ImageAspectFlagBits::eColor,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };
        m_temp_view = Check<"create fxaa temp view">(m_device.createImageViewUnique(view_ci));
    }

    constexpr vk::ImageSubresourceRange simple_subresource = {
        .aspectMask = vk::ImageAspectFlagBits::eColor,
        .levelCount = 1,
        .layerCount = 1,
    };

    // Transition input (frame.image) to ShaderReadOnly for sampling
    const std::array pre_barriers{
        vk::ImageMemoryBarrier2{
            .srcStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
            .srcAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
            .dstStageMask = vk::PipelineStageFlagBits2::eFragmentShader,
            .dstAccessMask = vk::AccessFlagBits2::eShaderRead,
            .oldLayout = vk::ImageLayout::eGeneral,
            .newLayout = vk::ImageLayout::eShaderReadOnlyOptimal,
            .image = frame.image,
            .subresourceRange = simple_subresource,
        },
        vk::ImageMemoryBarrier2{
            .srcStageMask = vk::PipelineStageFlagBits2::eTopOfPipe,
            .srcAccessMask = vk::AccessFlagBits2::eNone,
            .dstStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
            .dstAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
            .oldLayout = vk::ImageLayout::eUndefined,
            .newLayout = vk::ImageLayout::eColorAttachmentOptimal,
            .image = m_temp_image,
            .subresourceRange = simple_subresource,
        },
    };
    cmdbuf.pipelineBarrier2(vk::DependencyInfo{
        .imageMemoryBarrierCount = static_cast<u32>(pre_barriers.size()),
        .pImageMemoryBarriers = pre_barriers.data(),
    });

    // Render FXAA: sample frame.image, write to m_temp_image
    const std::array<vk::RenderingAttachmentInfo, 1> attachments{{
        {
            .imageView = *m_temp_view,
            .imageLayout = vk::ImageLayout::eColorAttachmentOptimal,
            .loadOp = vk::AttachmentLoadOp::eDontCare,
            .storeOp = vk::AttachmentStoreOp::eStore,
        },
    }};
    const vk::RenderingInfo rendering_info{
        .renderArea{
            .extent{
                .width = frame.width,
                .height = frame.height,
            },
        },
        .layerCount = 1,
        .colorAttachmentCount = attachments.size(),
        .pColorAttachments = attachments.data(),
    };

    vk::DescriptorImageInfo image_info{
        .sampler = *sampler,
        .imageView = input,
        .imageLayout = vk::ImageLayout::eShaderReadOnlyOptimal,
    };

    const std::array set_writes{
        vk::WriteDescriptorSet{
            .dstSet = VK_NULL_HANDLE,
            .dstBinding = 0,
            .dstArrayElement = 0,
            .descriptorCount = 1,
            .descriptorType = vk::DescriptorType::eCombinedImageSampler,
            .pImageInfo = &image_info,
        },
    };

    cmdbuf.bindPipeline(vk::PipelineBindPoint::eGraphics, *pipeline);

    const std::array viewports = {
        vk::Viewport{
            .width = static_cast<float>(frame.width),
            .height = static_cast<float>(frame.height),
            .minDepth = 0.0f,
            .maxDepth = 1.0f,
        },
    };

    cmdbuf.setViewport(0, viewports);
    cmdbuf.setScissor(0, vk::Rect2D{
                             .extent{
                                 .width = frame.width,
                                 .height = frame.height,
                             },
                         });

    cmdbuf.pushDescriptorSetKHR(vk::PipelineBindPoint::eGraphics, *pipeline_layout, 0, set_writes);

    struct PushConstants {
        float texel_size_x;       // 1.0f / width   (offset 0)
        float texel_size_y;       // 1.0f / height  (offset 4)
        float width;              // actual width   (offset 8)
        float height;             // actual height  (offset 12)
        float subpix;             // 0.75f          (offset 16)
        float edge_threshold;     // 0.166f         (offset 20)
        float edge_threshold_min; // 0.0833f        (offset 24)
        float _pad;               // 0.0f           (offset 28)
    };

    PushConstants pc = {
        .texel_size_x = 1.0f / static_cast<float>(input_size.width),
        .texel_size_y = 1.0f / static_cast<float>(input_size.height),
        .width = static_cast<float>(input_size.width),
        .height = static_cast<float>(input_size.height),
        .subpix = settings.subpix_quality,
        .edge_threshold = settings.edge_threshold,
        .edge_threshold_min = settings.edge_threshold_min,
        ._pad = 0.0f,
    };

    cmdbuf.pushConstants(*pipeline_layout, vk::ShaderStageFlagBits::eFragment, 0, sizeof(pc), &pc);

    cmdbuf.beginRendering(rendering_info);
    cmdbuf.draw(3, 1, 0, 0);
    cmdbuf.endRendering();

    // Transition temp to TransferSrc, frame.image to TransferDst, blit back
    const std::array blit_barriers{
        vk::ImageMemoryBarrier2{
            .srcStageMask = vk::PipelineStageFlagBits2::eColorAttachmentOutput,
            .srcAccessMask = vk::AccessFlagBits2::eColorAttachmentWrite,
            .dstStageMask = vk::PipelineStageFlagBits2::eTransfer,
            .dstAccessMask = vk::AccessFlagBits2::eTransferRead,
            .oldLayout = vk::ImageLayout::eColorAttachmentOptimal,
            .newLayout = vk::ImageLayout::eTransferSrcOptimal,
            .image = m_temp_image,
            .subresourceRange = simple_subresource,
        },
        vk::ImageMemoryBarrier2{
            .srcStageMask = vk::PipelineStageFlagBits2::eFragmentShader,
            .srcAccessMask = vk::AccessFlagBits2::eShaderRead,
            .dstStageMask = vk::PipelineStageFlagBits2::eTransfer,
            .dstAccessMask = vk::AccessFlagBits2::eTransferWrite,
            .oldLayout = vk::ImageLayout::eShaderReadOnlyOptimal,
            .newLayout = vk::ImageLayout::eTransferDstOptimal,
            .image = frame.image,
            .subresourceRange = simple_subresource,
        },
    };
    cmdbuf.pipelineBarrier2(vk::DependencyInfo{
        .imageMemoryBarrierCount = static_cast<u32>(blit_barriers.size()),
        .pImageMemoryBarriers = blit_barriers.data(),
    });

    const vk::ImageBlit blit_region{
        .srcSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
        .srcOffsets = std::array{
            vk::Offset3D{0, 0, 0},
            vk::Offset3D{s32(frame.width), s32(frame.height), 1}
        },
        .dstSubresource = {vk::ImageAspectFlagBits::eColor, 0, 0, 1},
        .dstOffsets = std::array{
            vk::Offset3D{0, 0, 0},
            vk::Offset3D{s32(frame.width), s32(frame.height), 1}
        },
    };

    cmdbuf.blitImage(m_temp_image, vk::ImageLayout::eTransferSrcOptimal,
                     frame.image, vk::ImageLayout::eTransferDstOptimal,
                     blit_region, vk::Filter::eLinear);

    // Transition frame.image back to General for next pass
    const auto post_barrier = vk::ImageMemoryBarrier2{
        .srcStageMask = vk::PipelineStageFlagBits2::eTransfer,
        .srcAccessMask = vk::AccessFlagBits2::eTransferWrite,
        .dstStageMask = vk::PipelineStageFlagBits2::eAllCommands,
        .dstAccessMask = vk::AccessFlagBits2::eNone,
        .oldLayout = vk::ImageLayout::eTransferDstOptimal,
        .newLayout = vk::ImageLayout::eGeneral,
        .image = frame.image,
        .subresourceRange = simple_subresource,
    };

    cmdbuf.pipelineBarrier2(vk::DependencyInfo{
        .imageMemoryBarrierCount = 1,
        .pImageMemoryBarriers = &post_barrier,
    });

    if (EmulatorSettings.IsVkHostMarkersEnabled()) {
        cmdbuf.endDebugUtilsLabelEXT();
    }
}

} // namespace Vulkan::HostPasses
