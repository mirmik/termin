#include <array>
#include <cstdint>
#include <exception>
#include <memory>
#include <span>
#include <string>
#include <utility>

#include <emscripten/emscripten.h>

#include "tgfx2/webgpu/webgpu_render_device.hpp"

namespace {

    std::unique_ptr<tgfx::WebGpuRenderDevice> fixture_device;
    std::string fixture_error;
    int fixture_status = 0;

    tgfx::ShaderHandle create_shader(tgfx::WebGpuRenderDevice& device,
                                     tgfx::ShaderStage stage,
                                     const char* source,
                                     const char* layout,
                                     const char* name) {
        tgfx::ShaderDesc desc;
        desc.stage = stage;
        desc.source = source;
        desc.resource_layout_json = layout;
        desc.entry_point = stage == tgfx::ShaderStage::Vertex ? "vs_main" : "fs_main";
        desc.debug_name = name;
        return device.create_shader(desc);
    }

    tgfx::PipelineHandle
    create_pipeline(tgfx::WebGpuRenderDevice& device,
                    const char* source,
                    const char* layout,
                    const char* name,
                    tgfx::PrimitiveTopology topology = tgfx::PrimitiveTopology::TriangleList,
                    tgfx::StripIndexFormat strip_index_format = tgfx::StripIndexFormat::Undefined) {
        tgfx::PipelineDesc desc;
        desc.vertex_shader = create_shader(device, tgfx::ShaderStage::Vertex, source, layout, name);
        desc.fragment_shader = create_shader(device, tgfx::ShaderStage::Fragment, source, layout, name);
        desc.color_formats = {device.surface_pixel_format()};
        desc.depth_format = tgfx::PixelFormat::Undefined;
        desc.raster.cull = tgfx::CullMode::None;
        desc.topology = topology;
        desc.strip_index_format = strip_index_format;
        return device.create_pipeline(desc);
    }

    tgfx::ResourceSetHandle create_set(tgfx::WebGpuRenderDevice& device,
                                       tgfx::PipelineHandle pipeline,
                                       tgfx::ShaderResourceKind kind,
                                       tgfx::ShaderResourceScope scope,
                                       uint32_t stage_mask,
                                       uint32_t binding,
                                       tgfx::BoundResourceValue value,
                                       uint32_t sampler_binding = 0) {
        tgfx::BoundResourceBinding resource;
        resource.slot.kind = kind;
        resource.slot.scope = scope;
        resource.slot.stage_mask = stage_mask;
        resource.slot.placement.kind = tgfx::BackendPlacementKind::WebGPU;
        resource.slot.placement.webgpu.binding = binding;
        resource.slot.placement.webgpu.has_sampler_binding = sampler_binding != 0;
        resource.slot.placement.webgpu.sampler_binding = sampler_binding;
        resource.slot.debug_name = "browser-binding-layout-fixture";
        resource.value = value;
        tgfx::BoundResourceGroupView group;
        group.scope = scope;
        group.bindings = &resource;
        group.binding_count = 1;
        tgfx::BoundResourceSetDesc desc;
        desc.resource_layout_token = device.pipeline_resource_layout_token(pipeline);
        desc.groups = &group;
        desc.group_count = 1;
        return device.create_bound_resource_set(desc);
    }

    void render_fixture(tgfx::WebGpuRenderDevice& device) {
        constexpr const char* depth_source = R"wgsl(
@group(0) @binding(0) var shadow_map: texture_depth_2d;
@group(0) @binding(1) var shadow_sampler: sampler_comparison;
@vertex fn vs_main(@builtin(vertex_index) i: u32) -> @builtin(position) vec4<f32> {
  let p = array<vec2<f32>, 3>(vec2<f32>(-1.0, -1.0), vec2<f32>(3.0, -1.0), vec2<f32>(-1.0, 3.0));
  return vec4<f32>(p[i], 0.0, 1.0);
}
@fragment fn fs_main() -> @location(0) vec4<f32> {
  let visible = textureSampleCompare(shadow_map, shadow_sampler, vec2<f32>(0.5), 0.5);
  return vec4<f32>(visible, 0.05, 0.05, 1.0);
})wgsl";
        constexpr const char* depth_layout = R"json({"version":3,"target":"webgpu","resources":[
{"name":"shadow_map","kind":"texture","stage_mask":2,"webgpu":{"group":0,"binding":0,
"sampler_binding":1,"sample_type":"depth","sampler_kind":"comparison","view_aspect":"depth_only",
"view_dimension":"2d","multisampled":false}}]})json";

        constexpr const char* r32_source = R"wgsl(
