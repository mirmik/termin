#include "common.hpp"

#include <stdexcept>

namespace termin {

    void bind_affine3(nb::module_& m) {
        nb::class_<Basis3d>(m, "Basis3d")
            .def(nb::init<>())
            .def(
                "__init__",
                [](Basis3d* self, const Vec3& x, const Vec3& y, const Vec3& z) { new (self) Basis3d{x, y, z}; },
                nb::arg("x"),
                nb::arg("y"),
                nb::arg("z"))
            .def_rw("x", &Basis3d::x)
            .def_rw("y", &Basis3d::y)
            .def_rw("z", &Basis3d::z)
            .def("__matmul__", [](const Basis3d& a, const Basis3d& b) { return a * b; })
            .def("__matmul__", [](const Basis3d& basis, const Vec3& vector) { return basis.transform_vector(vector); })
            .def("transform_vector", &Basis3d::transform_vector)
            .def(
                "try_transform_normal",
                [](const Basis3d& basis, const Vec3& normal, double epsilon) -> nb::object {
                    Vec3 result;
                    if (!basis.try_transform_normal(normal, result, epsilon)) {
                        return nb::none();
                    }
                    return nb::cast(result);
                },
                nb::arg("normal"),
                nb::arg("epsilon") = 1.0e-12)
            .def("determinant", &Basis3d::determinant)
            .def("is_finite", &Basis3d::is_finite)
            .def(
                "try_inverse",
                [](const Basis3d& basis, double epsilon) -> nb::object {
                    Basis3d inverse;
                    if (!basis.try_inverse(inverse, epsilon)) {
                        return nb::none();
                    }
                    return nb::cast(inverse);
                },
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "inverse",
                [](const Basis3d& basis, double epsilon) {
                    Basis3d inverse;
                    if (!basis.try_inverse(inverse, epsilon)) {
                        throw std::runtime_error("Basis3d is singular and cannot be inverted");
                    }
                    return inverse;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def("to_rows",
                 [](const Basis3d& basis) {
                     const double data[9] = {
                         basis.x.x,
                         basis.y.x,
                         basis.z.x,
                         basis.x.y,
                         basis.y.y,
                         basis.z.y,
                         basis.x.z,
                         basis.y.z,
                         basis.z.z,
                     };
                     return mat33_row_tuple(data);
                 })
            .def_static("identity", &Basis3d::identity)
            .def_static(
                "try_from_quat",
                [](const Quat& rotation, double epsilon) -> nb::object {
                    Quat unit;
                    if (!rotation.try_normalized(unit, epsilon)) {
                        return nb::none();
                    }
                    return nb::cast(Basis3d::from_quat(unit));
                },
                nb::arg("rotation"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "from_quat",
                [](const Quat& rotation, double epsilon) {
                    Quat unit;
                    if (!rotation.try_normalized(unit, epsilon)) {
                        throw nb::value_error("Basis3d rotation requires a finite non-degenerate quaternion");
                    }
                    return Basis3d::from_quat(unit);
                },
                nb::arg("rotation"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static("scaling",
                        nb::overload_cast<double, double, double>(&Basis3d::scaling),
                        nb::arg("x"),
                        nb::arg("y"),
                        nb::arg("z"))
            .def_static("scaling", nb::overload_cast<double>(&Basis3d::scaling), nb::arg("uniform"))
            .def("__repr__", [](const Basis3d&) { return "<Basis3d>"; });

        nb::class_<Affine3d>(m, "Affine3d")
            .def(nb::init<>())
            .def(
                "__init__",
                [](Affine3d* self, const Basis3d& basis, const Vec3& translation) {
                    new (self) Affine3d{basis, translation};
                },
                nb::arg("basis"),
                nb::arg("translation"))
            .def_rw("basis", &Affine3d::basis)
            .def_rw("translation", &Affine3d::translation)
            .def("__matmul__", [](const Affine3d& a, const Affine3d& b) { return a * b; })
            .def("transform_point", &Affine3d::transform_point)
            .def("transform_vector", &Affine3d::transform_vector)
            .def(
                "try_transform_normal",
                [](const Affine3d& affine, const Vec3& normal, double epsilon) -> nb::object {
                    Vec3 result;
                    if (!affine.try_transform_normal(normal, result, epsilon)) {
                        return nb::none();
                    }
                    return nb::cast(result);
                },
                nb::arg("normal"),
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "try_inverse_transform_point",
                [](const Affine3d& affine, const Vec3& point, double epsilon) -> nb::object {
                    Vec3 result;
                    if (!affine.try_inverse_transform_point(point, result, epsilon)) {
                        return nb::none();
                    }
                    return nb::cast(result);
                },
                nb::arg("point"),
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "try_inverse_transform_vector",
                [](const Affine3d& affine, const Vec3& vector, double epsilon) -> nb::object {
                    Vec3 result;
                    if (!affine.try_inverse_transform_vector(vector, result, epsilon)) {
                        return nb::none();
                    }
                    return nb::cast(result);
                },
                nb::arg("vector"),
                nb::arg("epsilon") = 1.0e-12)
            .def("determinant", &Affine3d::determinant)
            .def("is_finite", &Affine3d::is_finite)
            .def(
                "try_inverse",
                [](const Affine3d& affine, double epsilon) -> nb::object {
                    Affine3d inverse;
                    if (!affine.try_inverse(inverse, epsilon)) {
                        return nb::none();
                    }
                    return nb::cast(inverse);
                },
                nb::arg("epsilon") = 1.0e-12)
            .def(
                "inverse",
                [](const Affine3d& affine, double epsilon) {
                    Affine3d inverse;
                    if (!affine.try_inverse(inverse, epsilon)) {
                        throw std::runtime_error("Affine3d is singular and cannot be inverted");
                    }
                    return inverse;
                },
                nb::arg("epsilon") = 1.0e-12)
            .def("as_matrix",
                 [](const Affine3d& affine) {
                     double column_major[16];
                     double row_major[16];
                     affine.matrix4(column_major);
                     for (int row = 0; row < 4; ++row) {
                         for (int col = 0; col < 4; ++col) {
                             row_major[row * 4 + col] = column_major[col * 4 + row];
                         }
                     }
                     return mat44_row_tuple(row_major);
                 })
            .def("as_mat44",
                 [](const Affine3d& affine) {
                     double column_major[16];
                     affine.matrix4(column_major);
                     Mat44 matrix;
                     for (size_t i = 0; i < 16; ++i) {
                         matrix.data[i] = column_major[i];
                     }
                     return matrix;
                 })
            .def_static("identity", &Affine3d::identity)
            .def_static("from_translation", nb::overload_cast<const Vec3&>(&Affine3d::from_translation))
            .def_static(
                "try_rotation",
                [](const Quat& rotation, double epsilon) -> nb::object {
                    Quat unit;
                    if (!rotation.try_normalized(unit, epsilon)) {
                        return nb::none();
                    }
                    return nb::cast(Affine3d::from_rotation(unit));
                },
                nb::arg("rotation"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "rotation",
                [](const Quat& rotation, double epsilon) {
                    Quat unit;
                    if (!rotation.try_normalized(unit, epsilon)) {
                        throw nb::value_error("Affine3d rotation requires a finite non-degenerate quaternion");
                    }
                    return Affine3d::from_rotation(unit);
                },
                nb::arg("rotation"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static("scaling",
                        nb::overload_cast<double, double, double>(&Affine3d::scaling),
                        nb::arg("x"),
                        nb::arg("y"),
                        nb::arg("z"))
            .def_static("scaling", nb::overload_cast<double>(&Affine3d::scaling))
            .def_static(
                "try_trs",
                [](const Vec3& translation, const Quat& rotation, const Vec3& scale, double epsilon) -> nb::object {
                    Quat unit;
                    if (!rotation.try_normalized(unit, epsilon)) {
                        return nb::none();
                    }
                    return nb::cast(Affine3d::trs(translation, unit, scale));
                },
                nb::arg("translation"),
                nb::arg("rotation"),
                nb::arg("scale"),
                nb::arg("epsilon") = 1.0e-12)
            .def_static(
                "trs",
                [](const Vec3& translation, const Quat& rotation, const Vec3& scale, double epsilon) {
                    Quat unit;
                    if (!rotation.try_normalized(unit, epsilon)) {
                        throw nb::value_error("Affine3d TRS requires a finite non-degenerate quaternion");
                    }
                    return Affine3d::trs(translation, unit, scale);
                },
                nb::arg("translation"),
                nb::arg("rotation"),
                nb::arg("scale"),
                nb::arg("epsilon") = 1.0e-12)
            .def("__repr__", [](const Affine3d&) { return "<Affine3d>"; });
    }

} // namespace termin
