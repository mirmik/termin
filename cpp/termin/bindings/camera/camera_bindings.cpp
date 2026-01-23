// camera_bindings.cpp - Python bindings for CameraComponent
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/pair.h>

#include "../../camera/camera_component.hpp"
#include "../../entity/vtable_utils.hpp"
#include "../../viewport/tc_viewport_handle.hpp"

namespace nb = nanobind;

namespace termin {

void bind_camera_component(nb::module_& m) {
    BIND_NATIVE_COMPONENT(m, CameraComponent)

        // Projection type
        .def_prop_rw("projection_type",
            &CameraComponent::get_projection_type_str,
            &CameraComponent::set_projection_type_str)

        // Common parameters
        .def_rw("near", &CameraComponent::near_clip)
        .def_rw("far", &CameraComponent::far_clip)

        // Perspective parameters
        .def_rw("fov_y", &CameraComponent::fov_y)
        .def_rw("aspect", &CameraComponent::aspect)

        // FOV in degrees (property)
        .def_prop_rw("fov_y_degrees",
            [](CameraComponent& c) { return c.get_fov_degrees(); },
            [](CameraComponent& c, double deg) { c.set_fov_degrees(deg); })

        // Orthographic parameters
        .def_rw("ortho_size", &CameraComponent::ortho_size)

        // Methods
        .def("set_aspect", &CameraComponent::set_aspect, nb::arg("aspect"))

        .def("get_view_matrix", &CameraComponent::get_view_matrix)
        .def("get_projection_matrix", &CameraComponent::get_projection_matrix)
        .def("view_matrix", &CameraComponent::get_view_matrix)
        .def("projection_matrix", &CameraComponent::get_projection_matrix)

        .def("get_position", [](CameraComponent& c) {
            Vec3 p = c.get_position();
            return nb::make_tuple(p.x, p.y, p.z);
        })

        // Viewport management (using TcViewport with reference counting)
        .def("add_viewport", [](CameraComponent& c, const TcViewport& vp) {
            c.add_viewport(vp);
        }, nb::arg("viewport"))

        .def("remove_viewport", [](CameraComponent& c, const TcViewport& vp) {
            c.remove_viewport(vp);
        }, nb::arg("viewport"))

        .def("has_viewport", [](CameraComponent& c, const TcViewport& vp) {
            return c.has_viewport(vp);
        }, nb::arg("viewport"))

        .def("viewport_count", &CameraComponent::viewport_count)

        .def("viewport_at", [](CameraComponent& c, size_t index) {
            return c.viewport_at(index);
        }, nb::arg("index"))

        .def("clear_viewports", &CameraComponent::clear_viewports)

        // First viewport (backward compat)
        .def_prop_rw("viewport",
            [](CameraComponent& c) {
                return c.viewport_at(0);
            },
            [](CameraComponent& c, const TcViewport& vp) {
                c.clear_viewports();
                if (vp.is_valid()) {
                    c.add_viewport(vp);
                }
            })

        // Viewports list (read-only)
        .def_prop_ro("viewports", [](CameraComponent& c) {
            nb::list result;
            for (size_t i = 0; i < c.viewport_count(); i++) {
                TcViewport vp = c.viewport_at(i);
                if (vp.is_valid()) {
                    result.append(vp);
                }
            }
            return result;
        })

        // Screen point to ray
        .def("screen_point_to_ray",
            [](CameraComponent& c, double x, double y, nb::object viewport_rect) -> nb::object {
                int vp_x = 0, vp_y = 0, vp_w = 1, vp_h = 1;
                if (!viewport_rect.is_none()) {
                    auto rect = nb::cast<nb::tuple>(viewport_rect);
                    vp_x = nb::cast<int>(rect[0]);
                    vp_y = nb::cast<int>(rect[1]);
                    vp_w = nb::cast<int>(rect[2]);
                    vp_h = nb::cast<int>(rect[3]);
                }

                auto [origin, direction] = c.screen_point_to_ray(x, y, vp_x, vp_y, vp_w, vp_h);

                // Import Ray3 from Python
                nb::module_ geom = nb::module_::import_("termin.geombase");
                nb::object Ray3 = geom.attr("Ray3");
                nb::object Vec3Py = geom.attr("Vec3");

                nb::object py_origin = Vec3Py(origin.x, origin.y, origin.z);
                nb::object py_dir = Vec3Py(direction.x, direction.y, direction.z);

                return Ray3(py_origin, py_dir);
            },
            nb::arg("x"), nb::arg("y"), nb::arg("viewport_rect") = nb::none())
        ;
}

} // namespace termin
