#pragma once

#include "../export.hpp"
#include "../entity/component.hpp"
#include "../geom/vec3.hpp"
#include "light.hpp"

namespace termin {

// LightComponent - component that provides a light source.
// Uses entity transform for direction/position.
class ENTITY_API LightComponent : public CxxComponent {
public:
    // Light type
    LightType light_type = LightType::Directional;

    // Color (RGB, 0-1)
    Vec3 color = Vec3(1.0, 1.0, 1.0);

    // Intensity multiplier
    double intensity = 1.0;

    // Shadow parameters
    LightShadowParams shadows;

public:
    LightComponent();

    // Type accessors (for serialization as string)
    std::string get_light_type_str() const;
    void set_light_type_str(const std::string& type);

    // Shadow accessors
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

    // Convert to Light object for rendering
    // Uses entity transform for direction (Directional) or position (Point/Spot)
    Light to_light() const;
};

} // namespace termin
