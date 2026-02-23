// editor_interaction_bindings.cpp - Python bindings for editor interaction system

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/function.h>

#include "termin/editor/editor_interaction_system.hpp"
#include "termin/editor/editor_viewport_input_manager.hpp"
#include "termin/editor/selection_manager.hpp"
#include "termin/entity/entity.hpp"
#include "tgfx/graphics_backend.hpp"

namespace nb = nanobind;

namespace termin {

void bind_editor_interaction(nb::module_& m) {
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

    // EditorInteractionSystem (singleton)
    nb::class_<EditorInteractionSystem>(m, "EditorInteractionSystem")
        .def(nb::init<>())
        .def_static("instance", &EditorInteractionSystem::instance,
            nb::rv_policy::reference)
        .def_static("set_instance", &EditorInteractionSystem::set_instance)
        .def("set_graphics", &EditorInteractionSystem::set_graphics,
            nb::arg("graphics"), nb::keep_alive<1, 2>())
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
        .def("set_gizmo_target", [](EditorInteractionSystem& s, nb::object obj) {
            s.set_gizmo_target(obj.is_none() ? Entity() : nb::cast<Entity>(obj));
        }, nb::arg("entity").none())
        .def("pick_entity_at", [](EditorInteractionSystem& s,
                float x, float y,
                uint32_t vp_index, uint32_t vp_generation,
                uintptr_t display_ptr) {
            tc_viewport_handle vp;
            vp.index = vp_index;
            vp.generation = vp_generation;
            return s.pick_entity_at(x, y, vp,
                reinterpret_cast<tc_display*>(display_ptr));
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
            });
}

} // namespace termin
