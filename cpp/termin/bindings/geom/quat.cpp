#include "common.hpp"

namespace termin {

void bind_quat(py::module_& m) {
    py::class_<Quat>(m, "Quat")
        .def(py::init<>())
        .def(py::init<double, double, double, double>())
        .def(py::init([](py::array_t<double> arr) {
            return numpy_to_quat(arr);
        }))
        .def_readwrite("x", &Quat::x)
        .def_readwrite("y", &Quat::y)
        .def_readwrite("z", &Quat::z)
        .def_readwrite("w", &Quat::w)
        .def("__getitem__", [](const Quat& q, int i) {
            if (i == 0) return q.x;
            if (i == 1) return q.y;
            if (i == 2) return q.z;
            if (i == 3) return q.w;
            throw py::index_error("Quat index out of range");
        })
        .def("__setitem__", [](Quat& q, int i, double val) {
            if (i == 0) q.x = val;
            else if (i == 1) q.y = val;
            else if (i == 2) q.z = val;
            else if (i == 3) q.w = val;
            else throw py::index_error("Quat index out of range");
        })
        .def("__setitem__", [](Quat& q, py::ellipsis, py::object val) {
            // Support quat[...] = (x, y, z, w) or quat[...] = other_quat
            if (py::isinstance<Quat>(val)) {
                Quat other = val.cast<Quat>();
                q.x = other.x;
                q.y = other.y;
                q.z = other.z;
                q.w = other.w;
            } else {
                auto seq = val.cast<py::sequence>();
                q.x = seq[0].cast<double>();
                q.y = seq[1].cast<double>();
                q.z = seq[2].cast<double>();
                q.w = seq[3].cast<double>();
            }
        })
        .def("__len__", [](const Quat&) { return 4; })
        .def("__iter__", [](const Quat& q) {
            return py::make_iterator(&q.x, &q.x + 4);
        }, py::keep_alive<0, 1>())
        .def(py::self * py::self)
        .def("conjugate", &Quat::conjugate)
        .def("inverse", &Quat::inverse)
        .def("norm", &Quat::norm)
        .def("normalized", &Quat::normalized)
        .def("rotate", &Quat::rotate)
        .def("inverse_rotate", &Quat::inverse_rotate)
        .def_static("identity", &Quat::identity)
        .def_static("from_axis_angle", &Quat::from_axis_angle)
        .def("to_numpy", &quat_to_numpy)
        .def("tolist", [](const Quat& q) { return py::list(py::make_tuple(q.x, q.y, q.z, q.w)); })
        .def("copy", [](const Quat& q) { return q; })
        .def("__repr__", [](const Quat& q) {
            return "Quat(" + std::to_string(q.x) + ", " +
                   std::to_string(q.y) + ", " + std::to_string(q.z) + ", " +
                   std::to_string(q.w) + ")";
        });

    m.def("slerp", &slerp, "Spherical linear interpolation between quaternions");
}

} // namespace termin
