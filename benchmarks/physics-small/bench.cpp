#include <termin/physics_qopt/physics_qopt.hpp>
#include <termin/robotics/robotics.hpp>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

using namespace termin;
using namespace termin::physics_qopt;
using namespace termin::robotics;
using Clock = std::chrono::steady_clock;
constexpr double dt = 0.001;

void require(bool condition, const char* message) {
    if (!condition)
        throw std::runtime_error(message);
}

std::vector<ArticulationUnit3D> units(int n) {
    std::vector<ArticulationUnit3D> result;
    for (int i = 0; i < n; ++i) {
        result.push_back({
            .parent_unit = i ? std::size_t(i - 1) : articulation_root_frame,
            .parent_to_unit_zero = Pose3::translation(i ? 0.3 : 0.0, 0, 0),
            .motion_twist_at_unit = {i % 2 ? Vec3::unit_z() : Vec3::unit_y(), Vec3::zero()},
            .inertia = SpatialInertia3{1.0, {0.02, 0.025, 0.03}, Pose3::translation(0.15, 0, 0)},
            .diagnostic_name = "link",
        });
    }
    return result;
}

Articulation3DState initial(int n) {
    Articulation3DState state{std::vector<double>(n), std::vector<double>(n)};
    for (int i = 0; i < n; ++i)
        state.coordinates[i] = i % 2 ? -0.15 : 0.2;
    return state;
}

void vector_json(const std::vector<double>& values) {
    std::cout << '[';
    for (std::size_t i = 0; i < values.size(); ++i) {
        require(std::isfinite(values[i]), "non-finite benchmark output");
        if (i)
            std::cout << ',';
        std::cout << values[i];
    }
    std::cout << ']';
}

void timings_json(const char* name, const std::vector<double>& samples) {
    auto sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    const auto half = sorted.size() / 2;
    const double median = sorted.size() % 2 ? sorted[half] : 0.5 * (sorted[half - 1] + sorted[half]);
    std::cout << '"' << name << "\":{\"median_us\":" << median << ",\"min_us\":" << sorted.front()
              << ",\"max_us\":" << sorted.back() << ",\"samples_us\":";
    vector_json(samples);
    std::cout << '}';
}

template <class Function> double timed(int count, Function function) {
    const auto start = Clock::now();
    for (int i = 0; i < count; ++i)
        function();
    return std::chrono::duration<double, std::micro>(Clock::now() - start).count() / count;
}

// Composition keeps instrumentation outside production code and throughput runs.
// This fixture has no limits/contacts: all articulation overrides are forwarded.
class ProfiledArticulation final : public DynamicsContribution {
public:
    explicit ProfiledArticulation(Articulation3D& arm)
        : inner(arm, {0, 0, -9.81}, "profile") {}
    Articulation3DDynamicsContribution inner;
    double mass_assembly_us = 0, cached_assembly_us = 0, velocity_us = 0, configuration_us = 0;
    std::size_t velocity_calls = 0;
    AssemblyDiagnostic register_topology(DynamicsTopology& topology) noexcept override {
        return inner.register_topology(topology);
    }
    AssemblyDiagnostic register_unilateral_constraints(DynamicsUnilateralTopology& topology,
                                                       double dt) noexcept override {
        return inner.register_unilateral_constraints(topology, dt);
    }
    AssemblyDiagnostic begin_step() noexcept override {
        return inner.begin_step();
    }
    void commit_step() noexcept override {
        inner.commit_step();
    }
    void rollback_step() noexcept override {
        inner.rollback_step();
    }
    AssemblyDiagnostic assemble(DynamicsAssembly& assembly, DynamicsAssemblyPhase phase) noexcept override {
        const auto before = inner.assembly_counters();
        const auto start = Clock::now();
        const auto result = inner.assemble(assembly, phase);
        const double us = std::chrono::duration<double, std::micro>(Clock::now() - start).count();
        if (inner.assembly_counters().mass_matrix_evaluations != before.mass_matrix_evaluations)
            mass_assembly_us += us;
        else
            cached_assembly_us += us;
        return result;
    }
    void apply_solution(DynamicsAssemblyPhase phase,
                        const DynamicsTopology& topology,
                        ConstDenseVectorView values,
                        ConstDenseVectorView reactions) noexcept override {
        inner.apply_solution(phase, topology, values, reactions);
    }
    void apply_unilateral_solution(const DynamicsTopology& topology,
                                   const DynamicsUnilateralTopology& unilateral,
                                   ConstDenseVectorView reactions,
                                   ConstDenseVectorView mask) noexcept override {
        inner.apply_unilateral_solution(topology, unilateral, reactions, mask);
    }
    AssemblyDiagnostic write_velocity(const DynamicsTopology& topology,
                                      DenseVectorView values) const noexcept override {
        return inner.write_velocity(topology, values);
    }
    AssemblyDiagnostic set_velocity(const DynamicsTopology& topology, ConstDenseVectorView values) noexcept override {
        const auto start = Clock::now();
        const auto result = inner.set_velocity(topology, values);
        velocity_us += std::chrono::duration<double, std::micro>(Clock::now() - start).count();
        ++velocity_calls;
        return result;
    }
    AssemblyDiagnostic set_trial_configuration(const DynamicsTopology& topology,
                                               ConstDenseVectorView values,
                                               double dt) noexcept override {
        const auto start = Clock::now();
        const auto result = inner.set_trial_configuration(topology, values, dt);
        configuration_us += std::chrono::duration<double, std::micro>(Clock::now() - start).count();
        return result;
    }
    AssemblyDiagnostic write_corrected_midpoint_velocity(const DynamicsTopology& topology,
                                                         ConstDenseVectorView midpoint,
                                                         ConstDenseVectorView correction,
                                                         double dt,
                                                         DenseVectorView destination) const noexcept override {
        return inner.write_corrected_midpoint_velocity(topology, midpoint, correction, dt, destination);
    }
};

