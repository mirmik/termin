#include <termin/entity/component_registry_python.hpp>
#include "core/tc_component.h"

#include <memory>
#include <cstring>
#include <unordered_map>

#include <tcbase/tc_log.hpp>

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

void ComponentRegistryPython::register_python(const std::string& name, nb::object cls, const char* parent) {
    if (tc_component_registry_has(name.c_str()) &&
        tc_component_registry_get_kind(name.c_str()) == TC_CXX_COMPONENT) {
        return;
    }

    auto cls_ptr = std::make_shared<nb::object>(std::move(cls));
    python_classes()[name] = cls_ptr;

    // The string is used as factory userdata and lives for process lifetime.
    const char* interned_name = strdup(name.c_str());

    tc_component_registry_register_with_parent(
        name.c_str(),
        python_component_factory,
        const_cast<char*>(interned_name),
        TC_PYTHON_COMPONENT,
        parent
    );
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
