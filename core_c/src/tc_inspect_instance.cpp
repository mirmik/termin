// tc_inspect_instance.cpp - InspectRegistry singleton, vtable callbacks, and methods needing Component
// This file must be compiled into entity_lib to ensure single instance across all modules

#include "../../cpp/trent/trent.h"

// Include Component BEFORE tc_inspect.hpp so it's fully defined
#include "../../cpp/termin/entity/component.hpp"

#include "../include/tc_inspect.hpp"

namespace tc {

// ============================================================================
// InspectRegistry singleton
// ============================================================================

InspectRegistry& InspectRegistry::instance() {
    static InspectRegistry reg;
    return reg;
}

// ============================================================================
// Python field registration
// ============================================================================

void InspectRegistry::register_python_fields(const std::string& type_name, nb::dict fields_dict) {
    _fields.erase(type_name);

    for (auto item : fields_dict) {
        std::string field_name = nb::cast<std::string>(item.first);
        nb::object field_obj = nb::borrow<nb::object>(item.second);

        InspectFieldInfo info;
        info.type_name = type_name;

        // Extract attributes
        info.path = field_name;
        if (nb::hasattr(field_obj, "path") && !field_obj.attr("path").is_none()) {
            info.path = nb::cast<std::string>(field_obj.attr("path"));
        }

        info.label = field_name;
        if (nb::hasattr(field_obj, "label") && !field_obj.attr("label").is_none()) {
            info.label = nb::cast<std::string>(field_obj.attr("label"));
        }

        info.kind = "float";
        if (nb::hasattr(field_obj, "kind")) {
            info.kind = nb::cast<std::string>(field_obj.attr("kind"));
        }

        if (nb::hasattr(field_obj, "min") && !field_obj.attr("min").is_none()) {
            info.min = nb::cast<double>(field_obj.attr("min"));
        }
        if (nb::hasattr(field_obj, "max") && !field_obj.attr("max").is_none()) {
            info.max = nb::cast<double>(field_obj.attr("max"));
        }
        if (nb::hasattr(field_obj, "step") && !field_obj.attr("step").is_none()) {
            info.step = nb::cast<double>(field_obj.attr("step"));
        }

        // is_serializable (default true, can be set via is_serializable=False or legacy non_serializable=True)
        if (nb::hasattr(field_obj, "is_serializable")) {
            info.is_serializable = nb::cast<bool>(field_obj.attr("is_serializable"));
        } else if (nb::hasattr(field_obj, "non_serializable")) {
            info.is_serializable = !nb::cast<bool>(field_obj.attr("non_serializable"));
        }

        // is_inspectable (default true)
        if (nb::hasattr(field_obj, "is_inspectable")) {
            info.is_inspectable = nb::cast<bool>(field_obj.attr("is_inspectable"));
        }

        // Choices for enum
        if (nb::hasattr(field_obj, "choices") && !field_obj.attr("choices").is_none()) {
            for (auto c : field_obj.attr("choices")) {
                nb::tuple t = nb::cast<nb::tuple>(c);
                if (t.size() >= 2) {
                    EnumChoice choice;
                    // Convert value to string (handles ints, enums, strings)
                    nb::object val_obj = nb::borrow<nb::object>(t[0]);
                    if (nb::isinstance<nb::str>(val_obj)) {
                        choice.value = nb::cast<std::string>(val_obj);
                    } else if (nb::isinstance<nb::int_>(val_obj)) {
                        choice.value = std::to_string(nb::cast<int64_t>(val_obj));
                    } else {
                        // Fallback: use Python str()
                        choice.value = nb::cast<std::string>(nb::str(val_obj));
                    }
                    choice.label = nb::cast<std::string>(t[1]);
                    info.choices.push_back(choice);
                }
            }
        }

        // Action for button
        if (nb::hasattr(field_obj, "action") && !field_obj.attr("action").is_none()) {
            info.action = field_obj.attr("action");
        }

        // Custom getter/setter
        nb::object py_getter = nb::none();
        nb::object py_setter = nb::none();
        if (nb::hasattr(field_obj, "getter") && !field_obj.attr("getter").is_none()) {
            py_getter = field_obj.attr("getter");
        }
        if (nb::hasattr(field_obj, "setter") && !field_obj.attr("setter").is_none()) {
            py_setter = field_obj.attr("setter");
        }

        std::string path_copy = info.path;

        info.py_getter = [path_copy, py_getter](void* obj) -> nb::object {
            // obj is PyObject* from get_raw_pointer for Python types
            nb::object py_obj = nb::borrow<nb::object>(
                nb::handle(static_cast<PyObject*>(obj)));
            if (!py_getter.is_none()) {
                return py_getter(py_obj);
            }
            // Use getattr for path resolution
            nb::object result = py_obj;
            size_t start = 0, end;
            while ((end = path_copy.find('.', start)) != std::string::npos) {
                result = nb::getattr(result, path_copy.substr(start, end - start).c_str());
                start = end + 1;
            }
            return nb::getattr(result, path_copy.substr(start).c_str());
        };

        info.py_setter = [path_copy, py_setter](void* obj, nb::object value) {
            try {
                // obj is PyObject* from get_raw_pointer for Python types
                nb::object py_obj = nb::borrow<nb::object>(
                    nb::handle(static_cast<PyObject*>(obj)));
                if (!py_setter.is_none()) {
                    py_setter(py_obj, value);
                    return;
                }
                // Use setattr for path resolution
                nb::object target = py_obj;
                std::vector<std::string> parts;
                size_t start = 0, end;
                while ((end = path_copy.find('.', start)) != std::string::npos) {
                    parts.push_back(path_copy.substr(start, end - start));
                    start = end + 1;
                }
                parts.push_back(path_copy.substr(start));

                for (size_t i = 0; i < parts.size() - 1; ++i) {
                    target = nb::getattr(target, parts[i].c_str());
                }
                nb::setattr(target, parts.back().c_str(), value);
            } catch (const std::exception& e) {
                std::cerr << "[Python setter error] path=" << path_copy
                          << " error=" << e.what() << std::endl;
            }
        };

        _fields[type_name].push_back(std::move(info));
    }

    _type_backends[type_name] = TypeBackend::Python;
}

// ============================================================================
// C++ vtable callbacks for C dispatcher
// ============================================================================

static bool cpp_has_type(const char* type_name, void* ctx) {
    (void)ctx;
    return InspectRegistry::instance().has_type(type_name);
}

static const char* cpp_get_parent(const char* type_name, void* ctx) {
    (void)ctx;
    static std::string parent;  // Static to keep string alive
    parent = InspectRegistry::instance().get_type_parent(type_name);
    return parent.empty() ? nullptr : parent.c_str();
}

static size_t cpp_field_count(const char* type_name, void* ctx) {
    (void)ctx;
    return InspectRegistry::instance().all_fields_count(type_name);
}

static bool cpp_get_field(const char* type_name, size_t index, tc_field_info* out, void* ctx) {
    (void)ctx;
    const InspectFieldInfo* info = InspectRegistry::instance().get_field_by_index(type_name, index);
    if (!info) return false;
    info->fill_c_info(out);
    return true;
}

static bool cpp_find_field(const char* type_name, const char* path, tc_field_info* out, void* ctx) {
    (void)ctx;
    const InspectFieldInfo* info = InspectRegistry::instance().find_field(type_name, path);
    if (!info) return false;
    info->fill_c_info(out);
    return true;
}

static tc_value cpp_get(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)ctx;
    return InspectRegistry::instance().get_tc_value(obj, type_name, path);
}

