#include "common.hpp"
#include "termin/render/immediate_renderer.hpp"

namespace termin {

void bind_immediate(py::module_& m) {
    py::class_<ImmediateRenderer>(m, "ImmediateRenderer")
        .def(py::init<>())
        .def("begin", &ImmediateRenderer::begin,
             "Clear all accumulated primitives")
        // Basic primitives
        .def("line", &ImmediateRenderer::line,
             py::arg("start"), py::arg("end"), py::arg("color"))
        .def("triangle", &ImmediateRenderer::triangle,
             py::arg("p0"), py::arg("p1"), py::arg("p2"), py::arg("color"))
        .def("quad", &ImmediateRenderer::quad,
             py::arg("p0"), py::arg("p1"), py::arg("p2"), py::arg("p3"), py::arg("color"))
        // Wireframe
        .def("polyline", &ImmediateRenderer::polyline,
             py::arg("points"), py::arg("color"), py::arg("closed") = false)
        .def("circle", &ImmediateRenderer::circle,
             py::arg("center"), py::arg("normal"), py::arg("radius"), py::arg("color"),
             py::arg("segments") = 32)
        .def("arrow", &ImmediateRenderer::arrow,
             py::arg("origin"), py::arg("direction"), py::arg("length"), py::arg("color"),
             py::arg("head_length") = 0.2, py::arg("head_width") = 0.1)
        .def("box", &ImmediateRenderer::box,
             py::arg("min_pt"), py::arg("max_pt"), py::arg("color"))
        .def("cylinder_wireframe", &ImmediateRenderer::cylinder_wireframe,
             py::arg("start"), py::arg("end"), py::arg("radius"), py::arg("color"),
             py::arg("segments") = 16)
        .def("sphere_wireframe", &ImmediateRenderer::sphere_wireframe,
             py::arg("center"), py::arg("radius"), py::arg("color"),
             py::arg("segments") = 16)
        .def("capsule_wireframe", &ImmediateRenderer::capsule_wireframe,
             py::arg("start"), py::arg("end"), py::arg("radius"), py::arg("color"),
             py::arg("segments") = 16)
        // Solid
        .def("cylinder_solid", &ImmediateRenderer::cylinder_solid,
             py::arg("start"), py::arg("end"), py::arg("radius"), py::arg("color"),
             py::arg("segments") = 16, py::arg("caps") = true)
        .def("cone_solid", &ImmediateRenderer::cone_solid,
             py::arg("base"), py::arg("tip"), py::arg("radius"), py::arg("color"),
             py::arg("segments") = 16, py::arg("cap") = true)
        .def("torus_solid", &ImmediateRenderer::torus_solid,
             py::arg("center"), py::arg("axis"), py::arg("major_radius"), py::arg("minor_radius"),
             py::arg("color"), py::arg("major_segments") = 32, py::arg("minor_segments") = 12)
        .def("arrow_solid", &ImmediateRenderer::arrow_solid,
             py::arg("origin"), py::arg("direction"), py::arg("length"), py::arg("color"),
             py::arg("shaft_radius") = 0.03, py::arg("head_radius") = 0.06,
             py::arg("head_length_ratio") = 0.25, py::arg("segments") = 16)
        // Rendering
        // Note: graphics parameter is ignored (C++ initializes OpenGL resources itself)
        // but kept for backward compatibility with existing Python callers
        .def("flush", [](ImmediateRenderer& self,
                         py::object /*graphics*/,
                         py::array_t<double> view,
                         py::array_t<double> proj,
                         bool depth_test,
                         bool blend) {
            auto view_buf = view.unchecked<2>();
            auto proj_buf = proj.unchecked<2>();

            Mat44 view_mat, proj_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    view_mat.data[col * 4 + row] = view_buf(row, col);
                    proj_mat.data[col * 4 + row] = proj_buf(row, col);
                }
            }

            self.flush(view_mat, proj_mat, depth_test, blend);
        },
             py::arg("graphics"), py::arg("view_matrix"), py::arg("proj_matrix"),
             py::arg("depth_test") = true, py::arg("blend") = true)
        // Properties
        .def_property_readonly("line_count", &ImmediateRenderer::line_count)
        .def_property_readonly("triangle_count", &ImmediateRenderer::triangle_count);
}

} // namespace termin
