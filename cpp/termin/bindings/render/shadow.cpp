#include "common.hpp"
#include "termin/render/shadow_camera.hpp"

namespace termin {

void bind_shadow(py::module_& m) {
    py::class_<ShadowCameraParams>(m, "ShadowCameraParams")
        .def(py::init<>())
        .def(py::init([](
            py::array_t<double> light_direction,
            py::object ortho_bounds,
            double ortho_size,
            double near,
            double far,
            py::object center
        ) {
            auto dir_buf = light_direction.request();
            Vec3 light_dir{
                static_cast<double*>(dir_buf.ptr)[0],
                static_cast<double*>(dir_buf.ptr)[1],
                static_cast<double*>(dir_buf.ptr)[2]
            };

            std::optional<std::array<float, 4>> bounds;
            if (!ortho_bounds.is_none()) {
                auto t = ortho_bounds.cast<py::tuple>();
                bounds = std::array<float, 4>{
                    static_cast<float>(t[0].cast<double>()),
                    static_cast<float>(t[1].cast<double>()),
                    static_cast<float>(t[2].cast<double>()),
                    static_cast<float>(t[3].cast<double>())
                };
            }

            Vec3 c{0, 0, 0};
            if (!center.is_none()) {
                auto arr = center.cast<py::array_t<double>>();
                auto buf = arr.request();
                c = Vec3{
                    static_cast<double*>(buf.ptr)[0],
                    static_cast<double*>(buf.ptr)[1],
                    static_cast<double*>(buf.ptr)[2]
                };
            }

            return ShadowCameraParams(light_dir, bounds, static_cast<float>(ortho_size), static_cast<float>(near), static_cast<float>(far), c);
        }),
            py::arg("light_direction"),
            py::arg("ortho_bounds") = py::none(),
            py::arg("ortho_size") = 20.0,
            py::arg("near") = 0.1,
            py::arg("far") = 100.0,
            py::arg("center") = py::none()
        )
        // Properties
        .def_property("light_direction",
            [](const ShadowCameraParams& self) {
                return py::array_t<double>({3}, {sizeof(double)},
                    &self.light_direction.x);
            },
            [](ShadowCameraParams& self, py::array_t<double> arr) {
                auto buf = arr.request();
                auto* ptr = static_cast<double*>(buf.ptr);
                self.light_direction = Vec3{ptr[0], ptr[1], ptr[2]}.normalized();
            }
        )
        .def_property("ortho_bounds",
            [](const ShadowCameraParams& self) -> py::object {
                if (self.ortho_bounds) {
                    auto& b = *self.ortho_bounds;
                    return py::make_tuple(b[0], b[1], b[2], b[3]);
                }
                return py::none();
            },
            [](ShadowCameraParams& self, py::object val) {
                if (val.is_none()) {
                    self.ortho_bounds = std::nullopt;
                } else {
                    auto t = val.cast<py::tuple>();
                    self.ortho_bounds = std::array<float, 4>{
                        static_cast<float>(t[0].cast<double>()),
                        static_cast<float>(t[1].cast<double>()),
                        static_cast<float>(t[2].cast<double>()),
                        static_cast<float>(t[3].cast<double>())
                    };
                }
            }
        )
        .def_readwrite("ortho_size", &ShadowCameraParams::ortho_size)
        .def_readwrite("near", &ShadowCameraParams::near)
        .def_readwrite("far", &ShadowCameraParams::far)
        .def_property("center",
            [](const ShadowCameraParams& self) {
                return py::array_t<double>({3}, {sizeof(double)}, &self.center.x);
            },
            [](ShadowCameraParams& self, py::array_t<double> arr) {
                auto buf = arr.request();
                auto* ptr = static_cast<double*>(buf.ptr);
                self.center = Vec3{ptr[0], ptr[1], ptr[2]};
            }
        );

    m.def("build_shadow_view_matrix", [](const ShadowCameraParams& params) {
        Mat44f mat = build_shadow_view_matrix(params);
        py::array_t<double> result({4, 4});
        auto buf = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                buf(row, col) = static_cast<double>(mat.data[col * 4 + row]);
            }
        }
        return result;
    }, py::arg("params"), "Build view matrix for shadow camera");

    m.def("build_shadow_projection_matrix", [](const ShadowCameraParams& params) {
        Mat44f mat = build_shadow_projection_matrix(params);
        py::array_t<double> result({4, 4});
        auto buf = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                buf(row, col) = static_cast<double>(mat.data[col * 4 + row]);
            }
        }
        return result;
    }, py::arg("params"), "Build orthographic projection matrix for shadow camera");

    m.def("compute_light_space_matrix", [](const ShadowCameraParams& params) {
        Mat44f mat = compute_light_space_matrix(params);
        py::array_t<double> result({4, 4});
        auto buf = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                buf(row, col) = static_cast<double>(mat.data[col * 4 + row]);
            }
        }
        return result;
    }, py::arg("params"), "Compute combined light space matrix (projection * view)");

    m.def("compute_frustum_corners", [](py::array_t<double> view, py::array_t<double> proj) {
        auto view_buf = view.unchecked<2>();
        auto proj_buf = proj.unchecked<2>();

        Mat44f view_mat, proj_mat;
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                view_mat.data[col * 4 + row] = static_cast<float>(view_buf(row, col));
                proj_mat.data[col * 4 + row] = static_cast<float>(proj_buf(row, col));
            }
        }

        auto corners = compute_frustum_corners(view_mat, proj_mat);

        py::array_t<double> result({8, 3});
        auto buf = result.mutable_unchecked<2>();
        for (int i = 0; i < 8; ++i) {
            buf(i, 0) = corners[i].x;
            buf(i, 1) = corners[i].y;
            buf(i, 2) = corners[i].z;
        }
        return result;
    }, py::arg("view_matrix"), py::arg("projection_matrix"),
       "Compute 8 corners of view frustum in world space");

    m.def("fit_shadow_frustum_to_camera", [](
        py::array_t<double> view,
        py::array_t<double> proj,
        py::array_t<double> light_direction,
        double padding,
        int shadow_map_resolution,
        bool stabilize,
        double caster_offset
    ) {
        auto view_buf = view.unchecked<2>();
        auto proj_buf = proj.unchecked<2>();
        auto dir_buf = light_direction.request();

        Mat44f view_mat, proj_mat;
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                view_mat.data[col * 4 + row] = static_cast<float>(view_buf(row, col));
                proj_mat.data[col * 4 + row] = static_cast<float>(proj_buf(row, col));
            }
        }

        auto* dir_ptr = static_cast<double*>(dir_buf.ptr);
        Vec3 light_dir{dir_ptr[0], dir_ptr[1], dir_ptr[2]};

        return fit_shadow_frustum_to_camera(
            view_mat, proj_mat, light_dir,
            static_cast<float>(padding), shadow_map_resolution, stabilize, static_cast<float>(caster_offset)
        );
    },
        py::arg("view_matrix"),
        py::arg("projection_matrix"),
        py::arg("light_direction"),
        py::arg("padding") = 1.0,
        py::arg("shadow_map_resolution") = 1024,
        py::arg("stabilize") = true,
        py::arg("caster_offset") = 50.0,
        "Fit shadow camera to view frustum"
    );
}

} // namespace termin
