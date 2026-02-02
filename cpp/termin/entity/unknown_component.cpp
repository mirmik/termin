#include "unknown_component.hpp"
#include "component_registry.hpp"
#include "tc_inspect_cpp.hpp"

namespace termin {

UnknownComponent::UnknownComponent() {
    link_type_entry("UnknownComponent");
    // Disabled by default since it's a placeholder
    set_enabled(false);
}

UnknownComponent::~UnknownComponent() {
    tc_value_free(&original_data);
}

tc_value UnknownComponent::serialize() const {
    // Return original type and data, not "UnknownComponent"
    // This preserves the data correctly when scene is saved
    tc_value result = tc_value_dict_new();

    if (!original_type.empty()) {
        tc_value_dict_set(&result, "type", tc_value_string(original_type.c_str()));
    } else {
        tc_value_dict_set(&result, "type", tc_value_string("UnknownComponent"));
    }

    // Copy original_data
    tc_value data_copy = tc_value_copy(&original_data);
    tc_value_dict_set(&result, "data", data_copy);

    return result;
}

tc_value UnknownComponent::serialize_data() const {
    // Return a copy of original_data
    return tc_value_copy(&original_data);
}

void UnknownComponent::deserialize_data(const tc_value* data, tc_scene_handle scene) {
    (void)scene;
    // Free old data and store new
    tc_value_free(&original_data);
    if (data) {
        original_data = tc_value_copy(data);
    } else {
        original_data = tc_value_dict_new();
    }
}

REGISTER_COMPONENT(UnknownComponent, CxxComponent);

// Register original_type field (read-only in inspector)
static struct _UnknownComponentFieldRegistrar {
    _UnknownComponentFieldRegistrar() {
        // original_type field
        {
            tc::InspectFieldInfo info;
            info.type_name = "UnknownComponent";
            info.path = "original_type";
            info.label = "Original Type";
            info.kind = "string";
            info.is_inspectable = true;
            info.is_serializable = true;

            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<UnknownComponent*>(obj);
                return tc_value_string(c->original_type.c_str());
            };

            info.setter = [](void* obj, tc_value value, tc_scene_handle) {
                auto* c = static_cast<UnknownComponent*>(obj);
                if (value.type == TC_VALUE_STRING && value.data.s) {
                    c->original_type = value.data.s;
                }
            };

            tc::InspectRegistry::instance().add_field_with_choices("UnknownComponent", std::move(info));
        }

        // original_data field (dict, not shown in inspector but serializable)
        {
            tc::InspectFieldInfo info;
            info.type_name = "UnknownComponent";
            info.path = "original_data";
            info.label = "Original Data";
            info.kind = "dict";
            info.is_inspectable = false;  // Don't show in inspector
            info.is_serializable = true;

            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<UnknownComponent*>(obj);
                return tc_value_copy(&c->original_data);
            };

            info.setter = [](void* obj, tc_value value, tc_scene_handle) {
                auto* c = static_cast<UnknownComponent*>(obj);
                tc_value_free(&c->original_data);
                c->original_data = tc_value_copy(&value);
            };

            tc::InspectRegistry::instance().add_field_with_choices("UnknownComponent", std::move(info));
        }
    }
} _unknown_component_registrar;

} // namespace termin
