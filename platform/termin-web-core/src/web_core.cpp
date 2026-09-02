#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <memory>
#include <span>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

#include <emscripten/emscripten.h>
#include <emscripten/html5.h>
#include <emscripten/html5_webgl.h>

#include <core/tc_component.h>
#include <core/tc_scene.h>
#include <core/tc_scene_extension.h>
#include <core/tc_scene_extension_ids.h>
#include <inspect/tc_kind.h>
#include <render/tc_pass.h>
#include <tcbase/tc_version.h>
#include <termin/bootstrap/bootstrap.hpp>
#include <termin/engine/engine_core.hpp>
#include <termin/platform/offscreen_render_surface.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin/scene/tc_scene_render_ext.hpp>
#include <termin_scene/termin_scene.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/graphics_host.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/opengl/opengl_render_device.hpp>
#include <tgfx2/output_transform.hpp>
#include <tgfx2/pixel_format_utils.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/webgpu/webgpu_render_device.hpp>

extern "C" {
#include <render/tc_display.h>
#include <render/tc_render_surface.h>
#include <render/tc_viewport.h>
#include <render/tc_viewport_input_manager.h>
}

#include "visual_scene_example.hpp"
#include "web_render_shaders.hpp"

namespace {

    enum class WebGraphicsBackend : int {
        None = 0,
        WebGPU = 1,
        WebGL2 = 2,
    };

    struct WebGL2Context {
        EMSCRIPTEN_WEBGL_CONTEXT_HANDLE handle = 0;

        ~WebGL2Context() {
            if (handle > 0) {
                emscripten_webgl_destroy_context(handle);
            }
        }

        bool make_current() const {
            return handle > 0 && emscripten_webgl_make_context_current(handle) == EMSCRIPTEN_RESULT_SUCCESS;
        }
    };

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

    struct WebPlayerState {
        std::unique_ptr<WebGL2Context> webgl2_context;
        std::unique_ptr<tgfx::GraphicsHost> graphics_host;
        tgfx::IRenderDevice* device = nullptr;
        tgfx::WebGpuRenderDevice* webgpu_device = nullptr;
        tgfx::OpenGLRenderDevice* webgl2_device = nullptr;
        tgfx::OutputTransformRenderer output_transform;
        tgfx::TextureHandle webgl2_presentation_texture;
        WebGraphicsBackend backend = WebGraphicsBackend::None;
        std::unique_ptr<termin::EngineCore> engine;
        termin::runtime::RuntimePackageLoadResult package;
        std::vector<termin::SceneKey> registered_scene_keys;
        std::vector<tc_viewport_handle> viewports;
        std::vector<tc_viewport_input_manager*> viewport_input_managers;
        std::vector<tc_display_handle> owned_displays;
        tc_display_handle presentation_display = TC_DISPLAY_HANDLE_INVALID;
        uint32_t width = 640;
        uint32_t height = 360;
    };

    std::unique_ptr<WebPlayerState> web_player;
    termin::runtime::RuntimePackageLoadResult web_headless_package;
    int web_player_graphics_status = 0;
    std::string web_player_graphics_error;
    std::string web_host_error;
    std::string web_visual_scene_error;
    std::shared_ptr<termin::runtime::RuntimePackageReader> web_pending_package_reader;
    std::uint32_t web_host_frame_count = 0;
    bool web_host_loop_running = false;
    double web_host_loop_last_timestamp = -1.0;

    extern "C" int termin_web_host_tick(double delta_seconds);

    EM_BOOL web_host_animation_frame(double timestamp_ms, void*) {
        if (!web_host_loop_running)
            return EM_FALSE;
        const double delta_seconds =
            web_host_loop_last_timestamp < 0.0 ? 0.0 : (timestamp_ms - web_host_loop_last_timestamp) / 1000.0;
        web_host_loop_last_timestamp = timestamp_ms;
        if (!termin_web_host_tick(delta_seconds)) {
            web_host_loop_running = false;
            return EM_FALSE;
        }
        return EM_TRUE;
    }

