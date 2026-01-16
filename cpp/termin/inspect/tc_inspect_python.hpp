// tc_inspect_python.hpp - Python wrapper for tc_inspect with nanobind
#pragma once

#include "../../../core_c/include/tc_inspect.hpp"
#include <unordered_map>
#include <vector>

namespace tc {

// nb_to_tc_value and tc_value_to_nb are defined in tc_inspect.hpp

// ============================================================================
// Python field context - stores Python getter/setter
// ============================================================================

struct PythonFieldContext {
    nb::object py_getter;  // None or callable
    nb::object py_setter;  // None or callable
    std::string path;      // Field path for getattr/setattr fallback

    PythonFieldContext() = default;
    PythonFieldContext(nb::object g, nb::object s, const std::string& p)
        : py_getter(std::move(g)), py_setter(std::move(s)), path(p) {}
};

// ============================================================================
// Python field getter/setter implementations
// ============================================================================

inline tc_value python_field_getter(void* obj, const tc_field_desc* field, void* user_data) {
    (void)field;
    auto* ctx = static_cast<PythonFieldContext*>(user_data);

    // obj is PyObject* for Python types
    nb::object py_obj = nb::borrow<nb::object>(nb::handle(static_cast<PyObject*>(obj)));

    try {
        if (!ctx->py_getter.is_none()) {
            nb::object result = ctx->py_getter(py_obj);
            return nb_to_tc_value(result);
        }

        // Fallback to getattr
        nb::object result = py_obj;
        std::string path = ctx->path;
        size_t start = 0, end;
        while ((end = path.find('.', start)) != std::string::npos) {
            result = nb::getattr(result, path.substr(start, end - start).c_str());
            start = end + 1;
        }
        result = nb::getattr(result, path.substr(start).c_str());
        return nb_to_tc_value(result);
    } catch (const std::exception& e) {
        // Log error but don't crash
        return tc_value_nil();
    }
}

inline void python_field_setter(void* obj, const tc_field_desc* field, tc_value value, void* user_data, tc_scene* scene) {
    (void)field;
    (void)scene;
    auto* ctx = static_cast<PythonFieldContext*>(user_data);

    nb::object py_obj = nb::borrow<nb::object>(nb::handle(static_cast<PyObject*>(obj)));
    nb::object py_value = tc_value_to_nb(&value);

    try {
        if (!ctx->py_setter.is_none()) {
            ctx->py_setter(py_obj, py_value);
            return;
        }

        // Fallback to setattr
        nb::object target = py_obj;
        std::string path = ctx->path;
        std::vector<std::string> parts;
        size_t start = 0, end;
        while ((end = path.find('.', start)) != std::string::npos) {
            parts.push_back(path.substr(start, end - start));
            start = end + 1;
        }
        parts.push_back(path.substr(start));

        for (size_t i = 0; i < parts.size() - 1; ++i) {
            target = nb::getattr(target, parts[i].c_str());
        }
        nb::setattr(target, parts.back().c_str(), py_value);
    } catch (const std::exception& e) {
        // Log error but don't crash
    }
}

// ============================================================================
// InspectPython - Python field registration
// ============================================================================

class InspectPython {
    // Storage for Python contexts (must outlive registrations)
    static std::unordered_map<std::string, std::vector<PythonFieldContext>>& contexts() {
        static std::unordered_map<std::string, std::vector<PythonFieldContext>> ctx;
        return ctx;
    }

public:
    // Register a type
    static void register_type(const char* type_name, const char* base_type = nullptr) {
        if (!tc_inspect_has_type(type_name)) {
            tc_inspect_register_type(type_name, base_type);
        }
    }

    // Register a Python field
    static void register_field(
        const char* type_name,
        const char* path,
        const char* label,
        const char* kind,
        nb::object py_getter = nb::none(),
        nb::object py_setter = nb::none(),
        double min = 0.0,
        double max = 1.0,
        double step = 0.01,
        bool is_serializable = true,
        bool is_inspectable = true
    ) {
        // Ensure type exists
        register_type(type_name);

        // Create field descriptor
        tc_field_desc desc = {};
        desc.path = path;
        desc.label = label;
        desc.kind = kind;
        desc.min = min;
        desc.max = max;
        desc.step = step;
        desc.is_serializable = is_serializable;
        desc.is_inspectable = is_inspectable;

        tc_inspect_add_field(type_name, &desc);

        // Store context (prevent GC)
        auto& type_contexts = contexts()[type_name];
        type_contexts.emplace_back(py_getter, py_setter, path);
        PythonFieldContext* ctx = &type_contexts.back();

        // Create vtable
        tc_field_vtable vtable = {};
        vtable.get = python_field_getter;
        vtable.set = python_field_setter;
        vtable.user_data = ctx;

        tc_inspect_set_field_vtable(type_name, path, TC_INSPECT_LANG_PYTHON, &vtable);
    }

    // Register fields from Python __inspect_fields__ dict
    static void register_fields_from_dict(const char* type_name, nb::dict fields_dict, const char* base_type = nullptr) {
        register_type(type_name, base_type);

        for (auto item : fields_dict) {
            std::string field_name = nb::cast<std::string>(item.first);
            nb::object field_obj = nb::borrow<nb::object>(item.second);

            // Extract attributes
            std::string path = field_name;
            if (nb::hasattr(field_obj, "path") && !field_obj.attr("path").is_none()) {
                path = nb::cast<std::string>(field_obj.attr("path"));
            }

            std::string label = field_name;
            if (nb::hasattr(field_obj, "label") && !field_obj.attr("label").is_none()) {
                label = nb::cast<std::string>(field_obj.attr("label"));
            }

            std::string kind = "float";
            if (nb::hasattr(field_obj, "kind")) {
                kind = nb::cast<std::string>(field_obj.attr("kind"));
            }

            double min_val = 0.0, max_val = 1.0, step_val = 0.01;
            if (nb::hasattr(field_obj, "min") && !field_obj.attr("min").is_none()) {
                min_val = nb::cast<double>(field_obj.attr("min"));
            }
            if (nb::hasattr(field_obj, "max") && !field_obj.attr("max").is_none()) {
                max_val = nb::cast<double>(field_obj.attr("max"));
            }
            if (nb::hasattr(field_obj, "step") && !field_obj.attr("step").is_none()) {
                step_val = nb::cast<double>(field_obj.attr("step"));
            }

            bool is_serializable = true;
            if (nb::hasattr(field_obj, "is_serializable")) {
                is_serializable = nb::cast<bool>(field_obj.attr("is_serializable"));
            }

            bool is_inspectable = true;
            if (nb::hasattr(field_obj, "is_inspectable")) {
                is_inspectable = nb::cast<bool>(field_obj.attr("is_inspectable"));
            }

            nb::object py_getter = nb::none();
            nb::object py_setter = nb::none();
            if (nb::hasattr(field_obj, "getter") && !field_obj.attr("getter").is_none()) {
                py_getter = field_obj.attr("getter");
            }
            if (nb::hasattr(field_obj, "setter") && !field_obj.attr("setter").is_none()) {
                py_setter = field_obj.attr("setter");
            }

            register_field(
                type_name,
                path.c_str(),
                label.c_str(),
                kind.c_str(),
                py_getter,
                py_setter,
                min_val,
                max_val,
                step_val,
                is_serializable,
                is_inspectable
            );
        }
    }

    // Unregister a type and clean up contexts
    static void unregister_type(const char* type_name) {
        tc_inspect_unregister_type(type_name);
        contexts().erase(type_name);
    }
};

} // namespace tc
