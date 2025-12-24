#include "common.hpp"

namespace termin {

void bind_aabb(py::module_& m) {
    py::class_<AABB>(m, "AABB")
        .def(py::init<>())
        .def(py::init<const Vec3&, const Vec3&>())
        .def(py::init([](py::array_t<double> min_arr, py::array_t<double> max_arr) {
            return AABB(numpy_to_vec3(min_arr), numpy_to_vec3(max_arr));
        }))
        .def_readwrite("min_point", &AABB::min_point)
        .def_readwrite("max_point", &AABB::max_point)
        .def("extend", &AABB::extend)
        .def("intersects", &AABB::intersects)
        .def("contains", &AABB::contains)
        .def("merge", &AABB::merge)
        .def("center", &AABB::center)
        .def("size", &AABB::size)
        .def("half_size", &AABB::half_size)
        .def("project_point", &AABB::project_point)
        .def("surface_area", &AABB::surface_area)
        .def("volume", &AABB::volume)
        .def("corners", [](const AABB& aabb) {
            auto corners = aabb.corners();
            auto result = py::array_t<double>({8, 3});
            auto buf = result.mutable_unchecked<2>();
            for (size_t i = 0; i < 8; ++i) {
                buf(i, 0) = corners[i].x;
                buf(i, 1) = corners[i].y;
                buf(i, 2) = corners[i].z;
            }
            return result;
        })
        .def("get_corners_homogeneous", [](const AABB& aabb) {
            auto corners = aabb.corners();
            auto result = py::array_t<double>({8, 4});
            auto buf = result.mutable_unchecked<2>();
            for (size_t i = 0; i < 8; ++i) {
                buf(i, 0) = corners[i].x;
                buf(i, 1) = corners[i].y;
                buf(i, 2) = corners[i].z;
                buf(i, 3) = 1.0;
            }
            return result;
        })
        .def_static("from_points", [](py::array_t<double> points) {
            auto buf = points.unchecked<2>();
            if (buf.shape(0) == 0) {
                return AABB();
            }
            Vec3 min_pt{buf(0, 0), buf(0, 1), buf(0, 2)};
            Vec3 max_pt = min_pt;
            for (py::ssize_t i = 1; i < buf.shape(0); ++i) {
                Vec3 p{buf(i, 0), buf(i, 1), buf(i, 2)};
                min_pt.x = std::min(min_pt.x, p.x);
                min_pt.y = std::min(min_pt.y, p.y);
                min_pt.z = std::min(min_pt.z, p.z);
                max_pt.x = std::max(max_pt.x, p.x);
                max_pt.y = std::max(max_pt.y, p.y);
                max_pt.z = std::max(max_pt.z, p.z);
            }
            return AABB(min_pt, max_pt);
        })
        .def("transformed_by", [](const AABB& aabb, const Pose3& pose) {
            return aabb.transformed_by(pose);
        })
        .def("transformed_by", [](const AABB& aabb, const GeneralPose3& pose) {
            return aabb.transformed_by(pose);
        })
        .def("__repr__", [](const AABB& aabb) {
            return "AABB(min_point=Vec3(" + std::to_string(aabb.min_point.x) + ", " +
                   std::to_string(aabb.min_point.y) + ", " + std::to_string(aabb.min_point.z) +
                   "), max_point=Vec3(" + std::to_string(aabb.max_point.x) + ", " +
                   std::to_string(aabb.max_point.y) + ", " + std::to_string(aabb.max_point.z) + "))";
        });
}

} // namespace termin
