#include "scene_light_collector.hpp"

extern "C" {
#include "core/tc_light_capability.h"
#include "core/tc_scene.h"
}

namespace termin::rendering_manager_detail {

static bool collect_lights_cap_cb(tc_component* c, void* user_data) {
    std::vector<Light>* lights = static_cast<std::vector<Light>*>(user_data);
    const tc_light_capability* cap = tc_light_capability_get(c);
    if (!cap || !cap->vtable || !cap->vtable->get_light_data) return true;

    tc_light_data ld;
    if (!cap->vtable->get_light_data(c, &ld)) return true;

    Light light;
    light.type = static_cast<LightType>(ld.type);
    light.color = Vec3(ld.color[0], ld.color[1], ld.color[2]);
    light.intensity = ld.intensity;
    light.direction = Vec3(ld.direction[0], ld.direction[1], ld.direction[2]);
    light.position = Vec3(ld.position[0], ld.position[1], ld.position[2]);
    if (ld.has_range) light.range = ld.range;
    light.inner_angle = ld.inner_angle;
    light.outer_angle = ld.outer_angle;
    light.shadows.enabled = ld.shadows.enabled;
    light.shadows.bias = ld.shadows.bias;
    light.shadows.normal_bias = ld.shadows.normal_bias;
    light.shadows.map_resolution = ld.shadows.map_resolution;
    light.shadows.cascade_count = ld.shadows.cascade_count;
    light.shadows.max_distance = ld.shadows.max_distance;
    light.shadows.split_lambda = ld.shadows.split_lambda;
    light.shadows.cascade_blend = ld.shadows.cascade_blend;
    light.shadows.blend_distance = ld.shadows.blend_distance;
    lights->push_back(std::move(light));
    return true;
}

std::vector<Light> collect_lights(tc_scene_handle scene) {
    std::vector<Light> lights;
    if (!tc_scene_handle_valid(scene)) return lights;

    tc_component_cap_id light_cap = tc_light_capability_id();
    if (light_cap == TC_COMPONENT_CAPABILITY_INVALID_ID) return lights;

    tc_scene_foreach_with_capability(
        scene, light_cap, collect_lights_cap_cb, &lights,
        TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_ENTITY_ENABLED);

    return lights;
}

} // namespace termin::rendering_manager_detail