static void cpp_set(void* obj, const char* type_name, const char* path, tc_value value, tc_scene* scene, void* ctx) {
    (void)ctx;
    InspectRegistry::instance().set_tc_value(obj, type_name, path, value, scene);
}

static void cpp_action(void* obj, const char* type_name, const char* path, void* ctx) {
    (void)ctx;
    InspectRegistry::instance().action_field(obj, type_name, path);
}

static bool g_cpp_vtable_initialized = false;

void init_cpp_inspect_vtable() {
    if (g_cpp_vtable_initialized) return;
    g_cpp_vtable_initialized = true;

    static tc_inspect_lang_vtable cpp_vtable = {
        cpp_has_type,
        cpp_get_parent,
        cpp_field_count,
        cpp_get_field,
        cpp_find_field,
        cpp_get,
        cpp_set,
        cpp_action,
        nullptr  // ctx
    };

    tc_inspect_set_lang_vtable(TC_INSPECT_LANG_CPP, &cpp_vtable);
}

// ============================================================================
// Component field access - C API implementation
// ============================================================================

static void* get_inspect_object(tc_component* c) {
    if (!c) return nullptr;
    if (c->kind == TC_NATIVE_COMPONENT) {
        return termin::CxxComponent::from_tc(c);
    } else {
        return c->wrapper;
    }
}

} // namespace tc

extern "C" {

tc_value tc_component_inspect_get(tc_component* c, const char* path) {
    if (!c || !path) return tc_value_nil();

    const char* type_name = tc_component_type_name(c);
    if (!type_name) return tc_value_nil();

    void* obj = tc::get_inspect_object(c);
    if (!obj) return tc_value_nil();

    return tc::InspectRegistry::instance().get_tc_value(obj, type_name, path);
}

void tc_component_inspect_set(tc_component* c, const char* path, tc_value value, tc_scene* scene) {
    if (!c || !path) return;

    const char* type_name = tc_component_type_name(c);
    if (!type_name) return;

    void* obj = tc::get_inspect_object(c);
    if (!obj) return;

    tc::InspectRegistry::instance().set_tc_value(obj, type_name, path, value, scene);
}

} // extern "C"
