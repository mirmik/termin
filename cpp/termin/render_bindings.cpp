#include "render_bindings.hpp"

#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <fstream>
#include <sstream>

#include "termin/mesh/mesh3.hpp"
#include "termin/render/render.hpp"
#include "termin/render/types.hpp"
#include "termin/render/opengl/opengl_mesh.hpp"
#include "termin/render/shader_program.hpp"
#include "termin/camera/camera.hpp"

namespace py = pybind11;

namespace termin {

void bind_render(py::module_& m) {
    // --- init_opengl ---
    m.def("init_opengl", &init_opengl, "Initialize OpenGL via glad. Call after context creation.");

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

    // --- Handles (abstract, exposed for type hints) ---

    py::class_<ShaderHandle, std::unique_ptr<ShaderHandle>>(m, "ShaderHandle")
        .def("use", &ShaderHandle::use)
        .def("stop", &ShaderHandle::stop)
        .def("release", &ShaderHandle::release)
        .def("set_uniform_int", &ShaderHandle::set_uniform_int)
        .def("set_uniform_float", &ShaderHandle::set_uniform_float)
        .def("set_uniform_vec2", &ShaderHandle::set_uniform_vec2)
        .def("set_uniform_vec2", [](ShaderHandle& self, const char* name, py::array_t<float> v) {
            auto buf = v.request();
            auto* ptr = static_cast<float*>(buf.ptr);
            self.set_uniform_vec2(name, ptr[0], ptr[1]);
        })
        .def("set_uniform_vec3", &ShaderHandle::set_uniform_vec3)
        .def("set_uniform_vec3", [](ShaderHandle& self, const char* name, py::array_t<float> v) {
            auto buf = v.request();
            auto* ptr = static_cast<float*>(buf.ptr);
            self.set_uniform_vec3(name, ptr[0], ptr[1], ptr[2]);
        })
        .def("set_uniform_vec4", &ShaderHandle::set_uniform_vec4)
        .def("set_uniform_vec4", [](ShaderHandle& self, const char* name, py::array_t<float> v) {
            auto buf = v.request();
            auto* ptr = static_cast<float*>(buf.ptr);
            self.set_uniform_vec4(name, ptr[0], ptr[1], ptr[2], ptr[3]);
        })
        .def("set_uniform_matrix4", [](ShaderHandle& self, const char* name, py::array matrix, bool transpose) {
            // Ensure contiguous float32 array
            py::array_t<float, py::array::c_style | py::array::forcecast> arr(matrix);
            auto buf = arr.request();
            if (buf.size < 16) {
                throw std::runtime_error("Matrix must have at least 16 elements");
            }
            self.set_uniform_matrix4(name, static_cast<float*>(buf.ptr), transpose);
        }, py::arg("name"), py::arg("matrix"), py::arg("transpose") = true)
        .def("set_uniform_matrix4_array", [](ShaderHandle& self, const char* name, py::array matrices, int count, bool transpose) {
            // Ensure contiguous float32 array
            py::array_t<float, py::array::c_style | py::array::forcecast> arr(matrices);
            auto buf = arr.request();
            self.set_uniform_matrix4_array(name, static_cast<float*>(buf.ptr), count, transpose);
        }, py::arg("name"), py::arg("matrices"), py::arg("count"), py::arg("transpose") = true);

    py::class_<MeshHandle, std::unique_ptr<MeshHandle>>(m, "MeshHandle")
        .def("draw", &MeshHandle::draw)
        .def("release", &MeshHandle::release);

    py::class_<GPUTextureHandle, std::unique_ptr<GPUTextureHandle>>(m, "GPUTextureHandle")
        .def("bind", &GPUTextureHandle::bind, py::arg("unit") = 0)
        .def("release", &GPUTextureHandle::release)
        .def("get_id", &GPUTextureHandle::get_id)
        .def("get_width", &GPUTextureHandle::get_width)
        .def("get_height", &GPUTextureHandle::get_height);

    py::class_<FramebufferHandle, std::unique_ptr<FramebufferHandle>>(m, "FramebufferHandle")
        .def("resize", static_cast<void (FramebufferHandle::*)(int, int)>(&FramebufferHandle::resize))
        .def("resize", static_cast<void (FramebufferHandle::*)(Size2i)>(&FramebufferHandle::resize))
        .def("release", &FramebufferHandle::release)
        .def("get_fbo_id", &FramebufferHandle::get_fbo_id)
        .def("get_width", &FramebufferHandle::get_width)
        .def("get_height", &FramebufferHandle::get_height)
        .def("get_size", &FramebufferHandle::get_size)
        .def("get_samples", &FramebufferHandle::get_samples)
        .def("is_msaa", &FramebufferHandle::is_msaa)
        .def("color_texture", &FramebufferHandle::color_texture, py::return_value_policy::reference)
        .def("depth_texture", &FramebufferHandle::depth_texture, py::return_value_policy::reference)
        .def("set_external_target", static_cast<void (FramebufferHandle::*)(uint32_t, int, int)>(&FramebufferHandle::set_external_target))
        .def("set_external_target", static_cast<void (FramebufferHandle::*)(uint32_t, Size2i)>(&FramebufferHandle::set_external_target));

    // --- GraphicsBackend ---

    py::class_<GraphicsBackend, std::shared_ptr<GraphicsBackend>>(m, "GraphicsBackend")
        .def("ensure_ready", &GraphicsBackend::ensure_ready)
        .def("set_viewport", &GraphicsBackend::set_viewport)
        .def("enable_scissor", &GraphicsBackend::enable_scissor)
        .def("disable_scissor", &GraphicsBackend::disable_scissor)
        // clear_color_depth with 4 floats, Color4, and tuple
        .def("clear_color_depth", static_cast<void (GraphicsBackend::*)(float, float, float, float)>(&GraphicsBackend::clear_color_depth))
        .def("clear_color_depth", static_cast<void (GraphicsBackend::*)(const Color4&)>(&GraphicsBackend::clear_color_depth))
        .def("clear_color_depth", [](GraphicsBackend& self, py::tuple color) {
            float a = color.size() >= 4 ? color[3].cast<float>() : 1.0f;
            self.clear_color_depth(color[0].cast<float>(), color[1].cast<float>(), color[2].cast<float>(), a);
        })
        .def("clear_color", static_cast<void (GraphicsBackend::*)(float, float, float, float)>(&GraphicsBackend::clear_color))
        .def("clear_color", static_cast<void (GraphicsBackend::*)(const Color4&)>(&GraphicsBackend::clear_color))
        .def("clear_color", [](GraphicsBackend& self, py::tuple color) {
            float a = color.size() >= 4 ? color[3].cast<float>() : 1.0f;
            self.clear_color(color[0].cast<float>(), color[1].cast<float>(), color[2].cast<float>(), a);
        })
        .def("clear_depth", &GraphicsBackend::clear_depth, py::arg("value") = 1.0f)
        .def("set_color_mask", &GraphicsBackend::set_color_mask)
        .def("set_depth_test", &GraphicsBackend::set_depth_test)
        .def("set_depth_mask", &GraphicsBackend::set_depth_mask)
        // set_depth_func with enum and string
        .def("set_depth_func", &GraphicsBackend::set_depth_func)
        .def("set_depth_func", [](GraphicsBackend& self, const std::string& func) {
            self.set_depth_func(depth_func_from_string(func));
        })
        .def("set_cull_face", &GraphicsBackend::set_cull_face)
        .def("set_blend", &GraphicsBackend::set_blend)
        // set_blend_func with enum and string
        .def("set_blend_func", &GraphicsBackend::set_blend_func)
        .def("set_blend_func", [](GraphicsBackend& self, const std::string& src, const std::string& dst) {
            self.set_blend_func(blend_factor_from_string(src), blend_factor_from_string(dst));
        })
        // set_polygon_mode with enum and string
        .def("set_polygon_mode", &GraphicsBackend::set_polygon_mode)
        .def("set_polygon_mode", [](GraphicsBackend& self, const std::string& mode) {
            self.set_polygon_mode(polygon_mode_from_string(mode));
        })
        .def("reset_state", &GraphicsBackend::reset_state)
        .def("apply_render_state", &GraphicsBackend::apply_render_state)
        // Aliases for Python API compatibility
        .def("set_cull_face_enabled", &GraphicsBackend::set_cull_face)
        .def("set_depth_test_enabled", &GraphicsBackend::set_depth_test)
        .def("set_depth_write_enabled", &GraphicsBackend::set_depth_mask)
        .def("bind_framebuffer", &GraphicsBackend::bind_framebuffer, py::arg("fbo").none(true))
        // bind_framebuffer for Python FBO objects
        .def("bind_framebuffer", [](GraphicsBackend& self, py::object fbo) {
            if (fbo.is_none()) {
                glBindFramebuffer(GL_FRAMEBUFFER, 0);
                return;
            }
            // Try C++ FramebufferHandle first
            try {
                auto* handle = fbo.cast<FramebufferHandle*>();
                self.bind_framebuffer(handle);
            } catch (py::cast_error&) {
                // Must be Python OpenGLFramebufferHandle - get _fbo attribute
                GLuint fbo_id = fbo.attr("_fbo").cast<GLuint>();
                glBindFramebuffer(GL_FRAMEBUFFER, fbo_id);
            }
        })
        .def("read_pixel", &GraphicsBackend::read_pixel)
        .def("read_depth_pixel", &GraphicsBackend::read_depth_pixel)
        // read_depth_buffer - returns numpy array or None
        .def("read_depth_buffer", [](GraphicsBackend& self, FramebufferHandle* fbo) -> py::object {
            if (fbo == nullptr) return py::none();
            if (fbo->is_msaa()) return py::none();  // Cannot read from MSAA

            int width = fbo->get_width();
            int height = fbo->get_height();
            if (width <= 0 || height <= 0) return py::none();

            // Allocate numpy array
            py::array_t<float> result({height, width});
            auto buf = result.mutable_unchecked<2>();

            bool success = self.read_depth_buffer(fbo, buf.mutable_data(0, 0));
            if (!success) return py::none();

            return result;
        });

    // --- OpenGLGraphicsBackend ---

    py::class_<OpenGLGraphicsBackend, GraphicsBackend, std::shared_ptr<OpenGLGraphicsBackend>>(m, "OpenGLGraphicsBackend")
        .def(py::init<>())
        .def("create_shader", [](OpenGLGraphicsBackend& self, const std::string& vert, const std::string& frag, py::object geom) {
            const char* geom_ptr = nullptr;
            std::string geom_str;
            if (!geom.is_none()) {
                geom_str = geom.cast<std::string>();
                if (!geom_str.empty()) {
                    geom_ptr = geom_str.c_str();
                }
            }
            return self.create_shader(vert.c_str(), frag.c_str(), geom_ptr);
        }, py::arg("vertex_source"), py::arg("fragment_source"), py::arg("geometry_source") = py::none())
        // create_texture with (width, height) and with tuple size
        .def("create_texture", [](OpenGLGraphicsBackend& self, py::array_t<uint8_t> data, int width, int height, int channels, bool mipmap, bool clamp) {
            auto buf = data.request();
            return self.create_texture(static_cast<uint8_t*>(buf.ptr), width, height, channels, mipmap, clamp);
        }, py::arg("data"), py::arg("width"), py::arg("height"), py::arg("channels") = 4, py::arg("mipmap") = true, py::arg("clamp") = false)
        .def("create_texture", [](OpenGLGraphicsBackend& self, py::array_t<uint8_t> data, py::tuple size, int channels, bool mipmap, bool clamp) {
            auto buf = data.request();
            int width = size[0].cast<int>();
            int height = size[1].cast<int>();
            return self.create_texture(static_cast<uint8_t*>(buf.ptr), width, height, channels, mipmap, clamp);
        }, py::arg("data"), py::arg("size"), py::arg("channels") = 4, py::arg("mipmap") = true, py::arg("clamp") = false)
        // create_framebuffer with (width, height) and with tuple size
        .def("create_framebuffer", static_cast<FramebufferHandlePtr (OpenGLGraphicsBackend::*)(int, int, int)>(&OpenGLGraphicsBackend::create_framebuffer),
            py::arg("width"), py::arg("height"), py::arg("samples") = 1)
        .def("create_framebuffer", [](OpenGLGraphicsBackend& self, py::tuple size, int samples) {
            return self.create_framebuffer(size[0].cast<int>(), size[1].cast<int>(), samples);
        }, py::arg("size"), py::arg("samples") = 1)
        // create_shadow_framebuffer
        .def("create_shadow_framebuffer", static_cast<FramebufferHandlePtr (OpenGLGraphicsBackend::*)(int, int)>(&OpenGLGraphicsBackend::create_shadow_framebuffer))
        .def("create_shadow_framebuffer", [](OpenGLGraphicsBackend& self, py::tuple size) {
            return self.create_shadow_framebuffer(size[0].cast<int>(), size[1].cast<int>());
        })
        // blit_framebuffer with 8 ints and with tuple rects
        .def("blit_framebuffer", static_cast<void (OpenGLGraphicsBackend::*)(FramebufferHandle*, FramebufferHandle*, int, int, int, int, int, int, int, int)>(&OpenGLGraphicsBackend::blit_framebuffer))
        .def("blit_framebuffer", [](OpenGLGraphicsBackend& self, FramebufferHandle* src, FramebufferHandle* dst, py::tuple src_rect, py::tuple dst_rect) {
            self.blit_framebuffer(src, dst,
                src_rect[0].cast<int>(), src_rect[1].cast<int>(), src_rect[2].cast<int>(), src_rect[3].cast<int>(),
                dst_rect[0].cast<int>(), dst_rect[1].cast<int>(), dst_rect[2].cast<int>(), dst_rect[3].cast<int>());
        })
        // blit_framebuffer with Python FBO objects (for window FBOs)
        .def("blit_framebuffer", [](OpenGLGraphicsBackend& self, py::object src, py::object dst, py::tuple src_rect, py::tuple dst_rect) {
            // Extract FBO IDs from either C++ FramebufferHandle or Python OpenGLFramebufferHandle
            GLuint src_fbo = 0;
            GLuint dst_fbo = 0;

            // Try to get C++ FramebufferHandle first
            try {
                auto* src_handle = src.cast<FramebufferHandle*>();
                src_fbo = src_handle->get_fbo_id();
            } catch (py::cast_error&) {
                // Must be Python OpenGLFramebufferHandle - get _fbo attribute
                src_fbo = src.attr("_fbo").cast<GLuint>();
            }

            try {
                auto* dst_handle = dst.cast<FramebufferHandle*>();
                dst_fbo = dst_handle->get_fbo_id();
            } catch (py::cast_error&) {
                dst_fbo = dst.attr("_fbo").cast<GLuint>();
            }

            // Perform the blit using raw FBO IDs
            int sx0 = src_rect[0].cast<int>(), sy0 = src_rect[1].cast<int>();
            int sx1 = src_rect[2].cast<int>(), sy1 = src_rect[3].cast<int>();
            int dx0 = dst_rect[0].cast<int>(), dy0 = dst_rect[1].cast<int>();
            int dx1 = dst_rect[2].cast<int>(), dy1 = dst_rect[3].cast<int>();

            glBindFramebuffer(GL_READ_FRAMEBUFFER, src_fbo);
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, dst_fbo);
            glBlitFramebuffer(sx0, sy0, sx1, sy1, dx0, dy0, dx1, dy1,
                              GL_COLOR_BUFFER_BIT, GL_NEAREST);
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
        })
        .def("draw_ui_vertices", [](OpenGLGraphicsBackend& self, int64_t context_key, py::array_t<float> vertices) {
            auto buf = vertices.request();
            int count = static_cast<int>(buf.size / 2);
            self.draw_ui_vertices(context_key, static_cast<float*>(buf.ptr), count);
        })
        .def("draw_ui_textured_quad", static_cast<void (OpenGLGraphicsBackend::*)(int64_t)>(&OpenGLGraphicsBackend::draw_ui_textured_quad))
        .def("draw_ui_textured_quad", [](OpenGLGraphicsBackend& self, int64_t context_key, py::array_t<float> vertices) {
            auto buf = vertices.request();
            int count = static_cast<int>(buf.size / 4);  // 4 floats per vertex (x, y, u, v)
            self.draw_ui_textured_quad(context_key, static_cast<float*>(buf.ptr), count);
        })
        // Generic create_mesh for all Python mesh objects (Mesh3, SkinnedMesh3, Mesh2, etc.)
        // Uses interleaved_buffer() and get_vertex_layout() to support any vertex format
        .def("create_mesh", [](OpenGLGraphicsBackend& self, py::object mesh, DrawMode mode) -> std::unique_ptr<MeshHandle> {
            // Get interleaved buffer
            py::array_t<float> buffer = mesh.attr("interleaved_buffer")().cast<py::array_t<float>>();
            auto buf = buffer.request();

            // Get indices and flatten to uint32
            py::array indices_arr = mesh.attr("indices").cast<py::array>();
            py::array_t<uint32_t> indices = indices_arr.attr("flatten")().attr("astype")("uint32").cast<py::array_t<uint32_t>>();
            auto idx_buf = indices.request();

            // Get vertex layout
            py::object layout = mesh.attr("get_vertex_layout")();
            int stride = layout.attr("stride").cast<int>();

            // Parse attributes
            py::list attrs = layout.attr("attributes").cast<py::list>();
            int position_offset = 0;
            int position_size = 3;
            bool has_normal = false;
            int normal_offset = 0;
            bool has_uv = false;
            int uv_offset = 0;
            bool has_joints = false;
            int joints_offset = 0;
            bool has_weights = false;
            int weights_offset = 0;

            for (auto attr : attrs) {
                std::string name = attr.attr("name").cast<std::string>();
                int offset = attr.attr("offset").cast<int>();
                int size = attr.attr("size").cast<int>();
                if (name == "position") {
                    position_offset = offset;
                    position_size = size;
                } else if (name == "normal") {
                    has_normal = true;
                    normal_offset = offset;
                } else if (name == "uv") {
                    has_uv = true;
                    uv_offset = offset;
                } else if (name == "joints") {
                    has_joints = true;
                    joints_offset = offset;
                } else if (name == "weights") {
                    has_weights = true;
                    weights_offset = offset;
                }
            }

            // If mode not specified, try to determine from indices shape
            DrawMode actual_mode = mode;
            if (mode == DrawMode::Triangles && indices_arr.attr("ndim").cast<int>() == 2) {
                int cols = indices_arr.attr("shape").cast<py::tuple>()[1].cast<int>();
                if (cols == 2) {
                    actual_mode = DrawMode::Lines;
                }
            }

            return std::make_unique<OpenGLRawMeshHandle>(
                static_cast<float*>(buf.ptr), buf.size * sizeof(float),
                static_cast<uint32_t*>(idx_buf.ptr), idx_buf.size,
                stride,
                position_offset, position_size,
                has_normal, normal_offset,
                has_uv, uv_offset,
                has_joints, joints_offset,
                has_weights, weights_offset,
                actual_mode
            );
        }, py::arg("mesh"), py::arg("mode") = DrawMode::Triangles);

