#include "termin/render/solid_primitive_renderer.hpp"
#include <termin/geom/mat44.hpp>
#include <tgfx2/render_context.hpp>
#include <nanobind/nanobind.h>
#include <nanobind/stl/tuple.h>

namespace nb = nanobind;

namespace termin {

namespace {

Mat44f mat44_to_mat44f(const Mat44& src) {
    Mat44f mat;
    for (int i = 0; i < 16; ++i) {
        mat.data[i] = static_cast<float>(src.data[i]);
    }
    return mat;
}

Vec3f vec3_to_vec3f(const Vec3& v) {
    return Vec3f{
        static_cast<float>(v.x),
        static_cast<float>(v.y),
        static_cast<float>(v.z)
    };
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
        .def("begin", [](SolidPrimitiveRenderer& self,
                         tgfx::RenderContext2* ctx2,
                         const Mat44f& view,
                         const Mat44f& proj,
                         bool depth_test,
                         bool blend) {
            self.begin(ctx2, view, proj, depth_test, blend);
        },
             nb::arg("ctx2"), nb::arg("view"), nb::arg("proj"),
             nb::arg("depth_test") = true, nb::arg("blend") = false)
        .def("begin", [](SolidPrimitiveRenderer& self,
                         tgfx::RenderContext2* ctx2,
                         const Mat44& view,
                         const Mat44& proj,
                         bool depth_test,
                         bool blend) {
            self.begin(ctx2, mat44_to_mat44f(view), mat44_to_mat44f(proj), depth_test, blend);
        },
             nb::arg("ctx2"), nb::arg("view"), nb::arg("proj"),
             nb::arg("depth_test") = true, nb::arg("blend") = false)
        .def("end", &SolidPrimitiveRenderer::end)
        .def("draw_torus", [](SolidPrimitiveRenderer& self,
                              const Mat44f& model,
                              nb::tuple color_tuple) {
            self.draw_torus(model, tuple_to_color4(color_tuple));
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_torus", [](SolidPrimitiveRenderer& self,
                              const Mat44& model,
                              nb::tuple color_tuple) {
            self.draw_torus(mat44_to_mat44f(model), tuple_to_color4(color_tuple));
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_cylinder", [](SolidPrimitiveRenderer& self,
                                 const Mat44f& model,
                                 nb::tuple color_tuple) {
            self.draw_cylinder(model, tuple_to_color4(color_tuple));
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_cylinder", [](SolidPrimitiveRenderer& self,
                                 const Mat44& model,
                                 nb::tuple color_tuple) {
            self.draw_cylinder(mat44_to_mat44f(model), tuple_to_color4(color_tuple));
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_cone", [](SolidPrimitiveRenderer& self,
                             const Mat44f& model,
                             nb::tuple color_tuple) {
            self.draw_cone(model, tuple_to_color4(color_tuple));
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_cone", [](SolidPrimitiveRenderer& self,
                             const Mat44& model,
                             nb::tuple color_tuple) {
            self.draw_cone(mat44_to_mat44f(model), tuple_to_color4(color_tuple));
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_quad", [](SolidPrimitiveRenderer& self,
                             const Mat44f& model,
                             nb::tuple color_tuple) {
            self.draw_quad(model, tuple_to_color4(color_tuple));
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_quad", [](SolidPrimitiveRenderer& self,
                             const Mat44& model,
                             nb::tuple color_tuple) {
            self.draw_quad(mat44_to_mat44f(model), tuple_to_color4(color_tuple));
        },
             nb::arg("model"), nb::arg("color"))
        .def("draw_arrow", [](SolidPrimitiveRenderer& self,
                              const Vec3& origin,
                              const Vec3& direction,
                              float length,
                              nb::tuple color_tuple,
                              float shaft_radius,
                              float head_radius,
                              float head_length_ratio) {
            self.draw_arrow(
                vec3_to_vec3f(origin),
                vec3_to_vec3f(direction),
                length,
                tuple_to_color4(color_tuple),
                shaft_radius,
                head_radius,
                head_length_ratio
            );
        },
             nb::arg("origin"), nb::arg("direction"), nb::arg("length"), nb::arg("color"),
             nb::arg("shaft_radius") = 0.02f, nb::arg("head_radius") = 0.06f,
             nb::arg("head_length_ratio") = 0.2f);
}

} // namespace termin
