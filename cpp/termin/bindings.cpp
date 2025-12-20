#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/operators.h>
#include <pybind11/stl.h>

#include "termin/geom/geom.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin::geom;

// Helper to create numpy array from Vec3
py::array_t<double> vec3_to_numpy(const Vec3& v) {
    auto result = py::array_t<double>(3);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v.x;
    buf(1) = v.y;
    buf(2) = v.z;
    return result;
}

// Helper to create Vec3 from numpy array
Vec3 numpy_to_vec3(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return {buf(0), buf(1), buf(2)};
}

// Helper to create numpy array from Quat
py::array_t<double> quat_to_numpy(const Quat& q) {
    auto result = py::array_t<double>(4);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = q.x;
    buf(1) = q.y;
    buf(2) = q.z;
    buf(3) = q.w;
    return result;
}

// Helper to create Quat from numpy array
Quat numpy_to_quat(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return {buf(0), buf(1), buf(2), buf(3)};
}

PYBIND11_MODULE(_geom_native, m) {
    m.doc() = "Native C++ geometry module for termin";

    // Vec3
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
        .def("__repr__", [](const Vec3& v) {
            return "Vec3(" + std::to_string(v.x) + ", " +
                   std::to_string(v.y) + ", " + std::to_string(v.z) + ")";
        });

    // Quat
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
        .def("__repr__", [](const Quat& q) {
            return "Quat(" + std::to_string(q.x) + ", " +
                   std::to_string(q.y) + ", " + std::to_string(q.z) + ", " +
                   std::to_string(q.w) + ")";
        });

    m.def("slerp", &slerp, "Spherical linear interpolation between quaternions");

    // Pose3
    py::class_<Pose3>(m, "Pose3")
        .def(py::init<>())
        .def(py::init<const Quat&, const Vec3&>())
        .def(py::init([](py::array_t<double> ang_arr, py::array_t<double> lin_arr) {
            return Pose3(numpy_to_quat(ang_arr), numpy_to_vec3(lin_arr));
        }))
        .def_readwrite("ang", &Pose3::ang)
        .def_readwrite("lin", &Pose3::lin)
        .def(py::self * py::self)
        .def("inverse", &Pose3::inverse)
        .def("transform_point", &Pose3::transform_point)
        .def("transform_vector", &Pose3::transform_vector)
        .def("rotate_point", &Pose3::rotate_point)
        .def("inverse_transform_point", &Pose3::inverse_transform_point)
        .def("inverse_transform_vector", &Pose3::inverse_transform_vector)
        .def("normalized", &Pose3::normalized)
        .def("with_translation", py::overload_cast<const Vec3&>(&Pose3::with_translation, py::const_))
        .def("with_rotation", &Pose3::with_rotation)
        .def("rotation_matrix", [](const Pose3& p) {
            auto result = py::array_t<double>({3, 3});
            auto buf = result.mutable_unchecked<2>();
            double m[9];
            p.rotation_matrix(m);
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    buf(i, j) = m[i * 3 + j];
            return result;
        })
        .def_static("identity", &Pose3::identity)
        .def_static("translation", py::overload_cast<double, double, double>(&Pose3::translation))
        .def_static("rotation", &Pose3::rotation)
        .def_static("rotate_x", &Pose3::rotate_x)
        .def_static("rotate_y", &Pose3::rotate_y)
        .def_static("rotate_z", &Pose3::rotate_z)
        .def("__repr__", [](const Pose3& p) {
            return "Pose3(ang=Quat(" + std::to_string(p.ang.x) + ", " +
                   std::to_string(p.ang.y) + ", " + std::to_string(p.ang.z) + ", " +
                   std::to_string(p.ang.w) + "), lin=Vec3(" +
                   std::to_string(p.lin.x) + ", " + std::to_string(p.lin.y) + ", " +
                   std::to_string(p.lin.z) + "))";
        });

    m.def("lerp", py::overload_cast<const Pose3&, const Pose3&, double>(&lerp),
          "Linear interpolation between poses");

    // Screw3
    py::class_<Screw3>(m, "Screw3")
        .def(py::init<>())
        .def(py::init<const Vec3&, const Vec3&>())
        .def(py::init([](py::array_t<double> ang_arr, py::array_t<double> lin_arr) {
            return Screw3(numpy_to_vec3(ang_arr), numpy_to_vec3(lin_arr));
        }))
        .def_readwrite("ang", &Screw3::ang)
        .def_readwrite("lin", &Screw3::lin)
        .def(py::self + py::self)
        .def(py::self - py::self)
        .def(py::self * double())
        .def(double() * py::self)
        .def(-py::self)
        .def("dot", &Screw3::dot)
        .def("cross_motion", &Screw3::cross_motion)
        .def("cross_force", &Screw3::cross_force)
        .def("transform_by", &Screw3::transform_by)
        .def("inverse_transform_by", &Screw3::inverse_transform_by)
        .def("to_pose", &Screw3::to_pose)
        .def("scaled", &Screw3::scaled)
        .def_static("zero", &Screw3::zero)
        .def("__repr__", [](const Screw3& s) {
            return "Screw3(ang=Vec3(" + std::to_string(s.ang.x) + ", " +
                   std::to_string(s.ang.y) + ", " + std::to_string(s.ang.z) +
                   "), lin=Vec3(" + std::to_string(s.lin.x) + ", " +
                   std::to_string(s.lin.y) + ", " + std::to_string(s.lin.z) + "))";
        });
}
