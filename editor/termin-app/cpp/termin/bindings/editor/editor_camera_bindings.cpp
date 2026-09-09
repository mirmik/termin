#include <nanobind/nanobind.h>
#include <nanobind/stl/function.h>
#include <nanobind/stl/string.h>
#include <termin/bindings/entity_helpers.hpp>
#include "termin/editor/editor_camera_component.hpp"

namespace nb = nanobind;

namespace termin {
    void bind_editor_camera(nb::module_& m) {
        nb::module_::import_("termin.render_components._components_render_native");
        EditorCameraComponent::register_type();
        nb::class_<EditorCameraComponent, CameraComponent>(m, "EditorCameraComponent")
            .def("__init__", [](nb::handle self) { cxx_component_init<EditorCameraComponent>(self); })
            .def_static("register_type", &EditorCameraComponent::register_type)
            .def("enter_axis_view", &EditorCameraComponent::enter_axis_view, nb::arg("focus_distance"))
            .def("leave_axis_view", &EditorCameraComponent::leave_axis_view)
            .def("reset_projection_transition", &EditorCameraComponent::reset_projection_transition)
            .def("finish_projection_transition", &EditorCameraComponent::finish_projection_transition)
            .def("update", &EditorCameraComponent::update, nb::arg("dt"))
            .def_prop_ro("axis_view", &EditorCameraComponent::axis_view)
            .def_prop_ro("transitioning", &EditorCameraComponent::transitioning)
            .def_prop_ro("navigation_projection_type", &EditorCameraComponent::navigation_projection_type)
            .def_prop_ro("navigation_ortho_size", &EditorCameraComponent::navigation_ortho_size)
            .def_rw("transition_duration", &EditorCameraComponent::transition_duration)
            .def_prop_rw("request_render_callback",
                [](EditorCameraComponent& camera) { return camera.request_render_callback; },
                [](EditorCameraComponent& camera, nb::object callback) {
                    camera.request_render_callback = callback.is_none()
                        ? std::function<void()>{} : nb::cast<std::function<void()>>(callback);
                }, nb::for_setter(nb::arg("callback").none()));
    }
} // namespace termin
