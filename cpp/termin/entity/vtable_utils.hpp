#pragma once

#include "component.hpp"

namespace termin {

/**
 * Utility for detecting virtual method overrides via vtable inspection.
 *
 * Problem:
 *   C++ doesn't provide a direct way to check if a derived class overrides
 *   a virtual method. Comparing member function pointers doesn't work because
 *   for virtual methods, &Derived::method == &Base::method even when Derived
 *   overrides the method (both point to the same vtable slot descriptor).
 *
 * Solution:
 *   Inspect the vtable directly. Each class has its own vtable, and if a
 *   derived class overrides a virtual method, the corresponding vtable entry
 *   will point to a different function than the base class's vtable.
 *
 * How it works:
 *   1. Create probe classes that override exactly one method each
 *   2. Compare their vtables with base to find which slot changed
 *   3. Cache these slot indices (computed once at startup)
 *   4. Use cached indices to detect overrides in user components
 *
 * Note: This is platform-specific but works on any ABI because we detect
 *       the vtable layout dynamically rather than hardcoding it.
 */

/**
 * Helper class that can instantiate Component (protected constructor).
 */
class ComponentVTableProbe : public Component {
public:
    ComponentVTableProbe() = default;
};

/**
 * Probe class that overrides ONLY update() - used to find its vtable slot.
 * Implementation is in vtable_utils.cpp to prevent ICF optimization.
 */
class UpdateProbe : public Component {
public:
    UpdateProbe() = default;
    void update(float dt) override;  // Defined in .cpp
private:
    volatile float _probe_marker = 0;
};

/**
 * Probe class that overrides ONLY fixed_update() - used to find its vtable slot.
 * Implementation is in vtable_utils.cpp to prevent ICF optimization.
 */
class FixedUpdateProbe : public Component {
public:
    FixedUpdateProbe() = default;
    void fixed_update(float dt) override;  // Defined in .cpp
private:
    volatile float _probe_marker = 0;
};

/**
 * Cached vtable slot indices, computed once at startup.
 *
 * Algorithm:
 *   We use three probe classes: BaseProbe, UpdateProbe, FixedUpdateProbe.
 *   - UpdateProbe overrides ONLY update()
 *   - FixedUpdateProbe overrides ONLY fixed_update()
 *
 *   To find the update slot:
 *     Find a slot that differs between Base and UpdateProbe,
 *     BUT is the same between Base and FixedUpdateProbe.
 *     This uniquely identifies the update slot regardless of ABI.
 *
 *   Same logic for fixed_update slot (reversed).
 */
struct VTableSlots {
    int update_slot = -1;
    int fixed_update_slot = -1;

    static VTableSlots& instance() {
        static VTableSlots slots = compute();
        return slots;
    }

private:
    static VTableSlots compute();  // Defined in vtable_utils.cpp
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
