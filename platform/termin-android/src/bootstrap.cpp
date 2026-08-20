#include "termin/android/bootstrap.h"

#include <chrono>
#include <cmath>
#include <cstdarg>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#ifdef __ANDROID__
#include <android/log.h>
#endif

#include <tcbase/tc_log.h>
#include <termin/bootstrap/bootstrap.hpp>
#include <termin/engine/engine_core.hpp>
#include <termin/framegraph_remote_target/target_service.hpp>
#include <termin/platform/offscreen_render_surface.hpp>
#include <termin/profiler_remote/target_service.hpp>
#include <termin/render/frame_graph_debugger.hpp>
#include <termin/render/tc_display_handle.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin/scene/tc_scene_render_ext.hpp>
#include <termin/tc_scene.hpp>
#include <termin/ui/tc_scene_ui_document_capability.h>
#include <termin_collision/termin_collision.h>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/graphics_host.hpp>

#ifdef __ANDROID__
#include <unistd.h>
#endif

extern "C" {
#include "core/tc_scene.h"
#include "core/tc_scene_render_mount.h"
#include "core/tc_scene_render_state.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_viewport_input_manager.h"
#include "tc_input_event.h"
#include "tc_profiler.h"
}

#ifdef __ANDROID__
#ifndef VK_USE_PLATFORM_ANDROID_KHR
#define VK_USE_PLATFORM_ANDROID_KHR
#endif
#include <tgfx2/shader_artifact_resolver.hpp>
#include <tgfx2/vulkan/vulkan_render_device.hpp>
#include <tgfx2/vulkan/vulkan_swapchain.hpp>
#include <vulkan/vulkan.h>
#include <vulkan/vulkan_android.h>
#endif

namespace {

    struct AndroidBootstrapState {
        std::string app_data_dir;
        std::string asset_root;
        std::string shader_artifact_root;
        bool shader_artifact_root_explicit = false;
        std::string native_lib_dir;
        ANativeWindow* window = nullptr;
        int32_t surface_width = 0;
        int32_t surface_height = 0;
        termin_android_presentation_metrics presentation_metrics{};
        bool has_presentation_metrics = false;
        bool initialized = false;
        bool profiler_enabled = false;
        std::unique_ptr<termin::profiler_remote::RemoteProfilerTarget> remote_profiler;
        uint64_t remote_profiler_pump_calls = 0;
        uint64_t remote_profiler_pump_ns = 0;
        uint64_t remote_profiler_last_log_bytes = 0;
        int64_t remote_profiler_last_log_time_nanos = 0;
        std::unique_ptr<termin::framegraph_remote_target::RemoteFrameGraphTarget> remote_framegraph;
        std::unique_ptr<termin::FrameGraphDebugger> remote_framegraph_debugger;
        uint64_t remote_framegraph_pump_calls = 0;
        uint64_t remote_framegraph_pump_ns = 0;
        uint64_t remote_framegraph_last_log_bytes = 0;
        int64_t remote_framegraph_last_log_time_nanos = 0;
#ifdef __ANDROID__
        struct QueuedPointerEvent {
            uint64_t pointer_id = 0;
            int device = TC_POINTER_DEVICE_TOUCH;
            int phase = TC_POINTER_MOVE;
            double x = 0.0;
            double y = 0.0;
            float pressure = 0.0f;
        };

        std::unique_ptr<tgfx::GraphicsHost> graphics_host;
        tgfx::VulkanRenderDevice* render_device = nullptr;
        uint32_t swapchain_width = 0;
        uint32_t swapchain_height = 0;
        bool renderer_create_failed = false;

        std::unique_ptr<termin::EngineCore> player_engine;
        termin::runtime::RuntimePackageLoadResult player_package;
        termin::TcSceneRef player_scene;
        std::unordered_map<std::string, termin::TcDisplay> player_displays;
        std::vector<termin::SceneKey> registered_scene_keys;
        tc_display_handle presentation_display = TC_DISPLAY_HANDLE_INVALID;
        std::vector<tc_viewport_handle> player_viewports;
        std::vector<tc_viewport_input_manager*> viewport_input_managers;
        std::vector<QueuedPointerEvent> pointer_events;
        uint32_t player_frame = 0;
        int64_t last_frame_time_nanos = 0;
        bool scene_extensions_registered = false;
#endif
    };

    std::mutex g_state_mutex;
    AndroidBootstrapState g_state;

    std::string infer_shader_artifact_root(const std::string& asset_root) {
        if (asset_root.empty()) {
            return "";
        }

        std::filesystem::path build_assets = std::filesystem::path(asset_root) / "assets";
        if (std::filesystem::is_directory(build_assets / "shaders" / "vulkan")) {
            return build_assets.string();
        }
        return asset_root;
    }

#ifdef __ANDROID__
    constexpr const char* kAndroidLogTag = "TerminAndroid";
    constexpr const char* kTcLogTag = "TerminTcLog";

    int tc_log_android_priority(tc_log_level level) {
        switch (level) {
        case TC_LOG_DEBUG:
            return ANDROID_LOG_DEBUG;
        case TC_LOG_INFO:
            return ANDROID_LOG_INFO;
        case TC_LOG_WARN:
            return ANDROID_LOG_WARN;
        case TC_LOG_ERROR:
            return ANDROID_LOG_ERROR;
        }
        return ANDROID_LOG_INFO;
    }

    void tc_log_android_callback(tc_log_level level, const char* message) {
        __android_log_write(tc_log_android_priority(level), kTcLogTag, message ? message : "");
    }

    void android_log_info(const char* fmt, ...) {
        va_list args;
        va_start(args, fmt);
        __android_log_vprint(ANDROID_LOG_INFO, kAndroidLogTag, fmt, args);
        va_end(args);
    }

    void android_log_error(const char* fmt, ...) {
        va_list args;
        va_start(args, fmt);
        __android_log_vprint(ANDROID_LOG_ERROR, kAndroidLogTag, fmt, args);
        va_end(args);
    }

    bool configure_ui_font_locked() {
        const std::filesystem::path font_path = std::filesystem::path(g_state.asset_root) / "fonts" / "DroidSans.ttf";
        if (!std::filesystem::is_regular_file(font_path)) {
            android_log_error("initialize: packaged UI font not found at '%s'", font_path.c_str());
            tc_log_error("termin_android_initialize: packaged UI font not found at '%s'", font_path.c_str());
            return false;
        }
        if (setenv("TERMIN_UI_FONT", font_path.c_str(), 1) != 0) {
            android_log_error("initialize: failed to configure TERMIN_UI_FONT='%s'", font_path.c_str());
            tc_log_error("termin_android_initialize: failed to configure TERMIN_UI_FONT='%s'", font_path.c_str());
            return false;
        }
        android_log_info("initialize: UI font='%s'", font_path.c_str());
        return true;
    }
#else
    void android_log_info(const char*, ...) {}
    void android_log_error(const char*, ...) {}
#endif

