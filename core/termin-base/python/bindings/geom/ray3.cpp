#include "common.hpp"

#include <optional>

namespace termin {

    void bind_ray3(nb::module_& m) {
        nb::class_<Ray3>(m, "Ray3")
            .def(nb::init<>())
            .def(nb::init<const Vec3&, const Vec3&>(), nb::arg("origin"), nb::arg("direction"))
            .def_rw("origin", &Ray3::origin)
            .def_rw("direction", &Ray3::direction)
            .def("point_at", &Ray3::point_at, nb::arg("t"))
            .def(
                "try_intersect_plane",
                [](const Ray3& ray,
                   const Vec3& plane_origin,
                   const Vec3& plane_normal,
                   bool forward_only,
                   double epsilon) -> std::optional<Vec3> {
                    Vec3 point;
                    if (!try_intersect_ray_plane(ray, plane_origin, plane_normal, point, forward_only, epsilon)) {
                        return std::nullopt;
                    }
                    return point;
                },
                nb::arg("plane_origin"),
                nb::arg("plane_normal"),
                nb::arg("forward_only") = true,
                nb::arg("epsilon") = 1.0e-10)
            .def("copy", [](const Ray3& ray) { return ray; })
            .def("__repr__", [](const Ray3& ray) {
                return "Ray3(origin=Vec3(" + std::to_string(ray.origin.x) + ", " + std::to_string(ray.origin.y) + ", " +
                       std::to_string(ray.origin.z) + "), direction=Vec3(" + std::to_string(ray.direction.x) + ", " +
                       std::to_string(ray.direction.y) + ", " + std::to_string(ray.direction.z) + "))";
            });
    }

} // namespace termin
