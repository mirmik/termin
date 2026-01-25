// tc_pass_bindings.cpp - nanobind bindings for tc_pass, tc_pipeline, tc_frame_graph
#include "common.hpp"
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/set.h>
#include <cstring>

extern "C" {
#include "tc_pass.h"
#include "tc_pipeline.h"
#include "tc_frame_graph.h"
#include "tc_render.h"
#include "tc_log.h"
}

#include "termin/render/frame_pass.hpp"
#include "termin/render/tc_pass.hpp"

namespace termin {

// Convert tc_pass to Python object
// For Python-native passes: returns body directly
// For C++-native passes with externally_managed: returns body (Python wrapper)
// For C++-native passes without wrapper: creates nanobind wrapper
inline nb::object tc_pass_to_python(tc_pass* p) {
    if (!p) {
        return nb::none();
    }

    // Check kind is valid
    if (p->kind != TC_NATIVE_PASS && p->kind != TC_EXTERNAL_PASS) {
        tc_log(TC_LOG_ERROR, "[tc_pass_to_python] Invalid kind=%d for p=%p",
               (int)p->kind, (void*)p);
        return nb::none();
    }

    // External pass (Python) or native pass with Python wrapper - return body directly
    if (p->body && p->externally_managed) {
        return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(p->body));
    }

    // Native pass (C++) without wrapper - use FramePass::from_tc and let nanobind create wrapper
    if (p->kind == TC_NATIVE_PASS) {
        FramePass* fp = FramePass::from_tc(p);
        if (fp) {
            return nb::cast(fp, nb::rv_policy::reference);
        }
    }

    return nb::none();
}

// ============================================================================
// External pass callbacks - dispatch to Python methods
// ============================================================================

static void py_pass_execute(void* wrapper, tc_execute_context* ctx) {
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_pass = nb::borrow<nb::object>(static_cast<PyObject*>(wrapper));

        // Build a simple dict for context
        nb::dict py_ctx;
        py_ctx["rect_x"] = ctx->rect_x;
        py_ctx["rect_y"] = ctx->rect_y;
        py_ctx["rect_width"] = ctx->rect_width;
        py_ctx["rect_height"] = ctx->rect_height;
        py_ctx["layer_mask"] = ctx->layer_mask;

        // Call Python execute method
        if (nb::hasattr(py_pass, "execute")) {
            py_pass.attr("execute")(py_ctx);
        }
    } catch (const std::exception& e) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Python execute failed: %s", e.what());
    }
}

static size_t py_pass_get_reads(void* wrapper, const char** out, size_t max) {
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_pass = nb::borrow<nb::object>(static_cast<PyObject*>(wrapper));

        if (!nb::hasattr(py_pass, "compute_reads")) return 0;

        nb::object reads = py_pass.attr("compute_reads")();
        size_t count = 0;

        // Cache the strings in _cached_tc_reads to avoid dangling pointers
        nb::list cached;
        for (auto item : reads) {
            if (count >= max) break;
            nb::str s = nb::cast<nb::str>(item);
            cached.append(s);
            count++;
        }
        py_pass.attr("_cached_tc_reads") = cached;

        // Now extract c_str pointers
        count = 0;
        for (auto item : cached) {
            if (count >= max) break;
            out[count] = PyUnicode_AsUTF8(item.ptr());
            count++;
        }
        return count;
    } catch (const std::exception& e) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Python get_reads failed: %s", e.what());
        return 0;
    }
}

static size_t py_pass_get_writes(void* wrapper, const char** out, size_t max) {
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_pass = nb::borrow<nb::object>(static_cast<PyObject*>(wrapper));

        if (!nb::hasattr(py_pass, "compute_writes")) return 0;

        nb::object writes = py_pass.attr("compute_writes")();
        size_t count = 0;

        // Cache the strings
        nb::list cached;
        for (auto item : writes) {
            if (count >= max) break;
            nb::str s = nb::cast<nb::str>(item);
            cached.append(s);
            count++;
        }
        py_pass.attr("_cached_tc_writes") = cached;

        count = 0;
        for (auto item : cached) {
            if (count >= max) break;
            out[count] = PyUnicode_AsUTF8(item.ptr());
            count++;
        }
        return count;
    } catch (const std::exception& e) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Python get_writes failed: %s", e.what());
        return 0;
    }
}

