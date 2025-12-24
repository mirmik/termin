#include "common.hpp"

namespace termin {

void bind_vec3(py::module_& m) {
    py::class_<Vec3>(m, "Vec3")
        .def(py::init<>())
        .def(py::init<double, double, double>())
        .def(py::init([](py::array_t<double> arr) {
            return numpy_to_vec3(arr);
        }))
        .def_readwrite("x", &Vec3::x)
        .def_readwrite("y", &Vec3::y)
        .def_readwrite("z", &Vec3::z)
        .def("__getitem__", [](const Vec3& v, int i) { return v[i]; })
        .def("__setitem__", [](Vec3& v, int i, double val) { v[i] = val; })
        .def("__setitem__", [](Vec3& v, py::ellipsis, py::object val) {
            // Support vec[...] = (x, y, z) or vec[...] = other_vec
            if (py::isinstance<Vec3>(val)) {
                Vec3 other = val.cast<Vec3>();
                v.x = other.x;
                v.y = other.y;
                v.z = other.z;
            } else {
                auto seq = val.cast<py::sequence>();
                v.x = seq[0].cast<double>();
                v.y = seq[1].cast<double>();
                v.z = seq[2].cast<double>();
            }
        })
        .def("__len__", [](const Vec3&) { return 3; })
        .def("__iter__", [](const Vec3& v) {
            return py::make_iterator(&v.x, &v.x + 3);
        }, py::keep_alive<0, 1>())
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(py::self * double())
        .def(double() * py::self)
        .def(py::self / double())
        .def(-py::self)
        .def("dot", &Vec3::dot)
        .def("cross", &Vec3::cross)
        .def("norm", &Vec3::norm)
        .def("norm_squared", &Vec3::norm_squared)
        .def("normalized", &Vec3::normalized)
        .def_static("zero", &Vec3::zero)
        .def_static("unit_x", &Vec3::unit_x)
        .def_static("unit_y", &Vec3::unit_y)
        .def_static("unit_z", &Vec3::unit_z)
        .def("to_numpy", &vec3_to_numpy)
        .def("tolist", [](const Vec3& v) { return py::list(py::make_tuple(v.x, v.y, v.z)); })
        .def("copy", [](const Vec3& v) { return v; })
        .def("__eq__", [](const Vec3& a, const Vec3& b) {
            return a.x == b.x && a.y == b.y && a.z == b.z;
        })
        .def("__ne__", [](const Vec3& a, const Vec3& b) {
            return a.x != b.x || a.y != b.y || a.z != b.z;
        })
        .def("approx_eq", [](const Vec3& a, const Vec3& b, double eps) {
            return std::abs(a.x - b.x) < eps &&
                   std::abs(a.y - b.y) < eps &&
                   std::abs(a.z - b.z) < eps;
        }, py::arg("other"), py::arg("eps") = 1e-9)
        .def("__repr__", [](const Vec3& v) {
            return "Vec3(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ", " + std::to_string(v.z) + ")";
        });
}

} // namespace termin
