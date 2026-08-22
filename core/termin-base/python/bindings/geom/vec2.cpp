#include "common.hpp"

#include <optional>
#include <string>
#include <type_traits>

namespace termin {

    namespace {

        template <typename VecT, typename ScalarT> void bind_vec2_type(nb::module_& m, const char* name) {
            auto binding = nb::class_<VecT>(m, name);
            binding
                .def(nb::init<>())
                .def(nb::init<ScalarT, ScalarT>())
                .def_rw("x", &VecT::x)
                .def_rw("y", &VecT::y)
                .def("__getitem__", [](const VecT& v, int i) { return v[i]; })
                .def("__setitem__", [](VecT& v, int i, ScalarT val) { v[i] = val; })
                .def("__len__", [](const VecT&) { return 2; })
                .def("__iter__", [](const VecT& v) { return nb::iter(nb::make_tuple(v.x, v.y)); })
                .def(nb::self + nb::self)
                .def(nb::self - nb::self)
                .def(nb::self * ScalarT())
                .def(ScalarT() * nb::self)
                .def(nb::self / ScalarT())
                .def(-nb::self)
                .def("dot", &VecT::dot)
                .def("cross", &VecT::cross)
                .def("norm", &VecT::norm)
                .def("norm_squared", &VecT::norm_squared)
                .def("normalized", &VecT::normalized)
                .def(
                    "try_normalized",
                    [](const VecT& value, ScalarT epsilon) -> std::optional<VecT> {
                        VecT normalized;
                        if (!value.try_normalized(normalized, epsilon)) {
                            return std::nullopt;
                        }
                        return normalized;
                    },
                    nb::arg("epsilon") =
                        (std::is_same_v<ScalarT, float> ? ScalarT{1.0e-6f} : ScalarT{1.0e-10}))
                .def("normalized_or",
                     &VecT::normalized_or,
                     nb::arg("fallback"),
                     nb::arg("epsilon") =
                         (std::is_same_v<ScalarT, float> ? ScalarT{1.0e-6f} : ScalarT{1.0e-10}))
                .def("is_finite", &VecT::is_finite)
                .def("cwise_product", &VecT::cwise_product)
                .def("cwise_quotient", &VecT::cwise_quotient)
                .def("cwise_min", &VecT::cwise_min)
                .def("cwise_max", &VecT::cwise_max)
                .def("clamped", &VecT::clamped)
                .def("cwise_abs", &VecT::cwise_abs)
                .def("min_component", &VecT::min_component)
                .def("max_component", &VecT::max_component)
                .def_static("zero", &VecT::zero)
                .def_static("unit_x", &VecT::unit_x)
                .def_static("unit_y", &VecT::unit_y)
                .def("tolist",
                     [](const VecT& v) {
                         nb::list lst;
                         lst.append(v.x);
                         lst.append(v.y);
                         return lst;
                     })
                .def("copy", [](const VecT& v) { return v; })
                .def("__eq__", &VecT::operator==)
                .def("__ne__", &VecT::operator!=)
                .def("__repr__", [name](const VecT& v) {
                    return std::string(name) + "(" + std::to_string(v.x) + ", " + std::to_string(v.y) + ")";
                });
            if constexpr (std::is_same_v<ScalarT, float>) {
                binding.def("to_double", &VecT::to_double);
            } else {
                binding.def("to_float", &VecT::to_float);
            }
        }

        template <typename VecT> void bind_vec2i_type(nb::module_& m, const char* name) {
            nb::class_<VecT>(m, name)
                .def(nb::init<>())
                .def(nb::init<int, int>())
                .def_rw("x", &VecT::x)
                .def_rw("y", &VecT::y)
                .def("__getitem__", [](const VecT& v, int i) { return v[i]; })
                .def("__setitem__", [](VecT& v, int i, int val) { v[i] = val; })
                .def("__len__", [](const VecT&) { return 2; })
                .def("__iter__", [](const VecT& v) { return nb::iter(nb::make_tuple(v.x, v.y)); })
                .def(nb::self + nb::self)
                .def(nb::self - nb::self)
                .def(nb::self * int())
                .def(int() * nb::self)
                .def(nb::self / int())
                .def(-nb::self)
                .def("dot", &VecT::dot)
                .def("cross", &VecT::cross)
                .def_static("zero", &VecT::zero)
                .def_static("unit_x", &VecT::unit_x)
                .def_static("unit_y", &VecT::unit_y)
                .def("to_double", &VecT::to_double)
                .def("to_float", &VecT::to_float)
                .def("tolist",
                     [](const VecT& v) {
                         nb::list lst;
                         lst.append(v.x);
                         lst.append(v.y);
                         return lst;
                     })
                .def("copy", [](const VecT& v) { return v; })
                .def("__eq__", &VecT::operator==)
                .def("__ne__", &VecT::operator!=)
                .def("__repr__", [name](const VecT& v) {
                    return std::string(name) + "(" + std::to_string(v.x) + ", " + std::to_string(v.y) + ")";
                });
        }

    } // namespace

    void bind_vec2(nb::module_& m) {
        bind_vec2_type<Vec2, double>(m, "Vec2");
        bind_vec2_type<Vec2f, float>(m, "Vec2f");
        bind_vec2i_type<Vec2i>(m, "Vec2i");
    }

} // namespace termin
