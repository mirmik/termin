// tc_inspect_python.hpp - Python wrapper for tc_inspect with nanobind
#pragma once

#include "tc_inspect.h"
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <string>
#include <unordered_map>
#include <vector>

namespace nb = nanobind;

namespace tc {

// ============================================================================
// tc_value <-> nb::object conversion
// ============================================================================

inline tc_value nb_to_tc_value(nb::object obj) {
    if (obj.is_none()) {
        return tc_value_nil();
    }

    if (nb::isinstance<nb::bool_>(obj)) {
        return tc_value_bool(nb::cast<bool>(obj));
    }

    if (nb::isinstance<nb::int_>(obj)) {
        return tc_value_int(nb::cast<int64_t>(obj));
    }

    if (nb::isinstance<nb::float_>(obj)) {
        return tc_value_double(nb::cast<double>(obj));
    }

    if (nb::isinstance<nb::str>(obj)) {
        return tc_value_string(nb::cast<std::string>(obj).c_str());
    }

    if (nb::isinstance<nb::list>(obj) || nb::isinstance<nb::tuple>(obj)) {
        tc_value list = tc_value_list_new();
        for (auto item : obj) {
            tc_value_list_push(&list, nb_to_tc_value(nb::borrow<nb::object>(item)));
        }
        return list;
    }

    if (nb::isinstance<nb::dict>(obj)) {
        tc_value dict = tc_value_dict_new();
        for (auto item : nb::cast<nb::dict>(obj)) {
            std::string key = nb::cast<std::string>(nb::str(item.first));
            tc_value_dict_set(&dict, key.c_str(),
                nb_to_tc_value(nb::borrow<nb::object>(item.second)));
        }
        return dict;
    }

    // Try vec3-like (length 3 sequence)
    if (nb::hasattr(obj, "__len__") && nb::len(obj) == 3) {
        try {
            nb::list lst = nb::cast<nb::list>(obj);
            tc_vec3 v = {
                nb::cast<double>(lst[0]),
                nb::cast<double>(lst[1]),
                nb::cast<double>(lst[2])
            };
            return tc_value_vec3(v);
        } catch (...) {}
    }

    // Try tolist() for numpy
    if (nb::hasattr(obj, "tolist")) {
        return nb_to_tc_value(obj.attr("tolist")());
    }

    return tc_value_nil();
}

inline nb::object tc_value_to_nb(const tc_value* v) {
    if (!v) return nb::none();

    switch (v->type) {
    case TC_VALUE_NIL:
        return nb::none();

    case TC_VALUE_BOOL:
        return nb::bool_(v->data.b);

    case TC_VALUE_INT:
        return nb::int_(v->data.i);

    case TC_VALUE_FLOAT:
        return nb::float_(static_cast<double>(v->data.f));

    case TC_VALUE_DOUBLE:
        return nb::float_(v->data.d);

    case TC_VALUE_STRING:
        return nb::str(v->data.s ? v->data.s : "");

    case TC_VALUE_VEC3: {
        nb::list l;
        l.append(v->data.v3.x);
        l.append(v->data.v3.y);
        l.append(v->data.v3.z);
        return l;
    }

    case TC_VALUE_QUAT: {
        nb::list l;
        l.append(v->data.q.x);
        l.append(v->data.q.y);
        l.append(v->data.q.z);
        l.append(v->data.q.w);
        return l;
    }

    case TC_VALUE_LIST: {
        nb::list l;
        for (size_t i = 0; i < v->data.list.count; i++) {
            l.append(tc_value_to_nb(&v->data.list.items[i]));
        }
        return l;
    }

    case TC_VALUE_DICT: {
        nb::dict d;
        for (size_t i = 0; i < v->data.dict.count; i++) {
            d[v->data.dict.entries[i].key] = tc_value_to_nb(v->data.dict.entries[i].value);
        }
        return d;
    }

    case TC_VALUE_CUSTOM:
        // Custom types need kind handler - return None for now
        return nb::none();

    default:
        return nb::none();
    }
}

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

inline void python_field_setter(void* obj, const tc_field_desc* field, tc_value value, void* user_data) {
    (void)field;
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
