#include "common.hpp"

namespace termin {

void bind_mat44(py::module_& m) {
    py::class_<Mat44>(m, "Mat44")
        .def(py::init<>())
        .def("__call__", [](const Mat44& m, int col, int row) { return m(col, row); })
        .def("__getitem__", [](const Mat44& m, std::pair<int, int> idx) {
            return m(idx.first, idx.second);
        })
        .def("__setitem__", [](Mat44& m, std::pair<int, int> idx, double val) {
            m(idx.first, idx.second) = val;
        })
        .def(py::self * py::self)
        .def("transform_point", &Mat44::transform_point)
        .def("transform_direction", &Mat44::transform_direction)
        .def("transposed", &Mat44::transposed)
        .def("inverse", &Mat44::inverse)
        .def("get_translation", &Mat44::get_translation)
        .def("get_scale", &Mat44::get_scale)
        .def_static("identity", &Mat44::identity)
        .def_static("zero", &Mat44::zero)
        .def_static("translation", py::overload_cast<const Vec3&>(&Mat44::translation))
        .def_static("translation", py::overload_cast<double, double, double>(&Mat44::translation))
        .def_static("scale", py::overload_cast<const Vec3&>(&Mat44::scale))
        .def_static("scale", py::overload_cast<double>(&Mat44::scale))
        .def_static("rotation", &Mat44::rotation)
        .def_static("rotation_axis_angle", &Mat44::rotation_axis_angle)
        .def_static("perspective", &Mat44::perspective,
            py::arg("fov_y"), py::arg("aspect"), py::arg("near"), py::arg("far"),
            "Perspective projection (Y-forward, Z-up)")
        .def_static("orthographic", &Mat44::orthographic,
            py::arg("left"), py::arg("right"), py::arg("bottom"), py::arg("top"),
            py::arg("near"), py::arg("far"),
            "Orthographic projection (Y-forward, Z-up)")
        .def_static("look_at", &Mat44::look_at,
            py::arg("eye"), py::arg("target"), py::arg("up") = Vec3::unit_z(),
            "Look-at view matrix (Y-forward, Z-up)")
        .def_static("compose", &Mat44::compose,
            py::arg("translation"), py::arg("rotation"), py::arg("scale"),
            "Compose TRS matrix")
        .def("to_numpy", [](const Mat44& m) {
            auto result = py::array_t<double>({4, 4});
            auto buf = result.mutable_unchecked<2>();
            for (int col = 0; col < 4; ++col) {
                for (int row = 0; row < 4; ++row) {
                    buf(row, col) = m(col, row);
                }
            }
            return result;
        })
        .def("to_numpy_f32", [](const Mat44& m) {
            auto result = py::array_t<float>({4, 4});
            auto buf = result.mutable_unchecked<2>();
            for (int col = 0; col < 4; ++col) {
                for (int row = 0; row < 4; ++row) {
                    buf(row, col) = static_cast<float>(m(col, row));
                }
            }
            return result;
        })
        .def("__repr__", [](const Mat44& m) {
            return "<Mat44>";
        });
}

} // namespace termin
