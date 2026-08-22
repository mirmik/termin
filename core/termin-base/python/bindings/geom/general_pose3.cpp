#include "common.hpp"

namespace termin {

    namespace {

        Quat checked_general_pose3_rotation(const Quat& rotation) {
            Quat unit;
            if (!rotation.try_normalized(unit)) {
                throw nb::value_error("GeneralPose3 rotation must be finite and non-degenerate");
            }
            return unit;
        }

        GeneralPose3 checked_general_pose3(const GeneralPose3& pose) {
            return {checked_general_pose3_rotation(pose.ang), pose.lin, pose.scale};
        }

        Pose3 checked_general_pose3_child(const Pose3& pose) {
            return {checked_general_pose3_rotation(pose.ang), pose.lin};
        }

        Vec3 checked_general_pose3_rotate(const Quat& rotation, const Vec3& value, bool inverse) {
            Vec3 result;
            const bool success =
                inverse ? rotation.try_inverse_rotate(value, result) : rotation.try_rotate(value, result);
            if (!success) {
                throw nb::value_error(
                    "GeneralPose3 rotation and vector must be finite, and the rotation must be non-degenerate");
            }
            return result;
        }

        Vec3 checked_general_pose3_finite_vector(const Vec3& value, const char* diagnostic) {
            if (!value.is_finite()) {
                throw nb::value_error(diagnostic);
            }
            return value;
        }

        Vec3 checked_general_pose3_cwise_product(const Vec3& first, const Vec3& second) {
            return checked_general_pose3_finite_vector(first.cwise_product(second),
                                                       "GeneralPose3 operation produced a non-finite scaled vector");
        }

        Vec3 checked_general_pose3_add(const Vec3& first, const Vec3& second) {
            return checked_general_pose3_finite_vector(first + second,
                                                       "GeneralPose3 operation produced a non-finite translation");
        }

        Vec3 checked_general_pose3_inverse_scale(const Vec3& scale) {
            if (!scale.is_finite()) {
                throw nb::value_error("GeneralPose3 scale must be finite");
            }
            return checked_general_pose3_finite_vector(
                {
                    scale.x != 0.0 ? 1.0 / scale.x : 0.0,
                    scale.y != 0.0 ? 1.0 / scale.y : 0.0,
                    scale.z != 0.0 ? 1.0 / scale.z : 0.0,
                },
                "GeneralPose3 scale inverse is not representable");
        }

        Quat checked_general_pose3_rotation_product(const Quat& first, const Quat& second) {
            Quat result;
            if (!(first * second).try_normalized(result, 0.0)) {
                throw nb::value_error("GeneralPose3 rotation composition produced an invalid quaternion");
            }
            return result;
        }

        GeneralPose3 checked_general_pose3_compose(const GeneralPose3& parent, const GeneralPose3& child) {
            const GeneralPose3 checked_parent = checked_general_pose3(parent);
            const GeneralPose3 checked_child = checked_general_pose3(child);
            const Vec3 scaled_child = checked_general_pose3_cwise_product(checked_parent.scale, checked_child.lin);
            return {
                checked_general_pose3_rotation_product(checked_parent.ang, checked_child.ang),
                checked_general_pose3_add(checked_parent.lin,
                                          checked_general_pose3_rotate(checked_parent.ang, scaled_child, false)),
                checked_general_pose3_cwise_product(checked_parent.scale, checked_child.scale),
            };
        }

        GeneralPose3 checked_general_pose3_compose_pose(const GeneralPose3& parent, const Pose3& child) {
            const GeneralPose3 checked_parent = checked_general_pose3(parent);
            const Pose3 checked_child = checked_general_pose3_child(child);
            const Vec3 scaled_child = checked_general_pose3_cwise_product(checked_parent.scale, checked_child.lin);
            return {
                checked_general_pose3_rotation_product(checked_parent.ang, checked_child.ang),
                checked_general_pose3_add(checked_parent.lin,
                                          checked_general_pose3_rotate(checked_parent.ang, scaled_child, false)),
                checked_parent.scale,
            };
        }

