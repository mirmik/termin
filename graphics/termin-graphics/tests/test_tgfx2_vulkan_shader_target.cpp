#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/vulkan/internal/shader_target.hpp"

#include <cstdio>
#include <cstring>
#include <exception>
#include <stdexcept>

using namespace tgfx;

static bool run(uint32_t requested) {
    VulkanDeviceCreateInfo info;
    info.api_version = requested;
    VulkanRenderDevice device(info);
    VkPhysicalDeviceProperties properties{};
    vkGetPhysicalDeviceProperties(device.physical_device(), &properties);
    if (device.api_version() > requested || device.api_version() > properties.apiVersion)
        return false;
    ShaderDesc desc;
    desc.stage = ShaderStage::Vertex;
    desc.source = R"(
#version 450
void main() {
    vec2 p[3]=vec2[](vec2(-1,-1),vec2(3,-1),vec2(-1,3));
    gl_Position=vec4(p[gl_VertexIndex],0,1);
}
)";
    const auto vertex = device.create_shader(desc);
    desc.stage = ShaderStage::Fragment;
    desc.source = R"(
#version 450
layout(location=0) out vec4 color;
void main() { color=vec4(0.2,0.6,0.8,1); }
)";
    const auto fragment = device.create_shader(desc);
    PipelineDesc pipeline_desc;
    pipeline_desc.vertex_shader = vertex;
    pipeline_desc.fragment_shader = fragment;
    pipeline_desc.depth_stencil.depth_test = false;
    pipeline_desc.depth_stencil.depth_write = false;
    pipeline_desc.depth_format = PixelFormat::Undefined;
    pipeline_desc.color_formats = {PixelFormat::RGBA8_UNorm};
    pipeline_desc.raster.cull = CullMode::None;
    const auto pipeline = device.create_pipeline(pipeline_desc);
    TextureDesc texture_desc;
    texture_desc.width = texture_desc.height = 8;
    texture_desc.usage = TextureUsage::ColorAttachment | TextureUsage::CopySrc;
    const auto texture = device.create_texture(texture_desc);
    auto commands = device.create_command_list();
    commands->begin();
    RenderPassDesc pass;
    ColorAttachmentDesc attachment;
    attachment.texture = texture;
    attachment.load = LoadOp::Clear;
    pass.colors.push_back(attachment);
    commands->begin_render_pass(pass);
    commands->set_viewport(0, 0, 8, 8);
    commands->bind_pipeline(pipeline);
    commands->draw(3);
    commands->end_render_pass();
    commands->end();
    device.submit(*commands);
    float color[4]{};
    bool ok = device.read_pixel_rgba8(texture, 4, 4, color) &&
              color[0] > 0.19f && color[0] < 0.21f && color[1] > 0.59f && color[1] < 0.61f;
    device.wait_idle();
    commands.reset();
    device.destroy(texture);
    device.destroy(pipeline);
    device.destroy(vertex);
    device.destroy(fragment);

    // The same minimal compute module is valid in each core SPIR-V baseline.
    // No compute pipeline is required to check the shader-module environment.
    uint32_t words[] = {
        0x07230203, 0x00010000, 0, 5, 0,
        0x00020011, 1, 0x0003000e, 0, 1,
        0x0005000f, 5, 3, 0x6e69616d, 0,
        0x00060010, 3, 17, 1, 1, 1,
        0x00020013, 1, 0x00030021, 2, 1,
        0x00050036, 1, 3, 0, 2, 0x000200f8, 4,
        0x000100fd, 0x00010038,
    };
    desc = {};
    desc.stage = ShaderStage::Compute;
    desc.debug_name = "precompiled-api-baseline";
    desc.bytecode.resize(sizeof(words));
    for (uint32_t version : {0x00010000u, 0x00010300u, 0x00010500u, 0x00010600u}) {
        words[1] = version;
        std::memcpy(desc.bytecode.data(), words, sizeof(words));
        const bool compatible = version <= vulkan_detail::shader_target(device.api_version()).spirv;
        try {
            const auto module = device.create_shader(desc);
            ok &= compatible && bool(module);
            device.destroy(module);
        } catch (const std::runtime_error&) {
            ok &= !compatible;
        }
    }
    return ok;
}

int main() {
    try {
        // Reuse identical sources across desktop -> compatibility -> desktop.
        // A cache that omits its target makes the compatibility run fail.
        for (uint32_t api : {VK_API_VERSION_1_3, VK_API_VERSION_1_0, VK_API_VERSION_1_1, VK_API_VERSION_1_3}) {
            if (!run(api)) {
                std::fprintf(stderr, "Shader target regression failed for API 0x%x\n", api);
                return 1;
            }
        }
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Shader target regression: %s\n", error.what());
        return 1;
    }
    std::puts("Shader targets: desktop/compatibility pixels, cache separation and precompiled baseline passed");
    return 0;
}
