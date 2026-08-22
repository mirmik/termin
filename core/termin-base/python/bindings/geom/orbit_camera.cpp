#include "common.hpp"

#include <nanobind/stl/optional.h>

#include <termin/camera/orbit_camera.hpp>

namespace termin {
    void bind_orbit_camera(nb::module_& m) {
        nb::class_<OrbitCameraPan>(m, "OrbitCameraPan")
            .def_prop_ro("grabbed_point", &OrbitCameraPan::grabbed_point);

        nb::class_<OrbitCamera>(m, "OrbitCamera")
            .def(nb::init<>())
            .def_rw("target", &OrbitCamera::target)
            .def_rw("distance", &OrbitCamera::distance)
            .def_rw("azimuth", &OrbitCamera::azimuth)
            .def_rw("elevation", &OrbitCamera::elevation)
            .def_rw("fov_y", &OrbitCamera::fov_y)
            .def_rw("near", &OrbitCamera::near_clip)
            .def_rw("far", &OrbitCamera::far_clip)
            .def_rw("near_clip", &OrbitCamera::near_clip)
            .def_rw("far_clip", &OrbitCamera::far_clip)
            .def_rw("fitted_radius", &OrbitCamera::fitted_radius)
            .def_rw("min_distance", &OrbitCamera::min_distance)
            .def_rw("max_distance", &OrbitCamera::max_distance)
            .def_rw("min_elevation", &OrbitCamera::min_elevation)
            .def_rw("max_elevation", &OrbitCamera::max_elevation)
            .def_prop_ro("eye", &OrbitCamera::eye)
            .def("view_matrix", [](const OrbitCamera& camera) { return camera.view_matrix(); })
            .def(
                "projection_matrix",
                [](const OrbitCamera& camera, double aspect) { return camera.projection_matrix(aspect); },
                nb::arg("aspect"))
            .def(
                "mvp", [](const OrbitCamera& camera, double aspect) { return camera.mvp(aspect); }, nb::arg("aspect"))
            .def("orbit", &OrbitCamera::orbit, nb::arg("d_azimuth"), nb::arg("d_elevation"))
            .def("zoom", &OrbitCamera::zoom, nb::arg("factor"))
            .def("begin_pan", &OrbitCamera::begin_pan, nb::arg("screen_position"), nb::arg("viewport"))
            .def("pan",
                 nb::overload_cast<const OrbitCameraPan&, const Vec2&>(&OrbitCamera::pan),
                 nb::arg("gesture"),
                 nb::arg("screen_position"))
            .def("pan",
                 nb::overload_cast<const Vec2&, const Vec2&, const Rect2&>(&OrbitCamera::pan),
                 nb::arg("from_position"),
                 nb::arg("to_position"),
                 nb::arg("viewport"))
            .def("fit_bounds", &OrbitCamera::fit_bounds, nb::arg("bounds"))
            .def(
                "try_screen_ray",
                [](const OrbitCamera& camera, const Vec2& screen_position, const Rect2& viewport) {
                    return camera.try_screen_ray(screen_position, viewport);
                },
                nb::arg("screen_position"),
                nb::arg("viewport"))
            .def(
                "screen_ray",
                [](const OrbitCamera& camera, const Vec2& screen_position, const Rect2& viewport) -> Ray3 {
                    ScreenRayError error = ScreenRayError::None;
                    const std::optional<Ray3> ray = camera.try_screen_ray(screen_position, viewport, &error);
                    if (!ray) {
                        throw nb::value_error(screen_ray_error_message(error));
                    }
                    return *ray;
                },
                nb::arg("screen_position"),
                nb::arg("viewport"))
            .def(
                "try_project_world_point",
                [](const OrbitCamera& camera, const Vec3& world_point, const Rect2& viewport) {
                    return camera.try_project_world_point(world_point, viewport);
                },
                nb::arg("world_point"),
                nb::arg("viewport"))
            .def("world_point_on_z_plane",
                 &OrbitCamera::world_point_on_z_plane,
                 nb::arg("screen_position"),
                 nb::arg("viewport"),
                 nb::arg("z") = 0.0);
    }

} // namespace termin
