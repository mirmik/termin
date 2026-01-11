#include "common.hpp"
#include "termin/render/immediate_renderer.hpp"
#include "termin/render/graphics_backend.hpp"

namespace termin {

void bind_immediate(nb::module_& m) {
    nb::class_<ImmediateRenderer>(m, "ImmediateRenderer")
        .def(nb::init<>())
        .def("begin", &ImmediateRenderer::begin,
             "Clear all accumulated primitives")
        // Basic primitives
        .def("line", &ImmediateRenderer::line,
             nb::arg("start"), nb::arg("end"), nb::arg("color"), nb::arg("depth_test") = false)
        .def("triangle", &ImmediateRenderer::triangle,
             nb::arg("p0"), nb::arg("p1"), nb::arg("p2"), nb::arg("color"), nb::arg("depth_test") = false)
        .def("quad", &ImmediateRenderer::quad,
             nb::arg("p0"), nb::arg("p1"), nb::arg("p2"), nb::arg("p3"), nb::arg("color"), nb::arg("depth_test") = false)
        // Wireframe
        .def("polyline", &ImmediateRenderer::polyline,
             nb::arg("points"), nb::arg("color"), nb::arg("closed") = false, nb::arg("depth_test") = false)
        .def("circle", &ImmediateRenderer::circle,
             nb::arg("center"), nb::arg("normal"), nb::arg("radius"), nb::arg("color"),
             nb::arg("segments") = 32, nb::arg("depth_test") = false)
        .def("arrow", &ImmediateRenderer::arrow,
             nb::arg("origin"), nb::arg("direction"), nb::arg("length"), nb::arg("color"),
             nb::arg("head_length") = 0.2, nb::arg("head_width") = 0.1, nb::arg("depth_test") = false)
        .def("box", &ImmediateRenderer::box,
             nb::arg("min_pt"), nb::arg("max_pt"), nb::arg("color"), nb::arg("depth_test") = false)
        .def("cylinder_wireframe", &ImmediateRenderer::cylinder_wireframe,
             nb::arg("start"), nb::arg("end"), nb::arg("radius"), nb::arg("color"),
             nb::arg("segments") = 16, nb::arg("depth_test") = false)
        .def("sphere_wireframe", &ImmediateRenderer::sphere_wireframe,
             nb::arg("center"), nb::arg("radius"), nb::arg("color"),
             nb::arg("segments") = 16, nb::arg("depth_test") = false)
        .def("capsule_wireframe", &ImmediateRenderer::capsule_wireframe,
             nb::arg("start"), nb::arg("end"), nb::arg("radius"), nb::arg("color"),
             nb::arg("segments") = 16, nb::arg("depth_test") = false)
        // Solid
        .def("cylinder_solid", &ImmediateRenderer::cylinder_solid,
             nb::arg("start"), nb::arg("end"), nb::arg("radius"), nb::arg("color"),
             nb::arg("segments") = 16, nb::arg("caps") = true, nb::arg("depth_test") = false)
        .def("cone_solid", &ImmediateRenderer::cone_solid,
             nb::arg("base"), nb::arg("tip"), nb::arg("radius"), nb::arg("color"),
             nb::arg("segments") = 16, nb::arg("cap") = true, nb::arg("depth_test") = false)
        .def("torus_solid", &ImmediateRenderer::torus_solid,
             nb::arg("center"), nb::arg("axis"), nb::arg("major_radius"), nb::arg("minor_radius"),
             nb::arg("color"), nb::arg("major_segments") = 32, nb::arg("minor_segments") = 12,
             nb::arg("depth_test") = false)
        .def("arrow_solid", &ImmediateRenderer::arrow_solid,
             nb::arg("origin"), nb::arg("direction"), nb::arg("length"), nb::arg("color"),
             nb::arg("shaft_radius") = 0.03, nb::arg("head_radius") = 0.06,
             nb::arg("head_length_ratio") = 0.25, nb::arg("segments") = 16, nb::arg("depth_test") = false)
        // Rendering - numpy overload (converts row-major numpy to column-major Mat44)
        .def("flush", [](ImmediateRenderer& self,
                         GraphicsBackend* graphics,
                         nb::ndarray<nb::numpy, double, nb::shape<4, 4>> view,
                         nb::ndarray<nb::numpy, double, nb::shape<4, 4>> proj,
                         bool depth_test,
                         bool blend) {
            Mat44 view_mat, proj_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    view_mat.data[col * 4 + row] = view(row, col);
                    proj_mat.data[col * 4 + row] = proj(row, col);
                }
            }

            self.flush(graphics, view_mat, proj_mat, depth_test, blend);
        },
             nb::arg("graphics"), nb::arg("view_matrix"), nb::arg("proj_matrix"),
             nb::arg("depth_test") = true, nb::arg("blend") = true)
        // Mat44 overload (already column-major)
        .def("flush", [](ImmediateRenderer& self,
                         GraphicsBackend* graphics,
                         const Mat44& view,
                         const Mat44& proj,
                         bool depth_test,
                         bool blend) {
            self.flush(graphics, view, proj, depth_test, blend);
        },
             nb::arg("graphics"), nb::arg("view_matrix"), nb::arg("proj_matrix"),
             nb::arg("depth_test") = true, nb::arg("blend") = true)
        .def("flush_depth", [](ImmediateRenderer& self,
                         GraphicsBackend* graphics,
                         nb::ndarray<nb::numpy, double, nb::shape<4, 4>> view,
                         nb::ndarray<nb::numpy, double, nb::shape<4, 4>> proj,
                         bool blend) {
            Mat44 view_mat, proj_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    view_mat.data[col * 4 + row] = view(row, col);
                    proj_mat.data[col * 4 + row] = proj(row, col);
                }
            }

            self.flush_depth(graphics, view_mat, proj_mat, blend);
        },
             nb::arg("graphics"), nb::arg("view_matrix"), nb::arg("proj_matrix"),
             nb::arg("blend") = true)
        // Mat44 overload
        .def("flush_depth", [](ImmediateRenderer& self,
                         GraphicsBackend* graphics,
                         const Mat44& view,
                         const Mat44& proj,
                         bool blend) {
            self.flush_depth(graphics, view, proj, blend);
        },
             nb::arg("graphics"), nb::arg("view_matrix"), nb::arg("proj_matrix"),
             nb::arg("blend") = true)
        // Properties
        .def_prop_ro("line_count", &ImmediateRenderer::line_count)
        .def_prop_ro("triangle_count", &ImmediateRenderer::triangle_count)
        .def_prop_ro("line_count_depth", &ImmediateRenderer::line_count_depth)
        .def_prop_ro("triangle_count_depth", &ImmediateRenderer::triangle_count_depth);
}

} // namespace termin