        GeneralPose3 checked_general_pose3_inverse(const GeneralPose3& pose) {
            const GeneralPose3 checked = checked_general_pose3(pose);
            const Vec3 inverse_scale = checked_general_pose3_inverse_scale(checked.scale);
            const Vec3 rotated_translation = checked_general_pose3_rotate(checked.ang, -checked.lin, true);
            return {
                checked.ang.conjugate(),
                checked_general_pose3_cwise_product(rotated_translation, inverse_scale),
                inverse_scale,
            };
        }

        Vec3 checked_general_pose3_transform_point(const GeneralPose3& pose, const Vec3& point) {
            const Vec3 scaled = checked_general_pose3_cwise_product(pose.scale, point);
            return checked_general_pose3_add(checked_general_pose3_rotate(pose.ang, scaled, false), pose.lin);
        }

        Vec3 checked_general_pose3_transform_vector(const GeneralPose3& pose, const Vec3& vector) {
            return checked_general_pose3_rotate(
                pose.ang, checked_general_pose3_cwise_product(pose.scale, vector), false);
        }

        Vec3 checked_general_pose3_transform_direction(const GeneralPose3& pose, const Vec3& direction) {
            return checked_general_pose3_rotate(pose.ang, direction, false);
        }

        Vec3 checked_general_pose3_inverse_transform_point(const GeneralPose3& pose, const Vec3& point) {
            const Vec3 rotated = checked_general_pose3_rotate(pose.ang, point - pose.lin, true);
            return checked_general_pose3_cwise_product(rotated, checked_general_pose3_inverse_scale(pose.scale));
        }

        Vec3 checked_general_pose3_inverse_transform_vector(const GeneralPose3& pose, const Vec3& vector) {
            const Vec3 rotated = checked_general_pose3_rotate(pose.ang, vector, true);
            return checked_general_pose3_cwise_product(rotated, checked_general_pose3_inverse_scale(pose.scale));
        }

        Vec3 checked_general_pose3_inverse_transform_direction(const GeneralPose3& pose, const Vec3& direction) {
            return checked_general_pose3_rotate(pose.ang, direction, true);
        }

        auto checked_general_pose3_direction(const Vec3& unit_direction, bool inverse) {
            return [unit_direction, inverse](const GeneralPose3& pose, double distance) {
                if (!std::isfinite(distance)) {
                    throw nb::value_error("GeneralPose3 direction distance must be finite");
                }
                return checked_general_pose3_rotate(pose.ang, unit_direction * distance, inverse);
            };
        }

        void checked_general_pose3_rotation_matrix(const GeneralPose3& pose, double* out_row_major_9) {
            checked_general_pose3(pose).rotation_matrix(out_row_major_9);
        }

        GeneralPose3 checked_general_pose3_from_axis_angle(const Vec3& axis, double angle) {
            Quat rotation;
            if (!Quat::try_from_axis_angle(axis, angle, rotation)) {
                throw nb::value_error("GeneralPose3 axis must be finite and non-degenerate, and angle must be finite");
            }
            return {rotation, Vec3::zero(), Vec3{1.0, 1.0, 1.0}};
        }

        GeneralPose3 checked_general_pose3_lerp(const GeneralPose3& from, const GeneralPose3& to, double t) {
            if (!std::isfinite(t)) {
                throw nb::value_error("GeneralPose3 interpolation factor must be finite");
            }
            const GeneralPose3 checked_from = checked_general_pose3(from);
            const GeneralPose3 checked_to = checked_general_pose3(to);
            if (!checked_from.lin.is_finite() || !checked_to.lin.is_finite()) {
                throw nb::value_error("GeneralPose3 interpolation translations must be finite");
            }
            if (!checked_from.scale.is_finite() || !checked_to.scale.is_finite()) {
                throw nb::value_error("GeneralPose3 interpolation scales must be finite");
            }

            Quat rotation;
            if (!Quat::try_slerp(checked_from.ang, checked_to.ang, t, rotation, 0.0)) {
                throw nb::value_error("GeneralPose3 rotation interpolation is not representable");
            }
            const Vec3 translation = Vec3::lerp(checked_from.lin, checked_to.lin, t);
            if (!translation.is_finite()) {
                throw nb::value_error("GeneralPose3 translation interpolation is not representable");
            }
            const Vec3 scale = Vec3::lerp(checked_from.scale, checked_to.scale, t);
            if (!scale.is_finite()) {
                throw nb::value_error("GeneralPose3 scale interpolation is not representable");
            }
            return {rotation, translation, scale};
        }

    } // namespace

