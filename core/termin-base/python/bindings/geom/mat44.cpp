#include "common.hpp"
#include <nanobind/stl/pair.h>

namespace termin {

    void bind_mat44(nb::module_& m) {
        nb::class_<Mat44>(m, "Mat44")
            .def(nb::init<>())
            .def("__call__", [](const Mat44& m, int col, int row) { return m(col, row); })
            .def("__getitem__", [](const Mat44& m, std::pair<int, int> idx) { return m(idx.first, idx.second); })
            .def("__setitem__", [](Mat44& m, std::pair<int, int> idx, double val) { m(idx.first, idx.second) = val; })
            .def(nb::self * nb::self)
            .def("__matmul__", [](const Mat44& a, const Mat44& b) { return a * b; })
            .def("__matmul__", [](const Mat44& m, const Vec3& v) { return m.transform_point(v); })
            .def("__matmul__", [](const Mat44& m, const Vec4& v) { return m.transform_homogeneous(v); })
            .def("transform_point", &Mat44::transform_point)
            .def("transform_direction", &Mat44::transform_direction)
            .def("transform_homogeneous", &Mat44::transform_homogeneous)
            .def("transform_vec4", &Mat44::transform_homogeneous)
            .def("is_finite", &Mat44::is_finite)
            .def(
                "try_transform_point",
                [](const Mat44& matrix, const Vec3& point, double epsilon) -> nb::object {
                    Vec3 transformed;
                    return matrix.try_transform_point(point, transformed, epsilon) ? nb::cast(transformed) : nb::none();
                },
                nb::arg("point"),
                nb::arg("epsilon") = 1.0e-10)
            .def(
                "try_inverse",
                [](const Mat44& matrix, double epsilon) -> nb::object {
                    Mat44 inverse;
                    return matrix.try_inverse(inverse, epsilon) ? nb::cast(inverse) : nb::none();
                },
                nb::arg("epsilon") = 1.0e-12)
            .def("transposed", &Mat44::transposed)
            .def("inverse", &Mat44::inverse)
            .def("get_translation", &Mat44::get_translation)
            .def("get_scale", &Mat44::get_scale)
            .def("with_translation", nb::overload_cast<const Vec3&>(&Mat44::with_translation, nb::const_))
            .def("with_translation", nb::overload_cast<double, double, double>(&Mat44::with_translation, nb::const_))
            .def_static("identity", &Mat44::identity)
            .def_static("zero", &Mat44::zero)
            .def_static(
                "from_column_major",
                [](nb::object values) { return column_major_sequence_to_mat44(values); },
                nb::arg("values"),
                "Construct from exactly 16 flat column-major values")
            .def_static("translation", nb::overload_cast<const Vec3&>(&Mat44::translation))
            .def_static("translation", nb::overload_cast<double, double, double>(&Mat44::translation))
            .def_static("scale", nb::overload_cast<const Vec3&>(&Mat44::scale))
            .def_static("scale", nb::overload_cast<double>(&Mat44::scale))
            .def_static(
                "try_rotation",
                [](const Quat& orientation, double epsilon) -> std::optional<Mat44> {
                    Mat44 result;
                    if (!Mat44::try_rotation(orientation, result, epsilon)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("orientation"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "rotation",
                [](const Quat& orientation, double epsilon) {
                    Mat44 result;
                    if (!Mat44::try_rotation(orientation, result, epsilon)) {
                        throw nb::value_error("Quaternion cannot be converted to a Mat44 rotation matrix");
                    }
                    return result;
                },
                nb::arg("orientation"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "rotation_axis_angle",
                [](const Vec3& axis, double angle, double epsilon) {
                    Mat44 result;
                    if (!Mat44::try_rotation_axis_angle(axis, angle, result, epsilon)) {
                        throw nb::value_error(
                            "Mat44 axis-angle rotation requires a finite non-degenerate axis and angle");
                    }
                    return result;
                },
                nb::arg("axis"),
                nb::arg("angle"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static("perspective",
                        &Mat44::perspective,
                        nb::arg("fov_y"),
                        nb::arg("aspect"),
                        nb::arg("near"),
                        nb::arg("far"),
                        "Perspective projection (Y-forward, Z-up)")
            .def_static("orthographic",
                        &Mat44::orthographic,
                        nb::arg("left"),
                        nb::arg("right"),
                        nb::arg("bottom"),
                        nb::arg("top"),
                        nb::arg("near"),
                        nb::arg("far"),
                        "Orthographic projection (Y-forward, Z-up)")
            .def_static(
                "look_at",
                [](const Vec3& eye, const Vec3& target, std::optional<Vec3> up) {
                    return Mat44::look_at(eye, target, up.value_or(Vec3::unit_z()));
                },
                nb::arg("eye"),
                nb::arg("target"),
                nb::arg("up").none() = nb::none(),
                "Look-at view matrix (Y-forward, Z-up)")
            .def_static(
                "try_compose",
                [](const Vec3& translation, const Quat& rotation, const Vec3& scale, double epsilon)
                    -> std::optional<Mat44> {
                    Quat unit_rotation;
                    if (!rotation.try_normalized(unit_rotation, epsilon)) {
                        return std::nullopt;
                    }
                    return Mat44::compose(translation, unit_rotation, scale);
                },
                nb::arg("translation"),
                nb::arg("rotation"),
                nb::arg("scale"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "compose",
                [](const Vec3& translation, const Quat& rotation, const Vec3& scale, double epsilon) {
                    Quat unit_rotation;
                    if (!rotation.try_normalized(unit_rotation, epsilon)) {
                        throw nb::value_error("Mat44 composition requires a finite non-degenerate rotation");
                    }
                    return Mat44::compose(translation, unit_rotation, scale);
                },
                nb::arg("translation"),
                nb::arg("rotation"),
                nb::arg("scale"),
                nb::arg("epsilon") = 1.0e-12,
                "Compose TRS matrix")
            .def("to_rows",
                 [](const Mat44& mat) {
                     double data[16];
                     for (int row = 0; row < 4; ++row)
                         for (int col = 0; col < 4; ++col)
                             data[row * 4 + col] = mat(col, row);
                     return mat44_row_tuple(data);
                 })
            .def("to_column_major",
                 [](const Mat44& mat) {
                     nb::list values;
                     for (double value : mat.data) {
                         values.append(value);
                     }
                     return values;
                 })
            .def("tolist",
                 [](const Mat44& mat) {
                     double data[16];
                     for (int row = 0; row < 4; ++row)
                         for (int col = 0; col < 4; ++col)
                             data[row * 4 + col] = mat(col, row);
                     return mat44_row_tuple(data);
                 })
            .def("__repr__", [](const Mat44& m) { return "<Mat44>"; })
            .def("to_float", &Mat44::to_float);

        // Mat44f (float version)
        nb::class_<Mat44f>(m, "Mat44f")
            .def(nb::init<>())
            .def("__call__", [](const Mat44f& m, int col, int row) { return m(col, row); })
            .def("__getitem__", [](const Mat44f& m, std::pair<int, int> idx) { return m(idx.first, idx.second); })
            .def("__setitem__", [](Mat44f& m, std::pair<int, int> idx, float val) { m(idx.first, idx.second) = val; })
            .def(nb::self * nb::self)
            .def("__matmul__", [](const Mat44f& a, const Mat44f& b) { return a * b; })
            .def("__matmul__", [](const Mat44f& m, const Vec3f& v) { return m.transform_point(v); })
            .def("__matmul__", [](const Mat44f& m, const Vec4f& v) { return m.transform_homogeneous(v); })
            .def("transform_point", &Mat44f::transform_point)
            .def("transform_direction", &Mat44f::transform_direction)
            .def("transform_homogeneous", &Mat44f::transform_homogeneous)
            .def("transform_vec4", &Mat44f::transform_homogeneous)
            .def("is_finite", &Mat44f::is_finite)
            .def(
                "try_transform_point",
                [](const Mat44f& matrix, const Vec3f& point, float epsilon) -> nb::object {
                    Vec3f transformed;
                    return matrix.try_transform_point(point, transformed, epsilon) ? nb::cast(transformed) : nb::none();
                },
                nb::arg("point"),
                nb::arg("epsilon") = 1.0e-6f)
            .def(
                "try_inverse",
                [](const Mat44f& matrix, float epsilon) -> nb::object {
                    Mat44f inverse;
                    return matrix.try_inverse(inverse, epsilon) ? nb::cast(inverse) : nb::none();
                },
                nb::arg("epsilon") = 1.0e-6f)
            .def("transposed", &Mat44f::transposed)
            .def("inverse", &Mat44f::inverse)
            .def("get_translation", &Mat44f::get_translation)
            .def("get_scale", &Mat44f::get_scale)
            .def("with_translation", nb::overload_cast<const Vec3&>(&Mat44f::with_translation, nb::const_))
            .def("with_translation", nb::overload_cast<float, float, float>(&Mat44f::with_translation, nb::const_))
            .def_static("identity", &Mat44f::identity)
            .def_static("zero", &Mat44f::zero)
            .def_static("translation", nb::overload_cast<const Vec3&>(&Mat44f::translation))
            .def_static("translation", nb::overload_cast<float, float, float>(&Mat44f::translation))
            .def_static("scale", nb::overload_cast<const Vec3&>(&Mat44f::scale))
            .def_static("scale", nb::overload_cast<float>(&Mat44f::scale))
            .def_static(
                "try_rotation",
                [](const Quat& orientation, double epsilon) -> std::optional<Mat44f> {
                    Mat44f result;
                    if (!Mat44f::try_rotation(orientation, result, epsilon)) {
                        return std::nullopt;
                    }
                    return result;
                },
                nb::arg("orientation"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "rotation",
                [](const Quat& orientation, double epsilon) {
                    Mat44f result;
                    if (!Mat44f::try_rotation(orientation, result, epsilon)) {
                        throw nb::value_error("Quaternion cannot be converted to a Mat44f rotation matrix");
                    }
                    return result;
                },
                nb::arg("orientation"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "rotation_axis_angle",
                [](const Vec3& axis, float angle, double epsilon) {
                    Mat44f result;
                    if (!Mat44f::try_rotation_axis_angle(axis, angle, result, epsilon)) {
                        throw nb::value_error(
                            "Mat44f axis-angle rotation requires a finite non-degenerate axis and angle");
                    }
                    return result;
                },
                nb::arg("axis"),
                nb::arg("angle"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static("perspective",
                        &Mat44f::perspective,
                        nb::arg("fov_y"),
                        nb::arg("aspect"),
                        nb::arg("near"),
                        nb::arg("far"))
            .def_static("orthographic",
                        &Mat44f::orthographic,
                        nb::arg("left"),
                        nb::arg("right"),
                        nb::arg("bottom"),
                        nb::arg("top"),
                        nb::arg("near"),
                        nb::arg("far"))
            .def_static(
                "look_at",
                [](const Vec3& eye, const Vec3& target, std::optional<Vec3> up) {
                    return Mat44f::look_at(eye, target, up.value_or(Vec3::unit_z()));
                },
                nb::arg("eye"),
                nb::arg("target"),
                nb::arg("up").none() = nb::none())
            .def_static(
                "try_compose",
                [](const Vec3& translation, const Quat& rotation, const Vec3& scale, double epsilon)
                    -> std::optional<Mat44f> {
                    Quat unit_rotation;
                    if (!rotation.try_normalized(unit_rotation, epsilon)) {
                        return std::nullopt;
                    }
                    return Mat44f::compose(translation, unit_rotation, scale);
                },
                nb::arg("translation"),
                nb::arg("rotation"),
                nb::arg("scale"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "compose",
                [](const Vec3& translation, const Quat& rotation, const Vec3& scale, double epsilon) {
                    Quat unit_rotation;
                    if (!rotation.try_normalized(unit_rotation, epsilon)) {
                        throw nb::value_error("Mat44f composition requires a finite non-degenerate rotation");
                    }
                    return Mat44f::compose(translation, unit_rotation, scale);
                },
                nb::arg("translation"),
                nb::arg("rotation"),
                nb::arg("scale"),
                nb::arg("epsilon") = 1.0e-12)
            .def("to_rows",
                 [](const Mat44f& mat) {
                     double data[16];
                     for (int row = 0; row < 4; ++row)
                         for (int col = 0; col < 4; ++col)
                             data[row * 4 + col] = mat(col, row);
                     return mat44_row_tuple(data);
                 })
            .def("tolist",
                 [](const Mat44f& mat) {
                     double data[16];
                     for (int row = 0; row < 4; ++row)
                         for (int col = 0; col < 4; ++col)
                             data[row * 4 + col] = mat(col, row);
                     return mat44_row_tuple(data);
                 })
            .def("__repr__", [](const Mat44f& m) { return "<Mat44f>"; })
            .def("to_double", &Mat44f::to_double);
    }

} // namespace termin
