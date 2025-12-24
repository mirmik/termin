#include "common.hpp"
#include "termin/render/render.hpp"
#include "termin/render/types.hpp"
#include "termin/render/opengl/opengl_mesh.hpp"
#include "termin/render/shader_parser.hpp"
#include "termin/render/glsl_preprocessor.hpp"

namespace termin {

void bind_graphics_backend(py::module_& m) {
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

    // init_opengl function
    m.def("init_opengl", &init_opengl, "Initialize OpenGL via glad. Call after context creation.");
}

} // namespace termin
