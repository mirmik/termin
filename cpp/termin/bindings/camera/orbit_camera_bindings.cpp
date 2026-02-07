// orbit_camera_bindings.cpp - Python bindings for OrbitCameraController

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include "termin/camera/orbit_camera_controller.hpp"
#include "termin/geom/vec3.hpp"
#include "termin/input/input_events.hpp"
#include "termin/bindings/entity/entity_helpers.hpp"

namespace nb = nanobind;
using namespace nb::literals;

namespace termin {

void bind_orbit_camera_controller(nb::module_& m) {
    nb::class_<OrbitCameraController, CxxComponent>(m, "OrbitCameraController")
        .def("__init__", [](nb::handle self, double radius, double min_radius, double max_radius, bool prevent_moving) {
            cxx_component_init<OrbitCameraController>(self, radius, min_radius, max_radius, prevent_moving);
        },
            nb::arg("radius") = 5.0,
            nb::arg("min_radius") = 1.0,
            nb::arg("max_radius") = 100.0,
            nb::arg("prevent_moving") = false)

        // Public parameters
        .def_rw("radius", &OrbitCameraController::radius)
        .def_rw("min_radius", &OrbitCameraController::min_radius)
        .def_rw("max_radius", &OrbitCameraController::max_radius)

        // Camera operations
        .def("orbit", &OrbitCameraController::orbit,
            nb::arg("delta_azimuth"), nb::arg("delta_elevation"),
            "Orbit camera around target (angles in degrees)")
        .def("pan", &OrbitCameraController::pan,
            nb::arg("dx"), nb::arg("dy"),
            "Pan camera (move target in screen space)")
        .def("zoom", &OrbitCameraController::zoom,
            nb::arg("delta"),
            "Zoom camera (change radius or ortho_size)")
        .def("center_on", [](OrbitCameraController& c, nb::object position) {
            // Accept numpy array, list, tuple, or Vec3
            Vec3 pos;
            if (nb::hasattr(position, "__len__")) {
                auto seq = nb::cast<nb::sequence>(position);
                pos.x = nb::cast<double>(seq[0]);
                pos.y = nb::cast<double>(seq[1]);
                pos.z = nb::cast<double>(seq[2]);
            } else {
                pos = nb::cast<Vec3>(position);
            }
            c.center_on(pos);
        }, nb::arg("position"), "Center camera on position")
        .def("fly_move", &OrbitCameraController::fly_move,
            nb::arg("right"), nb::arg("forward"), nb::arg("up"),
            "Translate camera along local axes")
        .def("fly_forward", &OrbitCameraController::fly_forward,
            nb::arg("delta"),
            "Move camera forward/backward along view direction")
        .def("fly_rotate", &OrbitCameraController::fly_rotate,
            nb::arg("yaw"), nb::arg("pitch"), nb::arg("roll") = 0.0,
            "Rotate camera in place: yaw (world Z), pitch (local X), roll (local Y)")
        .def_rw("horizon_lock", &OrbitCameraController::horizon_lock)

        // State accessors
        .def_prop_ro("target", [](OrbitCameraController& c) {
            Vec3 t = c.target();
            // Return as numpy array for compatibility
            nb::module_ np = nb::module_::import_("numpy");
            return np.attr("array")(nb::make_tuple(t.x, t.y, t.z), "dtype"_a = "float32");
        })
        .def_prop_ro("azimuth", &OrbitCameraController::azimuth)
        .def_prop_ro("elevation", &OrbitCameraController::elevation)

        // For internal state access (Python used _azimuth, _elevation, _target)
        .def_prop_ro("_azimuth", &OrbitCameraController::azimuth)
        .def_prop_ro("_elevation", &OrbitCameraController::elevation)
        .def_prop_rw("_target", 
            [](OrbitCameraController& c) {
                Vec3 t = c.target();
                nb::module_ np = nb::module_::import_("numpy");
                return np.attr("array")(nb::make_tuple(t.x, t.y, t.z), "dtype"_a = "float32");
            },
            [](OrbitCameraController& c, nb::object position) {
                Vec3 pos;
                if (nb::hasattr(position, "__len__")) {
                    auto seq = nb::cast<nb::sequence>(position);
                    pos.x = nb::cast<double>(seq[0]);
                    pos.y = nb::cast<double>(seq[1]);
                    pos.z = nb::cast<double>(seq[2]);
                } else {
                    pos = nb::cast<Vec3>(position);
                }
                c.center_on(pos);  // center_on updates target and pose
            })

        // Movement control
        .def_prop_rw("prevent_moving",
            [](OrbitCameraController& c) { return c.prevent_moving(); },
            [](OrbitCameraController& c, bool v) { c.set_prevent_moving(v); })
        .def_prop_rw("_prevent_moving",  // Python uses _prevent_moving
            [](OrbitCameraController& c) { return c.prevent_moving(); },
            [](OrbitCameraController& c, bool v) { c.set_prevent_moving(v); })

        // Control speed parameters (Python compatibility)
        .def_prop_rw("_orbit_speed",
            [](OrbitCameraController& c) { return 0.2; },  // Default
            [](OrbitCameraController& c, double v) { /* TODO: add setter */ })
        .def_prop_rw("_pan_speed",
            [](OrbitCameraController& c) { return 0.005; },
            [](OrbitCameraController& c, double v) { /* TODO: add setter */ })
        .def_prop_rw("_zoom_speed",
            [](OrbitCameraController& c) { return 0.5; },
            [](OrbitCameraController& c, double v) { /* TODO: add setter */ })

        // camera_component property (Python used this)
        .def_prop_ro("camera_component", [](OrbitCameraController& c) -> nb::object {
            // Get CameraComponent from same entity
            if (!c.entity().valid()) {
                return nb::none();
            }
            CameraComponent* cam = c.entity().get_component<CameraComponent>();
            if (!cam) {
                return nb::none();
            }
            return nb::cast(cam, nb::rv_policy::reference);
        })

        // Internal methods (for Python compatibility)
        .def("_sync_from_transform", &OrbitCameraController::_sync_from_transform)
        .def("_update_pose", &OrbitCameraController::_update_pose)

        // Input event handlers - exposed to Python for dispatch
        .def("on_mouse_button", [](OrbitCameraController& c, MouseButtonEvent& e) {
            c.on_mouse_button(&e);
        }, nb::arg("event"))
        .def("on_mouse_move", [](OrbitCameraController& c, MouseMoveEvent& e) {
            c.on_mouse_move(&e);
        }, nb::arg("event"))
        .def("on_scroll", [](OrbitCameraController& c, ScrollEvent& e) {
            c.on_scroll(&e);
        }, nb::arg("event"))

        // c_component_ptr for compatibility
        .def("c_component_ptr", [](OrbitCameraController& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(c.c_component());
        })
        ;
}

} // namespace termin
