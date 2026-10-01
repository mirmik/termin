#include "common.hpp"

#include <cstring>
#include <limits>
#include <memory>
#include <optional>

#include <nanobind/ndarray.h>
#include <tcbase/tc_log.hpp>

namespace termin {

    namespace {

        using QuaternionInputArray = nb::ndarray<nb::numpy, const double, nb::device::cpu>;
        using QuaternionRowsArray = nb::ndarray<nb::numpy, double, nb::c_contig, nb::device::cpu>;

        QuaternionInputArray checked_quaternion_array(nb::handle value, const char* operation) {
            QuaternionInputArray result;
            if (!nb::isinstance(value, nb::module_::import_("numpy").attr("ndarray")) ||
                !nb::try_cast(value, result, false)) {
                tc::Log::error("Quat.%s requires a NumPy float64 array", operation);
                throw nb::type_error("Expected a NumPy float64 array");
            }
            return result;
        }

        // Read strided (including reversed and unaligned) NumPy storage without
        // requiring writable input or changing the caller's array.
        double quaternion_array_coefficient(const QuaternionInputArray& array, size_t row, size_t column) {
            const auto offset = static_cast<int64_t>(row) * array.stride(0) +
                                static_cast<int64_t>(column) * array.stride(1);
            const auto* bytes = reinterpret_cast<const unsigned char*>(array.data());
            double result;
            std::memcpy(&result, bytes + offset * static_cast<int64_t>(sizeof(double)), sizeof(result));
            return result;
        }

        Quat quaternion_from_rotation_matrix(nb::handle matrix, double epsilon) {
            const QuaternionInputArray array = checked_quaternion_array(matrix, "from_rotation_matrix");
            if (array.ndim() != 2 || array.shape(0) != 3 || array.shape(1) != 3) {
                tc::Log::error("Quat.from_rotation_matrix requires shape (3, 3)");
                throw nb::value_error("Rotation matrix must have shape (3, 3)");
            }
            double row_major[9];
            for (size_t row = 0; row < 3; ++row) {
                for (size_t column = 0; column < 3; ++column) {
                    row_major[row * 3 + column] = quaternion_array_coefficient(array, row, column);
                }
            }
            Quat result;
            if (!Quat::try_from_rotation_matrix(row_major, result, epsilon)) {
                tc::Log::error("Quat.from_rotation_matrix requires a finite proper rotation and finite "
                               "epsilon in [0, 1); epsilon=%g", epsilon);
                throw nb::value_error("Matrix must be a finite proper rotation; epsilon must be finite in [0, 1)");
            }
            return result;
        }

        QuaternionRowsArray quaternion_left_multiply_rows(const Quat& left, nb::handle rows) {
            const QuaternionInputArray array = checked_quaternion_array(rows, "left_multiply_rows");
            if (array.ndim() != 2 || array.shape(1) != 4) {
                tc::Log::error("Quat.left_multiply_rows requires shape (N, 4)");
                throw nb::value_error("Quaternion rows must have shape (N, 4)");
            }
            if (!left.is_finite()) {
                tc::Log::error("Quat.left_multiply_rows requires a finite left quaternion");
                throw nb::value_error("Left quaternion must be finite");
            }
            const size_t count = array.shape(0);
            if (count > std::numeric_limits<size_t>::max() / (4 * sizeof(double))) {
                tc::Log::error("Quat.left_multiply_rows output size is not representable");
                throw nb::value_error("Quaternion row output is too large");
            }
            auto values = std::make_unique<double[]>(count * 4);
            for (size_t row = 0; row < count; ++row) {
                const Quat right{quaternion_array_coefficient(array, row, 0),
                                 quaternion_array_coefficient(array, row, 1),
                                 quaternion_array_coefficient(array, row, 2),
                                 quaternion_array_coefficient(array, row, 3)};
                if (!right.is_finite()) {
                    tc::Log::error("Quat.left_multiply_rows requires finite coefficients at row %zu", row);
                    throw nb::value_error("Quaternion rows must be finite");
                }
                // Raw multiplication deliberately preserves zero/nonunit
                // animation tangents and does not canonicalize their signs.
                const Quat product = left * right;
                if (!product.is_finite()) {
                    tc::Log::error("Quat.left_multiply_rows produced non-finite coefficients at row %zu", row);
                    throw nb::value_error("Quaternion row multiplication overflowed");
                }
                values[row * 4] = product.x;
                values[row * 4 + 1] = product.y;
                values[row * 4 + 2] = product.z;
                values[row * 4 + 3] = product.w;
            }
            double* data = values.get();
            nb::capsule owner(data, [](void* pointer) noexcept { delete[] static_cast<double*>(pointer); });
            values.release();
            return QuaternionRowsArray(data, {count, 4}, owner);
        }

    } // namespace

