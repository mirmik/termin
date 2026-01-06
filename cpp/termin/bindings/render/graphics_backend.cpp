#include "common.hpp"
#include <nanobind/stl/unique_ptr.h>
#include "termin/render/render.hpp"
#include "termin/render/types.hpp"
#include "termin/render/opengl/opengl_mesh.hpp"
#include "termin/render/shader_parser.hpp"
#include "termin/render/glsl_preprocessor.hpp"

namespace termin {

void bind_graphics_backend(nb::module_& m) {
    // --- Handles (abstract, exposed for type hints) ---

    nb::class_<ShaderHandle>(m, "ShaderHandle")
        .def("use", &ShaderHandle::use)
        .def("stop", &ShaderHandle::stop)
        .def("release", &ShaderHandle::release)
        .def("set_uniform_int", &ShaderHandle::set_uniform_int)
        .def("set_uniform_float", &ShaderHandle::set_uniform_float)
        .def("set_uniform_vec2", &ShaderHandle::set_uniform_vec2)
        .def("set_uniform_vec2", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<2>> v) {
            self.set_uniform_vec2(name, v(0), v(1));
        })
        .def("set_uniform_vec2", [](ShaderHandle& self, const char* name, nb::tuple t) {
            self.set_uniform_vec2(name, nb::cast<float>(t[0]), nb::cast<float>(t[1]));
        })
        .def("set_uniform_vec3", &ShaderHandle::set_uniform_vec3)
        .def("set_uniform_vec3", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<3>> v) {
            self.set_uniform_vec3(name, v(0), v(1), v(2));
        })
        .def("set_uniform_vec3", [](ShaderHandle& self, const char* name, nb::tuple t) {
            self.set_uniform_vec3(name, nb::cast<float>(t[0]), nb::cast<float>(t[1]), nb::cast<float>(t[2]));
        })
        .def("set_uniform_vec4", &ShaderHandle::set_uniform_vec4)
        .def("set_uniform_vec4", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<4>> v) {
            self.set_uniform_vec4(name, v(0), v(1), v(2), v(3));
        })
        .def("set_uniform_vec4", [](ShaderHandle& self, const char* name, nb::tuple t) {
            self.set_uniform_vec4(name, nb::cast<float>(t[0]), nb::cast<float>(t[1]), nb::cast<float>(t[2]), nb::cast<float>(t[3]));
        })
        .def("set_uniform_matrix4", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> matrix, bool transpose) {
            self.set_uniform_matrix4(name, matrix.data(), transpose);
        }, nb::arg("name"), nb::arg("matrix"), nb::arg("transpose") = true)
        .def("set_uniform_matrix4_array", [](ShaderHandle& self, const char* name, nb::ndarray<nb::numpy, float> matrices, int count, bool transpose) {
            self.set_uniform_matrix4_array(name, matrices.data(), count, transpose);
        }, nb::arg("name"), nb::arg("matrices"), nb::arg("count"), nb::arg("transpose") = true);

    nb::class_<GPUMeshHandle>(m, "GPUMeshHandle")
        .def("draw", &GPUMeshHandle::draw)
        .def("release", &GPUMeshHandle::release)
        .def("delete", &GPUMeshHandle::release);  // Alias for Python interface

    nb::class_<GPUTextureHandle>(m, "GPUTextureHandle")
        .def("bind", &GPUTextureHandle::bind, nb::arg("unit") = 0)
        .def("release", &GPUTextureHandle::release)
        .def("delete", &GPUTextureHandle::release)  // Alias for Python interface
        .def("get_id", &GPUTextureHandle::get_id)
        .def("get_width", &GPUTextureHandle::get_width)
        .def("get_height", &GPUTextureHandle::get_height);

    nb::class_<FramebufferHandle>(m, "FramebufferHandle")
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
        .def("color_texture", &FramebufferHandle::color_texture, nb::rv_policy::reference)
        .def("depth_texture", &FramebufferHandle::depth_texture, nb::rv_policy::reference)
        .def("set_external_target", static_cast<void (FramebufferHandle::*)(uint32_t, int, int)>(&FramebufferHandle::set_external_target))
        .def("set_external_target", static_cast<void (FramebufferHandle::*)(uint32_t, Size2i)>(&FramebufferHandle::set_external_target));

    // --- GraphicsBackend ---

    nb::class_<GraphicsBackend>(m, "GraphicsBackend")
        .def("ensure_ready", &GraphicsBackend::ensure_ready)
        .def("set_viewport", &GraphicsBackend::set_viewport)
        .def("enable_scissor", &GraphicsBackend::enable_scissor)
        .def("disable_scissor", &GraphicsBackend::disable_scissor)
        // clear_color_depth with 4 floats, Color4, and tuple
        .def("clear_color_depth", static_cast<void (GraphicsBackend::*)(float, float, float, float)>(&GraphicsBackend::clear_color_depth))
        .def("clear_color_depth", static_cast<void (GraphicsBackend::*)(const Color4&)>(&GraphicsBackend::clear_color_depth))
        .def("clear_color_depth", [](GraphicsBackend& self, nb::tuple color) {
            float a = nb::len(color) >= 4 ? nb::cast<float>(color[3]) : 1.0f;
            self.clear_color_depth(nb::cast<float>(color[0]), nb::cast<float>(color[1]), nb::cast<float>(color[2]), a);
        })
        .def("clear_color", static_cast<void (GraphicsBackend::*)(float, float, float, float)>(&GraphicsBackend::clear_color))
        .def("clear_color", static_cast<void (GraphicsBackend::*)(const Color4&)>(&GraphicsBackend::clear_color))
        .def("clear_color", [](GraphicsBackend& self, nb::tuple color) {
            float a = nb::len(color) >= 4 ? nb::cast<float>(color[3]) : 1.0f;
            self.clear_color(nb::cast<float>(color[0]), nb::cast<float>(color[1]), nb::cast<float>(color[2]), a);
        })
        .def("clear_depth", &GraphicsBackend::clear_depth, nb::arg("value") = 1.0f)
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
        .def("bind_framebuffer", &GraphicsBackend::bind_framebuffer, nb::arg("fbo").none())
        // bind_framebuffer for Python FBO objects
        .def("bind_framebuffer", [](GraphicsBackend& self, nb::object fbo) {
            if (fbo.is_none()) {
                glBindFramebuffer(GL_FRAMEBUFFER, 0);
                return;
            }
            // Try C++ FramebufferHandle first
            try {
                auto* handle = nb::cast<FramebufferHandle*>(fbo);
                self.bind_framebuffer(handle);
            } catch (nb::cast_error&) {
                // Must be Python OpenGLFramebufferHandle - get _fbo attribute
                GLuint fbo_id = nb::cast<GLuint>(fbo.attr("_fbo"));
                glBindFramebuffer(GL_FRAMEBUFFER, fbo_id);
            }
        })
        .def("read_pixel", &GraphicsBackend::read_pixel)
        .def("read_depth_pixel", &GraphicsBackend::read_depth_pixel)
        // read_depth_buffer - returns numpy array or None
        .def("read_depth_buffer", [](GraphicsBackend& self, FramebufferHandle* fbo) -> nb::object {
            if (fbo == nullptr) return nb::none();
            if (fbo->is_msaa()) return nb::none();  // Cannot read from MSAA

            int width = fbo->get_width();
            int height = fbo->get_height();
            if (width <= 0 || height <= 0) return nb::none();

            // Allocate buffer and read
            float* data = new float[width * height];
            bool success = self.read_depth_buffer(fbo, data);
            if (!success) {
                delete[] data;
                return nb::none();
            }

            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            return nb::ndarray<nb::numpy, float>(data, {static_cast<size_t>(height), static_cast<size_t>(width)}, owner);
        });

    // --- OpenGLGraphicsBackend ---

    nb::class_<OpenGLGraphicsBackend, GraphicsBackend>(m, "OpenGLGraphicsBackend")
        .def(nb::init<>())
        .def("create_shader", [](OpenGLGraphicsBackend& self, const std::string& vert, const std::string& frag, nb::object geom) {
            const char* geom_ptr = nullptr;
            std::string geom_str;
            if (!geom.is_none()) {
                geom_str = nb::cast<std::string>(geom);
                if (!geom_str.empty()) {
                    geom_ptr = geom_str.c_str();
                }
            }
            return self.create_shader(vert.c_str(), frag.c_str(), geom_ptr);
        }, nb::arg("vertex_source"), nb::arg("fragment_source"), nb::arg("geometry_source") = nb::none())
        // create_texture with (width, height) and with tuple size
        .def("create_texture", [](OpenGLGraphicsBackend& self, nb::ndarray<nb::numpy, uint8_t> data, int width, int height, int channels, bool mipmap, bool clamp) {
            return self.create_texture(data.data(), width, height, channels, mipmap, clamp);
        }, nb::arg("data"), nb::arg("width"), nb::arg("height"), nb::arg("channels") = 4, nb::arg("mipmap") = true, nb::arg("clamp") = false)
        .def("create_texture", [](OpenGLGraphicsBackend& self, nb::ndarray<nb::numpy, uint8_t> data, nb::tuple size, int channels, bool mipmap, bool clamp) {
            int width = nb::cast<int>(size[0]);
            int height = nb::cast<int>(size[1]);
            return self.create_texture(data.data(), width, height, channels, mipmap, clamp);
        }, nb::arg("data"), nb::arg("size"), nb::arg("channels") = 4, nb::arg("mipmap") = true, nb::arg("clamp") = false)
        // create_framebuffer with (width, height) and with tuple size
        .def("create_framebuffer", [](OpenGLGraphicsBackend& self, int width, int height, int samples, const std::string& format) {
            return self.create_framebuffer(width, height, samples, format);
        }, nb::arg("width"), nb::arg("height"), nb::arg("samples") = 1, nb::arg("format") = "")
        .def("create_framebuffer", [](OpenGLGraphicsBackend& self, nb::tuple size, int samples, const std::string& format) {
            return self.create_framebuffer(nb::cast<int>(size[0]), nb::cast<int>(size[1]), samples, format);
        }, nb::arg("size"), nb::arg("samples") = 1, nb::arg("format") = "")
        // create_shadow_framebuffer
        .def("create_shadow_framebuffer", static_cast<FramebufferHandlePtr (OpenGLGraphicsBackend::*)(int, int)>(&OpenGLGraphicsBackend::create_shadow_framebuffer))
        .def("create_shadow_framebuffer", [](OpenGLGraphicsBackend& self, nb::tuple size) {
            return self.create_shadow_framebuffer(nb::cast<int>(size[0]), nb::cast<int>(size[1]));
        })
        // create_external_framebuffer - wraps external FBO without allocating resources
        .def("create_external_framebuffer", &OpenGLGraphicsBackend::create_external_framebuffer,
            nb::arg("fbo_id"), nb::arg("width"), nb::arg("height"),
            "Create handle wrapping an external FBO (e.g., window default FBO)")
        .def("create_external_framebuffer", [](OpenGLGraphicsBackend& self, uint32_t fbo_id, nb::tuple size) {
            return self.create_external_framebuffer(fbo_id, nb::cast<int>(size[0]), nb::cast<int>(size[1]));
        }, nb::arg("fbo_id"), nb::arg("size"))
        // blit_framebuffer with tuple rects and optional blit_color/blit_depth
        .def("blit_framebuffer", [](OpenGLGraphicsBackend& self, FramebufferHandle* src, FramebufferHandle* dst,
                                    nb::tuple src_rect, nb::tuple dst_rect,
                                    bool blit_color, bool blit_depth) {
            self.blit_framebuffer(src, dst,
                nb::cast<int>(src_rect[0]), nb::cast<int>(src_rect[1]), nb::cast<int>(src_rect[2]), nb::cast<int>(src_rect[3]),
                nb::cast<int>(dst_rect[0]), nb::cast<int>(dst_rect[1]), nb::cast<int>(dst_rect[2]), nb::cast<int>(dst_rect[3]),
                blit_color, blit_depth);
        }, nb::arg("src"), nb::arg("dst"), nb::arg("src_rect"), nb::arg("dst_rect"),
           nb::arg("blit_color") = true, nb::arg("blit_depth") = false)
        // blit_framebuffer with Python FBO objects (for window FBOs)
        .def("blit_framebuffer", [](OpenGLGraphicsBackend& self, nb::object src, nb::object dst,
                                    nb::tuple src_rect, nb::tuple dst_rect,
                                    bool blit_color, bool blit_depth) {
            // Extract FBO IDs from either C++ FramebufferHandle or Python OpenGLFramebufferHandle
            GLuint src_fbo = 0;
            GLuint dst_fbo = 0;

            // Try to get C++ FramebufferHandle first
            try {
                auto* src_handle = nb::cast<FramebufferHandle*>(src);
                src_fbo = src_handle->get_fbo_id();
            } catch (nb::cast_error&) {
                // Must be Python OpenGLFramebufferHandle - get _fbo attribute
                src_fbo = nb::cast<GLuint>(src.attr("_fbo"));
            }

            try {
                auto* dst_handle = nb::cast<FramebufferHandle*>(dst);
                dst_fbo = dst_handle->get_fbo_id();
            } catch (nb::cast_error&) {
                dst_fbo = nb::cast<GLuint>(dst.attr("_fbo"));
            }

            // Perform the blit using raw FBO IDs
            int sx0 = nb::cast<int>(src_rect[0]), sy0 = nb::cast<int>(src_rect[1]);
            int sx1 = nb::cast<int>(src_rect[2]), sy1 = nb::cast<int>(src_rect[3]);
            int dx0 = nb::cast<int>(dst_rect[0]), dy0 = nb::cast<int>(dst_rect[1]);
            int dx1 = nb::cast<int>(dst_rect[2]), dy1 = nb::cast<int>(dst_rect[3]);

            GLbitfield mask = 0;
            if (blit_color) mask |= GL_COLOR_BUFFER_BIT;
            if (blit_depth) mask |= GL_DEPTH_BUFFER_BIT;

            glBindFramebuffer(GL_READ_FRAMEBUFFER, src_fbo);
            glBindFramebuffer(GL_DRAW_FRAMEBUFFER, dst_fbo);
            if (mask != 0) {
                glBlitFramebuffer(sx0, sy0, sx1, sy1, dx0, dy0, dx1, dy1, mask, GL_NEAREST);
            }
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
        }, nb::arg("src"), nb::arg("dst"), nb::arg("src_rect"), nb::arg("dst_rect"),
           nb::arg("blit_color") = true, nb::arg("blit_depth") = false)
        .def("draw_ui_vertices", [](OpenGLGraphicsBackend& self, int64_t context_key, nb::ndarray<nb::numpy, float> vertices) {
            int count = static_cast<int>(vertices.size() / 2);
            self.draw_ui_vertices(context_key, vertices.data(), count);
        })
        .def("draw_ui_textured_quad", static_cast<void (OpenGLGraphicsBackend::*)(int64_t)>(&OpenGLGraphicsBackend::draw_ui_textured_quad))
        .def("draw_ui_textured_quad", [](OpenGLGraphicsBackend& self, int64_t context_key, nb::ndarray<nb::numpy, float> vertices) {
            int count = static_cast<int>(vertices.size() / 4);  // 4 floats per vertex (x, y, u, v)
            self.draw_ui_textured_quad(context_key, vertices.data(), count);
        })
        // Generic create_mesh for all Python mesh objects (Mesh3, SkinnedMesh3, Mesh2, etc.)
        // Uses interleaved_buffer() and get_vertex_layout() to support any vertex format
        .def("create_mesh", [](OpenGLGraphicsBackend& self, nb::object mesh, DrawMode mode) -> std::unique_ptr<GPUMeshHandle> {
            // Get interleaved buffer
            nb::ndarray<nb::numpy, float> buffer = nb::cast<nb::ndarray<nb::numpy, float>>(mesh.attr("interleaved_buffer")());

            // Get indices and flatten to uint32
            nb::object indices_obj = mesh.attr("indices");
            nb::ndarray<nb::numpy, uint32_t> indices = nb::cast<nb::ndarray<nb::numpy, uint32_t>>(
                indices_obj.attr("flatten")().attr("astype")("uint32"));

            // Get vertex layout
            nb::object layout = mesh.attr("get_vertex_layout")();
            int stride = nb::cast<int>(layout.attr("stride"));

            // Parse attributes
            nb::list attrs = nb::cast<nb::list>(layout.attr("attributes"));
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

            for (size_t i = 0; i < nb::len(attrs); ++i) {
                nb::object attr = attrs[i];
                std::string name = nb::cast<std::string>(attr.attr("name"));
                int offset = nb::cast<int>(attr.attr("offset"));
                int size = nb::cast<int>(attr.attr("size"));
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
            if (mode == DrawMode::Triangles && nb::cast<int>(indices_obj.attr("ndim")) == 2) {
                nb::tuple shape = nb::cast<nb::tuple>(indices_obj.attr("shape"));
                int cols = nb::cast<int>(shape[1]);
                if (cols == 2) {
                    actual_mode = DrawMode::Lines;
                }
            }

            return std::make_unique<OpenGLRawMeshHandle>(
                buffer.data(), buffer.size() * sizeof(float),
                indices.data(), indices.size(),
                stride,
                position_offset, position_size,
                has_normal, normal_offset,
                has_uv, uv_offset,
                has_joints, joints_offset,
                has_weights, weights_offset,
                actual_mode
            );
        }, nb::arg("mesh"), nb::arg("mode") = DrawMode::Triangles);

    // init_opengl function
    m.def("init_opengl", &init_opengl, "Initialize OpenGL via glad. Call after context creation.");
}

} // namespace termin