    void register_android_scene_extensions_locked() {
#ifdef __ANDROID__
        if (g_state.scene_extensions_registered) {
            return;
        }

        tc_scene_render_mount_extension_init();
        tc_scene_render_state_extension_init();
        termin_collision_runtime_init();
        g_state.scene_extensions_registered = true;
        android_log_info("scene extensions registered");
        tc_log_info("termin_android: scene extensions registered");
#endif
    }

#ifdef __ANDROID__

    bool create_renderer_locked();
    void destroy_renderer_locked();
    bool resize_renderer_locked(uint32_t width, uint32_t height);

    struct PresentationMetricsApplyContext {
        tc_ui_presentation_metrics metrics{};
        std::size_t applied_count = 0;
        std::size_t failed_count = 0;
    };

    bool apply_presentation_metrics_to_component(tc_component* component, void* user_data) {
        auto* context = static_cast<PresentationMetricsApplyContext*>(user_data);
        tc_scene_ui_document_snapshot snapshot{};
        if (!tc_scene_ui_document_snapshot_get(component, &snapshot)) {
            ++context->failed_count;
            tc_log_error("termin_android_presentation: failed to snapshot UI component "
                         "type='%s' source_id='%s'",
                         tc_component_get_type_name(component),
                         tc_component_get_source_id(component));
            return true;
        }
        if (!tc_ui_document_set_presentation_metrics(snapshot.document, &context->metrics)) {
            ++context->failed_count;
            tc_log_error("termin_android_presentation: failed to apply metrics to UI "
                         "component type='%s' source_id='%s'",
                         tc_component_get_type_name(component),
                         tc_component_get_source_id(component));
            return true;
        }
        ++context->applied_count;
        return true;
    }

    bool apply_player_presentation_metrics_locked() {
        if (!g_state.has_presentation_metrics || !g_state.player_scene.valid() || g_state.surface_width <= 0 ||
            g_state.surface_height <= 0) {
            return false;
        }

        const auto& platform = g_state.presentation_metrics;
        PresentationMetricsApplyContext context{
            .metrics =
                tc_ui_presentation_metrics{
                    platform.density_scale,
                    platform.font_scale,
                    tc_ui_size{
                        static_cast<float>(g_state.surface_width),
                        static_cast<float>(g_state.surface_height),
                    },
                    tc_ui_insets{
                        platform.safe_inset_left,
                        platform.safe_inset_top,
                        platform.safe_inset_right,
                        platform.safe_inset_bottom,
                    },
                },
        };
        if (!tc_ui_presentation_metrics_is_valid(&context.metrics)) {
            tc_log_error("termin_android_presentation: metrics are incompatible with "
                         "surface %dx%d density=%.3f font=%.3f "
                         "insets=[%.1f,%.1f,%.1f,%.1f]",
                         static_cast<int>(g_state.surface_width),
                         static_cast<int>(g_state.surface_height),
                         static_cast<double>(platform.density_scale),
                         static_cast<double>(platform.font_scale),
                         static_cast<double>(platform.safe_inset_left),
                         static_cast<double>(platform.safe_inset_top),
                         static_cast<double>(platform.safe_inset_right),
                         static_cast<double>(platform.safe_inset_bottom));
            return false;
        }

        tc_scene_foreach_with_capability(g_state.player_scene.handle(),
                                         tc_scene_ui_document_capability_id(),
                                         apply_presentation_metrics_to_component,
                                         &context,
                                         TC_SCENE_FILTER_NONE);
        if (context.failed_count != 0) {
            tc_log_error("termin_android_presentation: failed to update %zu UI "
                         "document(s); updated=%zu",
                         context.failed_count,
                         context.applied_count);
            return false;
        }
        return true;
    }

    void destroy_player_session_locked() {
        if (g_state.remote_framegraph) {
            g_state.remote_framegraph->detach_debugger();
        }
        g_state.remote_framegraph_debugger.reset();
        termin::RenderingManager* manager = g_state.player_engine ? &g_state.player_engine->rendering_manager : nullptr;

        for (tc_viewport_input_manager* input : g_state.viewport_input_managers) {
            tc_viewport_input_manager_free(input);
        }
        g_state.viewport_input_managers.clear();

        if (manager) {
            manager->set_display_factory(nullptr);
            if (g_state.player_scene.valid() && manager->topology().is_attached(g_state.player_scene.handle())) {
                manager->detach_scene_full(g_state.player_scene.handle(), true);
            }
            for (auto& [name, display] : g_state.player_displays) {
                (void)name;
                if (display.is_valid()) {
                    manager->remove_display(display.handle());
                }
            }
        }

        for (auto& [name, display] : g_state.player_displays) {
            (void)name;
            if (display.is_valid() && !display.destroy()) {
                tc_log_error("termin_android_player: failed to destroy display");
            }
        }
        g_state.player_displays.clear();
        g_state.presentation_display = TC_DISPLAY_HANDLE_INVALID;
        g_state.player_viewports.clear();

        if (g_state.player_engine) {
            for (const termin::SceneKey& key : g_state.registered_scene_keys) {
                g_state.player_engine->scene_manager.unregister_scene(key);
            }
        }
        g_state.registered_scene_keys.clear();
        g_state.player_scene = termin::TcSceneRef();
        g_state.player_package.destroy();

        if (g_state.player_engine) {
            if (!g_state.player_engine->shutdown()) {
                tc_log_error("termin_android_player: EngineCore shutdown failed");
            }
            g_state.player_engine.reset();
        }

        g_state.player_frame = 0;
        g_state.last_frame_time_nanos = 0;
    }

    void setup_player_input_locked() {
        int active_viewports = 0;
        for (tc_viewport_handle viewport : g_state.player_viewports) {
            if (!tc_viewport_alive(viewport))
                continue;

            const char* raw_mode = tc_viewport_get_input_mode(viewport);
            const std::string mode = raw_mode && raw_mode[0] != '\0' ? raw_mode : "simple";
            if (mode == "none" || mode == "editor") {
                if (mode == "editor") {
                    tc_log_warn("termin_android_player: viewport '%s' requests editor-only input mode",
                                tc_viewport_get_name(viewport));
                }
                continue;
            }
            if (mode != "simple" && mode != "basic") {
                tc_log_error("termin_android_player: unsupported input mode '%s' for viewport '%s'",
                             mode.c_str(),
                             tc_viewport_get_name(viewport));
                continue;
            }
            if (tc_viewport_get_input_manager(viewport)) {
                ++active_viewports;
                continue;
            }
            tc_viewport_input_manager* input = tc_viewport_input_manager_new(viewport);
            if (!input) {
                tc_log_error("termin_android_player: failed to create input manager for viewport '%s'",
                             tc_viewport_get_name(viewport));
                continue;
            }
            g_state.viewport_input_managers.push_back(input);
            ++active_viewports;
        }
        tc_log_info("termin_android_player: input configured for %d viewport(s)", active_viewports);
    }

