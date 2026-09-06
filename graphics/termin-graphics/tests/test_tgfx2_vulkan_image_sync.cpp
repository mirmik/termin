#include "tgfx2/backend_binding_plan.hpp"
#include "tgfx2/vulkan/vulkan_render_device.hpp"
#include "tgfx/resources/tc_shader.h"

#include <array>
#include <cmath>
#include <cstdio>
#include <exception>
#include <vector>

using namespace tgfx;

int main() {
    try {
        VulkanRenderDevice device(VulkanDeviceCreateInfo{});
        ShaderDesc shader;
        shader.stage = ShaderStage::Vertex;
        shader.source = R"(
#version 450
layout(binding=0) uniform sampler2D source_texture;
layout(location=0) out vec4 color;
void main() {
    vec2 positions[3]=vec2[](vec2(-1,-1),vec2(3,-1),vec2(-1,3));
    gl_Position=vec4(positions[gl_VertexIndex],0,1);
    color=texelFetch(source_texture,ivec2(0),0);
}
)";
        const auto vs = device.create_shader(shader);
        shader.stage = ShaderStage::Fragment;
        shader.source = R"(
#version 450
layout(location=0) in vec4 color;
layout(location=0) out vec4 result;
void main() { result=color; }
)";
        const auto fs = device.create_shader(shader);
        PipelineDesc pipeline_desc;
        pipeline_desc.vertex_shader = vs;
        pipeline_desc.fragment_shader = fs;
        pipeline_desc.depth_stencil.depth_test = false;
        pipeline_desc.depth_stencil.depth_write = false;
        pipeline_desc.depth_format = PixelFormat::Undefined;
        pipeline_desc.raster.cull = CullMode::None;
        pipeline_desc.color_formats = {PixelFormat::RGBA8_UNorm};
        const auto pipeline = device.create_pipeline(pipeline_desc);
        TextureDesc sampled_desc;
        sampled_desc.usage = TextureUsage::Sampled | TextureUsage::CopyDst;
        const auto sampled = device.create_texture(sampled_desc);
        const auto sampler = device.create_sampler(SamplerDesc{});
        BackendBindingPlanEntry entry;
        entry.resource.name = "source_texture";
        entry.resource.kind = ShaderResourceKind::Texture;
        entry.resource.scope = ShaderResourceScope::Material;
        entry.stage_mask = TC_SHADER_STAGE_VERTEX;
        entry.placement.kind = BackendPlacementKind::VulkanDescriptor;
        entry.placement.vulkan.descriptor_kind = BackendDescriptorKind::SampledTexture;
        BoundResourceValue value;
        value.kind = BoundResourceKind::SampledTexture;
        value.texture = sampled;
        value.sampler = sampler;
        const BoundResourceBinding binding{bound_resource_slot_from_plan_entry(entry), value};
        std::vector<TextureHandle> targets;
        std::vector<std::array<uint8_t, 4>> expected;
        bool ok = true;
        for (unsigned frame = 0; frame < 3; ++frame) {
            const std::array<uint8_t, 4> color{static_cast<uint8_t>(40 + frame * 60), 117, 203, 255};
            device.upload_texture(sampled, color);
            TextureDesc target_desc;
            target_desc.width = target_desc.height = 16;
            target_desc.usage = TextureUsage::ColorAttachment | TextureUsage::CopySrc | TextureUsage::CopyDst;
            const auto rendered = device.create_texture(target_desc);
            const auto copied = device.create_texture(target_desc);
            target_desc.usage = TextureUsage::CopySrc | TextureUsage::CopyDst;
            const auto blitted = device.create_texture(target_desc);
            auto commands = device.create_command_list();
            commands->begin();
            BoundResourceSetStorage storage;
            storage.set_resource_layout_token(device.pipeline_resource_layout_token(pipeline));
            storage.append_group(ShaderResourceScope::Material, true, &binding, 1);
            const auto resources = device.create_bound_resource_set(storage.view());
            RenderPassDesc pass;
            ColorAttachmentDesc attachment;
            attachment.texture = rendered;
            attachment.load = LoadOp::Clear;
            pass.colors.push_back(attachment);
            commands->begin_render_pass(pass);
            commands->set_viewport(0, 0, 16, 16);
            commands->bind_pipeline(pipeline);
            commands->bind_resource_set(resources);
            commands->draw(3);
            commands->end_render_pass();
            commands->copy_texture(rendered, copied);
            ok &= device.get_texture(rendered)->current_layout == VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
            ok &= device.get_texture(copied)->current_layout == VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
            // Re-enter the destination as an attachment; LOAD must retain the copy.
            pass.colors[0].texture = copied;
            pass.colors[0].load = LoadOp::Load;
            commands->begin_render_pass(pass);
            commands->end_render_pass();
            commands->end();
            device.submit(*commands);
            device.destroy(resources);

            // Device blits are a next-submit prelude, so schedule after the
            // producer submission and explicitly submit that prelude.
            device.blit_to_texture(blitted, copied, {0, 0, 16, 16}, {0, 0, 16, 16});
            ok &= device.get_texture(copied)->current_layout == VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
            ok &= device.get_texture(blitted)->current_layout == VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL;
            auto flush = device.create_command_list();
            flush->begin();
            flush->end();
            device.submit(*flush);
            for (auto texture : {rendered, copied, blitted}) {
                targets.push_back(texture);
                expected.push_back(color);
            }
        }
        device.wait_idle();
        for (size_t i = 0; i < targets.size(); ++i) {
            float pixel[4]{};
            ok &= device.read_pixel_rgba8(targets[i], 8, 8, pixel);
            for (unsigned channel = 0; channel < 4; ++channel) {
                if (std::fabs(pixel[channel] - static_cast<float>(expected[i][channel]) / 255.0f) > 0.01f) {
                    std::fprintf(stderr, "Image sync pixel %zu channel %u: got %.3f expected %u\n",
                                 i, channel, pixel[channel], expected[i][channel]);
                    ok = false;
                }
            }
        }
        for (auto texture : targets) device.destroy(texture);
        device.destroy(sampled);
        device.destroy(sampler);
        device.destroy(pipeline);
        device.destroy(vs);
        device.destroy(fs);
        if (!ok) {
            std::fprintf(stderr, "Image sync: pixel or restored layout mismatch\n");
            return 1;
        }
        std::puts("Image sync: vertex sampling, attachment copy/reuse, transfer-only blit and nine pixels passed");
    } catch (const std::exception& error) {
        std::fprintf(stderr, "Image sync regression: %s\n", error.what());
        return 1;
    }
    return 0;
}
