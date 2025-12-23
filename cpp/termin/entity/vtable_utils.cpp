#include "vtable_utils.hpp"

namespace termin {

// Force the probe classes to have their vtables emitted in this TU
// by defining a non-inline virtual function (the key function).
// This prevents the compiler from merging identical empty functions.
void UpdateProbe::update(float dt) { _probe_marker = dt; }
void FixedUpdateProbe::fixed_update(float dt) { _probe_marker = dt; }

VTableSlots VTableSlots::compute() {
    VTableSlots slots;

    ComponentVTableProbe base;
    UpdateProbe update_probe;
    FixedUpdateProbe fixed_update_probe;

    void** base_vt = *reinterpret_cast<void***>(static_cast<Component*>(&base));
    void** update_vt = *reinterpret_cast<void***>(static_cast<Component*>(&update_probe));
    void** fixed_vt = *reinterpret_cast<void***>(static_cast<Component*>(&fixed_update_probe));

    constexpr int max_slots = 16;
    for (int i = 0; i < max_slots; ++i) {
        bool differs_update = (base_vt[i] != update_vt[i]);
        bool differs_fixed = (base_vt[i] != fixed_vt[i]);

        // update slot: differs from UpdateProbe, but same as FixedUpdateProbe
        if (differs_update && !differs_fixed) {
            slots.update_slot = i;
        }
        // fixed_update slot: differs from FixedUpdateProbe, but same as UpdateProbe
        if (differs_fixed && !differs_update) {
            slots.fixed_update_slot = i;
        }
    }

    return slots;
}

} // namespace termin
