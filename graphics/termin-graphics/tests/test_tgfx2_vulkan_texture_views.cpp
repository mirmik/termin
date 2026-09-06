#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx2/backend_binding_plan.hpp"

#include <cmath>
#include <array>
#include <cstdio>
#include <stdexcept>

using namespace tgfx;

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

static void run() {
    VulkanRenderDevice device(VulkanDeviceCreateInfo{});
    TextureDesc texture;
    texture.width = texture.height = 8;
    texture.mip_levels = 4;
    texture.usage = TextureUsage::Sampled | TextureUsage::ColorAttachment |
                    TextureUsage::CopySrc | TextureUsage::CopyDst;
    const auto source = device.create_texture(texture);
    const std::array<uint8_t, 4> upper_mip{153, 71, 29, 255};
    device.upload_texture_region(source, 0, 0, 1, 1, upper_mip, 3);
    TextureDesc depth_desc = texture;
    depth_desc.format = PixelFormat::D24_UNorm_S8_UInt;
    depth_desc.usage = TextureUsage::Sampled | TextureUsage::DepthStencilAttachment;
    const auto depth = device.supports_texture(depth_desc) ? device.create_texture(depth_desc) : TextureHandle{};
    texture.mip_levels = 1;
    const auto target = device.create_texture(texture);
    auto commands = device.create_command_list();
    commands->begin();
    RenderPassDesc pass;
    ColorAttachmentDesc attachment;
    attachment.texture = source;
    attachment.clear_color = {0.2f, 0.3f, 0.4f, 1.0f};
    pass.colors.push_back(attachment);
    if (depth) {
        pass.has_depth = true;
        pass.depth.texture = depth;
        pass.depth.clear_depth = 0.625f;
        pass.depth.clear_stencil = 37;
    }
    commands->begin_render_pass(pass);
    commands->end_render_pass();
    commands->end();
    device.submit(*commands);
    float pixel[4]{};
    require(device.read_pixel_rgba8(source, 4, 4, pixel), "mipmapped attachment readback failed");
    require(std::abs(pixel[0] - 0.2f) < 0.01f, "mipmapped attachment clear failed");
    device.wait_idle();
    commands.reset();

    // clear_texture also selects mip zero and keeps the sampling view intact.
    device.clear_texture(source, {0.8f, 0.3f, 0.4f, 1.0f}, {0, 0, 8, 8});
    commands = device.create_command_list();
    commands->begin();
    commands->end();
    device.submit(*commands);
    device.wait_idle();
    commands.reset();

    ShaderDesc shader;
    shader.stage = ShaderStage::Vertex;
    shader.source = R"(
#version 450
void main() {
    vec2 p[3]=vec2[](vec2(-1,-1),vec2(3,-1),vec2(-1,3));
    gl_Position=vec4(p[gl_VertexIndex],0,1);
})";
    const auto vertex = device.create_shader(shader);
    shader.stage = ShaderStage::Fragment;
    shader.source = R"(
#version 450
layout(binding=0) uniform sampler2D source_texture;
layout(binding=1) uniform sampler2D depth_texture;
layout(location=0) out vec4 result;
void main() {
    result=vec4(texelFetch(source_texture,ivec2(4),0).r,
                float(textureQueryLevels(source_texture))/4.0,
                texelFetch(source_texture,ivec2(0),3).r,
                texelFetch(depth_texture,ivec2(4),0).r);
})";
    const auto fragment = device.create_shader(shader);
    PipelineDesc pipeline_desc;
    pipeline_desc.vertex_shader = vertex;
    pipeline_desc.fragment_shader = fragment;
    pipeline_desc.color_formats = {PixelFormat::RGBA8_UNorm};
    pipeline_desc.depth_format = PixelFormat::Undefined;
    pipeline_desc.depth_stencil.depth_test = false;
    pipeline_desc.depth_stencil.depth_write = false;
    pipeline_desc.raster.cull = CullMode::None;
    const auto pipeline = device.create_pipeline(pipeline_desc);
    SamplerDesc sampler_desc;
    sampler_desc.min_filter = sampler_desc.mag_filter = sampler_desc.mip_filter = FilterMode::Nearest;
    const auto sampler = device.create_sampler(sampler_desc);
    BoundResourceBinding binding{};
    binding.slot.placement.kind = BackendPlacementKind::VulkanDescriptor;
    binding.slot.placement.vulkan.binding = 0;
    binding.slot.placement.vulkan.descriptor_kind = BackendDescriptorKind::SampledTexture;
    binding.value.kind = BoundResourceKind::SampledTexture;
    binding.value.texture = source;
    binding.value.sampler = sampler;
    BoundResourceSetStorage storage;
    storage.set_resource_layout_token(device.pipeline_resource_layout_token(pipeline));
    std::array<BoundResourceBinding, 2> bindings{binding, binding};
    binding.slot.placement.vulkan.binding = 1;
    binding.value.texture = depth ? depth : source;
    bindings[1] = binding;
    storage.append_group(ShaderResourceScope::Material, true, bindings.data(), bindings.size());
    const auto resources = device.create_bound_resource_set(storage.view());
    require(bool(resources), "mipmapped sampling resource set failed");
    commands = device.create_command_list();
    commands->begin();
    pass.colors[0].texture = target;
    pass.has_depth = false;
    commands->begin_render_pass(pass);
    commands->set_viewport(0, 0, 8, 8);
    commands->bind_pipeline(pipeline);
    commands->bind_resource_set(resources);
    commands->draw(3);
    commands->end_render_pass();
    commands->end();
    device.submit(*commands);
    require(device.read_pixel_rgba8(target, 4, 4, pixel), "sampling readback failed");
    require(std::abs(pixel[0] - 0.8f) < 0.01f, "mip zero sampling lost clear_texture output");
    require(std::abs(pixel[1] - 1.0f) < 0.01f, "sampling view lost higher mip levels");
    require(std::abs(pixel[2] - 0.6f) < 0.01f, "mip-zero rendering/clear damaged upper mip contents");
    require(std::abs(pixel[3] - (depth ? 0.625f : 0.8f)) < 0.01f, "depth-stencil sampling lost depth aspect");
    if (!depth) std::puts("D24/S8 sampled attachment unsupported; depth/stencil subcase unavailable");
    device.wait_idle();
    commands.reset();
    device.destroy(resources);
    device.destroy(pipeline);
    device.destroy(sampler);
    device.destroy(vertex);
    device.destroy(fragment);
    device.destroy(source);
    device.destroy(target);
    if (depth) device.destroy(depth);
}

int main() {
    try { run(); }
    catch (const std::exception& error) {
        std::fprintf(stderr, "Vulkan texture views: %s\n", error.what());
        return 1;
    }
    std::puts("Vulkan mip-zero attachments and full-chain sampling passed");
}
