#include "common.hpp"
#include <nanobind/stl/set.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/pair.h>
#include <nanobind/make_iterator.h>

extern "C" {
#include "render/tc_pass.h"
}

#include "termin/render/frame_pass.hpp"
#include "termin/render/tc_pass.hpp"
#include "termin/render/render_context.hpp"
#include "termin/editor/frame_graph_debugger_core.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render/render.hpp"
#include "termin/render/color_pass.hpp"
#include "termin/render/collider_gizmo_pass.hpp"
#include "termin/render/depth_pass.hpp"
#include "termin/render/normal_pass.hpp"
#include "termin/render/id_pass.hpp"
#include "termin/render/shadow_pass.hpp"
#include "termin/render/material_pass.hpp"
#include "termin/render/present_pass.hpp"
#include "termin/render/bloom_pass.hpp"
#include "termin/render/grayscale_pass.hpp"
#include "termin/render/tonemap_pass.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "termin/entity/entity.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/lighting/light.hpp"
#include "termin/lighting/shadow.hpp"
#include "termin/lighting/shadow_settings.hpp"
#include "termin/tc_scene.hpp"
#include "termin/viewport/tc_viewport_ref.hpp"
#include "core/tc_scene.h"
#include "tc_log.hpp"
#include <cstdint>
#include <cstdio>
#include <unordered_map>

namespace termin {

// Python ref_vtable for CxxFramePass created from Python (defined in tc_pass_bindings.cpp)
extern const tc_pass_ref_vtable g_py_pass_ref_vtable;

// Python ref_vtable for CxxFramePass wrappers: retain=Py_INCREF, release=Py_DECREF, drop=NULL
// (C++ CxxFramePass still owns memory; Python just holds a reference)
static void py_cxx_pass_ref_retain(tc_pass* p) {
    if (p && p->body) Py_INCREF(reinterpret_cast<PyObject*>(p->body));
}

static void py_cxx_pass_ref_release(tc_pass* p) {
    if (p && p->body) Py_DECREF(reinterpret_cast<PyObject*>(p->body));
}

static const tc_pass_ref_vtable g_py_cxx_pass_ref_vtable = {
    py_cxx_pass_ref_retain,
    py_cxx_pass_ref_release,
    nullptr,  // drop: C++ owns the CxxFramePass, no forced destroy
};

// ============================================================================
// Helper to initialize C++ pass created from Python bindings
// Combines: link_to_type_registry + set_python_ref + Py_INCREF
// ============================================================================

template<typename T>
void init_pass_from_python(T* self, const char* type_name) {
    self->link_to_type_registry(type_name);
    nb::object wrapper = nb::cast(self, nb::rv_policy::reference);
    self->set_python_ref(wrapper.ptr(), &g_py_cxx_pass_ref_vtable);
    Py_INCREF(wrapper.ptr());
}

// Variant for _deserialize_instance: takes ownership and returns wrapper
template<typename T>
nb::object init_pass_from_deserialize(T* pass, const char* type_name) {
    pass->link_to_type_registry(type_name);
    nb::object wrapper = nb::cast(pass, nb::rv_policy::take_ownership);
    pass->set_python_ref(wrapper.ptr(), &g_py_cxx_pass_ref_vtable);
    Py_INCREF(wrapper.ptr());
    return wrapper;
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
static std::unordered_map<CxxFramePass*, std::unique_ptr<PyDebuggerHolder>> g_debugger_holders;

// Helper to set up Python debugger callbacks on a pass
static void setup_py_debugger(CxxFramePass* pass, nb::object window,
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
static nb::object get_py_debugger_window(CxxFramePass* pass) {
    auto it = g_debugger_holders.find(pass);
    if (it != g_debugger_holders.end() && it->second) {
        return it->second->window;
    }
    return nb::none();
}

void bind_frame_pass(nb::module_& m) {
    // InternalSymbolTiming - timing info for debug symbols
    nb::class_<InternalSymbolTiming>(m, "InternalSymbolTiming")
        .def(nb::init<>())
        .def_rw("name", &InternalSymbolTiming::name)
        .def_rw("cpu_time_ms", &InternalSymbolTiming::cpu_time_ms)
        .def_rw("gpu_time_ms", &InternalSymbolTiming::gpu_time_ms)
        .def("__repr__", [](const InternalSymbolTiming& t) {
            char buf[128];
            snprintf(buf, sizeof(buf), "<InternalSymbolTiming '%s' cpu=%.3fms gpu=%.3fms>",
                     t.name.c_str(), t.cpu_time_ms, t.gpu_time_ms);
            return std::string(buf);
        });

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
        })
        .def("__iter__", [](const Rect4i& r) {
            return nb::make_tuple(r.x, r.y, r.width, r.height).attr("__iter__")();
        })
        .def("__len__", [](const Rect4i&) { return 4; });

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
           nb::arg("cascade_split_far") = 0.0f)
        .def("delete", [](ShadowMapArrayResource& self) {
            // Clear entries - FBOs are managed by ShadowPass
            self.clear();
        }, "Delete resource (clears entries)");

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
        .def("__init__", [dict_to_resource_map](ExecuteContext* self, nb::kwargs kwargs) {
            new (self) ExecuteContext();
            if (kwargs.contains("graphics")) {
                nb::object g = nb::borrow<nb::object>(kwargs["graphics"]);
                if (!g.is_none()) {
                    self->graphics = nb::cast<GraphicsBackend*>(g);
                }
            }
            if (kwargs.contains("reads_fbos")) {
                nb::dict d = nb::cast<nb::dict>(kwargs["reads_fbos"]);
                self->reads_fbos = dict_to_resource_map(d);
            }
            if (kwargs.contains("writes_fbos")) {
                nb::dict d = nb::cast<nb::dict>(kwargs["writes_fbos"]);
                self->writes_fbos = dict_to_resource_map(d);
            }
            if (kwargs.contains("rect")) {
                nb::tuple t = nb::cast<nb::tuple>(kwargs["rect"]);
                self->rect.x = nb::cast<int>(t[0]);
                self->rect.y = nb::cast<int>(t[1]);
                self->rect.width = nb::cast<int>(t[2]);
                self->rect.height = nb::cast<int>(t[3]);
            }
            if (kwargs.contains("scene")) {
                nb::object s = nb::borrow<nb::object>(kwargs["scene"]);
                if (!s.is_none()) {
                    // Accept TcSceneRef directly or extract from Scene (inherits TcScene)
                    if (nb::isinstance<TcSceneRef>(s)) {
                        self->scene = nb::cast<TcSceneRef>(s);
                    } else if (nb::hasattr(s, "scene_ref")) {
                        // Scene inherits from TcScene, has scene_ref method directly
                        self->scene = nb::cast<TcSceneRef>(s.attr("scene_ref")());
                    }
                }
            }
            if (kwargs.contains("camera")) {
                nb::object c = nb::borrow<nb::object>(kwargs["camera"]);
                if (!c.is_none()) {
                    self->camera = nb::cast<CameraComponent*>(c);
                }
            }
            if (kwargs.contains("viewport")) {
                nb::object v = nb::borrow<nb::object>(kwargs["viewport"]);
                if (!v.is_none() && nb::hasattr(v, "_viewport_handle")) {
                    auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(v.attr("_viewport_handle")());
                    self->viewport.index = std::get<0>(h);
                    self->viewport.generation = std::get<1>(h);
                }
            }
            if (kwargs.contains("lights")) {
                nb::object l = nb::borrow<nb::object>(kwargs["lights"]);
                if (!l.is_none()) {
                    self->lights = nb::cast<std::vector<Light>>(l);
                }
            }
            if (kwargs.contains("layer_mask")) {
                self->layer_mask = nb::cast<uint64_t>(kwargs["layer_mask"]);
            }
        })
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
        .def_rw("scene", &ExecuteContext::scene)
        .def_prop_rw("camera",
            [](const ExecuteContext& ctx) { return ctx.camera; },
            [](ExecuteContext& ctx, CameraComponent* c) { ctx.camera = c; },
            nb::rv_policy::reference)
        .def_prop_rw("viewport",
            [](const ExecuteContext& ctx) -> TcViewportRef {
                return TcViewportRef(ctx.viewport);
            },
            [](ExecuteContext& ctx, TcViewportRef& vp) {
                ctx.viewport = vp.handle();
            })
        .def_rw("lights", &ExecuteContext::lights)
        .def_rw("layer_mask", &ExecuteContext::layer_mask);

