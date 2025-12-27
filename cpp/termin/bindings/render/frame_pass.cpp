#include "common.hpp"
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

void bind_frame_pass(py::module_& m) {
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
        .def_property_readonly("inplace", &FramePass::is_inplace)
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

    // ColorPass - main color rendering pass
    py::class_<ColorPass, FramePass>(m, "ColorPass")
        .def(py::init<const std::string&, const std::string&, const std::string&,
                      const std::string&, const std::string&, bool, bool>(),
             py::arg("input_res") = "empty",
             py::arg("output_res") = "color",
             py::arg("shadow_res") = "shadow_maps",
             py::arg("phase_mark") = "opaque",
             py::arg("pass_name") = "Color",
             py::arg("sort_by_distance") = false,
             py::arg("clear_depth") = false)
        .def_readwrite("input_res", &ColorPass::input_res)
        .def_readwrite("output_res", &ColorPass::output_res)
        .def_readwrite("shadow_res", &ColorPass::shadow_res)
        .def_readwrite("phase_mark", &ColorPass::phase_mark)
        .def_readwrite("sort_by_distance", &ColorPass::sort_by_distance)
        .def_readwrite("clear_depth", &ColorPass::clear_depth)
        .def("get_resource_specs", &ColorPass::get_resource_specs)
        .def("get_internal_symbols", &ColorPass::get_internal_symbols)
        .def("set_debugger_window", &ColorPass::set_debugger_window,
             py::arg("window"),
             py::arg("depth_callback") = py::none())
        .def("get_debugger_window", &ColorPass::get_debugger_window)
        .def_readwrite("debugger_window", &ColorPass::debugger_window)
        .def_readwrite("depth_capture_callback", &ColorPass::depth_capture_callback)
        .def_property("_debugger_window",
            [](const ColorPass& self) { return self.debugger_window; },
            [](ColorPass& self, py::object val) { self.debugger_window = val; })
        .def_property("_depth_capture_callback",
            [](const ColorPass& self) { return self.depth_capture_callback; },
            [](ColorPass& self, py::object val) { self.depth_capture_callback = val; })
        .def("execute_with_data", [](
            ColorPass& self,
            GraphicsBackend* graphics,
            py::dict reads_fbos_py,
            py::dict writes_fbos_py,
            py::tuple rect_py,
            py::list entities_py,
            py::array_t<float> view_py,
            py::array_t<float> projection_py,
            py::array_t<double> camera_position_py,
            int64_t context_key,
            py::list lights_py,
            py::array_t<double> ambient_color_py,
            float ambient_intensity,
            py::object shadow_array_py,
            py::object shadow_settings_py
        ) {
            // Convert FBO maps (skip non-FBO resources like ShadowMapArrayResource)
            FBOMap reads_fbos, writes_fbos;
            for (auto item : reads_fbos_py) {
                std::string key = py::str(item.first);
                py::object val = py::reinterpret_borrow<py::object>(item.second);
                if (!val.is_none()) {
                    try {
                        reads_fbos[key] = val.cast<FramebufferHandle*>();
                    } catch (const py::cast_error&) {
                        // Skip non-FBO resources (e.g., ShadowMapArrayResource)
                    }
                }
            }
            for (auto item : writes_fbos_py) {
                std::string key = py::str(item.first);
                py::object val = py::reinterpret_borrow<py::object>(item.second);
                if (!val.is_none()) {
                    try {
                        writes_fbos[key] = val.cast<FramebufferHandle*>();
                    } catch (const py::cast_error&) {
                        // Skip non-FBO resources
                    }
                }
            }

            // Convert rect
            Rect4i rect;
            rect.x = rect_py[0].cast<int>();
            rect.y = rect_py[1].cast<int>();
            rect.width = rect_py[2].cast<int>();
            rect.height = rect_py[3].cast<int>();

            // Convert entities
            std::vector<Entity*> entities;
            for (auto item : entities_py) {
                entities.push_back(item.cast<Entity*>());
            }

            // Convert view matrix (row-major numpy -> column-major Mat44f)
            Mat44f view;
            auto view_buf = view_py.unchecked<2>();
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    view(col, row) = view_buf(row, col);
                }
            }

            // Convert projection matrix
            Mat44f projection;
            auto proj_buf = projection_py.unchecked<2>();
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    projection(col, row) = proj_buf(row, col);
                }
            }

            // Convert camera position
            auto cam_buf = camera_position_py.unchecked<1>();
            Vec3 camera_position{cam_buf(0), cam_buf(1), cam_buf(2)};

            // Convert lights
            std::vector<Light> lights;
            for (auto item : lights_py) {
                lights.push_back(item.cast<Light>());
            }

            // Convert ambient color
            auto amb_buf = ambient_color_py.unchecked<1>();
            Vec3 ambient_color{amb_buf(0), amb_buf(1), amb_buf(2)};

            // Convert shadow maps
            std::vector<ShadowMapEntry> shadow_maps;
            if (!shadow_array_py.is_none()) {
                py::ssize_t count = py::len(shadow_array_py);
                for (py::ssize_t i = 0; i < count; ++i) {
                    py::object entry = shadow_array_py[py::int_(i)];

                    // Get light_space_matrix as numpy array (compute_light_space_matrix returns float64)
                    py::array_t<double> matrix_py = entry.attr("light_space_matrix").cast<py::array_t<double>>();
                    auto matrix_buf = matrix_py.unchecked<2>();
                    Mat44f matrix;
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            matrix(col, row) = static_cast<float>(matrix_buf(row, col));
                        }
                    }

                    int light_index = entry.attr("light_index").cast<int>();
                    shadow_maps.emplace_back(matrix, light_index);
                }
            }

            // Convert shadow settings
            ShadowSettings shadow_settings;
            if (!shadow_settings_py.is_none()) {
                shadow_settings.method = shadow_settings_py.attr("method").cast<int>();
                shadow_settings.softness = shadow_settings_py.attr("softness").cast<double>();
                shadow_settings.bias = shadow_settings_py.attr("bias").cast<double>();
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
        py::arg("graphics"),
        py::arg("reads_fbos"),
        py::arg("writes_fbos"),
        py::arg("rect"),
        py::arg("entities"),
        py::arg("view"),
        py::arg("projection"),
        py::arg("camera_position"),
        py::arg("context_key"),
        py::arg("lights"),
        py::arg("ambient_color"),
        py::arg("ambient_intensity"),
        py::arg("shadow_array") = py::none(),
        py::arg("shadow_settings") = py::none())
        .def("__repr__", [](const ColorPass& p) {
            return "<ColorPass '" + p.pass_name + "' phase='" + p.phase_mark + "'>";
        });
}

} // namespace termin
