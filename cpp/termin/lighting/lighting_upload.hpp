#pragma once

#include <vector>
#include <string>
#include <cmath>

#include "termin/lighting/light.hpp"
#include "termin/render/shader_program.hpp"

namespace termin {

constexpr int MAX_LIGHTS = 8;

/**
 * Convert LightType to shader integer.
 * 0 = Directional, 1 = Point, 2 = Spot
 */
inline int light_type_to_int(LightType type) {
    switch (type) {
        case LightType::Directional: return 0;
        case LightType::Point: return 1;
        case LightType::Spot: return 2;
    }
    return 0;
}

/**
 * Upload lights array to shader uniforms.
 *
 * Uniforms:
 *   u_light_count: int
 *   u_light_type[i]: int (0=DIR, 1=POINT, 2=SPOT)
 *   u_light_color[i]: vec3
 *   u_light_intensity[i]: float
 *   u_light_direction[i]: vec3
 *   u_light_position[i]: vec3
 *   u_light_range[i]: float
 *   u_light_attenuation[i]: vec3 (constant, linear, quadratic)
 *   u_light_inner_angle[i]: float
 *   u_light_outer_angle[i]: float
 */
inline void upload_lights_to_shader(ShaderProgram* shader, const std::vector<Light>& lights) {
    int count = static_cast<int>(std::min(lights.size(), static_cast<size_t>(MAX_LIGHTS)));
    shader->set_uniform_int("u_light_count", count);

    for (int i = 0; i < count; ++i) {
        const Light& light = lights[i];
        std::string prefix = "u_light_";
        std::string idx = "[" + std::to_string(i) + "]";

        shader->set_uniform_int((prefix + "type" + idx).c_str(), light_type_to_int(light.type));
        shader->set_uniform_vec3((prefix + "color" + idx).c_str(), light.color);
        shader->set_uniform_float((prefix + "intensity" + idx).c_str(), static_cast<float>(light.intensity));
        shader->set_uniform_vec3((prefix + "direction" + idx).c_str(), light.direction);
        shader->set_uniform_vec3((prefix + "position" + idx).c_str(), light.position);

        float light_range = light.range.has_value() ? static_cast<float>(light.range.value()) : 1e9f;
        shader->set_uniform_float((prefix + "range" + idx).c_str(), light_range);

        // Attenuation coefficients: constant, linear, quadratic
        shader->set_uniform_vec3((prefix + "attenuation" + idx).c_str(),
            static_cast<float>(light.attenuation.constant),
            static_cast<float>(light.attenuation.linear),
            static_cast<float>(light.attenuation.quadratic));

        shader->set_uniform_float((prefix + "inner_angle" + idx).c_str(), static_cast<float>(light.inner_angle));
        shader->set_uniform_float((prefix + "outer_angle" + idx).c_str(), static_cast<float>(light.outer_angle));
    }
}

/**
 * Upload ambient lighting uniforms.
 *
 * Uniforms:
 *   u_ambient_color: vec3
 *   u_ambient_intensity: float
 */
inline void upload_ambient_to_shader(ShaderProgram* shader, const Vec3& ambient_color, float ambient_intensity) {
    shader->set_uniform_vec3("u_ambient_color", ambient_color);
    shader->set_uniform_float("u_ambient_intensity", ambient_intensity);
}

} // namespace termin
