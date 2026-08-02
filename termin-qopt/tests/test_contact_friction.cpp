#include "test_check.hpp"

#include <array>
#include <cmath>
#include <numbers>

#include <termin/qopt/contact_friction.hpp>

namespace
{
    using namespace termin::qopt;

    void check_near(double actual, double expected, double tolerance)
    {
        if (std::abs(actual - expected) > tolerance)
        {
            std::fprintf(stderr,
                         "actual=%.17g expected=%.17g error=%.17g\n",
                         actual,
                         expected,
                         actual - expected);
            TERMIN_QOPT_CHECK(false);
        }
    }

    struct OneContactFixture
    {
        std::array<double, 9> mass{
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
        };
        std::array<double, 3> velocity{1.0, 0.0, 0.0};
        std::array<double, 3> normal{0.0, 0.0, 1.0};
        std::array<double, 1> minimum_normal_velocity{0.0};
        std::array<double, 6> tangents{
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
        };
        std::array<double, 1> normal_impulse{1.0};
        std::array<double, 1> coefficient{1.0};
        std::array<double, 3> solved_velocity{};
        std::array<double, 2> tangent_impulse{};
        std::array<double, 1> solved_normal_impulse{};
        std::array<double, 1> work{};

        ContactFrictionProblemView problem() const
        {
            return {
                ConstDenseMatrixView::row_major(mass.data(), 3, 3),
                ConstDenseMatrixView::row_major(nullptr, 0, 3),
                {velocity.data(), velocity.size(), 1},
                ConstDenseMatrixView::row_major(normal.data(), 1, 3),
                {minimum_normal_velocity.data(), 1, 1},
                ConstDenseMatrixView::row_major(normal.data(), 1, 3),
                ConstDenseMatrixView::row_major(tangents.data(), 2, 3),
                {normal_impulse.data(), 1, 1},
                {coefficient.data(), 1, 1},
            };
        }

        ContactFrictionSolutionView solution()
        {
            return {
                {solved_velocity.data(), solved_velocity.size(), 1},
                {tangent_impulse.data(), tangent_impulse.size(), 1},
                {solved_normal_impulse.data(), solved_normal_impulse.size(), 1},
                {work.data(), work.size(), 1},
            };
        }
    };

    void test_zero_friction_is_exact_noop()
    {
        OneContactFixture fixture;
        fixture.velocity = {1.25, -0.5, 0.0};
        fixture.coefficient[0] = 0.0;
        const QpSolveResult result =
            solve_contact_friction(fixture.problem(), fixture.solution());
        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        for (std::size_t index = 0; index < fixture.velocity.size(); ++index)
        {
            TERMIN_QOPT_CHECK(fixture.solved_velocity[index] ==
                              fixture.velocity[index]);
        }
        TERMIN_QOPT_CHECK(fixture.tangent_impulse[0] == 0.0);
        TERMIN_QOPT_CHECK(fixture.tangent_impulse[1] == 0.0);
        TERMIN_QOPT_CHECK(fixture.work[0] == 0.0);
    }

    void test_static_and_sliding_regimes()
    {
        OneContactFixture sticking;
        sticking.coefficient[0] = 2.0;
        QpSolveResult result =
            solve_contact_friction(sticking.problem(), sticking.solution());
        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        check_near(sticking.solved_velocity[0], 0.0, 2e-10);
        check_near(sticking.solved_velocity[1], 0.0, 2e-10);
        check_near(sticking.tangent_impulse[0], -1.0, 2e-10);
        TERMIN_QOPT_CHECK(sticking.work[0] <= 1e-12);

        OneContactFixture sliding;
        sliding.coefficient[0] = 0.5;
        result = solve_contact_friction(sliding.problem(), sliding.solution());
        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        const double impulse_norm =
            std::hypot(sliding.tangent_impulse[0], sliding.tangent_impulse[1]);
        TERMIN_QOPT_CHECK(impulse_norm <= 0.5 + 2e-10);
        check_near(impulse_norm, 0.5, 2e-10);
        check_near(sliding.solved_velocity[0], 0.5, 2e-10);
        TERMIN_QOPT_CHECK(sliding.work[0] < 0.0);
    }

    void test_rotated_tangent_basis()
    {
        constexpr double rotation = 0.37;
        OneContactFixture reference;
        reference.velocity = {std::cos(0.21), std::sin(0.21), 0.0};
        reference.coefficient[0] = 0.45;
        TERMIN_QOPT_CHECK(
            solve_contact_friction(reference.problem(), reference.solution()).status ==
            QpStatus::Optimal);

        OneContactFixture rotated = reference;
        rotated.tangents = {
            std::cos(rotation),
            std::sin(rotation),
            0.0,
            -std::sin(rotation),
            std::cos(rotation),
            0.0,
        };
        TERMIN_QOPT_CHECK(
            solve_contact_friction(rotated.problem(), rotated.solution()).status ==
            QpStatus::Optimal);
        const double physical_difference =
            std::hypot(rotated.solved_velocity[0] - reference.solved_velocity[0],
                       rotated.solved_velocity[1] - reference.solved_velocity[1]);
        // Two arbitrarily rotated regular N-gons can quantize the opposing
        // impulse directions by at most one facet angle relative to each
        // other. Both impulses remain inside the true Coulomb disk.
        constexpr double polygon_bound = 2.0 * 0.45 * std::sin(std::numbers::pi / 32.0);
        TERMIN_QOPT_CHECK(physical_difference <= polygon_bound + 1e-10);
        TERMIN_QOPT_CHECK(rotated.work[0] <= 1e-12);
    }

