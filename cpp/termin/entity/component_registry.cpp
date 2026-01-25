#include "component_registry.hpp"
#include "component.hpp"
#include "../../../core_c/include/tc_component.h"
#include <stdexcept>
#include <algorithm>
#include <memory>
#include <tc_log.hpp>

#ifdef TERMIN_HAS_NANOBIND
#include "component_registry_python.hpp"
#endif

namespace termin {

// ============================================================================
// ComponentRegistry implementation
// ============================================================================

ComponentRegistry& ComponentRegistry::instance() {
    static ComponentRegistry inst;
    return inst;
}

void ComponentRegistry::register_native(const std::string& name, tc_component_factory factory, void* userdata, const char* parent) {
    // Register directly in C registry with factory
    tc_component_registry_register_with_parent(name.c_str(), factory, userdata, TC_CXX_COMPONENT, parent);
}

void ComponentRegistry::unregister(const std::string& name) {
    tc_component_registry_unregister(name.c_str());
}

bool ComponentRegistry::has(const std::string& name) const {
    return tc_component_registry_has(name.c_str());
}

bool ComponentRegistry::is_native(const std::string& name) const {
    return tc_component_registry_get_kind(name.c_str()) == TC_CXX_COMPONENT;
}

std::vector<std::string> ComponentRegistry::list_all() const {
    std::vector<std::string> result;
    size_t count = tc_component_registry_type_count();
    result.reserve(count);
    for (size_t i = 0; i < count; i++) {
        const char* name = tc_component_registry_type_at(i);
        if (name) {
            result.push_back(name);
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}

std::vector<std::string> ComponentRegistry::list_native() const {
    std::vector<std::string> result;
    size_t count = tc_component_registry_type_count();
    for (size_t i = 0; i < count; i++) {
        const char* name = tc_component_registry_type_at(i);
        if (name && tc_component_registry_get_kind(name) == TC_CXX_COMPONENT) {
            result.push_back(name);
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}

void ComponentRegistry::clear() {
    // Note: can't really clear C registry, this is mainly for testing
}

void ComponentRegistry::set_drawable(const std::string& name, bool is_drawable) {
    tc_component_registry_set_drawable(name.c_str(), is_drawable);
}

void ComponentRegistry::set_input_handler(const std::string& name, bool is_input_handler) {
    tc_component_registry_set_input_handler(name.c_str(), is_input_handler);
}

#ifdef TERMIN_HAS_NANOBIND
// ============================================================================
// ComponentRegistryPython implementation (Python support)
// ============================================================================

// Storage for Python classes (for get_class and factory)
static std::unordered_map<std::string, std::shared_ptr<nb::object>>& python_classes() {
    static std::unordered_map<std::string, std::shared_ptr<nb::object>> classes;
    return classes;
}

// Python component factory trampoline
// userdata is the interned type_name string
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
        if (nb::hasattr(py_obj, "c_component_ptr")) {
            uintptr_t ptr = nb::cast<uintptr_t>(py_obj.attr("c_component_ptr")());
            tc_component* tc = reinterpret_cast<tc_component*>(ptr);
            // Keep Python object alive - this INCREF will be balanced by release on remove
            Py_INCREF(py_obj.ptr());
            tc->factory_retained = true;
            return tc;
        }
    } catch (const nb::python_error& e) {
        tc::Log::error(e, "python_component_factory: failed to create %s", type_name);
        PyErr_Clear();
    }

    return nullptr;
}

void ComponentRegistryPython::register_python(const std::string& name, nb::object cls, const char* parent) {
    // Don't overwrite native components with Python
    if (tc_component_registry_has(name.c_str()) &&
        tc_component_registry_get_kind(name.c_str()) == TC_CXX_COMPONENT) {
        return;
    }

    // Store Python class
    auto cls_ptr = std::make_shared<nb::object>(std::move(cls));
    python_classes()[name] = cls_ptr;

    // Get interned type name to use as userdata (stable pointer)
    const char* interned_name = tc_intern_string(name.c_str());

    // Register in C registry with trampoline factory
    tc_component_registry_register_with_parent(
        name.c_str(),
        python_component_factory,
        const_cast<char*>(interned_name),  // userdata = type name for lookup
        TC_PYTHON_COMPONENT,
        parent
    );
}

tc_component* ComponentRegistryPython::create_tc_component(const std::string& name) {
    return tc_component_registry_create(name.c_str());
}

nb::object ComponentRegistryPython::get_class(const std::string& name) {
    // First check Python classes storage
    auto& py_classes = python_classes();
    auto py_it = py_classes.find(name);
    if (py_it != py_classes.end()) {
        return *(py_it->second);
    }

    // For native components, look up the class in the appropriate module
    if (tc_component_registry_get_kind(name.c_str()) != TC_CXX_COMPONENT) {
        return nb::none();
    }

    try {
        // Try entity module first (for CXXRotatorComponent, etc.)
        nb::object entity_mod = nb::module_::import_("termin.entity._entity_native");
        if (nb::hasattr(entity_mod, name.c_str())) {
            return entity_mod.attr(name.c_str());
        }
        // Then render module (for MeshRenderer, SkinnedMeshRenderer)
        nb::object render_mod = nb::module_::import_("termin._native.render");
        if (nb::hasattr(render_mod, name.c_str())) {
            return render_mod.attr(name.c_str());
        }
        // Skeleton native module (for SkeletonController, SkeletonInstance)
        nb::object skeleton_native_mod = nb::module_::import_("termin.skeleton._skeleton_native");
        if (nb::hasattr(skeleton_native_mod, name.c_str())) {
            return skeleton_native_mod.attr(name.c_str());
        }
        // Animation native module (for AnimationPlayer)
        nb::object animation_native_mod = nb::module_::import_("termin.visualization.animation._animation_native");
        if (nb::hasattr(animation_native_mod, name.c_str())) {
            return animation_native_mod.attr(name.c_str());
        }
        // NavMesh native module (for RecastNavMeshBuilderComponent)
        nb::object navmesh_native_mod = nb::module_::import_("termin.navmesh._navmesh_native");
        if (nb::hasattr(navmesh_native_mod, name.c_str())) {
            return navmesh_native_mod.attr(name.c_str());
        }
        // Legacy skeleton module in _native
        nb::object skeleton_mod = nb::module_::import_("termin._native.skeleton");
        if (nb::hasattr(skeleton_mod, name.c_str())) {
            return skeleton_mod.attr(name.c_str());
        }
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
#endif // TERMIN_HAS_NANOBIND

} // namespace termin