    void dispatch_pointer_events_locked() {
        if (g_state.pointer_events.empty())
            return;
        if (!tc_display_handle_valid(g_state.presentation_display)) {
            tc_log_error("termin_android_player: dropping %zu pointer event(s) without presentation display",
                         g_state.pointer_events.size());
            g_state.pointer_events.clear();
            return;
        }

        for (const AndroidBootstrapState::QueuedPointerEvent& event : g_state.pointer_events) {
            if (!tc_display_dispatch_pointer(g_state.presentation_display,
                                             event.pointer_id,
                                             event.device,
                                             event.phase,
                                             event.x,
                                             event.y,
                                             event.pressure)) {
                tc_log_error("termin_android_player: failed to dispatch pointer id=%llu phase=%d",
                             (unsigned long long)event.pointer_id,
                             event.phase);
            }
        }
        g_state.pointer_events.clear();
    }

    tc_display_handle create_player_display_locked(const std::string& requested_name) {
        if (!g_state.render_device || g_state.swapchain_width == 0 || g_state.swapchain_height == 0) {
            tc_log_error("termin_android_player: display '%s' requested before graphics initialization",
                         requested_name.c_str());
            return TC_DISPLAY_HANDLE_INVALID;
        }

        const std::string name = requested_name.empty() ? "Main" : requested_name;
        auto existing = g_state.player_displays.find(name);
        if (existing != g_state.player_displays.end() && existing->second.is_valid()) {
            return existing->second.handle();
        }

        tc_display_handle handle = termin::create_offscreen_display(g_state.render_device,
                                                                    static_cast<int>(g_state.swapchain_width),
                                                                    static_cast<int>(g_state.swapchain_height),
                                                                    name.c_str());
        if (!tc_display_handle_valid(handle)) {
            tc_log_error("termin_android_player: failed to create offscreen display '%s'", name.c_str());
            return TC_DISPLAY_HANDLE_INVALID;
        }

        g_state.player_displays.emplace(name, termin::TcDisplay(handle));
        return handle;
    }

    bool ensure_player_session_locked() {
        if (g_state.player_engine && g_state.player_scene.valid() &&
            tc_display_handle_valid(g_state.presentation_display) && !g_state.player_viewports.empty()) {
            return true;
        }
        if (!g_state.graphics_host || !g_state.render_device) {
            tc_log_error("termin_android_player: graphics host is unavailable");
            return false;
        }
        if (g_state.asset_root.empty()) {
            tc_log_error("termin_android_player: asset_root is empty");
            return false;
        }

        const std::filesystem::path manifest_path = std::filesystem::path(g_state.asset_root) / "manifest.json";
        if (!std::filesystem::is_regular_file(manifest_path)) {
            tc_log_error("termin_android_player: runtime manifest not found at '%s'", manifest_path.c_str());
            return false;
        }

        destroy_player_session_locked();
        register_android_scene_extensions_locked();

        g_state.player_engine = std::make_unique<termin::EngineCore>();
        g_state.player_engine->rendering_manager.render_engine()->set_graphics_host(*g_state.graphics_host);

        tgfx::set_builtin_shader_root(nullptr);
        termin::runtime::RuntimePackageLoader loader;
        termin::runtime::RuntimePackageLoadOptions load_options;
        load_options.scene_extensions = termin::default_scene_extension_ids();
        g_state.player_package = loader.load(g_state.asset_root, load_options);
        if (!g_state.player_package.ok || !g_state.player_package.scene.valid()) {
            tc_log_error("termin_android_player: runtime package load failed: %s",
                         g_state.player_package.message.c_str());
            destroy_player_session_locked();
            return false;
        }

        const std::string artifact_root = g_state.shader_artifact_root_explicit
                                              ? g_state.shader_artifact_root
                                              : g_state.player_package.shader_runtime.artifact_root;
        const std::string cache_root = g_state.app_data_dir.empty()
                                           ? g_state.player_package.shader_runtime.cache_root
                                           : (std::filesystem::path(g_state.app_data_dir) / "shader-cache").string();
        tgfx::set_builtin_shader_root(g_state.player_package.shader_runtime.builtin_shader_root.c_str());
        g_state.player_engine->rendering_manager.render_engine()->configure_shader_artifacts(
            artifact_root,
            cache_root,
            g_state.player_package.shader_runtime.compiler_path,
            g_state.player_package.shader_runtime.dev_compile_enabled);

        termin::SceneManager& scene_manager = g_state.player_engine->scene_manager;
        for (const termin::runtime::RuntimePackageScene& packaged_scene : g_state.player_package.scenes) {
            const termin::SceneKey key{packaged_scene.identity, termin::SceneRole::Runtime};
            if (!scene_manager.register_scene(key, packaged_scene.scene.handle())) {
                tc_log_error("termin_android_player: failed to register packaged scene '%s'",
                             packaged_scene.identity.c_str());
                destroy_player_session_locked();
                return false;
            }
            scene_manager.set_scene_path(key, packaged_scene.scene.source_path());
            scene_manager.set_mode(key, TC_SCENE_MODE_INACTIVE);
            g_state.registered_scene_keys.push_back(key);
        }

        const std::string& entry_scene_name = g_state.player_package.entry_scene_identity;
        const termin::SceneKey entry_scene_key{entry_scene_name, termin::SceneRole::Runtime};
        if (!scene_manager.has_scene(entry_scene_key)) {
            tc_log_error("termin_android_player: entry scene '%s' was not registered", entry_scene_name.c_str());
            destroy_player_session_locked();
            return false;
        }
        scene_manager.set_mode(entry_scene_key, TC_SCENE_MODE_PLAY);

        termin::RenderingManager& manager = g_state.player_engine->rendering_manager;
        manager.set_display_factory([](const std::string& name) { return create_player_display_locked(name); });

        g_state.player_scene = g_state.player_package.scene;
        g_state.player_viewports = manager.attach_scene_full(g_state.player_scene.handle());
        if (g_state.player_viewports.empty()) {
            tc_log_error("termin_android_player: entry scene render_mount created no viewports");
            destroy_player_session_locked();
            return false;
        }

        g_state.presentation_display = manager.get_display_by_name("Main");
        if (!tc_display_handle_valid(g_state.presentation_display)) {
            tc_log_error("termin_android_player: entry scene render_mount has no 'Main' display");
            destroy_player_session_locked();
            return false;
        }

        setup_player_input_locked();
        if (g_state.remote_framegraph) {
            g_state.remote_framegraph_debugger = std::make_unique<termin::FrameGraphDebugger>(manager);
            if (!g_state.remote_framegraph->attach_debugger(*g_state.remote_framegraph_debugger)) {
                tc_log_error("termin_android_player: failed to attach remote framegraph debugger");
                destroy_player_session_locked();
                return false;
            }
        }
        scene_manager.request_render();
        android_log_info("player: attached runtime package entities=%zu viewports=%zu targets=%zu",
                         g_state.player_scene.entity_count(),
                         g_state.player_viewports.size(),
                         manager.managed_render_targets().size());
        tc_log_info("termin_android_player: attached scene '%s' through RenderingManager", entry_scene_name.c_str());
        return true;
    }

