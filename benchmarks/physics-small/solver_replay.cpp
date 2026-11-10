#include "solver_replay.hpp"

#include "benchmark_common.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <iostream>
#include <optional>
#include <utility>

using namespace termin::physics_qopt;

ConstDynamicsSystemView SolverTrace::Equation::system() const noexcept {
    const std::size_t n = load.size();
    return {ConstDenseMatrixView::row_major(mass.data(), n, n),
            {load.data(), n, 1},
            ConstDenseMatrixView::row_major(nullptr, 0, n),
            {nullptr, 0, 1}};
}

bool SolverTrace::begin_step() noexcept {
    try {
        require(steps_.empty() || !steps_.back().equations.empty(), "empty previous solver trace step");
        steps_.emplace_back();
        return true;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "[physics-small-benchmark] solver trace begin failed: %s\n", error.what());
    } catch (...) {
        std::fprintf(stderr, "[physics-small-benchmark] solver trace begin failed with unknown exception\n");
    }
    return false;
}

bool SolverTrace::record(ConstDynamicsSystemView system) noexcept {
    try {
        require(!steps_.empty(), "solver trace record without begin_step");
        const std::size_t n = system.load.size;
        require(n > 0 && system.mass.rows == n && system.mass.columns == n && system.constraint_jacobian.rows == 0 &&
                    system.constraint_rhs.size == 0,
                "solver replay supports only unconstrained chains");
        Equation equation;
        equation.mass.resize(n * n);
        equation.load.resize(n);
        for (std::size_t row = 0; row < n; ++row) {
            equation.load[row] = system.load[row];
            for (std::size_t column = 0; column < n; ++column)
                equation.mass[row * n + column] = system.mass(row, column);
        }
        auto& equations = steps_.back().equations;
        if (equations.size() > 1)
            require(equation.mass == equations[1].mass, "endpoint matrix changed within traced configuration pass");
        equations.push_back(std::move(equation));
        return true;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "[physics-small-benchmark] solver trace recording failed: %s\n", error.what());
    } catch (...) {
        std::fprintf(stderr, "[physics-small-benchmark] solver trace recording failed with unknown exception\n");
    }
    return false;
}

bool SolverTrace::record_solution(ConstDenseVectorView acceleration) noexcept {
    try {
        require(!steps_.empty() && !steps_.back().equations.empty(), "solver trace solution without equation");
        Equation& equation = steps_.back().equations.back();
        require(acceleration.size == equation.load.size(), "solver trace solution dimension mismatch");
        require(equation.applied_acceleration.empty(), "duplicate applied solver trace solution");
        equation.applied_acceleration.resize(acceleration.size);
        for (std::size_t index = 0; index < acceleration.size; ++index)
            equation.applied_acceleration[index] = acceleration[index];
        return true;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "[physics-small-benchmark] solver trace solution failed: %s\n", error.what());
    } catch (...) {
        std::fprintf(stderr, "[physics-small-benchmark] solver trace solution failed with unknown exception\n");
    }
    return false;
}

