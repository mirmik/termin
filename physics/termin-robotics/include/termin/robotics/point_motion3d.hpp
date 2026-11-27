#pragma once

#include <termin/geom/pose3.hpp>
#include <termin/geom/screw3.hpp>

namespace termin::robotics {

    // Position and linear velocity of one material point in the inertial frame.
    struct PointMotion3D {
        termin::Vec3 position_world = termin::Vec3::zero();
        termin::Vec3 velocity_world = termin::Vec3::zero();

        [[nodiscard]] static PointMotion3D from_local_point(const termin::Pose3& pose_world,
                                                            const termin::Screw3& velocity_local,
                                                            termin::Vec3 point_local) noexcept {
            return {pose_world.transform_point(point_local),
                    velocity_local.velocity_at_offset(point_local).rotated_by(pose_world.ang).lin};
        }
    };

} // namespace termin::robotics