static size_t py_pass_get_inplace_aliases(void* wrapper, const char** out, size_t max) {
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_pass = nb::borrow<nb::object>(static_cast<PyObject*>(wrapper));

        if (!nb::hasattr(py_pass, "get_inplace_aliases")) return 0;

        nb::object aliases = py_pass.attr("get_inplace_aliases")();
        size_t pair_count = 0;

        // Cache the strings
        nb::list cached;
        for (auto item : aliases) {
            if (pair_count >= max) break;
            nb::tuple pair = nb::cast<nb::tuple>(item);
            cached.append(pair[0]);
            cached.append(pair[1]);
            pair_count++;
        }
        py_pass.attr("_cached_tc_aliases") = cached;

        // Extract c_str pointers
        size_t i = 0;
        for (auto item : cached) {
            out[i] = PyUnicode_AsUTF8(item.ptr());
            i++;
        }
        return pair_count;
    } catch (const std::exception& e) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Python get_inplace_aliases failed: %s", e.what());
        return 0;
    }
}

static size_t py_pass_get_resource_specs(void* wrapper, tc_resource_spec* out, size_t max) {
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_pass = nb::borrow<nb::object>(static_cast<PyObject*>(wrapper));

        if (!nb::hasattr(py_pass, "get_resource_specs")) return 0;

        nb::object specs = py_pass.attr("get_resource_specs")();
        size_t count = 0;

        // Cache strings to avoid dangling pointers
        nb::list cached_resources;

        for (auto item : specs) {
            if (count >= max) break;

            nb::object spec = nb::borrow<nb::object>(item);
            tc_resource_spec& s = out[count];

            // Get resource name
            nb::str res_name = nb::cast<nb::str>(spec.attr("resource"));
            cached_resources.append(res_name);
            s.resource = PyUnicode_AsUTF8(res_name.ptr());

            // Get dimensions
            if (nb::hasattr(spec, "fixed_width")) {
                s.fixed_width = nb::cast<int>(spec.attr("fixed_width"));
            } else {
                s.fixed_width = 0;
            }
            if (nb::hasattr(spec, "fixed_height")) {
                s.fixed_height = nb::cast<int>(spec.attr("fixed_height"));
            } else {
                s.fixed_height = 0;
            }

            // Get clear values
            s.has_clear_color = false;
            s.has_clear_depth = false;
            if (nb::hasattr(spec, "clear_color") && !spec.attr("clear_color").is_none()) {
                nb::tuple cc = nb::cast<nb::tuple>(spec.attr("clear_color"));
                s.clear_color[0] = nb::cast<float>(cc[0]);
                s.clear_color[1] = nb::cast<float>(cc[1]);
                s.clear_color[2] = nb::cast<float>(cc[2]);
                s.clear_color[3] = nb::cast<float>(cc[3]);
                s.has_clear_color = true;
            }
            if (nb::hasattr(spec, "clear_depth") && !spec.attr("clear_depth").is_none()) {
                s.clear_depth = nb::cast<float>(spec.attr("clear_depth"));
                s.has_clear_depth = true;
            }

            // Get format
            s.format = nullptr;
            if (nb::hasattr(spec, "format") && !spec.attr("format").is_none()) {
                nb::str fmt = nb::cast<nb::str>(spec.attr("format"));
                cached_resources.append(fmt);
                s.format = PyUnicode_AsUTF8(fmt.ptr());
            }

            count++;
        }
        py_pass.attr("_cached_tc_specs") = cached_resources;

        return count;
    } catch (const std::exception& e) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Python get_resource_specs failed: %s", e.what());
        return 0;
    }
}