void profile(int n, int steps, const std::vector<double>& final_q, const std::vector<double>& final_v) {
    Articulation3D arm(units(n), initial(n), "profile");
    DynamicsSystem system;
    auto contribution = std::make_unique<ProfiledArticulation>(arm);
    auto* measurements = contribution.get();
    require(system.add_contribution(std::move(contribution)) == DynamicsSystemDiagnostic::None, "profile add failed");
    require(system.finalize() == DynamicsSystemDiagnostic::None, "profile finalize failed");
    const double total = timed(steps, [&] { require(system.step({.time_step = dt}).ok(), "profile step failed"); });
    require(arm.state().coordinates == final_q && arm.state().velocities == final_v, "profile changed trajectory");
    std::cout << ",\"instrumented_profile_us_per_step\":{\"total\":" << total
              << ",\"assembly_with_mass_rebuild\":" << measurements->mass_assembly_us / steps
              << ",\"assembly_with_cached_mass\":" << measurements->cached_assembly_us / steps
              << ",\"set_velocity\":" << measurements->velocity_us / steps
              << ",\"set_trial_configuration\":" << measurements->configuration_us / steps
              << ",\"set_velocity_calls\":" << static_cast<double>(measurements->velocity_calls) / steps << '}';
}

void chain(int n, int steps, int warmups, int repeats) {
    std::vector<double> step_times, mass_times, bias_times;
    std::vector<double> final_q, final_v, mass, bias;
    std::size_t mass_evaluations = 0, bias_evaluations = 0, factorizations = 0, reuses = 0;
    for (int trial = -warmups; trial < repeats; ++trial) {
        Articulation3D arm(units(n), initial(n), "benchmark");
        DynamicsSystem system;
        auto contribution = std::make_unique<Articulation3DDynamicsContribution>(arm, Vec3{0, 0, -9.81}, "dynamics");
        auto* counters = contribution.get();
        require(system.add_contribution(std::move(contribution)) == DynamicsSystemDiagnostic::None,
                "add contribution failed");
        require(system.finalize() == DynamicsSystemDiagnostic::None, "finalize failed");
        std::size_t trial_factorizations = 0, trial_reuses = 0;
        const double step_us = timed(steps, [&] {
            const auto result = system.step({.time_step = dt});
            require(result.ok(), "dynamics step failed");
            trial_factorizations += result.endpoint_equality_factorizations;
            trial_reuses += result.endpoint_equality_factorization_reuses;
        });
        if (trial >= 0) {
            step_times.push_back(step_us);
            mass_evaluations += counters->assembly_counters().mass_matrix_evaluations;
            bias_evaluations += counters->assembly_counters().bias_evaluations;
            factorizations += trial_factorizations;
            reuses += trial_reuses;
        }
        if (trial == 0) {
            final_q = arm.state().coordinates;
            final_v = arm.state().velocities;
        } else if (trial > 0) {
            require(final_q == arm.state().coordinates && final_v == arm.state().velocities,
                    "non-deterministic trajectory");
        }
        // Kernel timings use a fixed configuration and a deterministic nonzero velocity.
        // They are microbenchmarks, not an additive profile of the evolving step.
        Articulation3D reference(units(n), initial(n), "kernel benchmark");
        std::vector<double> velocity(n), zero(n, 0.0);
        for (int i = 0; i < n; ++i)
            velocity[i] = i % 2 ? -0.3 : 0.4;
        require(reference.mass_matrix(mass), "mass prewarm failed");
        require(reference.inverse_dynamics(velocity, zero, {0, 0, -9.81}, bias), "bias prewarm failed");
        const double mass_us = timed(steps, [&] { require(reference.mass_matrix(mass), "mass matrix failed"); });
        const double bias_us = timed(steps, [&] {
            require(reference.inverse_dynamics(velocity, zero, {0, 0, -9.81}, bias), "inverse dynamics failed");
        });
        if (trial >= 0) {
            mass_times.push_back(mass_us);
            bias_times.push_back(bias_us);
        }
    }
    const double divisor = static_cast<double>(steps) * repeats;
    std::cout << "{\"dof\":" << n << ',';
    timings_json("step", step_times);
    std::cout << ',';
    timings_json("mass_matrix", mass_times);
    std::cout << ',';
    timings_json("bias", bias_times);
    std::cout << ",\"counts_per_step\":{\"mass_evaluations\":" << mass_evaluations / divisor
              << ",\"bias_evaluations\":" << bias_evaluations / divisor
              << ",\"endpoint_factorizations\":" << factorizations / divisor
              << ",\"endpoint_factorization_reuses\":" << reuses / divisor << '}' << ",\"final_q\":";
    vector_json(final_q);
    std::cout << ",\"final_v\":";
    vector_json(final_v);
    std::cout << ",\"initial_mass\":";
    vector_json(mass);
    std::cout << ",\"initial_bias_nonzero_velocity\":";
    vector_json(bias);
    profile(n, steps, final_q, final_v);
    std::cout << '}';
}

