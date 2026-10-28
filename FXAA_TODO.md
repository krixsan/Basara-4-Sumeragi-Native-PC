# FXAA Implementation Status

## Current State: INCOMPLETE - Requires glslang

### Completed
- ✅ UI toggle added in launcher.py (Graphics Settings → Anti-Aliasing)
- ✅ Settings save/load to basara.ini (anti_aliasing key)
- ✅ GLSL shaders written:
  - `gpu/shadps4/video_core/renderer_vulkan/shaders/fxaa.vert` (fullscreen quad)
  - `gpu/shadps4/video_core/renderer_vulkan/shaders/fxaa.frag` (FXAA 3.11 Lottes)
- ✅ CMakeLists.txt updated to compile fxaa shaders
- ✅ Placeholder check in vk_presenter.cpp Present() for `BbSettings::Get().anti_aliasing == 1`

### Blocked - Missing glslangValidator
**ERROR**: Cannot compile GLSL → SPIR-V without glslangValidator binary.

CMake configuration expects glslangValidator but it's not installed:
- Not in PATH
- Not in Vulkan SDK (VULKAN_SDK env var not set)
- Not in project third_party

### Required to Complete

#### 1. Install Vulkan SDK
Download from https://vulkan.lunarg.com/
- Install with glslangValidator component
- Verify with: `glslangValidator --version`

#### 2. Reconfigure CMake
```cmd
cd "F:\Project Porting Game PS4\Basara 4 Sumeragi v2.0-Perf\build"
cmake .. -DENABLE_QT_GUI=ON -DUSE_SYSTEM_FFMPEG=OFF
```

This will:
- Detect glslangValidator
- Compile fxaa.vert → fxaa_vert.h
- Compile fxaa.frag → fxaa_frag.h
- Generate SPIR-V header files in `gpu/shadps4/video_core/host_shaders/`

#### 3. Create FxaaPass Class
File: `gpu/shadps4/video_core/renderer_vulkan/host_passes/fxaa_pass.h`
```cpp
#pragma once
#include "video_core/renderer_vulkan/vk_common.h"

namespace Vulkan {
class Instance;
class Scheduler;
class RenderState;

class FxaaPass {
public:
    explicit FxaaPass(const Instance& instance, Scheduler& scheduler);
    ~FxaaPass();

    void Draw(RenderState& rstate, vk::ImageView src_image, vk::Image dst_image,
              VkExtent2D extent);

private:
    const Instance& instance;
    Scheduler& scheduler;
    vk::UniqueDescriptorSetLayout desc_layout;
    vk::UniquePipelineLayout pipeline_layout;
    vk::UniquePipeline pipeline;
    vk::UniqueDescriptorPool desc_pool;
    vk::DescriptorSet desc_set;
    vk::UniqueSampler sampler;
};
} // namespace Vulkan
```

