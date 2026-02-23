#include "common.hpp"
#include "termin/render/wireframe_renderer.hpp"
#include "tgfx/graphics_backend.hpp"

namespace termin {

void bind_wireframe(nb::module_& m) {
    nb::class_<WireframeRenderer>(m, "WireframeRenderer")
        .def(nb::init<>())
        .def("begin", [](WireframeRenderer& self,
                         GraphicsBackend* graphics,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> proj,
                         bool depth_test) {
            Mat44f view_mat, proj_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    view_mat.data[col * 4 + row] = view(row, col);
                    proj_mat.data[col * 4 + row] = proj(row, col);
                }
            }

            self.begin(graphics, view_mat, proj_mat, depth_test);
        },
             nb::arg("graphics"),
             nb::arg("view"),
             nb::arg("proj"),
             nb::arg("depth_test") = false,
             "Begin wireframe rendering")
        .def("end", &WireframeRenderer::end,
             "End wireframe rendering")
        .def("draw_circle", [](WireframeRenderer& self,
                               nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                               nb::tuple color) {
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat.data[col * 4 + row] = model(row, col);
                }
            }

            Color4 c{
                nb::cast<float>(color[0]),
                nb::cast<float>(color[1]),
                nb::cast<float>(color[2]),
                nb::cast<float>(color[3])
            };

            self.draw_circle(model_mat, c);
        },
             nb::arg("model"), nb::arg("color"),
             "Draw a circle")
        .def("draw_arc", [](WireframeRenderer& self,
                            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                            nb::tuple color) {
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat.data[col * 4 + row] = model(row, col);
                }
            }

            Color4 c{
                nb::cast<float>(color[0]),
                nb::cast<float>(color[1]),
                nb::cast<float>(color[2]),
                nb::cast<float>(color[3])
            };

            self.draw_arc(model_mat, c);
        },
             nb::arg("model"), nb::arg("color"),
             "Draw an arc (half-circle)")
        .def("draw_box", [](WireframeRenderer& self,
                            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                            nb::tuple color) {
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat.data[col * 4 + row] = model(row, col);
                }
            }

            Color4 c{
                nb::cast<float>(color[0]),
                nb::cast<float>(color[1]),
                nb::cast<float>(color[2]),
                nb::cast<float>(color[3])
            };

            self.draw_box(model_mat, c);
        },
             nb::arg("model"), nb::arg("color"),
             "Draw a wireframe box")
        .def("draw_line", [](WireframeRenderer& self,
                             nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                             nb::tuple color) {
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat.data[col * 4 + row] = model(row, col);
                }
            }

            Color4 c{
                nb::cast<float>(color[0]),
                nb::cast<float>(color[1]),
                nb::cast<float>(color[2]),
                nb::cast<float>(color[3])
            };

            self.draw_line(model_mat, c);
        },
             nb::arg("model"), nb::arg("color"),
             "Draw a line")
        .def_prop_ro("initialized", &WireframeRenderer::initialized);

    // Matrix helper functions
    m.def("mat4_identity", &mat4_identity, "Create identity 4x4 matrix");

    m.def("mat4_translate", [](float x, float y, float z) {
        Mat44f m = mat4_translate(x, y, z);
        float* data = new float[16];
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                data[row * 4 + col] = m.data[col * 4 + row];
            }
        }
        nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
        return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, {4, 4}, owner);
    }, nb::arg("x"), nb::arg("y"), nb::arg("z"), "Create translation matrix");

    m.def("mat4_scale", [](float sx, float sy, float sz) {
        Mat44f m = mat4_scale(sx, sy, sz);
        float* data = new float[16];
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                data[row * 4 + col] = m.data[col * 4 + row];
            }
        }
        nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
        return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, {4, 4}, owner);
    }, nb::arg("sx"), nb::arg("sy"), nb::arg("sz"), "Create scale matrix");

    m.def("mat4_scale_uniform", [](float s) {
        Mat44f m = mat4_scale_uniform(s);
        float* data = new float[16];
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                data[row * 4 + col] = m.data[col * 4 + row];
            }
        }
        nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
        return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, {4, 4}, owner);
    }, nb::arg("s"), "Create uniform scale matrix");

    m.def("mat4_from_rotation_matrix", [](nb::ndarray<nb::numpy, float, nb::shape<3, 3>> rot3x3) {
        float rot[9];
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                rot[i * 3 + j] = rot3x3(i, j);
            }
        }
        Mat44f m = mat4_from_rotation_matrix(rot);
        float* data = new float[16];
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                data[row * 4 + col] = m.data[col * 4 + row];
            }
        }
        nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
        return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, {4, 4}, owner);
    }, nb::arg("rot3x3"), "Create 4x4 matrix from 3x3 rotation matrix");

    m.def("rotation_matrix_align_z_to_axis", [](nb::ndarray<nb::numpy, float, nb::shape<3>> axis) {
        float axis_arr[3] = {axis(0), axis(1), axis(2)};
        float rot[9];
        rotation_matrix_align_z_to_axis(axis_arr, rot);
        float* data = new float[9];
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                data[i * 3 + j] = rot[i * 3 + j];
            }
        }
        nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
        return nb::ndarray<nb::numpy, float, nb::shape<3, 3>>(data, {3, 3}, owner);
    }, nb::arg("axis"), "Build rotation matrix that aligns Z axis to given axis");
}

} // namespace termin