static size_t py_pass_get_internal_symbols(void* wrapper, const char** out, size_t max) {
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_pass = nb::borrow<nb::object>(static_cast<PyObject*>(wrapper));

        if (!nb::hasattr(py_pass, "get_internal_symbols")) return 0;

        nb::object symbols = py_pass.attr("get_internal_symbols")();
        size_t count = 0;

        nb::list cached;
        for (auto item : symbols) {
            if (count >= max) break;
            nb::str s = nb::cast<nb::str>(item);
            cached.append(s);
            count++;
        }
        py_pass.attr("_cached_tc_symbols") = cached;

        count = 0;
        for (auto item : cached) {
            if (count >= max) break;
            out[count] = PyUnicode_AsUTF8(item.ptr());
            count++;
        }
        return count;
    } catch (const std::exception& e) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Python get_internal_symbols failed: %s", e.what());
        return 0;
    }
}

static void py_pass_destroy(void* wrapper) {
    nb::gil_scoped_acquire gil;
    try {
        nb::object py_pass = nb::borrow<nb::object>(static_cast<PyObject*>(wrapper));
        if (nb::hasattr(py_pass, "destroy")) {
            py_pass.attr("destroy")();
        }
    } catch (const std::exception& e) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Python destroy failed: %s", e.what());
    }
}

static void py_pass_incref(void* wrapper) {
    nb::gil_scoped_acquire gil;
    PyObject* obj = static_cast<PyObject*>(wrapper);
    Py_INCREF(obj);
}

static void py_pass_decref(void* wrapper) {
    nb::gil_scoped_acquire gil;
    PyObject* obj = static_cast<PyObject*>(wrapper);
    Py_DECREF(obj);
}

static tc_external_pass_callbacks g_py_pass_callbacks = {
    .execute = py_pass_execute,
    .get_reads = py_pass_get_reads,
    .get_writes = py_pass_get_writes,
    .get_inplace_aliases = py_pass_get_inplace_aliases,
    .get_resource_specs = py_pass_get_resource_specs,
    .get_internal_symbols = py_pass_get_internal_symbols,
    .destroy = py_pass_destroy,
    .incref = py_pass_incref,
    .decref = py_pass_decref,
};

static bool g_py_callbacks_registered = false;

static void ensure_py_callbacks_registered() {
    if (!g_py_callbacks_registered) {
        tc_pass_set_external_callbacks(&g_py_pass_callbacks);
        g_py_callbacks_registered = true;
    }
}

// ============================================================================
// Bindings
// ============================================================================