    struct AndroidFrameTiming {
        termin::EngineHostFrameCadence cadence;
        double delta_seconds = 0.0;
    };

    AndroidFrameTiming observe_frame_timing_locked(int64_t frame_time_nanos) {
        AndroidFrameTiming timing;
        timing.cadence.start_time_ms = static_cast<double>(frame_time_nanos) / 1'000'000.0;
        if (g_state.last_frame_time_nanos == 0) {
            g_state.last_frame_time_nanos = frame_time_nanos;
            return timing;
        }
        const int64_t elapsed = frame_time_nanos - g_state.last_frame_time_nanos;
        g_state.last_frame_time_nanos = frame_time_nanos;
        if (elapsed <= 0) {
            throw std::runtime_error("non-monotonic Choreographer frame timestamp");
        }
        timing.cadence.interval_ms = static_cast<double>(elapsed) / 1'000'000.0;
        timing.delta_seconds = static_cast<double>(elapsed) / 1'000'000'000.0;
        return timing;
    }

    void pump_remote_profiler_locked() {
        if (!g_state.remote_profiler) {
            return;
        }
        const auto started = std::chrono::steady_clock::now();
        g_state.remote_profiler->pump_frame_thread();
        const auto elapsed = std::chrono::steady_clock::now() - started;
        g_state.remote_profiler_pump_ns +=
            static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count());
        ++g_state.remote_profiler_pump_calls;
    }

    void pump_remote_framegraph_locked() {
        if (!g_state.remote_framegraph) {
            return;
        }
        const auto started = std::chrono::steady_clock::now();
        g_state.remote_framegraph->pump_render_thread();
        const auto elapsed = std::chrono::steady_clock::now() - started;
        g_state.remote_framegraph_pump_ns +=
            static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(elapsed).count());
        ++g_state.remote_framegraph_pump_calls;
    }

    int render_player_frame_locked(int64_t frame_time_nanos) {
        if (frame_time_nanos <= 0) {
            tc_log_error("termin_android_player: frame timestamp must be positive");
            return 0;
        }
        // Apply controls and export the preceding completed host frame before
        // opening this frame. This keeps socket work off the render thread and
        // makes capture state effective for the complete new frame.
        pump_remote_profiler_locked();
        pump_remote_framegraph_locked();
        if (!g_state.render_device && !create_renderer_locked()) {
            return 0;
        }
        if (!ensure_player_session_locked()) {
            return 0;
        }

        try {
            const AndroidFrameTiming timing = observe_frame_timing_locked(frame_time_nanos);
            termin::EngineHostFrameScope frame_scope(timing.cadence);

            auto* swapchain = g_state.render_device->swapchain();
            const uint32_t surface_width = static_cast<uint32_t>(g_state.surface_width);
            const uint32_t surface_height = static_cast<uint32_t>(g_state.surface_height);
            if (swapchain->width() != surface_width || swapchain->height() != surface_height) {
                android_log_info("renderer: retry stale surface extent swapchain=%ux%u surface=%ux%u",
                                 swapchain->width(),
                                 swapchain->height(),
                                 surface_width,
                                 surface_height);
                if (!resize_renderer_locked(surface_width, surface_height)) {
                    return 0;
                }
                swapchain = g_state.render_device->swapchain();
                if (swapchain->width() != surface_width || swapchain->height() != surface_height) {
                    // SurfaceHolder can publish its new dimensions just before Vulkan
                    // surface capabilities catch up. Do not render a mismatched
                    // document/display pair; retry on the next Choreographer frame.
                    return 1;
                }
            }
            if (!g_state.has_presentation_metrics) {
                tc_log_error("termin_android_player: platform presentation metrics were not "
                             "published before rendering");
                return 0;
            }
            (void)apply_player_presentation_metrics_locked();

            dispatch_pointer_events_locked();
            const bool rendered = g_state.player_engine->tick_and_render(timing.delta_seconds);
            if (!rendered) {
                return 1;
            }

            termin::TcDisplay display(g_state.presentation_display);
            uint32_t output_texture_id = 0;
            if (!display.validate_output(reinterpret_cast<uintptr_t>(g_state.render_device), &output_texture_id)) {
                tc_log_error("termin_android_player: RenderingManager presentation output is invalid");
                return 0;
            }

            const bool recreate =
                g_state.render_device->swapchain()->compose_and_present(tgfx::TextureHandle{output_texture_id});
            ++g_state.player_frame;
            if (recreate || g_state.player_frame == 1 || g_state.player_frame % 60 == 0) {
                android_log_info(
                    "player: rendered topology frame=%u recreate=%d", g_state.player_frame, recreate ? 1 : 0);
            }
            if (g_state.profiler_enabled && (g_state.player_frame <= 2 || g_state.player_frame % 60 == 0)) {
                // The current scope is still open, so this reports the most
                // recently completed frame. On player frame 2 that is the first
                // frame after a lifecycle reset and its interval must be zero.
                const int history_count = tc_profiler_history_count();
                const tc_frame_profile* completed =
                    history_count > 0 ? tc_profiler_history_at(history_count - 1) : nullptr;
                android_log_info("profiler: completed=%d latest_frame=%d sections=%d interval_ms=%.3f active_ms=%.3f",
                                 history_count,
                                 completed ? completed->frame_number : -1,
                                 completed ? completed->section_count : 0,
                                 completed ? completed->interval_ms : 0.0,
                                 completed ? completed->active_ms : 0.0);
            }
            if (g_state.remote_profiler && (g_state.player_frame <= 2 || g_state.player_frame % 60 == 0)) {
                const auto status = g_state.remote_profiler->status();
                const double average_pump_us = g_state.remote_profiler_pump_calls == 0
                                                   ? 0.0
                                                   : static_cast<double>(g_state.remote_profiler_pump_ns) /
                                                         static_cast<double>(g_state.remote_profiler_pump_calls) /
                                                         1000.0;
                double transmit_kib_per_second = 0.0;
                if (g_state.remote_profiler_last_log_time_nanos > 0 &&
                    frame_time_nanos > g_state.remote_profiler_last_log_time_nanos) {
                    const double elapsed_seconds =
                        static_cast<double>(frame_time_nanos - g_state.remote_profiler_last_log_time_nanos) / 1.0e9;
                    transmit_kib_per_second =
                        static_cast<double>(status.transmitted_bytes - g_state.remote_profiler_last_log_bytes) /
                        1024.0 / elapsed_seconds;
                }
                android_log_info("profiler_remote: connected=%d capture=%d sections=%d "
                                 "frames=%llu bytes=%llu tx_kib_s=%.3f drops=%llu "
                                 "avg_pump_us=%.3f",
                                 status.client_connected ? 1 : 0,
                                 status.capturing ? 1 : 0,
                                 status.profiling_sections ? 1 : 0,
                                 static_cast<unsigned long long>(status.completed_frames),
                                 static_cast<unsigned long long>(status.transmitted_bytes),
                                 transmit_kib_per_second,
                                 static_cast<unsigned long long>(status.dropped_frames),
                                 average_pump_us);
                g_state.remote_profiler_last_log_bytes = status.transmitted_bytes;
                g_state.remote_profiler_last_log_time_nanos = frame_time_nanos;
            }
            if (g_state.remote_framegraph && (g_state.player_frame <= 2 || g_state.player_frame % 60 == 0)) {
                const auto status = g_state.remote_framegraph->status();
                const double average_pump_us = g_state.remote_framegraph_pump_calls == 0
                                                   ? 0.0
                                                   : static_cast<double>(g_state.remote_framegraph_pump_ns) /
                                                         static_cast<double>(g_state.remote_framegraph_pump_calls) /
                                                         1000.0;
                double transmit_kib_per_second = 0.0;
                if (g_state.remote_framegraph_last_log_time_nanos > 0 &&
                    frame_time_nanos > g_state.remote_framegraph_last_log_time_nanos) {
                    const double elapsed_seconds =
                        static_cast<double>(frame_time_nanos - g_state.remote_framegraph_last_log_time_nanos) / 1.0e9;
                    transmit_kib_per_second =
                        static_cast<double>(status.transmitted_bytes - g_state.remote_framegraph_last_log_bytes) /
                        1024.0 / elapsed_seconds;
                }
                android_log_info("framegraph_remote: connected=%d attached=%d revision=%llu "
                                 "captures=%llu preview=%llu burst=%llu bytes=%llu "
                                 "tx_kib_s=%.3f drops=%llu avg_pump_us=%.3f",
                                 status.client_connected ? 1 : 0,
                                 status.debugger_attached ? 1 : 0,
                                 static_cast<unsigned long long>(status.graph_revision),
                                 static_cast<unsigned long long>(status.completed_captures),
                                 static_cast<unsigned long long>(status.preview_captures),
                                 static_cast<unsigned long long>(status.burst_captures),
                                 static_cast<unsigned long long>(status.transmitted_bytes),
                                 transmit_kib_per_second,
                                 static_cast<unsigned long long>(status.dropped_captures),
                                 average_pump_us);
                g_state.remote_framegraph_last_log_bytes = status.transmitted_bytes;
                g_state.remote_framegraph_last_log_time_nanos = frame_time_nanos;
            }
            if (recreate && !resize_renderer_locked(static_cast<uint32_t>(g_state.surface_width),
                                                    static_cast<uint32_t>(g_state.surface_height))) {
                return 0;
            }
            return 1;
        } catch (const std::exception& error) {
            android_log_error("player: render failed: %s", error.what());
            tc_log_error("termin_android_player: render failed: %s", error.what());
            destroy_renderer_locked();
            return 0;
        }
    }

    void destroy_renderer_locked() {
        if (g_state.render_device) {
            android_log_info("renderer: destroy");
            try {
                g_state.render_device->wait_idle();
            } catch (const std::exception& error) {
                android_log_error("renderer: wait_idle failed: %s", error.what());
                tc_log_error("termin_android_renderer: wait_idle failed: %s", error.what());
            }
        }

        destroy_player_session_locked();
        g_state.graphics_host.reset();
        g_state.render_device = nullptr;
        g_state.swapchain_width = 0;
        g_state.swapchain_height = 0;
    }

    bool resize_renderer_locked(uint32_t width, uint32_t height) {
        if (!g_state.render_device || !g_state.render_device->swapchain()) {
            return false;
        }
        if (width == 0 || height == 0) {
            tc_log_error("termin_android_renderer: invalid resize %ux%u", width, height);
            destroy_renderer_locked();
            return false;
        }

        try {
            g_state.render_device->swapchain()->recreate(width, height);
            g_state.swapchain_width = g_state.render_device->swapchain()->width();
            g_state.swapchain_height = g_state.render_device->swapchain()->height();

            for (auto& [name, display] : g_state.player_displays) {
                if (!display.resize(static_cast<int>(g_state.swapchain_width),
                                    static_cast<int>(g_state.swapchain_height))) {
                    throw std::runtime_error("failed to resize offscreen display '" + name + "'");
                }
            }

            android_log_info("renderer: swapchain resized %ux%u images=%u",
                             g_state.swapchain_width,
                             g_state.swapchain_height,
                             g_state.render_device->swapchain()->image_count());
            return true;
        } catch (const std::exception& error) {
            android_log_error("renderer: swapchain resize failed: %s", error.what());
            tc_log_error("termin_android_renderer: swapchain resize failed: %s", error.what());
            destroy_renderer_locked();
            return false;
        }
    }

    bool create_renderer_locked() {
        if (g_state.renderer_create_failed) {
            android_log_info("renderer: create skipped after earlier failure on this surface");
            return false;
        }
        if (!g_state.window) {
            tc_log_error("termin_android_renderer: cannot create without ANativeWindow");
            return false;
        }
        if (g_state.surface_width <= 0 || g_state.surface_height <= 0) {
            tc_log_error("termin_android_renderer: invalid surface size %dx%d",
                         static_cast<int>(g_state.surface_width),
                         static_cast<int>(g_state.surface_height));
            return false;
        }

        destroy_renderer_locked();

        try {
            android_log_info("renderer: create Vulkan surface=%p size=%dx%d",
                             static_cast<void*>(g_state.window),
                             static_cast<int>(g_state.surface_width),
                             static_cast<int>(g_state.surface_height));
            tgfx::VulkanDeviceCreateInfo info{};
            info.enable_validation = false;
            info.instance_extensions = {
                VK_KHR_SURFACE_EXTENSION_NAME,
                VK_KHR_ANDROID_SURFACE_EXTENSION_NAME,
            };
            info.swapchain_width = static_cast<uint32_t>(g_state.surface_width);
            info.swapchain_height = static_cast<uint32_t>(g_state.surface_height);
            ANativeWindow* window = g_state.window;
            info.surface_factory = [window](VkInstance instance) -> VkSurfaceKHR {
                VkAndroidSurfaceCreateInfoKHR create_info{};
                create_info.sType = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
                create_info.window = window;
                VkSurfaceKHR surface = VK_NULL_HANDLE;
                const VkResult result = vkCreateAndroidSurfaceKHR(instance, &create_info, nullptr, &surface);
                if (result != VK_SUCCESS) {
                    tc_log_error("termin_android_renderer: vkCreateAndroidSurfaceKHR failed result=%d",
                                 static_cast<int>(result));
                    return VK_NULL_HANDLE;
                }
                return surface;
            };

            auto render_device = std::make_unique<tgfx::VulkanRenderDevice>(info);
            render_device->configure_shader_artifacts(termin::ShaderArtifactResolver(
                g_state.shader_artifact_root,
                g_state.app_data_dir.empty() ? std::string()
                                             : (std::filesystem::path(g_state.app_data_dir) / "shader-cache").string(),
                "",
                false));
            g_state.render_device = render_device.get();
            g_state.graphics_host = tgfx::GraphicsHost::adopt_application_device(std::move(render_device));
            g_state.swapchain_width = g_state.render_device->swapchain()->width();
            g_state.swapchain_height = g_state.render_device->swapchain()->height();

            android_log_info("renderer: Vulkan swapchain=%ux%u images=%u",
                             g_state.swapchain_width,
                             g_state.swapchain_height,
                             g_state.render_device->swapchain()->image_count());
            return true;
        } catch (const std::exception& error) {
            android_log_error("renderer: create failed: %s", error.what());
            tc_log_error("termin_android_renderer: create failed: %s", error.what());
            destroy_renderer_locked();
            g_state.renderer_create_failed = true;
            return false;
        }
    }