@group(0) @binding(0) var values: texture_2d<f32>;
@vertex fn vs_main(@builtin(vertex_index) i: u32) -> @builtin(position) vec4<f32> {
  let p = array<vec2<f32>, 3>(vec2<f32>(-1.0, -1.0), vec2<f32>(3.0, -1.0), vec2<f32>(-1.0, 3.0));
  return vec4<f32>(p[i], 0.0, 1.0);
}
@fragment fn fs_main() -> @location(0) vec4<f32> {
  return vec4<f32>(0.05, textureLoad(values, vec2<i32>(0), 0).r, 0.05, 1.0);
})wgsl";
        constexpr const char* r32_layout = R"json({"version":3,"target":"webgpu","resources":[
{"name":"values","kind":"texture","stage_mask":2,"webgpu":{"group":0,"binding":0,
"sample_type":"unfilterable_float","sampler_kind":"none","view_aspect":"all","view_dimension":"2d",
"multisampled":false}}]})json";

        constexpr const char* storage_source = R"wgsl(
@group(0) @binding(0) var<storage, read> vertices: array<vec4<f32>>;
@vertex fn vs_main(@builtin(vertex_index) i: u32) -> @builtin(position) vec4<f32> { return vertices[i]; }
@fragment fn fs_main() -> @location(0) vec4<f32> { return vec4<f32>(0.05, 0.1, 0.9, 1.0); }
)wgsl";
        constexpr const char* storage_layout = R"json({"version":3,"target":"webgpu","resources":[
{"name":"vertices","kind":"storage_buffer","stage_mask":1,"webgpu":{"group":0,"binding":0,
"access":"read_only"}}]})json";

        constexpr const char* rgba_source = R"wgsl(
