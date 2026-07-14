#include "guard_main.h"

#include <cmath>
#include <limits>

#include <termin/lighting/light.hpp>

TEST_CASE("Directional lights have infinite distance and no attenuation") {
    termin::Light light;
    light.type = termin::LightType::Directional;
    light.color = termin::Vec3(0.5, 0.25, 1.0);
    light.intensity = 2.0;
    light.direction = termin::Vec3(0.0, -2.0, 0.0);

    const termin::LightSample sample = light.sample(termin::Vec3(5.0, 4.0, 3.0));
    CHECK(std::isinf(sample.distance));
    CHECK_EQ(sample.attenuation, 1.0);
    CHECK_EQ(sample.L.y, 1.0);
    CHECK_EQ(sample.radiance.x, 1.0);
    CHECK_EQ(sample.radiance.y, 0.5);
    CHECK_EQ(sample.radiance.z, 2.0);
}

TEST_CASE("Point and spot lights preserve range and cone boundaries") {
    termin::Light light;
    light.type = termin::LightType::Point;
    light.position = termin::Vec3(0.0, 0.0, 0.0);
    light.range = 2.0;

    CHECK_EQ(light.sample(termin::Vec3(3.0, 0.0, 0.0)).attenuation, 0.0);
    CHECK(light.sample(termin::Vec3(0.0, 0.0, 0.0)).attenuation > 0.0);

    light.type = termin::LightType::Spot;
    light.direction = termin::Vec3(0.0, 0.0, -1.0);
    light.inner_angle = 0.25;
    light.outer_angle = 0.5;
    light.range.reset();

    const termin::LightSample inside = light.sample(termin::Vec3(0.0, 0.0, -1.0));
    const termin::LightSample outside = light.sample(termin::Vec3(1.0, 0.0, 0.0));
    CHECK(inside.attenuation > 0.0);
    CHECK_EQ(outside.attenuation, 0.0);
}

GUARD_TEST_MAIN();