File: `gpu/shadps4/video_core/renderer_vulkan/host_passes/fxaa_pass.cpp`
```cpp
#include "fxaa_pass.h"
#include "video_core/host_shaders/fxaa_frag.h"
#include "video_core/host_shaders/fxaa_vert.h"
#include "video_core/renderer_vulkan/vk_instance.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"

namespace Vulkan {

FxaaPass::FxaaPass(const Instance& instance_, Scheduler& scheduler_)
    : instance(instance_), scheduler(scheduler_) {
    
    const auto device = instance.GetDevice();

    // Create descriptor set layout
    const vk::DescriptorSetLayoutBinding bindings[] = {
        {
            .binding = 0,
            .descriptorType = vk::DescriptorType::eCombinedImageSampler,
            .descriptorCount = 1,
            .stageFlags = vk::ShaderStageFlagBits::eFragment,
        },
    };

    const vk::DescriptorSetLayoutCreateInfo layout_ci = {
        .bindingCount = std::size(bindings),
        .pBindings = bindings,
    };
    desc_layout = device.createDescriptorSetLayoutUnique(layout_ci);

    // Push constants
    const vk::PushConstantRange push_range = {
        .stageFlags = vk::ShaderStageFlagBits::eFragment,
        .offset = 0,
        .size = sizeof(float) * 8, // u_texelSize (vec4) + u_settings (vec4)
    };

    const vk::PipelineLayoutCreateInfo pipeline_layout_ci = {
        .setLayoutCount = 1,
        .pSetLayouts = &*desc_layout,
        .pushConstantRangeCount = 1,
        .pPushConstantRanges = &push_range,
    };
    pipeline_layout = device.createPipelineLayoutUnique(pipeline_layout_ci);

    // Shader modules
    const vk::ShaderModuleCreateInfo vert_ci = {
        .codeSize = sizeof(FXAA_VERT),
        .pCode = FXAA_VERT,
    };
    auto vert_module = device.createShaderModuleUnique(vert_ci);

    const vk::ShaderModuleCreateInfo frag_ci = {
        .codeSize = sizeof(FXAA_FRAG),
        .pCode = FXAA_FRAG,
    };
    auto frag_module = device.createShaderModuleUnique(frag_ci);

    // Pipeline stages
    const vk::PipelineShaderStageCreateInfo stages[] = {
        {
            .stage = vk::ShaderStageFlagBits::eVertex,
            .module = *vert_module,
            .pName = "main",
        },
        {
            .stage = vk::ShaderStageFlagBits::eFragment,
            .module = *frag_module,
            .pName = "main",
        },
    };

    // Pipeline state
    const vk::PipelineVertexInputStateCreateInfo vertex_input_ci = {};

    const vk::PipelineInputAssemblyStateCreateInfo input_assembly_ci = {
        .topology = vk::PrimitiveTopology::eTriangleList,
    };

    const vk::PipelineRasterizationStateCreateInfo raster_ci = {
        .polygonMode = vk::PolygonMode::eFill,
        .cullMode = vk::CullModeFlagBits::eNone,
        .frontFace = vk::FrontFace::eClockwise,
        .lineWidth = 1.0f,
    };

    const vk::PipelineMultisampleStateCreateInfo multisample_ci = {
        .rasterizationSamples = vk::SampleCountFlagBits::e1,
    };

    const vk::PipelineColorBlendAttachmentState color_blend_attachment = {
        .blendEnable = VK_FALSE,
        .colorWriteMask = vk::ColorComponentFlagBits::eR | vk::ColorComponentFlagBits::eG |
                          vk::ColorComponentFlagBits::eB | vk::ColorComponentFlagBits::eA,
    };

    const vk::PipelineColorBlendStateCreateInfo color_blend_ci = {
        .attachmentCount = 1,
        .pAttachments = &color_blend_attachment,
    };

    const std::array dynamic_states = {
        vk::DynamicState::eViewport,
        vk::DynamicState::eScissor,
    };

    const vk::PipelineDynamicStateCreateInfo dynamic_state_ci = {
        .dynamicStateCount = dynamic_states.size(),
        .pDynamicStates = dynamic_states.data(),
    };

    const vk::PipelineViewportStateCreateInfo viewport_ci = {
        .viewportCount = 1,
        .scissorCount = 1,
    };

    // Rendering info (dynamic rendering)
    const vk::Format color_format = vk::Format::eB8G8R8A8Unorm;
    const vk::PipelineRenderingCreateInfo rendering_ci = {
        .colorAttachmentCount = 1,
        .pColorAttachmentFormats = &color_format,
    };

    const vk::GraphicsPipelineCreateInfo pipeline_ci = {
        .pNext = &rendering_ci,
        .stageCount = std::size(stages),
        .pStages = stages,
        .pVertexInputState = &vertex_input_ci,
        .pInputAssemblyState = &input_assembly_ci,
        .pViewportState = &viewport_ci,
        .pRasterizationState = &raster_ci,
        .pMultisampleState = &multisample_ci,
        .pColorBlendState = &color_blend_ci,
        .pDynamicState = &dynamic_state_ci,
        .layout = *pipeline_layout,
    };

    auto result = device.createGraphicsPipelineUnique(nullptr, pipeline_ci);
    if (result.result != vk::Result::eSuccess) {
        LOG_ERROR(Render_Vulkan, "Failed to create FXAA pipeline: {}", 
                  vk::to_string(result.result));
    }
    pipeline = std::move(result.value);

    // Descriptor pool
    const vk::DescriptorPoolSize pool_size = {
        .type = vk::DescriptorType::eCombinedImageSampler,
        .descriptorCount = 1,
    };

    const vk::DescriptorPoolCreateInfo pool_ci = {
        .maxSets = 1,
        .poolSizeCount = 1,
        .pPoolSizes = &pool_size,
    };
    desc_pool = device.createDescriptorPoolUnique(pool_ci);

    // Allocate descriptor set
    const vk::DescriptorSetAllocateInfo alloc_info = {
        .descriptorPool = *desc_pool,
        .descriptorSetCount = 1,
        .pSetLayouts = &*desc_layout,
    };
    desc_set = device.allocateDescriptorSets(alloc_info)[0];

    // Create sampler
    const vk::SamplerCreateInfo sampler_ci = {
        .magFilter = vk::Filter::eLinear,
        .minFilter = vk::Filter::eLinear,
        .mipmapMode = vk::SamplerMipmapMode::eNearest,
        .addressModeU = vk::SamplerAddressMode::eClampToEdge,
        .addressModeV = vk::SamplerAddressMode::eClampToEdge,
        .addressModeW = vk::SamplerAddressMode::eClampToEdge,
    };
    sampler = device.createSamplerUnique(sampler_ci);
}

FxaaPass::~FxaaPass() = default;

void FxaaPass::Draw(RenderState& rstate, vk::ImageView src_image, vk::Image dst_image,
                    VkExtent2D extent) {
    const auto cmdbuf = rstate.command_buffer;

    // Update descriptor set
    const vk::DescriptorImageInfo image_info = {
        .sampler = *sampler,
        .imageView = src_image,
        .imageLayout = vk::ImageLayout::eShaderReadOnlyOptimal,
    };

    const vk::WriteDescriptorSet write = {
        .dstSet = desc_set,
        .dstBinding = 0,
        .descriptorCount = 1,
        .descriptorType = vk::DescriptorType::eCombinedImageSampler,
        .pImageInfo = &image_info,
    };

    instance.GetDevice().updateDescriptorSets(write, {});

    // Transition src to shader read
    const vk::ImageMemoryBarrier src_barrier = {
        .srcAccessMask = vk::AccessFlagBits::eColorAttachmentWrite,
        .dstAccessMask = vk::AccessFlagBits::eShaderRead,
        .oldLayout = vk::ImageLayout::eColorAttachmentOptimal,
        .newLayout = vk::ImageLayout::eShaderReadOnlyOptimal,
        .image = rstate.image, // src_image handle
        .subresourceRange = {
            .aspectMask = vk::ImageAspectFlagBits::eColor,
            .levelCount = 1,
            .layerCount = 1,
        },
    };

    cmdbuf.pipelineBarrier(vk::PipelineStageFlagBits::eColorAttachmentOutput,
                           vk::PipelineStageFlagBits::eFragmentShader,
                           vk::DependencyFlagBits::eByRegion, {}, {}, src_barrier);

    // Begin rendering to dst
    const vk::RenderingAttachmentInfo color_attachment = {
        .imageView = /* dst_image_view */,
        .imageLayout = vk::ImageLayout::eColorAttachmentOptimal,
        .loadOp = vk::AttachmentLoadOp::eDontCare,
        .storeOp = vk::AttachmentStoreOp::eStore,
    };

    const vk::RenderingInfo rendering_info = {
        .renderArea = {
            .extent = extent,
        },
        .layerCount = 1,
        .colorAttachmentCount = 1,
        .pColorAttachments = &color_attachment,
    };

    cmdbuf.beginRendering(rendering_info);

    // Bind pipeline and descriptors
    cmdbuf.bindPipeline(vk::PipelineBindPoint::eGraphics, *pipeline);
    cmdbuf.bindDescriptorSets(vk::PipelineBindPoint::eGraphics, *pipeline_layout, 0, desc_set, {});

    // Push constants
    struct {
        float texelSize[4]; // xy: 1/width, 1/height; zw: width, height
        float settings[4];  // x: subpix=0.75, y: edge_thresh=0.166, z: edge_thresh_min=0.0833, w: unused
    } push;

    push.texelSize[0] = 1.0f / extent.width;
    push.texelSize[1] = 1.0f / extent.height;
    push.texelSize[2] = static_cast<float>(extent.width);
    push.texelSize[3] = static_cast<float>(extent.height);
    push.settings[0] = 0.75f;  // quality_subpix
    push.settings[1] = 0.166f; // quality_edge_threshold
    push.settings[2] = 0.0833f; // quality_edge_threshold_min
    push.settings[3] = 0.0f;

    cmdbuf.pushConstants(*pipeline_layout, vk::ShaderStageFlagBits::eFragment, 0, sizeof(push), &push);

    // Set viewport and scissor
    const vk::Viewport viewport = {
        .width = static_cast<float>(extent.width),
        .height = static_cast<float>(extent.height),
        .minDepth = 0.0f,
        .maxDepth = 1.0f,
    };
    cmdbuf.setViewport(0, viewport);

    const vk::Rect2D scissor = {
        .extent = extent,
    };
    cmdbuf.setScissor(0, scissor);

    // Draw fullscreen triangle
    cmdbuf.draw(3, 1, 0, 0);

    cmdbuf.endRendering();
}

} // namespace Vulkan
```

