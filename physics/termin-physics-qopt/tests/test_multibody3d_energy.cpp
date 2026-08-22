#include <termin/physics_qopt/multibody3d.hpp>

#include "test_check.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <memory>

using namespace termin;
using namespace termin::physics_qopt;

namespace {

    template <typename Contribution>
    Contribution* add(Multibody3DSystem& system, std::unique_ptr<Contribution> contribution) {
        Contribution* result = contribution.get();
        TERMIN_QOPT_CHECK(system.add_contribution(std::move(contribution)) == DynamicsSystemDiagnostic::None);
        return result;
    }

    struct EnergyEnvelope {
        double initial = 0.0;
        double final = 0.0;
        double maximum_relative_drift = 0.0;
    };

    struct FreeBodyInvariantError {
        double maximum_relative_energy_drift = 0.0;
        double maximum_angular_momentum_error = 0.0;
    };

    void sample_energy(EnergyEnvelope& envelope, double energy) {
        envelope.final = energy;
        envelope.maximum_relative_drift =
            std::max(envelope.maximum_relative_drift,
                     std::abs(energy - envelope.initial) / std::max(1.0, std::abs(envelope.initial)));
    }

    Multibody3DStepOptions options(double dt) {
        return {
            .time_step = dt,
            .position_tolerance = 1e-10,
            .velocity_tolerance = 1e-10,
            .max_position_iterations = 10,
            .qp_tolerance = {},
        };
    }

    EnergyEnvelope simulate_single_pendulum(double dt, double duration) {
        Multibody3DSystem system;
        auto* body =
            add(system,
                std::make_unique<RigidBody3DContribution>(SpatialInertia3{1.0, {0.01, 1.0 / 12.0, 1.0 / 12.0}, {}},
                                                          RigidBody3DState{
                                                              {Quat::identity(), {0.5, 0.0, 0.0}},
                                                              Screw3::zero(),
                                                          },
                                                          Vec3{0.0, 0.0, -9.81},
                                                          "pendulum"));
        add(system,
            std::make_unique<FixedRevoluteJoint3DContribution>(
                *body, Vec3{-0.5, 0.0, 0.0}, Vec3::unit_y(), Vec3::zero(), Vec3::unit_y(), "world-hinge"));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

        EnergyEnvelope result;
        result.initial = body->total_energy();
        result.final = result.initial;
        const std::size_t steps = static_cast<std::size_t>(std::llround(duration / dt));
        for (std::size_t step = 0; step < steps; ++step) {
            TERMIN_QOPT_CHECK(system.step(options(dt)).ok());
            sample_energy(result, body->total_energy());
        }
        return result;
    }

    EnergyEnvelope simulate_double_pendulum(double dt, double duration) {
        Multibody3DSystem system;
        const SpatialInertia3 inertia{1.0, {0.01, 1.0 / 12.0, 1.0 / 12.0}, {}};
        auto* upper = add(system,
                          std::make_unique<RigidBody3DContribution>(inertia,
                                                                    RigidBody3DState{
                                                                        {Quat::identity(), {0.5, 0.0, 0.0}},
                                                                        Screw3::zero(),
                                                                    },
                                                                    Vec3{0.0, 0.0, -9.81},
                                                                    "upper"));
        auto* lower = add(system,
                          std::make_unique<RigidBody3DContribution>(inertia,
                                                                    RigidBody3DState{
                                                                        {Quat::identity(), {1.5, 0.0, 0.0}},
                                                                        Screw3::zero(),
                                                                    },
                                                                    Vec3{0.0, 0.0, -9.81},
                                                                    "lower"));
        add(system,
            std::make_unique<FixedRevoluteJoint3DContribution>(
                *upper, Vec3{-0.5, 0.0, 0.0}, Vec3::unit_y(), Vec3::zero(), Vec3::unit_y(), "world-hinge"));
        add(system,
            std::make_unique<RevoluteJoint3DContribution>(*upper,
                                                          Vec3{0.5, 0.0, 0.0},
                                                          Vec3::unit_y(),
                                                          *lower,
                                                          Vec3{-0.5, 0.0, 0.0},
                                                          Vec3::unit_y(),
                                                          "middle-hinge"));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);

