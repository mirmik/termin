// tc_inspect_instance.cpp - InspectRegistry singleton, vtable callbacks, and methods needing Component
// This file must be compiled into entity_lib to ensure single instance across all modules

#include "../../cpp/trent/trent.h"

// Include Component BEFORE tc_inspect so it's fully defined
#include "../../cpp/termin/entity/component.hpp"

#ifdef TERMIN_HAS_NANOBIND
#include "../include/tc_inspect.hpp"
#else
#include "../include/tc_inspect_cpp.hpp"
#endif
#include "../include/render/tc_pass.h"

namespace tc {

// ============================================================================
// InspectRegistry singleton
// ============================================================================

InspectRegistry& InspectRegistry::instance() {
    static InspectRegistry reg;
    return reg;
}

#ifdef TERMIN_HAS_NANOBIND
// ============================================================================
// InspectRegistryPythonExt implementation (Python-only)
// ============================================================================

void InspectRegistryPythonExt::add_button(InspectRegistry& reg, const std::string& type_name,
                                          const std::string& path, const std::string& label,
                                          nb::object action) {
    InspectFieldInfo info;
    info.type_name = type_name;
    info.path = path;
    info.label = label;
    info.kind = "button";
    info.is_serializable = false;
    info.is_inspectable = true;
    info.py_action = new nb::object(std::move(action));

    reg._fields[type_name].push_back(std::move(info));
}

void InspectRegistryPythonExt::register_python_fields(InspectRegistry& reg, const std::string& type_name,
                                                       nb::dict fields_dict) {
    reg._fields.erase(type_name);

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
            info.py_action = new nb::object(field_obj.attr("action"));
        }

        // Custom getter/setter from Python InspectField
        nb::object py_getter = nb::none();
        nb::object py_setter = nb::none();
        if (nb::hasattr(field_obj, "getter") && !field_obj.attr("getter").is_none()) {
            py_getter = field_obj.attr("getter");
        }
        if (nb::hasattr(field_obj, "setter") && !field_obj.attr("setter").is_none()) {
            py_setter = field_obj.attr("setter");
        }

        std::string path_copy = info.path;
        std::string kind_copy = info.kind;

        info.getter = [path_copy, kind_copy, py_getter](void* obj) -> tc_value {
            // obj is PyObject* for Python types
            nb::object py_obj = nb::borrow<nb::object>(
                nb::handle(static_cast<PyObject*>(obj)));

            nb::object result;
            if (!py_getter.is_none()) {
                result = py_getter(py_obj);
            } else {
                // Use getattr for path resolution
                result = py_obj;
                size_t start = 0, end;
                while ((end = path_copy.find('.', start)) != std::string::npos) {
                    result = nb::getattr(result, path_copy.substr(start, end - start).c_str());
                    start = end + 1;
                }
                result = nb::getattr(result, path_copy.substr(start).c_str());
            }

            // Serialize through kind handler if available
            ensure_list_handler(kind_copy);
            auto& py_reg = KindRegistryPython::instance();
            if (py_reg.has(kind_copy)) {
                result = py_reg.serialize(kind_copy, result);
            }
            return nb_to_tc_value(result);
        };

        info.setter = [path_copy, kind_copy, py_setter](void* obj, tc_value value, tc_scene*) {
            try {
                // obj is PyObject* for Python types
                nb::object py_obj = nb::borrow<nb::object>(
                    nb::handle(static_cast<PyObject*>(obj)));

                // Convert tc_value to Python object
                nb::object py_value = tc_value_to_nb(&value);

                // Deserialize through kind handler if available
                ensure_list_handler(kind_copy);
                auto& py_reg = KindRegistryPython::instance();
                if (py_reg.has(kind_copy)) {
                    py_value = py_reg.deserialize(kind_copy, py_value);
                }

                if (!py_setter.is_none()) {
                    py_setter(py_obj, py_value);
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
                nb::setattr(target, parts.back().c_str(), py_value);
            } catch (const std::exception& e) {
                std::cerr << "[Python setter error] path=" << path_copy
                          << " error=" << e.what() << std::endl;
            }
        };

        reg._fields[type_name].push_back(std::move(info));
    }

    reg._type_backends[type_name] = TypeBackend::Python;
}

nb::object InspectRegistryPythonExt::get(InspectRegistry& reg, void* obj,
                                         const std::string& type_name, const std::string& field_path) {
    const InspectFieldInfo* f = reg.find_field(type_name, field_path);
    if (!f) {
        throw nb::attribute_error(("Field not found: " + field_path).c_str());
    }
    if (!f->getter) {
        throw nb::type_error(("No getter for field: " + field_path).c_str());
    }
    tc_value val = f->getter(obj);
    nb::object result = tc_value_to_nb(&val);
    tc_value_free(&val);
    return result;
}

void InspectRegistryPythonExt::set(InspectRegistry& reg, void* obj, const std::string& type_name,
                                   const std::string& field_path, nb::object value, tc_scene* scene) {
    const InspectFieldInfo* f = reg.find_field(type_name, field_path);
    if (!f) {
        throw nb::attribute_error(("Field not found: " + field_path).c_str());
    }
    if (!f->setter) {
        throw nb::type_error(("No setter for field: " + field_path).c_str());
    }
    tc_value val = nb_to_tc_value(value);
    f->setter(obj, val, scene);
    tc_value_free(&val);
}

void InspectRegistryPythonExt::deserialize_all_py(InspectRegistry& reg, void* obj,
                                                   const std::string& type_name,
                                                   const nb::dict& data, tc_scene* scene) {
    for (const auto& f : reg.all_fields(type_name)) {
        if (!f.is_serializable) continue;
        if (!f.setter) continue;

        nb::str key(f.path.c_str());
        if (!data.contains(key)) continue;

        nb::object field_data = data[key];
        if (field_data.is_none()) continue;

        tc_value val = nb_to_tc_value(field_data);
        f.setter(obj, val, scene);
        tc_value_free(&val);
    }
}

void InspectRegistryPythonExt::deserialize_component_fields_over_python(
    InspectRegistry& reg, void* ptr, nb::object obj, const std::string& type_name,
    const nb::dict& data, tc_scene* scene) {
    // For C++ components ptr is the object, for Python components obj.ptr() is used
    void* target = (reg.get_type_backend(type_name) == TypeBackend::Cpp) ? ptr : obj.ptr();
    deserialize_all_py(reg, target, type_name, data, scene);
}
#endif // TERMIN_HAS_NANOBIND

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
        // For external components, body holds the Python object
        return c->body;
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

tc_value tc_pass_inspect_get(tc_pass* p, const char* path) {
    if (!p || !path) return tc_value_nil();

    const char* type_name = tc_pass_type_name(p);
    if (!type_name) return tc_value_nil();

    void* obj = p->body;
    if (!obj) return tc_value_nil();

    return tc::InspectRegistry::instance().get_tc_value(obj, type_name, path);
}

void tc_pass_inspect_set(tc_pass* p, const char* path, tc_value value, tc_scene* scene) {
    if (!p || !path) return;

    const char* type_name = tc_pass_type_name(p);
    if (!type_name) return;

    void* obj = p->body;
    if (!obj) return;

    tc::InspectRegistry::instance().set_tc_value(obj, type_name, path, value, scene);
}

} // extern "C"
