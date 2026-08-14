#include <termin/robotics/robotics.hpp>

#include <array>
#include <cmath>
#include <cstdio>

using namespace termin;
using namespace termin::robotics;

namespace {
    ArticulationUnit3D planar_unit(std::size_t parent, double length) {
        return {
            .parent_unit = parent,
            .parent_to_unit_zero = Pose3::translation(length, 0.0, 0.0),
            .motion_twist_at_unit =
                Screw3{Vec3::unit_z(), Vec3::zero()}.adjoint_inv(Pose3::translation(length, 0.0, 0.0)),
            .inertia = SpatialInertia3{1.0, {0.1, 0.1, 0.1}, Pose3::identity()},
        };
    }
} // namespace

int main() {
    Articulation3D arm({planar_unit(articulation_root_frame, 0.7), planar_unit(0, 0.6)},
                       {{-0.8, 1.0}, {0.0, 0.0}},
                       "kinematic-example");
    VelocityHqpController3D controller(arm);
    constexpr double time_step = 0.01;
    const Vec3 target{0.8, 0.65, 0.0};

    for (std::size_t step = 0; step < 500; ++step) {
        const auto point = arm.point_kinematics(1, Vec3::zero());
        if (!point.ok()) {
            return 1;
        }
        PointVelocityTask3D point_task(1, Vec3::zero(), (target - point.value.position_world) * 3.0);
        JointVelocityLimitConstraint3D velocity_limit({}, {-2.0, -2.0}, {2.0, 2.0}, {.priority = 0});
        const std::array<const ArticulationTask3D*, 2> tasks{&velocity_limit, &point_task};
        const VelocityControlResult3D control = controller.solve(tasks, {.time_step = time_step});
        if (!control.ok() ||
            !integrate_articulation_velocity(
                 arm, {control.generalized_velocity.data(), control.generalized_velocity.size()}, time_step)
                 .ok()) {
            return 2;
        }
    }
    const auto final_point = arm.point_kinematics(1, Vec3::zero());
    const double error = (target - final_point.value.position_world).norm();
    std::printf("kinematic point error=%g\n", error);
    return error < 1.0e-4 ? 0 : 3;
}
