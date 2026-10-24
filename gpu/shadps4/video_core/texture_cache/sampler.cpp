// SPDX-FileCopyrightText: Copyright 2024 shadPS4 Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#include <algorithm>
#include "bbport_settings.h"
#include "video_core/renderer_vulkan/liverpool_to_vk.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/texture_cache/sampler.h"

namespace VideoCore {

Sampler::Sampler(const Vulkan::Instance& instance, const AmdGpu::Sampler& sampler,
                 const AmdGpu::BorderColorBuffer border_color_base, const bool is_depth, float extra_lod_bias) {
    using namespace Vulkan;
    // A depth texture is not automatically a shadow map. SSAO/post-processing read the depth
    // buffer with depth_compare_func == Never: forcing clamp-to-white/linear/compare on those
    // samplers breaks ordinary depth reads. Only hardware PCF (compare != Never) gets the
    // shadow-specific treatment.
    const bool shadow_sampler = sampler.depth_compare_func != AmdGpu::DepthCompare::Never;
    const bool is_depth_sampler = is_depth || shadow_sampler;
    const bool game_anisotropy = AmdGpu::IsAnisoFilter(sampler.xy_mag_filter) ||
                                 AmdGpu::IsAnisoFilter(sampler.xy_min_filter);
    const int forced = BbSettings::Get().anisotropy.load();
    const bool force_anisotropy = forced > 1 && !is_depth_sampler &&
                                  sampler.xy_min_filter != AmdGpu::Filter::Point &&
                                  sampler.mip_filter != AmdGpu::MipFilter::None;
    const bool anisotropy_enable =
        !is_depth_sampler && instance.IsAnisotropicFilteringSupported() &&
        (game_anisotropy || force_anisotropy);
    const float requested = std::max(game_anisotropy ? sampler.MaxAniso() : 1.0f,
                                     force_anisotropy ? float(forced) : 1.0f);
    const float max_anisotropy =
        anisotropy_enable ? std::clamp(requested, 1.0f, instance.MaxSamplerAnisotropy()) : 1.0f;

    auto border_color = LiverpoolToVK::BorderColor(sampler.border_color_type);
    if (border_color == vk::BorderColor::eFloatCustomEXT &&
        !instance.IsCustomBorderColorSupported()) {
        LOG_WARNING(Render_Vulkan, "Custom border color is not supported, falling back to black");
        border_color = vk::BorderColor::eFloatOpaqueBlack;
    }

    auto address_mode_u = LiverpoolToVK::ClampMode(sampler.clamp_x);
    auto address_mode_v = LiverpoolToVK::ClampMode(sampler.clamp_y);
    auto address_mode_w = LiverpoolToVK::ClampMode(sampler.clamp_z);

    if (shadow_sampler) {
        // Shadow map cascade sampling: sampling outside [0, 1] must never repeat or stretch edge shadows.
        // Force ClampToBorder with Opaque White (depth = 1.0f) so outside-cascade regions are 100% lit.
        auto sanitize_depth_clamp = [](vk::SamplerAddressMode mode) {
            if (mode == vk::SamplerAddressMode::eRepeat ||
                mode == vk::SamplerAddressMode::eMirroredRepeat ||
                mode == vk::SamplerAddressMode::eClampToEdge ||
                mode == vk::SamplerAddressMode::eMirrorClampToEdge) {
                return vk::SamplerAddressMode::eClampToBorder;
            }
            return mode;
        };
        address_mode_u = sanitize_depth_clamp(address_mode_u);
        address_mode_v = sanitize_depth_clamp(address_mode_v);
        address_mode_w = sanitize_depth_clamp(address_mode_w);

        // In shadow maps, 1.0f corresponds to the far plane (unshadowed).
        // Using Opaque White guarantees that UV coordinates outside the shadow map cascade
        // evaluate as unshadowed (depth comparison ref <= 1.0f returns true), eliminating
        // infinite stretched shadow lines along the terrain edges.
        border_color = vk::BorderColor::eFloatOpaqueWhite;
    }

    const auto custom_color = [&]() -> std::optional<vk::SamplerCustomBorderColorCreateInfoEXT> {
        if (!is_depth_sampler && border_color == vk::BorderColor::eFloatCustomEXT) {
            const auto border_color_index = sampler.border_color_ptr.Value();
            const auto border_color_buffer = border_color_base.Address<std::array<float, 4>*>();
            const auto custom_border_color_array = border_color_buffer[border_color_index];

            const vk::SamplerCustomBorderColorCreateInfoEXT ret{
                .customBorderColor =
                    vk::ClearColorValue{
                        .float32 = custom_border_color_array,
                    },
                .format = vk::Format::eR32G32B32A32Sfloat,
            };
            return ret;
        } else {
            return std::nullopt;
        }
    }();

    // Hardware PCF (Percentage-Closer Filtering): only a comparison sampler (depth_compare_func
    // != Never) gets linear filtering for the GPU's 2x2 comparison filter. Plain depth reads keep
    // the guest's filter modes.
    const vk::Filter mag_filter = shadow_sampler ? vk::Filter::eLinear : LiverpoolToVK::Filter(sampler.xy_mag_filter);
    const vk::Filter min_filter = shadow_sampler ? vk::Filter::eLinear : LiverpoolToVK::Filter(sampler.xy_min_filter);

    const vk::SamplerCreateInfo sampler_ci = {
        .pNext = custom_color ? &*custom_color : nullptr,
        .magFilter = mag_filter,
        .minFilter = min_filter,
        .mipmapMode = LiverpoolToVK::MipFilter(sampler.mip_filter),
        .addressModeU = address_mode_u,
        .addressModeV = address_mode_v,
        .addressModeW = address_mode_w,
        .mipLodBias = std::clamp(sampler.LodBias() + extra_lod_bias, -instance.MaxSamplerLodBias(),
                                 instance.MaxSamplerLodBias()),
        .anisotropyEnable = anisotropy_enable,
        .maxAnisotropy = max_anisotropy,
        // GCN compares per instruction; only an explicit compare sampler enables Vulkan's
        // compareEnable. Never is an ordinary depth read (SSAO/post), not a shadow map.
        .compareEnable = shadow_sampler,
        .compareOp = LiverpoolToVK::DepthCompare(sampler.depth_compare_func),
        .minLod = sampler.MinLod(),
        .maxLod = sampler.MaxLod(),
        .borderColor = border_color,
        .unnormalizedCoordinates = false, // Handled in shader due to Vulkan limitations.
    };
    auto [sampler_result, smplr] = instance.GetDevice().createSamplerUnique(sampler_ci);
    ASSERT_MSG(sampler_result == vk::Result::eSuccess, "Failed to create sampler: {}",
               vk::to_string(sampler_result));
    handle = std::move(smplr);
}

Sampler::~Sampler() = default;

} // namespace VideoCore
