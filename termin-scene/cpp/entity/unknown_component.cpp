#include <termin/entity/unknown_component.hpp>

#include <termin/entity/component_registry.hpp>
#include <tc_inspect_cpp.hpp>

namespace termin {

UnknownComponent::UnknownComponent() {
    link_type_entry("UnknownComponent");
    set_enabled(false);
}

UnknownComponent::~UnknownComponent() {
    tc_value_free(&original_data);
}

tc_value UnknownComponent::serialize() const {
    tc_value result = tc_value_dict_new();

    if (!original_type.empty()) {
        tc_value_dict_set(&result, "type", tc_value_string(original_type.c_str()));
    } else {
        tc_value_dict_set(&result, "type", tc_value_string("UnknownComponent"));
    }

    tc_value data_copy = tc_value_copy(&original_data);
    tc_value_dict_set(&result, "data", data_copy);
    return result;
}

tc_value UnknownComponent::serialize_data() const {
    return tc_value_copy(&original_data);
}

void UnknownComponent::deserialize_data(const tc_value* data, tc_scene_handle scene) {
    (void)scene;
    tc_value_free(&original_data);
    if (data) {
        original_data = tc_value_copy(data);
    } else {
        original_data = tc_value_dict_new();
    }
}

REGISTER_COMPONENT(UnknownComponent, CxxComponent);

static struct UnknownComponentFieldRegistrar {
    UnknownComponentFieldRegistrar() {
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

            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<UnknownComponent*>(obj);
                if (value.type == TC_VALUE_STRING && value.data.s) {
                    c->original_type = value.data.s;
                }
            };

            tc::InspectRegistry::instance().add_field_with_choices("UnknownComponent", std::move(info));
        }

        {
            tc::InspectFieldInfo info;
            info.type_name = "UnknownComponent";
            info.path = "original_data";
            info.label = "Original Data";
            info.kind = "dict";
            info.is_inspectable = false;
            info.is_serializable = true;

            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<UnknownComponent*>(obj);
                return tc_value_copy(&c->original_data);
            };

            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<UnknownComponent*>(obj);
                tc_value_free(&c->original_data);
                c->original_data = tc_value_copy(&value);
            };

            tc::InspectRegistry::instance().add_field_with_choices("UnknownComponent", std::move(info));
        }
    }
} unknown_component_field_registrar;

} // namespace termin