#endif

    void release_window_locked() {
#ifdef __ANDROID__
        destroy_renderer_locked();
        if (g_state.window) {
            ANativeWindow_release(g_state.window);
        }
#endif
        g_state.window = nullptr;
        g_state.surface_width = 0;
        g_state.surface_height = 0;
#ifdef __ANDROID__
        g_state.pointer_events.clear();
#endif
#ifdef __ANDROID__
        g_state.renderer_create_failed = false;
#endif
    }

    void rollback_initialize_locked() {
        if (g_state.remote_framegraph) {
            g_state.remote_framegraph->stop();
            g_state.remote_framegraph.reset();
        }
        g_state.remote_framegraph_debugger.reset();
        g_state.remote_framegraph_pump_calls = 0;
        g_state.remote_framegraph_pump_ns = 0;
        g_state.remote_framegraph_last_log_bytes = 0;
        g_state.remote_framegraph_last_log_time_nanos = 0;
        if (g_state.remote_profiler) {
            g_state.remote_profiler->stop();
            g_state.remote_profiler.reset();
        }
        g_state.remote_profiler_pump_calls = 0;
        g_state.remote_profiler_pump_ns = 0;
        g_state.remote_profiler_last_log_bytes = 0;
        g_state.remote_profiler_last_log_time_nanos = 0;
        g_state.app_data_dir.clear();
        g_state.asset_root.clear();
        g_state.shader_artifact_root.clear();
        g_state.shader_artifact_root_explicit = false;
        g_state.native_lib_dir.clear();
        g_state.profiler_enabled = false;
        tc_profiler_set_enabled(false);
        tgfx::set_builtin_shader_root(nullptr);
        termin::bootstrap::shutdown_runtime();
    }

} // namespace

