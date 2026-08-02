#include <cstring>
#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <span>
#include <string>

#include <emscripten/emscripten.h>

#include <core/tc_scene.h>
#include <core/tc_component.h>
#include <inspect/tc_kind.h>
#include <tcbase/tc_version.h>
#include <termin/bootstrap/bootstrap.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin_scene/termin_scene.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx2/webgpu/webgpu_render_device.hpp>

#include "web_render_shaders.hpp"

namespace {

struct WebVertex {
    float position[2];
    float uv[2];
};

struct WebRenderState {
    std::unique_ptr<tgfx::WebGpuRenderDevice> device;
    tgfx::PipelineHandle triangle_pipeline;
    tgfx::PipelineHandle mesh_pipeline;
    tgfx::BufferHandle vertex_buffer;
    tgfx::BufferHandle index_buffer;
    tgfx::TextureHandle texture;
    tgfx::SamplerHandle sampler;
    tgfx::ResourceSetHandle resource_set;
    uint32_t width = 640;
    uint32_t height = 360;
};

std::unique_ptr<WebRenderState> web_render_state;
int web_render_status = 0;
std::string web_render_error;

termin::runtime::RuntimePackageLoadResult web_host_package;
std::string web_host_error;
std::uint32_t web_host_frame_count = 0;

void unload_web_host_package() {
    for (termin::runtime::RuntimePackageScene& packaged : web_host_package.scenes) {
        if (packaged.scene.valid()) {
            packaged.scene.destroy();
        }
    }
    web_host_package = {};
    web_host_frame_count = 0;
}

tgfx::ShaderHandle create_web_shader(
    tgfx::WebGpuRenderDevice& device,
    tgfx::ShaderStage stage,
    const char* source,
    const char* layout,
    const char* entry,
    const char* name) {
    tgfx::ShaderDesc desc;
    desc.stage = stage;
    desc.source = source;
    desc.resource_layout_json = layout;
    desc.entry_point = entry;
    desc.debug_name = name;
    return device.create_shader(desc);
}

tgfx::PipelineHandle create_web_pipeline(
    tgfx::WebGpuRenderDevice& device,
    const char* source,
    const char* layout,
    bool textured) {
    tgfx::PipelineDesc desc;
    desc.vertex_shader = create_web_shader(
        device, tgfx::ShaderStage::Vertex, source, layout, "vs_main",
        textured ? "web-textured-vs" : "web-triangle-vs");
    desc.fragment_shader = create_web_shader(
        device, tgfx::ShaderStage::Fragment, source, layout, "fs_main",
        textured ? "web-textured-fs" : "web-triangle-fs");
    desc.color_formats = {device.surface_pixel_format()};
    desc.depth_format = tgfx::PixelFormat::Undefined;
    desc.raster.cull = tgfx::CullMode::None;
    if (textured) {
        tgfx::VertexLayoutDesc vertex_layout;
        vertex_layout.stride = sizeof(WebVertex);
        vertex_layout.attribute_count = 2;
        vertex_layout.attributes[0].location = 0;
        vertex_layout.attributes[0].format = tgfx::VertexFormat::Float2;
        vertex_layout.attributes[0].offset = offsetof(WebVertex, position);
        vertex_layout.attributes[1].location = 1;
        vertex_layout.attributes[1].format = tgfx::VertexFormat::Float2;
        vertex_layout.attributes[1].offset = offsetof(WebVertex, uv);
        desc.vertex_layouts.push_back(vertex_layout);
    }
    return device.create_pipeline(desc);
}

void render_web_smoke(WebRenderState& state) {
    tgfx::TextureHandle surface = state.device->acquire_surface_texture();
    tgfx::RenderPassDesc pass;
    tgfx::ColorAttachmentDesc color;
    color.texture = surface;
    color.clear_color[0] = 0.035f;
    color.clear_color[1] = 0.055f;
    color.clear_color[2] = 0.09f;
    color.clear_color[3] = 1.0f;
    pass.colors.push_back(color);

    std::unique_ptr<tgfx::ICommandList> commands = state.device->create_command_list();
    commands->begin();
    commands->begin_render_pass(pass);
    commands->set_viewport(0, 0, state.width / 2, state.height);
    commands->set_scissor(0, 0, state.width / 2, state.height);
    commands->bind_pipeline(state.triangle_pipeline);
    commands->draw(3);

    commands->set_viewport(state.width / 2, 0, state.width - state.width / 2, state.height);
    commands->set_scissor(state.width / 2, 0, state.width - state.width / 2, state.height);
    commands->bind_pipeline(state.mesh_pipeline);
    commands->bind_resource_set(state.resource_set);
    commands->bind_vertex_buffer(0, state.vertex_buffer);
    commands->bind_index_buffer(state.index_buffer, tgfx::IndexType::Uint16);
    commands->draw_indexed(6);
    commands->end_render_pass();
    commands->end();
    state.device->submit(*commands);
    state.device->present();
}

void initialize_web_render(std::unique_ptr<tgfx::WebGpuRenderDevice> device) {
    auto state = std::make_unique<WebRenderState>();
    state->device = std::move(device);
    state->triangle_pipeline = create_web_pipeline(
        *state->device, termin_web_shaders::triangle_wgsl,
        termin_web_shaders::triangle_layout, false);
    state->mesh_pipeline = create_web_pipeline(
        *state->device, termin_web_shaders::textured_mesh_wgsl,
        termin_web_shaders::textured_mesh_layout, true);

    constexpr std::array<WebVertex, 4> vertices{{
        {{-0.72f, -0.72f}, {0.0f, 0.0f}},
        {{ 0.72f, -0.72f}, {1.0f, 0.0f}},
        {{ 0.72f,  0.72f}, {1.0f, 1.0f}},
        {{-0.72f,  0.72f}, {0.0f, 1.0f}},
    }};
    constexpr std::array<uint16_t, 6> indices{{0, 1, 2, 0, 2, 3}};
    tgfx::BufferDesc vertex_desc;
    vertex_desc.size = sizeof(vertices);
    vertex_desc.usage = tgfx::BufferUsage::Vertex | tgfx::BufferUsage::CopyDst;
    state->vertex_buffer = state->device->create_buffer(vertex_desc);
    state->device->upload_buffer(state->vertex_buffer,
        std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(vertices.data()),
                                 sizeof(vertices)));
    tgfx::BufferDesc index_desc;
    index_desc.size = sizeof(indices);
    index_desc.usage = tgfx::BufferUsage::Index | tgfx::BufferUsage::CopyDst;
    state->index_buffer = state->device->create_buffer(index_desc);
    state->device->upload_buffer(state->index_buffer,
        std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(indices.data()),
                                 sizeof(indices)));

    constexpr std::array<uint8_t, 16> pixels{{
        255, 230, 55, 255,  30, 150, 255, 255,
         30, 150, 255, 255, 255, 230, 55, 255,
    }};
    tgfx::TextureDesc texture_desc;
    texture_desc.width = 2;
    texture_desc.height = 2;
    texture_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
    texture_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
    state->texture = state->device->create_texture(texture_desc);
    state->device->upload_texture(state->texture, pixels);
    state->sampler = state->device->create_sampler({});

    tgfx::BoundResourceBinding texture_binding;
    texture_binding.slot.kind = tgfx::ShaderResourceKind::Texture;
    texture_binding.slot.scope = tgfx::ShaderResourceScope::Material;
    texture_binding.slot.stage_mask = 2;
    texture_binding.slot.placement.kind = tgfx::BackendPlacementKind::WebGPU;
    texture_binding.slot.placement.webgpu.binding = 0;
    texture_binding.slot.placement.webgpu.has_sampler_binding = true;
    texture_binding.slot.placement.webgpu.sampler_binding = 1;
    texture_binding.slot.debug_name = "mesh_texture";
    texture_binding.value.kind = tgfx::BoundResourceKind::SampledTexture;
    texture_binding.value.texture = state->texture;
    texture_binding.value.sampler = state->sampler;
    tgfx::BoundResourceGroupView group;
    group.scope = tgfx::ShaderResourceScope::Material;
    group.bindings = &texture_binding;
    group.binding_count = 1;
    tgfx::BoundResourceSetDesc set_desc;
    set_desc.resource_layout_token =
        state->device->pipeline_resource_layout_token(state->mesh_pipeline);
    set_desc.groups = &group;
    set_desc.group_count = 1;
    state->resource_set = state->device->create_bound_resource_set(set_desc);

    render_web_smoke(*state);
    web_render_state = std::move(state);
}

} // namespace

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_core_smoke() {
    if (tc_version_int() <= 0 || termin_scene_version_int() <= 0) {
        return 1;
    }
    if (tc_kind_get_lang_registry(TC_KIND_LANG_RUST) != nullptr) {
        return 2;
    }
    termin::bootstrap::bootstrap_runtime(
        termin::bootstrap::RuntimeBootstrapProfile::Minimal
    );
    if (!tc_component_registry_has("UnknownComponent") ||
            tc_component_registry_has("MeshComponent")) {
        termin::bootstrap::shutdown_runtime();
        return 3;
    }

    tc_mesh_init();
    tc_mesh_handle mesh = tc_mesh_declare("web-smoke-mesh", "Web smoke mesh");
    if (!tc_mesh_is_valid(mesh) || tc_mesh_count() != 1) {
        tc_mesh_shutdown();
        termin::bootstrap::shutdown_runtime();
        return 4;
    }
    tc_mesh_destroy(mesh);
    tc_mesh_shutdown();

    tc_scene_handle scene = tc_scene_new_named("Web smoke scene");
    const char* scene_name = tc_scene_get_name(scene);
    if (scene_name == nullptr || std::strcmp(scene_name, "Web smoke scene") != 0) {
        tc_scene_free(scene);
        termin::bootstrap::shutdown_runtime();
        return 5;
    }
    tc_scene_update(scene, 1.0 / 60.0);
    tc_scene_free(scene);
    termin::bootstrap::shutdown_runtime();
    return 0x5443;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_load(const char* root_path) {
    unload_web_host_package();
    web_host_error.clear();
    if (root_path == nullptr || root_path[0] == '\0') {
        web_host_error = "runtime package root must not be empty";
        tc_log_error("TerminWebHost: %s", web_host_error.c_str());
        return 0;
    }
    termin::runtime::RuntimePackageLoadOptions options;
    options.bootstrap_profile =
        termin::bootstrap::RuntimeBootstrapProfile::Minimal;
    termin::runtime::RuntimePackageLoader loader;
    web_host_package = loader.load(root_path, options);
    if (!web_host_package.ok) {
        web_host_error = web_host_package.message;
        unload_web_host_package();
        termin::bootstrap::shutdown_runtime();
        return 0;
    }
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_tick(double delta_seconds) {
    if (!web_host_package.ok || !web_host_package.scene.valid()) {
        web_host_error = "runtime package is not loaded";
        tc_log_error("TerminWebHost: %s", web_host_error.c_str());
        return 0;
    }
    if (!(delta_seconds >= 0.0) || delta_seconds > 1.0) {
        web_host_error = "invalid browser frame delta";
        tc_log_error("TerminWebHost: %s", web_host_error.c_str());
        return 0;
    }
    try {
        web_host_package.scene.update(delta_seconds);
        ++web_host_frame_count;
        return 1;
    } catch (const std::exception& exception) {
        web_host_error = exception.what();
        tc_log_error("TerminWebHost update failed: %s", web_host_error.c_str());
        return 0;
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE void termin_web_host_unload() {
    unload_web_host_package();
    web_host_error.clear();
    termin::bootstrap::shutdown_runtime();
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_host_error() {
    return web_host_error.c_str();
}

extern "C" EMSCRIPTEN_KEEPALIVE std::uint32_t termin_web_host_frame_count() {
    return web_host_frame_count;
}

extern "C" EMSCRIPTEN_KEEPALIVE std::size_t termin_web_host_entity_count() {
    return web_host_package.ok && web_host_package.scene.valid()
        ? web_host_package.scene.entity_count()
        : 0;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_render_smoke_start() {
    if (web_render_status != 0) return web_render_status;
    web_render_status = 1;
    tgfx::WebGpuDeviceRequest request;
    request.canvas_selector = "#termin-canvas";
    request.width = 640;
    request.height = 360;
    tgfx::WebGpuRenderDevice::request_async(
        request,
        [](std::unique_ptr<tgfx::WebGpuRenderDevice> device, std::string error) {
            if (!device) {
                web_render_error = std::move(error);
                web_render_status = -1;
                return;
            }
            try {
                initialize_web_render(std::move(device));
                web_render_status = 2;
            } catch (const std::exception& exception) {
                web_render_error = exception.what();
                web_render_status = -2;
            }
        });
    return web_render_status;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_render_smoke_status() {
    if (web_render_state && web_render_state->device->has_device_error()) {
        web_render_error = web_render_state->device->device_error_message();
        web_render_status = -4;
    }
    return web_render_status;
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_render_smoke_error() {
    return web_render_error.c_str();
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_render_smoke_resize(
    uint32_t width, uint32_t height) {
    if (!web_render_state || width == 0 || height == 0) return 0;
    try {
        web_render_state->device->configure_surface(width, height);
        web_render_state->width = width;
        web_render_state->height = height;
        render_web_smoke(*web_render_state);
        return 1;
    } catch (const std::exception& exception) {
        web_render_error = exception.what();
        web_render_status = -3;
        return 0;
    }
}
