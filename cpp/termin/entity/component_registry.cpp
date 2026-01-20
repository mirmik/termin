#include "component_registry.hpp"
#include "component.hpp"
#include "../../../core_c/include/tc_component.h"
#include <stdexcept>
#include <algorithm>
#include <iostream>
#include <tc_log.hpp>

namespace termin {

ComponentRegistry& ComponentRegistry::instance() {
    static ComponentRegistry inst;
    return inst;
}

void ComponentRegistry::register_native(const std::string& name, NativeFactory factory, const char* parent) {
    ComponentInfo info;
    info.name = name;
    info.kind = TC_CXX_COMPONENT;
    info.native_factory = std::move(factory);

    registry_[name] = std::move(info);

    // Register in C registry for type hierarchy (no factory needed for hierarchy)
    tc_component_registry_register_with_parent(name.c_str(), nullptr, TC_CXX_COMPONENT, parent);
}

void ComponentRegistry::register_python(const std::string& name, nb::object cls, const char* parent) {
    auto it = registry_.find(name);
    if (it != registry_.end() && it->second.kind == TC_CXX_COMPONENT) {
        // Don't overwrite native components with Python
        return;
    }

    ComponentInfo info;
    info.name = name;
    info.kind = TC_PYTHON_COMPONENT;
    info.python_class = std::move(cls);

    registry_[name] = std::move(info);

    // Register in C registry for type hierarchy
    tc_component_registry_register_with_parent(name.c_str(), nullptr, TC_PYTHON_COMPONENT, parent);
}

void ComponentRegistry::unregister(const std::string& name) {
    registry_.erase(name);
}

nb::object ComponentRegistry::create(const std::string& name) const {
    auto it = registry_.find(name);
    if (it == registry_.end()) {
        throw std::runtime_error("Unknown component type: " + name);
    }

    const auto& info = it->second;

    if (info.kind == TC_CXX_COMPONENT) {
        // For native components, we need to call the Python class constructor
        // because nb::cast(CxxComponent*) doesn't know the derived type.
        // Get the Python class and call its constructor.
        nb::object cls = get_class(name);
        if (cls.is_none()) {
            throw std::runtime_error("Cannot find Python class for native component: " + name);
        }
        return cls();
    } else {
        return info.python_class();
    }
}

CxxComponent* ComponentRegistry::create_component(const std::string& name) const {
    auto it = registry_.find(name);
    if (it == registry_.end()) {
        return nullptr;
    }

    const auto& info = it->second;

    if (info.kind == TC_CXX_COMPONENT) {
        return info.native_factory();
    } else {
        // For Python components, this method shouldn't be used
        // Use create() instead and handle Python objects properly
        return nullptr;
    }
}

bool ComponentRegistry::has(const std::string& name) const {
    return registry_.count(name) > 0;
}

const ComponentRegistry::ComponentInfo* ComponentRegistry::get_info(const std::string& name) const {
    auto it = registry_.find(name);
    if (it == registry_.end()) {
        return nullptr;
    }
    return &it->second;
}

nb::object ComponentRegistry::get_class(const std::string& name) const {
    auto it = registry_.find(name);
    if (it == registry_.end()) {
        return nb::none();
    }

    const auto& info = it->second;
    if (info.kind == TC_CXX_COMPONENT) {
        // For native components, look up the class in the appropriate module
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
    } else {
        return info.python_class;
    }
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

std::vector<std::string> ComponentRegistry::list_python() const {
    std::vector<std::string> result;
    for (const auto& [name, info] : registry_) {
        if (info.kind == TC_PYTHON_COMPONENT) {
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

} // namespace termin