    void unload_web_host_package() {
        web_host_loop_running = false;
        web_host_loop_last_timestamp = -1.0;
        web_headless_package.destroy();
        tgfx::set_builtin_shader_read_callback({});
        tgfx::set_builtin_shader_root(nullptr);
        if (!web_player) {
            web_host_frame_count = 0;
            return;
        }
        if (web_player->engine) {
            for (tc_viewport_input_manager* input : web_player->viewport_input_managers) {
                tc_viewport_input_manager_free(input);
            }
            web_player->viewport_input_managers.clear();
            tc_log_info("TerminWebHost unload: shutting down EngineCore");
            if (!web_player->engine->shutdown()) {
                tc_log_error("TerminWebHost: EngineCore shutdown failed");
            }
            web_player->engine.reset();
            tc_log_info("TerminWebHost unload: EngineCore released");
        }
        tc_log_info("TerminWebHost unload: destroying packaged scenes");
        web_player->package.destroy();
        web_player->viewports.clear();
        web_player->presentation_display = TC_DISPLAY_HANDLE_INVALID;
        web_player->registered_scene_keys.clear();
        for (tc_display_handle display : web_player->owned_displays) {
            if (tc_display_alive(display) && !tc_display_free(display)) {
                tc_log_error("TerminWebHost: failed to release owned display");
            }
        }
        web_player->owned_displays.clear();
        web_player->output_transform.close();
        if (web_player->webgl2_presentation_texture && web_player->device) {
            web_player->device->destroy(web_player->webgl2_presentation_texture);
            web_player->webgl2_presentation_texture = {};
        }
        if (web_player->graphics_host) {
            if (web_player->webgl2_context && !web_player->webgl2_context->make_current()) {
                tc_log_error("TerminWebHost unload: failed to make WebGL2 context current");
            }
            tc_log_info("TerminWebHost unload: closing GraphicsHost");
            web_player->graphics_host->close();
            web_player->graphics_host.reset();
            tc_log_info("TerminWebHost unload: GraphicsHost released");
        }
        web_player.reset();
        web_player_graphics_status = 0;
        web_host_frame_count = 0;
    }

    tc_display_handle create_web_player_display(const std::string& requested_name) {
        if (!web_player || !web_player->device) {
            tc_log_error("TerminWebHost: display requested without a graphics device");
            return TC_DISPLAY_HANDLE_INVALID;
        }
        const std::string name = requested_name.empty() ? "Main" : requested_name;
        const tc_display_handle display = termin::create_offscreen_display(web_player->device,
                                                                           static_cast<int>(web_player->width),
                                                                           static_cast<int>(web_player->height),
                                                                           name.c_str());
        if (tc_display_alive(display)) {
            web_player->owned_displays.push_back(display);
        }
        return display;
    }

    bool present_web_player_canvas() {
        if (!web_player || !web_player->device || !tc_display_handle_valid(web_player->presentation_display)) {
            return false;
        }
        tc_render_surface* display_surface = tc_display_get_surface(web_player->presentation_display);
        uint32_t output_texture_id = 0;
        if (!display_surface || !tc_render_surface_validate_output(display_surface,
                                                                   reinterpret_cast<uintptr_t>(web_player->device),
                                                                   &output_texture_id)) {
            tc_log_error("TerminWebHost: rendered display output is invalid");
            return false;
        }
        if (web_player->backend == WebGraphicsBackend::WebGPU) {
            tgfx::TextureHandle canvas = web_player->webgpu_device->acquire_surface_texture();
            const termin::Bounds2i extent{
                0, 0, static_cast<int>(web_player->width), static_cast<int>(web_player->height)};
            web_player->webgpu_device->blit_to_texture(canvas, tgfx::TextureHandle{output_texture_id}, extent, extent);
            web_player->device->present();
        } else if (web_player->backend == WebGraphicsBackend::WebGL2) {
            if (!web_player->webgl2_context->make_current()) {
                tc_log_error("TerminWebHost: failed to make WebGL2 context current for presentation");
                return false;
            }

            const tgfx::TextureDesc current_desc = web_player->webgl2_presentation_texture
                                                       ? web_player->device->texture_desc(
                                                             web_player->webgl2_presentation_texture)
                                                       : tgfx::TextureDesc{};
            if (!web_player->webgl2_presentation_texture || current_desc.width != web_player->width ||
                current_desc.height != web_player->height || current_desc.format != tgfx::PixelFormat::RGBA8_sRGB) {
                if (web_player->webgl2_presentation_texture) {
                    web_player->device->destroy(web_player->webgl2_presentation_texture);
                }
                tgfx::TextureDesc desc;
                desc.width = web_player->width;
                desc.height = web_player->height;
                desc.format = tgfx::PixelFormat::RGBA8_sRGB;
                desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::Sampled |
                             tgfx::TextureUsage::CopySrc;
                web_player->webgl2_presentation_texture = web_player->device->create_texture(desc);
                if (!web_player->webgl2_presentation_texture) {
                    tc_log_error("TerminWebHost: failed to allocate WebGL2 sRGB presentation texture");
                    return false;
                }
            }

            tgfx::RenderContext2& output_context = web_player->graphics_host->context();
            output_context.begin_frame();
            const bool transformed = web_player->output_transform.record(
                output_context,
                tgfx::TextureHandle{output_texture_id},
                web_player->webgl2_presentation_texture,
                tgfx::OutputTransformParams{
                    .sampled_input_encoding = tgfx::TextureEncoding::Linear,
                    .target_encoding = tgfx::TextureEncoding::SRGB,
                    .dither = tgfx::OutputDitherMode::StableSpatial,
                    .target_rgb_bits = 8,
                });
            output_context.end_frame();
            if (!transformed) {
                tc_log_error("TerminWebHost: WebGL2 display output transform failed");
                return false;
            }

            web_player->webgl2_device->present_to_default_framebuffer(web_player->webgl2_presentation_texture,
                                                                      static_cast<int>(web_player->width),
                                                                      static_cast<int>(web_player->height));
            web_player->device->present();
        } else {
            tc_log_error("TerminWebHost: no browser graphics backend selected");
            return false;
        }
        return true;
    }