    void bind_general_pose3(nb::module_& m) {
        nb::class_<GeneralPose3>(m, "GeneralPose3")
            .def(nb::init<>())
            .def(
                "__init__",
                [](GeneralPose3* self, std::optional<Quat> ang, std::optional<Vec3> lin, std::optional<Vec3> scale) {
                    new (self) GeneralPose3{ang.value_or(Quat::identity()),
                                            lin.value_or(Vec3::zero()),
                                            scale.value_or(Vec3{1.0, 1.0, 1.0})};
                },
                nb::arg("ang").none() = nb::none(),
                nb::arg("lin").none() = nb::none(),
                nb::arg("scale").none() = nb::none())
            .def_prop_rw(
                "ang",
                [](const GeneralPose3& p) { return p.ang; },
                [](GeneralPose3& p, const Quat& val) { p.ang = val; })
            .def_prop_rw(
                "lin",
                [](const GeneralPose3& p) { return p.lin; },
                [](GeneralPose3& p, const Vec3& val) { p.lin = val; })
            .def_prop_rw(
                "scale",
                [](const GeneralPose3& p) { return p.scale; },
                [](GeneralPose3& p, const Vec3& val) { p.scale = val; })
            .def("compose_trs_projected",
                 &checked_general_pose3_compose,
                 nb::arg("child"),
                 "Compose and project the affine result back to TRS; may lose shear.")
            .def("compose_trs_projected",
                 &checked_general_pose3_compose_pose,
                 nb::arg("child"),
                 "Compose and project the affine result back to TRS; may lose shear.")
            .def("inverse_trs_projected",
                 &checked_general_pose3_inverse,
                 "Invert and project the affine result back to TRS; may lose shear.")
            .def("transform_point", &checked_general_pose3_transform_point)
            .def("transform_vector", &checked_general_pose3_transform_vector)
            .def("transform_direction", &checked_general_pose3_transform_direction)
            .def("rotate_point", &checked_general_pose3_transform_vector)
            .def("inverse_transform_point", &checked_general_pose3_inverse_transform_point)
            .def("inverse_transform_vector", &checked_general_pose3_inverse_transform_vector)
            .def("inverse_transform_direction", &checked_general_pose3_inverse_transform_direction)
            .def("point_to_global", &checked_general_pose3_transform_point)
            .def("vector_to_global", &checked_general_pose3_transform_vector)
            .def("direction_to_global", &checked_general_pose3_transform_direction)
            .def("point_to_local", &checked_general_pose3_inverse_transform_point)
            .def("vector_to_local", &checked_general_pose3_inverse_transform_vector)
            .def("direction_to_local", &checked_general_pose3_inverse_transform_direction)
            .def("forward_in_global", checked_general_pose3_direction(Vec3::unit_y(), false), nb::arg("distance") = 1.0)
            .def("backward_in_global",
                 checked_general_pose3_direction(-Vec3::unit_y(), false),
                 nb::arg("distance") = 1.0)
            .def("up_in_global", checked_general_pose3_direction(Vec3::unit_z(), false), nb::arg("distance") = 1.0)
            .def("down_in_global", checked_general_pose3_direction(-Vec3::unit_z(), false), nb::arg("distance") = 1.0)
            .def("right_in_global", checked_general_pose3_direction(Vec3::unit_x(), false), nb::arg("distance") = 1.0)
            .def("left_in_global", checked_general_pose3_direction(-Vec3::unit_x(), false), nb::arg("distance") = 1.0)
            .def("global_forward_in_local",
                 checked_general_pose3_direction(Vec3::unit_y(), true),
                 nb::arg("distance") = 1.0)
            .def("global_backward_in_local",
                 checked_general_pose3_direction(-Vec3::unit_y(), true),
                 nb::arg("distance") = 1.0)
            .def("global_up_in_local", checked_general_pose3_direction(Vec3::unit_z(), true), nb::arg("distance") = 1.0)
            .def("global_down_in_local",
                 checked_general_pose3_direction(-Vec3::unit_z(), true),
                 nb::arg("distance") = 1.0)
            .def("global_right_in_local",
                 checked_general_pose3_direction(Vec3::unit_x(), true),
                 nb::arg("distance") = 1.0)
            .def("global_left_in_local",
                 checked_general_pose3_direction(-Vec3::unit_x(), true),
                 nb::arg("distance") = 1.0)
            .def("normalized",
                 [](const GeneralPose3& pose) {
                     Quat rotation;
                     if (!pose.ang.try_normalized(rotation)) {
                         throw nb::value_error("GeneralPose3 rotation cannot be normalized");
                     }
                     return GeneralPose3{rotation, pose.lin, pose.scale};
                 })
            .def("with_translation", nb::overload_cast<const Vec3&>(&GeneralPose3::with_translation, nb::const_))
            .def("with_rotation", &GeneralPose3::with_rotation)
            .def("with_scale", nb::overload_cast<const Vec3&>(&GeneralPose3::with_scale, nb::const_))
            .def("to_pose3", &GeneralPose3::to_pose3)
            .def("rotation_matrix",
                 [](const GeneralPose3& p) {
                     double data[9];
                     checked_general_pose3_rotation_matrix(p, data);
                     return mat33_row_tuple(data);
                 })
            .def("rotation_mat33",
                 [](const GeneralPose3& p) {
                     double data[9];
                     checked_general_pose3_rotation_matrix(p, data);
                     Mat33 mat;
                     for (int row = 0; row < 3; ++row)
                         for (int col = 0; col < 3; ++col)
                             mat(col, row) = data[row * 3 + col];
                     return mat;
                 })
            .def("as_matrix",
                 [](const GeneralPose3& p) {
                     double data[16];
                     double matrix[16];
                     checked_general_pose3(p).matrix4(matrix);
                     for (int row = 0; row < 4; ++row)
                         for (int col = 0; col < 4; ++col)
                             data[row * 4 + col] = matrix[col * 4 + row];
                     return mat44_row_tuple(data);
                 })
            .def("as_mat44",
                 [](const GeneralPose3& p) {
                     Mat44 matrix;
                     checked_general_pose3(p).matrix4(matrix.data);
                     return matrix;
                 })
            .def("as_matrix34",
                 [](const GeneralPose3& p) {
                     double data[12];
                     double matrix[12];
                     checked_general_pose3(p).matrix34(matrix);
                     for (int row = 0; row < 3; ++row)
                         for (int col = 0; col < 4; ++col)
                             data[row * 4 + col] = matrix[col * 3 + row];
                     return mat34_row_tuple(data);
                 })
            .def("inverse_matrix",
                 [](const GeneralPose3& p) {
                     double data[16];
                     double matrix[16];
                     checked_general_pose3(p).inverse_matrix4(matrix);
                     for (int row = 0; row < 4; ++row)
                         for (int col = 0; col < 4; ++col)
                             data[row * 4 + col] = matrix[col * 4 + row];
                     return mat44_row_tuple(data);
                 })
            .def_static("identity", &GeneralPose3::identity)
            .def_static("translation", nb::overload_cast<double, double, double>(&GeneralPose3::translation))
            .def_static("translation", nb::overload_cast<const Vec3&>(&GeneralPose3::translation))
            .def_static("rotation", &checked_general_pose3_from_axis_angle)
            .def_static("scaling", nb::overload_cast<double>(&GeneralPose3::scaling))
            .def_static("scaling", nb::overload_cast<double, double, double>(&GeneralPose3::scaling))
            .def_static("rotate_x",
                        [](double angle) { return checked_general_pose3_from_axis_angle(Vec3::unit_x(), angle); })
            .def_static("rotate_y",
                        [](double angle) { return checked_general_pose3_from_axis_angle(Vec3::unit_y(), angle); })
            .def_static("rotate_z",
                        [](double angle) { return checked_general_pose3_from_axis_angle(Vec3::unit_z(), angle); })
            // Python-style aliases (rotateX instead of rotate_x)
            .def_static("rotateX",
                        [](double angle) { return checked_general_pose3_from_axis_angle(Vec3::unit_x(), angle); })
            .def_static("rotateY",
                        [](double angle) { return checked_general_pose3_from_axis_angle(Vec3::unit_y(), angle); })
            .def_static("rotateZ",
                        [](double angle) { return checked_general_pose3_from_axis_angle(Vec3::unit_z(), angle); })
            .def("copy", [](const GeneralPose3& p) { return p; })
            .def_static("move", &GeneralPose3::move)
            .def_static("move_x", &GeneralPose3::move_x)
            .def_static("move_y", &GeneralPose3::move_y)
            .def_static("move_z", &GeneralPose3::move_z)
            .def_static("right", &GeneralPose3::right)
            .def_static("forward", &GeneralPose3::forward)
            .def_static("up", &GeneralPose3::up)
            .def_static(
                "looking_at",
                [](const Vec3& eye, const Vec3& target, std::optional<Vec3> up_vec) {
                    return GeneralPose3::looking_at(eye, target, up_vec.value_or(Vec3{0.0, 0.0, 1.0}));
                },
                nb::arg("eye"),
                nb::arg("target"),
                nb::arg("up_vec").none() = nb::none())
            .def_static("lerp", &checked_general_pose3_lerp, "Linear interpolation between GeneralPose3 (with scale)")
            .def_static("from_matrix",
                        [](const Mat44& mat) {
                            double buf[16];
                            for (int row = 0; row < 4; ++row) {
                                for (int col = 0; col < 4; ++col) {
                                    buf[row * 4 + col] = mat(col, row);
                                }
                            }
                            // Extract translation from 4th column
                            Vec3 lin{buf[0 * 4 + 3], buf[1 * 4 + 3], buf[2 * 4 + 3]};

                            // Extract column vectors of upper-left 3x3 for scale
                            Vec3 col0{buf[0 * 4 + 0], buf[1 * 4 + 0], buf[2 * 4 + 0]};
                            Vec3 col1{buf[0 * 4 + 1], buf[1 * 4 + 1], buf[2 * 4 + 1]};
                            Vec3 col2{buf[0 * 4 + 2], buf[1 * 4 + 2], buf[2 * 4 + 2]};

                            // Scale is the length of each column
                            Vec3 scale{col0.norm(), col1.norm(), col2.norm()};

                            // Build rotation matrix by dividing out scale
                            double rot[9];
                            if (scale.x > 1e-10) {
                                rot[0] = col0.x / scale.x;
                                rot[3] = col0.y / scale.x;
                                rot[6] = col0.z / scale.x;
                            } else {
                                rot[0] = 1;
                                rot[3] = 0;
                                rot[6] = 0;
                            }
                            if (scale.y > 1e-10) {
                                rot[1] = col1.x / scale.y;
                                rot[4] = col1.y / scale.y;
                                rot[7] = col1.z / scale.y;
                            } else {
                                rot[1] = 0;
                                rot[4] = 1;
                                rot[7] = 0;
                            }
                            if (scale.z > 1e-10) {
                                rot[2] = col2.x / scale.z;
                                rot[5] = col2.y / scale.z;
                                rot[8] = col2.z / scale.z;
                            } else {
                                rot[2] = 0;
                                rot[5] = 0;
                                rot[8] = 1;
                            }

                            // Convert rotation matrix to quaternion
                            Quat q = Quat::from_rotation_matrix(rot);

                            return GeneralPose3(q, lin, scale);
                        })
            .def("__repr__", [](const GeneralPose3& p) {
                return "GeneralPose3(ang=Quat(" + std::to_string(p.ang.x) + ", " + std::to_string(p.ang.y) + ", " +
                       std::to_string(p.ang.z) + ", " + std::to_string(p.ang.w) + "), lin=Vec3(" +
                       std::to_string(p.lin.x) + ", " + std::to_string(p.lin.y) + ", " + std::to_string(p.lin.z) +
                       "), scale=Vec3(" + std::to_string(p.scale.x) + ", " + std::to_string(p.scale.y) + ", " +
                       std::to_string(p.scale.z) + "))";
            });

        m.def("lerp_general_pose3",
              &checked_general_pose3_lerp,
              "Linear interpolation between GeneralPose3 (with scale)");
    }

} // namespace termin
