#pragma once

#include <termin/physics_qopt/contact_friction.hpp>
#include <termin/physics_qopt/dynamics.hpp>

namespace termin::physics_qopt::detail {
    [[nodiscard]] QpSolveResult
    solve_constrained_dynamics_impl(ConstDynamicsSystemView system,
                                    DynamicsSolutionView solution,
                                    QpTolerance tolerance,
                                    EqualityQpFactorizationCache* factorization_cache) noexcept;

    [[nodiscard]] QpSolveResult
    solve_contact_friction_impl(ContactFrictionProblemView problem,
                                ContactFrictionSolutionView solution,
                                ContactFrictionOptions options,
                                EqualityQpFactorizationCache* mass_factorization) noexcept;
}
