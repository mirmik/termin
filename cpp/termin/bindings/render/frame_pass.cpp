#include "common.hpp"
#include <nanobind/stl/set.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/make_iterator.h>

extern "C" {
#include "tc_pass.h"
}

#include "termin/render/frame_pass.hpp"
#include "termin/render/frame_graph.hpp"
#include "termin/render/render_context.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/render.hpp"
#include "termin/render/color_pass.hpp"
#include "termin/render/depth_pass.hpp"
#include "termin/render/normal_pass.hpp"
#include "termin/render/id_pass.hpp"
#include "termin/render/shadow_pass.hpp"
#include "termin/entity/entity.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/lighting/light.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/lighting/shadow_settings.hpp"
#include "tc_scene.h"
#include "tc_log.hpp"
#include <cstdint>
#include <unordered_map>

namespace termin {

// ============================================================================
// Helper to create external tc_pass for C++ passes used from Python
// This ensures Python methods (compute_reads, compute_writes) are called
// ============================================================================

static void setup_external_tc_pass(FramePass* pass, nb::object py_self) {
    // Increment refcount since C code will hold a reference to the Python object
    Py_INCREF(py_self.ptr());

    // Create external tc_pass that will call Python methods
    tc_pass* ext_pass = tc_pass_new_external(py_self.ptr(), nb::type_name(py_self.type()).c_str());
    if (ext_pass) {
        tc_pass_set_name(ext_pass, pass->pass_name.c_str());
        pass->_tc_pass = ext_pass;
    } else {
        // Failed to create, decrement refcount
        Py_DECREF(py_self.ptr());
    }
}

// ============================================================================
// Python debugger callbacks holder
// Stores Python objects and provides C-style callbacks for FrameDebuggerCallbacks
// ============================================================================

struct PyDebuggerHolder {
    nb::object window;
    nb::object depth_callback;
    nb::object error_callback;

    static void blit_from_pass_cb(void* user_data, FramebufferHandle* fb,
                                   GraphicsBackend* graphics, int width, int height) {
        auto* holder = static_cast<PyDebuggerHolder*>(user_data);
        if (!holder || holder->window.is_none()) return;

        nb::gil_scoped_acquire gil;
        try {
            holder->window.attr("blit_from_pass")(
                nb::cast(fb, nb::rv_policy::reference),
                nb::cast(graphics, nb::rv_policy::reference),
                width, height,
                holder->depth_callback
            );
        } catch (const std::exception& e) {
            tc::Log::error("PyDebuggerHolder::blit_from_pass: %s", e.what());
        }
    }