    // --- GlslPreprocessor ---

    py::class_<GlslPreprocessor>(m, "GlslPreprocessor")
        .def(py::init<>())
        .def("register_include", &GlslPreprocessor::register_include,
            py::arg("name"), py::arg("source"),
            "Register an include file")
        .def("has_include", &GlslPreprocessor::has_include)
        .def("get_include", [](const GlslPreprocessor& pp, const std::string& name) -> py::object {
            const std::string* src = pp.get_include(name);
            return src ? py::cast(*src) : py::none();
        })
        .def("clear", &GlslPreprocessor::clear)
        .def("size", &GlslPreprocessor::size)
        .def_static("has_includes", &GlslPreprocessor::has_includes)
        .def("preprocess", &GlslPreprocessor::preprocess,
            py::arg("source"), py::arg("source_name") = "<unknown>",
            "Preprocess GLSL source, resolving #include directives");

    // Global preprocessor instance
    m.def("glsl_preprocessor", &glsl_preprocessor, py::return_value_policy::reference,
        "Get the global GLSL preprocessor instance");

    // --- ShaderProgram ---

    py::class_<ShaderProgram>(m, "ShaderProgram")
        .def(py::init<>())
        .def(py::init<std::string, std::string, std::string, std::string>(),
            py::arg("vertex_source"),
            py::arg("fragment_source"),
            py::arg("geometry_source") = "",
            py::arg("source_path") = "")
        .def_property_readonly("vertex_source", &ShaderProgram::vertex_source)
        .def_property_readonly("fragment_source", &ShaderProgram::fragment_source)
        .def_property_readonly("geometry_source", &ShaderProgram::geometry_source)
        .def_property_readonly("source_path", &ShaderProgram::source_path)
        .def_property_readonly("is_compiled", &ShaderProgram::is_compiled)
        .def("ensure_ready", [](ShaderProgram& self, OpenGLGraphicsBackend& backend) {
            self.ensure_ready([&backend](const char* v, const char* f, const char* g) {
                return backend.create_shader(v, f, g);
            });
        }, py::arg("graphics"), "Compile shader using graphics backend")
        .def("set_handle", &ShaderProgram::set_handle)
        .def("use", &ShaderProgram::use)
        .def("stop", &ShaderProgram::stop)
        .def("release", &ShaderProgram::release)
        .def("set_uniform_int", &ShaderProgram::set_uniform_int)
        .def("set_uniform_float", &ShaderProgram::set_uniform_float)
        .def("set_uniform_vec2", py::overload_cast<const char*, float, float>(&ShaderProgram::set_uniform_vec2))
        .def("set_uniform_vec2", [](ShaderProgram& self, const char* name, py::array_t<float> v) {
            auto buf = v.unchecked<1>();
            self.set_uniform_vec2(name, buf(0), buf(1));
        })
        .def("set_uniform_vec3", py::overload_cast<const char*, float, float, float>(&ShaderProgram::set_uniform_vec3))
        .def("set_uniform_vec3", py::overload_cast<const char*, const Vec3&>(&ShaderProgram::set_uniform_vec3))
        .def("set_uniform_vec3", [](ShaderProgram& self, const char* name, py::array_t<float> v) {
            auto buf = v.unchecked<1>();
            self.set_uniform_vec3(name, buf(0), buf(1), buf(2));
        })
        .def("set_uniform_vec4", py::overload_cast<const char*, float, float, float, float>(&ShaderProgram::set_uniform_vec4))
        .def("set_uniform_vec4", [](ShaderProgram& self, const char* name, py::array_t<float> v) {
            auto buf = v.unchecked<1>();
            self.set_uniform_vec4(name, buf(0), buf(1), buf(2), buf(3));
        })
        .def("set_uniform_matrix4", [](ShaderProgram& self, const char* name, py::array matrix, bool transpose) {
            auto buf = matrix.request();
            if (buf.ndim != 2 || buf.shape[0] != 4 || buf.shape[1] != 4) {
                throw std::runtime_error("Matrix must be 4x4");
            }
            // Convert to float if needed
            auto float_matrix = py::array_t<float>::ensure(matrix);
            self.set_uniform_matrix4(name, static_cast<float*>(float_matrix.request().ptr), transpose);
        }, py::arg("name"), py::arg("matrix"), py::arg("transpose") = true)
        .def("set_uniform_matrix4", [](ShaderProgram& self, const char* name, const Mat44& m, bool transpose) {
            self.set_uniform_matrix4(name, m, transpose);
        }, py::arg("name"), py::arg("matrix"), py::arg("transpose") = true)
        .def("set_uniform_matrix4_array", [](ShaderProgram& self, const char* name, py::array matrices, int count, bool transpose) {
            auto buf = matrices.request();
            auto float_matrices = py::array_t<float>::ensure(matrices);
            self.set_uniform_matrix4_array(name, static_cast<float*>(float_matrices.request().ptr), count, transpose);
        }, py::arg("name"), py::arg("matrices"), py::arg("count"), py::arg("transpose") = true)
        .def("set_uniform_auto", [](ShaderProgram& self, const char* name, py::object value) {
            // Automatic type inference for uniforms
            if (py::isinstance<py::array>(value) || py::isinstance<py::list>(value) || py::isinstance<py::tuple>(value)) {
                auto arr = py::array_t<float>::ensure(value);
                auto buf = arr.request();

                if (buf.ndim == 2 && buf.shape[0] == 4 && buf.shape[1] == 4) {
                    self.set_uniform_matrix4(name, static_cast<float*>(buf.ptr), true);
                } else if (buf.ndim == 1) {
                    auto data = static_cast<float*>(buf.ptr);
                    if (buf.size == 2) {
                        self.set_uniform_vec2(name, data[0], data[1]);
                    } else if (buf.size == 3) {
                        self.set_uniform_vec3(name, data[0], data[1], data[2]);
                    } else if (buf.size == 4) {
                        self.set_uniform_vec4(name, data[0], data[1], data[2], data[3]);
                    } else {
                        throw std::runtime_error("Unsupported uniform array size: " + std::to_string(buf.size));
                    }
                } else {
                    throw std::runtime_error("Unsupported uniform array shape");
                }
            } else if (py::isinstance<py::bool_>(value)) {
                self.set_uniform_int(name, value.cast<bool>() ? 1 : 0);
            } else if (py::isinstance<py::int_>(value)) {
                self.set_uniform_int(name, value.cast<int>());
            } else {
                self.set_uniform_float(name, value.cast<float>());
            }
        }, py::arg("name"), py::arg("value"), "Set uniform with automatic type inference")
        .def("delete", &ShaderProgram::release)
        .def("direct_serialize", [](const ShaderProgram& prog) -> py::dict {
            py::dict result;
            if (!prog.source_path().empty()) {
                result["type"] = "path";
                result["path"] = prog.source_path();
            } else {
                result["type"] = "inline";
                result["vertex"] = prog.vertex_source();
                result["fragment"] = prog.fragment_source();
                if (!prog.geometry_source().empty()) {
                    result["geometry"] = prog.geometry_source();
                }
            }
            return result;
        })
        .def_static("direct_deserialize", [](py::dict data) {
            std::string source_path;
            if (data.contains("type") && data["type"].cast<std::string>() == "path") {
                source_path = data["path"].cast<std::string>();
            }
            return ShaderProgram(
                data["vertex"].cast<std::string>(),
                data["fragment"].cast<std::string>(),
                data.contains("geometry") ? data["geometry"].cast<std::string>() : "",
                source_path
            );
        })
        .def_static("from_files", [](const std::string& vertex_path, const std::string& fragment_path) {
            auto read_file = [](const std::string& path) -> std::string {
                std::ifstream file(path);
                if (!file) {
                    throw std::runtime_error("Cannot open file: " + path);
                }
                std::stringstream buffer;
                buffer << file.rdbuf();
                return buffer.str();
            };
            return ShaderProgram(
                read_file(vertex_path),
                read_file(fragment_path),
                "",
                vertex_path
            );
        }, py::arg("vertex_path"), py::arg("fragment_path"), "Load shader from files")
        .def("__repr__", [](const ShaderProgram& prog) -> std::string {
            std::string path = prog.source_path().empty() ? "<inline>" : prog.source_path();
            return "<ShaderProgram " + path + (prog.is_compiled() ? " compiled>" : " not compiled>");
        });

