// editor_interaction_bindings.cpp - Python bindings for editor interaction system

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/function.h>

#include "termin/editor/editor_interaction_system.hpp"
#include "termin/editor/editor_viewport_input_manager.hpp"
#include "termin/editor/selection_manager.hpp"
#include <termin/entity/entity.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx2/immediate_renderer.hpp>
#include <tgfx2/render_context.hpp>

#include <utility>

namespace nb = nanobind;

namespace termin {

void bind_editor_interaction(nb::module_& m) {
    nb::module_::import_("tcbase._geom_native");

    // SelectionManager
    nb::class_<SelectionManager>(m, "SelectionManager")
        .def_prop_ro("selected", &SelectionManager::selected)
        .def_prop_ro("hovered", &SelectionManager::hovered)
        .def_ro("selected_pick_id", &SelectionManager::selected_pick_id)
        .def_ro("hovered_pick_id", &SelectionManager::hovered_pick_id)
        .def("select", [](SelectionManager& s, nb::object obj) {
            s.select(obj.is_none() ? Entity() : nb::cast<Entity>(obj));
        }, nb::arg("entity").none())
        .def("hover", [](SelectionManager& s, nb::object obj) {
            s.hover(obj.is_none() ? Entity() : nb::cast<Entity>(obj));
        }, nb::arg("entity").none())
        .def("clear", &SelectionManager::clear)
        .def("deselect", &SelectionManager::deselect)
        .def_prop_rw("on_selection_changed",
            [](SelectionManager& s) { return s.on_selection_changed; },
            [](SelectionManager& s, std::function<void(Entity)> cb) {
                s.on_selection_changed = cb;
            })
        .def_prop_rw("on_hover_changed",
            [](SelectionManager& s) { return s.on_hover_changed; },
            [](SelectionManager& s, std::function<void(Entity)> cb) {
                s.on_hover_changed = cb;
            });

    // EditorViewportInputManager (per-viewport)
    nb::class_<EditorViewportInputManager>(m, "EditorViewportInputManager")
        .def("__init__", [](EditorViewportInputManager* self,
                           uint32_t vp_index, uint32_t vp_generation,
                           uintptr_t display_ptr) {
            tc_viewport_handle vh;
            vh.index = vp_index;
            vh.generation = vp_generation;
            new (self) EditorViewportInputManager(
                vh, reinterpret_cast<tc_display*>(display_ptr));
        }, nb::arg("vp_index"), nb::arg("vp_generation"), nb::arg("display_ptr"))
        .def("tc_input_manager_ptr", [](EditorViewportInputManager& s) {
            return reinterpret_cast<uintptr_t>(s.tc_input_manager_ptr());
        });

    nb::class_<SurfacePickResult>(m, "SurfacePickResult")
        .def(nb::init<>())
        .def_prop_rw("entity",
            [](const SurfacePickResult& r) -> nb::object {
                return r.entity.valid() ? nb::cast(r.entity) : nb::none();
            },
            [](SurfacePickResult& r, nb::object obj) {
                r.entity = obj.is_none() ? Entity() : nb::cast<Entity>(obj);
            })
        .def_rw("has_world_point", &SurfacePickResult::has_world_point)
        .def_rw("world_point", &SurfacePickResult::world_point)
        .def_rw("depth", &SurfacePickResult::depth)
        .def_rw("view_depth", &SurfacePickResult::view_depth)
        .def_rw("reproject_screen_error", &SurfacePickResult::reproject_screen_error)
        .def_rw("reproject_depth_error", &SurfacePickResult::reproject_depth_error)
        .def_rw("has_mesh_hit", &SurfacePickResult::has_mesh_hit)
        .def_rw("mesh_point", &SurfacePickResult::mesh_point)
        .def_rw("mesh_normal", &SurfacePickResult::mesh_normal)
        .def_rw("mesh_triangle_index", &SurfacePickResult::mesh_triangle_index)
        .def_rw("mesh_indices", &SurfacePickResult::mesh_indices);

    nb::class_<EditorEntityClickEvent>(m, "EditorEntityClickEvent")
        .def(nb::init<>())
        .def_prop_rw("entity",
            [](const EditorEntityClickEvent& e) -> nb::object {
                return e.entity.valid() ? nb::cast(e.entity) : nb::none();
            },
            [](EditorEntityClickEvent& e, nb::object obj) {
                e.entity = obj.is_none() ? Entity() : nb::cast<Entity>(obj);
            })
        .def_rw("screen", &EditorEntityClickEvent::screen)
        .def_rw("surface", &EditorEntityClickEvent::surface);

    nb::class_<ViewportPointerEvent>(m, "ViewportPointerEvent")
        .def(nb::init<>())
        .def_rw("phase", &ViewportPointerEvent::phase)
        .def_rw("screen", &ViewportPointerEvent::screen)
        .def_rw("delta", &ViewportPointerEvent::delta)
        .def_rw("button", &ViewportPointerEvent::button)
        .def_rw("action", &ViewportPointerEvent::action)
        .def_rw("mods", &ViewportPointerEvent::mods);

    // EditorInteractionSystem (singleton)
    nb::class_<EditorInteractionSystem>(m, "EditorInteractionSystem")
        .def(nb::init<>())
        .def_static("instance", &EditorInteractionSystem::instance,
            nb::rv_policy::reference)
        .def_static("set_instance", [](nb::object obj) {
            EditorInteractionSystem::set_instance(
                obj.is_none() ? nullptr : nb::cast<EditorInteractionSystem*>(obj));
        }, nb::arg("instance").none())
        .def_prop_ro("selection",
            [](EditorInteractionSystem& s) -> SelectionManager& {
                return s.selection;
            }, nb::rv_policy::reference_internal)
        .def_prop_ro("gizmo_manager",
            [](EditorInteractionSystem& s) -> GizmoManager& {
                return s.gizmo_manager;
            }, nb::rv_policy::reference_internal)
        .def_prop_ro("transform_gizmo",
            [](EditorInteractionSystem& s) -> TransformGizmo* {
                return s.transform_gizmo();
            }, nb::rv_policy::reference_internal)
        .def("after_render", &EditorInteractionSystem::after_render)
        .def_prop_rw("camera_frustums_visible",
            [](const EditorInteractionSystem& s) {
                return s.camera_frustums_visible();
            },
            [](EditorInteractionSystem& s, bool visible) {
                s.set_camera_frustums_visible(visible);
            })
        .def("set_camera_frustums_visible", &EditorInteractionSystem::set_camera_frustums_visible,
            nb::arg("visible"))
        .def("set_camera_frustum_render_context",
            [](EditorInteractionSystem& s, const TcSceneRef& scene, const Rect2i& rect) {
                s.set_camera_frustum_render_context(scene.handle(), rect.width, rect.height);
            },
            nb::arg("scene"),
            nb::arg("render_rect"))
        .def("set_gizmo_target", [](EditorInteractionSystem& s, nb::object obj) {
            s.set_gizmo_target(obj.is_none() ? Entity() : nb::cast<Entity>(obj));
        }, nb::arg("entity").none())
        .def("render", [](EditorInteractionSystem& s,
                          ImmediateRenderer* renderer,
                          tgfx::RenderContext2* ctx2,
                          const Mat44& view,
                          const Mat44& proj) {
            Mat44f view_f, proj_f;
            for (int i = 0; i < 16; ++i) {
                view_f.data[i] = static_cast<float>(view.data[i]);
                proj_f.data[i] = static_cast<float>(proj.data[i]);
            }
            s.gizmo_manager.render(renderer, ctx2, view_f, proj_f);
        }, nb::arg("renderer"), nb::arg("ctx2"), nb::arg("view"), nb::arg("proj"))
        .def("pick_entity_at", [](EditorInteractionSystem& s,
                float x, float y,
                uint32_t vp_index, uint32_t vp_generation,
                uintptr_t display_ptr) {
            tc_viewport_handle vp;
            vp.index = vp_index;
            vp.generation = vp_generation;
            return s.pick_entity_at(Vec2f{x, y}, vp,
                reinterpret_cast<tc_display*>(display_ptr));
        })
        .def("pick_surface_at", [](EditorInteractionSystem& s,
                float x, float y,
                uint32_t vp_index, uint32_t vp_generation,
                uintptr_t display_ptr) {
            tc_viewport_handle vp;
            vp.index = vp_index;
            vp.generation = vp_generation;
            return s.pick_surface_at(
                Vec2f{x, y}, vp, reinterpret_cast<tc_display*>(display_ptr));
        })
        .def_prop_rw("on_request_update",
            [](EditorInteractionSystem& s) { return s.on_request_update; },
            [](EditorInteractionSystem& s, std::function<void()> cb) {
                s.on_request_update = cb;
            })
        .def_prop_rw("on_transform_end",
            [](EditorInteractionSystem& s) { return s.on_transform_end; },
            [](EditorInteractionSystem& s,
               std::function<void(const GeneralPose3&, const GeneralPose3&)> cb) {
                s.on_transform_end = cb;
            })
        .def_prop_rw("on_key",
            [](EditorInteractionSystem& s) { return s.on_key; },
            [](EditorInteractionSystem& s,
               std::function<void(const KeyEvent&)> cb) {
                s.on_key = cb;
            })
        .def_prop_rw("on_entity_click",
            [](EditorInteractionSystem&) -> nb::object { return nb::none(); },
            [](EditorInteractionSystem& s, nb::object cb) {
                if (cb.is_none()) {
                    s.on_entity_click = nullptr;
                    return;
                }
                nb::callable fn = nb::cast<nb::callable>(cb);
                s.on_entity_click = [fn = std::move(fn)](const EditorEntityClickEvent& event) -> bool {
                    nb::gil_scoped_acquire gil;
                    return nb::cast<bool>(fn(event));
                };
            })
        .def_prop_rw("on_viewport_pointer_event",
            [](EditorInteractionSystem&) -> nb::object { return nb::none(); },
            [](EditorInteractionSystem& s, nb::object cb) {
                if (cb.is_none()) {
                    s.on_viewport_pointer_event = nullptr;
                    return;
                }
                nb::callable fn = nb::cast<nb::callable>(cb);
                s.on_viewport_pointer_event = [fn = std::move(fn)](const ViewportPointerEvent& event) -> bool {
                    nb::gil_scoped_acquire gil;
                    return nb::cast<bool>(fn(event));
                };
            });
}

} // namespace termin
