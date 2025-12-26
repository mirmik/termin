#include "common.hpp"
#include "termin/render/wireframe_renderer.hpp"
#include "termin/render/graphics_backend.hpp"

namespace termin {

void bind_wireframe(py::module_& m) {
    py::class_<WireframeRenderer>(m, "WireframeRenderer")
        .def(py::init<>())
        .def("begin", [](WireframeRenderer& self,
                         GraphicsBackend* graphics,
                         py::array_t<float> view,
                         py::array_t<float> proj,
                         bool depth_test) {
            auto view_buf = view.unchecked<2>();
            auto proj_buf = proj.unchecked<2>();

            Mat44f view_mat, proj_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    view_mat.data[col * 4 + row] = view_buf(row, col);
                    proj_mat.data[col * 4 + row] = proj_buf(row, col);
                }
            }

            self.begin(graphics, view_mat, proj_mat, depth_test);
        },
             py::arg("graphics"),
             py::arg("view"),
             py::arg("proj"),
             py::arg("depth_test") = false,
             "Begin wireframe rendering")
        .def("end", &WireframeRenderer::end,
             "End wireframe rendering")
        .def("draw_circle", [](WireframeRenderer& self,
                               py::array_t<float> model,
                               py::tuple color) {
            auto model_buf = model.unchecked<2>();
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat.data[col * 4 + row] = model_buf(row, col);
                }
            }

            Color4 c{
                color[0].cast<float>(),
                color[1].cast<float>(),
                color[2].cast<float>(),
                color[3].cast<float>()
            };

            self.draw_circle(model_mat, c);
        },
             py::arg("model"), py::arg("color"),
             "Draw a circle")
        .def("draw_arc", [](WireframeRenderer& self,
                            py::array_t<float> model,
                            py::tuple color) {
            auto model_buf = model.unchecked<2>();
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat.data[col * 4 + row] = model_buf(row, col);
                }
            }

            Color4 c{
                color[0].cast<float>(),
                color[1].cast<float>(),
                color[2].cast<float>(),
                color[3].cast<float>()
            };

            self.draw_arc(model_mat, c);
        },
             py::arg("model"), py::arg("color"),
             "Draw an arc (half-circle)")
        .def("draw_box", [](WireframeRenderer& self,
                            py::array_t<float> model,
                            py::tuple color) {
            auto model_buf = model.unchecked<2>();
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat.data[col * 4 + row] = model_buf(row, col);
                }
            }

            Color4 c{
                color[0].cast<float>(),
                color[1].cast<float>(),
                color[2].cast<float>(),
                color[3].cast<float>()
            };

            self.draw_box(model_mat, c);
        },
             py::arg("model"), py::arg("color"),
             "Draw a wireframe box")
        .def("draw_line", [](WireframeRenderer& self,
                             py::array_t<float> model,
                             py::tuple color) {
            auto model_buf = model.unchecked<2>();
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat.data[col * 4 + row] = model_buf(row, col);
                }
            }

            Color4 c{
                color[0].cast<float>(),
                color[1].cast<float>(),
                color[2].cast<float>(),
                color[3].cast<float>()
            };

            self.draw_line(model_mat, c);
        },
             py::arg("model"), py::arg("color"),
             "Draw a line")
        .def_property_readonly("initialized", &WireframeRenderer::initialized);

    // Matrix helper functions
    m.def("mat4_identity", &mat4_identity, "Create identity 4x4 matrix");

    m.def("mat4_translate", [](float x, float y, float z) {
        Mat44f m = mat4_translate(x, y, z);
        py::array_t<float> result({4, 4});
        auto buf = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                buf(row, col) = m.data[col * 4 + row];
            }
        }
        return result;
    }, py::arg("x"), py::arg("y"), py::arg("z"), "Create translation matrix");

    m.def("mat4_scale", [](float sx, float sy, float sz) {
        Mat44f m = mat4_scale(sx, sy, sz);
        py::array_t<float> result({4, 4});
        auto buf = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                buf(row, col) = m.data[col * 4 + row];
            }
        }
        return result;
    }, py::arg("sx"), py::arg("sy"), py::arg("sz"), "Create scale matrix");

    m.def("mat4_scale_uniform", [](float s) {
        Mat44f m = mat4_scale_uniform(s);
        py::array_t<float> result({4, 4});
        auto buf = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                buf(row, col) = m.data[col * 4 + row];
            }
        }
        return result;
    }, py::arg("s"), "Create uniform scale matrix");

    m.def("mat4_from_rotation_matrix", [](py::array_t<float> rot3x3) {
        auto buf = rot3x3.unchecked<2>();
        float rot[9];
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                rot[i * 3 + j] = buf(i, j);
            }
        }
        Mat44f m = mat4_from_rotation_matrix(rot);
        py::array_t<float> result({4, 4});
        auto out = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                out(row, col) = m.data[col * 4 + row];
            }
        }
        return result;
    }, py::arg("rot3x3"), "Create 4x4 matrix from 3x3 rotation matrix");

    m.def("rotation_matrix_align_z_to_axis", [](py::array_t<float> axis) {
        auto buf = axis.unchecked<1>();
        float axis_arr[3] = {buf(0), buf(1), buf(2)};
        float rot[9];
        rotation_matrix_align_z_to_axis(axis_arr, rot);
        py::array_t<float> result({3, 3});
        auto out = result.mutable_unchecked<2>();
        for (int i = 0; i < 3; ++i) {
            for (int j = 0; j < 3; ++j) {
                out(i, j) = rot[i * 3 + j];
            }
        }
        return result;
    }, py::arg("axis"), "Build rotation matrix that aligns Z axis to given axis");
}

} // namespace termin
