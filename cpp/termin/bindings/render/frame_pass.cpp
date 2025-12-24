#include "common.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render/frame_graph.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/render.hpp"
#include "termin/render/shader_program.hpp"

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
}

} // namespace termin
