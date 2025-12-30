#include "common.hpp"
#include "termin/camera/camera.hpp"
#include "termin/geom/vec3.hpp"

namespace termin {

void bind_camera(nb::module_& m) {
    nb::enum_<CameraProjection>(m, "CameraProjection")
        .value("Perspective", CameraProjection::Perspective)
        .value("Orthographic", CameraProjection::Orthographic);

    nb::class_<Camera>(m, "Camera")
        .def(nb::init<>())
        .def_rw("projection_type", &Camera::projection_type)
        .def_rw("near", &Camera::near)
        .def_rw("far", &Camera::far)
        .def_rw("fov_y", &Camera::fov_y)
        .def_rw("aspect", &Camera::aspect)
        .def_rw("ortho_left", &Camera::ortho_left)
        .def_rw("ortho_right", &Camera::ortho_right)
        .def_rw("ortho_bottom", &Camera::ortho_bottom)
        .def_rw("ortho_top", &Camera::ortho_top)
        .def_static("perspective", &Camera::perspective,
            nb::arg("fov_y_rad"), nb::arg("aspect"),
            nb::arg("near") = 0.1, nb::arg("far") = 100.0)
        .def_static("perspective_deg", &Camera::perspective_deg,
            nb::arg("fov_y_deg"), nb::arg("aspect"),
            nb::arg("near") = 0.1, nb::arg("far") = 100.0)
        .def_static("orthographic", &Camera::orthographic,
            nb::arg("left"), nb::arg("right"),
            nb::arg("bottom"), nb::arg("top"),
            nb::arg("near") = 0.1, nb::arg("far") = 100.0)
        .def("projection_matrix", &Camera::projection_matrix)
        .def_static("view_matrix", &Camera::view_matrix,
            nb::arg("position"), nb::arg("rotation"))
        .def_static("view_matrix_look_at", &Camera::view_matrix_look_at,
            nb::arg("eye"), nb::arg("target"),
            nb::arg("up") = Vec3::unit_z())
        .def("set_aspect", &Camera::set_aspect, nb::arg("aspect"))
        .def("set_fov", &Camera::set_fov, nb::arg("fov_rad"))
        .def("set_fov_deg", &Camera::set_fov_deg, nb::arg("fov_deg"))
        .def("get_fov_deg", &Camera::get_fov_deg)
        .def("__repr__", [](const Camera& cam) -> std::string {
            if (cam.projection_type == CameraProjection::Perspective) {
                return "<Camera perspective fov=" + std::to_string(cam.get_fov_deg()) + "deg>";
            } else {
                return "<Camera orthographic>";
            }
        });
}

} // namespace termin