void SolverTrace::report(int warmups, int repeats) const {
    require(warmups >= 0 && repeats > 0 && !steps_.empty(), "invalid solver replay trial counts");
    require(!steps_.front().equations.empty(), "empty solver replay trace");
    const std::size_t n = steps_.front().equations.front().load.size();
    std::size_t expected_reuses = 0;
    for (const Step& step : steps_) {
        require(step.equations.size() >= 2, "solver trace missing endpoint solve");
        require(!step.equations.front().applied_acceleration.empty() &&
                    !step.equations.back().applied_acceleration.empty(),
                "solver trace missing initial/final applied acceleration");
        expected_reuses += step.equations.size() - 2;
        for (const Equation& equation : step.equations)
            require(equation.load.size() == n, "solver trace DOF count changed");
    }

    std::vector<double> initial_samples, cold_samples, reused_samples, gradient_samples, lifecycle_samples;
    std::vector<double> subtotal_samples;
    std::vector<double> acceleration(n), gradient(n);
    const DynamicsSolutionView dynamics_output{{acceleration.data(), n, 1}, {nullptr, 0, 1}};
    const EqualityQpSolutionView qp_output{{acceleration.data(), n, 1}, {nullptr, 0, 1}};
    double max_scaled_residual = 0.0, max_applied_difference = 0.0;
    const auto validate = [&](const Equation& equation) {
        for (std::size_t row = 0; row < n; ++row) {
            require(std::isfinite(acceleration[row]), "solver replay acceleration is non-finite");
            double product = 0.0, scale = std::abs(equation.load[row]);
            for (std::size_t column = 0; column < n; ++column) {
                const double term = equation.mass[row * n + column] * acceleration[column];
                product += term;
                scale += std::abs(term);
            }
            const double residual = std::abs(product - equation.load[row]) / std::max(1.0, scale);
            max_scaled_residual = std::max(max_scaled_residual, residual);
            require(residual <= 1e-8, "solver replay M*a-load residual failed");
            if (!equation.applied_acceleration.empty()) {
                const double difference = std::abs(acceleration[row] - equation.applied_acceleration[row]);
                max_applied_difference = std::max(max_applied_difference, difference);
                require(difference <= 1e-10 * (1.0 + std::abs(equation.applied_acceleration[row])),
                        "solver replay differs from applied acceleration");
            }
        }
    };
    const auto elapsed = [](Clock::time_point start) {
        return std::chrono::duration<double, std::micro>(Clock::now() - start).count();
    };
    for (int trial = -warmups; trial < repeats; ++trial) {
        double initial_us = 0.0, cold_us = 0.0, reused_us = 0.0, gradient_us = 0.0, lifecycle_us = 0.0;
        std::size_t reuses = 0, factorizations = 0;
        for (const Step& step : steps_) {
            const auto initial_start = Clock::now();
            const QpSolveResult initial_result =
                solve_constrained_dynamics(step.equations.front().system(), dynamics_output);
            initial_us += elapsed(initial_start);
            require(initial_result.status == QpStatus::Optimal, "solver replay initial solve failed");
            validate(step.equations.front());

            // A new cache is essential: clear() would retain storage across
            // physical steps, unlike the production endpoint loop.
            std::optional<EqualityQpFactorizationCache> cache;
            auto lifecycle_start = Clock::now();
            cache.emplace();
            lifecycle_us += elapsed(lifecycle_start);
            for (std::size_t index = 1; index < step.equations.size(); ++index) {
                const Equation& equation = step.equations[index];
                const auto setup_start = Clock::now();
                for (std::size_t dof = 0; dof < n; ++dof)
                    gradient[dof] = -equation.load[dof];
                const EqualityQpProblemView problem{equation.system().mass,
                                                    {gradient.data(), n, 1},
                                                    ConstDenseMatrixView::row_major(nullptr, 0, n),
                                                    {nullptr, 0, 1}};
                gradient_us += elapsed(setup_start);
                const auto solve_start = Clock::now();
                const QpSolveResult solved = cache->solve(problem, qp_output);
                const double solve_us = elapsed(solve_start);
                if (index == 1)
                    cold_us += solve_us;
                else
                    reused_us += solve_us;
                require(solved.status == QpStatus::Optimal, "solver replay endpoint solve failed");
                validate(equation);
            }
            const auto counters = cache->counters();
            require(counters.factorizations == 1 && counters.reuse_hits == step.equations.size() - 2,
                    "solver replay cache did not match production sequence");
            factorizations += counters.factorizations;
            reuses += counters.reuse_hits;
            lifecycle_start = Clock::now();
            cache.reset();
            lifecycle_us += elapsed(lifecycle_start);
        }
        require(factorizations == steps_.size() && reuses == expected_reuses, "solver replay total count mismatch");
        if (trial >= 0) {
            const double count = static_cast<double>(steps_.size());
            initial_samples.push_back(initial_us / count);
            cold_samples.push_back(cold_us / count);
            reused_samples.push_back(reused_us / count);
            gradient_samples.push_back(gradient_us / count);
            lifecycle_samples.push_back(lifecycle_us / count);
            subtotal_samples.push_back((initial_us + cold_us + reused_us + gradient_us + lifecycle_us) / count);
        }
    }

    std::cout << "{\"trace_steps\":" << steps_.size() << ",\"warmups\":" << warmups << ",\"repeats\":" << repeats
              << ",\"endpoint_factorizations_per_step\":1,\"endpoint_reuses_per_step\":"
              << static_cast<double>(expected_reuses) / steps_.size()
              << ",\"max_scaled_equation_residual\":" << max_scaled_residual
              << ",\"max_applied_acceleration_difference\":" << max_applied_difference
              << ",\"timing_unit\":\"microseconds_per_physical_step\","
              << "\"note\":\"Replay of actual unconstrained equations. Cold and reused solves both include checks and "
                 "copies; these are not pure factorization/validation timers. Initial public solve includes adapter "
                 "temporaries. Endpoint gradient/output buffers are preallocated, so endpoint adapter allocations and "
                 "validation are excluded. Oracle checks, recording and serialization are excluded.\",";
    timings_json("initial_public_solve", initial_samples);
    std::cout << ',';
    timings_json("endpoint_cold_solve", cold_samples);
    std::cout << ',';
    timings_json("endpoint_reused_solves", reused_samples);
    std::cout << ',';
    timings_json("endpoint_gradient_setup", gradient_samples);
    std::cout << ',';
    timings_json("cache_lifecycle", lifecycle_samples);
    std::cout << ',';
    timings_json("measured_subtotal", subtotal_samples);
    std::cout << '}';
}
