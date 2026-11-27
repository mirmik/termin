#pragma once

#include <array>
#include <cmath>
#include <cstddef>
#include <numbers>

namespace termin::physics_qopt::detail {
    // Cross section of the inscribed Coulomb polygon in contact tangent coordinates.
    struct FrictionPolygon {
        std::size_t sides;
        double apothem;

        [[nodiscard]] static constexpr bool valid_side_count(std::size_t count) noexcept {
            return count >= 4 && count % 2 == 0;
        }

        explicit FrictionPolygon(std::size_t count) noexcept
            : sides(count),
              apothem(std::cos(std::numbers::pi / static_cast<double>(count))) {}

        [[nodiscard]] std::array<double, 2> normal(std::size_t side) const noexcept {
            const double angle =
                (static_cast<double>(side) + 0.5) * 2.0 * std::numbers::pi / static_cast<double>(sides);
            return {std::cos(angle), std::sin(angle)};
        }

        [[nodiscard]] bool at_limit(double x, double y, double capacity) const noexcept {
            constexpr double relative_tolerance = 1e-8;
            const double limit = capacity * apothem * (1.0 - relative_tolerance);
            if (capacity <= 0.0 || std::hypot(x, y) < limit) {
                return false;
            }
            for (std::size_t side = 0; side < sides; ++side) {
                const auto n = normal(side);
                if (n[0] * x + n[1] * y >= limit) {
                    return true;
                }
            }
            return false;
        }
    };
} // namespace termin::physics_qopt::detail