    void bind_quat(nb::module_& m) {
        nb::class_<Quat>(m, "Quat")
            .def(nb::init<>())
            .def(nb::init<double, double, double, double>())
            .def("__init__", [](Quat* self, nb::object obj) { new (self) Quat(sequence_to_quat(obj)); })
            .def_rw("x", &Quat::x)
            .def_rw("y", &Quat::y)
            .def_rw("z", &Quat::z)
            .def_rw("w", &Quat::w)
            .def("__getitem__",
                 [](const Quat& q, int i) {
                     if (i == 0)
                         return q.x;
                     if (i == 1)
                         return q.y;
                     if (i == 2)
                         return q.z;
                     if (i == 3)
                         return q.w;
                     throw nb::index_error("Quat index out of range");
                 })
            .def("__setitem__",
                 [](Quat& q, int i, double val) {
                     if (i == 0)
                         q.x = val;
                     else if (i == 1)
                         q.y = val;
                     else if (i == 2)
                         q.z = val;
                     else if (i == 3)
                         q.w = val;
                     else
                         throw nb::index_error("Quat index out of range");
                 })
            .def("__len__", [](const Quat&) { return 4; })
            .def("__iter__", [](const Quat& q) { return nb::iter(nb::make_tuple(q.x, q.y, q.z, q.w)); })
            .def(nb::self * nb::self)
            .def("left_multiply_rows", &quaternion_left_multiply_rows, nb::arg("rows"),
                 "Multiply each raw float64 xyzw row by this quaternion without normalization.")
            .def("conjugate", &Quat::conjugate)
            .def("dot", &Quat::dot, nb::arg("other"))
            .def("norm_squared", &Quat::norm_squared)
            .def("norm", &Quat::norm)
            .def("is_finite", &Quat::is_finite)
            .def(
                "try_normalized",
                [](const Quat& value, double epsilon) -> std::optional<Quat> {
                    Quat result;
                    if (!value.try_normalized(result, epsilon)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def("normalized_or", &Quat::normalized_or, nb::arg("fallback"), nb::arg("epsilon") = 1.0e-12)
            .def(
                "normalized",
                [](const Quat& value, double epsilon) {
                    Quat result;
                    if (!value.try_normalized(result, epsilon)) {
                        throw nb::value_error("Quat cannot be normalized");
                    }
                    return result;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "try_inverse",
                [](const Quat& value, double epsilon) -> std::optional<Quat> {
                    Quat result;
                    if (!value.try_inverse(result, epsilon)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "inverse",
                [](const Quat& value, double epsilon) {
                    Quat result;
                    if (!value.try_inverse(result, epsilon)) {
                        throw nb::value_error("Quat cannot be inverted");
                    }
                    return result;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "try_rotate",
                [](const Quat& value, const Vec3& vector, double epsilon) -> std::optional<Vec3> {
                    Vec3 result;
                    if (!value.try_rotate(vector, result, epsilon)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("vector"),
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "rotate",
                [](const Quat& value, const Vec3& vector, double epsilon) {
                    Vec3 result;
                    if (!value.try_rotate(vector, result, epsilon)) {
                        throw nb::value_error("Quaternion cannot rotate this vector");
                    }
                    return result;
                },
                nb::arg("vector"),
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "try_inverse_rotate",
                [](const Quat& value, const Vec3& vector, double epsilon) -> std::optional<Vec3> {
                    Vec3 result;
                    if (!value.try_inverse_rotate(vector, result, epsilon)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("vector"),
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "inverse_rotate",
                [](const Quat& value, const Vec3& vector, double epsilon) {
                    Vec3 result;
                    if (!value.try_inverse_rotate(vector, result, epsilon)) {
                        throw nb::value_error("Quaternion cannot inverse-rotate this vector");
                    }
                    return result;
                },
                nb::arg("vector"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static("identity", &Quat::identity)
            .def_static("from_rotation_matrix", &quaternion_from_rotation_matrix,
                        nb::arg("matrix"), nb::arg("epsilon") = 1.0e-8,
                        "Convert a finite proper float64 3x3 rotation matrix to a canonical unit quaternion.")
            .def_static(
                "try_from_axis_angle",
                [](const Vec3& axis, double angle, double epsilon) -> std::optional<Quat> {
                    Quat result;
                    if (!Quat::try_from_axis_angle(axis, angle, result, epsilon)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("axis"),
                nb::arg("angle"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "from_axis_angle",
                [](const Vec3& axis, double angle, double epsilon) {
                    Quat result;
                    if (!Quat::try_from_axis_angle(axis, angle, result, epsilon)) {
                        throw nb::value_error("Axis-angle rotation requires a finite non-degenerate axis and angle");
                    }
                    return result;
                },
                nb::arg("axis"),
                nb::arg("angle"),
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "try_to_matrix",
                [](const Quat& value, double epsilon) -> std::optional<Mat33> {
                    double row_major[9];
                    if (!value.try_to_matrix(row_major, epsilon)) {
                        return std::nullopt;
                    }
                    Mat33 result;
                    for (int row = 0; row < 3; ++row) {
                        for (int column = 0; column < 3; ++column) {
                            result(column, row) = row_major[row * 3 + column];
                        }
                    }
                    return result;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "to_matrix",
                [](const Quat& value, double epsilon) {
                    double row_major[9];
                    if (!value.try_to_matrix(row_major, epsilon)) {
                        throw nb::value_error("Quaternion cannot be converted to a rotation matrix");
                    }
                    Mat33 result;
                    for (int row = 0; row < 3; ++row) {
                        for (int column = 0; column < 3; ++column) {
                            result(column, row) = row_major[row * 3 + column];
                        }
                    }
                    return result;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "try_from_euler",
                [](const Vec3& euler_xyz) -> std::optional<Quat> {
                    Quat result;
                    if (!Quat::try_from_euler(euler_xyz, result)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("euler_xyz"))
            .def_static(
                "from_euler",
                [](const Vec3& euler_xyz) {
                    Quat result;
                    if (!Quat::try_from_euler(euler_xyz, result)) {
                        throw nb::value_error("Euler angles must be finite");
                    }
                    return result;
                },
                nb::arg("euler_xyz"))
            .def(
                "try_to_euler",
                [](const Quat& value, double epsilon) -> std::optional<Vec3> {
                    Vec3 result;
                    if (!value.try_to_euler(result, epsilon)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "to_euler",
                [](const Quat& value, double epsilon) {
                    Vec3 result;
                    if (!value.try_to_euler(result, epsilon)) {
                        throw nb::value_error("Quat cannot be converted to Euler angles");
                    }
                    return result;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "look_rotation",
                [](const Vec3& forward, std::optional<Vec3> up) {
                    return Quat::look_rotation(forward, up.value_or(Vec3::unit_z()));
                },
                nb::arg("forward"),
                nb::arg("up").none() = nb::none(),
                "Create quaternion looking in direction (Forward=+Y, Up=+Z)")
            .def_static(
                "try_slerp",
                [](const Quat& a, const Quat& b, double t, double epsilon) -> std::optional<Quat> {
                    Quat result;
                    if (!Quat::try_slerp(a, b, t, result, epsilon)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("a"),
                nb::arg("b"),
                nb::arg("t"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "slerp",
                [](const Quat& a, const Quat& b, double t, double epsilon) {
                    Quat result;
                    if (!Quat::try_slerp(a, b, t, result, epsilon)) {
                        throw nb::value_error("Quaternions cannot be interpolated");
                    }
                    return result;
                },
                nb::arg("a"),
                nb::arg("b"),
                nb::arg("t"),
                nb::arg("epsilon") = 1.0e-12,
                "Spherical linear interpolation between quaternions")
            .def("tolist",
                 [](const Quat& q) {
                     nb::list lst;
                     lst.append(q.x);
                     lst.append(q.y);
                     lst.append(q.z);
                     lst.append(q.w);
                     return lst;
                 })
            .def("copy", [](const Quat& q) { return q; })
            .def("__repr__", [](const Quat& q) {
                return "Quat(" + std::to_string(q.x) + ", " + std::to_string(q.y) + ", " + std::to_string(q.z) + ", " +
                       std::to_string(q.w) + ")";
            });
    }

} // namespace termin