extern "C" int termin_android_initialize(const termin_android_config* config) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
#ifdef __ANDROID__
    tc_log_set_callback(tc_log_android_callback);
    tc_log_set_level(TC_LOG_DEBUG);
#endif
    if (!config) {
        android_log_error("initialize: config is NULL");
        tc_log_error("termin_android_initialize: config is NULL");
        return 0;
    }
    if (g_state.initialized) {
        android_log_error("initialize: runtime is already initialized");
        tc_log_error("termin_android_initialize: already initialized");
        return 0;
    }

    termin::bootstrap::bootstrap_runtime();

    g_state.app_data_dir = config->app_data_dir ? config->app_data_dir : "";
    g_state.asset_root = config->asset_root ? config->asset_root : "";
    g_state.native_lib_dir = config->native_lib_dir ? config->native_lib_dir : "";
    g_state.profiler_enabled = config->enable_profiler != 0;
    tc_profiler_set_enabled(g_state.profiler_enabled);
    g_state.shader_artifact_root = infer_shader_artifact_root(g_state.asset_root);
    g_state.shader_artifact_root_explicit = false;
#ifdef __ANDROID__
    if (!configure_ui_font_locked()) {
        rollback_initialize_locked();
        return 0;
    }
#endif

    if (config->enable_remote_profiler != 0) {
        if (config->remote_profiler_port == 0 || !config->remote_profiler_token ||
            config->remote_profiler_token[0] == '\0') {
            android_log_error("initialize: remote profiler requires a port and token");
            tc_log_error("termin_android_initialize: invalid remote profiler config");
            rollback_initialize_locked();
            return 0;
        }
        termin::profiler_remote::TargetServiceConfig target;
        target.port = config->remote_profiler_port;
        target.authentication_token = config->remote_profiler_token;
        target.platform = "Android";
#ifdef __ANDROID__
        target.abi = TERMIN_ANDROID_ABI;
        target.process_id = static_cast<uint32_t>(getpid());
#endif
        target.build_type = "Development";
        try {
            g_state.remote_profiler =
                std::make_unique<termin::profiler_remote::RemoteProfilerTarget>(std::move(target));
            if (!g_state.remote_profiler->start()) {
                g_state.remote_profiler.reset();
                throw std::runtime_error("listener start failed");
            }
        } catch (const std::exception& error) {
            android_log_error("initialize: remote profiler failed: %s", error.what());
            tc_log_error("termin_android_initialize: remote profiler failed: %s", error.what());
            rollback_initialize_locked();
            return 0;
        }
        android_log_info("profiler_remote: listening on device loopback port=%u",
                         static_cast<unsigned>(config->remote_profiler_port));
    }
    if (config->enable_remote_framegraph != 0) {
        if (config->remote_framegraph_port == 0 || !config->remote_framegraph_token ||
            config->remote_framegraph_token[0] == '\0') {
            android_log_error("initialize: remote framegraph requires a port and token");
            tc_log_error("termin_android_initialize: invalid remote framegraph config");
            rollback_initialize_locked();
            return 0;
        }
        if (config->enable_remote_profiler != 0 && config->remote_profiler_port == config->remote_framegraph_port) {
            android_log_error("initialize: remote profiler and framegraph ports must differ");
            tc_log_error("termin_android_initialize: diagnostics ports conflict");
            rollback_initialize_locked();
            return 0;
        }
        termin::framegraph_remote_target::TargetServiceConfig target;
        target.port = config->remote_framegraph_port;
        target.authentication_token = config->remote_framegraph_token;
        target.platform = "Android";
#ifdef __ANDROID__
        target.abi = TERMIN_ANDROID_ABI;
        target.process_id = static_cast<uint32_t>(getpid());
#endif
        target.build_type = "Development";
        try {
            g_state.remote_framegraph =
                std::make_unique<termin::framegraph_remote_target::RemoteFrameGraphTarget>(std::move(target));
            if (!g_state.remote_framegraph->start()) {
                g_state.remote_framegraph.reset();
                throw std::runtime_error("listener start failed");
            }
        } catch (const std::exception& error) {
            android_log_error("initialize: remote framegraph failed: %s", error.what());
            tc_log_error("termin_android_initialize: remote framegraph failed: %s", error.what());
            rollback_initialize_locked();
            return 0;
        }
        android_log_info("framegraph_remote: listening on device loopback port=%u",
                         static_cast<unsigned>(config->remote_framegraph_port));
    }
    g_state.initialized = true;

    android_log_info(
        "initialize: app_data_dir='%s', asset_root='%s', shader_artifact_root='%s', native_lib_dir='%s', profiler=%d",
        g_state.app_data_dir.c_str(),
        g_state.asset_root.c_str(),
        g_state.shader_artifact_root.c_str(),
        g_state.native_lib_dir.c_str(),
        g_state.profiler_enabled ? 1 : 0);
    tc_log_info(
        "termin_android_initialize: app_data_dir='%s', asset_root='%s', shader_artifact_root='%s', native_lib_dir='%s'",
        g_state.app_data_dir.c_str(),
        g_state.asset_root.c_str(),
        g_state.shader_artifact_root.c_str(),
        g_state.native_lib_dir.c_str());
    return 1;
}

