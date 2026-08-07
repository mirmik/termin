#pragma once

#include <optional>

#include <termin/robotics/articulation3d.hpp>

namespace termin::robotics::detail {
    // Internal cross-library bridge for formulations that integrate an
    // articulation. Normal kinematic consumers should use Articulation3D's
    // validated public setters instead of mutating its state in place.
    class Articulation3DMutableAccess {
    public:
        [[nodiscard]] static Articulation3DState& state(Articulation3D& articulation) noexcept {
            return articulation.state_;
        }

        [[nodiscard]] static std::optional<ArticulationFloatingBase3D>&
        floating_base(Articulation3D& articulation) noexcept {
            return articulation.floating_base_;
        }

        [[nodiscard]] static bool update_kinematics(Articulation3D& articulation) noexcept {
            return articulation.update_kinematics();
        }
    };
} // namespace termin::robotics::detail
