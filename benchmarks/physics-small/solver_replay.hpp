#pragma once

#include <termin/physics_qopt/dynamics.hpp>

#include <vector>

// Records the unconstrained, single-contribution chain only. Recording is a
// separate, untimed run; it must never be enabled for throughput/profile runs.
class SolverTrace {
public:
    [[nodiscard]] bool begin_step() noexcept;
    [[nodiscard]] bool record(termin::physics_qopt::ConstDynamicsSystemView system) noexcept;
    // Called at Acceleration apply_solution: the initial and final endpoint
    // solutions are attached to the most recently assembled equation.
    [[nodiscard]] bool record_solution(termin::qopt::ConstDenseVectorView acceleration) noexcept;
    void report(int warmups, int repeats) const;

private:
    struct Equation {
        std::vector<double> mass;
        std::vector<double> load;
        std::vector<double> applied_acceleration;

        [[nodiscard]] termin::physics_qopt::ConstDynamicsSystemView system() const noexcept;
    };
    struct Step {
        std::vector<Equation> equations;
    };
    std::vector<Step> steps_;
};
