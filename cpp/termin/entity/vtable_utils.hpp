#pragma once

#include "component.hpp"

namespace termin {

// Utility for detecting virtual method overrides via vtable inspection.
// Inspects the vtable directly to check if a derived class overrides a virtual method.

// Helper class that can instantiate Component (protected constructor).
class ENTITY_API ComponentVTableProbe : public Component {
public:
    ComponentVTableProbe() = default;
};

// Probe class that overrides ONLY update() - used to find its vtable slot.
// Implementation is in vtable_utils.cpp to prevent ICF optimization.
class ENTITY_API UpdateProbe : public Component {
public:
    UpdateProbe() = default;
    void update(float dt) override;
private:
    volatile float _probe_marker = 0;
};

// Probe class that overrides ONLY fixed_update() - used to find its vtable slot.
// Implementation is in vtable_utils.cpp to prevent ICF optimization.
class ENTITY_API FixedUpdateProbe : public Component {
public:
    FixedUpdateProbe() = default;
    void fixed_update(float dt) override;
private:
    volatile float _probe_marker = 0;
};

// Cached vtable slot indices, computed once at startup.
struct ENTITY_API VTableSlots {
    int update_slot = -1;
    int fixed_update_slot = -1;

    static VTableSlots& instance();

private:
    static VTableSlots compute();
};

/**
 * Check if type T overrides Component::update().
 */
template<typename T>
bool component_overrides_update() {
    int slot = VTableSlots::instance().update_slot;
    if (slot < 0) return false;

    ComponentVTableProbe base;
    T derived;

    void** base_vtable = *reinterpret_cast<void***>(static_cast<Component*>(&base));
    void** derived_vtable = *reinterpret_cast<void***>(static_cast<Component*>(&derived));

    return base_vtable[slot] != derived_vtable[slot];
}

/**
 * Check if type T overrides Component::fixed_update().
 */
template<typename T>
bool component_overrides_fixed_update() {
    int slot = VTableSlots::instance().fixed_update_slot;
    if (slot < 0) return false;

    ComponentVTableProbe base;
    T derived;

    void** base_vtable = *reinterpret_cast<void***>(static_cast<Component*>(&base));
    void** derived_vtable = *reinterpret_cast<void***>(static_cast<Component*>(&derived));

    return base_vtable[slot] != derived_vtable[slot];
}

/**
 * Macro for binding native C++ components to pybind11.
 * Automatically sets up the factory with proper flag detection.
 *
 * Usage:
 *   BIND_NATIVE_COMPONENT(m, MyComponent)
 *       .def_readwrite("speed", &MyComponent::speed);
 */
#define BIND_NATIVE_COMPONENT(module, ClassName) \
    py::class_<ClassName, Component>(module, #ClassName) \
        .def(py::init([]() { \
            auto comp = new ClassName(); \
            comp->set_type_name(#ClassName); \
            comp->is_native = true; \
            comp->has_update = component_overrides_update<ClassName>(); \
            comp->has_fixed_update = component_overrides_fixed_update<ClassName>(); \
            return comp; \
        }))

} // namespace termin