        const auto energy = [&]() {
            return upper->total_energy() + lower->total_energy();
        };
        EnergyEnvelope result;
        result.initial = energy();
        result.final = result.initial;
        const std::size_t steps = static_cast<std::size_t>(std::llround(duration / dt));
        for (std::size_t step = 0; step < steps; ++step) {
            TERMIN_QOPT_CHECK(system.step(options(dt)).ok());
            sample_energy(result, energy());
        }
        return result;
    }

    Vec3 angular_momentum_world(const RigidBody3DContribution& body) {
        const SpatialInertia3 inertia_world = body.inertia().rotated_by(body.state().pose.ang);
        return inertia_world.momentum(body.velocity_at_body_origin_world()).ang;
    }

    FreeBodyInvariantError simulate_free_body(double dt, double duration) {
        Multibody3DSystem system;
        auto* body = add(system,
                         std::make_unique<RigidBody3DContribution>(SpatialInertia3{1.0, {2.0, 3.0, 4.0}, {}},
                                                                   RigidBody3DState{
                                                                       {Quat::identity(), Vec3::zero()},
                                                                       Screw3{{1.0, 2.0, 3.0}, {0.5, -0.25, 0.75}},
                                                                   },
                                                                   Vec3::zero(),
                                                                   "free-asymmetric-body"));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);
        const double initial_energy = body->total_energy();
        const Vec3 initial_momentum = angular_momentum_world(*body);
        FreeBodyInvariantError result;
        const std::size_t steps = static_cast<std::size_t>(std::llround(duration / dt));
        for (std::size_t step = 0; step < steps; ++step) {
            TERMIN_QOPT_CHECK(system.step(options(dt)).ok());
            result.maximum_relative_energy_drift =
                std::max(result.maximum_relative_energy_drift,
                         std::abs(body->total_energy() - initial_energy) / std::max(1.0, std::abs(initial_energy)));
            result.maximum_angular_momentum_error = std::max(result.maximum_angular_momentum_error,
                                                             (angular_momentum_world(*body) - initial_momentum).norm() /
                                                                 std::max(1.0, initial_momentum.norm()));
        }
        return result;
    }

    void report(
        const char* name, double coarse_dt, const EnergyEnvelope& coarse, double fine_dt, const EnergyEnvelope& fine) {
        std::fprintf(stderr,
                     "%s energy: dt=%g max_drift=%.17g final=%.17g; "
                     "dt=%g max_drift=%.17g final=%.17g\n",
                     name,
                     coarse_dt,
                     coarse.maximum_relative_drift,
                     coarse.final,
                     fine_dt,
                     fine.maximum_relative_drift,
                     fine.final);
    }

    void check_convergence(const char* name,
                           double coarse_dt,
                           const EnergyEnvelope& coarse,
                           double fine_dt,
                           const EnergyEnvelope& fine,
                           double fine_bound) {
        const bool converges = std::isfinite(coarse.maximum_relative_drift) &&
                               std::isfinite(fine.maximum_relative_drift) &&
                               fine.maximum_relative_drift < 0.35 * coarse.maximum_relative_drift &&
                               fine.maximum_relative_drift < fine_bound;
        if (!converges) {
            report(name, coarse_dt, coarse, fine_dt, fine);
        }
        TERMIN_QOPT_CHECK(converges);
    }

    void check_energy_bound(const char* name,
                            double dt,
                            const EnergyEnvelope& envelope,
                            double maximum_drift) {
        const bool within_bound = std::isfinite(envelope.maximum_relative_drift) &&
                                  envelope.maximum_relative_drift < maximum_drift;
        if (!within_bound) {
            std::fprintf(stderr,
                         "%s energy: dt=%g max_drift=%.17g bound=%.17g "
                         "initial=%.17g final=%.17g\n",
                         name,
                         dt,
                         envelope.maximum_relative_drift,
                         maximum_drift,
                         envelope.initial,
                         envelope.final);
        }
        TERMIN_QOPT_CHECK(within_bound);
    }

    void test_continuous_power_balance() {
        constexpr double theta = 0.4;
        constexpr double angular_speed = 2.0;
        constexpr double mass = 1.0;
        constexpr double moment = 1.0 / 12.0;
        const Vec3 gravity{0.0, 0.0, -9.81};
        const Quat orientation = Quat::from_axis_angle(Vec3::unit_y(), theta);
        const Vec3 center = orientation.rotate({0.5, 0.0, 0.0});
        const Vec3 angular_velocity{0.0, angular_speed, 0.0};
        const Vec3 linear_velocity = angular_velocity.cross(center);

        Multibody3DSystem system;
        auto* body = add(system,
                         std::make_unique<RigidBody3DContribution>(SpatialInertia3{mass, {0.01, moment, moment}, {}},
                                                                   RigidBody3DState{
                                                                       {orientation, center},
                                                                       Screw3{
                                                                           orientation.inverse_rotate(angular_velocity),
                                                                           orientation.inverse_rotate(linear_velocity),
                                                                       },
                                                                   },
                                                                   gravity,
                                                                   "power-balance-body"));
        add(system,
            std::make_unique<FixedRevoluteJoint3DContribution>(
                *body, Vec3{-0.5, 0.0, 0.0}, Vec3::unit_y(), Vec3::zero(), Vec3::unit_y(), "power-balance-hinge"));
        TERMIN_QOPT_CHECK(system.finalize() == DynamicsSystemDiagnostic::None);
        TERMIN_QOPT_CHECK(system.step(options(1e-6)).ok());

        const RigidBody3DState& endpoint = body->state();
        const Screw3 acceleration = body->twist_rate_at_body_origin_local();
        const double kinetic_power = mass * endpoint.velocity_local.lin.dot(acceleration.lin) +
                                     moment * endpoint.velocity_local.ang.y * acceleration.ang.y;
        const double potential_power = -mass * gravity.dot(body->velocity_at_body_origin_world().lin);
        TERMIN_QOPT_CHECK(std::abs(kinetic_power + potential_power) < 1e-10);
    }

} // namespace

