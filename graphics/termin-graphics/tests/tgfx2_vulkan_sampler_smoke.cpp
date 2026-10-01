// GPU readback regressions for Vulkan texture sampler state.
#include "tgfx2_vulkan_sampler_smoke.hpp"

#include <array>
#include <cmath>
#include <cstdio>
#include <span>

#include "tgfx2/backend_binding_plan.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_sampler_bridge.hpp"
#include "tgfx2/vertex_layout.hpp"

extern "C" {
#include "tgfx/resources/tc_shader.h"
#include "tgfx/resources/tc_texture.h"
#include "tgfx/resources/tc_texture_registry.h"
}

bool render_sampler_state_smoke(tgfx::IRenderDevice& device, const char* vertex_source) {
    constexpr uint32_t kWidth = 16;
    constexpr const char* kFragmentSource = R"(
#version 450 core
layout(set = 0, binding = 0) uniform sampler2D source_texture;
layout(set = 0, binding = 1) uniform SampleParameters { vec4 settings; };
layout(location = 0) out vec4 FragColor;
void main() {
    vec2 uv = settings.xy;
    if (settings.w > 0.5) uv.x = gl_FragCoord.x * 0.25;
    FragColor = textureLod(source_texture, uv, settings.z);
}
)";
    // Each row has black and white columns. The generated 1x1 mip is gray,
    // so both texel interpolation and mip selection have distinct outputs.
    const uint8_t checker[] = {0, 0, 0, 255, 255, 255, 255, 255,
                              0, 0, 0, 255, 255, 255, 255, 255};
    tc_texture_init();
    std::array<tc_texture_handle, 2> cpu_textures{tc_texture_handle_invalid(), tc_texture_handle_invalid()};
    std::array<tgfx::TextureHandle, 2> images{};
    tgfx::ShaderHandle vs;
    tgfx::ShaderHandle fs;
    tgfx::PipelineHandle pipeline;
    tgfx::BufferHandle vb;
    tgfx::BufferHandle ubo;
    tgfx::TextureHandle target;
    const bool ok = [&]() {
        for (size_t i = 0; i < cpu_textures.size(); ++i) {
            cpu_textures[i] = tc_texture_create(i == 0 ? "vulkan-sampler-checker-mips" : "vulkan-sampler-checker-base");
            tc_texture* texture = tc_texture_get(cpu_textures[i]);
            const tc_texture_pixel_data pixels{checker, sizeof(checker), 2, 2, 4};
            if (!texture || !tc_texture_set_data(texture, &pixels, nullptr, nullptr))
                return false;
            if (!tc_texture_set_encoding(texture, TC_TEXTURE_ENCODING_LINEAR))
                return false;
            tc_texture_set_mipmap(texture, i == 0);
            images[i] = device.ensure_tc_texture(texture);
            if (!images[i] || device.texture_desc(images[i]).mip_levels != (i == 0 ? 2u : 1u)) {
                fprintf(stderr, "Vulkan sampler checker: unexpected generated mip count for image %zu\n", i);
                return false;
            }
        }

        tgfx::ShaderDesc shader_desc;
        shader_desc.stage = tgfx::ShaderStage::Vertex;
        shader_desc.source = vertex_source;
        shader_desc.debug_name = "vulkan-sampler-checker:vertex";
        vs = device.create_shader(shader_desc);
        shader_desc.stage = tgfx::ShaderStage::Fragment;
        shader_desc.source = kFragmentSource;
        shader_desc.debug_name = "vulkan-sampler-checker:fragment";
        fs = device.create_shader(shader_desc);
        if (!vs || !fs)
            return false;
        tgfx::PipelineDesc pipeline_desc;
        pipeline_desc.vertex_shader = vs;
        pipeline_desc.fragment_shader = fs;
        pipeline_desc.topology = tgfx::PrimitiveTopology::TriangleList;
        pipeline_desc.depth_stencil.depth_test = false;
        pipeline_desc.depth_stencil.depth_write = false;
        pipeline_desc.depth_format = tgfx::PixelFormat::Undefined;
        pipeline_desc.raster.cull = tgfx::CullMode::None;
        pipeline_desc.color_formats = {tgfx::PixelFormat::RGBA8_UNorm};
        tgfx::VertexBufferLayout layout;
        layout.stride = 2 * sizeof(float);
        layout.attributes = {{0, tgfx::VertexFormat::Float2, 0}};
        pipeline_desc.vertex_layouts.push_back(tgfx::make_vertex_layout_desc(layout));
        pipeline = device.create_pipeline(pipeline_desc);
        if (!pipeline)
            return false;
        const float vertices[] = {-1, -1, 3, -1, -1, 3};
        tgfx::BufferDesc buffer_desc;
        buffer_desc.size = sizeof(vertices);
        buffer_desc.usage = tgfx::BufferUsage::Vertex | tgfx::BufferUsage::CopyDst;
        vb = device.create_buffer(buffer_desc);
        buffer_desc.size = 4 * sizeof(float);
        buffer_desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
        ubo = device.create_buffer(buffer_desc);
        tgfx::TextureDesc target_desc;
        target_desc.width = kWidth;
        target_desc.height = 1;
        target_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        target_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        target = device.create_texture(target_desc);
        if (!vb || !ubo || !target)
            return false;
        device.upload_buffer(vb, std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(vertices), sizeof(vertices)));

        tgfx::BackendBindingPlanEntry texture_entry;
        texture_entry.resource.name = "source_texture";
        texture_entry.resource.kind = tgfx::ShaderResourceKind::Texture;
        texture_entry.resource.scope = tgfx::ShaderResourceScope::Material;
        texture_entry.stage_mask = TC_SHADER_STAGE_FRAGMENT;
        texture_entry.placement.kind = tgfx::BackendPlacementKind::VulkanDescriptor;
        texture_entry.placement.vulkan.set = 0;
        texture_entry.placement.vulkan.binding = 0;
        texture_entry.placement.vulkan.descriptor_kind = tgfx::BackendDescriptorKind::SampledTexture;
        tgfx::BackendBindingPlanEntry parameter_entry;
        parameter_entry.resource.name = "SampleParameters";
        parameter_entry.resource.kind = tgfx::ShaderResourceKind::ConstantBuffer;
        parameter_entry.resource.scope = tgfx::ShaderResourceScope::Material;
        parameter_entry.stage_mask = TC_SHADER_STAGE_FRAGMENT;
        parameter_entry.size = 4 * sizeof(float);
        parameter_entry.placement.kind = tgfx::BackendPlacementKind::VulkanDescriptor;
        parameter_entry.placement.vulkan.set = 0;
        parameter_entry.placement.vulkan.binding = 1;
        parameter_entry.placement.vulkan.descriptor_kind = tgfx::BackendDescriptorKind::UniformBuffer;
        tgfx::RenderPassDesc pass;
        tgfx::ColorAttachmentDesc color;
        color.texture = target;
        color.load = tgfx::LoadOp::Clear;
        pass.colors.push_back(color);

        const auto sample = [&](const char* name, size_t image_index, const tc_sampler_desc& sampler,
                                const std::array<float, 4>& parameters, bool strip, float expected) {
            tc_texture* texture = tc_texture_get(cpu_textures[image_index]);
            const uint32_t version = texture->header.version;
            tgfx::SamplerDesc native_desc;
            if (!tc_texture_set_sampler(texture, &sampler) || texture->header.version != version ||
                device.ensure_tc_texture(texture) != images[image_index] ||
                !tgfx::tc_sampler_to_tgfx2(texture->sampler, native_desc)) {
                fprintf(stderr, "Vulkan sampler checker: sampler edit changed image or conversion failed (%s)\n", name);
                return false;
            }
            const auto native_sampler = device.ensure_sampler(native_desc);
            if (!native_sampler)
                return false;
            // ensure_sampler owns this borrowed handle; only resource sets
            // created below are released by the fixture.
            const tgfx::BoundResourceBinding bindings[] = {
                {tgfx::bound_resource_slot_from_plan_entry(texture_entry),
                 {tgfx::BoundResourceKind::SampledTexture, {}, images[image_index], native_sampler}},
                {tgfx::bound_resource_slot_from_plan_entry(parameter_entry),
                 {tgfx::BoundResourceKind::UniformBuffer, ubo, {}, {}, 0, sizeof(parameters)}}};
            tgfx::BoundResourceSetStorage storage;
            storage.set_resource_layout_token(device.pipeline_resource_layout_token(pipeline));
            storage.append_group(tgfx::ShaderResourceScope::Material, true, bindings, 2);
            const auto resource_set = device.create_bound_resource_set(storage.view());
            if (!resource_set)
                return false;
            device.upload_buffer(ubo, std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(parameters.data()),
                                                             sizeof(parameters)));
            auto cmd = device.create_command_list();
            cmd->begin();
            cmd->begin_render_pass(pass);
            cmd->set_viewport(0, 0, kWidth, 1);
            cmd->bind_pipeline(pipeline);
            cmd->bind_resource_set(resource_set);
            cmd->bind_vertex_buffer(0, vb);
            cmd->draw(3);
            cmd->end_render_pass();
            cmd->end();
            device.submit(*cmd);
            device.wait_idle();
            bool matches = true;
            for (uint32_t x = 0; x < (strip ? kWidth : 1u); ++x) {
                float pixel[4] = {};
                float wanted = expected;
                if (strip) {
                    const bool white = sampler.address_u == TC_SAMPLER_ADDRESS_REPEAT ? x % 4 >= 2 : x >= 2;
                    wanted = white ? 1.0f : 0.0f;
                }
                const bool read_ok = device.read_pixel_rgba8(target, x, 0, pixel);
                const bool pixel_ok = read_ok && std::abs(pixel[0] - wanted) < 0.025f &&
                                      std::abs(pixel[1] - wanted) < 0.025f &&
                                      std::abs(pixel[2] - wanted) < 0.025f && pixel[3] > 0.99f;
                if (!pixel_ok)
                    fprintf(stderr, "Vulkan sampler checker %s x=%u: expected %.3f, got %.3f %.3f %.3f %.3f\n",
                            name, x, wanted, pixel[0], pixel[1], pixel[2], pixel[3]);
                matches = pixel_ok && matches;
            }
            device.destroy(resource_set);
            printf("Vulkan sampler checker %s: %s\n", name, matches ? "ok" : "failed");
            return matches;
        };
        tc_sampler_desc nearest = tc_sampler_desc_default();
        nearest.min_filter = TC_SAMPLER_FILTER_NEAREST;
        nearest.mag_filter = TC_SAMPLER_FILTER_NEAREST;
        nearest.mip_filter = TC_SAMPLER_FILTER_NEAREST;
        nearest.address_u = nearest.address_v = nearest.address_w = TC_SAMPLER_ADDRESS_REPEAT;
        nearest.max_anisotropy = 1.0f;
        nearest.compare_enable = 0;
        nearest.compare_op = TC_SAMPLER_COMPARE_NEVER;
        auto clamp = nearest;
        clamp.address_u = TC_SAMPLER_ADDRESS_CLAMP_TO_EDGE;
        auto linear = nearest;
        linear.min_filter = linear.mag_filter = TC_SAMPLER_FILTER_LINEAR;
        auto mip_linear = nearest;
        mip_linear.mip_filter = TC_SAMPLER_FILTER_LINEAR;
        bool passed = sample("repeat UV 0..4", 0, nearest, {0, 0.25f, 0, 1}, true, 0);
        passed = sample("clamp UV 0..4", 0, clamp, {0, 0.25f, 0, 1}, true, 0) && passed;
        passed = sample("repeat UV 1.25", 0, nearest, {1.25f, 0.25f, 0, 0}, false, 0) && passed;
        passed = sample("clamp UV 1.25", 0, clamp, {1.25f, 0.25f, 0, 0}, false, 1) && passed;
        passed = sample("nearest texel", 0, nearest, {0.375f, 0.25f, 0, 0}, false, 0) && passed;
        passed = sample("linear texel", 0, linear, {0.375f, 0.25f, 0, 0}, false, 0.25f) && passed;
        passed = sample("generated mip LOD 1", 0, nearest, {0.375f, 0.25f, 1, 0}, false, 128.0f / 255) && passed;
        passed = sample("one level LOD 1", 1, nearest, {0.375f, 0.25f, 1, 0}, false, 0) && passed;
        passed = sample("nearest mip LOD .75", 0, nearest, {0.375f, 0.25f, 0.75f, 0}, false, 128.0f / 255) && passed;
        passed = sample("linear mip LOD .75", 0, mip_linear, {0.375f, 0.25f, 0.75f, 0}, false,
                        0.75f * 128.0f / 255) && passed;
        return passed;
    }();
    if (!ok)
        fprintf(stderr, "Vulkan sampler checker regression failed\n");
    if (target)
        device.destroy(target);
    if (ubo)
        device.destroy(ubo);
    if (vb)
        device.destroy(vb);
    if (pipeline)
        device.destroy(pipeline);
    if (fs)
        device.destroy(fs);
    if (vs)
        device.destroy(vs);
    for (const auto texture : cpu_textures) {
        if (!tc_texture_handle_is_invalid(texture))
            tc_texture_destroy(texture);
    }
    tc_texture_shutdown();
    return ok;
}