    // --- Camera ---

    py::enum_<CameraProjection>(m, "CameraProjection")
        .value("Perspective", CameraProjection::Perspective)
        .value("Orthographic", CameraProjection::Orthographic);

    py::class_<Camera>(m, "Camera")
        .def(py::init<>())
        .def_readwrite("projection_type", &Camera::projection_type)
        .def_readwrite("near", &Camera::near)
        .def_readwrite("far", &Camera::far)
        .def_readwrite("fov_y", &Camera::fov_y)
        .def_readwrite("aspect", &Camera::aspect)
        .def_readwrite("ortho_left", &Camera::ortho_left)
        .def_readwrite("ortho_right", &Camera::ortho_right)
        .def_readwrite("ortho_bottom", &Camera::ortho_bottom)
        .def_readwrite("ortho_top", &Camera::ortho_top)
        .def_static("perspective", &Camera::perspective,
            py::arg("fov_y_rad"), py::arg("aspect"),
            py::arg("near") = 0.1, py::arg("far") = 100.0,
            "Create perspective camera (FOV in radians)")
        .def_static("perspective_deg", &Camera::perspective_deg,
            py::arg("fov_y_deg"), py::arg("aspect"),
            py::arg("near") = 0.1, py::arg("far") = 100.0,
            "Create perspective camera (FOV in degrees)")
        .def_static("orthographic", &Camera::orthographic,
            py::arg("left"), py::arg("right"),
            py::arg("bottom"), py::arg("top"),
            py::arg("near") = 0.1, py::arg("far") = 100.0,
            "Create orthographic camera")
        .def("projection_matrix", &Camera::projection_matrix,
            "Get projection matrix (Y-forward, Z-up)")
        .def_static("view_matrix", &Camera::view_matrix,
            py::arg("position"), py::arg("rotation"),
            "Compute view matrix from camera world pose")
        .def_static("view_matrix_look_at", &Camera::view_matrix_look_at,
            py::arg("eye"), py::arg("target"),
            py::arg("up") = Vec3::unit_z(),
            "Compute view matrix using look-at")
        .def("set_aspect", &Camera::set_aspect, py::arg("aspect"))
        .def("set_fov", &Camera::set_fov, py::arg("fov_rad"))
        .def("set_fov_deg", &Camera::set_fov_deg, py::arg("fov_deg"))
        .def("get_fov_deg", &Camera::get_fov_deg)
        .def("__repr__", [](const Camera& cam) -> std::string {
            if (cam.projection_type == CameraProjection::Perspective) {
                return "<Camera perspective fov=" + std::to_string(cam.get_fov_deg()) + "deg>";
            } else {
                return "<Camera orthographic>";
            }
        });
}

} // namespace termin