#### 4. Integrate into vk_presenter.cpp

In `vk_presenter.h`, add member:
```cpp
#include "video_core/renderer_vulkan/host_passes/fxaa_pass.h"

class Presenter {
    // ... existing members ...
    std::unique_ptr<FxaaPass> fxaa_pass;
};
```

In `vk_presenter.cpp` constructor:
```cpp
Presenter::Presenter(/* ... */) {
    // ... existing initialization ...
    fxaa_pass = std::make_unique<FxaaPass>(instance, scheduler);
}
```

In `Present()` function, after `pp_pass.Render()` (around line 940):
```cpp
// Apply FXAA if enabled
if (BbSettings::Get().anti_aliasing == 1) {
    fxaa_pass->Draw(rstate, rstate.image_view, rstate.image, frame_image_extent);
}
```

#### 5. Build and Test
```cmd
cd "F:\Project Porting Game PS4\Basara 4 Sumeragi v2.0-Perf\build"
nmake
```

Verify:
- Game launches without crash
- Graphics Settings → Anti-Aliasing toggle works
- With FXAA ON: edges visibly smoother
- With FXAA OFF: no performance overhead

### Failure Handling
If FXAA shader compilation fails:
1. Log loud error to console
2. Set `BbSettings::Get().anti_aliasing = 0` to disable toggle
3. Add TODO marker in CHANGELOG.md

---

**Status**: 🔴 BLOCKED - Requires Vulkan SDK installation  
**Time Spent**: 90+ minutes (deadline exceeded)  
**Reason**: glslangValidator not available in development environment
