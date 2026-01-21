#pragma once

#include "component_registry.hpp"
#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {

// Python extension for ComponentRegistry.
// Provides Python component registration and creation.
class ENTITY_API ComponentRegistryPython {
public:
    // Register a Python component class
    static void register_python(const std::string& name, nb::object cls, const char* parent = nullptr);

    // Create component by name - returns nb::object (works for both C++ and Python)
    static nb::object create(const std::string& name);

    // Create tc_component* for any component type (C++ or Python)
    static tc_component* create_tc_component(const std::string& name);

    // Get Python class for component
    static nb::object get_class(const std::string& name);

    // Get ComponentInfo (internal use)
    static const ComponentRegistry::ComponentInfo* get_info(const std::string& name);

    // List Python components
    static std::vector<std::string> list_python();
};

} // namespace termin
