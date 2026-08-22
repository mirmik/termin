#include "common.hpp"

namespace termin {

    void bind_aabb(nb::module_& m) {
        nb::class_<AABB>(m, "AABB")
            .def(nb::init<>())
            .def(nb::init<const Vec3&, const Vec3&>())
            .def_rw("min_point", &AABB::min_point)
            .def_rw("max_point", &AABB::max_point)
            .def("extend", &AABB::extend)
            .def("intersects", &AABB::intersects)
            .def("contains", &AABB::contains)
            .def("merge", &AABB::merge)
            .def("center", &AABB::center)
            .def("size", &AABB::size)
            .def("half_size", &AABB::half_size)
            .def("project_point", &AABB::project_point)
            .def("is_finite", &AABB::is_finite)
            .def("is_valid", &AABB::is_valid)
            .def("expanded", &AABB::expanded)
            .def("surface_area", &AABB::surface_area)
            .def("volume", &AABB::volume)
            .def("corners",
                 [](const AABB& aabb) {
                     Vec3 corners[8];
                     aabb.get_corners(corners);
                     nb::list result;
                     for (size_t i = 0; i < 8; ++i) {
                         result.append(corners[i]);
                     }
                     return result;
                 })
            .def_static("from_points",
                        [](const std::vector<Vec3>& points) {
                            if (points.empty()) {
                                return AABB();
                            }
                            return AABB::from_points(points.data(), points.size());
                        })
            .def("transformed_by", [](const AABB& self, const Pose3& pose) { return self.transformed_by(pose); })
            .def("transformed_by", [](const AABB& self, const GeneralPose3& pose) { return self.transformed_by(pose); })
            .def("__repr__", [](const AABB& aabb) {
                return "AABB(min_point=Vec3(" + std::to_string(aabb.min_point.x) + ", " +
                       std::to_string(aabb.min_point.y) + ", " + std::to_string(aabb.min_point.z) +
                       "), max_point=Vec3(" + std::to_string(aabb.max_point.x) + ", " +
                       std::to_string(aabb.max_point.y) + ", " + std::to_string(aabb.max_point.z) + "))";
            });

        nb::class_<AABBf>(m, "AABBf")
            .def(nb::init<>())
            .def(nb::init<const Vec3f&, const Vec3f&>())
            .def_rw("min_point", &AABBf::min_point)
            .def_rw("max_point", &AABBf::max_point)
            .def("extend", &AABBf::extend)
            .def("intersects", &AABBf::intersects)
            .def("contains", &AABBf::contains)
            .def("merge", &AABBf::merge)
            .def("center", &AABBf::center)
            .def("size", &AABBf::size)
            .def("half_size", &AABBf::half_size)
            .def("project_point", &AABBf::project_point)
            .def("is_finite", &AABBf::is_finite)
            .def("is_valid", &AABBf::is_valid)
            .def("expanded", &AABBf::expanded)
            .def_static("from_points",
                        [](const std::vector<Vec3f>& points) {
                            return AABBf::from_points(points.data(), points.size());
                        })
            .def("__repr__", [](const AABBf& aabb) {
                return "AABBf(min_point=Vec3f(" + std::to_string(aabb.min_point.x) + ", " +
                       std::to_string(aabb.min_point.y) + ", " + std::to_string(aabb.min_point.z) +
                       "), max_point=Vec3f(" + std::to_string(aabb.max_point.x) + ", " +
                       std::to_string(aabb.max_point.y) + ", " + std::to_string(aabb.max_point.z) + "))";
            });
    }

} // namespace termin