    tgfx::ShaderHandle create_web_shader(tgfx::WebGpuRenderDevice& device,
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

    tgfx::PipelineHandle
    create_web_pipeline(tgfx::WebGpuRenderDevice& device, const char* source, const char* layout, bool textured) {
        tgfx::PipelineDesc desc;
        desc.vertex_shader = create_web_shader(device,
                                               tgfx::ShaderStage::Vertex,
                                               source,
                                               layout,
                                               "vs_main",
                                               textured ? "web-textured-vs" : "web-triangle-vs");
        desc.fragment_shader = create_web_shader(device,
                                                 tgfx::ShaderStage::Fragment,
                                                 source,
                                                 layout,
                                                 "fs_main",
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
        color.clear_color = {0.035f, 0.055f, 0.09f, 1.0f};
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

    void render_web_texture_ops_smoke(WebRenderState& state) {
        constexpr uint32_t texture_size = 8;
        std::array<uint8_t, texture_size * texture_size * 4> pixels{};
        for (uint32_t y = 0; y < texture_size; ++y) {
            for (uint32_t x = 0; x < texture_size; ++x) {
                const size_t offset = (y * texture_size + x) * 4;
                const bool right = x >= texture_size / 2;
                const bool bottom = y >= texture_size / 2;
                pixels[offset + 0] = bottom ? (right ? 245 : 30) : 235;
                pixels[offset + 1] = bottom ? (right ? 245 : 65) : (right ? 205 : 35);
                pixels[offset + 2] = bottom ? (right ? 245 : 225) : 30;
                pixels[offset + 3] = 255;
            }
        }

        tgfx::TextureDesc source_desc;
        source_desc.width = texture_size;
        source_desc.height = texture_size;
        source_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        source_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopySrc | tgfx::TextureUsage::CopyDst;
        const tgfx::TextureHandle source = state.device->create_texture(source_desc);
        state.device->upload_texture(source, pixels);

        tgfx::TextureDesc copy_desc = source_desc;
        copy_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::ColorAttachment |
                          tgfx::TextureUsage::CopySrc | tgfx::TextureUsage::CopyDst;
        const tgfx::TextureHandle copy = state.device->create_texture(copy_desc);
        const termin::Bounds2i full_source = termin::Bounds2i::from_size(texture_size, texture_size);
        state.device->blit_to_texture(copy, source, full_source, full_source);

        const tgfx::TextureHandle surface = state.device->acquire_surface_texture();
        state.device->clear_texture(surface,
                                    termin::LinearColor{0.035f, 0.055f, 0.09f, 1.0f},
                                    termin::Bounds2i::from_size(state.width, state.height));
        state.device->blit_to_texture(surface, copy, full_source, termin::Bounds2i{80, 50, 560, 310});
        state.device->blit_to_texture(surface, copy, termin::Bounds2i{0, 0, 4, 4}, termin::Bounds2i{20, 20, 70, 70});
        state.device->clear_texture(
            surface, termin::LinearColor{0.05f, 0.85f, 0.12f, 1.0f}, termin::Bounds2i{280, 140, 360, 220});
        state.device->present();

        state.device->destroy(copy);
        state.device->destroy(source);
    }

    void initialize_web_render(std::unique_ptr<tgfx::WebGpuRenderDevice> device) {
        auto state = std::make_unique<WebRenderState>();
        state->device = std::move(device);
        state->triangle_pipeline = create_web_pipeline(
            *state->device, termin_web_shaders::triangle_wgsl, termin_web_shaders::triangle_layout, false);
        state->mesh_pipeline = create_web_pipeline(
            *state->device, termin_web_shaders::textured_mesh_wgsl, termin_web_shaders::textured_mesh_layout, true);

        constexpr std::array<WebVertex, 4> vertices{{
            {{-0.72f, -0.72f}, {0.0f, 0.0f}},
            {{0.72f, -0.72f}, {1.0f, 0.0f}},
            {{0.72f, 0.72f}, {1.0f, 1.0f}},
            {{-0.72f, 0.72f}, {0.0f, 1.0f}},
        }};
        constexpr std::array<uint16_t, 6> indices{{0, 1, 2, 0, 2, 3}};
        tgfx::BufferDesc vertex_desc;
        vertex_desc.size = sizeof(vertices);
        vertex_desc.usage = tgfx::BufferUsage::Vertex | tgfx::BufferUsage::CopyDst;
        state->vertex_buffer = state->device->create_buffer(vertex_desc);
        state->device->upload_buffer(
            state->vertex_buffer,
            std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(vertices.data()), sizeof(vertices)));
        tgfx::BufferDesc index_desc;
        index_desc.size = sizeof(indices);
        index_desc.usage = tgfx::BufferUsage::Index | tgfx::BufferUsage::CopyDst;
        state->index_buffer = state->device->create_buffer(index_desc);
        state->device->upload_buffer(
            state->index_buffer,
            std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(indices.data()), sizeof(indices)));

        constexpr std::array<uint8_t, 16> pixels{{
            255,
            230,
            55,
            255,
            30,
            150,
            255,
            255,
            30,
            150,
            255,
            255,
            255,
            230,
            55,
            255,
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
        set_desc.resource_layout_token = state->device->pipeline_resource_layout_token(state->mesh_pipeline);
        set_desc.groups = &group;
        set_desc.group_count = 1;
        state->resource_set = state->device->create_bound_resource_set(set_desc);

        render_web_smoke(*state);
        render_web_texture_ops_smoke(*state);
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
    termin::bootstrap::bootstrap_runtime(termin::bootstrap::RuntimeBootstrapProfile::Minimal);
    if (!tc_component_registry_has("UnknownComponent") || tc_component_registry_has("MeshComponent")) {
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

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_core_lifecycle_smoke() {
    termin::bootstrap::shutdown_runtime();
    size_t component_type_count = 0;
    size_t pass_type_count = 0;
    for (int cycle = 0; cycle < 2; ++cycle) {
        termin::bootstrap::bootstrap_runtime(termin::bootstrap::RuntimeBootstrapProfile::Render);
        const size_t current_component_type_count = tc_component_registry_type_count();
        const size_t current_pass_type_count = tc_pass_registry_type_count();
        const bool registry_complete = tc_component_registry_has("MeshComponent") &&
                                       tc_component_registry_has("MeshRenderer") && tc_pass_registry_has("ColorPass") &&
                                       tc_pass_registry_has("SkyBoxPass") &&
                                       tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_RENDER_MOUNT) &&
                                       tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_RENDER_STATE);
        const bool registry_counts_stable = cycle == 0 || (current_component_type_count == component_type_count &&
                                                           current_pass_type_count == pass_type_count);
        if (!registry_complete || !registry_counts_stable) {
            tc_log_error("TerminWebCore lifecycle smoke: incomplete or duplicate Render registry on cycle %d",
                         cycle + 1);
            termin::bootstrap::shutdown_runtime();
            return 1 + cycle;
        }
        component_type_count = current_component_type_count;
        pass_type_count = current_pass_type_count;
        termin::bootstrap::shutdown_runtime();
        if (tc_component_registry_type_count() != 0 || tc_pass_registry_type_count() != 0 ||
            tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_RENDER_MOUNT) ||
            tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_RENDER_STATE)) {
            tc_log_error("TerminWebCore lifecycle smoke: Render registry survived shutdown on cycle %d", cycle + 1);
            return 3 + cycle;
        }
    }
    return 0x5743;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_core_shutdown() {
    if (web_player_graphics_status == 1 || web_render_status == 1) {
        tc_log_error("TerminWebCore shutdown refused while WebGPU initialization is pending");
        return 0;
    }
    unload_web_host_package();
    web_pending_package_reader.reset();
    web_render_state.reset();
    web_render_status = 0;
    web_render_error.clear();
    web_player_graphics_error.clear();
    web_host_error.clear();
    termin::bootstrap::shutdown_runtime();
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_load(const char* root_path) {
    web_host_error.clear();
    if (!web_player || web_player_graphics_status != 2 || !web_player->graphics_host || !web_player->device) {
        web_host_error = "WebGPU player is not initialized";
        tc_log_error("TerminWebHost: %s", web_host_error.c_str());
        return 0;
    }
    if (!web_pending_package_reader && (root_path == nullptr || root_path[0] == '\0')) {
        web_host_error = "runtime package root must not be empty";
        tc_log_error("TerminWebHost: %s", web_host_error.c_str());
        return 0;
    }
    termin::runtime::RuntimePackageLoadOptions options;
    options.bootstrap_profile = termin::bootstrap::RuntimeBootstrapProfile::Render;
    options.scene_extensions = termin::default_scene_extension_ids();
    try {
        termin::runtime::RuntimePackageLoader loader;
        if (web_pending_package_reader) {
            web_player->package = loader.load(std::move(web_pending_package_reader), options);
        } else {
            web_player->package = loader.load(root_path, options);
        }
    } catch (const std::exception& exception) {
        web_host_error = exception.what();
        tc_log_error("TerminWebHost package load threw: %s", web_host_error.c_str());
        unload_web_host_package();
        return 0;
    }
    if (!web_player->package.ok || !web_player->package.scene.valid()) {
        web_host_error = web_player->package.message;
        unload_web_host_package();
        return 0;
    }
    try {
        web_player->engine = std::make_unique<termin::EngineCore>();
        termin::RenderEngine* render_engine = web_player->engine->rendering_manager.render_engine();
        render_engine->set_graphics_host(*web_player->graphics_host);
        termin::ShaderArtifactResolver::ReadCallback read_artifact;
        if (web_player->package.shader_runtime.resource_provider) {
            const auto provider = web_player->package.shader_runtime.resource_provider;
            tgfx::set_builtin_shader_root(web_player->package.shader_runtime.builtin_shader_root.c_str());
            tgfx::set_builtin_shader_read_callback([provider](std::string_view path, std::string& output) {
                if (!provider->contains(path))
                    return false;
                try {
                    const termin::runtime::RuntimePackageBytes bytes = provider->read(path);
                    output.assign(reinterpret_cast<const char*>(bytes.view().data()), bytes.view().size());
                    return true;
                } catch (const std::exception& exception) {
                    tc_log_error("TerminWebHost built-in shader read failed for '%.*s': %s",
                                 static_cast<int>(path.size()),
                                 path.data(),
                                 exception.what());
                    return false;
                }
            });
            read_artifact = [provider = web_player->package.shader_runtime.resource_provider](
                                std::string_view path, std::vector<std::uint8_t>& output) {
                if (!provider->contains(path))
                    return false;
                try {
                    const termin::runtime::RuntimePackageBytes bytes = provider->read(path);
                    output.assign(bytes.view().begin(), bytes.view().end());
                    return true;
                } catch (const std::exception& exception) {
                    tc_log_error("TerminWebHost shader artifact read failed for '%.*s': %s",
                                 static_cast<int>(path.size()),
                                 path.data(),
                                 exception.what());
                    return false;
                }
            };
        }
        render_engine->configure_shader_artifacts(web_player->package.shader_runtime.artifact_root,
                                                  web_player->package.shader_runtime.cache_root,
                                                  web_player->package.shader_runtime.compiler_path,
                                                  false,
                                                  std::move(read_artifact));

        termin::SceneManager& scene_manager = web_player->engine->scene_manager;
        for (const termin::runtime::RuntimePackageScene& packaged : web_player->package.scenes) {
            const termin::SceneKey key{packaged.identity, termin::SceneRole::Runtime};
            if (!scene_manager.register_scene(key, packaged.scene.handle())) {
                throw std::runtime_error("failed to register packaged scene '" + packaged.identity + "'");
            }
            scene_manager.set_scene_path(key, packaged.scene.source_path());
            scene_manager.set_mode(key, TC_SCENE_MODE_INACTIVE);
            web_player->registered_scene_keys.push_back(key);
        }
        scene_manager.set_mode(termin::SceneKey{web_player->package.entry_scene_identity, termin::SceneRole::Runtime},
                               TC_SCENE_MODE_PLAY);

        termin::RenderingManager& manager = web_player->engine->rendering_manager;
        manager.set_display_factory([](const std::string& name) { return create_web_player_display(name); });
        web_player->viewports = manager.attach_scene_full(web_player->package.scene.handle());
        if (web_player->viewports.empty()) {
            throw std::runtime_error("entry scene render_mount created no browser viewports");
        }
        for (tc_viewport_handle viewport : web_player->viewports) {
            if (!tc_viewport_alive(viewport))
                continue;
            const char* mode = tc_viewport_get_input_mode(viewport);
            if (mode && (std::strcmp(mode, "none") == 0 || std::strcmp(mode, "editor") == 0)) {
                continue;
            }
            if (mode && mode[0] != '\0' && std::strcmp(mode, "simple") != 0 && std::strcmp(mode, "basic") != 0) {
                throw std::runtime_error(std::string("unsupported browser viewport input mode: ") + mode);
            }
            tc_viewport_input_manager* input = tc_viewport_input_manager_new(viewport);
            if (!input) {
                const char* name = tc_viewport_get_name(viewport);
                throw std::runtime_error(std::string("failed to create browser input manager for viewport '") +
                                         (name ? name : "") + "'");
            }
            web_player->viewport_input_managers.push_back(input);
        }
        web_player->presentation_display = manager.get_display_by_name("Main");
        if (!tc_display_handle_valid(web_player->presentation_display)) {
            throw std::runtime_error("entry scene render_mount has no 'Main' display");
        }
        scene_manager.request_render();
        tc_log_info("TerminWebHost: attached packaged scene '%s' entities=%zu viewports=%zu input_managers=%zu",
                    web_player->package.entry_scene_identity.c_str(),
                    web_player->package.scene.entity_count(),
                    web_player->viewports.size(),
                    web_player->viewport_input_managers.size());
    } catch (const std::exception& exception) {
        web_host_error = exception.what();
        tc_log_error("TerminWebHost load failed: %s", web_host_error.c_str());
        unload_web_host_package();
        return 0;
    }
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_load_headless(const char* root_path) {
    unload_web_host_package();
    web_host_error.clear();
    if (!web_pending_package_reader && (root_path == nullptr || root_path[0] == '\0')) {
        web_host_error = "runtime package root must not be empty";
        tc_log_error("TerminWebHost: %s", web_host_error.c_str());
        return 0;
    }
    termin::runtime::RuntimePackageLoadOptions options;
    options.bootstrap_profile = termin::bootstrap::RuntimeBootstrapProfile::Minimal;
    termin::runtime::RuntimePackageLoader loader;
    if (web_pending_package_reader) {
        web_headless_package = loader.load(std::move(web_pending_package_reader), options);
    } else {
        web_headless_package = loader.load(root_path, options);
    }
    if (!web_headless_package.ok) {
        web_host_error = web_headless_package.message;
        unload_web_host_package();
        termin::bootstrap::shutdown_runtime();
        return 0;
    }
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_set_package_blob(const std::uint8_t* data, std::size_t size) {
    web_pending_package_reader.reset();
    web_host_error.clear();
    if (!data || size == 0) {
        web_host_error = "runtime package blob must not be empty";
        tc_log_error("TerminWebHost: %s", web_host_error.c_str());
        return 0;
    }
    try {
        auto blob = std::make_shared<const std::vector<std::uint8_t>>(data, data + size);
        web_pending_package_reader =
            termin::runtime::open_runtime_package_blob(std::move(blob), "browser-runtime-package");
        return 1;
    } catch (const std::exception& exception) {
        web_host_error = exception.what();
        tc_log_error("TerminWebHost package blob rejected: %s", web_host_error.c_str());
        return 0;
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_tick(double delta_seconds) {
    if (web_headless_package.ok && web_headless_package.scene.valid()) {
        try {
            web_headless_package.scene.update(delta_seconds);
            ++web_host_frame_count;
            return 1;
        } catch (const std::exception& exception) {
            web_host_error = exception.what();
            tc_log_error("TerminWebHost headless update failed: %s", web_host_error.c_str());
            return 0;
        }
    }
    if (!web_player || !web_player->package.ok || !web_player->package.scene.valid() || !web_player->engine) {
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
        if (web_player->webgpu_device && web_player->webgpu_device->has_device_error()) {
            web_player_graphics_error = web_player->webgpu_device->device_error_message();
            web_player_graphics_status = -4;
            throw std::runtime_error(web_player_graphics_error.empty() ? "WebGPU device lost"
                                                                       : web_player_graphics_error);
        }
        web_player->engine->scene_manager.request_render();
        const bool rendered = web_player->engine->tick_and_render(delta_seconds);
        if (rendered && !present_web_player_canvas()) {
            throw std::runtime_error("failed to present Termin render output to canvas");
        }
        ++web_host_frame_count;
        return 1;
    } catch (const std::exception& exception) {
        web_host_error = exception.what();
        tc_log_error("TerminWebHost update failed: %s", web_host_error.c_str());
        return 0;
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_loop_start() {
    if (!web_player || !web_player->engine || web_player_graphics_status != 2) {
        web_host_error = "cannot start browser frame loop before the render host is ready";
        tc_log_error("TerminWebHost: %s", web_host_error.c_str());
        return 0;
    }
    if (web_host_loop_running)
        return 1;
    web_host_loop_running = true;
    web_host_loop_last_timestamp = -1.0;
    emscripten_request_animation_frame_loop(&web_host_animation_frame, nullptr);
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE void termin_web_host_loop_stop() {
    web_host_loop_running = false;
    web_host_loop_last_timestamp = -1.0;
}

extern "C" EMSCRIPTEN_KEEPALIVE void termin_web_host_unload() {
    unload_web_host_package();
    web_host_error.clear();
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_host_error() {
    return web_host_error.c_str();
}

extern "C" EMSCRIPTEN_KEEPALIVE std::uint32_t termin_web_host_frame_count() {
    return web_host_frame_count;
}

extern "C" EMSCRIPTEN_KEEPALIVE std::size_t termin_web_host_entity_count() {
    if (web_headless_package.ok && web_headless_package.scene.valid()) {
        return web_headless_package.scene.entity_count();
    }
    return web_player && web_player->package.ok && web_player->package.scene.valid()
               ? web_player->package.scene.entity_count()
               : 0;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_resize(uint32_t width, uint32_t height) {
    if (!web_player || !web_player->device || !tc_display_handle_valid(web_player->presentation_display) ||
        web_player_graphics_status != 2) {
        return 0;
    }
    if (width == 0 || height == 0) {
        web_host_error = "browser canvas size must be positive";
        tc_log_error("TerminWebHost resize failed: %s", web_host_error.c_str());
        return 0;
    }
    if (web_player->width == width && web_player->height == height)
        return 1;
    try {
        if (web_player->webgpu_device) {
            web_player->webgpu_device->configure_surface(width, height);
        } else if (emscripten_set_canvas_element_size("#termin-canvas",
                                                      static_cast<int>(width),
                                                      static_cast<int>(height)) != EMSCRIPTEN_RESULT_SUCCESS) {
            throw std::runtime_error("failed to resize the WebGL2 canvas drawing buffer");
        }
        if (!tc_display_resize(web_player->presentation_display, static_cast<int>(width), static_cast<int>(height))) {
            throw std::runtime_error("offscreen display rejected browser resize");
        }
        web_player->width = width;
        web_player->height = height;
        web_player->engine->scene_manager.request_render();
        return 1;
    } catch (const std::exception& exception) {
        web_host_error = exception.what();
        tc_log_error("TerminWebHost resize failed: %s", web_host_error.c_str());
        return 0;
    }
}

namespace {

    bool web_host_input_ready() {
        return web_player && web_player->engine && tc_display_handle_valid(web_player->presentation_display);
    }

} // namespace

extern "C" EMSCRIPTEN_KEEPALIVE int
termin_web_host_dispatch_pointer(uint32_t pointer_id, int device, int phase, double x, double y, double pressure) {
    return web_host_input_ready() &&
           tc_display_dispatch_pointer(
               web_player->presentation_display, pointer_id, device, phase, x, y, static_cast<float>(pressure));
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_dispatch_mouse_move(double x, double y) {
    return web_host_input_ready() && tc_display_dispatch_pointer_move(web_player->presentation_display, x, y);
}

extern "C" EMSCRIPTEN_KEEPALIVE int
termin_web_host_dispatch_mouse_button(double x, double y, int button, int action, int mods, uint32_t click_count) {
    return web_host_input_ready() && tc_display_dispatch_pointer_button(
                                         web_player->presentation_display, x, y, button, action, mods, click_count);
}

extern "C" EMSCRIPTEN_KEEPALIVE int
termin_web_host_dispatch_wheel(double x, double y, double wheel_x, double wheel_y, int mods) {
    return web_host_input_ready() &&
           tc_display_dispatch_wheel(web_player->presentation_display, x, y, wheel_x, wheel_y, mods);
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_dispatch_key(int key, int scancode, int action, int mods) {
    return web_host_input_ready() &&
           tc_display_dispatch_key(web_player->presentation_display, key, scancode, action, mods);
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_dispatch_text(const char* text_utf8) {
    return web_host_input_ready() && text_utf8 &&
           tc_display_dispatch_text_utf8(web_player->presentation_display, text_utf8);
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_dispatch_focus_lost() {
    return web_host_input_ready() && tc_display_dispatch_focus_lost(web_player->presentation_display);
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_visual_scene_render() {
    if (!web_player || web_player_graphics_status != 2 || !web_player->device || !web_player->graphics_host) {
        web_visual_scene_error = "browser graphics player is not initialized";
        tc_log_error("TerminWebVisualScene: %s", web_visual_scene_error.c_str());
        return 0;
    }
    tgfx::TextureHandle presentation_texture;
    bool owns_presentation_texture = false;
    if (web_player->backend == WebGraphicsBackend::WebGPU) {
        presentation_texture = web_player->webgpu_device->acquire_surface_texture();
    } else if (web_player->backend == WebGraphicsBackend::WebGL2) {
        if (!web_player->webgl2_context->make_current()) {
            web_visual_scene_error = "failed to make WebGL2 context current";
            tc_log_error("TerminWebVisualScene: %s", web_visual_scene_error.c_str());
            return 0;
        }
        tgfx::TextureDesc presentation_desc;
        presentation_desc.width = web_player->width;
        presentation_desc.height = web_player->height;
        presentation_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        presentation_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        presentation_texture = web_player->device->create_texture(presentation_desc);
        owns_presentation_texture = true;
    }
    const bool rendered = termin::web::render_visual_scene_example(*web_player->device,
                                                                   *web_player->graphics_host,
                                                                   presentation_texture,
                                                                   web_player->width,
                                                                   web_player->height,
                                                                   web_visual_scene_error);
    if (rendered && web_player->backend == WebGraphicsBackend::WebGL2) {
        web_player->webgl2_device->present_to_default_framebuffer(
            presentation_texture, static_cast<int>(web_player->width), static_cast<int>(web_player->height));
        web_player->device->present();
    }
    if (owns_presentation_texture) {
        web_player->device->destroy(presentation_texture);
    }
    return rendered ? 1 : 0;
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_visual_scene_error() {
    return web_visual_scene_error.c_str();
}

extern "C" EMSCRIPTEN_KEEPALIVE int
termin_web_host_graphics_start(uint32_t width, uint32_t height, int requested_backend) {
    if (web_player_graphics_status != 0)
        return web_player_graphics_status;
    if (width == 0 || height == 0) {
        web_player_graphics_error = "browser canvas size must be positive";
        web_player_graphics_status = -1;
        return web_player_graphics_status;
    }
    web_player = std::make_unique<WebPlayerState>();
    web_player->width = width;
    web_player->height = height;

    if (requested_backend == static_cast<int>(WebGraphicsBackend::WebGL2)) {
        try {
            auto context = std::make_unique<WebGL2Context>();
            EmscriptenWebGLContextAttributes attributes;
            emscripten_webgl_init_context_attributes(&attributes);
            attributes.alpha = EM_TRUE;
            attributes.depth = EM_TRUE;
            attributes.stencil = EM_TRUE;
            attributes.antialias = EM_FALSE;
            attributes.majorVersion = 2;
            attributes.minorVersion = 0;
            attributes.enableExtensionsByDefault = EM_TRUE;
            context->handle = emscripten_webgl_create_context("#termin-canvas", &attributes);
            if (context->handle <= 0) {
                throw std::runtime_error("browser refused to create a WebGL 2 context");
            }
            if (!context->make_current()) {
                throw std::runtime_error("failed to make the WebGL 2 context current");
            }
            auto device =
                std::make_unique<tgfx::OpenGLRenderDevice>(tgfx::OpenGLDeviceCreateInfo{tgfx::GlFeatureTier::WebGL2});
            web_player->device = device.get();
            web_player->webgl2_device = device.get();
            web_player->backend = WebGraphicsBackend::WebGL2;
            web_player->webgl2_context = std::move(context);
            web_player->graphics_host = tgfx::GraphicsHost::adopt_application_device(std::move(device));
            web_player_graphics_status = 2;
            tc_log_info("TerminWebHost graphics initialized: backend=webgl2 target=webgl2");
            return web_player_graphics_status;
        } catch (const std::exception& exception) {
            web_player_graphics_error = exception.what();
            web_player_graphics_status = -3;
            tc_log_error("TerminWebHost WebGL2 initialization failed: %s", web_player_graphics_error.c_str());
            web_player.reset();
            return web_player_graphics_status;
        }
    }
    if (requested_backend != static_cast<int>(WebGraphicsBackend::WebGPU)) {
        web_player_graphics_error = "unsupported browser graphics backend request";
        web_player_graphics_status = -1;
        web_player.reset();
        tc_log_error("TerminWebHost: %s", web_player_graphics_error.c_str());
        return web_player_graphics_status;
    }

    web_player_graphics_status = 1;
    tgfx::WebGpuDeviceRequest request;
    request.canvas_selector = "#termin-canvas";
    request.width = width;
    request.height = height;
    tgfx::WebGpuRenderDevice::request_async(
        request, [](std::unique_ptr<tgfx::WebGpuRenderDevice> device, std::string error) {
            if (!device || !web_player) {
                web_player_graphics_error = error.empty() ? "WebGPU device initialization failed" : std::move(error);
                web_player_graphics_status = -2;
                tc_log_error("TerminWebHost: %s", web_player_graphics_error.c_str());
                return;
            }
            try {
                web_player->device = device.get();
                web_player->webgpu_device = device.get();
                web_player->backend = WebGraphicsBackend::WebGPU;
                web_player->graphics_host = tgfx::GraphicsHost::adopt_application_device(std::move(device));
                web_player_graphics_status = 2;
                tc_log_info("TerminWebHost graphics initialized: backend=webgpu target=webgpu");
            } catch (const std::exception& exception) {
                web_player_graphics_error = exception.what();
                web_player_graphics_status = -3;
                tc_log_error("TerminWebHost graphics initialization failed: %s", web_player_graphics_error.c_str());
            }
        });
    return web_player_graphics_status;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_graphics_status() {
    if (web_player && web_player->webgpu_device && web_player->webgpu_device->has_device_error()) {
        web_player_graphics_error = web_player->webgpu_device->device_error_message();
        web_player_graphics_status = -4;
    }
    if (web_player && web_player->webgl2_context &&
        emscripten_is_webgl_context_lost(web_player->webgl2_context->handle)) {
        web_player_graphics_error = "WebGL2 context lost";
        web_player_graphics_status = -4;
        tc_log_error("TerminWebHost: %s", web_player_graphics_error.c_str());
    }
    return web_player_graphics_status;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_graphics_backend() {
    return web_player ? static_cast<int>(web_player->backend) : 0;
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_host_graphics_error() {
    return web_player_graphics_error.c_str();
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_render_smoke_start() {
    if (web_render_status != 0)
        return web_render_status;
    web_render_status = 1;
    tgfx::WebGpuDeviceRequest request;
    request.canvas_selector = "#termin-canvas";
    request.width = 640;
    request.height = 360;
    tgfx::WebGpuRenderDevice::request_async(request,
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

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_render_smoke_resize(uint32_t width, uint32_t height) {
    if (!web_render_state || width == 0 || height == 0)
        return 0;
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
