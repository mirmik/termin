#pragma once

#include <termin/entity/component.hpp>
#include <string>

namespace termin {

// Placeholder for components whose type is not currently registered.
//
// When scene deserialization encounters an unavailable type, UnknownComponent
// preserves its serialized payload so it can be upgraded later when the real
// component type becomes available again.
class ENTITY_API UnknownComponent : public CxxComponent {
public:
    std::string original_type;
    tc_value original_data = tc_value_nil();
    // True only for placeholders created from live components during module unload.
    // Placeholders loaded from serialized unknown component data keep this false,
    // so their disabled runtime state does not override restored component defaults.
    bool preserve_runtime_state_on_upgrade = false;

public:
    UnknownComponent();
    ~UnknownComponent() override;

    static void register_type();

    tc_value serialize() const override;
    tc_value serialize_data() const override;
    void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;
};

ENTITY_API void register_builtin_scene_component_types();

} // namespace termin
