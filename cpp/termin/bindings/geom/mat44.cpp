#include "common.hpp"
#include <nanobind/stl/pair.h>

namespace termin {

void bind_mat44(nb::module_& m) {
    nb::class_<Mat44>(m, "Mat44")
        .def(nb::init<>())
        .def("__call__", [](const Mat44& m, int col, int row) { return m(col, row); })
        .def("__getitem__", [](const Mat44& m, std::pair<int, int> idx) {
            return m(idx.first, idx.second);
        })
        .def("__setitem__", [](Mat44& m, std::pair<int, int> idx, double val) {
            m(idx.first, idx.second) = val;
        })
        .def(nb::self * nb::self)
        .def("transform_point", &Mat44::transform_point)
        .def("transform_direction", &Mat44::transform_direction)
        .def("transposed", &Mat44::transposed)
        .def("inverse", &Mat44::inverse)
        .def("get_translation", &Mat44::get_translation)
        .def("get_scale", &Mat44::get_scale)
        .def_static("identity", &Mat44::identity)
        .def_static("zero", &Mat44::zero)
        .def_static("translation", nb::overload_cast<const Vec3&>(&Mat44::translation))
        .def_static("translation", nb::overload_cast<double, double, double>(&Mat44::translation))
        .def_static("scale", nb::overload_cast<const Vec3&>(&Mat44::scale))
        .def_static("scale", nb::overload_cast<double>(&Mat44::scale))
        .def_static("rotation", &Mat44::rotation)
        .def_static("rotation_axis_angle", &Mat44::rotation_axis_angle)
        .def_static("perspective", &Mat44::perspective,
            nb::arg("fov_y"), nb::arg("aspect"), nb::arg("near"), nb::arg("far"),
            "Perspective projection (Y-forward, Z-up)")
        .def_static("orthographic", &Mat44::orthographic,
            nb::arg("left"), nb::arg("right"), nb::arg("bottom"), nb::arg("top"),
            nb::arg("near"), nb::arg("far"),
            "Orthographic projection (Y-forward, Z-up)")
        .def_static("look_at", &Mat44::look_at,
            nb::arg("eye"), nb::arg("target"), nb::arg("up") = Vec3::unit_z(),
            "Look-at view matrix (Y-forward, Z-up)")
        .def_static("compose", &Mat44::compose,
            nb::arg("translation"), nb::arg("rotation"), nb::arg("scale"),
            "Compose TRS matrix")
        .def("to_numpy", [](const Mat44& mat) {
            double* data = new double[16];
            for (int col = 0; col < 4; ++col) {
                for (int row = 0; row < 4; ++row) {
                    data[row * 4 + col] = mat(col, row);
                }
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, 2, shape, owner);
        })
        .def("to_numpy_f32", [](const Mat44& mat) {
            float* data = new float[16];
            for (int col = 0; col < 4; ++col) {
                for (int row = 0; row < 4; ++row) {
                    data[row * 4 + col] = static_cast<float>(mat(col, row));
                }
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, 2, shape, owner);
        })
        .def("__repr__", [](const Mat44& m) {
            return "<Mat44>";
        });
}

} // namespace termin
