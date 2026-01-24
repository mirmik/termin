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
// ComponentRegistry implementation (C++ only)
// ============================================================================

ComponentRegistry& ComponentRegistry::instance() {
    static ComponentRegistry inst;
    return inst;
}

void ComponentRegistry::register_native(const std::string& name, TcFactory factory, const char* parent) {
    ComponentInfo info;
    info.name = name;
    info.kind = TC_CXX_COMPONENT;
    info.factory = std::move(factory);

    registry_[name] = std::move(info);

    // Register in C registry for type hierarchy (no factory needed for hierarchy)
    tc_component_registry_register_with_parent(name.c_str(), nullptr, TC_CXX_COMPONENT, parent);
}

void ComponentRegistry::unregister(const std::string& name) {
    auto it = registry_.find(name);
    if (it != registry_.end()) {
        registry_.erase(it);
    }
    // Also unregister from C registry
    tc_component_registry_unregister(name.c_str());
}

tc_component* ComponentRegistry::create(const std::string& name) const {
    auto it = registry_.find(name);
    if (it == registry_.end()) {
        return nullptr;
    }
    return it->second.factory();
}

bool ComponentRegistry::has(const std::string& name) const {
    return registry_.count(name) > 0;
}

bool ComponentRegistry::is_native(const std::string& name) const {
    auto it = registry_.find(name);
    if (it == registry_.end()) return false;
    return it->second.kind == TC_CXX_COMPONENT;
}

std::vector<std::string> ComponentRegistry::list_all() const {
    std::vector<std::string> result;
    result.reserve(registry_.size());
    for (const auto& [name, _] : registry_) {
        result.push_back(name);
    }
    std::sort(result.begin(), result.end());
    return result;
}

std::vector<std::string> ComponentRegistry::list_native() const {
    std::vector<std::string> result;
    for (const auto& [name, info] : registry_) {
        if (info.kind == TC_CXX_COMPONENT) {
            result.push_back(name);
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}

void ComponentRegistry::clear() {
    registry_.clear();
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

// Storage for Python classes (for get_class)
static std::unordered_map<std::string, std::shared_ptr<nb::object>>& python_classes() {
    static std::unordered_map<std::string, std::shared_ptr<nb::object>> classes;
    return classes;
}

void ComponentRegistryPython::register_python(const std::string& name, nb::object cls, const char* parent) {
    auto& registry = ComponentRegistry::instance();
    auto it = registry.registry_.find(name);
    if (it != registry.registry_.end() && it->second.kind == TC_CXX_COMPONENT) {
        // Don't overwrite native components with Python
        return;
    }

    // Store Python class in shared_ptr so it survives in the lambda
    auto cls_ptr = std::make_shared<nb::object>(std::move(cls));
    python_classes()[name] = cls_ptr;

    ComponentRegistry::ComponentInfo info;
    info.name = name;
    info.kind = TC_PYTHON_COMPONENT;
    info.factory = [cls_ptr]() -> tc_component* {
        nb::object py_obj = (*cls_ptr)();
        if (nb::hasattr(py_obj, "c_component_ptr")) {
            uintptr_t ptr = nb::cast<uintptr_t>(py_obj.attr("c_component_ptr")());
            tc_component* tc = reinterpret_cast<tc_component*>(ptr);
            // Keep Python object alive - this INCREF will be balanced by release on remove.
            // Without this, py_obj goes out of scope and Python object is destroyed.
            Py_INCREF(py_obj.ptr());
            // Tell entity that retain was already done by factory
            tc->factory_retained = true;
            return tc;
        }
        return nullptr;
    };

    registry.registry_[name] = std::move(info);

    // Register in C registry for type hierarchy
    tc_component_registry_register_with_parent(name.c_str(), nullptr, TC_PYTHON_COMPONENT, parent);
}

nb::object ComponentRegistryPython::create(const std::string& name) {
    nb::object cls = get_class(name);
    if (cls.is_none()) {
        throw std::runtime_error("Cannot find Python class for component: " + name);
    }
    return cls();
}

tc_component* ComponentRegistryPython::create_tc_component(const std::string& name) {
    return ComponentRegistry::instance().create(name);
}

nb::object ComponentRegistryPython::get_class(const std::string& name) {
    // First check Python classes storage
    auto& py_classes = python_classes();
    auto py_it = py_classes.find(name);
    if (py_it != py_classes.end()) {
        return *(py_it->second);
    }

    // For native components, look up the class in the appropriate module
    auto& registry = ComponentRegistry::instance();
    auto it = registry.registry_.find(name);
    if (it == registry.registry_.end() || it->second.kind != TC_CXX_COMPONENT) {
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

const ComponentRegistry::ComponentInfo* ComponentRegistryPython::get_info(const std::string& name) {
    auto& registry = ComponentRegistry::instance();
    auto it = registry.registry_.find(name);
    if (it == registry.registry_.end()) {
        return nullptr;
    }
    return &it->second;
}

std::vector<std::string> ComponentRegistryPython::list_python() {
    auto& registry = ComponentRegistry::instance();
    std::vector<std::string> result;
    for (const auto& [name, info] : registry.registry_) {
        if (info.kind == TC_PYTHON_COMPONENT) {
            result.push_back(name);
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}
#endif // TERMIN_HAS_NANOBIND

} // namespace termin