extern "C" void termin_android_shutdown(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    if (g_state.remote_profiler) {
        g_state.remote_profiler->stop();
        g_state.remote_profiler.reset();
    }
    g_state.remote_profiler_pump_calls = 0;
    g_state.remote_profiler_pump_ns = 0;
    g_state.remote_profiler_last_log_bytes = 0;
    g_state.remote_profiler_last_log_time_nanos = 0;
    release_window_locked();
    if (g_state.remote_framegraph) {
        g_state.remote_framegraph->stop();
        g_state.remote_framegraph.reset();
    }
    g_state.remote_framegraph_debugger.reset();
    g_state.remote_framegraph_pump_calls = 0;
    g_state.remote_framegraph_pump_ns = 0;
    g_state.remote_framegraph_last_log_bytes = 0;
    g_state.remote_framegraph_last_log_time_nanos = 0;
    g_state.app_data_dir.clear();
    g_state.asset_root.clear();
    g_state.shader_artifact_root.clear();
    g_state.shader_artifact_root_explicit = false;
    g_state.native_lib_dir.clear();
    g_state.presentation_metrics = {};
    g_state.has_presentation_metrics = false;
    tc_profiler_set_enabled(false);
    tc_profiler_clear_history();
    g_state.profiler_enabled = false;
    tgfx::set_builtin_shader_root(nullptr);
    g_state.initialized = false;
#ifdef __ANDROID__
    if (g_state.scene_extensions_registered) {
        termin_collision_runtime_shutdown();
        g_state.scene_extensions_registered = false;
    }
#endif
    termin::bootstrap::shutdown_runtime();
    android_log_info("shutdown");
    tc_log_info("termin_android_shutdown");
#ifdef __ANDROID__
    tc_log_set_callback(nullptr);
#endif
}

extern "C" void termin_android_set_shader_artifact_root(const char* root) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    g_state.shader_artifact_root = root ? root : "";
    g_state.shader_artifact_root_explicit = true;
#ifdef __ANDROID__
    if (g_state.player_engine) {
        const std::string cache_root = g_state.app_data_dir.empty()
                                           ? std::string()
                                           : (std::filesystem::path(g_state.app_data_dir) / "shader-cache").string();
        g_state.player_engine->rendering_manager.render_engine()->configure_shader_artifacts(
            g_state.shader_artifact_root, cache_root, "", false);
    }
#endif
    tc_log_info("termin_android_set_shader_artifact_root: '%s'", g_state.shader_artifact_root.c_str());
}

extern "C" const char* termin_android_get_shader_artifact_root(void) {
    return g_state.shader_artifact_root.c_str();
}

extern "C" void termin_android_on_surface_created(ANativeWindow* window) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    if (!window) {
        android_log_error("surface_created: window is NULL");
        tc_log_error("termin_android_on_surface_created: window is NULL");
        return;
    }

#ifdef __ANDROID__
    ANativeWindow_acquire(window);
    g_state.surface_width = ANativeWindow_getWidth(window);
    g_state.surface_height = ANativeWindow_getHeight(window);
#endif
    g_state.window = window;
#ifdef __ANDROID__
    g_state.renderer_create_failed = false;
#endif
    android_log_info("surface_created: window=%p size=%dx%d; waiting for surfaceChanged before render",
                     static_cast<void*>(window),
                     static_cast<int>(g_state.surface_width),
                     static_cast<int>(g_state.surface_height));
    tc_log_info("termin_android_on_surface_created: window=%p size=%dx%d",
                static_cast<void*>(window),
                static_cast<int>(g_state.surface_width),
                static_cast<int>(g_state.surface_height));
}

extern "C" void termin_android_on_surface_changed(int32_t width, int32_t height) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    const bool size_changed = g_state.surface_width != width || g_state.surface_height != height;
    g_state.surface_width = width;
    g_state.surface_height = height;
    android_log_info("surface_changed: size=%dx%d size_changed=%d",
                     static_cast<int>(width),
                     static_cast<int>(height),
                     size_changed ? 1 : 0);
    tc_log_info("termin_android_on_surface_changed: size=%dx%d", static_cast<int>(width), static_cast<int>(height));
