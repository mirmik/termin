#include "common.hpp"
#include <nanobind/stl/optional.h>
#include <nanobind/stl/array.h>
#include "termin/render/shadow_camera.hpp"

namespace termin {

void bind_shadow(nb::module_& m) {
    nb::class_<ShadowCameraParams>(m, "ShadowCameraParams")
        .def(nb::init<>())
        .def("__init__", [](ShadowCameraParams* self,
            nb::ndarray<nb::numpy, double, nb::shape<3>> light_direction,
            nb::object ortho_bounds,
            double ortho_size,
            double near,
            double far,
            nb::object center
        ) {
            Vec3 light_dir{
                light_direction(0),
                light_direction(1),
                light_direction(2)
            };

            std::optional<std::array<float, 4>> bounds;
            if (!ortho_bounds.is_none()) {
                nb::tuple t = nb::cast<nb::tuple>(ortho_bounds);
                bounds = std::array<float, 4>{
                    static_cast<float>(nb::cast<double>(t[0])),
                    static_cast<float>(nb::cast<double>(t[1])),
                    static_cast<float>(nb::cast<double>(t[2])),
                    static_cast<float>(nb::cast<double>(t[3]))
                };
            }

            Vec3 c{0, 0, 0};
            if (!center.is_none()) {
                nb::ndarray<nb::numpy, double, nb::shape<3>> arr = nb::cast<nb::ndarray<nb::numpy, double, nb::shape<3>>>(center);
                c = Vec3{arr(0), arr(1), arr(2)};
            }

            new (self) ShadowCameraParams(light_dir, bounds, static_cast<float>(ortho_size), static_cast<float>(near), static_cast<float>(far), c);
        },
            nb::arg("light_direction"),
            nb::arg("ortho_bounds") = nb::none(),
            nb::arg("ortho_size") = 20.0,
            nb::arg("near") = 0.1,
            nb::arg("far") = 100.0,
            nb::arg("center") = nb::none()
        )
        // Properties
        .def_prop_rw("light_direction",
            [](const ShadowCameraParams& self) {
                double* data = new double[3]{self.light_direction.x, self.light_direction.y, self.light_direction.z};
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
                return nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner);
            },
            [](ShadowCameraParams& self, nb::ndarray<nb::numpy, double, nb::shape<3>> arr) {
                self.light_direction = Vec3{arr(0), arr(1), arr(2)}.normalized();
            }
        )
        .def_prop_rw("ortho_bounds",
            [](const ShadowCameraParams& self) -> nb::object {
                if (self.ortho_bounds) {
                    auto& b = *self.ortho_bounds;
                    return nb::make_tuple(b[0], b[1], b[2], b[3]);
                }
                return nb::none();
            },
            [](ShadowCameraParams& self, nb::object val) {
                if (val.is_none()) {
                    self.ortho_bounds = std::nullopt;
                } else {
                    nb::tuple t = nb::cast<nb::tuple>(val);
                    self.ortho_bounds = std::array<float, 4>{
                        static_cast<float>(nb::cast<double>(t[0])),
                        static_cast<float>(nb::cast<double>(t[1])),
                        static_cast<float>(nb::cast<double>(t[2])),
                        static_cast<float>(nb::cast<double>(t[3]))
                    };
                }
            }
        )
        .def_rw("ortho_size", &ShadowCameraParams::ortho_size)
        .def_rw("near", &ShadowCameraParams::near)
        .def_rw("far", &ShadowCameraParams::far)
        .def_prop_rw("center",
            [](const ShadowCameraParams& self) {
                double* data = new double[3]{self.center.x, self.center.y, self.center.z};
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
                return nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner);
            },
            [](ShadowCameraParams& self, nb::ndarray<nb::numpy, double, nb::shape<3>> arr) {
                self.center = Vec3{arr(0), arr(1), arr(2)};
            }
        );

    m.def("build_shadow_view_matrix", [](const ShadowCameraParams& params) {
        Mat44f mat = build_shadow_view_matrix(params);
        double* data = new double[16];
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                data[row * 4 + col] = static_cast<double>(mat.data[col * 4 + row]);
            }
        }
        nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
        return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, {4, 4}, owner);
    }, nb::arg("params"), "Build view matrix for shadow camera");

    m.def("build_shadow_projection_matrix", [](const ShadowCameraParams& params) {
        Mat44f mat = build_shadow_projection_matrix(params);
        double* data = new double[16];
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                data[row * 4 + col] = static_cast<double>(mat.data[col * 4 + row]);
            }
        }
        nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
        return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, {4, 4}, owner);
    }, nb::arg("params"), "Build orthographic projection matrix for shadow camera");

    m.def("compute_light_space_matrix", [](const ShadowCameraParams& params) {
        Mat44f mat = compute_light_space_matrix(params);
        double* data = new double[16];
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                data[row * 4 + col] = static_cast<double>(mat.data[col * 4 + row]);
            }
        }
        nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
        return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, {4, 4}, owner);
    }, nb::arg("params"), "Compute combined light space matrix (projection * view)");

    m.def("compute_frustum_corners", [](
        nb::ndarray<nb::numpy, double, nb::shape<4, 4>> view,
        nb::ndarray<nb::numpy, double, nb::shape<4, 4>> proj
    ) {
        Mat44f view_mat, proj_mat;
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                view_mat.data[col * 4 + row] = static_cast<float>(view(row, col));
                proj_mat.data[col * 4 + row] = static_cast<float>(proj(row, col));
            }
        }

        auto corners = compute_frustum_corners(view_mat, proj_mat);

        double* data = new double[24];
        for (int i = 0; i < 8; ++i) {
            data[i * 3 + 0] = corners[i].x;
            data[i * 3 + 1] = corners[i].y;
            data[i * 3 + 2] = corners[i].z;
        }
        nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
        return nb::ndarray<nb::numpy, double, nb::shape<8, 3>>(data, {8, 3}, owner);
    }, nb::arg("view_matrix"), nb::arg("projection_matrix"),
       "Compute 8 corners of view frustum in world space");

    m.def("fit_shadow_frustum_to_camera", [](
        nb::ndarray<nb::numpy, double, nb::shape<4, 4>> view,
        nb::ndarray<nb::numpy, double, nb::shape<4, 4>> proj,
        nb::ndarray<nb::numpy, double, nb::shape<3>> light_direction,
        double padding,
        int shadow_map_resolution,
        bool stabilize,
        double caster_offset
    ) {
        Mat44f view_mat, proj_mat;
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                view_mat.data[col * 4 + row] = static_cast<float>(view(row, col));
                proj_mat.data[col * 4 + row] = static_cast<float>(proj(row, col));
            }
        }

        Vec3 light_dir{light_direction(0), light_direction(1), light_direction(2)};

        return fit_shadow_frustum_to_camera(
            view_mat, proj_mat, light_dir,
            static_cast<float>(padding), shadow_map_resolution, stabilize, static_cast<float>(caster_offset)
        );
    },
        nb::arg("view_matrix"),
        nb::arg("projection_matrix"),
        nb::arg("light_direction"),
        nb::arg("padding") = 1.0,
        nb::arg("shadow_map_resolution") = 1024,
        nb::arg("stabilize") = true,
        nb::arg("caster_offset") = 50.0,
        "Fit shadow camera to view frustum"
    );
}

} // namespace termin