void contact(int steps, int warmups, int repeats) {
    const std::array<double, 9> mass{1, 0, 0, 0, 1, 0, 0, 0, 1};
    const std::array<double, 3> velocity{1, 0, 0}, normal{0, 0, 1};
    const std::array<double, 6> tangents{1, 0, 0, 0, 1, 0};
    const std::array<double, 1> target{0}, impulse{1}, friction{0.5};
    const std::array<std::size_t, 1> rows{0};
    std::array<double, 3> solved{};
    std::array<double, 2> tangent_impulse{};
    std::array<double, 1> normal_impulse{}, work{};
    const ContactFrictionProblemView problem{ConstDenseMatrixView::row_major(mass.data(), 3, 3),
                                             ConstDenseMatrixView::row_major(nullptr, 0, 3),
                                             {velocity.data(), 3, 1},
                                             ConstDenseMatrixView::row_major(normal.data(), 1, 3),
                                             {target.data(), 1, 1},
                                             ConstDenseMatrixView::row_major(normal.data(), 1, 3),
                                             {rows.data(), 1},
                                             ConstDenseMatrixView::row_major(tangents.data(), 2, 3),
                                             {impulse.data(), 1, 1},
                                             {friction.data(), 1, 1}};
    const ContactFrictionSolutionView solution{
        {solved.data(), 3, 1}, {tangent_impulse.data(), 2, 1}, {normal_impulse.data(), 1, 1}, {work.data(), 1, 1}};
    std::vector<double> samples;
    for (int trial = -warmups; trial < repeats; ++trial) {
        const double us = timed(steps, [&] {
            require(solve_contact_friction(problem, solution).status == QpStatus::Optimal, "contact solve failed");
        });
        require(std::abs(solved[0] - 0.5) < 2e-10 && work[0] < 0, "contact oracle failed");
        if (trial >= 0)
            samples.push_back(us);
    }
    std::cout << "{\"case\":\"one_sliding_contact_solve_only\",";
    timings_json("solve", samples);
    std::cout << ",\"final_velocity\":[" << solved[0] << ',' << solved[1] << ',' << solved[2] << "]}";
}

int main(int argc, char** argv) {
    try {
        require(argc == 4, "usage: physics_small_benchmark steps warmups repeats");
        const int steps = std::stoi(argv[1]), warmups = std::stoi(argv[2]), repeats = std::stoi(argv[3]);
        require(steps > 0 && warmups > 0 && repeats > 0, "counts must be positive");
        std::cout << std::setprecision(17) << "{\"time_step\":" << dt << ",\"chains\":[";
        bool first = true;
        for (const int n : {2, 6, 12, 24}) {
            if (!first)
                std::cout << ',';
            first = false;
            chain(n, steps, warmups, repeats);
        }
        std::cout << "],\"contact\":";
        contact(steps, warmups, repeats);
        std::cout << "}\n";
    } catch (const std::exception& error) {
        std::cerr << "[physics-small-benchmark] " << error.what() << '\n';
        return 1;
    }
}
