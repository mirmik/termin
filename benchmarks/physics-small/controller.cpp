#include "benchmark_common.hpp"

#include <termin/robotics/inverse_dynamics_control.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <numeric>
#include <vector>

namespace {
    double max_difference(const std::vector<double>& actual, const std::vector<double>& expected) {
        require(actual.size() == expected.size(), "controller output dimension mismatch");
        double error = 0.0;
        for (std::size_t index = 0; index < actual.size(); ++index) {
            require(std::isfinite(actual[index]) && std::isfinite(expected[index]), "non-finite controller output");
            error = std::max(error, std::abs(actual[index] - expected[index]));
        }
        return error;
    }

    double max_absolute(const std::vector<double>& values) {
        double result = 0.0;
        for (double value : values)
            result = std::max(result, std::abs(value));
        return result;
    }
} // namespace

void controller(int n, int steps, int warmups, int repeats) {
    using namespace termin;
    using namespace termin::robotics;

    constexpr double kp = 16.0;
    constexpr double kd = 4.0;
    const Vec3 gravity{0, 0, -9.81};
    Articulation3DState state = initial(n);
    std::vector<std::size_t> indices(n);
    std::iota(indices.begin(), indices.end(), 0);
    std::vector<double> targets(n), target_velocities(n), feedforward(n), expected_acceleration(n);
    for (int index = 0; index < n; ++index) {
        state.velocities[index] = index % 2 ? -0.3 : 0.4;
        targets[index] = state.coordinates[index] + 0.08 * std::sin(index + 0.3);
        target_velocities[index] = 0.1 * std::cos(0.7 * index);
        feedforward[index] = 0.05 * std::sin(index + 0.1);
        expected_acceleration[index] = feedforward[index] + kp * (targets[index] - state.coordinates[index]) +
                                       kd * (target_velocities[index] - state.velocities[index]);
    }

    std::vector<double> samples, final_acceleration, final_effort, final_required_effort, final_residuals;
    std::vector<double> oracle_effort;
    std::size_t measured_warm_starts = 0;
    double acceleration_error = 0.0, effort_error = 0.0, priority_violation = 0.0;
    for (int trial = -warmups; trial < repeats; ++trial) {
        // This deliberately holds q/qdot fixed: measure the controller's full
        // solve (linearization, M/bias, HQP, outputs), without a dynamics step.
        Articulation3D arm(units(n), state, "controller benchmark");
        InverseDynamicsHqpController3D control(arm, gravity);
        JointPostureTask3D posture(indices, targets, target_velocities, kp, kd, feedforward);
        const std::array<const ArticulationTask3D*, 1> tasks{&posture};
        const InverseDynamicsControlOptions3D options{.time_step = dt};
        auto solved = control.solve(tasks, options);
        require(solved.ok(), "controller warm-start priming failed");
        std::size_t warm_start_count = 0;
        const double us = timed(steps, [&] {
            solved = control.solve(tasks, options);
            require(solved.ok(), "controller solve failed");
            warm_start_count += solved.primal_warm_start_used;
        });

        require(warm_start_count == static_cast<std::size_t>(steps), "controller did not reuse its primal warm start");
        require(solved.active_task_count == 1 && solved.hqp_result.levels_solved == 1,
                "unexpected controller task/level count");
        require(solved.unactuated_residual_linf == 0.0, "unexpected unactuated controller residual");
        require(arm.state().coordinates == state.coordinates && arm.state().velocities == state.velocities,
                "controller changed the fixed benchmark state");

        // Full actuation and no bounds make the posture optimum analytic.
        // RNEA provides an independent effort oracle for that optimum.
        require(arm.inverse_dynamics(state.velocities, expected_acceleration, gravity, oracle_effort),
                "controller inverse-dynamics oracle failed");
        acceleration_error =
            std::max(acceleration_error, max_difference(solved.generalized_acceleration, expected_acceleration));
        effort_error = std::max({effort_error,
                                 max_difference(solved.actuator_effort, oracle_effort),
                                 max_difference(solved.required_generalized_effort, oracle_effort)});
        require(acceleration_error <= 1e-8 * (1.0 + max_absolute(expected_acceleration)),
                "controller acceleration oracle failed");
        require(effort_error <= 1e-8 * (1.0 + max_absolute(oracle_effort)), "controller effort oracle failed");
        require(std::isfinite(solved.hqp_result.priority_violation_linf), "non-finite controller priority residual");
        priority_violation = std::max(priority_violation, solved.hqp_result.priority_violation_linf);

        if (trial >= 0) {
            samples.push_back(us);
            measured_warm_starts += warm_start_count;
            if (trial == 0) {
                final_acceleration = solved.generalized_acceleration;
                final_effort = solved.actuator_effort;
                final_required_effort = solved.required_generalized_effort;
                final_residuals = solved.level_task_residual_l2;
            } else {
                require(final_acceleration == solved.generalized_acceleration &&
                            final_effort == solved.actuator_effort &&
                            final_required_effort == solved.required_generalized_effort &&
                            final_residuals == solved.level_task_residual_l2,
                        "non-deterministic controller result");
            }
        }
    }

    std::cout << "{\"dof\":" << n << ",\"case\":\"fixed_state_full_actuation_posture_hqp\","
              << "\"primal_warm_start\":\"primed_before_each_trial\",\"position_gain\":" << kp
              << ",\"velocity_gain\":" << kd << ',';
    timings_json("solve", samples);
    std::cout << ",\"warm_starts_per_solve\":"
              << static_cast<double>(measured_warm_starts) / (static_cast<double>(steps) * repeats)
              << ",\"acceleration_oracle_error_linf\":" << acceleration_error
              << ",\"effort_oracle_error_linf\":" << effort_error
              << ",\"priority_violation_linf\":" << priority_violation << ",\"q\":";
    vector_json(state.coordinates);
    std::cout << ",\"v\":";
    vector_json(state.velocities);
    std::cout << ",\"target_q\":";
    vector_json(targets);
    std::cout << ",\"target_v\":";
    vector_json(target_velocities);
    std::cout << ",\"feedforward_acceleration\":";
    vector_json(feedforward);
    std::cout << ",\"expected_acceleration\":";
    vector_json(expected_acceleration);
    std::cout << ",\"generalized_acceleration\":";
    vector_json(final_acceleration);
    std::cout << ",\"actuator_effort\":";
    vector_json(final_effort);
    std::cout << ",\"required_generalized_effort\":";
    vector_json(final_required_effort);
    std::cout << ",\"oracle_effort\":";
    vector_json(oracle_effort);
    std::cout << ",\"level_task_residual_l2\":";
    vector_json(final_residuals);
    std::cout << '}';
}
