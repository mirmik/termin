#include "common.hpp"
#include "termin/render/solid_primitive_renderer.hpp"
#include "tgfx/graphics_backend.hpp"
#include "termin/geom/mat44.hpp"

namespace termin {

namespace {

template<typename T>
Mat44f ndarray_to_mat44f(nb::ndarray<nb::numpy, T, nb::shape<4, 4>> arr) {
    Mat44f mat;
    for (int row = 0; row < 4; ++row) {
        for (int col = 0; col < 4; ++col) {
            mat(col, row) = static_cast<float>(arr(row, col));
        }
    }
    return mat;
}

Color4 tuple_to_color4(nb::tuple t) {
    return Color4{
        nb::cast<float>(t[0]),
        nb::cast<float>(t[1]),
        nb::cast<float>(t[2]),
        nb::cast<float>(t[3])
    };
}

} // anonymous namespace

void bind_solid_primitive(nb::module_& m) {
    nb::class_<SolidPrimitiveRenderer>(m, "SolidPrimitiveRenderer")
        .def(nb::init<>())
        // float64 overload (from camera matrices)
        .def("begin", [](SolidPrimitiveRenderer& self,
                         GraphicsBackend* graphics,
                         nb::ndarray<nb::numpy, double, nb::shape<4, 4>> view,
                         nb::ndarray<nb::numpy, double, nb::shape<4, 4>> proj,
                         bool depth_test,
                         bool blend) {
            self.begin(graphics, ndarray_to_mat44f(view), ndarray_to_mat44f(proj), depth_test, blend);
        },
             nb::arg("graphics"), nb::arg("view"), nb::arg("proj"),
             nb::arg("depth_test") = true, nb::arg("blend") = false)
        // float32 ndarray overload
        .def("begin", [](SolidPrimitiveRenderer& self,
                         GraphicsBackend* graphics,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> proj,
                         bool depth_test,
                         bool blend) {
            self.begin(graphics, ndarray_to_mat44f(view), ndarray_to_mat44f(proj), depth_test, blend);
        },
             nb::arg("graphics"), nb::arg("view"), nb::arg("proj"),
             nb::arg("depth_test") = true, nb::arg("blend") = false)
        // Mat44 (double) overload - from camera matrices
        .def("begin", [](SolidPrimitiveRenderer& self,
                         GraphicsBackend* graphics,
                         const Mat44& view,
                         const Mat44& proj,
                         bool depth_test,
                         bool blend) {
            // Convert Mat44 (double) to Mat44f (float)
            Mat44f view_f, proj_f;
            for (int i = 0; i < 16; ++i) {
                view_f.data[i] = static_cast<float>(view.data[i]);
                proj_f.data[i] = static_cast<float>(proj.data[i]);
            }
            self.begin(graphics, view_f, proj_f, depth_test, blend);
        },
             nb::arg("graphics"), nb::arg("view"), nb::arg("proj"),
             nb::arg("depth_test") = true, nb::arg("blend") = false)
        .def("end", &SolidPrimitiveRenderer::end)
        .def("draw_torus", [](SolidPrimitiveRenderer& self,
                              nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                              nb::tuple color_tuple) {
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat(col, row) = model(row, col);
                }
            }
            Color4 color{
                nb::cast<float>(color_tuple[0]),
                nb::cast<float>(color_tuple[1]),
                nb::cast<float>(color_tuple[2]),
                nb::cast<float>(color_tuple[3])
            };
            self.draw_torus(model_mat, color);
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_cylinder", [](SolidPrimitiveRenderer& self,
                                 nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                                 nb::tuple color_tuple) {
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat(col, row) = model(row, col);
                }
            }
            Color4 color{
                nb::cast<float>(color_tuple[0]),
                nb::cast<float>(color_tuple[1]),
                nb::cast<float>(color_tuple[2]),
                nb::cast<float>(color_tuple[3])
            };
            self.draw_cylinder(model_mat, color);
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_cone", [](SolidPrimitiveRenderer& self,
                             nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                             nb::tuple color_tuple) {
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat(col, row) = model(row, col);
                }
            }
            Color4 color{
                nb::cast<float>(color_tuple[0]),
                nb::cast<float>(color_tuple[1]),
                nb::cast<float>(color_tuple[2]),
                nb::cast<float>(color_tuple[3])
            };
            self.draw_cone(model_mat, color);
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_quad", [](SolidPrimitiveRenderer& self,
                             nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                             nb::tuple color_tuple) {
            Mat44f model_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    model_mat(col, row) = model(row, col);
                }
            }
            Color4 color{
                nb::cast<float>(color_tuple[0]),
                nb::cast<float>(color_tuple[1]),
                nb::cast<float>(color_tuple[2]),
                nb::cast<float>(color_tuple[3])
            };
            self.draw_quad(model_mat, color);
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_arrow", [](SolidPrimitiveRenderer& self,
                              nb::ndarray<nb::numpy, float, nb::shape<3>> origin,
                              nb::ndarray<nb::numpy, float, nb::shape<3>> direction,
                              float length,
                              nb::tuple color_tuple,
                              float shaft_radius,
                              float head_radius,
                              float head_length_ratio) {
            Vec3f origin_v{origin(0), origin(1), origin(2)};
            Vec3f dir_v{direction(0), direction(1), direction(2)};
            Color4 color{
                nb::cast<float>(color_tuple[0]),
                nb::cast<float>(color_tuple[1]),
                nb::cast<float>(color_tuple[2]),
                nb::cast<float>(color_tuple[3])
            };
            self.draw_arrow(origin_v, dir_v, length, color, shaft_radius, head_radius, head_length_ratio);
        },
             nb::arg("origin"), nb::arg("direction"), nb::arg("length"), nb::arg("color"),
             nb::arg("shaft_radius") = 0.02f, nb::arg("head_radius") = 0.06f,
             nb::arg("head_length_ratio") = 0.2f);
}

} // namespace termin
