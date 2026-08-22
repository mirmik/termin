#include "common.hpp"

#include <optional>

namespace termin {

    void bind_vec4(nb::module_& m) {
        nb::class_<Vec4>(m, "Vec4")
            .def(nb::init<>())
            .def(nb::init<double, double, double, double>())
            .def("__init__", [](Vec4* self, nb::object obj) { new (self) Vec4(sequence_to_vec4(obj)); })
            .def_rw("x", &Vec4::x)
            .def_rw("y", &Vec4::y)
            .def_rw("z", &Vec4::z)
            .def_rw("w", &Vec4::w)
            .def("__getitem__", [](const Vec4& v, int i) { return v[i]; })
            .def("__setitem__", [](Vec4& v, int i, double val) { v[i] = val; })
            .def("__len__", [](const Vec4&) { return 4; })
            .def("__iter__", [](const Vec4& v) { return nb::iter(nb::make_tuple(v.x, v.y, v.z, v.w)); })
            .def(nb::self + nb::self)
            .def(nb::self - nb::self)
            .def(nb::self * double())
            .def(double() * nb::self)
            .def(nb::self / double())
            .def(-nb::self)
            .def("dot", &Vec4::dot)
            .def("norm", &Vec4::norm)
            .def("norm_squared", &Vec4::norm_squared)
            .def("normalized", &Vec4::normalized)
            .def(
                "try_normalized",
                [](const Vec4& value, double epsilon) -> std::optional<Vec4> {
                    Vec4 normalized;
                    if (!value.try_normalized(normalized, epsilon)) {
                        return std::nullopt;
                    }
                    return normalized;
                },
                nb::arg("epsilon") = 1.0e-10)
            .def("normalized_or", &Vec4::normalized_or, nb::arg("fallback"), nb::arg("epsilon") = 1.0e-10)
            .def("is_finite", &Vec4::is_finite)
            .def("to_float", &Vec4::to_float)
            .def_static("zero", &Vec4::zero)
            .def_static("unit_x", &Vec4::unit_x)
            .def_static("unit_y", &Vec4::unit_y)
            .def_static("unit_z", &Vec4::unit_z)
            .def_static("unit_w", &Vec4::unit_w)
            .def("tolist",
                 [](const Vec4& v) {
                     nb::list lst;
                     lst.append(v.x);
                     lst.append(v.y);
                     lst.append(v.z);
                     lst.append(v.w);
                     return lst;
                 })
            .def("copy", [](const Vec4& v) { return v; })
            .def("__eq__", &Vec4::operator==)
            .def("__ne__", &Vec4::operator!=)
            .def("__repr__", [](const Vec4& v) {
                return "Vec4(" + std::to_string(v.x) + ", " + std::to_string(v.y) + ", " + std::to_string(v.z) + ", " +
                       std::to_string(v.w) + ")";
            });

        nb::class_<Vec4f>(m, "Vec4f")
            .def(nb::init<>())
            .def(nb::init<float, float, float, float>())
            .def("__init__", [](Vec4f* self, nb::object obj) { new (self) Vec4f(sequence_to_vec4f(obj)); })
            .def_rw("x", &Vec4f::x)
            .def_rw("y", &Vec4f::y)
            .def_rw("z", &Vec4f::z)
            .def_rw("w", &Vec4f::w)
            .def("__getitem__", [](const Vec4f& v, int i) { return v[i]; })
            .def("__setitem__", [](Vec4f& v, int i, float value) { v[i] = value; })
            .def("__len__", [](const Vec4f&) { return 4; })
            .def("__iter__", [](const Vec4f& v) { return nb::iter(nb::make_tuple(v.x, v.y, v.z, v.w)); })
            .def(nb::self + nb::self)
            .def(nb::self - nb::self)
            .def(nb::self * float())
            .def(float() * nb::self)
            .def(nb::self / float())
            .def(-nb::self)
            .def("dot", &Vec4f::dot)
            .def("norm", &Vec4f::norm)
            .def("norm_squared", &Vec4f::norm_squared)
            .def("normalized", &Vec4f::normalized)
            .def(
                "try_normalized",
                [](const Vec4f& value, float epsilon) -> std::optional<Vec4f> {
                    Vec4f normalized;
                    if (!value.try_normalized(normalized, epsilon)) {
                        return std::nullopt;
                    }
                    return normalized;
                },
                nb::arg("epsilon") = 1.0e-6f)
            .def("normalized_or", &Vec4f::normalized_or, nb::arg("fallback"), nb::arg("epsilon") = 1.0e-6f)
            .def("is_finite", &Vec4f::is_finite)
            .def("to_double", &Vec4f::to_double)
            .def_static("zero", &Vec4f::zero)
            .def_static("unit_x", &Vec4f::unit_x)
            .def_static("unit_y", &Vec4f::unit_y)
            .def_static("unit_z", &Vec4f::unit_z)
            .def_static("unit_w", &Vec4f::unit_w)
            .def("tolist",
                 [](const Vec4f& v) {
                     nb::list result;
                     result.append(v.x);
                     result.append(v.y);
                     result.append(v.z);
                     result.append(v.w);
                     return result;
                 })
            .def("copy", [](const Vec4f& v) { return v; })
            .def("__eq__", &Vec4f::operator==)
            .def("__ne__", &Vec4f::operator!=)
            .def("__repr__", [](const Vec4f& v) {
                return "Vec4f(" + std::to_string(v.x) + ", " + std::to_string(v.y) + ", " + std::to_string(v.z) +
                       ", " + std::to_string(v.w) + ")";
            });
    }

} // namespace termin