@group(0) @binding(0) var color_texture: texture_2d<f32>;
@group(0) @binding(1) var color_sampler: sampler;
@vertex fn vs_main(@builtin(vertex_index) i: u32) -> @builtin(position) vec4<f32> {
  let p = array<vec2<f32>, 3>(vec2<f32>(-1.0, -1.0), vec2<f32>(3.0, -1.0), vec2<f32>(-1.0, 3.0));
  return vec4<f32>(p[i], 0.0, 1.0);
}
@fragment fn fs_main() -> @location(0) vec4<f32> {
  return textureSample(color_texture, color_sampler, vec2<f32>(0.5));
})wgsl";
        constexpr const char* rgba_layout = R"json({"version":3,"target":"webgpu","resources":[
{"name":"color_texture","kind":"texture","stage_mask":2,"webgpu":{"group":0,"binding":0,
"sampler_binding":1,"sample_type":"float","sampler_kind":"filtering","view_aspect":"all",
"view_dimension":"2d","multisampled":false}}]})json";

        tgfx::TextureDesc depth_desc;
        depth_desc.width = 2;
        depth_desc.height = 2;
        depth_desc.format = tgfx::PixelFormat::D32F;
        depth_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::DepthStencilAttachment;
        const tgfx::TextureHandle depth = device.create_texture(depth_desc);
        tgfx::RenderPassDesc depth_pass;
        depth_pass.has_depth = true;
        depth_pass.depth.texture = depth;
        depth_pass.depth.clear_depth = 1.0f;
        std::unique_ptr<tgfx::ICommandList> depth_commands = device.create_command_list();
        depth_commands->begin();
        depth_commands->begin_render_pass(depth_pass);
        depth_commands->end_render_pass();
        depth_commands->end();
        device.submit(*depth_commands);

        tgfx::SamplerDesc compare_desc;
        compare_desc.compare_enable = true;
        compare_desc.compare_op = tgfx::CompareOp::LessEqual;
        const tgfx::SamplerHandle comparison = device.create_sampler(compare_desc);

        tgfx::TextureDesc r32_desc;
        r32_desc.width = 2;
        r32_desc.height = 2;
        r32_desc.format = tgfx::PixelFormat::R32F;
        r32_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
        const tgfx::TextureHandle r32 = device.create_texture(r32_desc);
        constexpr std::array<float, 4> values{{0.8f, 0.8f, 0.8f, 0.8f}};
        device.upload_texture(
            r32, std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(values.data()), sizeof(values)));

        tgfx::BufferDesc storage_desc;
        storage_desc.size = sizeof(float) * 12;
        storage_desc.usage = tgfx::BufferUsage::Storage | tgfx::BufferUsage::CopyDst;
        const tgfx::BufferHandle storage = device.create_buffer(storage_desc);
        constexpr std::array<float, 12> positions{
            {-1.0f, -1.0f, 0.0f, 1.0f, 3.0f, -1.0f, 0.0f, 1.0f, -1.0f, 3.0f, 0.0f, 1.0f}};
        device.upload_buffer(
            storage, std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(positions.data()), sizeof(positions)));

        tgfx::TextureDesc rgba_desc;
        rgba_desc.width = 2;
        rgba_desc.height = 2;
        rgba_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        rgba_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
        const tgfx::TextureHandle rgba = device.create_texture(rgba_desc);
        constexpr std::array<uint8_t, 16> yellow{
            {245, 210, 30, 255, 245, 210, 30, 255, 245, 210, 30, 255, 245, 210, 30, 255}};
        device.upload_texture(rgba, yellow);
        const tgfx::SamplerHandle color_sampler = device.create_sampler({});

        const tgfx::PipelineHandle depth_pipeline =
            create_pipeline(device, depth_source, depth_layout, "depth-comparison-fixture");
        const tgfx::PipelineHandle r32_pipeline = create_pipeline(device, r32_source, r32_layout, "r32-load-fixture");
        const tgfx::PipelineHandle storage_pipeline =
            create_pipeline(device, storage_source, storage_layout, "readonly-vertex-storage-fixture");
        const tgfx::PipelineHandle rgba_pipeline =
            create_pipeline(device, rgba_source, rgba_layout, "rgba8-filtering-control-fixture");

        tgfx::BoundResourceValue depth_value;
        depth_value.kind = tgfx::BoundResourceKind::SampledTexture;
        depth_value.texture = depth;
        depth_value.sampler = comparison;
        const tgfx::ResourceSetHandle depth_set = create_set(device,
                                                             depth_pipeline,
                                                             tgfx::ShaderResourceKind::Texture,
                                                             tgfx::ShaderResourceScope::Transient,
                                                             2,
                                                             0,
                                                             depth_value,
                                                             1);
        tgfx::BoundResourceValue r32_value;
        r32_value.kind = tgfx::BoundResourceKind::SampledTexture;
        r32_value.texture = r32;
        const tgfx::ResourceSetHandle r32_set = create_set(device,
                                                           r32_pipeline,
                                                           tgfx::ShaderResourceKind::Texture,
                                                           tgfx::ShaderResourceScope::Transient,
                                                           2,
                                                           0,
                                                           r32_value);
        tgfx::BoundResourceValue storage_value;
        storage_value.kind = tgfx::BoundResourceKind::StorageBuffer;
        storage_value.buffer = storage;
        storage_value.range = storage_desc.size;
        const tgfx::ResourceSetHandle storage_set = create_set(device,
                                                               storage_pipeline,
                                                               tgfx::ShaderResourceKind::StorageBuffer,
                                                               tgfx::ShaderResourceScope::Transient,
                                                               1,
                                                               0,
                                                               storage_value);
        tgfx::BoundResourceValue rgba_value;
        rgba_value.kind = tgfx::BoundResourceKind::SampledTexture;
        rgba_value.texture = rgba;
        rgba_value.sampler = color_sampler;
        const tgfx::ResourceSetHandle rgba_set = create_set(device,
                                                            rgba_pipeline,
                                                            tgfx::ShaderResourceKind::Texture,
                                                            tgfx::ShaderResourceScope::Transient,
                                                            2,
                                                            0,
                                                            rgba_value,
                                                            1);

        const tgfx::TextureHandle surface = device.acquire_surface_texture();
        tgfx::RenderPassDesc pass;
        tgfx::ColorAttachmentDesc color;
        color.texture = surface;
        color.clear_color = {0.01f, 0.01f, 0.01f, 1.0f};
        pass.colors.push_back(color);
        std::unique_ptr<tgfx::ICommandList> commands = device.create_command_list();
        commands->begin();
        commands->begin_render_pass(pass);
        const std::array<tgfx::PipelineHandle, 4> pipelines{
            depth_pipeline, r32_pipeline, storage_pipeline, rgba_pipeline};
        const std::array<tgfx::ResourceSetHandle, 4> sets{depth_set, r32_set, storage_set, rgba_set};
        for (uint32_t index = 0; index < pipelines.size(); ++index) {
            const int x = static_cast<int>((index % 2) * 160);
            const int y = static_cast<int>((index / 2) * 160);
            commands->set_viewport(x, y, 160, 160);
            commands->set_scissor(x, y, 160, 160);
            commands->bind_pipeline(pipelines[index]);
            commands->bind_resource_set(sets[index]);
            commands->draw(3);
        }
        commands->end_render_pass();
        commands->end();
        device.submit(*commands);
        device.present();
    }

    void render_strip_fixture(tgfx::WebGpuRenderDevice& device) {
        constexpr const char* source = R"wgsl(
@vertex fn vs_main(@builtin(vertex_index) i: u32) -> @builtin(position) vec4<f32> {
  let p = array<vec2<f32>, 4>(
    vec2<f32>(-0.82, -0.72), vec2<f32>(-0.82, 0.72),
    vec2<f32>(0.82, -0.72), vec2<f32>(0.82, 0.72));
  return vec4<f32>(p[i], 0.0, 1.0);
}
@fragment fn fs_main(@builtin(position) p: vec4<f32>) -> @location(0) vec4<f32> {
  return vec4<f32>(0.25 + p.x / 480.0, 0.25 + p.y / 480.0, 0.85, 1.0);
})wgsl";
        constexpr const char* layout = R"json({"version":3,"target":"webgpu","resources":[]})json";

        constexpr std::array<uint16_t, 4> indices16{{0, 1, 2, 3}};
        constexpr std::array<uint32_t, 4> indices32{{0, 1, 2, 3}};
        tgfx::BufferDesc index16_desc;
        index16_desc.size = sizeof(indices16);
        index16_desc.usage = tgfx::BufferUsage::Index | tgfx::BufferUsage::CopyDst;
        const tgfx::BufferHandle index16 = device.create_buffer(index16_desc);
        device.upload_buffer(
            index16, std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(indices16.data()), sizeof(indices16)));
        tgfx::BufferDesc index32_desc;
        index32_desc.size = sizeof(indices32);
        index32_desc.usage = tgfx::BufferUsage::Index | tgfx::BufferUsage::CopyDst;
        const tgfx::BufferHandle index32 = device.create_buffer(index32_desc);
        device.upload_buffer(
            index32, std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(indices32.data()), sizeof(indices32)));

        struct DrawCase {
            tgfx::PrimitiveTopology topology;
            tgfx::StripIndexFormat strip_index_format;
            tgfx::IndexType index_type;
            bool indexed;
            const char* name;
        };
        constexpr std::array<DrawCase, 6> cases{{
            {tgfx::PrimitiveTopology::LineStrip,
             tgfx::StripIndexFormat::Uint16,
             tgfx::IndexType::Uint16,
             true,
             "line-strip-uint16"},
            {tgfx::PrimitiveTopology::LineStrip,
             tgfx::StripIndexFormat::Uint32,
             tgfx::IndexType::Uint32,
             true,
             "line-strip-uint32"},
            {tgfx::PrimitiveTopology::LineStrip,
             tgfx::StripIndexFormat::Undefined,
             tgfx::IndexType::Uint32,
             false,
             "line-strip-nonindexed"},
            {tgfx::PrimitiveTopology::TriangleStrip,
             tgfx::StripIndexFormat::Uint16,
             tgfx::IndexType::Uint16,
             true,
             "triangle-strip-uint16"},
            {tgfx::PrimitiveTopology::TriangleStrip,
             tgfx::StripIndexFormat::Uint32,
             tgfx::IndexType::Uint32,
             true,
             "triangle-strip-uint32"},
            {tgfx::PrimitiveTopology::TriangleStrip,
             tgfx::StripIndexFormat::Undefined,
             tgfx::IndexType::Uint32,
             false,
             "triangle-strip-nonindexed"},
        }};
        std::array<tgfx::PipelineHandle, cases.size()> pipelines;
        for (size_t index = 0; index < cases.size(); ++index) {
            pipelines[index] = create_pipeline(
                device, source, layout, cases[index].name, cases[index].topology, cases[index].strip_index_format);
        }

        const tgfx::TextureHandle surface = device.acquire_surface_texture();
        tgfx::RenderPassDesc pass;
        tgfx::ColorAttachmentDesc color;
        color.texture = surface;
        color.clear_color = {0.01f, 0.01f, 0.01f, 1.0f};
        pass.colors.push_back(color);
        std::unique_ptr<tgfx::ICommandList> commands = device.create_command_list();
        commands->begin();
        commands->begin_render_pass(pass);
        for (uint32_t index = 0; index < cases.size(); ++index) {
            const int x = static_cast<int>((index % 3) * 106);
            const int y = static_cast<int>((index / 3) * 160);
            const int width = index % 3 == 2 ? 108 : 106;
            commands->set_viewport(x, y, width, 160);
            commands->set_scissor(x, y, width, 160);
            commands->bind_pipeline(pipelines[index]);
            if (cases[index].indexed) {
                const tgfx::BufferHandle buffer =
                    cases[index].index_type == tgfx::IndexType::Uint16 ? index16 : index32;
                commands->bind_index_buffer(buffer, cases[index].index_type, 0);
                commands->draw_indexed(4);
            } else {
                commands->draw(4);
            }
        }
        commands->end_render_pass();
        commands->end();
        device.submit(*commands);
        device.present();
    }

} // namespace

