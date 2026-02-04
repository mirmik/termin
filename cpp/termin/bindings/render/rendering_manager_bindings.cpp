// rendering_manager_bindings.cpp - Python bindings for RenderingManager
#include "common.hpp"
#include "termin/render/rendering_manager.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/viewport_render_state.hpp"
#include "termin/render/tc_display_handle.hpp"
#include "termin/viewport/tc_viewport_handle.hpp"
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/function.h>

extern "C" {
#include "core/tc_scene.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"
}

namespace termin {

// Helper to extract tc_scene_handle from Python Scene object (Scene inherits TcScene)
static tc_scene_handle get_scene_handle(nb::object scene_py) {
    tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
    if (!scene_py.is_none() && nb::hasattr(scene_py, "scene_handle")) {
        auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene_py.attr("scene_handle")());
        scene.index = std::get<0>(h);
        scene.generation = std::get<1>(h);
    }
    return scene;
}

// Helper to extract tc_display* from Python Display object
static tc_display* get_display_ptr(nb::object display_py) {
    if (display_py.is_none()) return nullptr;
    // Display.tc_display_ptr is a property returning int (pointer as int)
    if (nb::hasattr(display_py, "tc_display_ptr")) {
        return reinterpret_cast<tc_display*>(
            nb::cast<uintptr_t>(display_py.attr("tc_display_ptr"))
        );
    }
    return nullptr;
}

// Helper to convert viewport handle tuple
static tc_viewport_handle tuple_to_viewport_handle(const std::tuple<uint32_t, uint32_t>& t) {
    tc_viewport_handle h;
    h.index = std::get<0>(t);
    h.generation = std::get<1>(t);
    return h;
}

static std::tuple<uint32_t, uint32_t> viewport_handle_to_tuple(tc_viewport_handle h) {
    return {h.index, h.generation};
}

// Helper to extract viewport handle from Python Viewport object (TcViewport)
static tc_viewport_handle get_viewport_handle(nb::object viewport_py) {
    tc_viewport_handle h = TC_VIEWPORT_HANDLE_INVALID;
    if (viewport_py.is_none()) return h;
    // Viewport.handle is a uint64 property that packs (index << 32 | generation)
    if (nb::hasattr(viewport_py, "handle")) {
        uint64_t packed = nb::cast<uint64_t>(viewport_py.attr("handle"));
        h.index = static_cast<uint32_t>(packed >> 32);
        h.generation = static_cast<uint32_t>(packed & 0xFFFFFFFF);
    }
    return h;
}

