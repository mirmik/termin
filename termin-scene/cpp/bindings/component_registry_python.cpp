#include <termin/entity/component_registry_python.hpp>
#include "core/tc_component.h"

#include <memory>
#include <cstring>
#include <unordered_map>

#include <tcbase/tc_log.hpp>
#include <tcbase/tc_string.h>
#include <inspect/tc_inspect_python.hpp>

namespace termin {

namespace nb = nanobind;

// Storage for Python classes (for get_class and factory)
static std::unordered_map<std::string, std::shared_ptr<nb::object>>& python_classes() {
    static std::unordered_map<std::string, std::shared_ptr<nb::object>> classes;
    return classes;
}

static nb::object module_attr_or_none(nb::object module, const char* name) {
    PyObject* value = PyObject_GetAttrString(module.ptr(), name);
    if (value) {
        return nb::steal<nb::object>(value);
    }
    if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
        PyErr_Clear();
        return nb::none();
    }
    throw nb::python_error();
}

// Python component factory trampoline
static tc_component* python_component_factory(void* userdata) {
    const char* type_name = static_cast<const char*>(userdata);

    auto& py_classes = python_classes();
    auto it = py_classes.find(type_name);
    if (it == py_classes.end()) {
        tc::Log::error("python_component_factory: class not found for type %s", type_name);
        return nullptr;
    }

    try {
        nb::object py_obj = (*(it->second))();
        uintptr_t ptr = nb::cast<uintptr_t>(py_obj.attr("c_component_ptr")());
        tc_component* tc = reinterpret_cast<tc_component*>(ptr);
        if (!tc) {
            tc::Log::error("python_component_factory: %s returned null c_component_ptr", type_name);
            return nullptr;
        }
        Py_INCREF(py_obj.ptr());
        tc->factory_retained = true;
        return tc;
    } catch (const nb::python_error& e) {
        tc::Log::error(e, "python_component_factory: failed to create %s", type_name);
        PyErr_Clear();
    }

    return nullptr;
}

bool ComponentRegistryPython::register_python(
    const std::string& name,
    nb::object cls,
    const char* parent,
    nb::dict fields,
    nb::dict metadata,
    const std::string& category,
    const std::string& display_name,
    nb::list requirements,
    nb::list capabilities) {
    if (tc_component_registry_has(name.c_str()) &&
        tc_component_registry_get_kind(name.c_str()) == TC_CXX_COMPONENT) {
        tc::Log::error(
            "[ComponentRegistry] refusing Python registration for native component %s",
            name.c_str());
        return false;
    }
    const char* ambient_owner = tc_component_registry_get_registration_owner();
    const bool allow_same_owner_replacement = ambient_owner && ambient_owner[0];
    if (tc_component_registry_has(name.c_str()) && !allow_same_owner_replacement) {
        auto existing = python_classes().find(name);
        if (existing != python_classes().end() && existing->second->ptr() == cls.ptr()) {
            return true;
        }
        tc::Log::error(
            "[ComponentRegistry] refusing duplicate Python component registration for %s",
            name.c_str());
        return false;
    }

    // Factory userdata must outlive registry entries, but reload cycles must
    // not allocate a fresh duplicate string for the same component name.
    const char* interned_name = tc_intern_string(name.c_str());
    if (!interned_name) {
        tc::Log::error("[ComponentRegistry] failed to intern Python component name %s", name.c_str());
        return false;
    }

    const char* owner = ambient_owner && ambient_owner[0]
        ? ambient_owner
        : "termin-scene-python";
    ComponentTypeDescriptorBuilder descriptor(
        name.c_str(), owner, parent, python_component_factory,
        const_cast<char*>(interned_name), TC_PYTHON_COMPONENT, false,
        allow_same_owner_replacement);
    descriptor.category(category).display_name(display_name);
    for (nb::handle item : requirements) {
        descriptor.require(nb::cast<std::string>(item));
    }
    for (nb::handle item : capabilities) {
        descriptor.capability(nb::cast<tc_component_cap_id>(item));
    }
    auto inspect = tc::build_python_inspect_facet(name, std::move(fields));
    tc_value metadata_value = tc::nb_to_tc_value(std::move(metadata));
    const bool metadata_ok = inspect.set_metadata(&metadata_value);
    tc_value_free(&metadata_value);
    if (!metadata_ok) return false;
    descriptor.set_inspect(std::move(inspect));
    if (!descriptor.commit()) return false;

    python_classes()[name] = std::make_shared<nb::object>(std::move(cls));
    return true;
}

void ComponentRegistryPython::unregister_python(const std::string& name) {
    python_classes().erase(name);
    tc_component_registry_unregister(name.c_str());
}

tc_component* ComponentRegistryPython::create_tc_component(const std::string& name) {
    return tc_component_registry_create(name.c_str());
}

nb::object ComponentRegistryPython::get_class(const std::string& name) {
    auto& py_classes = python_classes();
    auto py_it = py_classes.find(name);
    if (py_it != py_classes.end()) {
        return *(py_it->second);
    }

    if (tc_component_registry_get_kind(name.c_str()) != TC_CXX_COMPONENT) {
        return nb::none();
    }

    try {
        nb::object scene_mod = nb::module_::import_("termin.scene._scene_native");
        nb::object cls = module_attr_or_none(scene_mod, name.c_str());
        if (!cls.is_none()) return cls;

        nb::object render_mod = nb::module_::import_("termin.render_components._components_render_native");
        cls = module_attr_or_none(render_mod, name.c_str());
        if (!cls.is_none()) return cls;

        nb::object skeleton_native_mod = nb::module_::import_("termin.skeleton._skeleton_native");
        cls = module_attr_or_none(skeleton_native_mod, name.c_str());
        if (!cls.is_none()) return cls;

        nb::object animation_native_mod = nb::module_::import_("termin.animation._animation_native");
        cls = module_attr_or_none(animation_native_mod, name.c_str());
        if (!cls.is_none()) return cls;

        nb::object navmesh_native_mod = nb::module_::import_("termin.navmesh._navmesh_native");
        cls = module_attr_or_none(navmesh_native_mod, name.c_str());
        if (!cls.is_none()) return cls;
    } catch (...) {
        tc::Log::error("ComponentRegistry::get_class: error importing module for component %s", name.c_str());
    }
    return nb::none();
}

std::vector<std::string> ComponentRegistryPython::list_python() {
    std::vector<std::string> result;
    size_t count = tc_component_registry_type_count();
    for (size_t i = 0; i < count; i++) {
        const char* name = tc_component_registry_type_at(i);
        if (name && tc_component_registry_get_kind(name) == TC_PYTHON_COMPONENT) {
            result.push_back(name);
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}

} // namespace termin
