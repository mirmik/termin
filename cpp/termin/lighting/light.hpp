#pragma once

#define _USE_MATH_DEFINES
#include <cmath>
#include <string>
#include <optional>
#include <limits>
#include "termin/geom/vec3.hpp"
#include "termin/lighting/attenuation.hpp"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

/**
 * Supported light types.
 */
enum class LightType {
    Directional,
    Point,
    Spot
};

inline const char* light_type_to_string(LightType t) {
    switch (t) {
        case LightType::Directional: return "directional";
        case LightType::Point: return "point";
        case LightType::Spot: return "spot";
    }
    return "unknown";
}

inline LightType light_type_from_string(const std::string& s) {
    if (s == "directional") return LightType::Directional;
    if (s == "point") return LightType::Point;
    if (s == "spot") return LightType::Spot;
    return LightType::Directional;
}

/**
 * Shadow map parameters for a light source.
 */
struct LightShadowParams {
    bool enabled = false;
    double bias = 0.001;
    double normal_bias = 0.0;
    int map_resolution = 1024;

    LightShadowParams() = default;
    LightShadowParams(bool en, double b, double nb, int res)
        : enabled(en), bias(b), normal_bias(nb), map_resolution(res) {}
};

/**
 * Result of evaluating light contribution at a surface point.
 *
 * L: direction from surface point towards light source (for dot products)
 * radiance: L_o = attenuation * intensity_rgb
 */
struct LightSample {
    Vec3 L;             // Direction to light (normalized)
    double distance;    // Distance to light (inf for directional)
    double attenuation; // Attenuation factor [0, 1]
    Vec3 radiance;      // Final radiance contribution
};

/**
 * Light source with classic rendering parameters.
 *
 * Coordinate convention: Y-forward, Z-up
 *   - X: right
 *   - Y: forward (depth)
 *   - Z: up
 *
 * direction: axis of the light source (from light into scene).
 * For directional lights, default is +Y (forward/into scene).
 */
struct Light {
    LightType type = LightType::Directional;
    Vec3 color = Vec3(1.0, 1.0, 1.0);
    double intensity = 1.0;
    Vec3 direction = Vec3(0.0, 1.0, 0.0);  // Default: +Y (forward)
    Vec3 position = Vec3(0.0, 0.0, 0.0);
    std::optional<double> range;
    double inner_angle = 15.0 * M_PI / 180.0;  // radians
    double outer_angle = 30.0 * M_PI / 180.0;  // radians
    AttenuationCoefficients attenuation;
    LightShadowParams shadows;
    std::string name;

    Light() = default;

    /**
     * RGB intensity vector: I = intensity * color.
     */
    Vec3 intensity_rgb() const {
        return color * intensity;
    }

    /**
     * Evaluate light contribution at a surface point.
     */
    LightSample sample(const Vec3& point) const {
        if (type == LightType::Directional) {
            Vec3 incoming = direction.normalized() * -1.0;
            return LightSample{
                incoming,
                std::numeric_limits<double>::infinity(),
                1.0,
                intensity_rgb()
            };
        }

        Vec3 to_light = position - point;
        double dist = to_light.norm();
        Vec3 L = (dist > 1e-6) ? to_light / dist : Vec3(0.0, 1.0, 0.0);

        double atten = distance_weight(dist);
        if (type == LightType::Spot) {
            atten *= spot_weight(L);
        }

        return LightSample{
            L,
            dist,
            atten,
            intensity_rgb() * atten
        };
    }

private:
    double distance_weight(double dist) const {
        double w = attenuation.evaluate(dist);
        if (range.has_value() && dist > range.value()) {
            w = 0.0;
        }
        return w;
    }

    /**
     * Smooth spotlight weight based on angle from axis.
     * Uses smoothstep: w = clamp((cos(theta) - cos_o) / (cos_i - cos_o), 0, 1)
     */
    double spot_weight(const Vec3& L) const {
        double cos_theta = direction.dot(L * -1.0);
        double cos_outer = std::cos(outer_angle);
        double cos_inner = std::cos(inner_angle);

        if (cos_theta <= cos_outer) return 0.0;
        if (cos_theta >= cos_inner) return 1.0;

        double t = (cos_theta - cos_outer) / (cos_inner - cos_outer);
        return t * t * (3.0 - 2.0 * t);  // smoothstep
    }
};

} // namespace termin
