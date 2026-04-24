// soa_components.hpp - Built-in SoA data components
#pragma once

#include "soa_type.hpp"

struct Velocity {
    float dx = 0.0f;
    float dy = 0.0f;
    float dz = 0.0f;
};
SOA_COMPONENT(Velocity);