void bind_rendering_manager(nb::module_& m) {
    // ViewportRenderState - per-viewport GPU resource state
    nb::class_<ViewportRenderState>(m, "ViewportRenderState")
        .def_prop_ro("output_width", [](ViewportRenderState& self) { return self.output_width; })
        .def_prop_ro("output_height", [](ViewportRenderState& self) { return self.output_height; })
        .def("has_output_fbo", &ViewportRenderState::has_output_fbo)
        .def("clear_all", &ViewportRenderState::clear_all)
        .def_prop_ro("output_fbo_id", [](ViewportRenderState& self) -> uint32_t {
            return self.output_fbo ? self.output_fbo->get_fbo_id() : 0;
        })
    ;

    // RenderingManager singleton
    nb::class_<RenderingManager>(m, "RenderingManager")
        .def_static("instance", &RenderingManager::instance, nb::rv_policy::reference)

        // ================================================================
        // Configuration
        // ================================================================

        .def("set_graphics", [](RenderingManager& self, GraphicsBackend* graphics) {
            self.set_graphics(graphics);
        }, nb::arg("graphics").none(),
           "Set graphics backend for rendering")

        .def("set_make_current_callback", [](RenderingManager& self, nb::callable callback) {
            if (callback.is_none()) {
                self.set_make_current_callback(nullptr);
            } else {
                // Store callback preventing GC
                nb::callable stored = callback;
                self.set_make_current_callback([stored]() {
                    nb::gil_scoped_acquire gil;
                    stored();
                });
            }
        }, nb::arg("callback").none(),
           "Set callback to activate GL context before rendering")

        .def("set_display_factory", [](RenderingManager& self, nb::callable factory) {
            if (factory.is_none()) {
                self.set_display_factory(nullptr);
            } else {
                nb::callable stored = factory;
                self.set_display_factory([stored](const std::string& name) -> tc_display* {
                    nb::gil_scoped_acquire gil;
                    nb::object result = stored(name);
                    return get_display_ptr(result);
                });
            }
        }, nb::arg("factory").none(),
           "Set factory for creating displays on demand")

        .def("set_pipeline_factory", [](RenderingManager& self, nb::callable factory) {
            if (factory.is_none()) {
                self.set_pipeline_factory(nullptr);
            } else {
                nb::callable stored = factory;
                self.set_pipeline_factory([stored](const std::string& name) -> RenderPipeline* {
                    nb::gil_scoped_acquire gil;
                    nb::object result = stored(name);
                    if (result.is_none()) return nullptr;
                    return nb::cast<RenderPipeline*>(result);
                });
            }
        }, nb::arg("factory").none(),
           "Set factory for creating pipelines by special name")

        // ================================================================
        // Display Management
        // ================================================================

        .def("add_display", [](RenderingManager& self, TcDisplay& display, nb::object name_py) {
            if (display.ptr()) {
                self.add_display(display.ptr());
                if (!name_py.is_none()) {
                    std::string name = nb::cast<std::string>(name_py);
                    display.set_name(name);
                }
            }
        }, nb::arg("display"), nb::arg("name") = nb::none(),
           "Add display to management")

        .def("remove_display", [](RenderingManager& self, TcDisplay& display) {
            if (display.ptr()) {
                self.remove_display(display.ptr());
            }
        }, nb::arg("display"),
           "Remove display from management")

        .def("get_display_by_name", [](RenderingManager& self, const std::string& name) -> uintptr_t {
            tc_display* display = self.get_display_by_name(name);
            return reinterpret_cast<uintptr_t>(display);
        }, nb::arg("name"),
           "Find display by name, returns pointer as int (0 if not found)")

        .def("get_or_create_display", [](RenderingManager& self, const std::string& name) -> uintptr_t {
            tc_display* display = self.get_or_create_display(name);
            return reinterpret_cast<uintptr_t>(display);
        }, nb::arg("name"),
           "Get existing display or create via factory")

        .def_prop_ro("display_count", [](RenderingManager& self) {
            return self.displays().size();
        }, "Number of managed displays")

        .def_prop_ro("displays", [](RenderingManager& self) -> std::vector<TcDisplay> {
            std::vector<TcDisplay> result;
            for (tc_display* d : self.displays()) {
                // Non-owning wrapper - RenderingManager owns the displays
                result.push_back(TcDisplay::from_ptr(d, false));
            }
            return result;
        }, "List of managed displays")

        .def_prop_ro("display_ptrs", [](RenderingManager& self) -> std::vector<uintptr_t> {
            std::vector<uintptr_t> result;
            for (tc_display* d : self.displays()) {
                result.push_back(reinterpret_cast<uintptr_t>(d));
            }
            return result;
        }, "List of display pointers (as int) - for backwards compatibility")

        .def("get_display_for_viewport", [](RenderingManager& self, nb::object viewport_py) -> nb::object {
            tc_viewport_handle vh = get_viewport_handle(viewport_py);
            if (!tc_viewport_handle_valid(vh)) return nb::none();

            // Search through displays for this viewport
            for (tc_display* display : self.displays()) {
                size_t count = tc_display_get_viewport_count(display);
                for (size_t i = 0; i < count; ++i) {
                    tc_viewport_handle vph = tc_display_get_viewport_at_index(display, i);
                    if (tc_viewport_handle_eq(vph, vh)) {
                        return nb::cast(TcDisplay::from_ptr(display, false));
                    }
                }
            }
            return nb::none();
        }, nb::arg("viewport"),
           "Find display containing this viewport, returns Display or None")

        .def("get_display_name", [](RenderingManager& self, TcDisplay& display) -> std::string {
            return display.name();
        }, nb::arg("display"),
           "Get display name")

        .def("set_display_name", [](RenderingManager& self, TcDisplay& display, const std::string& name) {
            display.set_name(name);
        }, nb::arg("display"), nb::arg("name"),
           "Set display name")

        // ================================================================
        // Scene Mounting
        // ================================================================

        .def("attach_scene_full", [](RenderingManager& self, nb::object scene_py)
                -> std::vector<TcViewport> {
            tc_scene_handle scene = get_scene_handle(scene_py);
            std::vector<tc_viewport_handle> viewports = self.attach_scene_full(scene);
            std::vector<TcViewport> result;
            result.reserve(viewports.size());
            for (tc_viewport_handle h : viewports) {
                result.push_back(TcViewport(h));
            }
            return result;
        }, nb::arg("scene"),
           "Attach scene using viewport_configs, returns list of Viewport objects")

        .def("detach_scene_full", [](RenderingManager& self, nb::object scene_py) {
            tc_scene_handle scene = get_scene_handle(scene_py);
            self.detach_scene_full(scene);
        }, nb::arg("scene"),
           "Detach scene from all displays and cleanup")

        .def("unmount_scene", [](RenderingManager& self, nb::object scene_py, TcDisplay& display) {
            tc_scene_handle scene = get_scene_handle(scene_py);
            if (display.ptr()) {
                self.unmount_scene(scene, display.ptr());
            }
        }, nb::arg("scene"), nb::arg("display"),
           "Unmount scene from display (removes all viewports showing this scene)")

        // ================================================================
        // Scene Pipeline Management
        // ================================================================

        // attach_scene - full version that creates viewports and compiles pipelines
        .def("attach_scene", [](RenderingManager& self, nb::object scene_py)
                -> std::vector<TcViewport> {
            tc_scene_handle scene = get_scene_handle(scene_py);
            std::vector<tc_viewport_handle> viewports = self.attach_scene_full(scene);
            std::vector<TcViewport> result;
            result.reserve(viewports.size());
            for (tc_viewport_handle h : viewports) {
                result.push_back(TcViewport(h));
            }
            return result;
        }, nb::arg("scene"),
           "Attach scene - creates viewports from config and compiles pipelines")

        .def("detach_scene", [](RenderingManager& self, nb::object scene_py) {
            tc_scene_handle scene = get_scene_handle(scene_py);
            self.detach_scene(scene);
        }, nb::arg("scene"),
           "Detach scene pipelines - destroys compiled pipelines and notifies components")

        .def("get_scene_pipeline", [](RenderingManager& self,
                                       nb::object scene_py,
                                       const std::string& name) -> RenderPipeline* {
            tc_scene_handle scene = get_scene_handle(scene_py);
            return self.get_scene_pipeline(scene, name);
        }, nb::arg("scene"), nb::arg("name"), nb::rv_policy::reference)

        .def("get_scene_pipeline", [](RenderingManager& self,
                                       const std::string& name) -> RenderPipeline* {
            return self.get_scene_pipeline(name);
        }, nb::arg("name"), nb::rv_policy::reference)

        .def("clear_scene_pipelines", [](RenderingManager& self, nb::object scene_py) {
            tc_scene_handle scene = get_scene_handle(scene_py);
            self.clear_scene_pipelines(scene);
        }, nb::arg("scene"))

        .def("clear_all_scene_pipelines", &RenderingManager::clear_all_scene_pipelines)

        .def("set_pipeline_targets", &RenderingManager::set_pipeline_targets,
             nb::arg("pipeline_name"), nb::arg("targets"))

        .def("get_pipeline_targets", &RenderingManager::get_pipeline_targets,
             nb::arg("pipeline_name"), nb::rv_policy::reference)

        .def("get_pipeline_names", [](RenderingManager& self, nb::object scene_py) {
            tc_scene_handle scene = get_scene_handle(scene_py);
            return self.get_pipeline_names(scene);
        }, nb::arg("scene"))

        // ================================================================
        // Rendering
        // ================================================================

        .def("render_all", &RenderingManager::render_all,
             nb::arg("present") = true,
             "Render all viewports (offscreen + present)")

        .def("render_all_offscreen", &RenderingManager::render_all_offscreen,
             "Phase 1: Render all viewports to their output FBOs")

        .def("present_all", &RenderingManager::present_all,
             "Phase 2: Blit viewport FBOs to displays")

        .def("present_display", [](RenderingManager& self, TcDisplay& display) {
            if (display.ptr()) {
                self.present_display(display.ptr());
            }
        }, nb::arg("display"),
           "Blit viewport output_fbos to a single display")

        // ================================================================
        // Viewport State
        // ================================================================

        .def("get_viewport_state", [](RenderingManager& self, nb::object viewport_py) -> ViewportRenderState* {
            tc_viewport_handle vh = get_viewport_handle(viewport_py);
            return self.get_viewport_state(vh);
        }, nb::arg("viewport"), nb::rv_policy::reference,
           "Get render state for viewport (returns None if not found)")

        .def("get_or_create_viewport_state", [](RenderingManager& self, nb::object viewport_py) -> ViewportRenderState* {
            tc_viewport_handle vh = get_viewport_handle(viewport_py);
            return self.get_or_create_viewport_state(vh);
        }, nb::arg("viewport"), nb::rv_policy::reference,
           "Get or create render state for viewport")

        .def("remove_viewport_state", [](RenderingManager& self, nb::object viewport_py) {
            tc_viewport_handle vh = get_viewport_handle(viewport_py);
            self.remove_viewport_state(vh);
        }, nb::arg("viewport"),
           "Remove render state for viewport")

        // ================================================================
        // Shutdown
        // ================================================================

        .def("shutdown", &RenderingManager::shutdown,
             "Cleanup all resources")

        .def("get_render_stats", [](RenderingManager& self) -> nb::dict {
            nb::dict stats;
            stats["attached_scenes"] = self.attached_scenes().size();
            stats["display_count"] = self.displays().size();

            // Count scene pipelines
            int pipeline_count = 0;
            nb::list scene_names;
            nb::list pipeline_names;
            for (tc_scene_handle scene : self.attached_scenes()) {
                const char* name = tc_scene_get_name(scene);
                scene_names.append(name ? name : "<unnamed>");
                auto names = self.get_pipeline_names(scene);
                for (const auto& pn : names) {
                    pipeline_count++;
                    pipeline_names.append(pn);
                }
            }
            stats["scene_pipelines"] = pipeline_count;
            stats["scene_names"] = scene_names;
            stats["pipeline_names"] = pipeline_names;

            // Count unmanaged viewports
            int unmanaged = 0;
            for (tc_display* display : self.displays()) {
                size_t count = tc_display_get_viewport_count(display);
                for (size_t i = 0; i < count; ++i) {
                    tc_viewport_handle vp = tc_display_get_viewport_at_index(display, i);
                    if (!tc_viewport_handle_valid(vp)) continue;
                    const char* managed = tc_viewport_get_managed_by(vp);
                    if (!managed || managed[0] == '\0') {
                        tc_pipeline_handle ph = tc_viewport_get_pipeline(vp);
                        tc_scene_handle sh = tc_viewport_get_scene(vp);
                        if (tc_pipeline_handle_valid(ph) && tc_scene_handle_valid(sh)) {
                            unmanaged++;
                        }
                    }
                }
            }
            stats["unmanaged_viewports"] = unmanaged;

            return stats;
        }, "Get render statistics for debugging")
    ;
}

} // namespace termin
