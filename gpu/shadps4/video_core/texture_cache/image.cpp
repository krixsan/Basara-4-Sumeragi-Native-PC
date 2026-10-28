// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include "bbport_toggles.h"
#include <array>
#include <ranges>
#include "common/assert.h"
#include "video_core/renderer_vulkan/liverpool_to_vk.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_runtime.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/texture_cache/blit_helper.h"
#include "video_core/texture_cache/image.h"

#include <vk_mem_alloc.h>

namespace VideoCore {

using namespace Vulkan;

Common::IncrementalIdProvider<u64> Image::global_image_uid{};

static vk::ImageUsageFlags ImageUsageFlags(const Vulkan::Instance& instance,
                                           const ImageInfo& info) {
    vk::ImageUsageFlags usage = vk::ImageUsageFlagBits::eTransferSrc |
                                vk::ImageUsageFlagBits::eTransferDst |
                                vk::ImageUsageFlagBits::eSampled;
    if (!info.props.is_block) {
        if (info.props.is_depth) {
            usage |= vk::ImageUsageFlagBits::eDepthStencilAttachment;
        } else {
            usage |= vk::ImageUsageFlagBits::eColorAttachment;
            if (instance.IsAttachmentFeedbackLoopLayoutSupported()) {
                usage |= vk::ImageUsageFlagBits::eAttachmentFeedbackLoopEXT;
            }
            // Always create images with storage flag to avoid needing re-creation in case of e.g
            // compute clears This sacrifices a bit of performance but is less work. ExtendedUsage
            // flag is also used.
            usage |= vk::ImageUsageFlagBits::eStorage;
        }
    } else {
        // Similarly to above, we specify storage usage. This is typically not supported by
        // compressed formats, but may be used for uncompressed views. In order to satisfy this,
        // we will also specify the extended usage bit.
        usage |= vk::ImageUsageFlagBits::eStorage;
    }

    return usage;
}

static vk::ImageType ConvertImageType(AmdGpu::ImageType type) noexcept {
    switch (type) {
    case AmdGpu::ImageType::Color1D:
    case AmdGpu::ImageType::Color1DArray: // engine: lowered to 2D, height 1
    case AmdGpu::ImageType::Color2D:
    case AmdGpu::ImageType::Color2DMsaa:
    case AmdGpu::ImageType::Color2DArray:
        return vk::ImageType::e2D;
    case AmdGpu::ImageType::Color3D:
        return vk::ImageType::e3D;
    default:
        UNREACHABLE();
    }
}

static vk::FormatFeatureFlags2 FormatFeatureFlags(const vk::ImageUsageFlags usage_flags) {
    vk::FormatFeatureFlags2 feature_flags{};
    if (usage_flags & vk::ImageUsageFlagBits::eTransferSrc) {
        feature_flags |= vk::FormatFeatureFlagBits2::eTransferSrc;
    }
    if (usage_flags & vk::ImageUsageFlagBits::eTransferDst) {
        feature_flags |= vk::FormatFeatureFlagBits2::eTransferDst;
    }
    if (usage_flags & vk::ImageUsageFlagBits::eSampled) {
        feature_flags |= vk::FormatFeatureFlagBits2::eSampledImage;
    }
    if (usage_flags & vk::ImageUsageFlagBits::eColorAttachment) {
        feature_flags |= vk::FormatFeatureFlagBits2::eColorAttachment;
    }
    if (usage_flags & vk::ImageUsageFlagBits::eDepthStencilAttachment) {
        feature_flags |= vk::FormatFeatureFlagBits2::eDepthStencilAttachment;
    }
    // Note: StorageImage is intentionally ignored for now since it is always set, and can mess up
    // compatibility checks.
    return feature_flags;
}

UniqueImage::~UniqueImage() {
    if (image) {
        BbStats::vk_image_bytes.fetch_sub(size_bytes, std::memory_order_relaxed);
        vmaDestroyImage(allocator, image, allocation);
    }
}

void UniqueImage::Destroy() {
    if (image) {
        BbStats::vk_image_bytes.fetch_sub(size_bytes, std::memory_order_relaxed);
        vmaDestroyImage(allocator, image, allocation);
        image = vk::Image{};
        allocation = {};
    }
}

bool UniqueImage::Create(const vk::ImageCreateInfo& image_ci, bool allow_failure) {
    this->image_ci = image_ci;
    ASSERT(!image);
    // engine: images of BB_VMA_DEDICATED_MB (4) or more get memory of their own, given back to
    // the driver when they are freed. In shared VMA blocks the texture collector's evictions left
    // holes (~0.9 GB on an RX 7800 XT) that a block only returns once wholly empty.
    static const vk::DeviceSize dedicated_from = [] {
        const char* env = std::getenv("BB_VMA_DEDICATED_MB");
        return vk::DeviceSize(env ? std::strtoull(env, nullptr, 10) : 4) << 20;
    }();
    VmaAllocationCreateFlags dedicated = 0;
    vk::DeviceSize memory_size = 0;
    if (device) {
        const vk::DeviceImageMemoryRequirements query{.pCreateInfo = &image_ci};
        memory_size = device.getImageMemoryRequirements(query).memoryRequirements.size;
        if (dedicated_from != 0 && memory_size >= dedicated_from) {
            dedicated = VMA_ALLOCATION_CREATE_DEDICATED_MEMORY_BIT;
        }
    }

    const VkImageCreateInfo image_ci_unsafe = static_cast<VkImageCreateInfo>(image_ci);
    VkImage unsafe_image{};
    VmaAllocationInfo alloc_info{};
    VkResult result = VK_SUCCESS;
    VkResult last_failure = VK_SUCCESS;

    // engine: VMA's budget check, dedicated memory and the driver's allocation can each fail
    // transiently (Windows commit pressure, another process holding VRAM). Retry with fewer
    // constraints before giving up; a fatal assert here took down the whole GPU process on a
    // 1920x1080 video-out image even though 11 GiB of VRAM were free.
    const std::array<VmaAllocationCreateFlags, 3> attempts = {
        VMA_ALLOCATION_CREATE_WITHIN_BUDGET_BIT | dedicated,
        dedicated,
        0,
    };
    for (size_t attempt = 0; attempt < attempts.size(); ++attempt) {
        const VmaAllocationCreateFlags flags = attempts[attempt];
        if (attempt != 0 && flags == attempts[attempt - 1]) {
            continue;
        }
        const VmaAllocationCreateInfo alloc_ci = {
            .flags = flags,
            .usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE,
            .requiredFlags = 0,
            .preferredFlags = 0,
            .pool = VK_NULL_HANDLE,
            .pUserData = nullptr,
        };
        unsafe_image = VK_NULL_HANDLE;
        allocation = VK_NULL_HANDLE;
        alloc_info = {};
        result = vmaCreateImage(allocator, &image_ci_unsafe, &alloc_ci, &unsafe_image,
                                &allocation, &alloc_info);
        if (result == VK_SUCCESS) {
            if (attempt != 0) {
                LOG_WARNING(Render_Vulkan,
                            "Image allocation succeeded on attempt {} (flags {:#x}) after {}",
                            attempt + 1, static_cast<u32>(flags),
                            vk::to_string(vk::Result{last_failure}));
            }
            image = vk::Image{unsafe_image};
            size_bytes = alloc_info.size;
            BbStats::vk_image_bytes.fetch_add(size_bytes, std::memory_order_relaxed);
            return true;
        }
        last_failure = result;
        LOG_WARNING(Render_Vulkan,
                    "Image allocation attempt {} failed ({}): {}x{}x{}, mips {}, layers {}, "
                    "format {}, usage {:#x}, flags {:#x}, dedicated {}, requested {} MiB",
                    attempt + 1, vk::to_string(vk::Result{result}), image_ci.extent.width,
                    image_ci.extent.height, image_ci.extent.depth, image_ci.mipLevels,
                    image_ci.arrayLayers, vk::to_string(image_ci.format),
                    static_cast<u32>(image_ci.usage), static_cast<u32>(flags),
                    static_cast<bool>(flags & VMA_ALLOCATION_CREATE_DEDICATED_MEMORY_BIT),
                    static_cast<unsigned long long>(memory_size >> 20));
    }

    // Keep the diagnostics that matter when every attempt failed. VMA's heap budgets include
    // the driver's current pressure; the requested size distinguishes a bad extent from OOM.
    std::array<VmaBudget, VK_MAX_MEMORY_HEAPS> budgets{};
    vmaGetHeapBudgets(allocator, budgets.data());
    for (u32 heap = 0; heap < VK_MAX_MEMORY_HEAPS; ++heap) {
        if (budgets[heap].budget == 0 && budgets[heap].usage == 0) {
            continue;
        }
        LOG_ERROR(Render_Vulkan, "VMA heap {}: usage {} MiB, budget {} MiB", heap,
                  static_cast<unsigned long long>(budgets[heap].usage >> 20),
                  static_cast<unsigned long long>(budgets[heap].budget >> 20));
    }
    LOG_ERROR(Render_Vulkan,
              "Failed allocating image after {} attempts: {}x{}x{}, mips {}, layers {}, format "
              "{}, usage {:#x}, dedicated {}, requested {} MiB; using the 1x1 fallback",
              attempts.size(), image_ci.extent.width, image_ci.extent.height,
              image_ci.extent.depth, image_ci.mipLevels, image_ci.arrayLayers,
              vk::to_string(image_ci.format), static_cast<u32>(image_ci.usage),
              static_cast<bool>(dedicated), static_cast<unsigned long long>(memory_size >> 20));
    if (!allow_failure) {
        ASSERT_MSG(false, "Failed allocating image with error {}",
                   vk::to_string(vk::Result{result}));
    }
    image = vk::Image{};
    allocation = VK_NULL_HANDLE;
    size_bytes = 0;
    return false;
}

Image::Image(const Vulkan::Instance& instance, Vulkan::Runtime& runtime_,
             Common::SlotVector<ImageView>& slot_image_views_, const ImageInfo& info_)
    : guest_begin{info_.guest_address}, guest_end{info_.guest_address + info_.guest_size},
      info{info_}, runtime{&runtime_}, slot_image_views{&slot_image_views_} {
    BbStats::Timer timer{BbStats::t_image_create};
    // An unsupported/unknown guest format (notably some system/font textures) used to
    // return here with `backing == nullptr`. FindView() then read backing->num_samples
    // and faulted at address 0. Give such images a real 1x1 RGBA8 backing instead.
    if (info.pixel_format == vk::Format::eUndefined || info.size.width == 0 ||
        info.size.height == 0 || info.resources.levels == 0 || info.resources.layers == 0) {
        LOG_WARNING(Render_Vulkan,
                    "Guest image {:#x}:{:#x} has no usable Vulkan format/size (format {}, {}x{}x{}, "
                    "L:{} A:{}), using the 1x1 fallback texture",
                    info.guest_address, info.guest_size, vk::to_string(info.pixel_format),
                    info.size.width, info.size.height, info.size.depth, info.resources.levels,
                    info.resources.layers);
        CreateFallback(instance);
        return;
    }

    image_uid = global_image_uid.Next();
    mip_hashes.resize(info.resources.levels);
    vk::ImageCreateFlags flags{vk::ImageCreateFlagBits::eMutableFormat |
                               vk::ImageCreateFlagBits::eExtendedUsage};
    if (info.props.is_volume) {
        flags |= vk::ImageCreateFlagBits::e2DArrayCompatible;
        if (instance.Is2dViewOf3dSupported()) {
            flags |= vk::ImageCreateFlagBits::e2DViewCompatibleEXT;
        }
    }
    if (info.props.is_block && instance.IsBlockTexelViewSupported()) {
        flags |= vk::ImageCreateFlagBits::eBlockTexelViewCompatible;
    }

    usage_flags = ImageUsageFlags(instance, info);
    format_features = FormatFeatureFlags(usage_flags);
    if (info.props.is_depth) {
        aspect_mask = vk::ImageAspectFlagBits::eDepth;
        if (info.props.has_stencil) {
            aspect_mask |= vk::ImageAspectFlagBits::eStencil;
        }
    }

    constexpr auto tiling = vk::ImageTiling::eOptimal;
    const auto supported_format = instance.GetSupportedFormat(info.pixel_format, format_features);
    if (supported_format == vk::Format::eUndefined) {
        LOG_WARNING(Render_Vulkan,
                    "Image {:#x}:{:#x} format {} is not supported by the device, using the 1x1 "
                    "fallback texture",
                    info.guest_address, info.guest_size, vk::to_string(info.pixel_format));
        CreateFallback(instance);
        return;
    }
    vk::PhysicalDeviceImageFormatInfo2 format_info{
        .format = supported_format,
        .type = ConvertImageType(info.type),
        .tiling = tiling,
        .usage = usage_flags,
        .flags = flags,
    };
    auto image_format_properties =
        instance.GetPhysicalDevice().getImageFormatProperties2(format_info);
    // engine: storage usage is speculative (see ImageUsageFlags). Drivers that refuse it for a
    // format (AMD's Windows driver for BC6H) get the image without it: creating the unsupported
    // combination anyway loses the device a few frames later.
    if (image_format_properties.result == vk::Result::eErrorFormatNotSupported &&
        (usage_flags & vk::ImageUsageFlagBits::eStorage)) {
        format_info.usage = usage_flags & ~vk::ImageUsageFlagBits::eStorage;
        image_format_properties = instance.GetPhysicalDevice().getImageFormatProperties2(format_info);
        if (image_format_properties.result == vk::Result::eSuccess) {
            usage_flags = format_info.usage;
            format_features = FormatFeatureFlags(usage_flags);
        } else {
            format_info.usage = usage_flags;
        }
    }
    if (image_format_properties.result == vk::Result::eErrorFormatNotSupported) {
        LOG_ERROR(Render_Vulkan, "image format {} type {} is not supported (flags {}, usage {})",
                  vk::to_string(supported_format), vk::to_string(format_info.type),
                  vk::to_string(format_info.flags), vk::to_string(format_info.usage));
    }
    supported_samples = image_format_properties.result == vk::Result::eSuccess
                            ? image_format_properties.value.imageFormatProperties.sampleCounts
                            : vk::SampleCountFlagBits::e1;

    const vk::ImageCreateInfo image_ci = {
        .flags = flags,
        .imageType = ConvertImageType(info.type),
        .format = supported_format,
        .extent{
            .width = info.size.width,
            .height = info.size.height,
            .depth = info.size.depth,
        },
        .mipLevels = static_cast<u32>(info.resources.levels),
        .arrayLayers = static_cast<u32>(info.resources.layers),
        .samples = LiverpoolToVK::NumSamples(info.num_samples, supported_samples),
        .tiling = tiling,
        .usage = usage_flags,
        .initialLayout = vk::ImageLayout::eUndefined,
    };

    backing = &backing_images.emplace_back();
    backing->num_samples = info.num_samples;
    backing->image = UniqueImage{instance.GetDevice(), instance.GetAllocator()};
    if (!backing->image.Create(image_ci, true)) {
        allocation_failed = true;
        LOG_ERROR(Render_Vulkan,
                  "Image {:#x}:{:#x} ({}x{}x{}, format {}) could not be allocated; using the "
                  "1x1 fallback",
                  info.guest_address, info.guest_size, info.size.width, info.size.height,
                  info.size.depth, vk::to_string(info.pixel_format));
        CreateFallback(instance);
        return;
    }

    Vulkan::SetObjectName(instance.GetDevice(), GetImage(),
                          "Image {}x{}x{} {} {} {:#x}:{:#x} L:{} M:{} S:{}", info.size.width,
                          info.size.height, info.size.depth, AmdGpu::NameOf(info.tile_mode),
                          vk::to_string(info.pixel_format), info.guest_address, info.guest_size,
                          info.resources.layers, info.resources.levels, info.num_samples);
}

Image::~Image() = default;

void Image::CreateFallback(const Vulkan::Instance& instance) {
    is_fallback = true;

    // Keep the guest range so cache lookups still see the image where the guest asked
    // for it, but make every Vulkan-facing field describe a valid 1x1 RGBA8 texture.
    info.pixel_format = vk::Format::eR8G8B8A8Unorm;
    info.type = AmdGpu::ImageType::Color2D;
    info.size = {1, 1, 1};
    info.resources = {1, 1};
    info.num_bits = 32;
    info.num_samples = 1;
    info.pitch = 4;
    info.tile_mode = AmdGpu::TileMode::DisplayLinearAligned;
    info.array_mode = AmdGpu::ArrayMode::ArrayLinearAligned;
    info.props = {};
    info.meta_info = {};
    if (info.guest_size == 0) {
        info.guest_size = 4;
        guest_end = guest_begin + info.guest_size;
    }

    image_uid = global_image_uid.Next();
    mip_hashes.clear();
    mip_hashes.resize(1);
    usage_flags = vk::ImageUsageFlagBits::eTransferSrc | vk::ImageUsageFlagBits::eTransferDst |
                  vk::ImageUsageFlagBits::eSampled | vk::ImageUsageFlagBits::eStorage |
                  vk::ImageUsageFlagBits::eColorAttachment;
    format_features = FormatFeatureFlags(usage_flags);
    aspect_mask = vk::ImageAspectFlagBits::eColor;
    supported_samples = vk::SampleCountFlagBits::e1;

    if (!backing) {
        backing = &backing_images.emplace_back();
    } else {
        backing->image.Destroy();
        backing->state = {};
        backing->subresource_states.clear();
        backing->image_view_infos.clear();
        backing->image_view_ids.clear();
        backing->last_view = 0;
    }
    backing->num_samples = 1;
    backing->image = UniqueImage{instance.GetDevice(), instance.GetAllocator()};
    const vk::ImageCreateInfo fallback_ci = {
        .imageType = vk::ImageType::e2D,
        .format = vk::Format::eR8G8B8A8Unorm,
        .extent = {.width = 1, .height = 1, .depth = 1},
        .mipLevels = 1,
        .arrayLayers = 1,
        .samples = vk::SampleCountFlagBits::e1,
        .tiling = vk::ImageTiling::eOptimal,
        .usage = usage_flags,
        .initialLayout = vk::ImageLayout::eUndefined,
    };
    const bool created = backing->image.Create(fallback_ci, true);
    if (!created || !backing->image) {
        LOG_ERROR(Render_Vulkan, "Failed to create the 1x1 fallback texture for {:#x}:{:#x}",
                  info.guest_address, info.guest_size);
        return;
    }
    Vulkan::SetObjectName(instance.GetDevice(), backing->image.image,
                          "Fallback 1x1 RGBA8 {:#x}:{:#x}", info.guest_address, info.guest_size);
}

ImageView& Image::FindView(const ImageViewInfo& view_info, bool ensure_guest_samples) {
    // Defensive: older paths could construct an Image without a backing. Repair it
    // here instead of dereferencing 0x0 in the sample-count check below.
    if (!backing) {
        LOG_ERROR(Render_Vulkan, "Image {:#x}:{:#x} has no backing; creating the fallback",
                  info.guest_address, info.guest_size);
        CreateFallback(runtime->GetInstance());
    }
    if (!backing || !backing->image) {
        // The fallback allocation can fail too (host commit exhausted). Returning an invalid
        // view lets callers skip this texture instead of dereferencing a null Vulkan image.
        LOG_ERROR(Render_Vulkan, "Image {:#x}:{:#x} has no Vulkan image", info.guest_address,
                  info.guest_size);
        static ImageView invalid_view{};
        return invalid_view;
    }

    if (is_fallback) {
        // Invalid guest formats can also carry invalid view ranges/formats. Always use
        // the full 1x1 color view for the fallback image.
        if (backing->image_view_ids.empty() ||
            !slot_image_views->is_allocated(backing->image_view_ids.front())) {
            backing->image_view_infos.clear();
            backing->image_view_ids.clear();
            const ImageViewInfo fallback_info{};
            const auto view_id =
                slot_image_views->insert(runtime->GetInstance(), fallback_info, *this);
            backing->image_view_infos.emplace_back(fallback_info);
            backing->image_view_ids.emplace_back(view_id);
            backing->last_view = 0;
        }
        return (*slot_image_views)[backing->image_view_ids.front()];
    }

    if (ensure_guest_samples && backing->num_samples > 1 != info.num_samples > 1) {
        runtime->SetBackingSamples(this, info.num_samples);
    }
    const auto& view_infos = backing->image_view_infos;
    if (backing->last_view < view_infos.size() &&
        backing->last_view < backing->image_view_ids.size() &&
        slot_image_views->is_allocated(backing->image_view_ids[backing->last_view]) &&
        view_infos[backing->last_view] == view_info) {
        return (*slot_image_views)[backing->image_view_ids[backing->last_view]];
    }
    const auto it = std::ranges::find(view_infos, view_info);
    if (it != view_infos.end()) {
        backing->last_view = static_cast<u32>(std::distance(view_infos.begin(), it));
        if (backing->last_view >= backing->image_view_ids.size() ||
            !slot_image_views->is_allocated(backing->image_view_ids[backing->last_view])) {
            LOG_ERROR(Render_Vulkan, "Image {:#x}:{:#x} has an orphaned view info",
                      info.guest_address, info.guest_size);
            const auto view_id =
                slot_image_views->insert(runtime->GetInstance(), view_info, *this);
            // Replace the missing index rather than appending: view_infos and
            // image_view_ids are parallel arrays and must stay in lockstep.
            if (backing->last_view >= backing->image_view_ids.size()) {
                backing->image_view_ids.resize(backing->last_view + 1);
            }
            backing->image_view_ids[backing->last_view] = view_id;
            return (*slot_image_views)[view_id];
        }
        return (*slot_image_views)[backing->image_view_ids[backing->last_view]];
    }
    const auto view_id = slot_image_views->insert(runtime->GetInstance(), view_info, *this);
    backing->image_view_infos.emplace_back(view_info);
    backing->image_view_ids.emplace_back(view_id);
    return (*slot_image_views)[view_id];
}

void Image::GetBarriers(Barriers& barriers, vk::ImageLayout dst_layout, vk::AccessFlags2 dst_mask,
                        vk::PipelineStageFlags2 dst_stage,
                        std::optional<SubresourceRange> subres_range) {
    auto& last_state = backing->state;
    auto& subresource_states = backing->subresource_states;

    const bool needs_partial_transition =
        subres_range &&
        (subres_range->base != SubresourceBase{} || subres_range->extent != info.resources);
    const bool partially_transited = !subresource_states.empty();

    if (needs_partial_transition || partially_transited) {
        if (!partially_transited) {
            subresource_states.resize(info.resources.levels * info.resources.layers);
            std::fill(subresource_states.begin(), subresource_states.end(), last_state);
        }

        // In case of partial transition, we need to change the specified subresources only.
        // Otherwise all subresources need to be set to the same state so we can use a full
        // resource transition for the next time.
        const auto mips =
            needs_partial_transition
                ? std::ranges::views::iota(subres_range->base.level,
                                           subres_range->base.level + subres_range->extent.levels)
                : std::views::iota(0u, info.resources.levels);
        const auto layers =
            needs_partial_transition
                ? std::ranges::views::iota(subres_range->base.layer,
                                           subres_range->base.layer + subres_range->extent.layers)
                : std::views::iota(0u, info.resources.layers);

        for (u32 mip : mips) {
            for (u32 layer : layers) {
                // NOTE: these loops may produce a lot of small barriers.
                // If this becomes a problem, we can optimize it by merging adjacent barriers.
                const auto subres_idx = mip * info.resources.layers + layer;
                ASSERT(subres_idx < subresource_states.size());
                auto& state = subresource_states[subres_idx];

                constexpr auto write_flags = vk::AccessFlagBits2::eTransferWrite |
                                             vk::AccessFlagBits2::eShaderWrite |
                                             vk::AccessFlagBits2::eMemoryWrite;
                const bool is_write = static_cast<bool>(state.access_mask & write_flags);
                if (state.layout != dst_layout || state.access_mask != dst_mask || is_write) {
                    barriers.emplace_back(vk::ImageMemoryBarrier2{
                        .srcStageMask = state.pl_stage,
                        .srcAccessMask = state.access_mask,
                        .dstStageMask = dst_stage,
                        .dstAccessMask = dst_mask,
                        .oldLayout = state.layout,
                        .newLayout = dst_layout,
                        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                        .image = GetImage(),
                        .subresourceRange{
                            .aspectMask = aspect_mask,
                            .baseMipLevel = mip,
                            .levelCount = 1,
                            .baseArrayLayer = layer,
                            .layerCount = 1,
                        },
                    });
                    state.layout = dst_layout;
                    state.access_mask = dst_mask;
                    state.pl_stage = dst_stage;
                }
            }
        }

        if (!needs_partial_transition) {
            subresource_states.clear();
        }
    } else { // Full resource transition
        constexpr auto write_flags = vk::AccessFlagBits2::eTransferWrite |
                                     vk::AccessFlagBits2::eShaderWrite |
                                     vk::AccessFlagBits2::eMemoryWrite;
        const bool is_write = static_cast<bool>(last_state.access_mask & write_flags);
        if (last_state.layout == dst_layout && last_state.access_mask == dst_mask && !is_write) {
            return;
        }

        barriers.emplace_back(vk::ImageMemoryBarrier2{
            .srcStageMask = last_state.pl_stage,
            .srcAccessMask = last_state.access_mask,
            .dstStageMask = dst_stage,
            .dstAccessMask = dst_mask,
            .oldLayout = last_state.layout,
            .newLayout = dst_layout,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = GetImage(),
            .subresourceRange{
                .aspectMask = aspect_mask,
                .baseMipLevel = 0,
                .levelCount = VK_REMAINING_MIP_LEVELS,
                .baseArrayLayer = 0,
                .layerCount = VK_REMAINING_ARRAY_LAYERS,
            },
        });
    }

    last_state.layout = dst_layout;
    last_state.access_mask = dst_mask;
    last_state.pl_stage = dst_stage;
}

} // namespace VideoCore
