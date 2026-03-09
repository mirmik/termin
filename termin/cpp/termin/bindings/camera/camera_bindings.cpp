// camera_bindings.cpp - Python bindings for CameraComponent

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/tuple.h>

#include "termin/camera/camera_component.hpp"
#include "termin/bindings/entity/entity_helpers.hpp"

namespace nb = nanobind;

namespace termin {

void bind_camera_component(nb::module_& m) {
    nb::class_<CameraComponent, CxxComponent>(m, "CameraComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<CameraComponent>(self);
        })

        // Projection type
        .def_prop_rw("projection_type",
            &CameraComponent::get_projection_type_str,
            &CameraComponent::set_projection_type_str)

        // Clipping planes
        .def_rw("near", &CameraComponent::near_clip)
        .def_rw("far", &CameraComponent::far_clip)
        .def_prop_rw("near_clip",
            [](CameraComponent& c) { return c.near_clip; },
            [](CameraComponent& c, double v) { c.near_clip = v; })
        .def_prop_rw("far_clip",
            [](CameraComponent& c) { return c.far_clip; },
            [](CameraComponent& c, double v) { c.far_clip = v; })

        // FOV mode
        .def_prop_rw("fov_mode",
            &CameraComponent::get_fov_mode_str,
            &CameraComponent::set_fov_mode_str)

        // FOV (radians)
        .def_rw("fov_x", &CameraComponent::fov_x)
        .def_rw("fov_y", &CameraComponent::fov_y)

        // FOV (degrees) - convenience properties
        .def_prop_rw("fov_x_degrees",
            &CameraComponent::get_fov_x_degrees,
            &CameraComponent::set_fov_x_degrees)
        .def_prop_rw("fov_y_degrees",
            &CameraComponent::get_fov_y_degrees,
            &CameraComponent::set_fov_y_degrees)

        // Aspect ratio
        .def_rw("aspect", &CameraComponent::aspect)
        .def("set_aspect", &CameraComponent::set_aspect, nb::arg("aspect"))

        // Orthographic size
        .def_rw("ortho_size", &CameraComponent::ortho_size)

        // Matrix getters
        .def("get_view_matrix", &CameraComponent::get_view_matrix)
        .def("get_projection_matrix", &CameraComponent::get_projection_matrix)

        // Aliases for compatibility
        .def("view_matrix", &CameraComponent::get_view_matrix)
        .def("projection_matrix", &CameraComponent::get_projection_matrix)

        // Camera position
        .def("get_position", &CameraComponent::get_position)

        // Viewport management - use nb::object to avoid cross-module type issues
        // Expects viewport._viewport_handle() which returns (index, generation) tuple
        .def("add_viewport", [](CameraComponent& c, nb::object viewport) {
            auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(viewport.attr("_viewport_handle")());
            tc_viewport_handle handle;
            handle.index = std::get<0>(h);
            handle.generation = std::get<1>(h);
            c.add_viewport(TcViewport(handle));
        }, nb::arg("viewport"))
        .def("remove_viewport", [](CameraComponent& c, nb::object viewport) {
            auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(viewport.attr("_viewport_handle")());
            tc_viewport_handle handle;
            handle.index = std::get<0>(h);
            handle.generation = std::get<1>(h);
            c.remove_viewport(TcViewport(handle));
        }, nb::arg("viewport"))
        .def("has_viewport", [](CameraComponent& c, nb::object viewport) {
            auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(viewport.attr("_viewport_handle")());
            tc_viewport_handle handle;
            handle.index = std::get<0>(h);
            handle.generation = std::get<1>(h);
            return c.has_viewport(TcViewport(handle));
        }, nb::arg("viewport"))
        .def_prop_ro("viewport_count", &CameraComponent::viewport_count)
        .def("clear_viewports", &CameraComponent::clear_viewports)

        // First viewport (for backward compatibility)
        .def_prop_ro("viewport", [](CameraComponent& c) -> nb::object {
            if (c.viewport_count() == 0) {
                return nb::none();
            }
            TcViewport vp = c.viewport_at(0);
            if (!vp.is_valid()) {
                return nb::none();
            }
            // Create Viewport via _from_handle to avoid cross-module type issues
            nb::module_ vp_native = nb::module_::import_("termin.viewport._viewport_native");
            nb::object VpClass = vp_native.attr("Viewport");
            auto h = std::make_tuple(vp.handle_.index, vp.handle_.generation);
            return VpClass.attr("_from_handle")(h);
        })

        // Screen point to ray
        .def("screen_point_to_ray", [](CameraComponent& c, double x, double y, nb::object viewport_rect) {
            // Extract viewport rect
            auto rect = nb::cast<std::tuple<int, int, int, int>>(viewport_rect);
            int vp_x = std::get<0>(rect);
            int vp_y = std::get<1>(rect);
            int vp_w = std::get<2>(rect);
            int vp_h = std::get<3>(rect);

            auto [origin, direction] = c.screen_point_to_ray(x, y, vp_x, vp_y, vp_w, vp_h);

            // Import Ray3 and return
            nb::module_ geombase = nb::module_::import_("termin.geombase");
            nb::object Ray3 = geombase.attr("Ray3");
            nb::object Vec3 = geombase.attr("Vec3");

            nb::object py_origin = Vec3(origin.x, origin.y, origin.z);
            nb::object py_direction = Vec3(direction.x, direction.y, direction.z);

            return Ray3(py_origin, py_direction);
        }, nb::arg("x"), nb::arg("y"), nb::arg("viewport_rect"))

        // c_component_ptr for compatibility with Viewport
        .def("c_component_ptr", [](CameraComponent& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(c.c_component());
        })
        ;

    // Factory function for PerspectiveCameraComponent
    m.def("PerspectiveCameraComponent", [](double fov_degrees, double aspect, double near, double far) {
        auto* cam = new CameraComponent();
        // Link to CameraComponent type entry
        tc_type_entry* entry = tc_component_registry_get_entry("CameraComponent");
        if (entry) {
            cam->c_component()->type_entry = entry;
            cam->c_component()->type_version = entry->version;
        }
        cam->set_fov_x_degrees(fov_degrees);
        cam->fov_mode = FovMode::FixHorizontal;
        cam->aspect = aspect;
        cam->near_clip = near;
        cam->far_clip = far;
        cam->projection_type = CameraProjection::Perspective;
        return cam;
    },
    nb::arg("fov_degrees") = 60.0,
    nb::arg("aspect") = 1.0,
    nb::arg("near") = 0.1,
    nb::arg("far") = 100.0,
    nb::rv_policy::take_ownership);

    // Factory function for OrthographicCameraComponent
    m.def("OrthographicCameraComponent", [](double ortho_size, double aspect, double near, double far) {
        auto* cam = new CameraComponent();
        // Link to CameraComponent type entry
        tc_type_entry* entry = tc_component_registry_get_entry("CameraComponent");
        if (entry) {
            cam->c_component()->type_entry = entry;
            cam->c_component()->type_version = entry->version;
        }
        cam->ortho_size = ortho_size;
        cam->aspect = aspect;
        cam->near_clip = near;
        cam->far_clip = far;
        cam->projection_type = CameraProjection::Orthographic;
        return cam;
    },
    nb::arg("ortho_size") = 5.0,
    nb::arg("aspect") = 1.0,
    nb::arg("near") = 0.1,
    nb::arg("far") = 100.0,
    nb::rv_policy::take_ownership);
}

} // namespace termin
