#include "component_registry.hpp"
#include "component.hpp"
#include <stdexcept>
#include <algorithm>
#include <iostream>

namespace termin {

ComponentRegistry& ComponentRegistry::instance() {
    static ComponentRegistry inst;
    return inst;
}

void ComponentRegistry::register_native(const std::string& name, NativeFactory factory) {
    ComponentInfo info;
    info.name = name;
    info.kind = TC_CXX_COMPONENT;
    info.native_factory = std::move(factory);

    registry_[name] = std::move(info);
}

void ComponentRegistry::register_python(const std::string& name, py::object cls) {
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
}

void ComponentRegistry::unregister(const std::string& name) {
    registry_.erase(name);
}

py::object ComponentRegistry::create(const std::string& name) const {
    auto it = registry_.find(name);
    if (it == registry_.end()) {
        throw std::runtime_error("Unknown component type: " + name);
    }

    const auto& info = it->second;

    if (info.kind == TC_CXX_COMPONENT) {
        CxxComponent* comp = info.native_factory();
        return py::cast(comp, py::return_value_policy::take_ownership);
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

py::object ComponentRegistry::get_class(const std::string& name) const {
    auto it = registry_.find(name);
    if (it == registry_.end()) {
        return py::none();
    }

    const auto& info = it->second;
    if (info.kind == TC_CXX_COMPONENT) {
        // For native components, create an instance and return its type
        CxxComponent* comp = info.native_factory();
        py::object py_comp = py::cast(comp, py::return_value_policy::take_ownership);
        return py::type::of(py_comp);
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

} // namespace termin