void bind_tc_pass(nb::module_& m) {
    // Ensure callbacks are registered when module loads
    ensure_py_callbacks_registered();

    // tc_frame_graph_error enum
    nb::enum_<tc_frame_graph_error>(m, "TcFrameGraphError")
        .value("OK", TC_FG_OK)
        .value("MULTI_WRITER", TC_FG_ERROR_MULTI_WRITER)
        .value("CYCLE", TC_FG_ERROR_CYCLE)
        .value("INVALID_INPLACE", TC_FG_ERROR_INVALID_INPLACE);

    // TcPassRef - non-owning reference
    nb::class_<TcPassRef>(m, "TcPassRef")
        .def(nb::init<>())
        .def("valid", &TcPassRef::valid)
        .def_prop_rw("pass_name", &TcPassRef::pass_name, &TcPassRef::set_pass_name)
        .def_prop_rw("enabled", &TcPassRef::enabled, &TcPassRef::set_enabled)
        .def_prop_rw("passthrough", &TcPassRef::passthrough, &TcPassRef::set_passthrough)
        .def_prop_ro("type_name", &TcPassRef::type_name)
        .def("is_inplace", &TcPassRef::is_inplace)
        .def_prop_ro("body", [](TcPassRef& self) {
            return tc_pass_to_python(self.ptr());
        });

    // TcPass - owning wrapper for Python passes
    nb::class_<TcPass>(m, "TcPass")
        .def("__init__", [](TcPass* self, nb::object py_self, const std::string& type_name) {
            ensure_py_callbacks_registered();
            tc_pass* c = tc_pass_new_external(py_self.ptr(), type_name.c_str());
            new (self) TcPass(c);
        }, nb::arg("py_self"), nb::arg("type_name"))
        .def("ref", &TcPass::ref)
        .def_prop_rw("pass_name", &TcPass::pass_name, &TcPass::set_pass_name)
        .def_prop_rw("enabled", &TcPass::enabled, &TcPass::set_enabled)
        .def_prop_rw("passthrough", &TcPass::passthrough, &TcPass::set_passthrough)
        .def_prop_ro("type_name", &TcPass::type_name)
        .def("is_inplace", &TcPass::is_inplace);

    // tc_pipeline - struct is fully defined in header
    nb::class_<tc_pipeline>(m, "TcPipeline")
        .def_prop_ro("name", [](tc_pipeline* p) {
            return p->name ? std::string(p->name) : std::string();
        })
        .def_prop_ro("pass_count", [](tc_pipeline* p) {
            return p->pass_count;
        });

    // Factory functions for tc_pipeline
    m.def("tc_pipeline_create", [](const std::string& name) {
        return tc_pipeline_create(name.c_str());
    }, nb::arg("name") = "default", nb::rv_policy::reference);

    m.def("tc_pipeline_destroy", [](tc_pipeline* p) {
        tc_pipeline_destroy(p);
    });

    // Pipeline functions work with TcPassRef
    m.def("tc_pipeline_add_pass", [](tc_pipeline* p, TcPassRef pass_ref) {
        if (pass_ref.valid()) {
            tc_pipeline_add_pass(p, pass_ref.ptr());
        }
    });

    // Overload for TcPass (owning)
    m.def("tc_pipeline_add_pass", [](tc_pipeline* p, TcPass* pass) {
        if (pass && pass->ptr()) {
            tc_pipeline_add_pass(p, pass->ptr());
        }
    });

    m.def("tc_pipeline_remove_pass", [](tc_pipeline* p, TcPassRef pass_ref) {
        if (pass_ref.valid()) {
            tc_pipeline_remove_pass(p, pass_ref.ptr());
        }
    });

    m.def("tc_pipeline_remove_pass", [](tc_pipeline* p, TcPass* pass) {
        if (pass && pass->ptr()) {
            tc_pipeline_remove_pass(p, pass->ptr());
        }
    });

    m.def("tc_pipeline_insert_pass_before", [](tc_pipeline* p, TcPassRef pass_ref, TcPassRef before_ref) {
        if (pass_ref.valid()) {
            tc_pipeline_insert_pass_before(p, pass_ref.ptr(), before_ref.ptr());
        }
    });

    m.def("tc_pipeline_insert_pass_before", [](tc_pipeline* p, TcPass* pass, TcPassRef before_ref) {
        if (pass && pass->ptr()) {
            tc_pipeline_insert_pass_before(p, pass->ptr(), before_ref.ptr());
        }
    });

    m.def("tc_pipeline_get_pass", [](tc_pipeline* p, const std::string& name) {
        return TcPassRef(tc_pipeline_get_pass(p, name.c_str()));
    });

    m.def("tc_pipeline_get_pass_at", [](tc_pipeline* p, size_t index) {
        return TcPassRef(tc_pipeline_get_pass_at(p, index));
    });

    // Frame graph - opaque handle via intptr_t
    // tc_frame_graph is defined only in .c file, so we use intptr_t
    m.def("tc_frame_graph_build", [](tc_pipeline* p) -> intptr_t {
        return reinterpret_cast<intptr_t>(tc_frame_graph_build(p));
    });

    m.def("tc_frame_graph_destroy", [](intptr_t fg_ptr) {
        tc_frame_graph_destroy(reinterpret_cast<tc_frame_graph*>(fg_ptr));
    });

    m.def("tc_frame_graph_get_error", [](intptr_t fg_ptr) {
        return tc_frame_graph_get_error(reinterpret_cast<tc_frame_graph*>(fg_ptr));
    });

    m.def("tc_frame_graph_get_error_message", [](intptr_t fg_ptr) {
        const char* msg = tc_frame_graph_get_error_message(reinterpret_cast<tc_frame_graph*>(fg_ptr));
        return msg ? std::string(msg) : std::string();
    });

    m.def("tc_frame_graph_schedule_count", [](intptr_t fg_ptr) {
        return tc_frame_graph_schedule_count(reinterpret_cast<tc_frame_graph*>(fg_ptr));
    });

    m.def("tc_frame_graph_schedule_at", [](intptr_t fg_ptr, size_t index) {
        return TcPassRef(tc_frame_graph_schedule_at(reinterpret_cast<tc_frame_graph*>(fg_ptr), index));
    });

    m.def("tc_frame_graph_get_schedule", [](intptr_t fg_ptr) {
        tc_frame_graph* fg = reinterpret_cast<tc_frame_graph*>(fg_ptr);
        nb::list result;
        size_t count = tc_frame_graph_schedule_count(fg);
        for (size_t i = 0; i < count; i++) {
            tc_pass* p = tc_frame_graph_schedule_at(fg, i);
            result.append(TcPassRef(p));
        }
        return result;
    });

    m.def("tc_frame_graph_canonical_resource", [](intptr_t fg_ptr, const std::string& name) {
        return std::string(tc_frame_graph_canonical_resource(
            reinterpret_cast<tc_frame_graph*>(fg_ptr), name.c_str()));
    });

    m.def("tc_frame_graph_dump", [](intptr_t fg_ptr) {
        tc_frame_graph_dump(reinterpret_cast<tc_frame_graph*>(fg_ptr));
    });

    // Get alias groups as dict: {canonical_name: [alias1, alias2, ...]}
    m.def("tc_frame_graph_get_alias_groups", [](intptr_t fg_ptr) {
        tc_frame_graph* fg = reinterpret_cast<tc_frame_graph*>(fg_ptr);
        nb::dict result;

        // Get all canonical resources
        const char* canonical_names[256];
        size_t canon_count = tc_frame_graph_get_canonical_resources(fg, canonical_names, 256);

        for (size_t i = 0; i < canon_count; i++) {
            const char* canon = canonical_names[i];

            // Get all aliases for this canonical resource
            const char* alias_names[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, alias_names, 64);

            nb::list aliases;
            for (size_t j = 0; j < alias_count; j++) {
                aliases.append(nb::str(alias_names[j]));
            }

            result[nb::str(canon)] = aliases;
        }

        return result;
    });


    // ========================================================================
    // tc_fbo_pool bindings
    // ========================================================================

    // tc_fbo_pool as opaque handle
    m.def("tc_fbo_pool_create", []() -> intptr_t {
        return reinterpret_cast<intptr_t>(tc_fbo_pool_create());
    });

    m.def("tc_fbo_pool_destroy", [](intptr_t pool_ptr) {
        tc_fbo_pool_destroy(reinterpret_cast<tc_fbo_pool*>(pool_ptr));
    });

    // Set FBO for key (stores Python object as void*)
    m.def("tc_fbo_pool_set", [](intptr_t pool_ptr, const std::string& key, nb::object fbo) {
        tc_fbo_pool* pool = reinterpret_cast<tc_fbo_pool*>(pool_ptr);
        // Store Python object pointer (caller must keep fbo alive)
        tc_fbo_pool_set(pool, key.c_str(), fbo.ptr());
    });

    // Get FBO for key (returns Python object or None)
    m.def("tc_fbo_pool_get", [](intptr_t pool_ptr, const std::string& key) -> nb::object {
        tc_fbo_pool* pool = reinterpret_cast<tc_fbo_pool*>(pool_ptr);
        void* fbo = tc_fbo_pool_get(pool, key.c_str());
        if (fbo == nullptr) {
            return nb::none();
        }
        return nb::borrow<nb::object>(static_cast<PyObject*>(fbo));
    });

    m.def("tc_fbo_pool_clear", [](intptr_t pool_ptr) {
        tc_fbo_pool_clear(reinterpret_cast<tc_fbo_pool*>(pool_ptr));
    });

    // ========================================================================
    // tc_resources bindings
    // ========================================================================

    // Allocate resources based on frame graph alias groups
    // Returns dict: {resource_name: fbo_object}
    m.def("tc_resources_allocate_dict", [](
        intptr_t fg_ptr,
        nb::dict specs_dict,
        nb::object target_fbo,
        int width,
        int height
    ) -> nb::dict {
        tc_frame_graph* fg = reinterpret_cast<tc_frame_graph*>(fg_ptr);
        nb::dict result;

        // Get canonical resources
        const char* canonical_names[256];
        size_t canon_count = tc_frame_graph_get_canonical_resources(fg, canonical_names, 256);

        // Set OUTPUT and DISPLAY to target
        result["OUTPUT"] = target_fbo;
        result["DISPLAY"] = target_fbo;

        for (size_t i = 0; i < canon_count; i++) {
            const char* canon = canonical_names[i];

            // Get all aliases for this canonical resource
            const char* alias_names[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, alias_names, 64);

            // Check if DISPLAY or OUTPUT
            bool is_display = (strcmp(canon, "DISPLAY") == 0 || strcmp(canon, "OUTPUT") == 0);
            if (is_display) {
                for (size_t j = 0; j < alias_count; j++) {
                    result[nb::str(alias_names[j])] = target_fbo;
                }
                continue;
            }

            // Look up spec by canonical name or aliases
            nb::object spec = nb::none();
            if (specs_dict.contains(canon)) {
                spec = specs_dict[canon];
            } else {
                for (size_t j = 0; j < alias_count; j++) {
                    if (specs_dict.contains(alias_names[j])) {
                        spec = specs_dict[alias_names[j]];
                        break;
                    }
                }
            }

            // Determine resource type
            std::string resource_type = "fbo";
            if (!spec.is_none() && nb::hasattr(spec, "resource_type")) {
                nb::object rt = spec.attr("resource_type");
                if (!rt.is_none()) {
                    resource_type = nb::cast<std::string>(rt);
                }
            }

            // For non-fbo resources, set canonical name as key with None
            // Python side will handle special resources like shadow_map_array
            if (resource_type != "fbo") {
                for (size_t j = 0; j < alias_count; j++) {
                    result[nb::str(alias_names[j])] = nb::none();
                }
                continue;
            }

            // For fbo resources, set canonical name - Python side will ensure FBO
            // We store the canonical name so Python can create one FBO per group
            nb::dict fbo_info;
            fbo_info["canonical"] = nb::str(canon);
            fbo_info["width"] = width;
            fbo_info["height"] = height;
            fbo_info["samples"] = 1;
            fbo_info["format"] = nb::str("");

            if (!spec.is_none()) {
                if (nb::hasattr(spec, "size") && !spec.attr("size").is_none()) {
                    nb::tuple size = nb::cast<nb::tuple>(spec.attr("size"));
                    fbo_info["width"] = size[0];
                    fbo_info["height"] = size[1];
                }
                if (nb::hasattr(spec, "samples")) {
                    fbo_info["samples"] = spec.attr("samples");
                }
                if (nb::hasattr(spec, "format") && !spec.attr("format").is_none()) {
                    fbo_info["format"] = spec.attr("format");
                }
            }

            // Store info for all aliases
            for (size_t j = 0; j < alias_count; j++) {
                result[nb::str(alias_names[j])] = fbo_info;
            }
        }

        return result;
    });

    // Collect resource specs from pipeline passes
    m.def("tc_pipeline_collect_specs", [](tc_pipeline* pipeline) -> nb::dict {
        nb::dict result;

        tc_resource_spec specs[128];
        size_t count = tc_pipeline_collect_specs(pipeline, specs, 128);

        for (size_t i = 0; i < count; i++) {
            nb::dict spec_dict;
            spec_dict["resource"] = nb::str(specs[i].resource);
            spec_dict["resource_type"] = nb::str(specs[i].resource_type);
            spec_dict["fixed_width"] = specs[i].fixed_width;
            spec_dict["fixed_height"] = specs[i].fixed_height;
            spec_dict["samples"] = specs[i].samples;
            spec_dict["has_clear_color"] = specs[i].has_clear_color;
            spec_dict["has_clear_depth"] = specs[i].has_clear_depth;
            if (specs[i].has_clear_color) {
                spec_dict["clear_color"] = nb::make_tuple(
                    specs[i].clear_color[0],
                    specs[i].clear_color[1],
                    specs[i].clear_color[2],
                    specs[i].clear_color[3]
                );
            }
            if (specs[i].has_clear_depth) {
                spec_dict["clear_depth"] = specs[i].clear_depth;
            }
            if (specs[i].format) {
                spec_dict["format"] = nb::str(specs[i].format);
            }

            result[nb::str(specs[i].resource)] = spec_dict;
        }

        return result;
    });
}

} // namespace termin
