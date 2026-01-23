#pragma once

#include <cstdio>
#include "component.hpp"

namespace termin {

// Utility for detecting virtual method overrides via vtable inspection.
// Inspects the vtable directly to check if a derived class overrides a virtual method.

// Helper class that can instantiate CxxComponent (protected constructor).
class ENTITY_API ComponentVTableProbe : public CxxComponent {
public:
    ComponentVTableProbe() = default;
};

// Probe class that overrides ONLY update() - used to find its vtable slot.
// Implementation is in vtable_utils.cpp to prevent ICF optimization.
class ENTITY_API UpdateProbe : public CxxComponent {
public:
    UpdateProbe() = default;
    void update(float dt) override;
private:
    volatile float _probe_marker = 0;
};

// Probe class that overrides ONLY fixed_update() - used to find its vtable slot.
// Implementation is in vtable_utils.cpp to prevent ICF optimization.
class ENTITY_API FixedUpdateProbe : public CxxComponent {
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

// Check if type T overrides CxxComponent::update().
template<typename T>
bool component_overrides_update() {
    int slot = VTableSlots::instance().update_slot;
    printf("[component_overrides_update] update_slot=%d\n", slot);
    if (slot < 0) return false;

    ComponentVTableProbe base;
    T derived;

    void** base_vtable = *reinterpret_cast<void***>(static_cast<CxxComponent*>(&base));
    void** derived_vtable = *reinterpret_cast<void***>(static_cast<CxxComponent*>(&derived));

    bool result = base_vtable[slot] != derived_vtable[slot];
    printf("[component_overrides_update] base[%d]=%p derived[%d]=%p result=%d\n",
        slot, base_vtable[slot], slot, derived_vtable[slot], result ? 1 : 0);
    return result;
}

// Check if type T overrides CxxComponent::fixed_update().
template<typename T>
bool component_overrides_fixed_update() {
    int slot = VTableSlots::instance().fixed_update_slot;
    if (slot < 0) return false;

    ComponentVTableProbe base;
    T derived;

    void** base_vtable = *reinterpret_cast<void***>(static_cast<CxxComponent*>(&base));
    void** derived_vtable = *reinterpret_cast<void***>(static_cast<CxxComponent*>(&derived));

    return base_vtable[slot] != derived_vtable[slot];
}

} // namespace termin

// Macro for binding native C++ components to nanobind.
// Automatically sets up the factory with proper flag detection.
//
// Usage:
//   BIND_NATIVE_COMPONENT(m, MyComponent)
//       .def_rw("speed", &MyComponent::speed);
#ifdef TERMIN_HAS_NANOBIND
#include <nanobind/nanobind.h>
namespace nb = nanobind;

#define BIND_NATIVE_COMPONENT(module, ClassName) \
    nb::class_<ClassName, termin::CxxComponent>(module, #ClassName) \
        .def("__init__", [](ClassName* self) { \
            new (self) ClassName(); \
            self->set_type_name(#ClassName); \
            self->set_has_update(termin::component_overrides_update<ClassName>()); \
            self->set_has_fixed_update(termin::component_overrides_fixed_update<ClassName>()); \
        })
#endif // TERMIN_HAS_NANOBIND