extern "C" EMSCRIPTEN_KEEPALIVE int tgfx2_webgpu_binding_layout_start() {
    if (fixture_status != 0)
        return fixture_status;
    fixture_status = 1;
    tgfx::WebGpuDeviceRequest request;
    request.canvas_selector = "#fixture-canvas";
    request.width = 320;
    request.height = 320;
    tgfx::WebGpuRenderDevice::request_async(request,
                                            [](std::unique_ptr<tgfx::WebGpuRenderDevice> device, std::string error) {
                                                if (!device) {
                                                    fixture_error = std::move(error);
                                                    fixture_status = -1;
                                                    return;
                                                }
                                                try {
                                                    render_fixture(*device);
                                                    render_strip_fixture(*device);
                                                    fixture_device = std::move(device);
                                                    fixture_status = 2;
                                                } catch (const std::exception& exception) {
                                                    fixture_error = exception.what();
                                                    fixture_status = -2;
                                                }
                                            });
    return fixture_status;
}

extern "C" EMSCRIPTEN_KEEPALIVE int tgfx2_webgpu_binding_layout_status() {
    if (fixture_device && fixture_device->has_device_error()) {
        fixture_error = fixture_device->device_error_message();
        fixture_status = -3;
    }
    return fixture_status;
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* tgfx2_webgpu_binding_layout_error() {
    return fixture_error.c_str();
}
