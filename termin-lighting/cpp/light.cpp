#include <termin/lighting/light.hpp>

namespace termin {

Vec3 Light::intensity_rgb() const {
    return color * intensity;
}

LightSample Light::sample(const Vec3& point) const {
    if (type == LightType::Directional) {
        const Vec3 incoming = direction.normalized() * -1.0;
        return LightSample{
            incoming,
            std::numeric_limits<double>::infinity(),
            1.0,
            intensity_rgb(),
        };
    }

    const Vec3 to_light = position - point;
    const double distance = to_light.norm();
    const Vec3 light_direction = distance > 1e-6 ? to_light / distance : Vec3(0.0, 1.0, 0.0);

    double attenuation_weight = distance_weight(distance);
    if (type == LightType::Spot) {
        attenuation_weight *= spot_weight(light_direction);
    }

    return LightSample{
        light_direction,
        distance,
        attenuation_weight,
        intensity_rgb() * attenuation_weight,
    };
}

double Light::distance_weight(double distance) const {
    double weight = attenuation.evaluate(distance);
    if (range.has_value() && distance > range.value()) {
        weight = 0.0;
    }
    return weight;
}

double Light::spot_weight(const Vec3& light_direction) const {
    const double cos_theta = direction.dot(light_direction * -1.0);
    const double cos_outer = std::cos(outer_angle);
    const double cos_inner = std::cos(inner_angle);

    if (cos_theta <= cos_outer) return 0.0;
    if (cos_theta >= cos_inner) return 1.0;

    const double t = (cos_theta - cos_outer) / (cos_inner - cos_outer);
    return t * t * (3.0 - 2.0 * t);
}

} // namespace termin
