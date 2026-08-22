#include "common.hpp"

#include <optional>

namespace termin {

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
            .def("rotate", &Quat::rotate)
            .def("inverse_rotate", &Quat::inverse_rotate)
            .def_static("identity", &Quat::identity)
            .def_static("from_axis_angle", &Quat::from_axis_angle)
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
