#include "common.hpp"
#include "termin/render/types.hpp"
#include "termin/render/render_state.hpp"
#include "termin/render/opengl/opengl_mesh.hpp"

namespace termin {

void bind_render_types(py::module_& m) {
    // --- Types ---

    py::class_<Color4>(m, "Color4")
        .def(py::init<>())
        .def(py::init<float, float, float, float>(),
            py::arg("r"), py::arg("g"), py::arg("b"), py::arg("a") = 1.0f)
        .def(py::init([](py::tuple t) {
            if (t.size() < 3) throw std::runtime_error("Color tuple must have at least 3 elements");
            float a = t.size() >= 4 ? t[3].cast<float>() : 1.0f;
            return Color4(t[0].cast<float>(), t[1].cast<float>(), t[2].cast<float>(), a);
        }))
        .def_readwrite("r", &Color4::r)
        .def_readwrite("g", &Color4::g)
        .def_readwrite("b", &Color4::b)
        .def_readwrite("a", &Color4::a)
        .def_static("black", &Color4::black)
        .def_static("white", &Color4::white)
        .def_static("red", &Color4::red)
        .def_static("green", &Color4::green)
        .def_static("blue", &Color4::blue)
        .def_static("transparent", &Color4::transparent)
        .def("__iter__", [](const Color4& c) {
            return py::make_iterator(&c.r, &c.a + 1);
        }, py::keep_alive<0, 1>())
        .def("__getitem__", [](const Color4& c, int i) {
            if (i < 0 || i > 3) throw py::index_error();
            return (&c.r)[i];
        });

    py::class_<Size2i>(m, "Size2i")
        .def(py::init<>())
        .def(py::init<int, int>(), py::arg("width"), py::arg("height"))
        .def(py::init([](py::tuple t) {
            if (t.size() != 2) throw std::runtime_error("Size tuple must have 2 elements");
            return Size2i(t[0].cast<int>(), t[1].cast<int>());
        }))
        .def_readwrite("width", &Size2i::width)
        .def_readwrite("height", &Size2i::height)
        .def("__iter__", [](const Size2i& s) {
            return py::make_iterator(&s.width, &s.height + 1);
        }, py::keep_alive<0, 1>())
        .def("__getitem__", [](const Size2i& s, int i) {
            if (i == 0) return s.width;
            if (i == 1) return s.height;
            throw py::index_error();
        })
        .def("__eq__", &Size2i::operator==)
        .def("__ne__", &Size2i::operator!=);

    py::class_<Rect2i>(m, "Rect2i")
        .def(py::init<>())
        .def(py::init<int, int, int, int>(),
            py::arg("x0"), py::arg("y0"), py::arg("x1"), py::arg("y1"))
        .def(py::init([](py::tuple t) {
            if (t.size() != 4) throw std::runtime_error("Rect tuple must have 4 elements");
            return Rect2i(t[0].cast<int>(), t[1].cast<int>(), t[2].cast<int>(), t[3].cast<int>());
        }))
        .def_readwrite("x0", &Rect2i::x0)
        .def_readwrite("y0", &Rect2i::y0)
        .def_readwrite("x1", &Rect2i::x1)
        .def_readwrite("y1", &Rect2i::y1)
        .def("width", &Rect2i::width)
        .def("height", &Rect2i::height)
        .def_static("from_size", py::overload_cast<int, int>(&Rect2i::from_size))
        .def_static("from_size", py::overload_cast<Size2i>(&Rect2i::from_size))
        .def("__iter__", [](const Rect2i& r) {
            return py::make_iterator(&r.x0, &r.y1 + 1);
        }, py::keep_alive<0, 1>())
        .def("__getitem__", [](const Rect2i& r, int i) {
            if (i < 0 || i > 3) throw py::index_error();
            return (&r.x0)[i];
        });

    // Implicit conversions from Python tuples
    py::implicitly_convertible<py::tuple, Color4>();
    py::implicitly_convertible<py::tuple, Size2i>();
    py::implicitly_convertible<py::tuple, Rect2i>();

    // --- Enums ---

    py::enum_<PolygonMode>(m, "PolygonMode")
        .value("Fill", PolygonMode::Fill)
        .value("Line", PolygonMode::Line);

    py::enum_<BlendFactor>(m, "BlendFactor")
        .value("Zero", BlendFactor::Zero)
        .value("One", BlendFactor::One)
        .value("SrcAlpha", BlendFactor::SrcAlpha)
        .value("OneMinusSrcAlpha", BlendFactor::OneMinusSrcAlpha);

    py::enum_<DepthFunc>(m, "DepthFunc")
        .value("Less", DepthFunc::Less)
        .value("LessEqual", DepthFunc::LessEqual)
        .value("Equal", DepthFunc::Equal)
        .value("Greater", DepthFunc::Greater)
        .value("GreaterEqual", DepthFunc::GreaterEqual)
        .value("NotEqual", DepthFunc::NotEqual)
        .value("Always", DepthFunc::Always)
        .value("Never", DepthFunc::Never);

    py::enum_<DrawMode>(m, "DrawMode")
        .value("Triangles", DrawMode::Triangles)
        .value("Lines", DrawMode::Lines);

    // --- RenderState ---

    py::class_<RenderState>(m, "RenderState")
        .def(py::init<>())
        // Constructor with string args for backward compatibility
        .def(py::init([](
            const std::string& polygon_mode,
            bool cull,
            bool depth_test,
            bool depth_write,
            bool blend,
            const std::string& blend_src,
            const std::string& blend_dst
        ) {
            RenderState s;
            s.polygon_mode = polygon_mode_from_string(polygon_mode);
            s.cull = cull;
            s.depth_test = depth_test;
            s.depth_write = depth_write;
            s.blend = blend;
            s.blend_src = blend_factor_from_string(blend_src);
            s.blend_dst = blend_factor_from_string(blend_dst);
            return s;
        }),
            py::arg("polygon_mode") = "fill",
            py::arg("cull") = true,
            py::arg("depth_test") = true,
            py::arg("depth_write") = true,
            py::arg("blend") = false,
            py::arg("blend_src") = "src_alpha",
            py::arg("blend_dst") = "one_minus_src_alpha")
        .def_readwrite("cull", &RenderState::cull)
        .def_readwrite("depth_test", &RenderState::depth_test)
        .def_readwrite("depth_write", &RenderState::depth_write)
        .def_readwrite("blend", &RenderState::blend)
        // String properties for polygon_mode, blend_src, blend_dst
        .def_property("polygon_mode",
            [](const RenderState& s) { return polygon_mode_to_string(s.polygon_mode); },
            [](RenderState& s, const std::string& v) { s.polygon_mode = polygon_mode_from_string(v); })
        .def_property("blend_src",
            [](const RenderState& s) { return blend_factor_to_string(s.blend_src); },
            [](RenderState& s, const std::string& v) { s.blend_src = blend_factor_from_string(v); })
        .def_property("blend_dst",
            [](const RenderState& s) { return blend_factor_to_string(s.blend_dst); },
            [](RenderState& s, const std::string& v) { s.blend_dst = blend_factor_from_string(v); })
        .def_static("opaque", &RenderState::opaque)
        .def_static("transparent", &RenderState::transparent)
        .def_static("wireframe", &RenderState::wireframe);
}

} // namespace termin