#ifdef __ANDROID__
    if (size_changed && g_state.render_device) {
        if (width <= 0 || height <= 0) {
            tc_log_error("termin_android_on_surface_changed: invalid resize %dx%d",
                         static_cast<int>(width),
                         static_cast<int>(height));
            destroy_renderer_locked();
            return;
        }
        resize_renderer_locked(static_cast<uint32_t>(width), static_cast<uint32_t>(height));
    }
    (void)apply_player_presentation_metrics_locked();
#endif
}

extern "C" void termin_android_on_presentation_metrics_changed(const termin_android_presentation_metrics* metrics) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    if (!metrics) {
        android_log_error("presentation_metrics_changed: metrics is NULL");
        tc_log_error("termin_android_on_presentation_metrics_changed: metrics is NULL");
        return;
    }
    const bool valid = std::isfinite(metrics->density_scale) && metrics->density_scale > 0.0f &&
                       std::isfinite(metrics->font_scale) && metrics->font_scale > 0.0f &&
                       std::isfinite(metrics->safe_inset_left) && metrics->safe_inset_left >= 0.0f &&
                       std::isfinite(metrics->safe_inset_top) && metrics->safe_inset_top >= 0.0f &&
                       std::isfinite(metrics->safe_inset_right) && metrics->safe_inset_right >= 0.0f &&
                       std::isfinite(metrics->safe_inset_bottom) && metrics->safe_inset_bottom >= 0.0f;
    if (!valid) {
        android_log_error("presentation_metrics_changed: invalid density=%.3f font=%.3f "
                          "insets=[%.1f,%.1f,%.1f,%.1f]",
                          static_cast<double>(metrics->density_scale),
                          static_cast<double>(metrics->font_scale),
                          static_cast<double>(metrics->safe_inset_left),
                          static_cast<double>(metrics->safe_inset_top),
                          static_cast<double>(metrics->safe_inset_right),
                          static_cast<double>(metrics->safe_inset_bottom));
        tc_log_error("termin_android_on_presentation_metrics_changed: invalid "
                     "platform metrics");
        return;
    }

    const bool changed = !g_state.has_presentation_metrics ||
                         g_state.presentation_metrics.density_scale != metrics->density_scale ||
                         g_state.presentation_metrics.font_scale != metrics->font_scale ||
                         g_state.presentation_metrics.safe_inset_left != metrics->safe_inset_left ||
                         g_state.presentation_metrics.safe_inset_top != metrics->safe_inset_top ||
                         g_state.presentation_metrics.safe_inset_right != metrics->safe_inset_right ||
                         g_state.presentation_metrics.safe_inset_bottom != metrics->safe_inset_bottom;
    g_state.presentation_metrics = *metrics;
    g_state.has_presentation_metrics = true;
    android_log_info("presentation_metrics_changed: density=%.3f font=%.3f "
                     "insets=[%.1f,%.1f,%.1f,%.1f] changed=%d",
                     static_cast<double>(metrics->density_scale),
                     static_cast<double>(metrics->font_scale),
                     static_cast<double>(metrics->safe_inset_left),
                     static_cast<double>(metrics->safe_inset_top),
                     static_cast<double>(metrics->safe_inset_right),
                     static_cast<double>(metrics->safe_inset_bottom),
                     changed ? 1 : 0);
    tc_log_info("termin_android_on_presentation_metrics_changed: density=%.3f "
                "font=%.3f insets=[%.1f,%.1f,%.1f,%.1f] changed=%d",
                static_cast<double>(metrics->density_scale),
                static_cast<double>(metrics->font_scale),
                static_cast<double>(metrics->safe_inset_left),
                static_cast<double>(metrics->safe_inset_top),
                static_cast<double>(metrics->safe_inset_right),
                static_cast<double>(metrics->safe_inset_bottom),
                changed ? 1 : 0);
#ifdef __ANDROID__
    (void)apply_player_presentation_metrics_locked();
#endif
}

extern "C" void termin_android_on_surface_destroyed(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    android_log_info("surface_destroyed");
    tc_log_info("termin_android_on_surface_destroyed");
}

extern "C" void termin_android_on_pause(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
#ifdef __ANDROID__
    destroy_renderer_locked();
#endif
    android_log_info("pause: render runtime detached");
    tc_log_info("termin_android_on_pause");
}

extern "C" void termin_android_on_resume(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
#ifdef __ANDROID__
    g_state.renderer_create_failed = false;
#endif
    android_log_info("resume: render runtime will attach on next frame");
    tc_log_info("termin_android_on_resume");
}

extern "C" void
termin_android_on_pointer(uint64_t pointer_id, int32_t device, int32_t phase, float x, float y, float pressure) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
#ifdef __ANDROID__
    if (device < TC_POINTER_DEVICE_MOUSE || device > TC_POINTER_DEVICE_PEN) {
        tc_log_error("termin_android_on_pointer: invalid device %d", (int)device);
        return;
    }
    if (phase < TC_POINTER_DOWN || phase > TC_POINTER_CANCEL) {
        tc_log_error("termin_android_on_pointer: invalid phase %d", (int)phase);
        return;
    }
    constexpr size_t kMaxQueuedPointerEvents = 4096;
    if (g_state.pointer_events.size() >= kMaxQueuedPointerEvents) {
        tc_log_error("termin_android_on_pointer: input queue overflow; dropping pointer id=%llu",
                     (unsigned long long)pointer_id);
        return;
    }
    g_state.pointer_events.push_back({
        pointer_id,
        (int)device,
        (int)phase,
        (double)x,
        (double)y,
        pressure,
    });
#else
    (void)pointer_id;
    (void)device;
    (void)phase;
    (void)x;
    (void)y;
    (void)pressure;
    tc_log_error("termin_android_on_pointer: only supported on Android");
#endif
}

extern "C" int termin_android_render_frame(int64_t frame_time_nanos) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
#ifdef __ANDROID__
    return render_player_frame_locked(frame_time_nanos);
#else
    (void)frame_time_nanos;
    tc_log_error("termin_android_render_frame: only supported on Android");
    return 0;
#endif
}

extern "C" int termin_android_smoke_render(int64_t frame_time_nanos) {
    return termin_android_render_frame(frame_time_nanos);
}

extern "C" ANativeWindow* termin_android_native_window(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.window;
}

extern "C" int32_t termin_android_surface_width(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.surface_width;
}

extern "C" int32_t termin_android_surface_height(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.surface_height;
}
