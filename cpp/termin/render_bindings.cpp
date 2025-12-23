#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "termin/render/render.hpp"

namespace py = pybind11;

using namespace termin;

PYBIND11_MODULE(_render_native, m) {
    m.doc() = "Native render backend module";

    // --- init_opengl ---
    m.def("init_opengl", &init_opengl, "Initialize OpenGL via glad. Call after context creation.");

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

    // --- Handles (abstract, exposed for type hints) ---

    py::class_<ShaderHandle, std::shared_ptr<ShaderHandle>>(m, "ShaderHandle")
        .def("use", &ShaderHandle::use)
        .def("stop", &ShaderHandle::stop)
        .def("release", &ShaderHandle::release)
        .def("set_uniform_int", &ShaderHandle::set_uniform_int)
        .def("set_uniform_float", &ShaderHandle::set_uniform_float)
        .def("set_uniform_vec2", &ShaderHandle::set_uniform_vec2)
        .def("set_uniform_vec3", &ShaderHandle::set_uniform_vec3)
        .def("set_uniform_vec4", &ShaderHandle::set_uniform_vec4)
        .def("set_uniform_matrix4", [](ShaderHandle& self, const char* name, py::array_t<float> matrix, bool transpose) {
            auto buf = matrix.request();
            if (buf.size < 16) {
                throw std::runtime_error("Matrix must have at least 16 elements");
            }
            self.set_uniform_matrix4(name, static_cast<float*>(buf.ptr), transpose);
        }, py::arg("name"), py::arg("matrix"), py::arg("transpose") = true)
        .def("set_uniform_matrix4_array", [](ShaderHandle& self, const char* name, py::array_t<float> matrices, int count, bool transpose) {
            auto buf = matrices.request();
            self.set_uniform_matrix4_array(name, static_cast<float*>(buf.ptr), count, transpose);
        }, py::arg("name"), py::arg("matrices"), py::arg("count"), py::arg("transpose") = true);

    py::class_<MeshHandle, std::shared_ptr<MeshHandle>>(m, "MeshHandle")
        .def("draw", &MeshHandle::draw)
        .def("release", &MeshHandle::release);

    py::class_<TextureHandle, std::shared_ptr<TextureHandle>>(m, "TextureHandle")
        .def("bind", &TextureHandle::bind, py::arg("unit") = 0)
        .def("release", &TextureHandle::release)
        .def("get_id", &TextureHandle::get_id)
        .def("get_width", &TextureHandle::get_width)
        .def("get_height", &TextureHandle::get_height);

    py::class_<FramebufferHandle, std::shared_ptr<FramebufferHandle>>(m, "FramebufferHandle")
        .def("resize", &FramebufferHandle::resize)
        .def("release", &FramebufferHandle::release)
        .def("get_fbo_id", &FramebufferHandle::get_fbo_id)
        .def("get_width", &FramebufferHandle::get_width)
        .def("get_height", &FramebufferHandle::get_height)
        .def("get_samples", &FramebufferHandle::get_samples)
        .def("is_msaa", &FramebufferHandle::is_msaa)
        .def("color_texture", &FramebufferHandle::color_texture, py::return_value_policy::reference)
        .def("depth_texture", &FramebufferHandle::depth_texture, py::return_value_policy::reference);

    // --- GraphicsBackend ---

    py::class_<GraphicsBackend, std::shared_ptr<GraphicsBackend>>(m, "GraphicsBackend")
        .def("ensure_ready", &GraphicsBackend::ensure_ready)
        .def("set_viewport", &GraphicsBackend::set_viewport)
        .def("enable_scissor", &GraphicsBackend::enable_scissor)
        .def("disable_scissor", &GraphicsBackend::disable_scissor)
        .def("clear_color_depth", &GraphicsBackend::clear_color_depth)
        .def("clear_color", &GraphicsBackend::clear_color)
        .def("clear_depth", &GraphicsBackend::clear_depth, py::arg("value") = 1.0f)
        .def("set_color_mask", &GraphicsBackend::set_color_mask)
        .def("set_depth_test", &GraphicsBackend::set_depth_test)
        .def("set_depth_mask", &GraphicsBackend::set_depth_mask)
        .def("set_depth_func", &GraphicsBackend::set_depth_func)
        .def("set_cull_face", &GraphicsBackend::set_cull_face)
        .def("set_blend", &GraphicsBackend::set_blend)
        .def("set_blend_func", &GraphicsBackend::set_blend_func)
        .def("set_polygon_mode", &GraphicsBackend::set_polygon_mode)
        .def("reset_state", &GraphicsBackend::reset_state)
        .def("apply_render_state", &GraphicsBackend::apply_render_state)
        .def("bind_framebuffer", &GraphicsBackend::bind_framebuffer, py::arg("fbo").none(true))
        .def("read_pixel", &GraphicsBackend::read_pixel)
        .def("read_depth_pixel", &GraphicsBackend::read_depth_pixel);

    // --- OpenGLGraphicsBackend ---

    py::class_<OpenGLGraphicsBackend, GraphicsBackend, std::shared_ptr<OpenGLGraphicsBackend>>(m, "OpenGLGraphicsBackend")
        .def(py::init<>())
        .def("create_shader", [](OpenGLGraphicsBackend& self, const std::string& vert, const std::string& frag, const std::string& geom) {
            const char* geom_ptr = geom.empty() ? nullptr : geom.c_str();
            return self.create_shader(vert.c_str(), frag.c_str(), geom_ptr);
        }, py::arg("vertex_source"), py::arg("fragment_source"), py::arg("geometry_source") = "")
        .def("create_texture", [](OpenGLGraphicsBackend& self, py::array_t<uint8_t> data, int width, int height, int channels, bool mipmap, bool clamp) {
            auto buf = data.request();
            return self.create_texture(static_cast<uint8_t*>(buf.ptr), width, height, channels, mipmap, clamp);
        }, py::arg("data"), py::arg("width"), py::arg("height"), py::arg("channels") = 4, py::arg("mipmap") = true, py::arg("clamp") = false)
        .def("create_framebuffer", &OpenGLGraphicsBackend::create_framebuffer, py::arg("width"), py::arg("height"), py::arg("samples") = 1)
        .def("create_shadow_framebuffer", &OpenGLGraphicsBackend::create_shadow_framebuffer)
        .def("blit_framebuffer", &OpenGLGraphicsBackend::blit_framebuffer)
        .def("draw_ui_vertices", [](OpenGLGraphicsBackend& self, int context_key, py::array_t<float> vertices) {
            auto buf = vertices.request();
            int count = static_cast<int>(buf.size / 2);
            self.draw_ui_vertices(context_key, static_cast<float*>(buf.ptr), count);
        })
        .def("draw_ui_textured_quad", &OpenGLGraphicsBackend::draw_ui_textured_quad);

    // Note: create_mesh requires Mesh3 from _mesh_native.
    // For now, mesh creation will stay in Python until we unify the modules.
}
