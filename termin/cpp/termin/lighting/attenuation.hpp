#pragma once

#include <cmath>
#include <algorithm>

namespace termin {

/**
 * Polynomial attenuation coefficients: w(d) = 1 / (k_c + k_l * d + k_q * d^2)
 *
 * Classic OpenGL-style attenuation model. For physically correct inverse-square
 * falloff, set k_c = k_l = 0 and k_q = 1, giving w(d) = 1 / d^2.
 */
struct AttenuationCoefficients {
    double constant = 1.0;
    double linear = 0.0;
    double quadratic = 0.0;

    AttenuationCoefficients() = default;
    AttenuationCoefficients(double c, double l, double q)
        : constant(c), linear(l), quadratic(q) {}

    /**
     * Evaluate attenuation weight for a given distance.
     */
    double evaluate(double distance) const {
        double d = std::max(distance, 0.0);
        double denom = constant + linear * d + quadratic * d * d;
        if (denom <= 0.0) return 0.0;
        return 1.0 / denom;
    }

    /**
     * Create coefficients that reach cutoff at the given range.
     *
     * With k_c = 1 and k_l = 0, the equation cutoff = 1 / (1 + k_q * r^2)
     * gives k_q = (1 / cutoff - 1) / r^2.
     */
    static AttenuationCoefficients match_range(double falloff_range, double cutoff = 0.01) {
        double r = std::max(falloff_range, 1e-6);
        double k_q = (1.0 / cutoff - 1.0) / (r * r);
        return AttenuationCoefficients(1.0, 0.0, k_q);
    }

    /**
     * Physical inverse-square attenuation: w(d) = 1 / d^2.
     */
    static AttenuationCoefficients inverse_square() {
        return AttenuationCoefficients(0.0, 0.0, 1.0);
    }
};

} // namespace termin
