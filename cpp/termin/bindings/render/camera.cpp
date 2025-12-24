#include "common.hpp"
#include "termin/camera/camera.hpp"
#include "termin/geom/vec3.hpp"

namespace termin {

void bind_camera(py::module_& m) {
    py::enum_<CameraProjection>(m, "CameraProjection")
        .value("Perspective", CameraProjection::Perspective)
        .value("Orthographic", CameraProjection::Orthographic);

    py::class_<Camera>(m, "Camera")
        .def(py::init<>())
        .def_readwrite("projection_type", &Camera::projection_type)
        .def_readwrite("near", &Camera::near)
        .def_readwrite("far", &Camera::far)
        .def_readwrite("fov_y", &Camera::fov_y)
        .def_readwrite("aspect", &Camera::aspect)
        .def_readwrite("ortho_left", &Camera::ortho_left)
        .def_readwrite("ortho_right", &Camera::ortho_right)
        .def_readwrite("ortho_bottom", &Camera::ortho_bottom)
        .def_readwrite("ortho_top", &Camera::ortho_top)
        .def_static("perspective", &Camera::perspective,
            py::arg("fov_y_rad"), py::arg("aspect"),
            py::arg("near") = 0.1, py::arg("far") = 100.0)
        .def_static("perspective_deg", &Camera::perspective_deg,
            py::arg("fov_y_deg"), py::arg("aspect"),
            py::arg("near") = 0.1, py::arg("far") = 100.0)
        .def_static("orthographic", &Camera::orthographic,
            py::arg("left"), py::arg("right"),
            py::arg("bottom"), py::arg("top"),
            py::arg("near") = 0.1, py::arg("far") = 100.0)
        .def("projection_matrix", &Camera::projection_matrix)
        .def_static("view_matrix", &Camera::view_matrix,
            py::arg("position"), py::arg("rotation"))
        .def_static("view_matrix_look_at", &Camera::view_matrix_look_at,
            py::arg("eye"), py::arg("target"),
            py::arg("up") = Vec3::unit_z())
        .def("set_aspect", &Camera::set_aspect, py::arg("aspect"))
        .def("set_fov", &Camera::set_fov, py::arg("fov_rad"))
        .def("set_fov_deg", &Camera::set_fov_deg, py::arg("fov_deg"))
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
