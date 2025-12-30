#include "common.hpp"
#include <nanobind/stl/set.h>
#include "termin/render/frame_pass.hpp"
#include "termin/render/frame_graph.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/render.hpp"
#include "termin/render/shader_program.hpp"
#include "termin/render/color_pass.hpp"
#include "termin/entity/entity.hpp"
#include "termin/lighting/light.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/lighting/shadow_settings.hpp"

namespace termin {

void bind_frame_pass(nb::module_& m) {
    // FramePass base class
    nb::class_<FramePass>(m, "FramePass")
        .def(nb::init<>())
        .def("__init__", [](FramePass* self, std::string pass_name,
                            std::set<std::string> reads, std::set<std::string> writes) {
            new (self) FramePass(pass_name, reads, writes);
        },
             nb::arg("pass_name"),
             nb::arg("reads") = std::set<std::string>{},
             nb::arg("writes") = std::set<std::string>{})
        .def_rw("pass_name", &FramePass::pass_name)
        .def_rw("reads", &FramePass::reads)
        .def_rw("writes", &FramePass::writes)
        .def_rw("enabled", &FramePass::enabled)
        .def("get_inplace_aliases", &FramePass::get_inplace_aliases)
        .def("is_inplace", &FramePass::is_inplace)
        .def_prop_ro("inplace", &FramePass::is_inplace)
        .def("get_internal_symbols", &FramePass::get_internal_symbols)
        .def("set_debug_internal_point", &FramePass::set_debug_internal_point)
        .def("clear_debug_internal_point", &FramePass::clear_debug_internal_point)
        .def("get_debug_internal_point", &FramePass::get_debug_internal_point)
        .def("required_resources", &FramePass::required_resources)
        .def("__repr__", [](const FramePass& p) {
            return "<FramePass '" + p.pass_name + "'>";
        });

    // FrameGraph errors
    nb::exception<FrameGraphError>(m, "FrameGraphError");
    nb::exception<FrameGraphMultiWriterError>(m, "FrameGraphMultiWriterError");
    nb::exception<FrameGraphCycleError>(m, "FrameGraphCycleError");

    // FrameGraph
    nb::class_<FrameGraph>(m, "FrameGraph")
        .def("__init__", [](FrameGraph* self, nb::list passes) {
            std::vector<FramePass*> pass_ptrs;
            for (auto item : passes) {
                pass_ptrs.push_back(nb::cast<FramePass*>(item));
            }
            new (self) FrameGraph(pass_ptrs);
        }, nb::arg("passes"))
        .def("build_schedule", [](FrameGraph& self) {
            auto schedule = self.build_schedule();
            nb::list result;
            for (auto* p : schedule) {
                result.append(nb::cast(p, nb::rv_policy::reference));
            }
            return result;
        })
        .def("canonical_resource", &FrameGraph::canonical_resource)
        .def("fbo_alias_groups", &FrameGraph::fbo_alias_groups);

    // RenderContext
    nb::class_<RenderContext>(m, "RenderContext")
        .def(nb::init<>())
        // Constructor with keyword arguments for Python compatibility
        .def("__init__", [](RenderContext* self, nb::kwargs kwargs) {
            new (self) RenderContext();

            if (kwargs.contains("context_key")) {
                self->context_key = nb::cast<int64_t>(kwargs["context_key"]);
            }
            if (kwargs.contains("phase")) {
                self->phase = nb::cast<std::string>(kwargs["phase"]);
            }
            if (kwargs.contains("scene")) {
                self->scene = nb::borrow<nb::object>(kwargs["scene"]);
            }
            if (kwargs.contains("shadow_data")) {
                self->shadow_data = nb::borrow<nb::object>(kwargs["shadow_data"]);
            }
            if (kwargs.contains("extra_uniforms")) {
                self->extra_uniforms = nb::borrow<nb::object>(kwargs["extra_uniforms"]);
            }
            if (kwargs.contains("camera")) {
                self->camera = nb::borrow<nb::object>(kwargs["camera"]);
            }
            if (kwargs.contains("graphics")) {
                nb::object g_obj = nb::borrow<nb::object>(kwargs["graphics"]);
                if (!g_obj.is_none()) {
                    self->graphics = nb::cast<GraphicsBackend*>(g_obj);
                }
            }
            if (kwargs.contains("current_shader")) {
                nb::object s_obj = nb::borrow<nb::object>(kwargs["current_shader"]);
                if (!s_obj.is_none()) {
                    self->current_shader = nb::cast<ShaderProgram*>(s_obj);
                }
            }
            if (kwargs.contains("view")) {
                nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(kwargs["view"]);
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        self->view.data[col * 4 + row] = arr(row, col);
                    }
                }
            }
            if (kwargs.contains("projection")) {
                nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(kwargs["projection"]);
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        self->projection.data[col * 4 + row] = arr(row, col);
                    }
                }
            }
            if (kwargs.contains("model")) {
                nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(kwargs["model"]);
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        self->model.data[col * 4 + row] = arr(row, col);
                    }
                }
            }
        })
        .def_rw("context_key", &RenderContext::context_key)
        .def_rw("phase", &RenderContext::phase)
        .def_rw("scene", &RenderContext::scene)
        .def_rw("shadow_data", &RenderContext::shadow_data)
        .def_rw("extra_uniforms", &RenderContext::extra_uniforms)
        .def_rw("camera", &RenderContext::camera)
        // graphics
        .def_prop_rw("graphics",
            [](const RenderContext& self) -> GraphicsBackend* { return self.graphics; },
            [](RenderContext& self, GraphicsBackend* g) { self.graphics = g; },
            nb::rv_policy::reference)
        // current_shader
        .def_prop_rw("current_shader",
            [](const RenderContext& self) -> ShaderProgram* { return self.current_shader; },
            [](RenderContext& self, ShaderProgram* s) { self.current_shader = s; },
            nb::rv_policy::reference)
        // view matrix
        .def_prop_rw("view",
            [](const RenderContext& self) {
                float* data = new float[16];
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        data[row * 4 + col] = self.view.data[col * 4 + row];
                    }
                }
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
                return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, {4, 4}, owner);
            },
            [](RenderContext& self, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr) {
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        self.view.data[col * 4 + row] = arr(row, col);
                    }
                }
            }
        )
        // projection matrix
        .def_prop_rw("projection",
            [](const RenderContext& self) {
                float* data = new float[16];
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        data[row * 4 + col] = self.projection.data[col * 4 + row];
                    }
                }
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
                return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, {4, 4}, owner);
            },
            [](RenderContext& self, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr) {
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        self.projection.data[col * 4 + row] = arr(row, col);
                    }
                }
            }
        )
        // model matrix
        .def_prop_rw("model",
            [](const RenderContext& self) {
                float* data = new float[16];
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        data[row * 4 + col] = self.model.data[col * 4 + row];
                    }
                }
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
                return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, {4, 4}, owner);
            },
            [](RenderContext& self, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr) {
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        self.model.data[col * 4 + row] = arr(row, col);
                    }
                }
            }
        )
        .def("set_model", [](RenderContext& self, nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr) {
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    self.model.data[col * 4 + row] = arr(row, col);
                }
            }
        })
        .def("mvp", [](const RenderContext& self) {
            Mat44f mvp = self.mvp();
            float* data = new float[16];
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    data[row * 4 + col] = mvp.data[col * 4 + row];
                }
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            return nb::ndarray<nb::numpy, float, nb::shape<4, 4>>(data, {4, 4}, owner);
        });

    // ColorPass - main color rendering pass
    nb::class_<ColorPass, FramePass>(m, "ColorPass")
        .def("__init__", [](ColorPass* self, const std::string& input_res, const std::string& output_res,
                            const std::string& shadow_res, const std::string& phase_mark,
                            const std::string& pass_name, bool sort_by_distance, bool clear_depth) {
            new (self) ColorPass(input_res, output_res, shadow_res, phase_mark, pass_name, sort_by_distance, clear_depth);
        },
             nb::arg("input_res") = "empty",
             nb::arg("output_res") = "color",
             nb::arg("shadow_res") = "shadow_maps",
             nb::arg("phase_mark") = "opaque",
             nb::arg("pass_name") = "Color",
             nb::arg("sort_by_distance") = false,
             nb::arg("clear_depth") = false)
        .def_rw("input_res", &ColorPass::input_res)
        .def_rw("output_res", &ColorPass::output_res)
        .def_rw("shadow_res", &ColorPass::shadow_res)
        .def_rw("phase_mark", &ColorPass::phase_mark)
        .def_rw("sort_by_distance", &ColorPass::sort_by_distance)
        .def_rw("clear_depth", &ColorPass::clear_depth)
        .def_rw("wireframe", &ColorPass::wireframe)
        .def("get_resource_specs", &ColorPass::get_resource_specs)
        .def("get_internal_symbols", &ColorPass::get_internal_symbols)
        .def("set_debugger_window", &ColorPass::set_debugger_window,
             nb::arg("window"),
             nb::arg("depth_callback") = nb::none())
        .def("get_debugger_window", &ColorPass::get_debugger_window)
        .def_rw("debugger_window", &ColorPass::debugger_window)
        .def_rw("depth_capture_callback", &ColorPass::depth_capture_callback)
        .def_prop_rw("_debugger_window",
            [](const ColorPass& self) { return self.debugger_window; },
            [](ColorPass& self, nb::object val) { self.debugger_window = val; })
        .def_prop_rw("_depth_capture_callback",
            [](const ColorPass& self) { return self.depth_capture_callback; },
            [](ColorPass& self, nb::object val) { self.depth_capture_callback = val; })
        .def("execute_with_data", [](
            ColorPass& self,
            GraphicsBackend* graphics,
            nb::dict reads_fbos_py,
            nb::dict writes_fbos_py,
            nb::tuple rect_py,
            nb::list entities_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> projection_py,
            nb::ndarray<nb::numpy, double, nb::shape<3>> camera_position_py,
            int64_t context_key,
            nb::list lights_py,
            nb::ndarray<nb::numpy, double, nb::shape<3>> ambient_color_py,
            float ambient_intensity,
            nb::object shadow_array_py,
            nb::object shadow_settings_py
        ) {
            // Convert FBO maps (skip non-FBO resources like ShadowMapArrayResource)
            FBOMap reads_fbos, writes_fbos;
            for (auto item : reads_fbos_py) {
                std::string key = nb::cast<std::string>(nb::str(item.first));
                nb::object val = nb::borrow<nb::object>(item.second);
                if (!val.is_none()) {
                    try {
                        reads_fbos[key] = nb::cast<FramebufferHandle*>(val);
                    } catch (const nb::cast_error&) {
                        // Skip non-FBO resources (e.g., ShadowMapArrayResource)
                    }
                }
            }
            for (auto item : writes_fbos_py) {
                std::string key = nb::cast<std::string>(nb::str(item.first));
                nb::object val = nb::borrow<nb::object>(item.second);
                if (!val.is_none()) {
                    try {
                        writes_fbos[key] = nb::cast<FramebufferHandle*>(val);
                    } catch (const nb::cast_error&) {
                        // Skip non-FBO resources
                    }
                }
            }

            // Convert rect
            Rect4i rect;
            rect.x = nb::cast<int>(rect_py[0]);
            rect.y = nb::cast<int>(rect_py[1]);
            rect.width = nb::cast<int>(rect_py[2]);
            rect.height = nb::cast<int>(rect_py[3]);

            // Convert entities
            std::vector<Entity> entities;
            for (auto item : entities_py) {
                entities.push_back(nb::cast<Entity>(item));
            }

            // Convert view matrix (row-major numpy -> column-major Mat44f)
            Mat44f view;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    view(col, row) = view_py(row, col);
                }
            }

            // Convert projection matrix
            Mat44f projection;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    projection(col, row) = projection_py(row, col);
                }
            }

            // Convert camera position
            Vec3 camera_position{camera_position_py(0), camera_position_py(1), camera_position_py(2)};

            // Convert lights
            std::vector<Light> lights;
            for (auto item : lights_py) {
                lights.push_back(nb::cast<Light>(item));
            }

            // Convert ambient color
            Vec3 ambient_color{ambient_color_py(0), ambient_color_py(1), ambient_color_py(2)};

            // Convert shadow maps
            std::vector<ShadowMapEntry> shadow_maps;
            if (!shadow_array_py.is_none()) {
                size_t count = nb::len(shadow_array_py);
                for (size_t i = 0; i < count; ++i) {
                    nb::object entry = shadow_array_py[nb::int_(i)];

                    // Get light_space_matrix as numpy array (compute_light_space_matrix returns float64)
                    nb::ndarray<nb::numpy, double, nb::shape<4, 4>> matrix_py = nb::cast<nb::ndarray<nb::numpy, double, nb::shape<4, 4>>>(entry.attr("light_space_matrix"));
                    Mat44f matrix;
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            matrix(col, row) = static_cast<float>(matrix_py(row, col));
                        }
                    }

                    int light_index = nb::cast<int>(entry.attr("light_index"));
                    shadow_maps.emplace_back(matrix, light_index);
                }
            }

            // Convert shadow settings
            ShadowSettings shadow_settings;
            if (!shadow_settings_py.is_none()) {
                shadow_settings.method = nb::cast<int>(shadow_settings_py.attr("method"));
                shadow_settings.softness = nb::cast<double>(shadow_settings_py.attr("softness"));
                shadow_settings.bias = nb::cast<double>(shadow_settings_py.attr("bias"));
            }

            // Call C++ execute_with_data
            self.execute_with_data(
                graphics,
                reads_fbos,
                writes_fbos,
                rect,
                entities,
                view,
                projection,
                camera_position,
                context_key,
                lights,
                ambient_color,
                ambient_intensity,
                shadow_maps,
                shadow_settings
            );
        },
        nb::arg("graphics"),
        nb::arg("reads_fbos"),
        nb::arg("writes_fbos"),
        nb::arg("rect"),
        nb::arg("entities"),
        nb::arg("view"),
        nb::arg("projection"),
        nb::arg("camera_position"),
        nb::arg("context_key"),
        nb::arg("lights"),
        nb::arg("ambient_color"),
        nb::arg("ambient_intensity"),
        nb::arg("shadow_array") = nb::none(),
        nb::arg("shadow_settings") = nb::none())
        .def("__repr__", [](const ColorPass& p) {
            return "<ColorPass '" + p.pass_name + "' phase='" + p.phase_mark + "'>";
        });
}

} // namespace termin
