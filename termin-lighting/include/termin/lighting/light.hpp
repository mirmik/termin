#pragma once

#define _USE_MATH_DEFINES

#include <cmath>
#include <limits>
#include <optional>
#include <string>

#include <termin/geom/vec3.hpp>
#include <termin/lighting/attenuation.hpp>
#include <termin/lighting/termin_lighting_api.hpp>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

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

struct LightShadowParams {
public:
    bool enabled = false;
    double bias = 0.001;
    double normal_bias = 0.0;
    int map_resolution = 1024;
    int cascade_count = 1;
    float max_distance = 100.0f;
    float split_lambda = 0.5f;
    bool cascade_blend = true;
    float blend_distance = 2.0f;

public:
    LightShadowParams() = default;

    LightShadowParams(bool en, double b, double nb, int res)
        : enabled(en), bias(b), normal_bias(nb), map_resolution(res) {}
};

struct LightSample {
public:
    Vec3 L;
    double distance;
    double attenuation;
    Vec3 radiance;
};

struct TERMIN_LIGHTING_API Light {
public:
    LightType type = LightType::Directional;
    Vec3 color = Vec3(1.0, 1.0, 1.0);
    double intensity = 1.0;
    Vec3 direction = Vec3(0.0, 1.0, 0.0);
    Vec3 position = Vec3(0.0, 0.0, 0.0);
    std::optional<double> range;
    double inner_angle = 15.0 * M_PI / 180.0;
    double outer_angle = 30.0 * M_PI / 180.0;
    AttenuationCoefficients attenuation;
    LightShadowParams shadows;
    std::string name;

public:
    Light() = default;

    Vec3 intensity_rgb() const;

    LightSample sample(const Vec3& point) const;

private:
    double distance_weight(double dist) const;

    double spot_weight(const Vec3& L) const;
};

} // namespace termin
