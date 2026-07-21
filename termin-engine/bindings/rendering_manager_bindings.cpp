// rendering_manager_bindings.cpp - Python bindings for RenderingManager
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/function.h>
#include <nanobind/stl/map.h>
#include <nanobind/stl/optional.h>
#include <nanobind/nanobind.h>

#include "termin/render/rendering_manager.hpp"
#include "termin/render/frame_graph_debugger.hpp"
#include "termin/render/render_attachment_context.hpp"
#include "termin/render/render_pipeline.hpp"
#include "termin/render/viewport_render_state.hpp"
#include "termin/render/tc_display_handle.hpp"
#include "termin/viewport/tc_viewport_handle.hpp"

extern "C" {
#include "core/tc_scene.h"
#include "render/tc_display.h"
#include "render/tc_viewport.h"
#include "render/tc_render_target.h"
}

namespace termin {

namespace nb = nanobind;

static nb::list size_list_to_python(const std::vector<size_t>& values) {
    nb::list out;
    for (size_t value : values) {
        out.append(value);
    }
    return out;
}

static tc_pipeline_handle pipeline_handle_from_python(nb::handle obj) {
    if (obj.is_none()) {
        return TC_PIPELINE_HANDLE_INVALID;
    }
    nb::object pipeline_obj = nb::borrow<nb::object>(obj);
    return nb::cast<tc_pipeline_handle>(pipeline_obj.attr("_pipeline_handle"));
}

static nb::object pipeline_to_python(tc_pipeline_handle h) {
    if (!tc_pipeline_handle_valid(h)) {
        return nb::none();
    }

    nb::module_ rf = nb::module_::import_("termin.render_framework._render_framework_native");
    return rf.attr("RenderPipeline").attr("from_handle")(h.index, h.generation);
}

// Helper to extract tc_scene_handle from Python Scene object (Scene inherits TcScene)
static tc_scene_handle get_scene_handle(nb::object scene_py) {
    if (scene_py.is_none()) return TC_SCENE_HANDLE_INVALID;
    return nb::cast<tc_scene_handle>(scene_py.attr("scene_handle")());
}

static tc_display_handle get_display_handle(nb::object display_py) {
    if (display_py.is_none()) return TC_DISPLAY_HANDLE_INVALID;
    return tc_display_handle{
        nb::cast<uint32_t>(display_py.attr("index")),
        nb::cast<uint32_t>(display_py.attr("generation"))
    };
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

static std::tuple<uint32_t, uint32_t> render_target_handle_to_tuple(
    tc_render_target_handle h
) {
    return {h.index, h.generation};
}

static std::tuple<uint32_t, uint32_t> pipeline_handle_to_tuple(tc_pipeline_handle h) {
    return {h.index, h.generation};
}

static std::tuple<uint32_t, uint32_t> display_handle_to_tuple(tc_display_handle h) {
    return {h.index, h.generation};
}

static std::tuple<uint32_t, uint32_t> scene_handle_to_tuple(tc_scene_handle h) {
    return {h.index, h.generation};
}

// Helper to extract viewport handle from Python Viewport object (TcViewport)
static tc_viewport_handle get_viewport_handle(nb::object viewport_py) {
    tc_viewport_handle h = TC_VIEWPORT_HANDLE_INVALID;
    if (viewport_py.is_none()) return h;
    // Viewport.handle is a uint64 property that packs (index << 32 | generation)
    uint64_t packed = nb::cast<uint64_t>(viewport_py.attr("handle"));
    h.index = static_cast<uint32_t>(packed >> 32);
    h.generation = static_cast<uint32_t>(packed & 0xFFFFFFFF);
    return h;
}

void bind_rendering_manager(nb::module_& m) {
    // ViewportRenderState - runtime GPU output state helper (native tgfx2).
    nb::class_<ViewportRenderState>(m, "ViewportRenderState")
        .def_prop_ro("output_width", [](ViewportRenderState& self) { return self.output_width; })
        .def_prop_ro("output_height", [](ViewportRenderState& self) { return self.output_height; })
        .def("has_output", &ViewportRenderState::has_output)
        .def("clear_all", &ViewportRenderState::clear_all)
        .def_prop_ro("output_color_tex", [](ViewportRenderState& self) {
            return self.output_color_tex;
        })
        .def_prop_ro("output_depth_tex", [](ViewportRenderState& self) {
            return self.output_depth_tex;
        })
    ;

    nb::class_<RenderAttachmentContext>(m, "RenderAttachmentContext")
        .def_static("_from_capsule", [](nb::object capsule) {
            void* pointer = PyCapsule_GetPointer(
                capsule.ptr(),
                "termin.RenderAttachmentContext"
            );
            if (!pointer) throw nb::python_error();
            return *reinterpret_cast<const RenderAttachmentContext*>(pointer);
        })
        .def_prop_ro("valid", &RenderAttachmentContext::valid)
        .def_prop_ro("scene_handle", [](const RenderAttachmentContext& self) {
            return self.scene();
        })
        .def_prop_ro("render_targets", &RenderAttachmentContext::render_targets)
        .def("find_render_target", [](const RenderAttachmentContext& self,
                                       const std::string& name) -> nb::object {
            tc_render_target_handle target = self.find_render_target(name);
            return tc_render_target_handle_valid(target) ? nb::cast(target) : nb::none();
        }, nb::arg("name"))
        .def("find_camera_target", [](const RenderAttachmentContext& self,
                                       nb::object camera) -> nb::object {
            if (camera.is_none()) return nb::none();
            uintptr_t pointer = nb::cast<uintptr_t>(camera.attr("c_ptr_int")());
            tc_render_target_handle target = self.find_camera_target(
                reinterpret_cast<const tc_component*>(pointer)
            );
            return tc_render_target_handle_valid(target) ? nb::cast(target) : nb::none();
        }, nb::arg("camera"))
        .def("get_pipeline", [](const RenderAttachmentContext& self,
                                 const std::string& name) -> nb::object {
            return pipeline_to_python(self.get_pipeline(name));
        }, nb::arg("name"))
    ;

    nb::class_<RenderTopology>(m, "RenderTopology")
        .def("is_attached", [](const RenderTopology& self, nb::object scene_py) {
            return self.is_attached(get_scene_handle(scene_py));
        }, nb::arg("scene"))
        .def("get_pipeline", [](const RenderTopology& self,
                                  nb::object scene_py,
                                  const std::string& name) -> nb::object {
            return pipeline_to_python(self.get_pipeline(get_scene_handle(scene_py), name));
        }, nb::arg("scene"), nb::arg("name"))
        .def("get_pipeline_names", [](const RenderTopology& self, nb::object scene_py) {
            return self.get_pipeline_names(get_scene_handle(scene_py));
        }, nb::arg("scene"))
        .def("find_render_target", [](const RenderTopology& self,
                                       nb::object scene_py,
                                       const std::string& name) -> nb::object {
            tc_render_target_handle target = self.find_render_target(
                get_scene_handle(scene_py),
                name
            );
            if (!tc_render_target_handle_valid(target)) return nb::none();
            return nb::cast(target);
        }, nb::arg("scene"), nb::arg("name"))
        .def("render_targets", [](const RenderTopology& self, nb::object scene_py) {
            return self.render_targets(get_scene_handle(scene_py));
        }, nb::arg("scene"))
        .def_prop_ro("managed_render_targets", [](const RenderTopology& self) {
            return self.managed_render_targets();
        })
        .def("viewports", [](const RenderTopology& self, nb::object scene_py) {
            std::vector<TcViewport> result;
            for (tc_viewport_handle viewport : self.viewports(get_scene_handle(scene_py))) {
                result.emplace_back(viewport);
            }
            return result;
        }, nb::arg("scene"))
    ;

    nb::class_<RenderingManager>(m, "RenderingManager")
        .def_prop_ro("topology", [](RenderingManager& self) -> RenderTopology& {
            return self.topology();
        }, nb::rv_policy::reference_internal)

        // ================================================================
        // Configuration
        // ================================================================

        .def_prop_ro("render_engine", &RenderingManager::render_engine,
                     nb::rv_policy::reference,
                     "Access the engine's RenderEngine (tgfx2_ctx lives on it)")

        .def("set_display_factory", [](RenderingManager& self, nb::object factory) {
            if (factory.is_none()) {
                self.set_display_factory(nullptr);
            } else {
                nb::object stored = factory;
                self.set_display_factory([stored](const std::string& name) -> tc_display_handle {
                    nb::gil_scoped_acquire gil;
                    nb::object result = stored(name);
                    return get_display_handle(result);
                });
            }
        }, nb::arg("factory").none(),
           "Set factory for creating displays on demand")

        .def("set_pipeline_factory", [](RenderingManager& self, nb::object factory) {
            if (factory.is_none()) {
                self.set_pipeline_factory(nullptr);
            } else {
                nb::object stored = factory;
                self.set_pipeline_factory([stored](const std::string& name) -> tc_pipeline_handle {
                    nb::gil_scoped_acquire gil;
                    nb::object result = stored(name);
                    return pipeline_handle_from_python(result);
                });
            }
        }, nb::arg("factory").none(),
           "Set factory for creating pipelines by special name")

        .def("set_display_removed_callback", [](RenderingManager& self, nb::object callback) {
            if (callback.is_none()) {
                self.set_display_removed_callback(nullptr);
            } else {
                nb::object stored = callback;
                self.set_display_removed_callback([stored](tc_display_handle display) {
                    nb::gil_scoped_acquire gil;
                    // Wrap in non-owning TcDisplay for Python
                    stored(TcDisplay::from_handle(display));
                });
            }
        }, nb::arg("callback").none(),
           "Set callback called when a display is removed (for editor cleanup)")

        .def("try_auto_remove_display", [](RenderingManager& self, TcDisplay& display) -> bool {
            return self.try_auto_remove_display(display.handle());
        }, nb::arg("display"),
           "Check if display should be auto-removed (empty + flag set). Returns true if removed.")

        // ================================================================
        // Display Management
        // ================================================================

        .def("add_display", [](RenderingManager& self, TcDisplay& display, nb::object name_py) {
            if (display.is_valid()) {
                self.add_display(display.handle());
                if (!name_py.is_none()) {
                    std::string name = nb::cast<std::string>(name_py);
                    display.set_name(name);
                }
            }
        }, nb::arg("display"), nb::arg("name") = nb::none(),
           "Add display to management")

        .def("remove_display", [](RenderingManager& self, TcDisplay& display) {
            if (display.is_valid()) {
                self.remove_display(display.handle());
            }
        }, nb::arg("display"),
           "Remove display from management")

        .def("add_editor_display", [](RenderingManager& self, TcDisplay& display) {
            if (display.is_valid()) {
                self.add_editor_display(display.handle());
            }
        }, nb::arg("display"),
           "Add editor display (skipped by detach_scene_full)")

        .def("remove_editor_display", [](RenderingManager& self, TcDisplay& display) {
            if (display.is_valid()) {
                self.remove_editor_display(display.handle());
            }
        }, nb::arg("display"),
           "Remove editor display from management")

        .def("register_viewport_attachment", [](RenderingManager& self,
                                                  TcDisplay& display,
                                                  nb::object viewport_py,
                                                  bool destroy_on_scene_detach) {
            return self.register_viewport_attachment(
                display.handle(),
                get_viewport_handle(viewport_py),
                destroy_on_scene_detach
            );
        }, nb::arg("display"), nb::arg("viewport"),
           nb::arg("destroy_on_scene_detach") = true)

        .def("unregister_viewport_attachment", [](RenderingManager& self,
                                                    nb::object viewport_py) {
            return self.unregister_viewport_attachment(get_viewport_handle(viewport_py));
        }, nb::arg("viewport"))

        .def_prop_ro("editor_displays", [](RenderingManager& self) -> std::vector<TcDisplay> {
            std::vector<TcDisplay> result;
            for (tc_display_handle d : self.editor_displays()) {
                result.push_back(TcDisplay::from_handle(d));
            }
            return result;
        }, "List of editor displays")

        .def("get_display_by_name", [](RenderingManager& self, const std::string& name) -> nb::object {
            tc_display_handle display = self.get_display_by_name(name);
            return tc_display_alive(display)
                ? nb::cast(TcDisplay::from_handle(display)) : nb::none();
        }, nb::arg("name"),
           "Find display by name, returning a non-owning handle facade")

        .def("get_or_create_display", [](RenderingManager& self, const std::string& name) -> nb::object {
            tc_display_handle display = self.get_or_create_display(name);
            return tc_display_alive(display)
                ? nb::cast(TcDisplay::from_handle(display)) : nb::none();
        }, nb::arg("name"),
           "Get existing display or create via factory")

        .def_prop_ro("display_count", [](RenderingManager& self) {
            return self.displays().size() + self.editor_displays().size();
        }, "Number of all managed displays")

        .def_prop_ro("displays", [](RenderingManager& self) -> std::vector<TcDisplay> {
            std::vector<TcDisplay> result;
            for (tc_display_handle d : self.displays()) {
                result.push_back(TcDisplay::from_handle(d));
            }
            for (tc_display_handle d : self.editor_displays()) {
                result.push_back(TcDisplay::from_handle(d));
            }
            return result;
        }, "List of all managed displays (scene + editor)")

        .def_prop_ro("scene_displays", [](RenderingManager& self) -> std::vector<TcDisplay> {
            std::vector<TcDisplay> result;
            for (tc_display_handle d : self.displays()) {
                result.push_back(TcDisplay::from_handle(d));
            }
            return result;
        }, "List of scene displays only (cleaned up by detach_scene_full)")

        .def("get_display_for_viewport", [](RenderingManager& self, nb::object viewport_py) -> nb::object {
            tc_viewport_handle vh = get_viewport_handle(viewport_py);
            if (!tc_viewport_handle_valid(vh)) return nb::none();

            // Search through displays for this viewport
            for (tc_display_handle display : self.displays()) {
                size_t count = tc_display_get_viewport_count(display);
                for (size_t i = 0; i < count; ++i) {
                    tc_viewport_handle vph = tc_display_get_viewport_at_index(display, i);
                    if (tc_viewport_handle_eq(vph, vh)) {
                        return nb::cast(TcDisplay::from_handle(display));
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
            if (display.is_valid()) {
                self.unmount_scene(scene, display.handle());
            }
        }, nb::arg("scene"), nb::arg("display"),
           "Unmount scene from display (removes all viewports showing this scene)")

        // ================================================================
        // Managed Render Target Management
        // ================================================================

        .def("register_managed_render_target", [](RenderingManager& self, nb::object rt_py) {
            auto h = nb::cast<tc_render_target_handle>(rt_py);
            self.register_managed_render_target(h);
        }, nb::arg("render_target"),
           "Register a render target managed by RenderingManager")

        .def("unregister_managed_render_target", [](RenderingManager& self, nb::object rt_py) {
            auto h = nb::cast<tc_render_target_handle>(rt_py);
            self.unregister_managed_render_target(h);
        }, nb::arg("render_target"),
           "Unregister a render target managed by RenderingManager")

        .def_prop_ro("managed_render_targets", [](RenderingManager& self)
                -> std::vector<tc_render_target_handle> {
            return self.managed_render_targets();
        }, "List of render targets managed by RenderingManager")

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
                                       const std::string& name) -> nb::object {
            tc_scene_handle scene = get_scene_handle(scene_py);
            return pipeline_to_python(self.get_scene_pipeline(scene, name));
        }, nb::arg("scene"), nb::arg("name"))

        .def("get_scene_pipeline", [](RenderingManager& self,
                                       const std::string& name) -> nb::object {
            return pipeline_to_python(self.get_scene_pipeline(name));
        }, nb::arg("name"))

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
            if (display.is_valid()) {
                self.present_display(display.handle());
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

        .def("create_pipeline", [](RenderingManager& self, const std::string& name) -> nb::object {
            tc_pipeline_handle h = self.create_pipeline(name);
            return pipeline_to_python(h);
        }, nb::arg("name"))

        .def("recreate_render_target_pipelines_for_asset",
             &RenderingManager::recreate_render_target_pipelines_for_asset,
             nb::arg("asset_name"),
             nb::arg("asset_uuid") = "",
             "Recreate live render-target pipelines that came from a pipeline asset")

        .def("shutdown", &RenderingManager::shutdown,
             "Cleanup all resources")

        .def("get_render_stats", [](RenderingManager& self) -> nb::dict {
            nb::dict stats;
            stats["attached_scenes"] = self.attached_scenes().size();
            stats["display_count"] = self.displays().size();
            stats["editor_display_count"] = self.editor_displays().size();

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

            // Count unmanaged viewports across all displays
            auto count_unmanaged = [](const std::vector<tc_display_handle>& disp_list) -> int {
                int unmanaged = 0;
                for (tc_display_handle display : disp_list) {
                    size_t count = tc_display_get_viewport_count(display);
                    for (size_t i = 0; i < count; ++i) {
                        tc_viewport_handle vp = tc_display_get_viewport_at_index(display, i);
                        if (!tc_viewport_handle_valid(vp)) continue;
                        const char* managed = tc_viewport_get_managed_by(vp);
                        if (!managed || managed[0] == '\0') {
                            tc_render_target_handle rt = tc_viewport_get_render_target(vp);
                            tc_pipeline_handle ph = tc_render_target_get_pipeline(rt);
                            tc_scene_handle sh = tc_viewport_get_scene(vp);
                            if (tc_pipeline_handle_valid(ph) && tc_scene_handle_valid(sh)) {
                                unmanaged++;
                            }
                        }
                    }
                }
                return unmanaged;
            };
            stats["unmanaged_viewports"] = count_unmanaged(self.displays()) + count_unmanaged(self.editor_displays());

            termin::RenderPipelineCacheStats cache_stats;
            if (const RenderEngine* engine = self.render_engine_if_created()) {
                cache_stats = engine->pipeline_cache_stats();
            }
            stats["pipeline_cache_hits"] = cache_stats.hit_count;
            stats["pipeline_cache_misses"] = cache_stats.miss_count;
            stats["pipeline_cache_create_pipeline_count"] =
                cache_stats.create_pipeline_count;
            stats["pipeline_cache_cached_pipelines"] =
                cache_stats.cached_pipeline_count;
            stats["pipeline_cache_unique_vertex_layout_signatures"] =
                cache_stats.unique_vertex_layout_signature_count;
            stats["pipeline_cache_vertex_layout_signature_hashes"] =
                size_list_to_python(cache_stats.vertex_layout_signature_hashes);

            return stats;
        }, "Get render statistics for debugging")
    ;

    nb::enum_<RenderExecutionTargetKind>(m, "RenderExecutionTargetKind")
        .value("Viewport", RenderExecutionTargetKind::Viewport)
        .value("RenderTarget", RenderExecutionTargetKind::RenderTarget);

    nb::class_<RenderExecutionTargetId>(m, "RenderExecutionTargetId")
        .def_prop_ro("kind", [](const RenderExecutionTargetId& self) {
            return self.kind;
        })
        .def_prop_ro("viewport_handle", [](const RenderExecutionTargetId& self) {
            return viewport_handle_to_tuple(self.viewport);
        })
        .def_prop_ro("render_target_handle", [](const RenderExecutionTargetId& self) {
            return render_target_handle_to_tuple(self.render_target);
        })
        .def("__eq__", [](const RenderExecutionTargetId& self,
                            const RenderExecutionTargetId& other) {
            return self == other;
        });

    nb::class_<RenderExecutionTargetInfo>(m, "RenderExecutionTargetInfo")
        .def_prop_ro("id", [](const RenderExecutionTargetInfo& self) {
            return self.id;
        })
        .def_prop_ro("display_handle", [](const RenderExecutionTargetInfo& self) {
            return display_handle_to_tuple(self.display);
        })
        .def_prop_ro("scene_handle", [](const RenderExecutionTargetInfo& self) {
            return scene_handle_to_tuple(self.scene);
        })
        .def_prop_ro("pipeline_handle", [](const RenderExecutionTargetInfo& self) {
            return pipeline_handle_to_tuple(self.pipeline);
        })
        .def_prop_ro("pipeline", [](const RenderExecutionTargetInfo& self) {
            return pipeline_to_python(self.pipeline);
        })
        .def_ro("label", &RenderExecutionTargetInfo::label)
        .def_ro("renderable", &RenderExecutionTargetInfo::renderable);

    nb::enum_<FrameGraphDebuggerState>(m, "FrameGraphDebuggerState")
        .value("Unbound", FrameGraphDebuggerState::Unbound)
        .value("Bound", FrameGraphDebuggerState::Bound)
        .value("WaitingFrame", FrameGraphDebuggerState::WaitingFrame)
        .value("Captured", FrameGraphDebuggerState::Captured)
        .value("Suspended", FrameGraphDebuggerState::Suspended)
        .value("Error", FrameGraphDebuggerState::Error);

    nb::enum_<FrameGraphDebuggerSuspendReason>(m, "FrameGraphDebuggerSuspendReason")
        .value("None", FrameGraphDebuggerSuspendReason::None)
        .value("TargetRemoved", FrameGraphDebuggerSuspendReason::TargetRemoved)
        .value("PipelineUnavailable", FrameGraphDebuggerSuspendReason::PipelineUnavailable)
        .value("TargetNotRenderable", FrameGraphDebuggerSuspendReason::TargetNotRenderable);

    nb::enum_<FrameGraphDebuggerMode>(m, "FrameGraphDebuggerMode")
        .value("BetweenPasses", FrameGraphDebuggerMode::BetweenPasses)
        .value("InsidePass", FrameGraphDebuggerMode::InsidePass);

    nb::class_<FrameGraphDebuggerPassInfo>(m, "FrameGraphDebuggerPassInfo")
        .def_ro("index", &FrameGraphDebuggerPassInfo::index)
        .def_ro("name", &FrameGraphDebuggerPassInfo::name)
        .def_ro("type", &FrameGraphDebuggerPassInfo::type)
        .def_ro("enabled", &FrameGraphDebuggerPassInfo::enabled)
        .def_ro("passthrough", &FrameGraphDebuggerPassInfo::passthrough)
        .def_ro("reads", &FrameGraphDebuggerPassInfo::reads)
        .def_ro("writes", &FrameGraphDebuggerPassInfo::writes)
        .def_ro("internal_symbols", &FrameGraphDebuggerPassInfo::internal_symbols)
        .def_prop_ro("has_internal_symbols",
            &FrameGraphDebuggerPassInfo::has_internal_symbols)
        .def_prop_ro("display_name", &FrameGraphDebuggerPassInfo::display_name);

    nb::class_<FrameGraphDebugger>(m, "FrameGraphDebugger")
        .def(nb::init<RenderingManager&>(), nb::arg("rendering_manager"),
             nb::keep_alive<1, 2>())
        .def("refresh", &FrameGraphDebugger::refresh)
        .def("finish_frame", &FrameGraphDebugger::finish_frame)
        .def("select_target_at", &FrameGraphDebugger::select_target_at,
             nb::arg("index"))
        .def("clear_selection", &FrameGraphDebugger::clear_selection)
        .def("request_resource", &FrameGraphDebugger::request_resource,
             nb::arg("resource"))
        .def("request_internal", &FrameGraphDebugger::request_internal,
             nb::arg("pass_index"), nb::arg("symbol"))
        .def("set_paused", &FrameGraphDebugger::set_paused,
             nb::arg("paused"))
        .def("cancel_request", &FrameGraphDebugger::cancel_request)
        .def("connect", &FrameGraphDebugger::connect)
        .def("disconnect", &FrameGraphDebugger::disconnect)
        .def_prop_ro("targets", [](const FrameGraphDebugger& self) {
            return self.targets();
        })
        .def_prop_ro("selected_target_index",
            &FrameGraphDebugger::selected_target_index)
        .def_prop_ro("has_selection", &FrameGraphDebugger::has_selection)
        .def_prop_ro("state", &FrameGraphDebugger::state)
        .def_prop_ro("suspend_reason", &FrameGraphDebugger::suspend_reason)
        .def_prop_ro("revision", &FrameGraphDebugger::revision)
        .def_prop_ro("request_generation", &FrameGraphDebugger::request_generation)
        .def_prop_ro("requested_resource", &FrameGraphDebugger::requested_resource)
        .def_prop_ro("paused", &FrameGraphDebugger::paused)
        .def_prop_rw("mode", &FrameGraphDebugger::mode, &FrameGraphDebugger::set_mode)
        .def_prop_rw("selected_pass_index",
            &FrameGraphDebugger::selected_pass_index,
            &FrameGraphDebugger::set_selected_pass)
        .def_prop_ro("selected_pass", &FrameGraphDebugger::selected_pass_name)
        .def_prop_rw("selected_symbol",
            &FrameGraphDebugger::selected_symbol,
            &FrameGraphDebugger::set_selected_symbol)
        .def_prop_rw("selected_resource",
            &FrameGraphDebugger::selected_resource,
            &FrameGraphDebugger::set_selected_resource)
        .def_prop_rw("channel_mode",
            &FrameGraphDebugger::channel_mode,
            &FrameGraphDebugger::set_channel_mode)
        .def_prop_rw("highlight_hdr",
            &FrameGraphDebugger::highlight_hdr,
            &FrameGraphDebugger::set_highlight_hdr)
        .def("passes", &FrameGraphDebugger::passes)
        .def("schedule", &FrameGraphDebugger::schedule)
        .def("resources", &FrameGraphDebugger::resources)
        .def("alias_groups", &FrameGraphDebugger::alias_groups)
        .def("symbols", &FrameGraphDebugger::symbols)
        .def("format_capture_info", &FrameGraphDebugger::format_capture_info)
        .def("format_writer_pass", &FrameGraphDebugger::format_writer_pass)
        .def("format_pipeline_info", &FrameGraphDebugger::format_pipeline_info)
        .def("format_pass_json", &FrameGraphDebugger::format_pass_json)
        .def("format_pass_json_at", &FrameGraphDebugger::format_pass_json_at,
             nb::arg("pass_index"))
        .def("format_timing", &FrameGraphDebugger::format_timing)
        .def("format_render_stats", &FrameGraphDebugger::format_render_stats)
        .def("analyze_hdr", &FrameGraphDebugger::analyze_hdr)
        .def_prop_ro("resolved_pipeline_handle", [](const FrameGraphDebugger& self) {
            return pipeline_handle_to_tuple(self.resolved_pipeline());
        })
        .def_prop_ro("capture_tex", &FrameGraphDebugger::capture_tex)
        .def_prop_ro("depth_capture_tex", &FrameGraphDebugger::depth_capture_tex)
        .def_prop_ro("capture", [](FrameGraphDebugger& self) -> FrameGraphCapture& {
            return self.capture();
        }, nb::rv_policy::reference_internal)
        .def_prop_ro("depth_capture", [](FrameGraphDebugger& self) -> FrameGraphCapture& {
            return self.depth_capture();
        }, nb::rv_policy::reference_internal)
        .def_prop_ro("presenter", [](FrameGraphDebugger& self) -> FrameGraphPresenter& {
            return self.presenter();
        }, nb::rv_policy::reference_internal);
}

} // namespace termin
