#pragma once

#include "component.hpp"
#include <string>

namespace termin {

// UnknownComponent - placeholder for components whose type is not registered.
//
// When a scene is loaded and a component type is not found (e.g., module not loaded
// or has errors), an UnknownComponent is created to preserve the data. When the
// module is loaded/fixed, the component can be upgraded to the real type.
class ENTITY_API UnknownComponent : public CxxComponent {
public:
    // Original type name (e.g., "MyCustomComponent")
    std::string original_type;

    // Original serialized data (preserved as tc_value dict)
    tc_value original_data = tc_value_nil();

public:
    UnknownComponent();
    ~UnknownComponent() override;

    // Serialize returns original type and data (not "UnknownComponent")
    // This ensures data is preserved correctly when scene is saved
    tc_value serialize() const override;

    // serialize_data returns original_data as-is
    tc_value serialize_data() const override;

    // deserialize_data stores the data for later upgrade
    void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;
};

} // namespace termin
