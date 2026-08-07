#pragma once

#include <cstddef>
#include <span>

#include <termin/physics_qopt/termin_physics_qopt_api.hpp>
#include <termin/qopt/active_set_qp.hpp>
#include <termin/qopt/dense_views.hpp>

namespace termin::physics_qopt
{
    using namespace termin::qopt;

    // Global tangent-impulse maximum-dissipation problem evaluated after a
    // frictionless normal projection. Each friction contact owns two
    // consecutive rows of tangent_jacobian. normal_jacobian may contain a
    // larger set of unilateral rows which must all remain satisfied. Normal
    // rows use the physical separating-velocity convention
    // N*v >= minimum_normal_velocity.
    struct ContactFrictionProblemView
    {
        ConstDenseMatrixView mass;
        ConstDenseMatrixView bilateral_jacobian;
        ConstDenseVectorView normal_projected_velocity;
        ConstDenseMatrixView normal_jacobian;
        ConstDenseVectorView minimum_normal_velocity;
        // One physical normal row per friction contact. These rows also occur
        // in normal_jacobian and permit the second pass to redistribute the
        // previously solved normal impulses.
        ConstDenseMatrixView contact_normal_jacobian;
        // For each friction contact, identifies its row in normal_jacobian.
        // Supporting contacts replace that unilateral row with a delta-v_n=0
        // equality instead of adding an opposing inequality.
        std::span<const std::size_t> contact_normal_rows;
        ConstDenseMatrixView tangent_jacobian;
        ConstDenseVectorView normal_impulse;
        ConstDenseVectorView friction_coefficient;
    };

    struct ContactFrictionSolutionView
    {
        DenseVectorView velocity;
        // Two physical tangent impulse components per contact, in the same
        // row order as tangent_jacobian.
        DenseVectorView tangent_impulse;
        // Optional corrected normal impulses, one per friction contact.
        DenseVectorView normal_impulse;
        // Optional one-value-per-contact output. Negative values are dissipated
        // mechanical energy; zero means that contact did no friction work.
        DenseVectorView friction_work;
        // Optional physical bilateral impulse induced by the friction pass.
        DenseVectorView bilateral_impulse;
    };

    struct ContactFrictionOptions
    {
        // Number of sides in the inscribed regular polygon approximating the
        // circular Coulomb disk. Must be even and at least four.
        std::size_t cone_facets = 6;
        ActiveSetQpOptions qp;
    };

    // Solves one coupled impulse QP for all friction contacts. Normal impulses
    // may be redistributed among supporting contacts, while active support
    // velocities, nonpenetration and non-negative final normal impulses remain
    // constrained. Outputs are transactional and change only on Optimal.
    [[nodiscard]] TERMIN_PHYSICS_QOPT_API QpSolveResult
    solve_contact_friction(ContactFrictionProblemView problem,
                           ContactFrictionSolutionView solution,
                           ContactFrictionOptions options = {}) noexcept;

} // namespace termin::physics_qopt