    // CxxFramePass - base class for C++ frame passes (exposed as "FramePass" for compatibility)
    nb::class_<CxxFramePass>(m, "FramePass")
        .def(nb::init<>())
        .def_prop_rw("pass_name",
            [](CxxFramePass& p) { return p.get_pass_name(); },
            [](CxxFramePass& p, const std::string& n) { p.set_pass_name(n); })
        .def("compute_reads", [](CxxFramePass& p) {
            auto reads = p.compute_reads();
            std::set<std::string> result;
            for (const char* r : reads) {
                if (r) result.insert(r);
            }
            return result;
        })
        .def("compute_writes", [](CxxFramePass& p) {
            auto writes = p.compute_writes();
            std::set<std::string> result;
            for (const char* w : writes) {
                if (w) result.insert(w);
            }
            return result;
        })
        .def_prop_rw("enabled",
            [](CxxFramePass& p) { return p.get_enabled(); },
            [](CxxFramePass& p, bool v) { p.set_enabled(v); })
        .def_prop_rw("passthrough",
            [](CxxFramePass& p) { return p._c.passthrough; },
            [](CxxFramePass& p, bool v) { p._c.passthrough = v; })
        .def_prop_rw("viewport_name",
            [](CxxFramePass& p) { return p.get_viewport_name(); },
            [](CxxFramePass& p, const std::string& n) { p.set_viewport_name(n); })
        .def("get_inplace_aliases", &CxxFramePass::get_inplace_aliases)
        .def("is_inplace", &CxxFramePass::is_inplace)
        .def_prop_ro("inplace", &CxxFramePass::is_inplace)
        .def("get_internal_symbols", &CxxFramePass::get_internal_symbols)
        .def("get_internal_symbols_with_timing", &CxxFramePass::get_internal_symbols_with_timing)
        .def("get_resource_specs", &CxxFramePass::get_resource_specs)
        .def("set_debug_internal_point", &CxxFramePass::set_debug_internal_point)
        .def("clear_debug_internal_point", &CxxFramePass::clear_debug_internal_point)
        .def("get_debug_internal_point", &CxxFramePass::get_debug_internal_point)
        .def("required_resources", &CxxFramePass::required_resources)
        .def("destroy", &CxxFramePass::destroy)
        // Debug capture
        .def("set_debug_capture", &CxxFramePass::set_debug_capture, nb::arg("capture"))
        .def("clear_debug_capture", &CxxFramePass::clear_debug_capture)
        .def("get_debug_capture", &CxxFramePass::debug_capture, nb::rv_policy::reference)
        // Debugger integration
        .def("set_debugger_window", [](CxxFramePass& self, nb::object window,
                                       nb::object depth_callback, nb::object error_callback) {
            setup_py_debugger(&self, window, depth_callback, error_callback);
        }, nb::arg("window") = nb::none(), nb::arg("depth_callback") = nb::none(), nb::arg("error_callback") = nb::none())
        .def("get_debugger_window", [](CxxFramePass& self) {
            return get_py_debugger_window(&self);
        })
        .def_prop_rw("debugger_window",
            [](CxxFramePass& self) { return get_py_debugger_window(&self); },
            [](CxxFramePass& self, nb::object val) {
                setup_py_debugger(&self, val, nb::none(), nb::none());
            })
        // Expose TcPassRef for frame graph integration
        .def_prop_ro("_tc_pass",
            [](CxxFramePass& p) {
                return TcPassRef(p.tc_pass_ptr());
            })
        .def("_set_py_wrapper", [](CxxFramePass& p, nb::object py_self) {
            p.set_python_ref(py_self.ptr(), &g_py_cxx_pass_ref_vtable);
            Py_INCREF(py_self.ptr());
        }, nb::arg("py_self"))
        .def("__repr__", [](const CxxFramePass& p) {
            return "<CxxFramePass '" + p.get_pass_name() + "'>";
        })
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            auto* pass = new CxxFramePass();
            if (data.contains("pass_name")) {
                pass->set_pass_name(nb::cast<std::string>(data["pass_name"]));
            }
            return init_pass_from_deserialize(pass, "CxxFramePass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none());

    // RenderContext binding
    nb::class_<RenderContext>(m, "RenderContext")
        .def(nb::init<>())
        // Constructor with keyword arguments
        .def("__init__", [](RenderContext* self, nb::kwargs kwargs) {
            new (self) RenderContext();

            if (kwargs.contains("phase")) {
                self->phase = nb::cast<std::string>(kwargs["phase"]);
            }
            if (kwargs.contains("scene")) {
                nb::object s = nb::borrow<nb::object>(kwargs["scene"]);
                if (!s.is_none()) {
                    if (nb::isinstance<TcSceneRef>(s)) {
                        self->scene = nb::cast<TcSceneRef>(s);
                    } else if (nb::hasattr(s, "scene_ref")) {
                        // Scene inherits from TcScene, has scene_ref method directly
                        self->scene = nb::cast<TcSceneRef>(s.attr("scene_ref")());
                    }
                }
            }
            if (kwargs.contains("layer_mask")) {
                self->layer_mask = nb::cast<uint64_t>(kwargs["layer_mask"]);
            }
            if (kwargs.contains("camera")) {
                nb::object c = nb::borrow<nb::object>(kwargs["camera"]);
                if (!c.is_none()) {
                    self->camera = nb::cast<CameraComponent*>(c);
                }
            }
            if (kwargs.contains("graphics")) {
                nb::object g_obj = nb::borrow<nb::object>(kwargs["graphics"]);
                if (!g_obj.is_none()) {
                    self->graphics = nb::cast<GraphicsBackend*>(g_obj);
                }
            }
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
        .def_rw("layer_mask", &RenderContext::layer_mask)
        .def_prop_rw("camera",
            [](const RenderContext& self) -> CameraComponent* { return self.camera; },
            [](RenderContext& self, CameraComponent* c) { self.camera = c; },
            nb::rv_policy::reference)
        .def_prop_rw("graphics",
            [](const RenderContext& self) -> GraphicsBackend* { return self.graphics; },
            [](RenderContext& self, GraphicsBackend* g) { self.graphics = g; },
            nb::rv_policy::reference)
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

    // ColorPass - main color rendering pass
    auto color_pass = nb::class_<ColorPass, CxxFramePass>(m, "ColorPass")
        .def("__init__", [](ColorPass* self,
                            std::string input_res, std::string output_res,
                            nb::object shadow_res_obj, std::string phase_mark,
                            std::string pass_name, std::string sort_mode, bool clear_depth,
                            std::string camera_name) {
            // Convert None to empty string for shadow_res
            std::string shadow_res = "shadow_maps";
            if (!shadow_res_obj.is_none()) {
                shadow_res = nb::cast<std::string>(shadow_res_obj);
            } else {
                shadow_res = "";  // None means no shadows
            }
            new (self) ColorPass(input_res, output_res, shadow_res, phase_mark, pass_name, sort_mode, clear_depth, camera_name);
            init_pass_from_python(self, "ColorPass");
        },
             nb::arg("input_res") = "empty",
             nb::arg("output_res") = "color",
             nb::arg("shadow_res").none() = nb::none(),
             nb::arg("phase_mark") = "opaque",
             nb::arg("pass_name") = "Color",
             nb::arg("sort_mode") = "none",
             nb::arg("clear_depth") = false,
             nb::arg("camera_name") = "")
        .def_rw("input_res", &ColorPass::input_res)
        .def_rw("output_res", &ColorPass::output_res)
        .def_rw("shadow_res", &ColorPass::shadow_res)
        .def_rw("phase_mark", &ColorPass::phase_mark)
        .def_rw("sort_mode", &ColorPass::sort_mode)
        .def_rw("clear_depth", &ColorPass::clear_depth)
        .def_rw("wireframe", &ColorPass::wireframe)
        .def_rw("camera_name", &ColorPass::camera_name)
        .def_rw("extra_textures", &ColorPass::extra_textures)
        .def("add_extra_texture", &ColorPass::add_extra_texture,
             nb::arg("uniform_name"), nb::arg("resource_name"))
        .def("compute_reads", &ColorPass::compute_reads)
        .def("compute_writes", &ColorPass::compute_writes)
        .def("get_inplace_aliases", &ColorPass::get_inplace_aliases)
        .def("get_resource_specs", &ColorPass::get_resource_specs)
        .def("get_internal_symbols", &ColorPass::get_internal_symbols)
        .def("get_internal_symbols_with_timing", &ColorPass::get_internal_symbols_with_timing)
        .def_prop_ro("reads", &ColorPass::compute_reads)
        .def_prop_ro("writes", &ColorPass::compute_writes)
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

            // Get tc_scene_handle from Python Scene object (Scene inherits TcScene)
            tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "scene_handle")) {
                auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene_py.attr("scene_handle")());
                scene.index = std::get<0>(h);
                scene.generation = std::get<1>(h);
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
        .def("destroy", &ColorPass::destroy)
        .def("__repr__", [](const ColorPass& p) {
            return "<ColorPass '" + p.get_pass_name() + "' phase='" + p.phase_mark + "'>";
        })
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = data.contains("pass_name") ? nb::cast<std::string>(data["pass_name"]) : "unnamed";
            auto* p = new ColorPass();
            p->set_pass_name(pass_name);
            return init_pass_from_deserialize(p, "ColorPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none());

    // Node graph attributes for ColorPass
    color_pass.attr("category") = "Render";
    color_pass.attr("has_dynamic_inputs") = true;
    color_pass.attr("node_inputs") = nb::make_tuple(
        nb::make_tuple("input_res", "fbo"),
        nb::make_tuple("shadow_res", "shadow")
    );
    color_pass.attr("node_outputs") = nb::make_tuple(
        nb::make_tuple("output_res", "fbo")
    );
    color_pass.attr("node_inplace_pairs") = nb::make_tuple(
        nb::make_tuple("input_res", "output_res")
    );
    // Node parameter visibility conditions
    {
        nb::dict visibility;
        nb::dict camera_cond;
        camera_cond["_outside_viewport"] = true;
        visibility["camera_name"] = camera_cond;
        color_pass.attr("node_param_visibility") = visibility;
    }

    // DepthPass - linear depth rendering pass
    nb::class_<DepthPass, CxxFramePass>(m, "DepthPass")
        .def("__init__", [](DepthPass* self, const std::string& input_res,
                            const std::string& output_res, const std::string& pass_name) {
            new (self) DepthPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "DepthPass");
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

            // Get tc_scene_handle from Python Scene object (Scene inherits TcScene)
            tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "scene_handle")) {
                auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene_py.attr("scene_handle")());
                scene.index = std::get<0>(h);
                scene.generation = std::get<1>(h);
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
        .def_rw("camera_name", &DepthPass::camera_name)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = "Depth";
            std::string camera_name = "";
            std::string input_res = "empty_depth";
            std::string output_res = "depth";
            if (data.contains("pass_name")) {
                pass_name = nb::cast<std::string>(data["pass_name"]);
            }
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("camera_name")) {
                    camera_name = nb::cast<std::string>(d["camera_name"]);
                }
                if (d.contains("input_res")) {
                    input_res = nb::cast<std::string>(d["input_res"]);
                }
                if (d.contains("output_res")) {
                    output_res = nb::cast<std::string>(d["output_res"]);
                }
            }
            auto* p = new DepthPass(input_res, output_res, pass_name);
            p->camera_name = camera_name;
            return init_pass_from_deserialize(p, "DepthPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &DepthPass::compute_reads)
        .def_prop_ro("writes", &DepthPass::compute_writes)
        .def("destroy", &DepthPass::destroy)
        .def("__repr__", [](const DepthPass& p) {
            return "<DepthPass '" + p.get_pass_name() + "'>";
        });

    // Node graph attributes for DepthPass
    {
        nb::dict visibility;
        nb::dict camera_cond;
        camera_cond["_outside_viewport"] = true;
        visibility["camera_name"] = camera_cond;
        m.attr("DepthPass").attr("node_param_visibility") = visibility;
        m.attr("DepthPass").attr("category") = "Render";
        m.attr("DepthPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("DepthPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("DepthPass").attr("node_inplace_pairs") = nb::make_tuple(
            nb::make_tuple("input_res", "output_res")
        );
    }

    // NormalPass - world-space normal rendering pass
    nb::class_<NormalPass, CxxFramePass>(m, "NormalPass")
        .def("__init__", [](NormalPass* self, const std::string& input_res,
                            const std::string& output_res, const std::string& pass_name) {
            new (self) NormalPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "NormalPass");
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

            // Get tc_scene_handle from Python Scene object (Scene inherits TcScene)
            tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "scene_handle")) {
                auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene_py.attr("scene_handle")());
                scene.index = std::get<0>(h);
                scene.generation = std::get<1>(h);
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
        .def_rw("camera_name", &NormalPass::camera_name)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = "Normal";
            std::string camera_name = "";
            std::string input_res = "empty_normal";
            std::string output_res = "normal";
            if (data.contains("pass_name")) {
                pass_name = nb::cast<std::string>(data["pass_name"]);
            }
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("camera_name")) {
                    camera_name = nb::cast<std::string>(d["camera_name"]);
                }
                if (d.contains("input_res")) {
                    input_res = nb::cast<std::string>(d["input_res"]);
                }
                if (d.contains("output_res")) {
                    output_res = nb::cast<std::string>(d["output_res"]);
                }
            }
            auto* p = new NormalPass(input_res, output_res, pass_name);
            p->camera_name = camera_name;
            return init_pass_from_deserialize(p, "NormalPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &NormalPass::compute_reads)
        .def_prop_ro("writes", &NormalPass::compute_writes)
        .def("destroy", &NormalPass::destroy)
        .def("__repr__", [](const NormalPass& p) {
            return "<NormalPass '" + p.get_pass_name() + "'>";
        });

    // Node graph attributes for NormalPass
    {
        nb::dict visibility;
        nb::dict camera_cond;
        camera_cond["_outside_viewport"] = true;
        visibility["camera_name"] = camera_cond;
        m.attr("NormalPass").attr("node_param_visibility") = visibility;
        m.attr("NormalPass").attr("category") = "Render";
        m.attr("NormalPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("NormalPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("NormalPass").attr("node_inplace_pairs") = nb::make_tuple(
            nb::make_tuple("input_res", "output_res")
        );
    }

    // IdPass - entity ID rendering pass for picking
    nb::class_<IdPass, CxxFramePass>(m, "IdPass")
        .def("__init__", [](IdPass* self, const std::string& input_res,
                            const std::string& output_res, const std::string& pass_name) {
            new (self) IdPass(input_res, output_res, pass_name);
            init_pass_from_python(self, "IdPass");
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

            // Get tc_scene_handle from Python Scene object (Scene inherits TcScene)
            tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "scene_handle")) {
                auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene_py.attr("scene_handle")());
                scene.index = std::get<0>(h);
                scene.generation = std::get<1>(h);
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
        .def_rw("camera_name", &IdPass::camera_name)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = "IdPass";
            std::string camera_name = "";
            std::string input_res = "empty";
            std::string output_res = "id";
            if (data.contains("pass_name")) {
                pass_name = nb::cast<std::string>(data["pass_name"]);
            }
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("camera_name")) {
                    camera_name = nb::cast<std::string>(d["camera_name"]);
                }
                if (d.contains("input_res")) {
                    input_res = nb::cast<std::string>(d["input_res"]);
                }
                if (d.contains("output_res")) {
                    output_res = nb::cast<std::string>(d["output_res"]);
                }
            }
            auto* p = new IdPass(input_res, output_res, pass_name);
            p->camera_name = camera_name;
            return init_pass_from_deserialize(p, "IdPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &IdPass::compute_reads)
        .def_prop_ro("writes", &IdPass::compute_writes)
        .def("destroy", &IdPass::destroy)
        .def("__repr__", [](const IdPass& p) {
            return "<IdPass '" + p.get_pass_name() + "'>";
        });

    // Node graph attributes for IdPass
    {
        nb::dict visibility;
        nb::dict camera_cond;
        camera_cond["_outside_viewport"] = true;
        visibility["camera_name"] = camera_cond;
        m.attr("IdPass").attr("node_param_visibility") = visibility;
        m.attr("IdPass").attr("category") = "ID/Picking";
        m.attr("IdPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("IdPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("IdPass").attr("node_inplace_pairs") = nb::make_tuple(
            nb::make_tuple("input_res", "output_res")
        );
    }

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
    nb::class_<ShadowPass, CxxFramePass>(m, "ShadowPass")
        .def("__init__", [](ShadowPass* self, const std::string& output_res,
                            const std::string& pass_name, float caster_offset) {
            new (self) ShadowPass(output_res, pass_name, caster_offset);
            init_pass_from_python(self, "ShadowPass");
        },
             nb::arg("output_res") = "shadow_maps",
             nb::arg("pass_name") = "Shadow",
             nb::arg("caster_offset") = 50.0f)
        .def_rw("output_res", &ShadowPass::output_res)
        .def_rw("caster_offset", &ShadowPass::caster_offset)
        // Inherit set_debugger_window (nanobind doesn't auto-inherit lambda methods)
        .def("set_debugger_window", [](ShadowPass& self, nb::object window,
                                       nb::object depth_callback, nb::object error_callback) {
            setup_py_debugger(&self, window, depth_callback, error_callback);
        }, nb::arg("window") = nb::none(), nb::arg("depth_callback") = nb::none(), nb::arg("error_callback") = nb::none())
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
            // Get tc_scene_handle from Python Scene object (Scene inherits TcScene)
            tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
            if (!scene_py.is_none() && nb::hasattr(scene_py, "scene_handle")) {
                auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene_py.attr("scene_handle")());
                scene.index = std::get<0>(h);
                scene.generation = std::get<1>(h);
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
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = "Shadow";
            std::string output_res = "shadow_maps";
            float caster_offset = 50.0f;
            if (data.contains("pass_name")) {
                pass_name = nb::cast<std::string>(data["pass_name"]);
            }
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("output_res")) {
                    output_res = nb::cast<std::string>(d["output_res"]);
                }
                if (d.contains("caster_offset")) {
                    caster_offset = nb::cast<float>(d["caster_offset"]);
                }
            }
            auto* p = new ShadowPass(output_res, pass_name, caster_offset);
            return init_pass_from_deserialize(p, "ShadowPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def_prop_ro("reads", &ShadowPass::compute_reads)
        .def_prop_ro("writes", &ShadowPass::compute_writes)
        .def("destroy", &ShadowPass::destroy)
        .def("__repr__", [](const ShadowPass& p) {
            return "<ShadowPass '" + p.get_pass_name() + "'>";
        });

    // Node graph attributes for ShadowPass
    {
        m.attr("ShadowPass").attr("category") = "Render";
        m.attr("ShadowPass").attr("node_inputs") = nb::make_tuple();
        m.attr("ShadowPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "shadow")
        );
    }

    // ColliderGizmoPass - renders collider wireframes for editor visualization
    nb::class_<ColliderGizmoPass, CxxFramePass>(m, "ColliderGizmoPass")
        .def("__init__", [](ColliderGizmoPass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name,
                            bool depth_test) {
            new (self) ColliderGizmoPass(input_res, output_res, pass_name, depth_test);
            init_pass_from_python(self, "ColliderGizmoPass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "ColliderGizmo",
             nb::arg("depth_test") = false)
        .def_rw("input_res", &ColliderGizmoPass::input_res)
        .def_rw("output_res", &ColliderGizmoPass::output_res)
        .def_rw("depth_test", &ColliderGizmoPass::depth_test)
        .def("compute_reads", &ColliderGizmoPass::compute_reads)
        .def("compute_writes", &ColliderGizmoPass::compute_writes)
        .def("get_inplace_aliases", &ColliderGizmoPass::get_inplace_aliases)
        .def_prop_ro("reads", &ColliderGizmoPass::compute_reads)
        .def_prop_ro("writes", &ColliderGizmoPass::compute_writes)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = data.contains("pass_name") ? nb::cast<std::string>(data["pass_name"]) : "ColliderGizmo";
            auto* p = new ColliderGizmoPass();
            p->set_pass_name(pass_name);
            return init_pass_from_deserialize(p, "ColliderGizmoPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def("destroy", &ColliderGizmoPass::destroy)
        .def("__repr__", [](const ColliderGizmoPass& p) {
            return "<ColliderGizmoPass '" + p.get_pass_name() + "'>";
        });

    // Node graph attributes for ColliderGizmoPass
    {
        m.attr("ColliderGizmoPass").attr("category") = "Debug";
        m.attr("ColliderGizmoPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("ColliderGizmoPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("ColliderGizmoPass").attr("node_inplace_pairs") = nb::make_tuple(
            nb::make_tuple("input_res", "output_res")
        );
    }

    // MaterialPass - post-processing pass using a Material
    nb::class_<MaterialPass, CxxFramePass>(m, "MaterialPass")
        .def("__init__", [](MaterialPass* self,
                            const std::string& material_name,
                            const std::string& output_res,
                            const std::string& pass_name) {
            new (self) MaterialPass();
            self->set_pass_name(pass_name);
            self->output_res = output_res;
            if (!material_name.empty() && material_name != "(None)") {
                self->material = TcMaterial::from_name(material_name);
            }
            init_pass_from_python(self, "MaterialPass");
        },
             nb::arg("material_name") = "",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "Material")
        .def_prop_rw("material",
            [](MaterialPass& p) { return p.material; },
            [](MaterialPass& p, const TcMaterial& mat) { p.material = mat; })
        .def_prop_rw("material_name",
            [](MaterialPass& p) { return std::string(p.material.name()); },
            [](MaterialPass& p, const std::string& name) {
                if (!name.empty() && name != "(None)") {
                    p.material = TcMaterial::from_name(name);
                } else {
                    p.material = TcMaterial();
                }
            })
        .def_prop_rw("output_res",
            [](MaterialPass& p) { return p.output_res; },
            [](MaterialPass& p, const std::string& res) { p.output_res = res; })
        .def("set_texture_resource", &MaterialPass::set_texture_resource,
             nb::arg("uniform_name"), nb::arg("resource_name"))
        .def("add_resource", &MaterialPass::add_resource,
             nb::arg("resource_name"), nb::arg("uniform_name") = "")
        .def("remove_resource", &MaterialPass::remove_resource,
             nb::arg("resource_name"))
        .def("add_extra_texture", [](MaterialPass& self,
                                     const std::string& socket_name,
                                     const std::string& resource_name) {
            if (resource_name.empty() || resource_name.rfind("empty_", 0) == 0) {
                return;
            }
            std::string uniform_name = (socket_name.rfind("u_", 0) == 0)
                ? socket_name
                : "u_" + socket_name;
            self.set_texture_resource(uniform_name, resource_name);
        }, nb::arg("socket_name"), nb::arg("resource_name"))
        .def_prop_rw("before_draw",
            [](MaterialPass& p) {
                // Return None if no callback is set
                if (!p.before_draw()) {
                    return nb::none();
                }
                // Can't return C++ lambda to Python
                return nb::none();
            },
            [](MaterialPass& p, nb::object callback) {
                if (callback.is_none()) {
                    p.set_before_draw(nullptr);
                } else {
                    // Wrap Python callback
                    nb::object cb_ref = callback;
                    p.set_before_draw([cb_ref](TcShader* shader) {
                        nb::gil_scoped_acquire gil;
                        try {
                            cb_ref(nb::cast(shader, nb::rv_policy::reference));
                        } catch (const std::exception& e) {
                            tc::Log::error("[MaterialPass] before_draw callback error: %s", e.what());
                        }
                    });
                }
            })
        .def("compute_reads", &MaterialPass::compute_reads)
        .def("compute_writes", &MaterialPass::compute_writes)
        .def_prop_ro("reads", &MaterialPass::compute_reads)
        .def_prop_ro("writes", &MaterialPass::compute_writes)
        .def("destroy", &MaterialPass::destroy)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = data.contains("pass_name") ? nb::cast<std::string>(data["pass_name"]) : "Material";
            std::string output_res = data.contains("output_res") ? nb::cast<std::string>(data["output_res"]) : "color";
            std::string material_name = "";
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                // Support both "material" and legacy "material_name"
                if (d.contains("material")) {
                    material_name = nb::cast<std::string>(d["material"]);
                } else if (d.contains("material_name")) {
                    material_name = nb::cast<std::string>(d["material_name"]);
                }
            }
            auto* p = new MaterialPass();
            p->set_pass_name(pass_name);
            p->output_res = output_res;
            if (!material_name.empty() && material_name != "(None)") {
                p->material = TcMaterial::from_name(material_name);
            }
            // Restore texture_resources
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("texture_resources")) {
                    nb::dict tex_res = nb::cast<nb::dict>(d["texture_resources"]);
                    for (auto item : tex_res) {
                        std::string uniform_name = nb::cast<std::string>(item.first);
                        std::string resource_name = nb::cast<std::string>(item.second);
                        p->set_texture_resource(uniform_name, resource_name);
                    }
                }
                if (d.contains("extra_resources")) {
                    nb::dict extra_res = nb::cast<nb::dict>(d["extra_resources"]);
                    for (auto item : extra_res) {
                        std::string resource_name = nb::cast<std::string>(item.first);
                        std::string uniform_name = nb::cast<std::string>(item.second);
                        p->add_resource(resource_name, uniform_name);
                    }
                }
            }
            return init_pass_from_deserialize(p, "MaterialPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def("__repr__", [](const MaterialPass& p) {
            return "<MaterialPass '" + p.get_pass_name() + "' material='" + std::string(p.material.name()) + "'>";
        });

    // Node graph attributes for MaterialPass
    {
        m.attr("MaterialPass").attr("category") = "Effects";
        m.attr("MaterialPass").attr("has_dynamic_inputs") = true;
        m.attr("MaterialPass").attr("node_inputs") = nb::make_tuple();
        m.attr("MaterialPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("MaterialPass").attr("node_inplace_pairs") = nb::make_tuple();

        // inspect_fields for editor - uses Python InspectField class
        // Will be set from Python side after import
    }

    // PresentToScreenPass - blit input FBO to output (typically screen)
    nb::class_<PresentToScreenPass, CxxFramePass>(m, "PresentToScreenPass")
        .def("__init__", [](PresentToScreenPass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name) {
            new (self) PresentToScreenPass(input_res, output_res);
            if (!pass_name.empty()) {
                self->set_pass_name(pass_name);
            }
            init_pass_from_python(self, "PresentToScreenPass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "OUTPUT",
             nb::arg("pass_name") = "PresentToScreen")
        .def_rw("input_res", &PresentToScreenPass::input_res)
        .def_rw("output_res", &PresentToScreenPass::output_res)
        .def("compute_reads", &PresentToScreenPass::compute_reads)
        .def("compute_writes", &PresentToScreenPass::compute_writes)
        .def("get_inplace_aliases", &PresentToScreenPass::get_inplace_aliases)
        .def_prop_ro("reads", &PresentToScreenPass::compute_reads)
        .def_prop_ro("writes", &PresentToScreenPass::compute_writes)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = data.contains("pass_name") ? nb::cast<std::string>(data["pass_name"]) : "PresentToScreen";
            std::string input_res = "color";
            std::string output_res = "OUTPUT";
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("input_res")) {
                    input_res = nb::cast<std::string>(d["input_res"]);
                }
                if (d.contains("output_res")) {
                    output_res = nb::cast<std::string>(d["output_res"]);
                }
            }
            auto* p = new PresentToScreenPass(input_res, output_res);
            p->set_pass_name(pass_name);
            return init_pass_from_deserialize(p, "PresentToScreenPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def("destroy", &PresentToScreenPass::destroy)
        .def("__repr__", [](const PresentToScreenPass& p) {
            return "<PresentToScreenPass '" + p.get_pass_name() + "'>";
        });

    // Node graph attributes for PresentToScreenPass
    {
        m.attr("PresentToScreenPass").attr("category") = "Output";
        m.attr("PresentToScreenPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("PresentToScreenPass").attr("node_outputs") = nb::make_tuple();
    }

    // BloomPass - HDR bloom post-processing pass
    nb::class_<BloomPass, CxxFramePass>(m, "BloomPass")
        .def("__init__", [](BloomPass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name,
                            float threshold,
                            float soft_threshold,
                            float intensity,
                            int mip_levels) {
            new (self) BloomPass(input_res, output_res, threshold, soft_threshold, intensity, mip_levels);
            if (!pass_name.empty()) {
                self->set_pass_name(pass_name);
            }
            init_pass_from_python(self, "BloomPass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "Bloom",
             nb::arg("threshold") = 1.0f,
             nb::arg("soft_threshold") = 0.5f,
             nb::arg("intensity") = 1.0f,
             nb::arg("mip_levels") = 5)
        .def_rw("input_res", &BloomPass::input_res)
        .def_rw("output_res", &BloomPass::output_res)
        .def_rw("threshold", &BloomPass::threshold)
        .def_rw("soft_threshold", &BloomPass::soft_threshold)
        .def_rw("intensity", &BloomPass::intensity)
        .def_rw("mip_levels", &BloomPass::mip_levels)
        .def("compute_reads", &BloomPass::compute_reads)
        .def("compute_writes", &BloomPass::compute_writes)
        .def("get_inplace_aliases", &BloomPass::get_inplace_aliases)
        .def_prop_ro("reads", &BloomPass::compute_reads)
        .def_prop_ro("writes", &BloomPass::compute_writes)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = data.contains("pass_name") ? nb::cast<std::string>(data["pass_name"]) : "Bloom";
            std::string input_res = "color";
            std::string output_res = "color";
            float threshold = 1.0f;
            float soft_threshold = 0.5f;
            float intensity = 1.0f;
            int mip_levels = 5;
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("input_res")) {
                    input_res = nb::cast<std::string>(d["input_res"]);
                }
                if (d.contains("output_res")) {
                    output_res = nb::cast<std::string>(d["output_res"]);
                }
                if (d.contains("threshold")) {
                    threshold = nb::cast<float>(d["threshold"]);
                }
                if (d.contains("soft_threshold")) {
                    soft_threshold = nb::cast<float>(d["soft_threshold"]);
                }
                if (d.contains("intensity")) {
                    intensity = nb::cast<float>(d["intensity"]);
                }
                if (d.contains("mip_levels")) {
                    mip_levels = nb::cast<int>(d["mip_levels"]);
                }
            }
            auto* p = new BloomPass(input_res, output_res, threshold, soft_threshold, intensity, mip_levels);
            p->set_pass_name(pass_name);
            return init_pass_from_deserialize(p, "BloomPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def("destroy", &BloomPass::destroy)
        .def("__repr__", [](const BloomPass& p) {
            return "<BloomPass '" + p.get_pass_name() + "'>";
        });

    // Node graph attributes for BloomPass
    {
        m.attr("BloomPass").attr("category") = "Effects";
        m.attr("BloomPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("BloomPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("BloomPass").attr("node_inplace_pairs") = nb::make_tuple();
    }

    // GrayscalePass - simple grayscale post-processing pass
    nb::class_<GrayscalePass, CxxFramePass>(m, "GrayscalePass")
        .def("__init__", [](GrayscalePass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name,
                            float strength) {
            new (self) GrayscalePass(input_res, output_res, strength);
            if (!pass_name.empty()) {
                self->set_pass_name(pass_name);
            }
            init_pass_from_python(self, "GrayscalePass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "Grayscale",
             nb::arg("strength") = 1.0f)
        .def_rw("input_res", &GrayscalePass::input_res)
        .def_rw("output_res", &GrayscalePass::output_res)
        .def_rw("strength", &GrayscalePass::strength)
        .def("compute_reads", &GrayscalePass::compute_reads)
        .def("compute_writes", &GrayscalePass::compute_writes)
        .def("get_inplace_aliases", &GrayscalePass::get_inplace_aliases)
        .def_prop_ro("reads", &GrayscalePass::compute_reads)
        .def_prop_ro("writes", &GrayscalePass::compute_writes)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = data.contains("pass_name") ? nb::cast<std::string>(data["pass_name"]) : "Grayscale";
            std::string input_res = "color";
            std::string output_res = "color";
            float strength = 1.0f;
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("input_res")) {
                    input_res = nb::cast<std::string>(d["input_res"]);
                }
                if (d.contains("output_res")) {
                    output_res = nb::cast<std::string>(d["output_res"]);
                }
                if (d.contains("strength")) {
                    strength = nb::cast<float>(d["strength"]);
                }
            }
            auto* p = new GrayscalePass(input_res, output_res, strength);
            p->set_pass_name(pass_name);
            return init_pass_from_deserialize(p, "GrayscalePass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def("destroy", &GrayscalePass::destroy)
        .def("__repr__", [](const GrayscalePass& p) {
            return "<GrayscalePass '" + p.get_pass_name() + "'>";
        });

    // Node graph attributes for GrayscalePass
    {
        m.attr("GrayscalePass").attr("category") = "Effects";
        m.attr("GrayscalePass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("GrayscalePass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("GrayscalePass").attr("node_inplace_pairs") = nb::make_tuple();
    }

    // TonemapPass - HDR to LDR tonemapping pass
    nb::class_<TonemapPass, CxxFramePass>(m, "TonemapPass")
        .def("__init__", [](TonemapPass* self,
                            const std::string& input_res,
                            const std::string& output_res,
                            const std::string& pass_name,
                            float exposure,
                            int method) {
            new (self) TonemapPass(input_res, output_res, exposure, method);
            if (!pass_name.empty()) {
                self->set_pass_name(pass_name);
            }
            init_pass_from_python(self, "TonemapPass");
        },
             nb::arg("input_res") = "color",
             nb::arg("output_res") = "color",
             nb::arg("pass_name") = "Tonemap",
             nb::arg("exposure") = 1.0f,
             nb::arg("method") = 0)
        .def_rw("input_res", &TonemapPass::input_res)
        .def_rw("output_res", &TonemapPass::output_res)
        .def_rw("exposure", &TonemapPass::exposure)
        .def_rw("method", &TonemapPass::method)
        .def("compute_reads", &TonemapPass::compute_reads)
        .def("compute_writes", &TonemapPass::compute_writes)
        .def("get_inplace_aliases", &TonemapPass::get_inplace_aliases)
        .def_prop_ro("reads", &TonemapPass::compute_reads)
        .def_prop_ro("writes", &TonemapPass::compute_writes)
        .def_static("_deserialize_instance", [](nb::dict data, nb::object resource_manager) {
            std::string pass_name = data.contains("pass_name") ? nb::cast<std::string>(data["pass_name"]) : "Tonemap";
            std::string input_res = "color";
            std::string output_res = "color";
            float exposure = 1.0f;
            int method = 0;
            if (data.contains("data")) {
                nb::dict d = nb::cast<nb::dict>(data["data"]);
                if (d.contains("input_res")) {
                    input_res = nb::cast<std::string>(d["input_res"]);
                }
                if (d.contains("output_res")) {
                    output_res = nb::cast<std::string>(d["output_res"]);
                }
                if (d.contains("exposure")) {
                    exposure = nb::cast<float>(d["exposure"]);
                }
                if (d.contains("method")) {
                    method = nb::cast<int>(d["method"]);
                }
            }
            auto* p = new TonemapPass(input_res, output_res, exposure, method);
            p->set_pass_name(pass_name);
            return init_pass_from_deserialize(p, "TonemapPass");
        }, nb::arg("data"), nb::arg("resource_manager") = nb::none())
        .def("destroy", &TonemapPass::destroy)
        .def("__repr__", [](const TonemapPass& p) {
            return "<TonemapPass '" + p.get_pass_name() + "'>";
        });

    // Node graph attributes for TonemapPass
    {
        m.attr("TonemapPass").attr("category") = "Effects";
        m.attr("TonemapPass").attr("node_inputs") = nb::make_tuple(
            nb::make_tuple("input_res", "fbo")
        );
        m.attr("TonemapPass").attr("node_outputs") = nb::make_tuple(
            nb::make_tuple("output_res", "fbo")
        );
        m.attr("TonemapPass").attr("node_inplace_pairs") = nb::make_tuple();
    }

    // TonemapMethod enum constants
    m.attr("TONEMAP_ACES") = 0;
    m.attr("TONEMAP_REINHARD") = 1;
    m.attr("TONEMAP_NONE") = 2;
}

} // namespace termin