    void test_friction_preserves_normal_nonpenetration()
    {
        OneContactFixture fixture;
        fixture.mass = {
            1.0,
            0.0,
            -0.5,
            0.0,
            1.0,
            0.0,
            -0.5,
            0.0,
            1.0,
        };
        fixture.coefficient[0] = 10.0;
        const QpSolveResult result =
            solve_contact_friction(fixture.problem(), fixture.solution());
        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(fixture.solved_velocity[2] >= -1e-10);
        TERMIN_QOPT_CHECK(fixture.work[0] <= 1e-12);
    }

    void test_kinematically_locked_tangents_are_noop()
    {
        OneContactFixture fixture;
        fixture.tangents.fill(0.0);
        const QpSolveResult result =
            solve_contact_friction(fixture.problem(), fixture.solution());
        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(fixture.solved_velocity == fixture.velocity);
        TERMIN_QOPT_CHECK(fixture.tangent_impulse[0] == 0.0);
        TERMIN_QOPT_CHECK(fixture.tangent_impulse[1] == 0.0);
        TERMIN_QOPT_CHECK(fixture.work[0] == 0.0);
    }

    void test_multi_contact_support_redistributes_normal_impulse()
    {
        const std::array<double, 9> mass{
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            1.0,
        };
        const std::array<double, 3> velocity{1.0, 0.0, 0.0};
        const std::array<double, 6> normals{
            0.0,
            1.0,
            -1.0,
            0.0,
            1.0,
            1.0,
        };
        const std::array<double, 12> tangents{
            1.0,
            0.0,
            -1.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            -1.0,
            0.0,
            0.0,
            0.0,
        };
        const std::array<double, 2> targets{};
        const std::array<double, 2> normal_impulses{0.5, 0.5};
        const std::array<double, 2> coefficients{0.5, 0.5};
        std::array<double, 3> solved_velocity{};
        std::array<double, 4> tangent_impulses{};
        std::array<double, 2> solved_normal_impulses{};
        std::array<double, 2> work{};

        const QpSolveResult result = solve_contact_friction(
            {
                ConstDenseMatrixView::row_major(mass.data(), 3, 3),
                ConstDenseMatrixView::row_major(nullptr, 0, 3),
                {velocity.data(), velocity.size(), 1},
                ConstDenseMatrixView::row_major(normals.data(), 2, 3),
                {targets.data(), targets.size(), 1},
                ConstDenseMatrixView::row_major(normals.data(), 2, 3),
                ConstDenseMatrixView::row_major(tangents.data(), 4, 3),
                {normal_impulses.data(), normal_impulses.size(), 1},
                {coefficients.data(), coefficients.size(), 1},
            },
            {
                {solved_velocity.data(), solved_velocity.size(), 1},
                {tangent_impulses.data(), tangent_impulses.size(), 1},
                {solved_normal_impulses.data(), solved_normal_impulses.size(), 1},
                {work.data(), work.size(), 1},
                {},
            });
        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(std::hypot(tangent_impulses[0], tangent_impulses[2]) > 0.1);
        for (double impulse : solved_normal_impulses)
        {
            TERMIN_QOPT_CHECK(impulse >= -1e-10);
        }
        TERMIN_QOPT_CHECK(solved_velocity[1] - solved_velocity[2] >= -1e-10);
        TERMIN_QOPT_CHECK(solved_velocity[1] + solved_velocity[2] >= -1e-10);
        TERMIN_QOPT_CHECK(work[0] + work[1] <= 1e-10);
    }

    void test_invalid_normal_state_is_rejected_transactionally()
    {
        OneContactFixture fixture;
        fixture.velocity[2] = -0.1;
        fixture.solved_velocity = {7.0, 8.0, 9.0};
        fixture.tangent_impulse = {10.0, 11.0};
        const QpSolveResult result =
            solve_contact_friction(fixture.problem(), fixture.solution());
        TERMIN_QOPT_CHECK(result.status == QpStatus::InvalidInput);
        TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::InvalidWarmStart);
        TERMIN_QOPT_CHECK(fixture.solved_velocity[0] == 7.0);
        TERMIN_QOPT_CHECK(fixture.tangent_impulse[0] == 10.0);
    }
} // namespace

int main()
{
    test_zero_friction_is_exact_noop();
    test_static_and_sliding_regimes();
    test_rotated_tangent_basis();
    test_friction_preserves_normal_nonpenetration();
    test_kinematically_locked_tangents_are_noop();
    test_multi_contact_support_redistributes_normal_impulse();
    test_invalid_normal_state_is_rejected_transactionally();
    return 0;
}
