#pragma once

namespace termin {

/**
 * Shadow rendering settings.
 *
 * Attributes:
 *   method: Shadow sampling method (0=hard, 1=pcf, 2=poisson)
 *   softness: Sampling radius multiplier (0=sharp, 1=default, >1=softer)
 *   bias: Depth bias to prevent shadow acne
 */
struct ShadowSettings {
    // Method constants
    static constexpr int METHOD_HARD = 0;
    static constexpr int METHOD_PCF = 1;
    static constexpr int METHOD_POISSON = 2;

    int method = METHOD_PCF;
    double softness = 1.0;
    double bias = 0.005;

    ShadowSettings() = default;
    ShadowSettings(int method_, double softness_, double bias_)
        : method(method_), softness(softness_), bias(bias_) {}
};

} // namespace termin
