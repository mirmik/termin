#pragma once

#include <termin/entity/component.hpp>
#include <termin/export.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/render/light.hpp>

namespace termin {

class ENTITY_API LightComponent : public CxxComponent {
public:
    LightType light_type = LightType::Directional;
    Vec3 color = Vec3(1.0, 1.0, 1.0);
    double intensity = 1.0;
    LightShadowParams shadows;

public:
    LightComponent();

    std::string get_light_type_str() const;
    void set_light_type_str(const std::string& type);

    bool get_shadows_enabled() const { return shadows.enabled; }
    void set_shadows_enabled(bool v) { shadows.enabled = v; }

    int get_shadows_map_resolution() const { return shadows.map_resolution; }
    void set_shadows_map_resolution(int v) { shadows.map_resolution = v; }

    int get_cascade_count() const { return shadows.cascade_count; }
    void set_cascade_count(int v) { shadows.cascade_count = v; }

    float get_max_distance() const { return shadows.max_distance; }
    void set_max_distance(float v) { shadows.max_distance = v; }

    float get_split_lambda() const { return shadows.split_lambda; }
    void set_split_lambda(float v) { shadows.split_lambda = v; }

    bool get_cascade_blend() const { return shadows.cascade_blend; }
    void set_cascade_blend(bool v) { shadows.cascade_blend = v; }

    Light to_light() const;
};

} // namespace termin
