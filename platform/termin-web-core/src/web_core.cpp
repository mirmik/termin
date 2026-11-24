#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <optional>
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
#include <termin/gui_native/button.hpp>
#include <termin/physics_components/components.hpp>
#include <termin/platform/offscreen_render_surface.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin/ui/tc_scene_ui_document_capability.h>
#include <termin/ui/ui_component.hpp>
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
#include "web_graphics_assets.hpp"
#include "web_chart2d.hpp"
#include "web_chart3d.hpp"
#include "web_render_shaders.hpp"
#include "web_rigid_body_height_trace.hpp"
#include "web_scene_pick.hpp"

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

    struct WebButtonBinding {
        tc_ui_document_handle document;
        tc_widget_handle widget;
        size_t connection = 0;

        termin::gui_native::Button* resolve() const {
            auto* entry = tc_ui_document_resolve_widget(document, widget);
            return entry && entry->native_language == TC_LANGUAGE_CXX
                       ? dynamic_cast<termin::gui_native::Button*>(static_cast<termin::gui_native::Widget*>(entry->body))
                       : nullptr;
        }
    };

    EM_JS(void, notify_ui_button_click, (uint32_t id), {
        const listeners = Module['terminUiButtonListeners'];
        const listener = listeners && listeners.get(id);
        if (listener) {
            queueMicrotask(() => {
                if (listeners.get(id) === listener) listener();
            });
        }
    });

    struct WebPlayerState {
        std::string canvas_selector = "#termin-canvas";
        std::unique_ptr<WebGL2Context> webgl2_context;
        std::unique_ptr<tgfx::GraphicsHost> graphics_host;
        std::unique_ptr<termin::web::WebChart2D> chart;
        std::unique_ptr<termin::web::WebChart3D> chart3d;
        tgfx::IRenderDevice* device = nullptr;
        tgfx::WebGpuRenderDevice* webgpu_device = nullptr;
        tgfx::OpenGLRenderDevice* webgl2_device = nullptr;
        tgfx::OutputTransformRenderer output_transform;
        tgfx::TextureHandle webgl2_srgb_attachment;
        tgfx::TextureHandle webgl2_presentation_texture;
        WebGraphicsBackend backend = WebGraphicsBackend::None;
        std::unique_ptr<termin::EngineCore> engine;
        termin::runtime::RuntimePackageLoadResult package;
        std::unordered_map<uint32_t, WebButtonBinding> button_bindings;
        termin::Entity height_trace_entity;
        std::vector<termin::SceneKey> registered_scene_keys;
        std::vector<tc_viewport_handle> viewports;
        std::vector<tc_viewport_input_manager*> viewport_input_managers;
        std::vector<tc_display_handle> owned_displays;
        tc_display_handle presentation_display = TC_DISPLAY_HANDLE_INVALID;
        uint32_t width = 640;
        uint32_t height = 360;
    };

    std::unique_ptr<WebPlayerState> web_player;

    termin::RigidBodyComponent& find_rigid_body(const char* uuid) {
        if (!web_player || !web_player->engine || !web_player->package.scene.valid())
            throw std::runtime_error("there is no active browser scene");
        auto* pool = tc_scene_entity_pool(web_player->package.scene.handle());
        const auto id = uuid && *uuid ? tc_entity_pool_find_by_uuid(pool, uuid) : TC_ENTITY_ID_INVALID;
        if (!tc_entity_id_valid(id)) throw std::runtime_error("rigid body entity UUID was not found in the scene");
        auto* component = termin::Entity(pool, id).get_component<termin::RigidBodyComponent>();
        if (!component) throw std::runtime_error("entity has no RigidBodyComponent");
        return *component;
    }

    termin::web::RigidBodyHeightTrace* active_height_trace() {
        if (!web_player || !web_player->height_trace_entity.valid()) return nullptr;
        return web_player->height_trace_entity.get_component<termin::web::RigidBodyHeightTrace>();
    }

    tc_widget* find_ui_widget(const char* uuid, const char* name) {
        if (!web_player || !web_player->engine || !web_player->package.scene.valid())
            throw std::runtime_error("there is no active browser scene");
        if (!uuid || !name || !*uuid || !*name) throw std::invalid_argument("expected a UI entity UUID and widget name");
        auto* pool = tc_scene_entity_pool(web_player->package.scene.handle());
        const auto entity_id = tc_entity_pool_find_by_uuid(pool, uuid);
        if (!tc_entity_id_valid(entity_id)) throw std::runtime_error("UI entity was not found");
        auto* ui = termin::Entity(pool, entity_id).get_component<termin::UIComponent>();
        if (!ui || !ui->has_document()) throw std::runtime_error("entity has no active UI document");
        auto* widget = tc_ui_document_resolve_widget(ui->document().handle(), ui->named_widget(name));
        if (!widget) throw std::runtime_error("named widget is no longer available");
        return widget;
    }

    const char* ui_widget_error(const char* operation, const char* uuid, const char* name, const std::exception& e) {
        static std::string error;
        error = e.what();
        tc_log_error("TerminWebHost %s '%s' on '%s': %s", operation, name ? name : "", uuid ? uuid : "", error.c_str());
        return error.c_str();
    }

    void update_scene_ui_density(WebPlayerState& player) {
        if (!player.package.scene.valid())
            return;
        double css_width = 0, css_height = 0;
        if (emscripten_get_element_css_size(player.canvas_selector.c_str(), &css_width, &css_height) !=
            EMSCRIPTEN_RESULT_SUCCESS) {
            throw std::runtime_error("could not measure the browser canvas");
        }
        // A hidden canvas has no CSS extent. ResizeObserver publishes its size when it becomes visible.
        if (css_width <= 0 || css_height <= 0)
            return;
        const tc_ui_size extent{static_cast<float>(player.width), static_cast<float>(player.height)};
        auto metrics = tc_ui_presentation_metrics_identity(extent);
        metrics.density_scale = static_cast<float>(player.width / css_width);
        auto apply_metrics = [](tc_component* component, void* data) {
            tc_scene_ui_document_snapshot snapshot{};
            if (tc_scene_ui_document_snapshot_get(component, &snapshot) &&
                !tc_ui_document_set_presentation_metrics(snapshot.document,
                                                         static_cast<const tc_ui_presentation_metrics*>(data))) {
                tc_log_error("TerminWebHost: failed to update UI metrics on '%s'", tc_component_get_type_name(component));
            }
            return true;
        };
        tc_scene_foreach_with_capability(player.package.scene.handle(), tc_scene_ui_document_capability_id(),
                                         apply_metrics, &metrics, TC_SCENE_FILTER_NONE);
    }

    termin::runtime::RuntimePackageLoadResult web_headless_package;
    int web_player_graphics_status = 0;
    std::string web_player_graphics_error;
    std::string web_host_error;
    // A rejected probe is a synchronous caller error. The render loop separately
    // monitors web_host_error for fatal simulation/render failures.
    std::string web_height_trace_error;
    std::string web_visual_scene_error;
    std::string web_chart_error;
    std::shared_ptr<termin::runtime::RuntimePackageReader> web_pending_package_reader;
    std::uint32_t web_host_frame_count = 0;
    std::optional<int> web_host_frame_request;
    double web_host_loop_last_timestamp = -1.0;

    extern "C" int termin_web_host_tick(double delta_seconds);
    extern "C" int termin_web_host_graphics_status();

    void stop_web_host_loop() {
        if (web_host_frame_request) {
            emscripten_cancel_animation_frame(*web_host_frame_request);
            web_host_frame_request.reset();
        }
        web_host_loop_last_timestamp = -1.0;
    }

    EM_BOOL web_host_animation_frame(double timestamp_ms, void*) {
        // Keep an actual, cancelable request even while tick() is executing.
        web_host_frame_request = emscripten_request_animation_frame(&web_host_animation_frame, nullptr);
        const double elapsed_ms = timestamp_ms - web_host_loop_last_timestamp;
        // Browsers can suspend callbacks while the page is hidden. Resume from
        // the current simulation state instead of passing the suspension to physics.
        const double delta_seconds =
            web_host_loop_last_timestamp >= 0.0 && elapsed_ms >= 0.0 && elapsed_ms <= 1000.0 ? elapsed_ms / 1000.0 : 0.0;
        web_host_loop_last_timestamp = timestamp_ms;
        if (!termin_web_host_tick(delta_seconds))
            stop_web_host_loop();
        return EM_FALSE;
    }

    void unload_web_host_package() {
        stop_web_host_loop();
        web_headless_package.destroy();
        tgfx::set_builtin_shader_read_callback({});
        tgfx::set_builtin_shader_root(nullptr);
        if (!web_player) {
            web_host_frame_count = 0;
            return;
        }
        if (web_player->webgl2_context && !web_player->webgl2_context->make_current()) {
            tc_log_error("TerminWebHost unload: failed to make WebGL2 context current");
        }
        web_player->chart.reset();
        web_player->chart3d.reset();
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
        if (web_player->webgl2_srgb_attachment) {
            web_player->device->destroy(web_player->webgl2_srgb_attachment);
        }
        if (web_player->webgl2_presentation_texture && web_player->device) {
            web_player->device->destroy(web_player->webgl2_presentation_texture);
            web_player->webgl2_presentation_texture = {};
        }
        if (web_player->graphics_host) {
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

    tgfx::TextureHandle webgl2_canvas_target(tgfx::PixelFormat format) {
        if (!web_player->webgl2_context->make_current()) {
            throw std::runtime_error("failed to make WebGL2 context current for presentation");
        }
        auto& texture = tgfx::is_srgb_format(format) ? web_player->webgl2_srgb_attachment
                                                     : web_player->webgl2_presentation_texture;
        const auto current = texture ? web_player->device->texture_desc(texture) : tgfx::TextureDesc{};
        if (texture && current.width == web_player->width && current.height == web_player->height &&
            current.format == format) {
            return texture;
        }
        tgfx::TextureDesc desc;
        desc.width = web_player->width;
        desc.height = web_player->height;
        desc.format = format;
        desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopySrc;
        const auto replacement = web_player->device->create_texture(desc);
        if (!replacement) {
            throw std::runtime_error("failed to allocate WebGL2 presentation texture");
        }
        if (texture) {
            web_player->device->destroy(texture);
        }
        texture = replacement;
        return texture;
    }

    bool encode_canvas(tgfx::TextureHandle input, tgfx::TextureHandle output, tgfx::OutputDitherMode dither) {
        auto& context = web_player->graphics_host->context();
        context.begin_frame();
        bool transformed;
        try {
            transformed = web_player->output_transform.record(
                context, input, output,
                {.sampled_input_encoding = tgfx::TextureEncoding::Linear,
                 .target_encoding = tgfx::TextureEncoding::SRGB, .dither = dither, .target_rgb_bits = 8});
        } catch (...) {
            context.end_frame();
            throw;
        }
        context.end_frame();
        return transformed;
    }

    tgfx::TextureHandle encode_to_canvas_target(tgfx::TextureHandle input, tgfx::OutputDitherMode dither) {
        // Store sRGB display codes in a UNorm target. WebGPU can draw directly
        // into the canvas. WebGL2 transports the encoded texture by framebuffer blit.
        const auto output = web_player->webgpu_device
                                ? web_player->webgpu_device->acquire_surface_texture(tgfx::TextureEncoding::Linear)
                                : webgl2_canvas_target(tgfx::PixelFormat::RGBA8_UNorm);
        if (!encode_canvas(input, output, dither)) {
            throw std::runtime_error("canvas output transform failed");
        }
        return output;
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
        const auto target = encode_to_canvas_target(tgfx::TextureHandle{output_texture_id},
                                                    tgfx::OutputDitherMode::StableSpatial);
        if (web_player->webgl2_device) {
            web_player->webgl2_device->present_to_default_framebuffer(
                target, static_cast<int>(web_player->width), static_cast<int>(web_player->height));
        }
        web_player->device->present();
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
        // Exercise mip-zero attachment views while subsequent blits sample
        // through a view exposing the complete chain.
        copy_desc.mip_levels = 4;
        copy_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::ColorAttachment |
                          tgfx::TextureUsage::CopySrc | tgfx::TextureUsage::CopyDst;
        const tgfx::TextureHandle copy = state.device->create_texture(copy_desc);
        const termin::Bounds2i full_source = termin::Bounds2i::from_size(texture_size, texture_size);
        state.device->clear_texture(copy, {0.0f, 0.0f, 0.0f, 1.0f}, full_source);
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
        if (cycle == 0)
            termin::bootstrap::bootstrap_runtime(termin::bootstrap::RuntimeBootstrapProfile::Minimal);
        termin::bootstrap::bootstrap_runtime(termin::bootstrap::RuntimeBootstrapProfile::Render);
        const size_t current_component_type_count = tc_component_registry_type_count();
        const size_t current_pass_type_count = tc_pass_registry_type_count();
        const bool registry_complete = tc_component_registry_has("MeshComponent") &&
                                       tc_component_registry_has("MeshRenderer") &&
                                       tc_component_registry_has("ColliderComponent") &&
                                       tc_component_registry_has("RigidBodyComponent") &&
                                       tc_component_registry_has("PhysicsWorldComponent") &&
                                       tc_component_registry_has("UIComponent") &&
                                       tc_kind_exists("ui_document") &&
                                       tc_pass_registry_has("ColorPass") &&
                                       tc_pass_registry_has("UIWidgetPass") &&
                                       tc_pass_registry_has("SkyBoxPass") &&
                                       tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_COLLISION_WORLD) &&
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
            tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_COLLISION_WORLD) ||
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
    if (setenv("TERMIN_UI_FONT", termin::web::default_font_path, 0) != 0) {
        web_host_error = "failed to configure the embedded UI font";
        tc_log_error("TerminWebHost: %s", web_host_error.c_str());
        return 0;
    }
    termin::runtime::RuntimePackageLoadOptions options;
    options.bootstrap_profile = termin::bootstrap::RuntimeBootstrapProfile::Render;
    options.scene_extensions = {TC_SCENE_EXT_TYPE_RENDER_MOUNT, TC_SCENE_EXT_TYPE_RENDER_STATE,
                                TC_SCENE_EXT_TYPE_COLLISION_WORLD};
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
            read_artifact = termin::web::bind_package_shader_sources(
                web_player->package.shader_runtime.resource_provider,
                web_player->package.shader_runtime.builtin_shader_root.c_str());
        }
        render_engine->configure_shader_artifacts(web_player->package.shader_runtime.artifact_root,
                                                  web_player->package.shader_runtime.cache_root,
                                                  web_player->package.shader_runtime.compiler_path,
                                                  false,
                                                  std::move(read_artifact));

        termin::SceneManager& scene_manager = web_player->engine->scene_manager;
        std::string classification_error;
        if (!scene_manager.configure_entity_classification(
                web_player->package.layer_names,
                web_player->package.flag_names,
                &classification_error)) {
            throw std::runtime_error(
                "failed to configure packaged entity classification: " + classification_error);
        }
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
        update_scene_ui_density(*web_player);
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
    if (!web_host_frame_request)
        web_host_frame_request = emscripten_request_animation_frame(&web_host_animation_frame, nullptr);
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE void termin_web_host_loop_stop() {
    stop_web_host_loop();
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

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_host_pick_entity(float x, float y) {
    try {
        if (!web_player || !web_player->engine || !web_player->package.scene.valid())
            throw std::runtime_error("there is no active browser scene");
        return termin::web::pick_mesh_entity(web_player->presentation_display, x, y);
    } catch (const std::exception& e) {
        web_host_error = e.what();
        tc_log_error("TerminWebHost pick: %s", web_host_error.c_str());
        return nullptr;
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_set_light_enabled(const char* uuid, int enabled) {
    try {
        if (!web_player || !web_player->engine || !web_player->package.scene.valid())
            throw std::runtime_error("there is no active browser scene");
        tc_entity_pool* pool = tc_scene_entity_pool(web_player->package.scene.handle());
        const auto id = uuid && *uuid ? tc_entity_pool_find_by_uuid(pool, uuid) : TC_ENTITY_ID_INVALID;
        if (!tc_entity_id_valid(id)) throw std::runtime_error("light entity UUID was not found in the scene");
        termin::Entity entity(pool, id);
        tc_component* light = entity.get_component_by_type_name("LightComponent");
        if (!light) throw std::runtime_error("entity has no LightComponent");
        tc_component_set_enabled(light, enabled != 0);
        web_player->engine->scene_manager.request_render();
        return 1;
    } catch (const std::exception& e) {
        web_host_error = e.what();
        tc_log_error("TerminWebHost set light: %s", web_host_error.c_str());
        return 0;
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_reset_rigid_body(const char* uuid) {
    try {
        if (!find_rigid_body(uuid).reset_to_initial_pose()) throw std::runtime_error("rigid body has not been initialized");
        web_player->engine->scene_manager.request_render();
        return 1;
    } catch (const std::exception& e) {
        web_host_error = e.what();
        tc_log_error("TerminWebHost reset rigid body '%s': %s", uuid ? uuid : "", web_host_error.c_str());
        return 0;
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_record_rigid_body_height(const char* uuid, int max_samples) {
    try {
        if (max_samples < 1) throw std::invalid_argument("expected a positive height trace sample limit");
        auto& component = find_rigid_body(uuid);
        const auto* body = component.rigid_body();
        if (!body) throw std::runtime_error("rigid body has not been initialized");
        auto owner = component.entity();
        auto* previous = active_height_trace();
        const double height = body->position().z;
        if (previous && web_player->height_trace_entity == owner) {
            previous->begin(height, max_samples);
        } else {
            auto trace = std::make_unique<termin::web::RigidBodyHeightTrace>();
            trace->begin(height, max_samples);
            if (!owner.add_component_ptr_checked(trace->c_component()))
                throw std::runtime_error("could not attach physics height trace");
            trace.release(); // The entity retained the component.
            if (previous) web_player->height_trace_entity.remove_component(previous);
            web_player->height_trace_entity = owner;
        }
        return 1;
    } catch (const std::exception& e) {
        web_height_trace_error = e.what();
        tc_log_error("TerminWebHost record rigid body height '%s': %s", uuid ? uuid : "", web_height_trace_error.c_str());
        return 0;
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_read_rigid_body_height_trace(double* output, int capacity) {
    try {
        auto* trace = active_height_trace();
        if (!trace) throw std::runtime_error("no active rigid body height trace");
        return trace->read(output, capacity);
    } catch (const std::exception& e) {
        web_height_trace_error = e.what();
        tc_log_error("TerminWebHost read rigid body height trace: %s", web_height_trace_error.c_str());
        return -1;
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_host_height_trace_error() {
    return web_height_trace_error.c_str();
}

extern "C" EMSCRIPTEN_KEEPALIVE const char*
termin_web_host_bind_ui_button(const char* uuid, const char* name, uint32_t id) {
    try {
        auto* widget = find_ui_widget(uuid, name);
        const WebButtonBinding binding{widget->document, widget->handle};
        auto* button = binding.resolve();
        if (!button) throw std::runtime_error("target widget is not a Button");
        auto [it, inserted] = web_player->button_bindings.emplace(id, binding);
        if (!inserted) throw std::runtime_error("duplicate UI button subscription");
        try {
            it->second.connection = button->clicked().connect(
                [id](termin::gui_native::Button&) { notify_ui_button_click(id); });
        } catch (...) {
            web_player->button_bindings.erase(it);
            throw;
        }
        return nullptr;
    } catch (const std::exception& e) {
        return ui_widget_error("bind UI button", uuid, name, e);
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE const char*
termin_web_host_set_ui_widget_enabled(const char* uuid, const char* name, int enabled) {
    try {
        tc_widget_set_enabled(find_ui_widget(uuid, name), enabled != 0);
        web_player->engine->scene_manager.request_render();
        return nullptr;
    } catch (const std::exception& e) {
        return ui_widget_error("set UI widget enabled", uuid, name, e);
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE void termin_web_host_unbind_ui_button(uint32_t id) {
    if (!web_player) return;
    const auto it = web_player->button_bindings.find(id);
    if (it == web_player->button_bindings.end()) return;
    if (auto* button = it->second.resolve())
        button->clicked().disconnect(it->second.connection);
    web_player->button_bindings.erase(it);
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_host_resize(uint32_t width, uint32_t height) {
    if (!web_player || !web_player->device || web_player_graphics_status != 2) {
        return 0;
    }
    if (width == 0 || height == 0) {
        web_host_error = "browser canvas size must be positive";
        tc_log_error("TerminWebHost resize failed: %s", web_host_error.c_str());
        return 0;
    }
    try {
        if (web_player->width == width && web_player->height == height) {
            update_scene_ui_density(*web_player);
            if (web_player->engine)
                web_player->engine->scene_manager.request_render();
            return 1;
        }
        if (web_player->webgpu_device) {
            web_player->webgpu_device->configure_surface(width, height);
        } else if (emscripten_set_canvas_element_size(web_player->canvas_selector.c_str(),
                                                      static_cast<int>(width),
                                                      static_cast<int>(height)) != EMSCRIPTEN_RESULT_SUCCESS) {
            throw std::runtime_error("failed to resize the WebGL2 canvas drawing buffer");
        }
        if (tc_display_handle_valid(web_player->presentation_display) &&
            !tc_display_resize(web_player->presentation_display, static_cast<int>(width), static_cast<int>(height))) {
            throw std::runtime_error("offscreen display rejected browser resize");
        }
        web_player->width = width;
        web_player->height = height;
        update_scene_ui_density(*web_player);
        if (web_player->engine) {
            web_player->engine->scene_manager.request_render();
        }
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

namespace {

    template <typename Draw> bool render_canvas(tgfx::TextureEncoding encoding, std::string& error, Draw draw) {
        error.clear();
        try {
            if (!web_player || termin_web_host_graphics_status() != 2) {
                throw std::runtime_error(web_player_graphics_error.empty() ? "browser graphics host is not ready"
                                                                           : web_player_graphics_error);
            }
            const auto target =
                web_player->webgpu_device
                    ? web_player->webgpu_device->acquire_surface_texture(encoding)
                    : webgl2_canvas_target(tgfx::pixel_format_for_encoding(tgfx::PixelFormat::RGBA8_UNorm, encoding));
            if (!draw(target)) {
                throw std::runtime_error(error.empty() ? "failed to render canvas" : error);
            }
            if (web_player->webgl2_device) {
                const auto output = encoding == tgfx::TextureEncoding::SRGB
                                        ? encode_to_canvas_target(target, tgfx::OutputDitherMode::Disabled)
                                        : target;
                web_player->webgl2_device->present_to_default_framebuffer(
                    output, static_cast<int>(web_player->width), static_cast<int>(web_player->height));
            }
            web_player->device->present();
            return true;
        } catch (const std::exception& exception) {
            error = exception.what();
            tc_log_error("TerminWeb canvas render: %s", error.c_str());
            return false;
        }
    }

    int chart_failure(const char* message) {
        web_chart_error = message;
        tc_log_error("TerminWebChart: %s", message);
        return 0;
    }

    tc_retained_chart2d* active_chart() {
        if (!web_player || !web_player->chart) {
            chart_failure("chart is not initialized");
            return nullptr;
        }
        return web_player->chart->chart();
    }

    tc_retained_chart3d* active_chart3d() {
        if (!web_player || !web_player->chart3d) {
            chart_failure("3D chart is not initialized");
            return nullptr;
        }
        return web_player->chart3d->chart();
    }

    void prepare_chart_host() {
        if (!web_player || web_player_graphics_status != 2 || web_player->engine || web_player->chart ||
            web_player->chart3d) {
            throw std::runtime_error("chart creation requires an unused browser graphics host");
        }
        if (!web_pending_package_reader) {
            throw std::runtime_error("chart graphics assets have not been supplied");
        }
        termin::web::configure_graphics_assets(*web_player->graphics_host, std::move(web_pending_package_reader));
    }

} // namespace

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_visual_scene_render() {
    return render_canvas(tgfx::TextureEncoding::Linear, web_visual_scene_error, [](tgfx::TextureHandle target) {
        return termin::web::render_visual_scene_example(
            *web_player->graphics_host, target, web_player->width, web_player->height, web_visual_scene_error);
    });
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart2d_create(
    const char* title, const char* x_label, const char* y_label, const char* series_name, float pixel_scale) {
    try {
        prepare_chart_host();
        web_player->chart = std::make_unique<termin::web::WebChart2D>(
            *web_player->graphics_host,
            tc_plot_rect2d{0, 0, static_cast<float>(web_player->width), static_cast<float>(web_player->height)},
            pixel_scale,
            title,
            x_label,
            y_label,
            series_name);
        web_chart_error.clear();
        return 1;
    } catch (const std::exception& exception) {
        return chart_failure(exception.what());
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int
termin_web_chart2d_set_data(const double* x, const double* y, size_t count, int fit) {
    if (!active_chart()) {
        return 0;
    }
    try {
        if (!web_player->chart->set_data(x, y, count, fit)) {
            return chart_failure("could not set line data");
        }
        return 1;
    } catch (const std::exception& exception) {
        return chart_failure(exception.what());
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart2d_set_range(double xmin, double xmax, double ymin, double ymax) {
    auto* chart = active_chart();
    if (!chart) {
        return 0;
    }
    return tc_retained_chart2d_set_range(chart, {xmin, xmax, ymin, ymax}) ? 1 : chart_failure("invalid range");
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart2d_range(double* out) {
    tc_plot_range2d range;
    auto* chart = active_chart();
    if (!out || !tc_retained_chart2d_range(chart, &range)) {
        return chart_failure("could not read chart range");
    }
    out[0] = range.x_min;
    out[1] = range.x_max;
    out[2] = range.y_min;
    out[3] = range.y_max;
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart2d_resize(uint32_t width, uint32_t height, float pixel_scale) {
    auto* chart = active_chart();
    if (!chart) {
        return 0;
    }
    if (!std::isfinite(pixel_scale) || pixel_scale <= 0) {
        return chart_failure("invalid pixel scale");
    }
    if (!termin_web_host_resize(width, height)) {
        return chart_failure(web_host_error.c_str());
    }
    const tc_plot_rect2d viewport{0, 0, static_cast<float>(width), static_cast<float>(height)};
    return tc_retained_chart2d_set_viewport(chart, viewport, pixel_scale) ? 1 : chart_failure("invalid chart viewport");
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart2d_pointer(int phase, float x, float y, int button) {
    auto* chart = active_chart();
    if (!chart) {
        return 0;
    }
    switch (phase) {
    case 0:
        return tc_retained_chart2d_pointer_down(chart, x, y, button);
    case 1:
        return tc_retained_chart2d_pointer_move(chart, x, y);
    case 2:
        return tc_retained_chart2d_pointer_up(chart, x, y, button);
    case 3:
        tc_retained_chart2d_cancel_interaction(chart);
        return 1;
    default:
        return chart_failure("unknown chart pointer phase");
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart2d_wheel(float x, float y, float steps, int x_only) {
    auto* chart = active_chart();
    return chart && tc_retained_chart2d_wheel(chart, x, y, steps, x_only);
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart2d_render() {
    if (!active_chart()) {
        return 0;
    }
    return render_canvas(tgfx::TextureEncoding::SRGB, web_chart_error, [](tgfx::TextureHandle target) {
        return web_player->chart->render(
            target.id, static_cast<int>(web_player->width), static_cast<int>(web_player->height));
    });
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart2d_destroy() {
    if (web_player && web_player->chart) {
        if (web_player->webgl2_context && !web_player->webgl2_context->make_current()) {
            return chart_failure("failed to make WebGL2 context current for chart disposal");
        }
        web_player->chart.reset();
    }
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_chart2d_error() {
    return web_chart_error.c_str();
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_create(const char* x_label, const char* y_label,
                                                              const char* z_label) {
    try {
        prepare_chart_host();
        web_player->chart3d = std::make_unique<termin::web::WebChart3D>(*web_player->graphics_host,
                                                                       x_label, y_label, z_label);
        web_chart_error.clear();
        return 1;
    } catch (const std::exception& exception) {
        return chart_failure(exception.what());
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_set_surface(
    const double* x, const double* y, const double* z, uint32_t rows, uint32_t columns, int fit) {
    if (!active_chart3d()) {
        return 0;
    }
    return web_player->chart3d->set_surface(x, y, z, rows, columns, fit) ? 1 : chart_failure("invalid surface data");
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_fit() {
    auto* chart = active_chart3d();
    if (!chart) {
        return 0;
    }
    tc_retained_chart3d_fit_camera(chart);
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_reset() {
    auto* chart = active_chart3d();
    if (!chart) {
        return 0;
    }
    tc_retained_chart3d_reset_camera(chart);
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_camera(double* out) {
    tc_orbit_camera3d_state camera{};
    if (!out || !tc_retained_chart3d_get_camera(active_chart3d(), &camera)) {
        return chart_failure("could not read 3D chart camera");
    }
    const std::array values{camera.target_x, camera.target_y, camera.target_z, camera.distance, camera.azimuth,
                            camera.elevation, camera.fov_y, camera.near_clip, camera.far_clip, camera.ortho_size};
    std::memcpy(out, values.data(), sizeof(double) * values.size());
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_resize(uint32_t width, uint32_t height) {
    if (!active_chart3d()) {
        return 0;
    }
    return termin_web_host_resize(width, height) ? 1 : chart_failure(web_host_error.c_str());
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_pointer(int phase, float x, float y, int button) {
    auto* chart = active_chart3d();
    if (!chart) {
        return 0;
    }
    if (!std::isfinite(x) || !std::isfinite(y)) {
        return chart_failure("invalid chart pointer position");
    }
    switch (phase) {
    case 0:
        return tc_retained_chart3d_pointer_down(chart, x, y, button);
    case 1:
        tc_retained_chart3d_pointer_move(chart, x, y);
        return 1;
    case 2:
    case 3:
        tc_retained_chart3d_pointer_up(chart, x, y, button);
        return 1;
    default:
        return chart_failure("unknown chart pointer phase");
    }
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_wheel(float x, float y, float steps) {
    return tc_retained_chart3d_wheel(active_chart3d(), x, y, steps);
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_render() {
    auto* chart = active_chart3d();
    if (!chart) {
        return 0;
    }
    // The retained renderer publishes linear RGB in a UNorm texture. Write
    // display-encoded bytes to the canvas' UNorm target on both backends.
    return render_canvas(tgfx::TextureEncoding::Linear, web_chart_error, [chart](tgfx::TextureHandle target) {
        const tgfx::TextureHandle source{tc_retained_chart3d_render(
            chart, static_cast<int>(web_player->width), static_cast<int>(web_player->height))};
        return source && encode_canvas(source, target, tgfx::OutputDitherMode::Disabled);
    });
}

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_chart3d_destroy() {
    if (web_player && web_player->chart3d) {
        if (web_player->webgl2_context && !web_player->webgl2_context->make_current()) {
            return chart_failure("failed to make WebGL2 context current for chart disposal");
        }
        web_player->chart3d.reset();
    }
    return 1;
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_chart3d_error() {
    return web_chart_error.c_str();
}

extern "C" EMSCRIPTEN_KEEPALIVE const char* termin_web_visual_scene_error() {
    return web_visual_scene_error.c_str();
}

extern "C" EMSCRIPTEN_KEEPALIVE int
termin_web_host_graphics_start(uint32_t width, uint32_t height, int requested_backend, const char* canvas_selector) {
    if (web_player_graphics_status != 0)
        return web_player_graphics_status;
    if (width == 0 || height == 0) {
        web_player_graphics_error = "browser canvas size must be positive";
        web_player_graphics_status = -1;
        return web_player_graphics_status;
    }
    web_player = std::make_unique<WebPlayerState>();
    if (canvas_selector && *canvas_selector) {
        web_player->canvas_selector = canvas_selector;
    }
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
            context->handle = emscripten_webgl_create_context(web_player->canvas_selector.c_str(), &attributes);
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
    request.canvas_selector = web_player->canvas_selector.c_str();
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