    static void on_error_cb(void* user_data, const char* message) {
        auto* holder = static_cast<PyDebuggerHolder*>(user_data);
        if (!holder || holder->error_callback.is_none()) return;

        nb::gil_scoped_acquire gil;
        try {
            holder->error_callback(message);
        } catch (const std::exception& e) {
            tc::Log::error("PyDebuggerHolder::on_error: %s", e.what());
        }
    }
};

// Global map to hold Python debugger callbacks (prevents GC)
static std::unordered_map<RenderFramePass*, std::unique_ptr<PyDebuggerHolder>> g_debugger_holders;

// Helper to set up Python debugger callbacks on a pass
static void setup_py_debugger(RenderFramePass* pass, nb::object window,
                               nb::object depth_callback, nb::object error_callback) {
    if (window.is_none()) {
        // Clear callbacks
        g_debugger_holders.erase(pass);
        pass->clear_debugger_callbacks();
        return;
    }

    // Create or update holder
    auto& holder = g_debugger_holders[pass];
    if (!holder) {
        holder = std::make_unique<PyDebuggerHolder>();
    }
    holder->window = window;
    holder->depth_callback = depth_callback;
    holder->error_callback = error_callback;

    // Set C callbacks
    FrameDebuggerCallbacks callbacks;
    callbacks.user_data = holder.get();
    callbacks.blit_from_pass = PyDebuggerHolder::blit_from_pass_cb;
    callbacks.on_error = error_callback.is_none() ? nullptr : PyDebuggerHolder::on_error_cb;
    pass->set_debugger_callbacks(callbacks);
}

// Helper to get Python debugger window from pass
static nb::object get_py_debugger_window(RenderFramePass* pass) {
    auto it = g_debugger_holders.find(pass);
    if (it != g_debugger_holders.end() && it->second) {
        return it->second->window;
    }
    return nb::none();
}

void bind_frame_pass(nb::module_& m) {
    // Rect4i - viewport rectangle
    nb::class_<Rect4i>(m, "Rect4i")
        .def(nb::init<>())
        .def(nb::init<int, int, int, int>(),
             nb::arg("x"), nb::arg("y"), nb::arg("width"), nb::arg("height"))
        .def_rw("x", &Rect4i::x)
        .def_rw("y", &Rect4i::y)
        .def_rw("width", &Rect4i::width)
        .def_rw("height", &Rect4i::height)
        .def("__repr__", [](const Rect4i& r) {
            return "Rect4i(" + std::to_string(r.x) + ", " + std::to_string(r.y) +
                   ", " + std::to_string(r.width) + ", " + std::to_string(r.height) + ")";
        });

    // FrameGraphResource - base class for framegraph resources
    nb::class_<FrameGraphResource>(m, "FrameGraphResource")
        .def("resource_type", &FrameGraphResource::resource_type);

    // ShadowMapArrayEntry - single shadow map entry
    nb::class_<ShadowMapArrayEntry>(m, "ShadowMapArrayEntry")
        .def(nb::init<>())
        .def_rw("fbo", &ShadowMapArrayEntry::fbo)
        .def_rw("light_space_matrix", &ShadowMapArrayEntry::light_space_matrix)
        .def_rw("light_index", &ShadowMapArrayEntry::light_index)
        .def_rw("cascade_index", &ShadowMapArrayEntry::cascade_index)
        .def_rw("cascade_split_near", &ShadowMapArrayEntry::cascade_split_near)
        .def_rw("cascade_split_far", &ShadowMapArrayEntry::cascade_split_far)
        .def("texture", &ShadowMapArrayEntry::texture, nb::rv_policy::reference);

    // ShadowMapArrayResource - shadow map array for framegraph
    nb::class_<ShadowMapArrayResource, FrameGraphResource>(m, "ShadowMapArrayResource")
        .def(nb::init<>())
        .def(nb::init<int>(), nb::arg("resolution"))
        .def("resource_type", &ShadowMapArrayResource::resource_type)
        .def("size", &ShadowMapArrayResource::size)
        .def("empty", &ShadowMapArrayResource::empty)
        .def("clear", &ShadowMapArrayResource::clear)
        .def_rw("resolution", &ShadowMapArrayResource::resolution)
        .def_rw("entries", &ShadowMapArrayResource::entries)
        .def("__len__", &ShadowMapArrayResource::__len__)
        .def("__getitem__", [](ShadowMapArrayResource& self, size_t index) -> ShadowMapArrayEntry& {
            if (index >= self.size()) {
                throw nb::index_error("ShadowMapArrayResource index out of range");
            }
            return self[index];
        }, nb::rv_policy::reference)
        .def("__iter__", [](ShadowMapArrayResource& self) {
            return nb::make_iterator(nb::type<ShadowMapArrayResource>(), "iterator",
                                     self.begin(), self.end());
        }, nb::keep_alive<0, 1>())
        .def("get_by_light_index", &ShadowMapArrayResource::get_by_light_index, nb::rv_policy::reference)
        .def("add_entry", [](ShadowMapArrayResource& self,
                             FramebufferHandle* fbo,
                             nb::ndarray<nb::numpy, float, nb::shape<4, 4>> light_space_matrix,
                             int light_index,
                             int cascade_index,
                             float cascade_split_near,
                             float cascade_split_far) {
            Mat44f mat;
            auto view = light_space_matrix.view();
            // numpy is row-major: data[row * 4 + col]
            // Mat44f is column-major: data[col * 4 + row]
            // mat(col, row) accesses data[col * 4 + row]
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    mat(col, row) = view(row, col);
                }
            }
            self.add_entry(fbo, mat, light_index, cascade_index, cascade_split_near, cascade_split_far);
        }, nb::arg("fbo"), nb::arg("light_space_matrix"), nb::arg("light_index"),
           nb::arg("cascade_index") = 0, nb::arg("cascade_split_near") = 0.0f,
           nb::arg("cascade_split_far") = 0.0f);

    // Helper to convert Python dict to ResourceMap
    auto dict_to_resource_map = [](nb::dict py_dict) -> ResourceMap {
        ResourceMap result;
        for (auto item : py_dict) {
            std::string key = nb::cast<std::string>(nb::str(item.first));
            nb::object val = nb::borrow<nb::object>(item.second);
            if (!val.is_none()) {
                // Try FramebufferHandle first
                try {
                    result[key] = nb::cast<FramebufferHandle*>(val);
                    continue;
                } catch (const nb::cast_error&) {}
                // Try ShadowMapArrayResource
                try {
                    result[key] = nb::cast<ShadowMapArrayResource*>(val);
                    continue;
                } catch (const nb::cast_error&) {}
                // Unknown resource type - skip
            }
        }
        return result;
    };

    // ExecuteContext - context passed to render passes
    nb::class_<ExecuteContext>(m, "ExecuteContext")
        .def(nb::init<>())
        .def_prop_rw("graphics",
            [](const ExecuteContext& ctx) { return ctx.graphics; },
            [](ExecuteContext& ctx, GraphicsBackend* g) { ctx.graphics = g; },
            nb::rv_policy::reference)
        .def_prop_rw("reads_fbos",
            [](const ExecuteContext& ctx) -> nb::dict {
                nb::dict result;
                for (const auto& [key, val] : ctx.reads_fbos) {
                    if (auto* fbo = dynamic_cast<FramebufferHandle*>(val)) {
                        result[nb::str(key.c_str())] = nb::cast(fbo, nb::rv_policy::reference);
                    } else if (auto* shadow = dynamic_cast<ShadowMapArrayResource*>(val)) {
                        result[nb::str(key.c_str())] = nb::cast(shadow, nb::rv_policy::reference);
                    }
                }
                return result;
            },
            [dict_to_resource_map](ExecuteContext& ctx, nb::dict py_dict) {
                ctx.reads_fbos = dict_to_resource_map(py_dict);
            })
        .def_prop_rw("writes_fbos",
            [](const ExecuteContext& ctx) -> nb::dict {
                nb::dict result;
                for (const auto& [key, val] : ctx.writes_fbos) {
                    if (auto* fbo = dynamic_cast<FramebufferHandle*>(val)) {
                        result[nb::str(key.c_str())] = nb::cast(fbo, nb::rv_policy::reference);
                    } else if (auto* shadow = dynamic_cast<ShadowMapArrayResource*>(val)) {
                        result[nb::str(key.c_str())] = nb::cast(shadow, nb::rv_policy::reference);
                    }
                }
                return result;
            },
            [dict_to_resource_map](ExecuteContext& ctx, nb::dict py_dict) {
                ctx.writes_fbos = dict_to_resource_map(py_dict);
            })
        .def_rw("rect", &ExecuteContext::rect)
        .def_prop_rw("scene",
            [](const ExecuteContext& ctx) -> uintptr_t {
                return reinterpret_cast<uintptr_t>(ctx.scene);
            },
            [](ExecuteContext& ctx, uintptr_t ptr) {
                ctx.scene = reinterpret_cast<tc_scene*>(ptr);
            })
        .def_prop_rw("camera",
            [](const ExecuteContext& ctx) { return ctx.camera; },
            [](ExecuteContext& ctx, CameraComponent* c) { ctx.camera = c; },
            nb::rv_policy::reference)
        .def_prop_rw("viewport",
            [](const ExecuteContext& ctx) -> uintptr_t {
                return reinterpret_cast<uintptr_t>(ctx.viewport);
            },
            [](ExecuteContext& ctx, uintptr_t ptr) {
                ctx.viewport = reinterpret_cast<tc_viewport*>(ptr);
            })
        .def_rw("lights", &ExecuteContext::lights)
        .def_rw("layer_mask", &ExecuteContext::layer_mask);

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
        .def_rw("viewport_name", &FramePass::viewport_name)
        .def("get_inplace_aliases", &FramePass::get_inplace_aliases)
        .def("is_inplace", &FramePass::is_inplace)
        .def_prop_ro("inplace", &FramePass::is_inplace)
        .def("get_internal_symbols", &FramePass::get_internal_symbols)
        .def("set_debug_internal_point", &FramePass::set_debug_internal_point)
        .def("clear_debug_internal_point", &FramePass::clear_debug_internal_point)
        .def("get_debug_internal_point", &FramePass::get_debug_internal_point)
        .def("required_resources", &FramePass::required_resources)
        // Expose tc_pass handle to Python for frame graph integration
        // Writable to allow Python subclasses to replace with external tc_pass
        .def_prop_rw("_tc_pass",
            [](FramePass& p) -> tc_pass* {
                return p.tc_pass_handle();
            },
            [](FramePass& p, tc_pass* new_pass) {
                p._tc_pass = new_pass;
            },
            nb::rv_policy::reference)
        // Setup external tc_pass for Python usage (calls Python methods)
        .def("_setup_external_tc_pass", [](FramePass& self, nb::object py_self) {
            setup_external_tc_pass(&self, py_self);
        }, nb::arg("py_self"),
           "Create external tc_pass that calls Python methods. Call after super().__init__().")
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
            if (kwargs.contains("layer_mask")) {
                self->layer_mask = nb::cast<uint64_t>(kwargs["layer_mask"]);
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
            // current_shader removed - use current_tc_shader instead
            if (kwargs.contains("view")) {
                nb::object v = nb::borrow<nb::object>(kwargs["view"]);
                if (nb::isinstance<Mat44>(v)) {
                    self->view = nb::cast<Mat44>(v).to_float();
                } else {
                    nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(v);
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            self->view.data[col * 4 + row] = arr(row, col);
                        }
                    }
                }
            }
            if (kwargs.contains("projection")) {
                nb::object p = nb::borrow<nb::object>(kwargs["projection"]);
                if (nb::isinstance<Mat44>(p)) {
                    self->projection = nb::cast<Mat44>(p).to_float();
                } else {
                    nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(p);
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            self->projection.data[col * 4 + row] = arr(row, col);
                        }
                    }
                }
            }
            if (kwargs.contains("model")) {
                nb::object m = nb::borrow<nb::object>(kwargs["model"]);
                if (nb::isinstance<Mat44>(m)) {
                    self->model = nb::cast<Mat44>(m).to_float();
                } else {
                    nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(m);
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            self->model.data[col * 4 + row] = arr(row, col);
                        }
                    }
                }
            }
        })
        .def_rw("phase", &RenderContext::phase)
        .def_rw("scene", &RenderContext::scene)
        .def_rw("shadow_data", &RenderContext::shadow_data)
        .def_rw("extra_uniforms", &RenderContext::extra_uniforms)
        .def_rw("layer_mask", &RenderContext::layer_mask)
        .def_rw("camera", &RenderContext::camera)
        // graphics
        .def_prop_rw("graphics",
            [](const RenderContext& self) -> GraphicsBackend* { return self.graphics; },
            [](RenderContext& self, GraphicsBackend* g) { self.graphics = g; },
            nb::rv_policy::reference)
        // current_shader removed - use current_tc_shader instead
        // view matrix
        .def_prop_rw("view",
            [](const RenderContext& self) { return self.view; },
            [](RenderContext& self, nb::object v) {
                if (nb::isinstance<Mat44>(v)) {
                    self.view = nb::cast<Mat44>(v).to_float();
                } else if (nb::isinstance<Mat44f>(v)) {
                    self.view = nb::cast<Mat44f>(v);
                } else {
                    nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(v);
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            self.view.data[col * 4 + row] = arr(row, col);
                        }
                    }
                }
            }
        )
        // projection matrix
        .def_prop_rw("projection",
            [](const RenderContext& self) { return self.projection; },
            [](RenderContext& self, nb::object p) {
                if (nb::isinstance<Mat44>(p)) {
                    self.projection = nb::cast<Mat44>(p).to_float();
                } else if (nb::isinstance<Mat44f>(p)) {
                    self.projection = nb::cast<Mat44f>(p);
                } else {
                    nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(p);
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            self.projection.data[col * 4 + row] = arr(row, col);
                        }
                    }
                }
            }
        )
        // model matrix
        .def_prop_rw("model",
            [](const RenderContext& self) { return self.model; },
            [](RenderContext& self, nb::object m) {
                if (nb::isinstance<Mat44>(m)) {
                    self.model = nb::cast<Mat44>(m).to_float();
                } else if (nb::isinstance<Mat44f>(m)) {
                    self.model = nb::cast<Mat44f>(m);
                } else {
                    nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(m);
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            self.model.data[col * 4 + row] = arr(row, col);
                        }
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

    // RenderFramePass - base class for FBO-based render passes
    nb::class_<RenderFramePass, FramePass>(m, "RenderFramePass")
        .def("set_debugger_window", [](RenderFramePass& self, nb::object window,
                                        nb::object depth_callback, nb::object error_callback) {
            setup_py_debugger(&self, window, depth_callback, error_callback);
        },
             nb::arg("window").none(),
             nb::arg("depth_callback").none() = nb::none(),
             nb::arg("depth_error_callback").none() = nb::none())
        .def("get_debugger_window", [](RenderFramePass& self) {
            return get_py_debugger_window(&self);
        })
        .def_prop_rw("debugger_window",
            [](RenderFramePass& self) { return get_py_debugger_window(&self); },
            [](RenderFramePass& self, nb::object val) {
                setup_py_debugger(&self, val, nb::none(), nb::none());
            })
        .def_prop_rw("depth_capture_callback",
            [](RenderFramePass& self) {
                auto it = g_debugger_holders.find(&self);
                if (it != g_debugger_holders.end() && it->second) {
                    return it->second->depth_callback;
                }
                return nb::object(nb::none());
            },
            [](RenderFramePass& self, nb::object val) {
                auto it = g_debugger_holders.find(&self);
                if (it != g_debugger_holders.end() && it->second) {
                    it->second->depth_callback = val;
                }
            })
        .def_prop_rw("_debugger_window",
            [](RenderFramePass& self) { return get_py_debugger_window(&self); },
            [](RenderFramePass& self, nb::object val) {
                setup_py_debugger(&self, val, nb::none(), nb::none());
            })
        .def_prop_rw("_depth_capture_callback",
            [](RenderFramePass& self) {
                auto it = g_debugger_holders.find(&self);
                if (it != g_debugger_holders.end() && it->second) {
                    return it->second->depth_callback;
                }
                return nb::object(nb::none());
            },
            [](RenderFramePass& self, nb::object val) {
                auto it = g_debugger_holders.find(&self);
                if (it != g_debugger_holders.end() && it->second) {
                    it->second->depth_callback = val;
                }
            })
        .def("get_resource_specs", &RenderFramePass::get_resource_specs)
        .def("destroy", &RenderFramePass::destroy);

    // ColorPass - main color rendering pass
    nb::class_<ColorPass, RenderFramePass>(m, "ColorPass")
        .def("__init__", [](ColorPass* self, const std::string& input_res, const std::string& output_res,
                            const std::string& shadow_res, const std::string& phase_mark,
                            const std::string& pass_name, const std::string& sort_mode, bool clear_depth) {
            new (self) ColorPass(input_res, output_res, shadow_res, phase_mark, pass_name, sort_mode, clear_depth);
        },
             nb::arg("input_res") = "empty",
             nb::arg("output_res") = "color",
             nb::arg("shadow_res") = "shadow_maps",
             nb::arg("phase_mark") = "opaque",
             nb::arg("pass_name") = "Color",
             nb::arg("sort_mode") = "none",
             nb::arg("clear_depth") = false)
        .def_rw("input_res", &ColorPass::input_res)
        .def_rw("output_res", &ColorPass::output_res)
        .def_rw("shadow_res", &ColorPass::shadow_res)
        .def_rw("phase_mark", &ColorPass::phase_mark)
        .def_rw("sort_mode", &ColorPass::sort_mode)
        .def_rw("clear_depth", &ColorPass::clear_depth)
        .def_rw("wireframe", &ColorPass::wireframe)
        .def("get_resource_specs", &ColorPass::get_resource_specs)
        .def("get_internal_symbols", &ColorPass::get_internal_symbols)
        .def("execute_with_data", [](
            ColorPass& self,
            GraphicsBackend* graphics,
            nb::dict reads_fbos_py,
            nb::dict writes_fbos_py,
            nb::tuple rect_py,
            nb::object scene_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> projection_py,
            nb::ndarray<nb::numpy, double, nb::shape<3>> camera_position_py,
            nb::list lights_py,
            nb::ndarray<nb::numpy, double, nb::shape<3>> ambient_color_py,
            float ambient_intensity,
            nb::object shadow_array_py,
            nb::object shadow_settings_py,
            uint64_t layer_mask
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

            // Get tc_scene* from Python Scene object
            tc_scene* scene = nullptr;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "_tc_scene")) {
                nb::object tc_scene_obj = scene_py.attr("_tc_scene");
                if (nb::hasattr(tc_scene_obj, "scene_ptr")) {
                    uintptr_t scene_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                    scene = reinterpret_cast<tc_scene*>(scene_ptr);
                }
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
            std::vector<ShadowMapArrayEntry> shadow_maps;
            if (!shadow_array_py.is_none()) {
                size_t count = nb::len(shadow_array_py);
                for (size_t i = 0; i < count; ++i) {
                    nb::object entry = shadow_array_py[nb::int_(i)];

                    // Get fbo
                    FramebufferHandle* fbo = nb::cast<FramebufferHandle*>(entry.attr("fbo"));

                    // Get light_space_matrix as numpy array
                    nb::ndarray<nb::numpy, double, nb::shape<4, 4>> matrix_py = nb::cast<nb::ndarray<nb::numpy, double, nb::shape<4, 4>>>(entry.attr("light_space_matrix"));
                    Mat44f matrix;
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            matrix(col, row) = static_cast<float>(matrix_py(row, col));
                        }
                    }

                    int light_index = nb::cast<int>(entry.attr("light_index"));
                    int cascade_index = nb::cast<int>(entry.attr("cascade_index"));
                    float cascade_split_near = nb::cast<float>(entry.attr("cascade_split_near"));
                    float cascade_split_far = nb::cast<float>(entry.attr("cascade_split_far"));
                    shadow_maps.emplace_back(fbo, matrix, light_index, cascade_index, cascade_split_near, cascade_split_far);
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
                scene,
                view,
                projection,
                camera_position,
                lights,
                ambient_color,
                ambient_intensity,
                shadow_maps,
                shadow_settings,
                layer_mask
            );
        },
        nb::arg("graphics"),
        nb::arg("reads_fbos"),
        nb::arg("writes_fbos"),
        nb::arg("rect"),
        nb::arg("scene"),
        nb::arg("view"),
        nb::arg("projection"),
        nb::arg("camera_position"),
        nb::arg("lights"),
        nb::arg("ambient_color"),
        nb::arg("ambient_intensity"),
        nb::arg("shadow_array") = nb::none(),
        nb::arg("shadow_settings") = nb::none(),
        nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL)
        .def_rw("extra_texture_uniforms", &ColorPass::extra_texture_uniforms)
        .def("clear_extra_textures", &ColorPass::clear_extra_textures)
        .def("set_extra_texture_uniform", &ColorPass::set_extra_texture_uniform)
        .def("execute", [](ColorPass& self, ExecuteContext& ctx) {
            self.execute(ctx);
        }, nb::arg("ctx"))
        .def("destroy", &ColorPass::destroy)
        .def("__repr__", [](const ColorPass& p) {
            return "<ColorPass '" + p.pass_name + "' phase='" + p.phase_mark + "'>";
        });

    // DepthPass - linear depth rendering pass
    nb::class_<DepthPass, RenderFramePass>(m, "DepthPass")
        .def("__init__", [](DepthPass* self, const std::string& input_res,
                            const std::string& output_res, const std::string& pass_name) {
            new (self) DepthPass(input_res, output_res, pass_name);
        },
             nb::arg("input_res") = "empty_depth",
             nb::arg("output_res") = "depth",
             nb::arg("pass_name") = "Depth")
        .def_rw("input_res", &DepthPass::input_res)
        .def_rw("output_res", &DepthPass::output_res)
        .def("get_internal_symbols", &DepthPass::get_internal_symbols)
        .def("execute_with_data", [](
            DepthPass& self,
            GraphicsBackend* graphics,
            nb::dict reads_fbos_py,
            nb::dict writes_fbos_py,
            nb::tuple rect_py,
            nb::object scene_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> projection_py,
            float near_plane,
            float far_plane,
            uint64_t layer_mask
        ) {
            // Convert FBO maps
            FBOMap reads_fbos, writes_fbos;
            for (auto item : reads_fbos_py) {
                std::string key = nb::cast<std::string>(nb::str(item.first));
                nb::object val = nb::borrow<nb::object>(item.second);
                if (!val.is_none()) {
                    try {
                        reads_fbos[key] = nb::cast<FramebufferHandle*>(val);
                    } catch (const nb::cast_error&) {
                        // Skip non-FBO resources
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

            // Get tc_scene* from Python Scene object
            tc_scene* scene = nullptr;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "_tc_scene")) {
                nb::object tc_scene_obj = scene_py.attr("_tc_scene");
                if (nb::hasattr(tc_scene_obj, "scene_ptr")) {
                    uintptr_t scene_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                    scene = reinterpret_cast<tc_scene*>(scene_ptr);
                }
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

            // Call C++ execute_with_data
            self.execute_with_data(
                graphics,
                reads_fbos,
                writes_fbos,
                rect,
                scene,
                view,
                projection,
                near_plane,
                far_plane,
                layer_mask
            );
        },
        nb::arg("graphics"),
        nb::arg("reads_fbos"),
        nb::arg("writes_fbos"),
        nb::arg("rect"),
        nb::arg("scene"),
        nb::arg("view"),
        nb::arg("projection"),
        nb::arg("near_plane"),
        nb::arg("far_plane"),
        nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL)
        .def("destroy", &DepthPass::destroy)
        .def("__repr__", [](const DepthPass& p) {
            return "<DepthPass '" + p.pass_name + "'>";
        });

    // NormalPass - world-space normal rendering pass
    nb::class_<NormalPass, RenderFramePass>(m, "NormalPass")
        .def("__init__", [](NormalPass* self, const std::string& input_res,
                            const std::string& output_res, const std::string& pass_name) {
            new (self) NormalPass(input_res, output_res, pass_name);
        },
             nb::arg("input_res") = "empty_normal",
             nb::arg("output_res") = "normal",
             nb::arg("pass_name") = "Normal")
        .def_rw("input_res", &NormalPass::input_res)
        .def_rw("output_res", &NormalPass::output_res)
        .def("get_resource_specs", &NormalPass::get_resource_specs)
        .def("get_internal_symbols", &NormalPass::get_internal_symbols)
        .def("execute_with_data", [](
            NormalPass& self,
            GraphicsBackend* graphics,
            nb::dict reads_fbos_py,
            nb::dict writes_fbos_py,
            nb::tuple rect_py,
            nb::object scene_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> projection_py,
            uint64_t layer_mask
        ) {
            // Convert FBO maps
            FBOMap reads_fbos, writes_fbos;
            for (auto item : reads_fbos_py) {
                std::string key = nb::cast<std::string>(nb::str(item.first));
                nb::object val = nb::borrow<nb::object>(item.second);
                if (!val.is_none()) {
                    try {
                        reads_fbos[key] = nb::cast<FramebufferHandle*>(val);
                    } catch (const nb::cast_error&) {
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
                    }
                }
            }

            // Convert rect
            Rect4i rect;
            rect.x = nb::cast<int>(rect_py[0]);
            rect.y = nb::cast<int>(rect_py[1]);
            rect.width = nb::cast<int>(rect_py[2]);
            rect.height = nb::cast<int>(rect_py[3]);

            // Get tc_scene* from Python Scene object
            tc_scene* scene = nullptr;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "_tc_scene")) {
                nb::object tc_scene_obj = scene_py.attr("_tc_scene");
                if (nb::hasattr(tc_scene_obj, "scene_ptr")) {
                    uintptr_t scene_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                    scene = reinterpret_cast<tc_scene*>(scene_ptr);
                }
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

            // Call C++ execute_with_data
            self.execute_with_data(
                graphics,
                reads_fbos,
                writes_fbos,
                rect,
                scene,
                view,
                projection,
                layer_mask
            );
        },
        nb::arg("graphics"),
        nb::arg("reads_fbos"),
        nb::arg("writes_fbos"),
        nb::arg("rect"),
        nb::arg("scene"),
        nb::arg("view"),
        nb::arg("projection"),
        nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL)
        .def("destroy", &NormalPass::destroy)
        .def("__repr__", [](const NormalPass& p) {
            return "<NormalPass '" + p.pass_name + "'>";
        });

    // IdPass - entity ID rendering pass for picking
    nb::class_<IdPass, RenderFramePass>(m, "IdPass")
        .def("__init__", [](IdPass* self, const std::string& input_res,
                            const std::string& output_res, const std::string& pass_name) {
            new (self) IdPass(input_res, output_res, pass_name);
        },
             nb::arg("input_res") = "empty",
             nb::arg("output_res") = "id",
             nb::arg("pass_name") = "IdPass")
        .def_rw("input_res", &IdPass::input_res)
        .def_rw("output_res", &IdPass::output_res)
        .def("get_internal_symbols", &IdPass::get_internal_symbols)
        .def("execute_with_data", [](
            IdPass& self,
            GraphicsBackend* graphics,
            nb::dict reads_fbos_py,
            nb::dict writes_fbos_py,
            nb::tuple rect_py,
            nb::object scene_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> projection_py,
            uint64_t layer_mask
        ) {
            // Convert FBO maps
            FBOMap reads_fbos, writes_fbos;
            for (auto item : reads_fbos_py) {
                std::string key = nb::cast<std::string>(nb::str(item.first));
                nb::object val = nb::borrow<nb::object>(item.second);
                if (!val.is_none()) {
                    try {
                        reads_fbos[key] = nb::cast<FramebufferHandle*>(val);
                    } catch (const nb::cast_error&) {
                        // Skip non-FBO resources
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

            // Get tc_scene* from Python Scene object
            tc_scene* scene = nullptr;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "_tc_scene")) {
                nb::object tc_scene_obj = scene_py.attr("_tc_scene");
                if (nb::hasattr(tc_scene_obj, "scene_ptr")) {
                    uintptr_t scene_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                    scene = reinterpret_cast<tc_scene*>(scene_ptr);
                }
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

            // Call C++ execute_with_data
            self.execute_with_data(
                graphics,
                reads_fbos,
                writes_fbos,
                rect,
                scene,
                view,
                projection,
                layer_mask
            );
        },
        nb::arg("graphics"),
        nb::arg("reads_fbos"),
        nb::arg("writes_fbos"),
        nb::arg("rect"),
        nb::arg("scene"),
        nb::arg("view"),
        nb::arg("projection"),
        nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL)
        .def("destroy", &IdPass::destroy)
        .def("__repr__", [](const IdPass& p) {
            return "<IdPass '" + p.pass_name + "'>";
        });

    // ShadowMapResult - result of shadow map rendering
    nb::class_<ShadowMapResult>(m, "ShadowMapResult")
        .def(nb::init<>())
        .def_ro("fbo", &ShadowMapResult::fbo)
        .def_prop_ro("light_space_matrix", [](const ShadowMapResult& self) {
            // Convert Mat44f to numpy array (row-major)
            // Use nb::ndarray with copy semantics to avoid ownership issues
            size_t shape[2] = {4, 4};
            float* data = new float[16];
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    data[row * 4 + col] = self.light_space_matrix(col, row);
                }
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            return nb::ndarray<nb::numpy, float, nb::ndim<2>>(data, 2, shape, owner);
        }, nb::rv_policy::move)
        .def_ro("light_index", &ShadowMapResult::light_index)
        // Cascade parameters
        .def_ro("cascade_index", &ShadowMapResult::cascade_index)
        .def_ro("cascade_split_near", &ShadowMapResult::cascade_split_near)
        .def_ro("cascade_split_far", &ShadowMapResult::cascade_split_far);

    // ShadowPass - shadow map rendering pass
    nb::class_<ShadowPass, RenderFramePass>(m, "ShadowPass")
        .def("__init__", [](ShadowPass* self, const std::string& output_res,
                            const std::string& pass_name, float caster_offset) {
            new (self) ShadowPass(output_res, pass_name, caster_offset);
        },
             nb::arg("output_res") = "shadow_maps",
             nb::arg("pass_name") = "Shadow",
             nb::arg("caster_offset") = 50.0f)
        .def_rw("output_res", &ShadowPass::output_res)
        .def_rw("caster_offset", &ShadowPass::caster_offset)
        .def_prop_rw("shadow_shader",
            [](ShadowPass& self) -> TcShader* { return self.shadow_shader; },
            [](ShadowPass& self, TcShader* s) { self.shadow_shader = s; })
        .def("get_internal_symbols", &ShadowPass::get_internal_symbols)
        .def("execute_shadow_pass", [](
            ShadowPass& self,
            GraphicsBackend* graphics,
            nb::object scene_py,
            nb::list lights_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> camera_view_py,
            nb::ndarray<nb::numpy, float, nb::shape<4, 4>> camera_projection_py
        ) {
            // Get tc_scene* from Python Scene object
            tc_scene* scene = nullptr;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "_tc_scene")) {
                nb::object tc_scene_obj = scene_py.attr("_tc_scene");
                if (nb::hasattr(tc_scene_obj, "scene_ptr")) {
                    uintptr_t scene_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                    scene = reinterpret_cast<tc_scene*>(scene_ptr);
                }
            }

            // Convert lights
            std::vector<Light> lights;
            for (auto item : lights_py) {
                lights.push_back(nb::cast<Light>(item));
            }

            // Convert view matrix (row-major numpy -> column-major Mat44f)
            Mat44f camera_view;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    camera_view(col, row) = camera_view_py(row, col);
                }
            }

            // Convert projection matrix
            Mat44f camera_projection;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    camera_projection(col, row) = camera_projection_py(row, col);
                }
            }

            // Call C++ execute
            std::vector<ShadowMapResult> results = self.execute_shadow_pass(
                graphics, scene, lights, camera_view, camera_projection
            );

            // Convert results to Python list
            nb::list result_list;
            for (const auto& r : results) {
                result_list.append(nb::cast(r));
            }
            return result_list;
        },
        nb::arg("graphics"),
        nb::arg("scene"),
        nb::arg("lights"),
        nb::arg("camera_view"),
        nb::arg("camera_projection"))
        .def("destroy", &ShadowPass::destroy)
        .def("__repr__", [](const ShadowPass& p) {
            return "<ShadowPass '" + p.pass_name + "'>";
        });
}

} // namespace termin
