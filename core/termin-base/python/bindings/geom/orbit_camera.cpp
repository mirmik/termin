#include "common.hpp"

#include <nanobind/stl/optional.h>

#include <termin/camera/orbit_camera.hpp>

namespace termin {
    namespace {
        nb::tuple mat44_tuple(const Mat44& matrix) {
            nb::list result;
            for (double value : matrix.data) {
                result.append(value);
            }
            return nb::tuple(result);
        }
    } // namespace

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
            .def("view_matrix", [](const OrbitCamera& camera) { return mat44_tuple(camera.view_matrix()); })
            .def("projection_matrix",
                 [](const OrbitCamera& camera, double aspect) { return mat44_tuple(camera.projection_matrix(aspect)); },
                 nb::arg("aspect"))
            .def("mvp",
                 [](const OrbitCamera& camera, double aspect) { return mat44_tuple(camera.mvp(aspect)); },
                 nb::arg("aspect"))
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
                "screen_ray",
                [](const OrbitCamera& camera, const Vec2& screen_position, const Rect2& viewport) {
                    const OrbitCameraRay ray = camera.screen_ray(screen_position, viewport);
                    return nb::make_tuple(ray.origin, ray.direction);
                },
                nb::arg("screen_position"),
                nb::arg("viewport"))
            .def("world_point_on_z_plane",
                 &OrbitCamera::world_point_on_z_plane,
                 nb::arg("screen_position"),
                 nb::arg("viewport"),
                 nb::arg("z") = 0.0);
    }

} // namespace termin
