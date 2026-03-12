#include "termin/lighting/light_component.hpp"

#include <tc_inspect_cpp.hpp>
#include <termin/entity/component_registry.hpp>

namespace termin {

LightComponent::LightComponent() {
    link_type_entry("LightComponent");
}

std::string LightComponent::get_light_type_str() const {
    return light_type_to_string(light_type);
}

void LightComponent::set_light_type_str(const std::string& type) {
    light_type = light_type_from_string(type);
}

Light LightComponent::to_light() const {
    Light l;
    l.type = light_type;
    l.color = color;
    l.intensity = intensity;
    l.shadows = shadows;

    if (entity().valid()) {
        auto pose = entity().transform().global_pose();
        Vec3 forward = pose.ang.rotate(Vec3(0.0, 1.0, 0.0));
        l.direction = forward;
        l.position = pose.lin;
    }

    return l;
}

REGISTER_COMPONENT(LightComponent, CxxComponent);

static struct _LightTypeFieldRegistrar {
    _LightTypeFieldRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "LightComponent";
        info.path = "light_type";
        info.label = "Light Type";
        info.kind = "string";

        info.choices.push_back({"directional", "Directional"});
        info.choices.push_back({"point", "Point"});
        info.choices.push_back({"spot", "Spot"});

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<LightComponent*>(obj);
            return tc_value_string(c->get_light_type_str().c_str());
        };

        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<LightComponent*>(obj);
            if (value.type == TC_VALUE_STRING && value.data.s) {
                c->set_light_type_str(value.data.s);
                return;
            }
            if (value.type == TC_VALUE_INT) {
                c->light_type = static_cast<LightType>(value.data.i);
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("LightComponent", std::move(info));
    }
} _light_type_registrar;

static struct _LightColorFieldRegistrar {
    _LightColorFieldRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "LightComponent";
        info.path = "color";
        info.label = "Color";
        info.kind = "color";

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<LightComponent*>(obj);
            tc_vec3 v = {c->color.x, c->color.y, c->color.z};
            return tc_value_vec3(v);
        };

        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<LightComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->color = Vec3(value.data.v3.x, value.data.v3.y, value.data.v3.z);
                return;
            }
            if (value.type == TC_VALUE_LIST && tc_value_list_size(&value) == 3) {
                tc_value* r = tc_value_list_get(&value, 0);
                tc_value* g = tc_value_list_get(&value, 1);
                tc_value* b = tc_value_list_get(&value, 2);
                auto get_double = [](tc_value* v) -> double {
                    if (!v) return 0.0;
                    if (v->type == TC_VALUE_DOUBLE) return v->data.d;
                    if (v->type == TC_VALUE_FLOAT) return v->data.f;
                    if (v->type == TC_VALUE_INT) return static_cast<double>(v->data.i);
                    return 0.0;
                };
                c->color = Vec3(get_double(r), get_double(g), get_double(b));
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("LightComponent", std::move(info));
    }
} _light_color_registrar;

INSPECT_FIELD(LightComponent, intensity, "Intensity", "double", 0.0, 100.0, 0.1)