int main() {
    constexpr double coarse_dt = 0.005;
    constexpr double fine_dt = 0.0025;
    constexpr double duration = 5.0;

    const EnergyEnvelope single_coarse = simulate_single_pendulum(coarse_dt, duration);
    const EnergyEnvelope single_fine = simulate_single_pendulum(fine_dt, duration);
    check_convergence("single pendulum", coarse_dt, single_coarse, fine_dt, single_fine, 1.1e-4);

    const EnergyEnvelope double_coarse = simulate_double_pendulum(coarse_dt, duration);
    const EnergyEnvelope double_fine = simulate_double_pendulum(fine_dt, duration);
    check_convergence("double pendulum", coarse_dt, double_coarse, fine_dt, double_fine, 3.5e-3);

    const EnergyEnvelope single_reference = simulate_single_pendulum(0.0005, duration);
    const EnergyEnvelope double_reference = simulate_double_pendulum(0.0005, duration);
    const EnergyEnvelope single_long = simulate_single_pendulum(0.0025, 50.0);
    const EnergyEnvelope double_long = simulate_double_pendulum(0.0025, 50.0);
    const EnergyEnvelope double_long_fine = simulate_double_pendulum(0.00125, 50.0);
    const FreeBodyInvariantError free_coarse = simulate_free_body(0.002, 20.0);
    const FreeBodyInvariantError free_fine = simulate_free_body(0.001, 20.0);
    check_energy_bound("single pendulum reference", 0.0005, single_reference, 2e-5);
    check_energy_bound("double pendulum reference", 0.0005, double_reference, 4e-4);
    check_energy_bound("single pendulum long", 0.0025, single_long, 1e-3);
    check_energy_bound("double pendulum long", 0.0025, double_long, 6e-2);
    check_energy_bound("double pendulum long fine", 0.00125, double_long_fine, 1.5e-2);
    const bool long_run_converges =
        double_long_fine.maximum_relative_drift < 0.3 * double_long.maximum_relative_drift;
    if (!long_run_converges) {
        report("double pendulum long", 0.0025, double_long, 0.00125, double_long_fine);
    }
    TERMIN_QOPT_CHECK(long_run_converges);
    TERMIN_QOPT_CHECK(free_fine.maximum_relative_energy_drift < 0.35 * free_coarse.maximum_relative_energy_drift);
    TERMIN_QOPT_CHECK(free_fine.maximum_angular_momentum_error < 0.35 * free_coarse.maximum_angular_momentum_error);
    TERMIN_QOPT_CHECK(free_fine.maximum_relative_energy_drift < 2e-7);
    TERMIN_QOPT_CHECK(free_fine.maximum_angular_momentum_error < 1.2e-6);
    test_continuous_power_balance();
    return 0;
}
