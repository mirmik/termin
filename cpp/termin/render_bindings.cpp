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
#include "termin/render/shader_parser.hpp"
#include "termin/render/resource_spec.hpp"
#include "termin/render/shadow_camera.hpp"
#include "termin/render/immediate_renderer.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render/frame_graph.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/material.hpp"
#include "termin/render/drawable.hpp"
#include "termin/render/mesh_gpu.hpp"
#include "termin/render/texture_gpu.hpp"
#include "termin/render/mesh_renderer.hpp"
#include "termin/render/skinned_mesh_renderer.hpp"
#include "termin/assets/handles.hpp"
#include "termin/assets/texture_data.hpp"
#include "termin/camera/camera.hpp"
#include "termin/entity/entity.hpp"

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

    py::class_<GPUMeshHandle, std::unique_ptr<GPUMeshHandle>>(m, "GPUMeshHandle")
        .def("draw", &GPUMeshHandle::draw)
        .def("release", &GPUMeshHandle::release)
        .def("delete", &GPUMeshHandle::release);  // Alias for Python interface

    py::class_<GPUTextureHandle, std::unique_ptr<GPUTextureHandle>>(m, "GPUTextureHandle")
        .def("bind", &GPUTextureHandle::bind, py::arg("unit") = 0)
        .def("release", &GPUTextureHandle::release)
        .def("delete", &GPUTextureHandle::release)  // Alias for Python interface
        .def("get_id", &GPUTextureHandle::get_id)
        .def("get_width", &GPUTextureHandle::get_width)
        .def("get_height", &GPUTextureHandle::get_height);

    py::class_<FramebufferHandle, std::unique_ptr<FramebufferHandle>>(m, "FramebufferHandle")
        .def("resize", static_cast<void (FramebufferHandle::*)(int, int)>(&FramebufferHandle::resize))
        .def("resize", static_cast<void (FramebufferHandle::*)(Size2i)>(&FramebufferHandle::resize))
        .def("release", &FramebufferHandle::release)
        .def("delete", &FramebufferHandle::release)  // Alias for Python interface
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
        // create_external_framebuffer - wraps external FBO without allocating resources
        .def("create_external_framebuffer", &OpenGLGraphicsBackend::create_external_framebuffer,
            py::arg("fbo_id"), py::arg("width"), py::arg("height"),
            "Create handle wrapping an external FBO (e.g., window default FBO)")
        .def("create_external_framebuffer", [](OpenGLGraphicsBackend& self, uint32_t fbo_id, py::tuple size) {
            return self.create_external_framebuffer(fbo_id, size[0].cast<int>(), size[1].cast<int>());
        }, py::arg("fbo_id"), py::arg("size"))
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
        .def("create_mesh", [](OpenGLGraphicsBackend& self, py::object mesh, DrawMode mode) -> std::unique_ptr<GPUMeshHandle> {
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

    py::class_<ShaderProgram, std::shared_ptr<ShaderProgram>>(m, "ShaderProgram")
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

    // ========== Shader Parser ==========

    // MaterialProperty (UniformProperty)
    py::class_<MaterialProperty>(m, "MaterialProperty")
        .def(py::init<>())
        .def(py::init<std::string, std::string>(),
             py::arg("name"), py::arg("property_type"))
        // Full constructor with default value and range
        .def(py::init([](
            const std::string& name,
            const std::string& property_type,
            py::object default_val,
            std::optional<double> range_min,
            std::optional<double> range_max
        ) {
            MaterialProperty prop;
            prop.name = name;
            prop.property_type = property_type;
            prop.range_min = range_min;
            prop.range_max = range_max;

            // Convert Python default value to C++ variant
            if (default_val.is_none()) {
                prop.default_value = std::monostate{};
            } else if (py::isinstance<py::bool_>(default_val)) {
                prop.default_value = default_val.cast<bool>();
            } else if (py::isinstance<py::int_>(default_val)) {
                prop.default_value = default_val.cast<int>();
            } else if (py::isinstance<py::float_>(default_val)) {
                prop.default_value = default_val.cast<double>();
            } else if (py::isinstance<py::str>(default_val)) {
                prop.default_value = default_val.cast<std::string>();
            } else if (py::isinstance<py::tuple>(default_val) || py::isinstance<py::list>(default_val)) {
                std::vector<double> vec;
                for (auto item : default_val) {
                    vec.push_back(item.cast<double>());
                }
                prop.default_value = vec;
            }
            return prop;
        }),
            py::arg("name"),
            py::arg("property_type"),
            py::arg("default") = py::none(),
            py::arg("range_min") = std::nullopt,
            py::arg("range_max") = std::nullopt
        )
        .def_readwrite("name", &MaterialProperty::name)
        .def_readwrite("property_type", &MaterialProperty::property_type)
        .def_readwrite("range_min", &MaterialProperty::range_min)
        .def_readwrite("range_max", &MaterialProperty::range_max)
        .def_readwrite("label", &MaterialProperty::label)
        .def_property("default",
            [](const MaterialProperty& self) -> py::object {
                return std::visit([](auto&& arg) -> py::object {
                    using T = std::decay_t<decltype(arg)>;
                    if constexpr (std::is_same_v<T, std::monostate>) {
                        return py::none();
                    } else if constexpr (std::is_same_v<T, std::vector<double>>) {
                        py::tuple t(arg.size());
                        for (size_t i = 0; i < arg.size(); ++i) {
                            t[i] = arg[i];
                        }
                        return t;
                    } else {
                        return py::cast(arg);
                    }
                }, self.default_value);
            },
            [](MaterialProperty& self, py::object val) {
                if (val.is_none()) {
                    self.default_value = std::monostate{};
                } else if (py::isinstance<py::bool_>(val)) {
                    self.default_value = val.cast<bool>();
                } else if (py::isinstance<py::int_>(val)) {
                    self.default_value = val.cast<int>();
                } else if (py::isinstance<py::float_>(val)) {
                    self.default_value = val.cast<double>();
                } else if (py::isinstance<py::str>(val)) {
                    self.default_value = val.cast<std::string>();
                } else if (py::isinstance<py::tuple>(val) || py::isinstance<py::list>(val)) {
                    std::vector<double> vec;
                    for (auto item : val) {
                        vec.push_back(item.cast<double>());
                    }
                    self.default_value = vec;
                }
            }
        );

    // Alias for backward compatibility
    m.attr("UniformProperty") = m.attr("MaterialProperty");

    // ShaderStage
    py::class_<ShaderStage>(m, "ShaderStage")
        .def(py::init<>())
        .def(py::init<std::string, std::string>(),
             py::arg("name"), py::arg("source"))
        .def_readwrite("name", &ShaderStage::name)
        .def_readwrite("source", &ShaderStage::source);

    // Alias for typo compatibility
    m.attr("ShasderStage") = m.attr("ShaderStage");

    // ShaderPhase
    py::class_<ShaderPhase>(m, "ShaderPhase")
        .def(py::init<>())
        .def(py::init<std::string>(), py::arg("phase_mark"))
        // Full constructor with all parameters
        .def(py::init([](
            const std::string& phase_mark,
            int priority,
            std::optional<bool> gl_depth_mask,
            std::optional<bool> gl_depth_test,
            std::optional<bool> gl_blend,
            std::optional<bool> gl_cull,
            const std::unordered_map<std::string, ShaderStage>& stages,
            const std::vector<MaterialProperty>& uniforms
        ) {
            ShaderPhase phase;
            phase.phase_mark = phase_mark;
            phase.priority = priority;
            phase.gl_depth_mask = gl_depth_mask;
            phase.gl_depth_test = gl_depth_test;
            phase.gl_blend = gl_blend;
            phase.gl_cull = gl_cull;
            phase.stages = stages;
            phase.uniforms = uniforms;
            return phase;
        }),
            py::arg("phase_mark"),
            py::arg("priority") = 0,
            py::arg("gl_depth_mask") = std::nullopt,
            py::arg("gl_depth_test") = std::nullopt,
            py::arg("gl_blend") = std::nullopt,
            py::arg("gl_cull") = std::nullopt,
            py::arg("stages") = std::unordered_map<std::string, ShaderStage>{},
            py::arg("uniforms") = std::vector<MaterialProperty>{}
        )
        .def_readwrite("phase_mark", &ShaderPhase::phase_mark)
        .def_readwrite("priority", &ShaderPhase::priority)
        .def_readwrite("gl_depth_mask", &ShaderPhase::gl_depth_mask)
        .def_readwrite("gl_depth_test", &ShaderPhase::gl_depth_test)
        .def_readwrite("gl_blend", &ShaderPhase::gl_blend)
        .def_readwrite("gl_cull", &ShaderPhase::gl_cull)
        .def_readwrite("stages", &ShaderPhase::stages)
        .def_readwrite("uniforms", &ShaderPhase::uniforms)
        // Backward compatibility: identity transform
        .def_static("from_tree", [](const ShaderPhase& phase) {
            return phase;
        }, py::arg("tree"), "Backward compatibility: returns the object as-is");

    // ShaderMultyPhaseProgramm
    py::class_<ShaderMultyPhaseProgramm>(m, "ShaderMultyPhaseProgramm")
        .def(py::init<>())
        .def(py::init<std::string, std::vector<ShaderPhase>, std::string>(),
             py::arg("program"), py::arg("phases"), py::arg("source_path") = "")
        .def_readwrite("program", &ShaderMultyPhaseProgramm::program)
        .def_readwrite("phases", &ShaderMultyPhaseProgramm::phases)
        .def_readwrite("source_path", &ShaderMultyPhaseProgramm::source_path)
        .def("get_phase", &ShaderMultyPhaseProgramm::get_phase,
             py::arg("mark"), py::return_value_policy::reference)
        // Backward compatibility: parse_shader_text now returns ShaderMultyPhaseProgramm directly
        .def_static("from_tree", [](const ShaderMultyPhaseProgramm& prog) {
            return prog;  // Identity - already parsed
        }, py::arg("tree"), "Backward compatibility: returns the object as-is");

    // Parser functions
    m.def("parse_shader_text", &parse_shader_text,
          py::arg("text"),
          "Parse shader text in custom format");

    m.def("parse_property_directive", &parse_property_directive,
          py::arg("line"),
          "Parse @property directive line");

    // ========== ResourceSpec ==========

    py::class_<ResourceSpec>(m, "ResourceSpec")
        .def(py::init<>())
        .def(py::init<std::string, std::string>(),
             py::arg("resource"),
             py::arg("resource_type") = "fbo")
        // Full constructor
        .def(py::init([](
            const std::string& resource,
            const std::string& resource_type,
            py::object size,
            py::object clear_color,
            py::object clear_depth,
            py::object format,
            int samples
        ) {
            ResourceSpec spec;
            spec.resource = resource;
            spec.resource_type = resource_type;
            spec.samples = samples;

            if (!size.is_none()) {
                auto t = size.cast<py::tuple>();
                spec.size = std::make_pair(t[0].cast<int>(), t[1].cast<int>());
            }
            if (!clear_color.is_none()) {
                auto t = clear_color.cast<py::tuple>();
                spec.clear_color = std::array<double, 4>{
                    t[0].cast<double>(), t[1].cast<double>(),
                    t[2].cast<double>(), t[3].cast<double>()
                };
            }
            if (!clear_depth.is_none()) {
                spec.clear_depth = clear_depth.cast<float>();
            }
            if (!format.is_none()) {
                spec.format = format.cast<std::string>();
            }
            return spec;
        }),
            py::arg("resource"),
            py::arg("resource_type") = "fbo",
            py::arg("size") = py::none(),
            py::arg("clear_color") = py::none(),
            py::arg("clear_depth") = py::none(),
            py::arg("format") = py::none(),
            py::arg("samples") = 1
        )
        .def_readwrite("resource", &ResourceSpec::resource)
        .def_readwrite("resource_type", &ResourceSpec::resource_type)
        .def_readwrite("samples", &ResourceSpec::samples)
        // size property: optional<pair<int,int>> <-> tuple or None
        .def_property("size",
            [](const ResourceSpec& self) -> py::object {
                if (self.size) {
                    return py::make_tuple(self.size->first, self.size->second);
                }
                return py::none();
            },
            [](ResourceSpec& self, py::object val) {
                if (val.is_none()) {
                    self.size = std::nullopt;
                } else {
                    auto t = val.cast<py::tuple>();
                    self.size = std::make_pair(t[0].cast<int>(), t[1].cast<int>());
                }
            }
        )
        // clear_color property: optional<array<float,4>> <-> tuple or None
        .def_property("clear_color",
            [](const ResourceSpec& self) -> py::object {
                if (self.clear_color) {
                    auto& c = *self.clear_color;
                    return py::make_tuple(c[0], c[1], c[2], c[3]);
                }
                return py::none();
            },
            [](ResourceSpec& self, py::object val) {
                if (val.is_none()) {
                    self.clear_color = std::nullopt;
                } else {
                    auto t = val.cast<py::tuple>();
                    self.clear_color = std::array<double, 4>{
                        t[0].cast<double>(), t[1].cast<double>(),
                        t[2].cast<double>(), t[3].cast<double>()
                    };
                }
            }
        )
        // clear_depth property: optional<float> <-> float or None
        .def_property("clear_depth",
            [](const ResourceSpec& self) -> py::object {
                if (self.clear_depth) {
                    return py::cast(*self.clear_depth);
                }
                return py::none();
            },
            [](ResourceSpec& self, py::object val) {
                if (val.is_none()) {
                    self.clear_depth = std::nullopt;
                } else {
                    self.clear_depth = val.cast<float>();
                }
            }
        )
        // format property: optional<string> <-> str or None
        .def_property("format",
            [](const ResourceSpec& self) -> py::object {
                if (self.format) {
                    return py::cast(*self.format);
                }
                return py::none();
            },
            [](ResourceSpec& self, py::object val) {
                if (val.is_none()) {
                    self.format = std::nullopt;
                } else {
                    self.format = val.cast<std::string>();
                }
            }
        )
        // serialize() method - returns lists for JSON compatibility
        .def("serialize", [](const ResourceSpec& self) -> py::dict {
            py::dict data;
            data["resource"] = self.resource;
            data["resource_type"] = self.resource_type;
            if (self.size) {
                py::list size_list;
                size_list.append(self.size->first);
                size_list.append(self.size->second);
                data["size"] = size_list;
            }
            if (self.clear_color) {
                auto& c = *self.clear_color;
                py::list color_list;
                color_list.append(c[0]);
                color_list.append(c[1]);
                color_list.append(c[2]);
                color_list.append(c[3]);
                data["clear_color"] = color_list;
            }
            if (self.clear_depth) {
                data["clear_depth"] = *self.clear_depth;
            }
            if (self.format) {
                data["format"] = *self.format;
            }
            if (self.samples != 1) {
                data["samples"] = self.samples;
            }
            return data;
        })
        // deserialize() classmethod - handles both list and tuple
        .def_static("deserialize", [](py::dict data) -> ResourceSpec {
            ResourceSpec spec;
            spec.resource = data.contains("resource") ?
                data["resource"].cast<std::string>() : "";
            spec.resource_type = data.contains("resource_type") ?
                data["resource_type"].cast<std::string>() : "fbo";
            spec.samples = data.contains("samples") ?
                data["samples"].cast<int>() : 1;

            if (data.contains("size")) {
                py::object size_obj = data["size"];
                spec.size = std::make_pair(
                    size_obj[py::int_(0)].cast<int>(),
                    size_obj[py::int_(1)].cast<int>()
                );
            }
            if (data.contains("clear_color")) {
                py::object color_obj = data["clear_color"];
                spec.clear_color = std::array<double, 4>{
                    color_obj[py::int_(0)].cast<double>(),
                    color_obj[py::int_(1)].cast<double>(),
                    color_obj[py::int_(2)].cast<double>(),
                    color_obj[py::int_(3)].cast<double>()
                };
            }
            if (data.contains("clear_depth")) {
                spec.clear_depth = data["clear_depth"].cast<float>();
            }
            if (data.contains("format")) {
                spec.format = data["format"].cast<std::string>();
            }
            return spec;
        }, py::arg("data"));

    // ========== Shadow Camera ==========

    py::class_<ShadowCameraParams>(m, "ShadowCameraParams")
        .def(py::init<>())
        .def(py::init([](
            py::array_t<double> light_direction,
            py::object ortho_bounds,
            double ortho_size,
            double near,
            double far,
            py::object center
        ) {
            auto dir_buf = light_direction.request();
            Vec3 light_dir{
                static_cast<double*>(dir_buf.ptr)[0],
                static_cast<double*>(dir_buf.ptr)[1],
                static_cast<double*>(dir_buf.ptr)[2]
            };

            std::optional<std::array<float, 4>> bounds;
            if (!ortho_bounds.is_none()) {
                auto t = ortho_bounds.cast<py::tuple>();
                bounds = std::array<float, 4>{
                    static_cast<float>(t[0].cast<double>()),
                    static_cast<float>(t[1].cast<double>()),
                    static_cast<float>(t[2].cast<double>()),
                    static_cast<float>(t[3].cast<double>())
                };
            }

            Vec3 c{0, 0, 0};
            if (!center.is_none()) {
                auto arr = center.cast<py::array_t<double>>();
                auto buf = arr.request();
                c = Vec3{
                    static_cast<double*>(buf.ptr)[0],
                    static_cast<double*>(buf.ptr)[1],
                    static_cast<double*>(buf.ptr)[2]
                };
            }

            return ShadowCameraParams(light_dir, bounds, static_cast<float>(ortho_size), static_cast<float>(near), static_cast<float>(far), c);
        }),
            py::arg("light_direction"),
            py::arg("ortho_bounds") = py::none(),
            py::arg("ortho_size") = 20.0,
            py::arg("near") = 0.1,
            py::arg("far") = 100.0,
            py::arg("center") = py::none()
        )
        // Properties
        .def_property("light_direction",
            [](const ShadowCameraParams& self) {
                return py::array_t<double>({3}, {sizeof(double)},
                    &self.light_direction.x);
            },
            [](ShadowCameraParams& self, py::array_t<double> arr) {
                auto buf = arr.request();
                auto* ptr = static_cast<double*>(buf.ptr);
                self.light_direction = Vec3{ptr[0], ptr[1], ptr[2]}.normalized();
            }
        )
        .def_property("ortho_bounds",
            [](const ShadowCameraParams& self) -> py::object {
                if (self.ortho_bounds) {
                    auto& b = *self.ortho_bounds;
                    return py::make_tuple(b[0], b[1], b[2], b[3]);
                }
                return py::none();
            },
            [](ShadowCameraParams& self, py::object val) {
                if (val.is_none()) {
                    self.ortho_bounds = std::nullopt;
                } else {
                    auto t = val.cast<py::tuple>();
                    self.ortho_bounds = std::array<float, 4>{
                        static_cast<float>(t[0].cast<double>()),
                        static_cast<float>(t[1].cast<double>()),
                        static_cast<float>(t[2].cast<double>()),
                        static_cast<float>(t[3].cast<double>())
                    };
                }
            }
        )
        .def_readwrite("ortho_size", &ShadowCameraParams::ortho_size)
        .def_readwrite("near", &ShadowCameraParams::near)
        .def_readwrite("far", &ShadowCameraParams::far)
        .def_property("center",
            [](const ShadowCameraParams& self) {
                return py::array_t<double>({3}, {sizeof(double)}, &self.center.x);
            },
            [](ShadowCameraParams& self, py::array_t<double> arr) {
                auto buf = arr.request();
                auto* ptr = static_cast<double*>(buf.ptr);
                self.center = Vec3{ptr[0], ptr[1], ptr[2]};
            }
        );

    // Shadow camera functions
    // Note: Mat44.data is column-major flat array: data[col*4 + row]
    // Python numpy uses row-major by default, so we need to transpose

    m.def("build_shadow_view_matrix", [](const ShadowCameraParams& params) {
        Mat44f mat = build_shadow_view_matrix(params);
        py::array_t<double> result({4, 4});
        auto buf = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                // Mat44f is column-major: data[col*4 + row], convert to double
                buf(row, col) = static_cast<double>(mat.data[col * 4 + row]);
            }
        }
        return result;
    }, py::arg("params"), "Build view matrix for shadow camera");

    m.def("build_shadow_projection_matrix", [](const ShadowCameraParams& params) {
        Mat44f mat = build_shadow_projection_matrix(params);
        py::array_t<double> result({4, 4});
        auto buf = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                buf(row, col) = static_cast<double>(mat.data[col * 4 + row]);
            }
        }
        return result;
    }, py::arg("params"), "Build orthographic projection matrix for shadow camera");

    m.def("compute_light_space_matrix", [](const ShadowCameraParams& params) {
        Mat44f mat = compute_light_space_matrix(params);
        py::array_t<double> result({4, 4});
        auto buf = result.mutable_unchecked<2>();
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                buf(row, col) = static_cast<double>(mat.data[col * 4 + row]);
            }
        }
        return result;
    }, py::arg("params"), "Compute combined light space matrix (projection * view)");

    m.def("compute_frustum_corners", [](py::array_t<double> view, py::array_t<double> proj) {
        auto view_buf = view.unchecked<2>();
        auto proj_buf = proj.unchecked<2>();

        Mat44f view_mat, proj_mat;
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                // Python row-major to C++ column-major, double to float
                view_mat.data[col * 4 + row] = static_cast<float>(view_buf(row, col));
                proj_mat.data[col * 4 + row] = static_cast<float>(proj_buf(row, col));
            }
        }

        auto corners = compute_frustum_corners(view_mat, proj_mat);

        py::array_t<double> result({8, 3});
        auto buf = result.mutable_unchecked<2>();
        for (int i = 0; i < 8; ++i) {
            buf(i, 0) = corners[i].x;
            buf(i, 1) = corners[i].y;
            buf(i, 2) = corners[i].z;
        }
        return result;
    }, py::arg("view_matrix"), py::arg("projection_matrix"),
       "Compute 8 corners of view frustum in world space");

    m.def("fit_shadow_frustum_to_camera", [](
        py::array_t<double> view,
        py::array_t<double> proj,
        py::array_t<double> light_direction,
        double padding,
        int shadow_map_resolution,
        bool stabilize,
        double caster_offset
    ) {
        auto view_buf = view.unchecked<2>();
        auto proj_buf = proj.unchecked<2>();
        auto dir_buf = light_direction.request();

        Mat44f view_mat, proj_mat;
        for (int row = 0; row < 4; ++row) {
            for (int col = 0; col < 4; ++col) {
                // Python row-major to C++ column-major, double to float
                view_mat.data[col * 4 + row] = static_cast<float>(view_buf(row, col));
                proj_mat.data[col * 4 + row] = static_cast<float>(proj_buf(row, col));
            }
        }

        auto* dir_ptr = static_cast<double*>(dir_buf.ptr);
        Vec3 light_dir{dir_ptr[0], dir_ptr[1], dir_ptr[2]};

        return fit_shadow_frustum_to_camera(
            view_mat, proj_mat, light_dir,
            static_cast<float>(padding), shadow_map_resolution, stabilize, static_cast<float>(caster_offset)
        );
    },
        py::arg("view_matrix"),
        py::arg("projection_matrix"),
        py::arg("light_direction"),
        py::arg("padding") = 1.0,
        py::arg("shadow_map_resolution") = 1024,
        py::arg("stabilize") = true,
        py::arg("caster_offset") = 50.0,
        "Fit shadow camera to view frustum"
    );

    // --- ImmediateRenderer ---
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

    // ========== Frame Pass System ==========

    // FramePass base class
    py::class_<FramePass>(m, "FramePass")
        .def(py::init<>())
        .def(py::init<std::string, std::set<std::string>, std::set<std::string>>(),
             py::arg("pass_name"),
             py::arg("reads") = std::set<std::string>{},
             py::arg("writes") = std::set<std::string>{})
        .def_readwrite("pass_name", &FramePass::pass_name)
        .def_readwrite("reads", &FramePass::reads)
        .def_readwrite("writes", &FramePass::writes)
        .def_readwrite("enabled", &FramePass::enabled)
        .def("get_inplace_aliases", &FramePass::get_inplace_aliases)
        .def("is_inplace", &FramePass::is_inplace)
        .def("get_internal_symbols", &FramePass::get_internal_symbols)
        .def("set_debug_internal_point", &FramePass::set_debug_internal_point)
        .def("clear_debug_internal_point", &FramePass::clear_debug_internal_point)
        .def("get_debug_internal_point", &FramePass::get_debug_internal_point)
        .def("required_resources", &FramePass::required_resources)
        .def("__repr__", [](const FramePass& p) {
            return "<FramePass '" + p.pass_name + "'>";
        });

    // FrameGraph errors
    py::register_exception<FrameGraphError>(m, "FrameGraphError");
    py::register_exception<FrameGraphMultiWriterError>(m, "FrameGraphMultiWriterError");
    py::register_exception<FrameGraphCycleError>(m, "FrameGraphCycleError");

    // FrameGraph
    py::class_<FrameGraph>(m, "FrameGraph")
        .def(py::init([](py::list passes) {
            std::vector<FramePass*> pass_ptrs;
            for (auto item : passes) {
                pass_ptrs.push_back(item.cast<FramePass*>());
            }
            return FrameGraph(pass_ptrs);
        }), py::arg("passes"))
        .def("build_schedule", [](FrameGraph& self) {
            auto schedule = self.build_schedule();
            py::list result;
            for (auto* p : schedule) {
                result.append(py::cast(p, py::return_value_policy::reference));
            }
            return result;
        })
        .def("canonical_resource", &FrameGraph::canonical_resource)
        .def("fbo_alias_groups", &FrameGraph::fbo_alias_groups);

    // RenderContext
    py::class_<RenderContext>(m, "RenderContext")
        .def(py::init<>())
        // Constructor with keyword arguments for Python compatibility
        .def(py::init([](py::kwargs kwargs) {
            auto ctx = new RenderContext();

            if (kwargs.contains("context_key")) {
                ctx->context_key = kwargs["context_key"].cast<int64_t>();
            }
            if (kwargs.contains("phase")) {
                ctx->phase = kwargs["phase"].cast<std::string>();
            }
            if (kwargs.contains("scene")) {
                ctx->scene = kwargs["scene"];
            }
            if (kwargs.contains("shadow_data")) {
                ctx->shadow_data = kwargs["shadow_data"];
            }
            if (kwargs.contains("extra_uniforms")) {
                ctx->extra_uniforms = kwargs["extra_uniforms"];
            }
            if (kwargs.contains("camera")) {
                ctx->camera = kwargs["camera"];
            }
            if (kwargs.contains("graphics")) {
                py::object g_obj = kwargs["graphics"];
                if (!g_obj.is_none()) {
                    ctx->graphics = g_obj.cast<GraphicsBackend*>();
                }
            }
            if (kwargs.contains("current_shader")) {
                py::object s_obj = kwargs["current_shader"];
                if (!s_obj.is_none()) {
                    ctx->current_shader = s_obj.cast<ShaderProgram*>();
                }
            }
            if (kwargs.contains("view")) {
                py::array_t<float> arr = kwargs["view"].cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        ctx->view.data[col * 4 + row] = buf(row, col);
                    }
                }
            }
            if (kwargs.contains("projection")) {
                py::array_t<float> arr = kwargs["projection"].cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        ctx->projection.data[col * 4 + row] = buf(row, col);
                    }
                }
            }
            if (kwargs.contains("model")) {
                py::array_t<float> arr = kwargs["model"].cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        ctx->model.data[col * 4 + row] = buf(row, col);
                    }
                }
            }

            return ctx;
        }))
        .def_readwrite("context_key", &RenderContext::context_key)
        .def_readwrite("phase", &RenderContext::phase)
        .def_readwrite("scene", &RenderContext::scene)
        .def_readwrite("shadow_data", &RenderContext::shadow_data)
        .def_readwrite("extra_uniforms", &RenderContext::extra_uniforms)  // py::object (dict)
        .def_readwrite("camera", &RenderContext::camera)  // py::object (Camera or CameraComponent)
        // graphics
        .def_property("graphics",
            [](const RenderContext& self) -> GraphicsBackend* { return self.graphics; },
            [](RenderContext& self, GraphicsBackend* g) { self.graphics = g; },
            py::return_value_policy::reference)
        // current_shader
        .def_property("current_shader",
            [](const RenderContext& self) -> ShaderProgram* { return self.current_shader; },
            [](RenderContext& self, ShaderProgram* s) { self.current_shader = s; },
            py::return_value_policy::reference)
        // view matrix
        .def_property("view",
            [](const RenderContext& self) {
                py::array_t<float> result({4, 4});
                auto buf = result.mutable_unchecked<2>();
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        buf(row, col) = self.view.data[col * 4 + row];
                    }
                }
                return result;
            },
            [](RenderContext& self, py::array_t<float> arr) {
                auto buf = arr.unchecked<2>();
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        self.view.data[col * 4 + row] = buf(row, col);
                    }
                }
            }
        )
        // projection matrix
        .def_property("projection",
            [](const RenderContext& self) {
                py::array_t<float> result({4, 4});
                auto buf = result.mutable_unchecked<2>();
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        buf(row, col) = self.projection.data[col * 4 + row];
                    }
                }
                return result;
            },
            [](RenderContext& self, py::array_t<float> arr) {
                auto buf = arr.unchecked<2>();
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        self.projection.data[col * 4 + row] = buf(row, col);
                    }
                }
            }
        )
        // model matrix
        .def_property("model",
            [](const RenderContext& self) {
                py::array_t<float> result({4, 4});
                auto buf = result.mutable_unchecked<2>();
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        buf(row, col) = self.model.data[col * 4 + row];
                    }
                }
                return result;
            },
            [](RenderContext& self, py::array_t<float> arr) {
                auto buf = arr.unchecked<2>();
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        self.model.data[col * 4 + row] = buf(row, col);
                    }
                }
            }
        )
        .def("set_model", [](RenderContext& self, py::array_t<float> arr) {
            auto buf = arr.unchecked<2>();
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    self.model.data[col * 4 + row] = buf(row, col);
                }
            }
        })
        .def("mvp", [](const RenderContext& self) {
            Mat44f mvp = self.mvp();
            py::array_t<float> result({4, 4});
            auto buf = result.mutable_unchecked<2>();
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    buf(row, col) = mvp.data[col * 4 + row];
                }
            }
            return result;
        });

    // ========== Material System ==========

    // MaterialPhase
    py::class_<MaterialPhase, std::shared_ptr<MaterialPhase>>(m, "MaterialPhase")
        .def(py::init<>())
        .def(py::init([](std::shared_ptr<ShaderProgram> shader, const RenderState& rs,
                         const std::string& phase_mark, int priority) {
            return std::make_shared<MaterialPhase>(shader, rs, phase_mark, priority);
        }), py::arg("shader"), py::arg("render_state") = RenderState::opaque(),
            py::arg("phase_mark") = "opaque", py::arg("priority") = 0)
        // Python-compatible kwargs constructor (supports shader_programm, color)
        .def(py::init([](py::kwargs kwargs) {
            std::shared_ptr<ShaderProgram> shader;
            if (kwargs.contains("shader_programm")) {
                shader = kwargs["shader_programm"].cast<std::shared_ptr<ShaderProgram>>();
            } else if (kwargs.contains("shader")) {
                shader = kwargs["shader"].cast<std::shared_ptr<ShaderProgram>>();
            }
            if (!shader) {
                throw std::runtime_error("MaterialPhase requires 'shader' or 'shader_programm' argument");
            }

            RenderState rs = RenderState::opaque();
            if (kwargs.contains("render_state")) {
                rs = kwargs["render_state"].cast<RenderState>();
            }

            std::string phase_mark = "opaque";
            if (kwargs.contains("phase_mark")) {
                phase_mark = kwargs["phase_mark"].cast<std::string>();
            }

            int priority = 0;
            if (kwargs.contains("priority")) {
                priority = kwargs["priority"].cast<int>();
            }

            auto phase = std::make_shared<MaterialPhase>(shader, rs, phase_mark, priority);

            // Set color
            if (kwargs.contains("color") && !kwargs["color"].is_none()) {
                auto arr = py::array_t<float>::ensure(kwargs["color"]);
                auto buf = arr.unchecked<1>();
                phase->set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
            }

            // Set textures
            if (kwargs.contains("textures") && !kwargs["textures"].is_none()) {
                py::dict tex_dict = kwargs["textures"].cast<py::dict>();
                for (auto item : tex_dict) {
                    std::string key = item.first.cast<std::string>();
                    phase->textures[key] = item.second.cast<TextureHandle>();
                }
            }

            // Set uniforms
            if (kwargs.contains("uniforms") && !kwargs["uniforms"].is_none()) {
                py::dict uniforms_dict = kwargs["uniforms"].cast<py::dict>();
                for (auto item : uniforms_dict) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        phase->uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        phase->uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        phase->uniforms[key] = val.cast<float>();
                    }
                }
            }

            return phase;
        }))
        .def_readwrite("shader", &MaterialPhase::shader)
        .def_readwrite("shader_programm", &MaterialPhase::shader)  // Python compatibility alias
        .def_readwrite("render_state", &MaterialPhase::render_state)
        .def_property("color",
            [](MaterialPhase& self) -> py::object {
                if (!self.color.has_value()) return py::none();
                Vec4 c = self.color.value();
                auto result = py::array_t<float>(4);
                auto buf = result.mutable_unchecked<1>();
                buf(0) = static_cast<float>(c.x);
                buf(1) = static_cast<float>(c.y);
                buf(2) = static_cast<float>(c.z);
                buf(3) = static_cast<float>(c.w);
                return result;
            },
            [](MaterialPhase& self, py::object val) {
                if (val.is_none()) {
                    self.color = std::nullopt;
                } else {
                    auto arr = py::array_t<float>::ensure(val);
                    auto buf = arr.unchecked<1>();
                    self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
                }
            })
        .def_readwrite("phase_mark", &MaterialPhase::phase_mark)
        .def_readwrite("priority", &MaterialPhase::priority)
        .def_readwrite("textures", &MaterialPhase::textures)
        .def_property("uniforms",
            [](MaterialPhase& self) -> py::dict {
                py::dict result;
                for (const auto& [key, val] : self.uniforms) {
                    std::visit([&](auto&& arg) {
                        using T = std::decay_t<decltype(arg)>;
                        if constexpr (std::is_same_v<T, bool>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, int>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, float>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, Vec3>) {
                            auto arr = py::array_t<float>(3);
                            auto buf = arr.mutable_unchecked<1>();
                            buf(0) = arg.x;
                            buf(1) = arg.y;
                            buf(2) = arg.z;
                            result[key.c_str()] = arr;
                        } else if constexpr (std::is_same_v<T, Vec4>) {
                            auto arr = py::array_t<float>(4);
                            auto buf = arr.mutable_unchecked<1>();
                            buf(0) = arg.x;
                            buf(1) = arg.y;
                            buf(2) = arg.z;
                            buf(3) = arg.w;
                            result[key.c_str()] = arr;
                        }
                    }, val);
                }
                return result;
            },
            [](MaterialPhase& self, py::dict uniforms) {
                for (auto item : uniforms) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        self.uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        self.uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        self.uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::array>(val)) {
                        auto arr = py::array_t<float>::ensure(val);
                        auto buf = arr.request();
                        if (buf.size == 3) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            self.uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (buf.size == 4) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            self.uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            })
        .def("set_texture", [](MaterialPhase& self, const std::string& name, const TextureHandle& tex) {
            self.textures[name] = tex;
        })
        .def("set_param", [](MaterialPhase& self, const std::string& name, py::object value) {
            if (py::isinstance<py::bool_>(value)) {
                self.set_param(name, value.cast<bool>());
            } else if (py::isinstance<py::int_>(value)) {
                self.set_param(name, value.cast<int>());
            } else if (py::isinstance<py::float_>(value)) {
                self.set_param(name, value.cast<float>());
            } else if (py::isinstance<py::array>(value)) {
                auto arr = py::array_t<float>::ensure(value);
                auto buf = arr.request();
                if (buf.size == 3) {
                    auto* ptr = static_cast<float*>(buf.ptr);
                    self.set_param(name, Vec3{ptr[0], ptr[1], ptr[2]});
                } else if (buf.size == 4) {
                    auto* ptr = static_cast<float*>(buf.ptr);
                    self.set_param(name, Vec4{ptr[0], ptr[1], ptr[2], ptr[3]});
                }
            }
        })
        .def("set_color", [](MaterialPhase& self, py::array_t<float> rgba) {
            auto buf = rgba.unchecked<1>();
            self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
        })
        .def("update_color", [](MaterialPhase& self, py::array_t<float> rgba) {
            auto buf = rgba.unchecked<1>();
            self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
        })
        .def("apply", [](MaterialPhase& self,
                         py::array_t<float> model,
                         py::array_t<float> view,
                         py::array_t<float> proj,
                         GraphicsBackend* graphics,
                         int64_t context_key) {
            auto m_buf = model.unchecked<2>();
            auto v_buf = view.unchecked<2>();
            auto p_buf = proj.unchecked<2>();

            Mat44f m_mat, v_mat, p_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    m_mat.data[col * 4 + row] = m_buf(row, col);
                    v_mat.data[col * 4 + row] = v_buf(row, col);
                    p_mat.data[col * 4 + row] = p_buf(row, col);
                }
            }
            self.apply(m_mat, v_mat, p_mat, graphics, context_key);
        }, py::arg("model"), py::arg("view"), py::arg("projection"),
           py::arg("graphics"), py::arg("context_key") = 0)
        .def("apply_state", &MaterialPhase::apply_state)
        .def("copy", &MaterialPhase::copy)
        // serialize - serialize MaterialPhase to dict
        .def("serialize", [](const MaterialPhase& self) -> py::dict {
            py::dict result;
            result["phase_mark"] = self.phase_mark;
            result["priority"] = self.priority;

            // Color
            if (self.color.has_value()) {
                Vec4 c = self.color.value();
                py::list col_list;
                col_list.append(c.x);
                col_list.append(c.y);
                col_list.append(c.z);
                col_list.append(c.w);
                result["color"] = col_list;
            } else {
                result["color"] = py::none();
            }

            // Uniforms
            py::dict uniforms_dict;
            for (const auto& [key, val] : self.uniforms) {
                std::visit([&](auto&& arg) {
                    using T = std::decay_t<decltype(arg)>;
                    if constexpr (std::is_same_v<T, bool>) {
                        uniforms_dict[key.c_str()] = arg;
                    } else if constexpr (std::is_same_v<T, int>) {
                        uniforms_dict[key.c_str()] = arg;
                    } else if constexpr (std::is_same_v<T, float>) {
                        uniforms_dict[key.c_str()] = arg;
                    } else if constexpr (std::is_same_v<T, Vec3>) {
                        py::list vec;
                        vec.append(arg.x);
                        vec.append(arg.y);
                        vec.append(arg.z);
                        uniforms_dict[key.c_str()] = vec;
                    } else if constexpr (std::is_same_v<T, Vec4>) {
                        py::list vec;
                        vec.append(arg.x);
                        vec.append(arg.y);
                        vec.append(arg.z);
                        vec.append(arg.w);
                        uniforms_dict[key.c_str()] = vec;
                    }
                }, val);
            }
            result["uniforms"] = uniforms_dict;

            // Textures - store source_path
            py::dict textures_dict;
            for (const auto& [key, tex] : self.textures) {
                std::string path = tex.source_path();
                if (!path.empty()) {
                    textures_dict[key.c_str()] = path;
                }
            }
            result["textures"] = textures_dict;

            // Render state
            py::dict rs_dict;
            rs_dict["depth_test"] = self.render_state.depth_test;
            rs_dict["depth_write"] = self.render_state.depth_write;
            rs_dict["blend"] = self.render_state.blend;
            rs_dict["cull"] = self.render_state.cull;
            result["render_state"] = rs_dict;

            // Shader sources
            py::dict shader_dict;
            if (self.shader) {
                shader_dict["vertex"] = self.shader->vertex_source();
                shader_dict["fragment"] = self.shader->fragment_source();
                shader_dict["geometry"] = self.shader->geometry_source();
            }
            result["shader"] = shader_dict;

            return result;
        })
        // deserialize - deserialize MaterialPhase from dict
        .def_static("deserialize", [](py::dict data, py::object context) -> std::shared_ptr<MaterialPhase> {
            // Get shader sources
            py::dict shader_data = data["shader"].cast<py::dict>();
            std::string vs = shader_data["vertex"].cast<std::string>();
            std::string fs = shader_data["fragment"].cast<std::string>();
            std::string gs = shader_data.contains("geometry") ?
                shader_data["geometry"].cast<std::string>() : "";

            auto shader = std::make_shared<ShaderProgram>(vs, fs, gs, "");

            // Get render state
            RenderState rs;
            if (data.contains("render_state")) {
                py::dict rs_data = data["render_state"].cast<py::dict>();
                rs.depth_test = rs_data.contains("depth_test") ?
                    rs_data["depth_test"].cast<bool>() : true;
                rs.depth_write = rs_data.contains("depth_write") ?
                    rs_data["depth_write"].cast<bool>() : true;
                rs.blend = rs_data.contains("blend") ?
                    rs_data["blend"].cast<bool>() : false;
                rs.cull = rs_data.contains("cull") ?
                    rs_data["cull"].cast<bool>() : true;
            }

            std::string phase_mark = data.contains("phase_mark") ?
                data["phase_mark"].cast<std::string>() : "opaque";
            int priority = data.contains("priority") ?
                data["priority"].cast<int>() : 0;

            auto phase = std::make_shared<MaterialPhase>(shader, rs, phase_mark, priority);

            // Color
            if (data.contains("color") && !data["color"].is_none()) {
                py::list color_list = data["color"].cast<py::list>();
                if (py::len(color_list) >= 4) {
                    phase->set_color(Vec4{
                        color_list[0].cast<float>(),
                        color_list[1].cast<float>(),
                        color_list[2].cast<float>(),
                        color_list[3].cast<float>()
                    });
                }
            }

            // Uniforms
            if (data.contains("uniforms")) {
                py::dict uniforms_dict = data["uniforms"].cast<py::dict>();
                for (auto item : uniforms_dict) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::list>(val)) {
                        py::list lst = val.cast<py::list>();
                        if (py::len(lst) == 3) {
                            phase->uniforms[key] = Vec3{
                                lst[0].cast<float>(),
                                lst[1].cast<float>(),
                                lst[2].cast<float>()
                            };
                        } else if (py::len(lst) == 4) {
                            phase->uniforms[key] = Vec4{
                                lst[0].cast<float>(),
                                lst[1].cast<float>(),
                                lst[2].cast<float>(),
                                lst[3].cast<float>()
                            };
                        }
                    } else if (py::isinstance<py::float_>(val)) {
                        phase->uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::int_>(val)) {
                        phase->uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::bool_>(val)) {
                        phase->uniforms[key] = val.cast<bool>();
                    }
                }
            }

            // Textures (if context provided)
            if (data.contains("textures") && !context.is_none()) {
                py::dict textures_dict = data["textures"].cast<py::dict>();
                for (auto item : textures_dict) {
                    std::string key = item.first.cast<std::string>();
                    std::string path = item.second.cast<std::string>();
                    if (py::hasattr(context, "load_texture")) {
                        phase->textures[key] = context.attr("load_texture")(path).cast<TextureHandle>();
                    }
                }
            }

            return phase;
        }, py::arg("data"), py::arg("context") = py::none())
        // from_shader_phase - create MaterialPhase from parsed ShaderPhase
        .def_static("from_shader_phase", [](
            const ShaderPhase& shader_phase,
            py::object color,
            py::object textures,
            py::object extra_uniforms
        ) -> MaterialPhase {
            // 1. Get shader sources from stages
            auto it_vert = shader_phase.stages.find("vertex");
            auto it_frag = shader_phase.stages.find("fragment");
            auto it_geom = shader_phase.stages.find("geometry");

            if (it_vert == shader_phase.stages.end()) {
                throw std::runtime_error("Phase has no vertex stage");
            }
            if (it_frag == shader_phase.stages.end()) {
                throw std::runtime_error("Phase has no fragment stage");
            }

            std::string vs = it_vert->second.source;
            std::string fs = it_frag->second.source;
            std::string gs = (it_geom != shader_phase.stages.end()) ? it_geom->second.source : "";

            auto shader = std::make_shared<ShaderProgram>(vs, fs, gs, "");

            // 2. Build RenderState from gl-flags
            RenderState rs;
            rs.depth_write = shader_phase.gl_depth_mask.value_or(true);
            rs.depth_test = shader_phase.gl_depth_test.value_or(true);
            rs.blend = shader_phase.gl_blend.value_or(false);
            rs.cull = shader_phase.gl_cull.value_or(true);

            MaterialPhase phase(shader, rs, shader_phase.phase_mark, shader_phase.priority);

            // 3. Apply uniforms from defaults
            for (const auto& prop : shader_phase.uniforms) {
                if (std::holds_alternative<std::monostate>(prop.default_value)) continue;

                if (std::holds_alternative<bool>(prop.default_value)) {
                    phase.uniforms[prop.name] = std::get<bool>(prop.default_value);
                } else if (std::holds_alternative<int>(prop.default_value)) {
                    phase.uniforms[prop.name] = std::get<int>(prop.default_value);
                } else if (std::holds_alternative<double>(prop.default_value)) {
                    phase.uniforms[prop.name] = static_cast<float>(std::get<double>(prop.default_value));
                } else if (std::holds_alternative<std::vector<double>>(prop.default_value)) {
                    const auto& vec = std::get<std::vector<double>>(prop.default_value);
                    if (vec.size() == 3) {
                        phase.uniforms[prop.name] = Vec3{vec[0], vec[1], vec[2]};
                    } else if (vec.size() == 4) {
                        phase.uniforms[prop.name] = Vec4{vec[0], vec[1], vec[2], vec[3]};
                    }
                }
            }

            // 4. Apply extra_uniforms
            if (!extra_uniforms.is_none()) {
                py::dict extras = extra_uniforms.cast<py::dict>();
                for (auto item : extras) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        phase.uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        phase.uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        phase.uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::array>(val)) {
                        auto arr = py::array_t<float>::ensure(val);
                        auto buf = arr.request();
                        if (buf.size == 3) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            phase.uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (buf.size == 4) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            phase.uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            }

            // 5. Set textures (use white texture as default for Texture properties)
            py::object white_tex_fn = py::module_::import("termin.visualization.core.texture_handle").attr("get_white_texture_handle");
            TextureHandle white_tex = white_tex_fn().cast<TextureHandle>();

            for (const auto& prop : shader_phase.uniforms) {
                if (prop.property_type == "Texture") {
                    phase.textures[prop.name] = white_tex;
                }
            }

            // Override with provided textures
            if (!textures.is_none()) {
                py::dict tex_dict = textures.cast<py::dict>();
                for (auto item : tex_dict) {
                    std::string key = item.first.cast<std::string>();
                    phase.textures[key] = item.second.cast<TextureHandle>();
                }
            }

            // 6. Set color
            if (!color.is_none()) {
                auto arr = py::array_t<float>::ensure(color);
                auto buf = arr.unchecked<1>();
                phase.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
            }

            return phase;
        }, py::arg("shader_phase"),
           py::arg("color") = py::none(),
           py::arg("textures") = py::none(),
           py::arg("extra_uniforms") = py::none());

    // Material
    py::class_<Material, std::shared_ptr<Material>>(m, "Material")
        .def(py::init<>())
        .def(py::init([](std::shared_ptr<ShaderProgram> shader, const RenderState& rs,
                         const std::string& phase_mark, int priority) {
            return std::make_shared<Material>(shader, rs, phase_mark, priority);
        }), py::arg("shader"), py::arg("render_state") = RenderState::opaque(),
            py::arg("phase_mark") = "opaque", py::arg("priority") = 0)
        // Python-compatible kwargs constructor
        .def(py::init([](py::kwargs kwargs) {
            // Get default shader if not provided
            std::shared_ptr<ShaderProgram> shader;
            if (kwargs.contains("shader")) {
                shader = kwargs["shader"].cast<std::shared_ptr<ShaderProgram>>();
            } else {
                // Import default shader
                py::object shader_mod = py::module_::import("termin.visualization.render.materials.default_material");
                shader = shader_mod.attr("default_shader")().cast<std::shared_ptr<ShaderProgram>>();
            }

            RenderState rs = RenderState::opaque();
            if (kwargs.contains("render_state")) {
                rs = kwargs["render_state"].cast<RenderState>();
            }

            std::string phase_mark = "opaque";
            if (kwargs.contains("phase_mark")) {
                phase_mark = kwargs["phase_mark"].cast<std::string>();
            }

            int priority = 0;
            if (kwargs.contains("priority")) {
                priority = kwargs["priority"].cast<int>();
            }

            auto mat = std::make_shared<Material>(shader, rs, phase_mark, priority);

            if (kwargs.contains("name")) {
                mat->name = kwargs["name"].cast<std::string>();
            }
            if (kwargs.contains("source_path")) {
                mat->source_path = kwargs["source_path"].cast<std::string>();
            }
            if (kwargs.contains("shader_name")) {
                mat->shader_name = kwargs["shader_name"].cast<std::string>();
            }

            // Set color
            if (kwargs.contains("color")) {
                auto arr = py::array_t<float>::ensure(kwargs["color"]);
                auto buf = arr.unchecked<1>();
                mat->set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
            }

            // Set textures
            if (kwargs.contains("textures") && !kwargs["textures"].is_none()) {
                py::dict tex_dict = kwargs["textures"].cast<py::dict>();
                for (auto item : tex_dict) {
                    std::string key = item.first.cast<std::string>();
                    mat->default_phase().textures[key] = item.second.cast<TextureHandle>();
                }
            }

            // Set uniforms
            if (kwargs.contains("uniforms") && !kwargs["uniforms"].is_none()) {
                py::dict uniforms_dict = kwargs["uniforms"].cast<py::dict>();
                for (auto item : uniforms_dict) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        mat->default_phase().uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        mat->default_phase().uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        mat->default_phase().uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::array>(val)) {
                        auto arr = py::array_t<float>::ensure(val);
                        auto buf = arr.request();
                        if (buf.size == 3) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            mat->default_phase().uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (buf.size == 4) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            mat->default_phase().uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            }

            return mat;
        }))
        .def_readwrite("name", &Material::name)
        .def_readwrite("source_path", &Material::source_path)
        .def_readwrite("shader_name", &Material::shader_name)
        .def_readwrite("phases", &Material::phases)
        .def("default_phase", static_cast<MaterialPhase& (Material::*)()>(&Material::default_phase),
             py::return_value_policy::reference)
        .def_property_readonly("_default_phase", [](Material& self) -> MaterialPhase& {
            return self.default_phase();
        }, py::return_value_policy::reference)
        // Convenience properties for default phase (Python compatibility)
        .def_property("shader",
            [](Material& self) { return self.default_phase().shader; },
            [](Material& self, std::shared_ptr<ShaderProgram> shader) {
                self.default_phase().shader = shader;
            })
        .def_property("color",
            [](Material& self) -> py::object {
                if (!self.default_phase().color.has_value()) return py::none();
                Vec4 c = self.default_phase().color.value();
                auto result = py::array_t<float>(4);
                auto buf = result.mutable_unchecked<1>();
                buf(0) = static_cast<float>(c.x);
                buf(1) = static_cast<float>(c.y);
                buf(2) = static_cast<float>(c.z);
                buf(3) = static_cast<float>(c.w);
                return result;
            },
            [](Material& self, py::object val) {
                if (val.is_none()) {
                    self.default_phase().color = std::nullopt;
                } else {
                    auto arr = py::array_t<float>::ensure(val);
                    auto buf = arr.unchecked<1>();
                    self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
                }
            })
        .def_property("textures",
            [](Material& self) -> std::unordered_map<std::string, TextureHandle>& {
                return self.default_phase().textures;
            },
            [](Material& self, const std::unordered_map<std::string, TextureHandle>& textures) {
                self.default_phase().textures = textures;
            }, py::return_value_policy::reference)
        .def_property("uniforms",
            [](Material& self) -> py::dict {
                py::dict result;
                for (const auto& [key, val] : self.default_phase().uniforms) {
                    std::visit([&](auto&& arg) {
                        using T = std::decay_t<decltype(arg)>;
                        if constexpr (std::is_same_v<T, bool>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, int>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, float>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, Vec3>) {
                            auto arr = py::array_t<float>(3);
                            auto buf = arr.mutable_unchecked<1>();
                            buf(0) = arg.x;
                            buf(1) = arg.y;
                            buf(2) = arg.z;
                            result[key.c_str()] = arr;
                        } else if constexpr (std::is_same_v<T, Vec4>) {
                            auto arr = py::array_t<float>(4);
                            auto buf = arr.mutable_unchecked<1>();
                            buf(0) = arg.x;
                            buf(1) = arg.y;
                            buf(2) = arg.z;
                            buf(3) = arg.w;
                            result[key.c_str()] = arr;
                        }
                    }, val);
                }
                return result;
            },
            [](Material& self, py::dict uniforms) {
                // Convert from Python dict to C++ map
                for (auto item : uniforms) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        self.default_phase().uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        self.default_phase().uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        self.default_phase().uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::array>(val)) {
                        auto arr = py::array_t<float>::ensure(val);
                        auto buf = arr.request();
                        if (buf.size == 3) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            self.default_phase().uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (buf.size == 4) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            self.default_phase().uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            })
        .def("get_phases_for_mark", &Material::get_phases_for_mark)
        .def("set_param", [](Material& self, const std::string& name, py::object value) {
            if (py::isinstance<py::bool_>(value)) {
                self.set_param(name, value.cast<bool>());
            } else if (py::isinstance<py::int_>(value)) {
                self.set_param(name, value.cast<int>());
            } else if (py::isinstance<py::float_>(value)) {
                self.set_param(name, value.cast<float>());
            } else if (py::isinstance<py::array>(value)) {
                auto arr = py::array_t<float>::ensure(value);
                auto buf = arr.request();
                if (buf.size == 3) {
                    auto* ptr = static_cast<float*>(buf.ptr);
                    self.set_param(name, Vec3{ptr[0], ptr[1], ptr[2]});
                } else if (buf.size == 4) {
                    auto* ptr = static_cast<float*>(buf.ptr);
                    self.set_param(name, Vec4{ptr[0], ptr[1], ptr[2], ptr[3]});
                }
            }
        })
        .def("set_color", [](Material& self, py::array_t<float> rgba) {
            auto buf = rgba.unchecked<1>();
            self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
        })
        .def("update_color", [](Material& self, py::array_t<float> rgba) {
            auto buf = rgba.unchecked<1>();
            self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
        })
        .def("apply", [](Material& self,
                         py::array_t<float> model,
                         py::array_t<float> view,
                         py::array_t<float> proj,
                         GraphicsBackend* graphics,
                         int64_t context_key) {
            auto m_buf = model.unchecked<2>();
            auto v_buf = view.unchecked<2>();
            auto p_buf = proj.unchecked<2>();

            Mat44f m_mat, v_mat, p_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    m_mat.data[col * 4 + row] = m_buf(row, col);
                    v_mat.data[col * 4 + row] = v_buf(row, col);
                    p_mat.data[col * 4 + row] = p_buf(row, col);
                }
            }
            self.apply(m_mat, v_mat, p_mat, graphics, context_key);
        }, py::arg("model"), py::arg("view"), py::arg("projection"),
           py::arg("graphics"), py::arg("context_key") = 0)
        .def("copy", &Material::copy)
        // from_parsed - create Material from ShaderMultyPhaseProgramm
        .def_static("from_parsed", [](
            const ShaderMultyPhaseProgramm& program,
            py::object color,
            py::object textures,
            py::object uniforms,
            py::object name,
            py::object source_path
        ) -> std::shared_ptr<Material> {
            if (program.phases.empty()) {
                throw std::runtime_error("Program has no phases");
            }

            auto mat = std::make_shared<Material>();
            mat->name = name.is_none() ? program.program : name.cast<std::string>();
            mat->source_path = source_path.is_none() ? "" : source_path.cast<std::string>();
            mat->shader_name = program.program;
            mat->phases.clear();

            // Get MaterialPhase class for from_shader_phase
            py::object MaterialPhase_cls = py::module_::import("termin._native.render").attr("MaterialPhase");

            for (const auto& shader_phase : program.phases) {
                MaterialPhase phase = MaterialPhase_cls.attr("from_shader_phase")(
                    shader_phase, color, textures, uniforms
                ).cast<MaterialPhase>();
                mat->phases.push_back(std::move(phase));
            }

            return mat;
        }, py::arg("program"),
           py::arg("color") = py::none(),
           py::arg("textures") = py::none(),
           py::arg("uniforms") = py::none(),
           py::arg("name") = py::none(),
           py::arg("source_path") = py::none())
        // serialize - serialize Material to dict
        .def("serialize", [](const Material& self) -> py::dict {
            py::dict result;

            // If source_path is set, serialize as file reference
            if (!self.source_path.empty()) {
                result["type"] = "path";
                result["path"] = self.source_path;
                result["name"] = self.name;
                return result;
            }

            // Otherwise serialize inline
            result["type"] = "inline";
            result["name"] = self.name;
            result["shader_name"] = self.shader_name;

            py::list phases_list;
            for (const auto& phase : self.phases) {
                // Serialize phase using its serialize method
                py::dict phase_dict;
                phase_dict["phase_mark"] = phase.phase_mark;
                phase_dict["priority"] = phase.priority;

                // Color
                if (phase.color.has_value()) {
                    Vec4 c = phase.color.value();
                    py::list col_list;
                    col_list.append(c.x);
                    col_list.append(c.y);
                    col_list.append(c.z);
                    col_list.append(c.w);
                    phase_dict["color"] = col_list;
                } else {
                    phase_dict["color"] = py::none();
                }

                // Uniforms
                py::dict uniforms_dict;
                for (const auto& [key, val] : phase.uniforms) {
                    std::visit([&](auto&& arg) {
                        using T = std::decay_t<decltype(arg)>;
                        if constexpr (std::is_same_v<T, bool>) {
                            uniforms_dict[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, int>) {
                            uniforms_dict[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, float>) {
                            uniforms_dict[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, Vec3>) {
                            py::list vec;
                            vec.append(arg.x);
                            vec.append(arg.y);
                            vec.append(arg.z);
                            uniforms_dict[key.c_str()] = vec;
                        } else if constexpr (std::is_same_v<T, Vec4>) {
                            py::list vec;
                            vec.append(arg.x);
                            vec.append(arg.y);
                            vec.append(arg.z);
                            vec.append(arg.w);
                            uniforms_dict[key.c_str()] = vec;
                        }
                    }, val);
                }
                phase_dict["uniforms"] = uniforms_dict;

                // Textures - store source_path
                py::dict textures_dict;
                for (const auto& [key, tex] : phase.textures) {
                    std::string path = tex.source_path();
                    if (!path.empty()) {
                        textures_dict[key.c_str()] = path;
                    }
                }
                phase_dict["textures"] = textures_dict;

                // Render state
                py::dict rs_dict;
                rs_dict["depth_test"] = phase.render_state.depth_test;
                rs_dict["depth_write"] = phase.render_state.depth_write;
                rs_dict["blend"] = phase.render_state.blend;
                rs_dict["cull"] = phase.render_state.cull;
                phase_dict["render_state"] = rs_dict;

                // Shader sources
                py::dict shader_dict;
                if (phase.shader) {
                    shader_dict["vertex"] = phase.shader->vertex_source();
                    shader_dict["fragment"] = phase.shader->fragment_source();
                    shader_dict["geometry"] = phase.shader->geometry_source();
                }
                phase_dict["shader"] = shader_dict;

                phases_list.append(phase_dict);
            }
            result["phases"] = phases_list;

            return result;
        })
        // deserialize - deserialize Material from dict
        .def_static("deserialize", [](py::dict data, py::object context) -> std::shared_ptr<Material> {
            std::string type_str = "inline";
            if (data.contains("type")) {
                type_str = data["type"].cast<std::string>();
            }

            if (type_str == "path") {
                // Load from file
                std::string path = data["path"].cast<std::string>();
                if (!context.is_none() && py::hasattr(context, "load_material")) {
                    return context.attr("load_material")(path).cast<std::shared_ptr<Material>>();
                }
                throw std::runtime_error("Cannot deserialize path-based material without context");
            }

            // Inline deserialization
            auto mat = std::make_shared<Material>();
            if (data.contains("name")) {
                mat->name = data["name"].cast<std::string>();
            }
            if (data.contains("shader_name")) {
                mat->shader_name = data["shader_name"].cast<std::string>();
            }

            mat->phases.clear();
            if (data.contains("phases")) {
                py::list phases_list = data["phases"].cast<py::list>();
                for (auto phase_obj : phases_list) {
                    py::dict phase_data = phase_obj.cast<py::dict>();

                    // Get shader sources
                    py::dict shader_data = phase_data["shader"].cast<py::dict>();
                    std::string vs = shader_data["vertex"].cast<std::string>();
                    std::string fs = shader_data["fragment"].cast<std::string>();
                    std::string gs = shader_data.contains("geometry") ?
                        shader_data["geometry"].cast<std::string>() : "";

                    auto shader = std::make_shared<ShaderProgram>(vs, fs, gs, "");

                    // Get render state
                    RenderState rs;
                    if (phase_data.contains("render_state")) {
                        py::dict rs_data = phase_data["render_state"].cast<py::dict>();
                        rs.depth_test = rs_data.contains("depth_test") ?
                            rs_data["depth_test"].cast<bool>() : true;
                        rs.depth_write = rs_data.contains("depth_write") ?
                            rs_data["depth_write"].cast<bool>() : true;
                        rs.blend = rs_data.contains("blend") ?
                            rs_data["blend"].cast<bool>() : false;
                        rs.cull = rs_data.contains("cull") ?
                            rs_data["cull"].cast<bool>() : true;
                    }

                    std::string phase_mark = phase_data.contains("phase_mark") ?
                        phase_data["phase_mark"].cast<std::string>() : "opaque";
                    int priority = phase_data.contains("priority") ?
                        phase_data["priority"].cast<int>() : 0;

                    MaterialPhase phase(shader, rs, phase_mark, priority);

                    // Color
                    if (phase_data.contains("color") && !phase_data["color"].is_none()) {
                        py::list color_list = phase_data["color"].cast<py::list>();
                        if (py::len(color_list) >= 4) {
                            phase.set_color(Vec4{
                                color_list[0].cast<float>(),
                                color_list[1].cast<float>(),
                                color_list[2].cast<float>(),
                                color_list[3].cast<float>()
                            });
                        }
                    }

                    // Uniforms
                    if (phase_data.contains("uniforms")) {
                        py::dict uniforms_dict = phase_data["uniforms"].cast<py::dict>();
                        for (auto item : uniforms_dict) {
                            std::string key = item.first.cast<std::string>();
                            py::object val = py::reinterpret_borrow<py::object>(item.second);
                            if (py::isinstance<py::list>(val)) {
                                py::list lst = val.cast<py::list>();
                                if (py::len(lst) == 3) {
                                    phase.uniforms[key] = Vec3{
                                        lst[0].cast<float>(),
                                        lst[1].cast<float>(),
                                        lst[2].cast<float>()
                                    };
                                } else if (py::len(lst) == 4) {
                                    phase.uniforms[key] = Vec4{
                                        lst[0].cast<float>(),
                                        lst[1].cast<float>(),
                                        lst[2].cast<float>(),
                                        lst[3].cast<float>()
                                    };
                                }
                            } else if (py::isinstance<py::float_>(val)) {
                                phase.uniforms[key] = val.cast<float>();
                            } else if (py::isinstance<py::int_>(val)) {
                                phase.uniforms[key] = val.cast<int>();
                            } else if (py::isinstance<py::bool_>(val)) {
                                phase.uniforms[key] = val.cast<bool>();
                            }
                        }
                    }

                    // Textures (if context provided)
                    if (phase_data.contains("textures") && !context.is_none()) {
                        py::dict textures_dict = phase_data["textures"].cast<py::dict>();
                        for (auto item : textures_dict) {
                            std::string key = item.first.cast<std::string>();
                            std::string path = item.second.cast<std::string>();
                            if (py::hasattr(context, "load_texture")) {
                                phase.textures[key] = context.attr("load_texture")(path).cast<TextureHandle>();
                            }
                        }
                    }

                    mat->phases.push_back(std::move(phase));
                }
            }

            return mat;
        }, py::arg("data"), py::arg("context") = py::none());

    // get_error_material - singleton for error material
    m.def("get_error_material", []() -> std::shared_ptr<Material> {
        static std::shared_ptr<Material> error_mat;
        if (!error_mat) {
            // Import default shader
            py::object shader_mod = py::module_::import("termin.visualization.render.materials.default_material");
            auto shader = shader_mod.attr("default_shader")().cast<std::shared_ptr<ShaderProgram>>();
            error_mat = std::make_shared<Material>(shader, RenderState::opaque(), "opaque", 0);
            error_mat->name = "__ErrorMaterial__";
            error_mat->shader_name = "DefaultShader";
            error_mat->set_color(Vec4{1.0, 0.0, 1.0, 1.0});  // Magenta
        }
        return error_mat;
    });

    // ========== Drawable System ==========
    // Note: Drawable itself is a C++ abstract interface.
    // Python classes implement the Drawable protocol separately.
    // These structures are used for interop between C++ and Python passes.

    // GeometryDrawCall - links MaterialPhase to geometry ID
    py::class_<GeometryDrawCall>(m, "GeometryDrawCall")
        .def(py::init<>())
        .def(py::init([](MaterialPhase* phase, const std::string& geometry_id) {
            return GeometryDrawCall{phase, geometry_id};
        }), py::arg("phase"), py::arg("geometry_id") = "")
        .def_readwrite("phase", &GeometryDrawCall::phase)
        .def_readwrite("geometry_id", &GeometryDrawCall::geometry_id);

    // PhaseDrawCall - complete draw call for passes
    py::class_<PhaseDrawCall>(m, "PhaseDrawCall")
        .def(py::init<>())
        .def_readwrite("entity", &PhaseDrawCall::entity)
        .def_readwrite("phase", &PhaseDrawCall::phase)
        .def_readwrite("priority", &PhaseDrawCall::priority)
        .def_readwrite("geometry_id", &PhaseDrawCall::geometry_id);
        // Note: drawable is C++ only, Python uses its own Drawable protocol

    // ========== MeshGPU ==========
    py::class_<MeshGPU>(m, "MeshGPU")
        .def(py::init<>())
        .def_readwrite("uploaded_version", &MeshGPU::uploaded_version)
        .def_property_readonly("is_uploaded", &MeshGPU::is_uploaded)
        // Overload 1: explicit parameters
        .def("draw", [](MeshGPU& self, GraphicsBackend* graphics, const Mesh3& mesh, int version, int64_t context_key) {
            self.draw(graphics, mesh, version, context_key);
        }, py::arg("graphics"), py::arg("mesh"), py::arg("version"), py::arg("context_key"))
        // Overload 2: Python RenderContext (extracts graphics and context_key)
        .def("draw", [](MeshGPU& self, py::object context, const Mesh3& mesh, int version) {
            GraphicsBackend* graphics = context.attr("graphics").cast<GraphicsBackend*>();
            int64_t context_key = context.attr("context_key").cast<int64_t>();
            self.draw(graphics, mesh, version, context_key);
        }, py::arg("context"), py::arg("mesh"), py::arg("version"))
        .def("invalidate", &MeshGPU::invalidate)
        .def("delete", &MeshGPU::delete_resources);

    // ========== TextureGPU ==========
    py::class_<TextureGPU>(m, "TextureGPU")
        .def(py::init<>())
        .def_readwrite("uploaded_version", &TextureGPU::uploaded_version)
        .def_property_readonly("is_uploaded", &TextureGPU::is_uploaded)
        .def("bind", &TextureGPU::bind,
            py::arg("graphics"), py::arg("texture_data"), py::arg("version"),
            py::arg("unit") = 0, py::arg("context_key") = 0)
        .def("invalidate", &TextureGPU::invalidate)
        .def("delete", &TextureGPU::delete_resources);

    // ========== MeshRenderer ==========
    py::class_<MeshRenderer, Component>(m, "MeshRenderer")
        .def(py::init<>())
        // Constructor with mesh and material (for Python compatibility)
        .def(py::init([](py::object mesh_arg, py::object material_arg, bool cast_shadow) {
            auto renderer = new MeshRenderer();
            renderer->cast_shadow = cast_shadow;

            // Handle mesh argument
            if (!mesh_arg.is_none()) {
                // Check if it's a MeshHandle
                if (py::isinstance<MeshHandle>(mesh_arg)) {
                    renderer->mesh = mesh_arg.cast<MeshHandle>();
                }
                // Check if it's a MeshDrawable (has _handle attribute)
                else if (py::hasattr(mesh_arg, "_handle")) {
                    py::object handle = mesh_arg.attr("_handle");
                    if (py::isinstance<MeshHandle>(handle)) {
                        renderer->mesh = handle.cast<MeshHandle>();
                    }
                }
            }

            // Handle material argument - store as py::object asset
            if (!material_arg.is_none()) {
                renderer->material = MaterialHandle::from_asset(material_arg);
            }

            return renderer;
        }), py::arg("mesh") = py::none(), py::arg("material") = py::none(), py::arg("cast_shadow") = true)
        .def_readwrite("mesh", &MeshRenderer::mesh)
        .def_readwrite("material", &MeshRenderer::material)
        .def_readwrite("cast_shadow", &MeshRenderer::cast_shadow)
        .def_readwrite("_override_material", &MeshRenderer::_override_material)
        .def("mesh_handle", [](MeshRenderer& self) -> MeshHandle& {
            return self.mesh_handle();
        }, py::return_value_policy::reference_internal)
        .def("material_handle", [](MeshRenderer& self) -> MaterialHandle& {
            return self.material_handle();
        }, py::return_value_policy::reference_internal)
        .def("set_mesh", &MeshRenderer::set_mesh)
        .def("set_mesh_by_name", &MeshRenderer::set_mesh_by_name)
        .def("get_material", &MeshRenderer::get_material, py::return_value_policy::reference)
        .def("get_base_material", &MeshRenderer::get_base_material, py::return_value_policy::reference)
        .def("set_material", &MeshRenderer::set_material)
        .def("set_material_handle", &MeshRenderer::set_material_handle)
        .def("set_material_by_name", &MeshRenderer::set_material_by_name)
        .def_property("override_material",
            &MeshRenderer::override_material,
            &MeshRenderer::set_override_material)
        .def("set_override_material", &MeshRenderer::set_override_material)
        .def("overridden_material", &MeshRenderer::overridden_material, py::return_value_policy::reference)
        
        // phase marks is a readonly property of py::set type
        //.def("phase_marks", &MeshRenderer::phase_marks)
        .def_property_readonly("phase_marks", [](MeshRenderer& self) {
            py::set marks;
            for (const auto& mark : self.phase_marks()) {
                marks.add(mark);
            }
            return marks;
        })
        
        .def("draw_geometry", &MeshRenderer::draw_geometry,
            py::arg("context"), py::arg("geometry_id") = "")
        .def("get_phases_for_mark", &MeshRenderer::get_phases_for_mark,
            py::arg("phase_mark"))
        .def("get_geometry_draws", &MeshRenderer::get_geometry_draws,
            py::arg("phase_mark") = "")
        // .def("serialize_data", &MeshRenderer::serialize_data_py)
        // .def("deserialize_data", &MeshRenderer::deserialize_data_py)
        ;

    // ========== SkinnedMeshRenderer ==========
    py::class_<SkinnedMeshRenderer>(m, "SkinnedMeshRenderer")
        .def(py::init<>())
        .def("set_skeleton_instance", &SkinnedMeshRenderer::set_skeleton_instance)
        .def("update_bone_matrices", &SkinnedMeshRenderer::update_bone_matrices)
        .def("upload_bone_matrices", &SkinnedMeshRenderer::upload_bone_matrices)
        .def_readonly("bone_count", &SkinnedMeshRenderer::bone_count)
        .def("get_bone_matrices_flat", [](SkinnedMeshRenderer& self) {
            return py::array_t<float>(
                {self.bone_count, 4, 4},
                {16 * sizeof(float), 4 * sizeof(float), sizeof(float)},
                self.bone_matrices_flat.data()
            );
        });
}

} // namespace termin
