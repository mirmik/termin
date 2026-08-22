#include "common.hpp"

namespace termin {

    namespace {

        Quat checked_pose3_rotation(const Quat& rotation) {
            Quat unit;
            if (!rotation.try_normalized(unit)) {
                throw nb::value_error("Pose3 rotation must be finite and non-degenerate");
            }
            return unit;
        }

        Pose3 checked_pose3(const Pose3& pose) {
            return {checked_pose3_rotation(pose.ang), pose.lin};
        }

        Vec3 checked_pose3_rotate(const Quat& rotation, const Vec3& value, bool inverse) {
            Vec3 result;
            const bool success =
                inverse ? rotation.try_inverse_rotate(value, result) : rotation.try_rotate(value, result);
            if (!success) {
                throw nb::value_error(
                    "Pose3 rotation and vector must be finite, and the rotation must be non-degenerate");
            }
            return result;
        }

        Vec3 checked_pose3_add(const Vec3& first, const Vec3& second) {
            const Vec3 result = first + second;
            if (!result.is_finite()) {
                throw nb::value_error("Pose3 operation produced a non-finite translation");
            }
            return result;
        }

        Quat checked_pose3_rotation_product(const Quat& first, const Quat& second) {
            Quat result;
            if (!(first * second).try_normalized(result, 0.0)) {
                throw nb::value_error("Pose3 rotation composition produced an invalid quaternion");
            }
            return result;
        }

        Pose3 checked_pose3_compose(const Pose3& parent, const Pose3& child) {
            const Pose3 checked_parent = checked_pose3(parent);
            const Pose3 checked_child = checked_pose3(child);
            return {
                checked_pose3_rotation_product(checked_parent.ang, checked_child.ang),
                checked_pose3_add(checked_parent.lin,
                                  checked_pose3_rotate(checked_parent.ang, checked_child.lin, false)),
            };
        }

        Pose3 checked_pose3_inverse(const Pose3& pose) {
            const Pose3 checked = checked_pose3(pose);
            return {
                checked.ang.conjugate(),
                checked_pose3_rotate(checked.ang, -checked.lin, true),
            };
        }

        Vec3 checked_pose3_transform_point(const Pose3& pose, const Vec3& point) {
            return checked_pose3_add(checked_pose3_rotate(pose.ang, point, false), pose.lin);
        }

        Vec3 checked_pose3_transform_vector(const Pose3& pose, const Vec3& vector) {
            return checked_pose3_rotate(pose.ang, vector, false);
        }

        Vec3 checked_pose3_inverse_transform_point(const Pose3& pose, const Vec3& point) {
            return checked_pose3_rotate(pose.ang, point - pose.lin, true);
        }

        Vec3 checked_pose3_inverse_transform_vector(const Pose3& pose, const Vec3& vector) {
            return checked_pose3_rotate(pose.ang, vector, true);
        }

        auto checked_pose3_direction(const Vec3& unit_direction, bool inverse) {
            return [unit_direction, inverse](const Pose3& pose, double distance) {
                if (!std::isfinite(distance)) {
                    throw nb::value_error("Pose3 direction distance must be finite");
                }
                return checked_pose3_rotate(pose.ang, unit_direction * distance, inverse);
            };
        }

        void checked_pose3_rotation_matrix(const Pose3& pose, double* out_row_major_9) {
            checked_pose3(pose).rotation_matrix(out_row_major_9);
        }

        Pose3 checked_pose3_from_axis_angle(const Vec3& axis, double angle) {
            Quat rotation;
            if (!Quat::try_from_axis_angle(axis, angle, rotation)) {
                throw nb::value_error("Pose3 axis must be finite and non-degenerate, and angle must be finite");
            }
            return {rotation, Vec3::zero()};
        }

        Pose3 checked_pose3_lerp(const Pose3& from, const Pose3& to, double t) {
            if (!std::isfinite(t)) {
                throw nb::value_error("Pose3 interpolation factor must be finite");
            }
            const Pose3 checked_from = checked_pose3(from);
            const Pose3 checked_to = checked_pose3(to);
            if (!checked_from.lin.is_finite() || !checked_to.lin.is_finite()) {
                throw nb::value_error("Pose3 interpolation translations must be finite");
            }

            Quat rotation;
            if (!Quat::try_slerp(checked_from.ang, checked_to.ang, t, rotation, 0.0)) {
                throw nb::value_error("Pose3 rotation interpolation is not representable");
            }
            const Vec3 translation = Vec3::lerp(checked_from.lin, checked_to.lin, t);
            if (!translation.is_finite()) {
                throw nb::value_error("Pose3 translation interpolation is not representable");
            }
            return {rotation, translation};
        }

    } // namespace

