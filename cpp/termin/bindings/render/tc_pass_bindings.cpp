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
#include "tc_log.h"
}

namespace termin {

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
        py_ctx["context_key"] = ctx->context_key;
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
    Py_INCREF(static_cast<PyObject*>(wrapper));
}

static void py_pass_decref(void* wrapper) {
    nb::gil_scoped_acquire gil;
    Py_DECREF(static_cast<PyObject*>(wrapper));
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

    // tc_pass as opaque handle - struct is fully defined in header
    nb::class_<tc_pass>(m, "TcPass")
        .def_prop_ro("pass_name", [](tc_pass* p) {
            return p->pass_name ? std::string(p->pass_name) : std::string();
        })
        .def_prop_rw("enabled",
            [](tc_pass* p) { return p->enabled; },
            [](tc_pass* p, bool v) { p->enabled = v; })
        .def_prop_rw("passthrough",
            [](tc_pass* p) { return p->passthrough; },
            [](tc_pass* p, bool v) { p->passthrough = v; })
        .def_prop_ro("type_name", [](tc_pass* p) {
            return std::string(tc_pass_type_name(p));
        })
        .def("is_inplace", [](tc_pass* p) {
            return tc_pass_is_inplace(p);
        });

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

    m.def("tc_pipeline_add_pass", [](tc_pipeline* p, tc_pass* pass) {
        tc_pipeline_add_pass(p, pass);
    });

    m.def("tc_pipeline_get_pass", [](tc_pipeline* p, const std::string& name) {
        return tc_pipeline_get_pass(p, name.c_str());
    }, nb::rv_policy::reference);

    m.def("tc_pipeline_get_pass_at", [](tc_pipeline* p, size_t index) {
        return tc_pipeline_get_pass_at(p, index);
    }, nb::rv_policy::reference);

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
        return tc_frame_graph_schedule_at(reinterpret_cast<tc_frame_graph*>(fg_ptr), index);
    }, nb::rv_policy::reference);

    m.def("tc_frame_graph_get_schedule", [](intptr_t fg_ptr) {
        tc_frame_graph* fg = reinterpret_cast<tc_frame_graph*>(fg_ptr);
        nb::list result;
        size_t count = tc_frame_graph_schedule_count(fg);
        for (size_t i = 0; i < count; i++) {
            tc_pass* p = tc_frame_graph_schedule_at(fg, i);
            result.append(nb::cast(p, nb::rv_policy::reference));
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

    // External pass creation
    m.def("tc_pass_new_external", [](nb::object py_pass, const std::string& type_name) {
        ensure_py_callbacks_registered();

        // Increment refcount since C code will hold a reference
        Py_INCREF(py_pass.ptr());

        tc_pass* p = tc_pass_new_external(py_pass.ptr(), type_name.c_str());
        return p;
    }, nb::arg("wrapper"), nb::arg("type_name"), nb::rv_policy::reference);

    m.def("tc_pass_free_external", [](tc_pass* p) {
        if (p && p->wrapper) {
            nb::gil_scoped_acquire gil;
            Py_DECREF(static_cast<PyObject*>(p->wrapper));
        }
        tc_pass_free_external(p);
    });

    // Execute a pass with context
    m.def("tc_pass_execute", [](tc_pass* p, nb::dict ctx_dict) {
        tc_execute_context ctx = {};
        if (ctx_dict.contains("rect_x")) ctx.rect_x = nb::cast<int>(ctx_dict["rect_x"]);
        if (ctx_dict.contains("rect_y")) ctx.rect_y = nb::cast<int>(ctx_dict["rect_y"]);
        if (ctx_dict.contains("rect_width")) ctx.rect_width = nb::cast<int>(ctx_dict["rect_width"]);
        if (ctx_dict.contains("rect_height")) ctx.rect_height = nb::cast<int>(ctx_dict["rect_height"]);
        if (ctx_dict.contains("context_key")) ctx.context_key = nb::cast<int64_t>(ctx_dict["context_key"]);
        if (ctx_dict.contains("layer_mask")) ctx.layer_mask = nb::cast<uint64_t>(ctx_dict["layer_mask"]);

        tc_pass_execute(p, &ctx);
    });

    // Pass set_pass_name helper
    m.def("tc_pass_set_name", [](tc_pass* p, const std::string& name) {
        if (p->pass_name) free(p->pass_name);
        p->pass_name = strdup(name.c_str());
    });
}

} // namespace termin