static struct _LightShadowFieldsRegistrar {
    _LightShadowFieldsRegistrar() {
        {
            tc::InspectFieldInfo info;
            info.type_name = "LightComponent";
            info.path = "shadows_enabled";
            info.label = "Cast Shadows";
            info.kind = "bool";
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<LightComponent*>(obj);
                return tc_value_bool(c->shadows.enabled);
            };
            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<LightComponent*>(obj);
                if (value.type == TC_VALUE_BOOL) {
                    c->shadows.enabled = value.data.b;
                    return;
                }
                if (value.type == TC_VALUE_INT) {
                    c->shadows.enabled = value.data.i != 0;
                }
            };
            tc::InspectRegistry::instance().add_field_with_choices("LightComponent", std::move(info));
        }

        {
            tc::InspectFieldInfo info;
            info.type_name = "LightComponent";
            info.path = "shadows_map_resolution";
            info.label = "Shadow Resolution";
            info.kind = "int";
            info.min = 256;
            info.max = 4096;
            info.step = 256;
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<LightComponent*>(obj);
                return tc_value_int(c->shadows.map_resolution);
            };
            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<LightComponent*>(obj);
                if (value.type == TC_VALUE_INT) c->shadows.map_resolution = static_cast<int>(value.data.i);
                if (value.type == TC_VALUE_FLOAT) c->shadows.map_resolution = static_cast<int>(value.data.f);
                if (value.type == TC_VALUE_DOUBLE) c->shadows.map_resolution = static_cast<int>(value.data.d);
            };
            tc::InspectRegistry::instance().add_field_with_choices("LightComponent", std::move(info));
        }

        {
            tc::InspectFieldInfo info;
            info.type_name = "LightComponent";
            info.path = "cascade_count";
            info.label = "Cascade Count";
            info.kind = "int";
            info.min = 1;
            info.max = 4;
            info.step = 1;
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<LightComponent*>(obj);
                return tc_value_int(c->shadows.cascade_count);
            };
            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<LightComponent*>(obj);
                if (value.type == TC_VALUE_INT) c->shadows.cascade_count = static_cast<int>(value.data.i);
                if (value.type == TC_VALUE_FLOAT) c->shadows.cascade_count = static_cast<int>(value.data.f);
                if (value.type == TC_VALUE_DOUBLE) c->shadows.cascade_count = static_cast<int>(value.data.d);
            };
            tc::InspectRegistry::instance().add_field_with_choices("LightComponent", std::move(info));
        }

        {
            tc::InspectFieldInfo info;
            info.type_name = "LightComponent";
            info.path = "max_distance";
            info.label = "Max Distance";
            info.kind = "float";
            info.min = 1.0;
            info.max = 1000.0;
            info.step = 10.0;
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<LightComponent*>(obj);
                return tc_value_float(c->shadows.max_distance);
            };
            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<LightComponent*>(obj);
                if (value.type == TC_VALUE_FLOAT) c->shadows.max_distance = value.data.f;
                if (value.type == TC_VALUE_DOUBLE) c->shadows.max_distance = static_cast<float>(value.data.d);
                if (value.type == TC_VALUE_INT) c->shadows.max_distance = static_cast<float>(value.data.i);
            };
            tc::InspectRegistry::instance().add_field_with_choices("LightComponent", std::move(info));
        }

        {
            tc::InspectFieldInfo info;
            info.type_name = "LightComponent";
            info.path = "split_lambda";
            info.label = "Split Lambda";
            info.kind = "float";
            info.min = 0.0;
            info.max = 1.0;
            info.step = 0.1;
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<LightComponent*>(obj);
                return tc_value_float(c->shadows.split_lambda);
            };
            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<LightComponent*>(obj);
                if (value.type == TC_VALUE_FLOAT) c->shadows.split_lambda = value.data.f;
                if (value.type == TC_VALUE_DOUBLE) c->shadows.split_lambda = static_cast<float>(value.data.d);
                if (value.type == TC_VALUE_INT) c->shadows.split_lambda = static_cast<float>(value.data.i);
            };
            tc::InspectRegistry::instance().add_field_with_choices("LightComponent", std::move(info));
        }

        {
            tc::InspectFieldInfo info;
            info.type_name = "LightComponent";
            info.path = "cascade_blend";
            info.label = "Cascade Blend";
            info.kind = "bool";
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<LightComponent*>(obj);
                return tc_value_bool(c->shadows.cascade_blend);
            };
            info.setter = [](void* obj, tc_value value, void*) {
                auto* c = static_cast<LightComponent*>(obj);
                if (value.type == TC_VALUE_BOOL) {
                    c->shadows.cascade_blend = value.data.b;
                    return;
                }
                if (value.type == TC_VALUE_INT) {
                    c->shadows.cascade_blend = value.data.i != 0;
                }
            };
            tc::InspectRegistry::instance().add_field_with_choices("LightComponent", std::move(info));
        }
    }
} _light_shadow_fields_registrar;

} // namespace termin