    void bind_pose3(nb::module_& m) {
        nb::class_<Pose3>(m, "Pose3")
            .def(nb::init<>())
            .def(
                "__init__",
                [](Pose3* self, std::optional<Quat> ang, std::optional<Vec3> lin) {
                    new (self) Pose3{ang.value_or(Quat::identity()), lin.value_or(Vec3::zero())};
                },
                nb::arg("ang").none() = nb::none(),
                nb::arg("lin").none() = nb::none())
            // Convenience: Pose3(Vec3) - translation only
            .def("__init__", [](Pose3* self, const Vec3& lin) { new (self) Pose3{Quat::identity(), lin}; })
            .def_prop_rw(
                "ang", [](const Pose3& p) { return p.ang; }, [](Pose3& p, const Quat& val) { p.ang = val; })
            .def_prop_rw(
                "lin", [](const Pose3& p) { return p.lin; }, [](Pose3& p, const Vec3& val) { p.lin = val; })
            .def("__mul__", &checked_pose3_compose, nb::is_operator())
            .def("__matmul__", &checked_pose3_compose, nb::is_operator())
            .def("inverse", &checked_pose3_inverse)
            .def("transform_point", &checked_pose3_transform_point)
            .def("transform_vector", &checked_pose3_transform_vector)
            .def("rotate_point", &checked_pose3_transform_vector)
            .def("inverse_transform_point", &checked_pose3_inverse_transform_point)
            .def("inverse_transform_vector", &checked_pose3_inverse_transform_vector)
            .def("point_to_global", &checked_pose3_transform_point)
            .def("vector_to_global", &checked_pose3_transform_vector)
            .def("point_to_local", &checked_pose3_inverse_transform_point)
            .def("vector_to_local", &checked_pose3_inverse_transform_vector)
            .def("forward_in_global", checked_pose3_direction(Vec3::unit_y(), false), nb::arg("distance") = 1.0)
            .def("backward_in_global", checked_pose3_direction(-Vec3::unit_y(), false), nb::arg("distance") = 1.0)
            .def("up_in_global", checked_pose3_direction(Vec3::unit_z(), false), nb::arg("distance") = 1.0)
            .def("down_in_global", checked_pose3_direction(-Vec3::unit_z(), false), nb::arg("distance") = 1.0)
            .def("right_in_global", checked_pose3_direction(Vec3::unit_x(), false), nb::arg("distance") = 1.0)
            .def("left_in_global", checked_pose3_direction(-Vec3::unit_x(), false), nb::arg("distance") = 1.0)
            .def("global_forward_in_local", checked_pose3_direction(Vec3::unit_y(), true), nb::arg("distance") = 1.0)
            .def("global_backward_in_local", checked_pose3_direction(-Vec3::unit_y(), true), nb::arg("distance") = 1.0)
            .def("global_up_in_local", checked_pose3_direction(Vec3::unit_z(), true), nb::arg("distance") = 1.0)
            .def("global_down_in_local", checked_pose3_direction(-Vec3::unit_z(), true), nb::arg("distance") = 1.0)
            .def("global_right_in_local", checked_pose3_direction(Vec3::unit_x(), true), nb::arg("distance") = 1.0)
            .def("global_left_in_local", checked_pose3_direction(-Vec3::unit_x(), true), nb::arg("distance") = 1.0)
            // rotate_vector is an alias for transform_vector (for Pose3 without scale, they are the same)
            .def("rotate_vector", &checked_pose3_transform_vector)
            .def("inverse_rotate_vector", &checked_pose3_inverse_transform_vector)
            .def("normalized",
                 [](const Pose3& pose) {
                     Quat rotation;
                     if (!pose.ang.try_normalized(rotation)) {
                         throw nb::value_error("Pose3 rotation cannot be normalized");
                     }
                     return Pose3{rotation, pose.lin};
                 })
            .def("with_translation", nb::overload_cast<const Vec3&>(&Pose3::with_translation, nb::const_))
            .def("with_rotation", &Pose3::with_rotation)
            .def("rotation_matrix",
                 [](const Pose3& p) {
                     double data[9];
                     checked_pose3_rotation_matrix(p, data);
                     return mat33_row_tuple(data);
                 })
            .def("rotation_mat33",
                 [](const Pose3& p) {
                     double data[9];
                     checked_pose3_rotation_matrix(p, data);
                     Mat33 mat;
                     for (int row = 0; row < 3; ++row)
                         for (int col = 0; col < 3; ++col)
                             mat(col, row) = data[row * 3 + col];
                     return mat;
                 })
            .def_static("identity", &Pose3::identity)
            .def_static("translation", nb::overload_cast<double, double, double>(&Pose3::translation))
            .def_static("rotation", &checked_pose3_from_axis_angle)
            .def_static("rotate_x", [](double angle) { return checked_pose3_from_axis_angle(Vec3::unit_x(), angle); })
            .def_static("rotate_y", [](double angle) { return checked_pose3_from_axis_angle(Vec3::unit_y(), angle); })
            .def_static("rotate_z", [](double angle) { return checked_pose3_from_axis_angle(Vec3::unit_z(), angle); })
            // Python-style aliases (rotateX instead of rotate_x)
            .def_static("rotateX", [](double angle) { return checked_pose3_from_axis_angle(Vec3::unit_x(), angle); })
            .def_static("rotateY", [](double angle) { return checked_pose3_from_axis_angle(Vec3::unit_y(), angle); })
            .def_static("rotateZ", [](double angle) { return checked_pose3_from_axis_angle(Vec3::unit_z(), angle); })
            // moveX, moveY, moveZ for translation
            .def_static("moveX", [](double d) { return Pose3::translation(d, 0, 0); })
            .def_static("moveY", [](double d) { return Pose3::translation(0, d, 0); })
            .def_static("moveZ", [](double d) { return Pose3::translation(0, 0, d); })
            .def_static(
                "looking_at",
                [](const Vec3& eye, const Vec3& target, std::optional<Vec3> up) {
                    return Pose3::looking_at(eye, target, up.value_or(Vec3::unit_z()));
                },
                nb::arg("eye"),
                nb::arg("target"),
                nb::arg("up").none() = nb::none())
            .def_static(
                "from_euler",
                [](const Vec3& euler_xyz) {
                    Quat rotation;
                    if (!Quat::try_from_euler(euler_xyz, rotation)) {
                        throw nb::value_error("Euler angles must be finite");
                    }
                    return Pose3{rotation, Vec3::zero()};
                },
                nb::arg("euler_xyz"))
            .def("to_euler",
                 [](const Pose3& pose) {
                     Vec3 result;
                     if (!pose.ang.try_to_euler(result)) {
                         throw nb::value_error("Pose3 rotation cannot be converted to Euler angles");
                     }
                     return result;
                 })
            .def("to_axis_angle",
                 [](const Pose3& p) {
                     Vec3 axis;
                     double angle;
                     checked_pose3(p).to_axis_angle(axis, angle);
                     return nb::make_tuple(axis, angle);
                 })
            .def("distance", &Pose3::distance)
            .def("copy", &Pose3::copy)
            .def("as_matrix",
                 [](const Pose3& p) {
                     double data[16];
                     double matrix[16];
                     checked_pose3(p).as_matrix(matrix);
                     for (int row = 0; row < 4; ++row)
                         for (int col = 0; col < 4; ++col)
                             data[row * 4 + col] = matrix[col * 4 + row];
                     return mat44_row_tuple(data);
                 })
            .def("as_mat44", [](const Pose3& p) { return checked_pose3(p).as_mat44(); })
            .def("as_matrix34",
                 [](const Pose3& p) {
                     double data[12];
                     double rot[9];
                     checked_pose3_rotation_matrix(p, rot);
                     for (int i = 0; i < 3; i++)
                         for (int j = 0; j < 3; j++)
                             data[i * 4 + j] = rot[i * 3 + j];
                     data[3] = p.lin.x;
                     data[7] = p.lin.y;
                     data[11] = p.lin.z;
                     return mat34_row_tuple(data);
                 })
            .def("compose", &checked_pose3_compose)
            // x, y, z property shortcuts for translation
            .def_prop_rw(
                "x", [](const Pose3& p) { return p.lin.x; }, [](Pose3& p, double v) { p.lin.x = v; })
            .def_prop_rw(
                "y", [](const Pose3& p) { return p.lin.y; }, [](Pose3& p, double v) { p.lin.y = v; })
            .def_prop_rw(
                "z", [](const Pose3& p) { return p.lin.z; }, [](Pose3& p, double v) { p.lin.z = v; })
            // Static translation methods (aliases)
            .def_static("right", [](double d) { return Pose3::translation(d, 0, 0); })
            .def_static("forward", [](double d) { return Pose3::translation(0, d, 0); })
            .def_static("up", [](double d) { return Pose3::translation(0, 0, d); })
            // Static from_axis_angle
            .def_static("from_axis_angle", &checked_pose3_from_axis_angle)
            // Static lerp
            .def_static("lerp", &checked_pose3_lerp)
            .def(
                "to_general_pose3",
                [](const Pose3& p, std::optional<Vec3> scale) {
                    return GeneralPose3(p.ang, p.lin, scale.value_or(Vec3{1.0, 1.0, 1.0}));
                },
                nb::arg("scale").none() = nb::none())
            .def("__repr__", [](const Pose3& p) {
                return "Pose3(ang=Quat(" + std::to_string(p.ang.x) + ", " + std::to_string(p.ang.y) + ", " +
                       std::to_string(p.ang.z) + ", " + std::to_string(p.ang.w) + "), lin=Vec3(" +
                       std::to_string(p.lin.x) + ", " + std::to_string(p.lin.y) + ", " + std::to_string(p.lin.z) + "))";
            });

        m.def("lerp", &checked_pose3_lerp, "Linear interpolation between poses");
    }

} // namespace termin
