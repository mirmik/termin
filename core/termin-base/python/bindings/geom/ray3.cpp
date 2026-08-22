#include "common.hpp"

#include <optional>

namespace termin {

    void bind_ray3(nb::module_& m) {
        nb::class_<RayTriangleHit>(m, "RayTriangleHit")
            .def_ro("ray_parameter", &RayTriangleHit::ray_parameter)
            .def_ro("barycentric", &RayTriangleHit::barycentric)
            .def_ro("normal", &RayTriangleHit::normal)
            .def("copy", [](const RayTriangleHit& hit) { return hit; })
            .def("__repr__", [](const RayTriangleHit& hit) {
                return "RayTriangleHit(ray_parameter=" + std::to_string(hit.ray_parameter) + ", barycentric=Vec3(" +
                       std::to_string(hit.barycentric.x) + ", " + std::to_string(hit.barycentric.y) + ", " +
                       std::to_string(hit.barycentric.z) + "), normal=Vec3(" + std::to_string(hit.normal.x) + ", " +
                       std::to_string(hit.normal.y) + ", " + std::to_string(hit.normal.z) + "))";
            });

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
            .def(
                "try_intersect_triangle",
                [](const Ray3& ray, const Vec3& a, const Vec3& b, const Vec3& c, bool forward_only, double epsilon)
                    -> std::optional<RayTriangleHit> {
                    RayTriangleHit hit;
                    if (!try_intersect_ray_triangle(ray, a, b, c, hit, forward_only, epsilon)) {
                        return std::nullopt;
                    }
                    return hit;
                },
                nb::arg("a"),
                nb::arg("b"),
                nb::arg("c"),
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
