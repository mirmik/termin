#include <termin/physics_qopt/multibody2d.hpp>

#include "multibody_oracle_case.hpp"
#include "test_check.hpp"

#include <algorithm>
#include <cmath>
#include <iterator>

using namespace termin;
using namespace termin::physics_qopt;

namespace {

    Vec2 vec(OracleVec2 value) {
        return {value.x, value.y};
    }

    RigidBody2DState state(const OracleBody2D& body) {
        return {
            {body.initial_pose[2], {body.initial_pose[0], body.initial_pose[1]}},
            {body.initial_velocity[0], body.initial_velocity[1]},
            body.initial_velocity[2],
        };
    }

    bool finite_state(RigidBody2DState body, double limit) {
        return std::isfinite(body.pose.lin.x) && std::isfinite(body.pose.lin.y) && std::isfinite(body.pose.ang) &&
               std::isfinite(body.linear_velocity_world.x) && std::isfinite(body.linear_velocity_world.y) &&
               std::isfinite(body.angular_velocity) && std::abs(body.pose.lin.x) < limit &&
               std::abs(body.pose.lin.y) < limit && std::abs(body.pose.ang) < limit;
    }

} // namespace

int main() {
    const auto& oracle = kDoublePendulumOracle;
    Multibody2DSystem system;
    const auto first = system.add_body(
        {
            oracle.bodies[0].mass,
            oracle.bodies[0].inertia,
            vec(oracle.bodies[0].center_of_mass_local),
        },
        state(oracle.bodies[0]),
        "upper_link");
    const auto second = system.add_body(
        {
            oracle.bodies[1].mass,
            oracle.bodies[1].inertia,
            vec(oracle.bodies[1].center_of_mass_local),
        },
        state(oracle.bodies[1]),
        "lower_link");
    TERMIN_QOPT_CHECK(first.ok());
    TERMIN_QOPT_CHECK(second.ok());
    TERMIN_QOPT_CHECK(system
                          .add_fixed_point_joint(
                              first.handle, vec(oracle.body_a_fixed_anchor), vec(oracle.world_anchor), "world_anchor")
                          .ok());
    TERMIN_QOPT_CHECK(system
                          .add_revolute_joint(first.handle,
                                              vec(oracle.body_a_revolute_anchor),
                                              second.handle,
                                              vec(oracle.body_b_revolute_anchor),
                                              "link_joint")
                          .ok());
    TERMIN_QOPT_CHECK(system.finalize() == Multibody2DDiagnostic::None);

    const Vec2 gravity = vec(oracle.gravity);
    const double initial_energy = system.total_energy(gravity);
    double max_constraint = 0.0;
    std::size_t sample_index = 0;
    for (std::size_t step = 0; step <= oracle.steps; ++step) {
        if (sample_index < std::size(oracle.sample_steps) && step == oracle.sample_steps[sample_index]) {
            max_constraint = std::max(max_constraint, system.max_position_constraint_error());
            TERMIN_QOPT_CHECK(finite_state(system.body_state(first.handle), oracle.finite_state_limit));
            TERMIN_QOPT_CHECK(finite_state(system.body_state(second.handle), oracle.finite_state_limit));
            ++sample_index;
        }
        if (step == oracle.steps) {
            break;
        }
        const Multibody2DStepResult result = system.step(gravity,
                                                         {
                                                             .time_step = oracle.time_step,
                                                             .position_tolerance = 1e-9,
                                                             .velocity_tolerance = 1e-9,
                                                             .max_position_iterations = 4,
                                                             .qp_tolerance = {},
                                                         });
        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
    }

    const double final_energy = system.total_energy(gravity);
    const double relative_energy_drift =
        std::abs(final_energy - initial_energy) / std::max(1.0, std::abs(initial_energy));
    TERMIN_QOPT_CHECK(sample_index == std::size(oracle.sample_steps));
    TERMIN_QOPT_CHECK(max_constraint <= oracle.constraint_linf);
    TERMIN_QOPT_CHECK(system.max_velocity_constraint_error() <= oracle.constraint_linf);
    TERMIN_QOPT_CHECK(relative_energy_drift <= oracle.relative_energy_drift);
    return 0;
}
