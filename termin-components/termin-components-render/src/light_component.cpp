#include "termin/lighting/light_component.hpp"

#include <tc_inspect_cpp.hpp>
#include <termin/entity/component_registry.hpp>

extern "C" {
#include "core/tc_light_capability.h"
}

namespace termin {

// Light capability vtable callback
static bool light_cap_get_data(tc_component* self, tc_light_data* out) {
    if (!self || !out) return false;
    CxxComponent* cxx = CxxComponent::from_tc(self);
    if (!cxx) return false;
    LightComponent* lc = static_cast<LightComponent*>(cxx);
    Light l = lc->to_light();

    out->type = static_cast<tc_light_type>(l.type);
    out->color[0] = l.color.x;
    out->color[1] = l.color.y;
    out->color[2] = l.color.z;
    out->intensity = l.intensity;
    out->direction[0] = l.direction.x;
    out->direction[1] = l.direction.y;
    out->direction[2] = l.direction.z;
    out->position[0] = l.position.x;
    out->position[1] = l.position.y;
    out->position[2] = l.position.z;
    out->has_range = l.range.has_value();
    out->range = l.range.value_or(0.0);
    out->inner_angle = l.inner_angle;
    out->outer_angle = l.outer_angle;
    out->shadows.enabled = l.shadows.enabled;
    out->shadows.bias = l.shadows.bias;
    out->shadows.normal_bias = l.shadows.normal_bias;
    out->shadows.map_resolution = l.shadows.map_resolution;
    out->shadows.cascade_count = l.shadows.cascade_count;
    out->shadows.max_distance = l.shadows.max_distance;
    out->shadows.split_lambda = l.shadows.split_lambda;
    out->shadows.cascade_blend = l.shadows.cascade_blend;
    out->shadows.blend_distance = l.shadows.blend_distance;
    return true;
}

static const tc_light_vtable g_light_vtable = {
    .get_light_data = light_cap_get_data,
};

LightComponent::LightComponent() {
    link_type_entry("LightComponent");
    tc_light_capability_attach(&_c, &g_light_vtable, this);
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
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(c->color.x));
            tc_value_list_push(&list, tc_value_double(c->color.y));
            tc_value_list_push(&list, tc_value_double(c->color.z));
            return list;
        };

        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<LightComponent*>(obj);
            if (value.type == TC_VALUE_LIST && tc_value_list_size(&value) >= 3) {
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
