#pragma once

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/operators.h>
#include <pybind11/stl.h>

#include "termin/geom/geom.hpp"

namespace py = pybind11;

namespace termin {

// Helper to create numpy array from Vec3
inline py::array_t<double> vec3_to_numpy(const Vec3& v) {
    auto result = py::array_t<double>(3);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v.x;
    buf(1) = v.y;
    buf(2) = v.z;
    return result;
}

// Helper to create Vec3 from numpy array
inline Vec3 numpy_to_vec3(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return {buf(0), buf(1), buf(2)};
}

// Helper to create numpy array from Quat
inline py::array_t<double> quat_to_numpy(const Quat& q) {
    auto result = py::array_t<double>(4);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = q.x;
    buf(1) = q.y;
    buf(2) = q.z;
    buf(3) = q.w;
    return result;
}

// Helper to create Quat from numpy array
inline Quat numpy_to_quat(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return {buf(0), buf(1), buf(2), buf(3)};
}

// Helper to create 2D numpy matrix
inline py::array_t<double> make_mat(int rows, int cols) {
    return py::array_t<double>({rows, cols});
}

// Helper to convert any array-like Python object to Vec3
inline Vec3 py_to_vec3(py::object obj) {
    if (py::isinstance<Vec3>(obj)) {
        return obj.cast<Vec3>();
    }
    // Try numpy array or sequence
    auto arr = py::array_t<double>::ensure(obj);
    if (arr) {
        auto buf = arr.unchecked<1>();
        return Vec3{buf(0), buf(1), buf(2)};
    }
    // Try sequence protocol
    auto seq = obj.cast<py::sequence>();
    return Vec3{seq[0].cast<double>(), seq[1].cast<double>(), seq[2].cast<double>()};
}

// Forward declarations for binding functions
void bind_vec3(py::module_& m);
void bind_quat(py::module_& m);
void bind_mat44(py::module_& m);
void bind_pose3(py::module_& m);
void bind_general_pose3(py::module_& m);
void bind_screw3(py::module_& m);
void bind_transform(py::module_& m);
void bind_aabb(py::module_& m);

} // namespace termin
