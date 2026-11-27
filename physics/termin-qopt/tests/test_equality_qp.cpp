#include <termin/qopt/qopt.hpp>

#include "qp_oracle_cases.hpp"
#include "test_check.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
#include <string_view>
#include <vector>

namespace {

    using namespace termin::qopt;

    [[nodiscard]] ConstDenseVectorView const_vector(const std::vector<double>& values) {
        return {values.data(), values.size()};
    }

    [[nodiscard]] DenseVectorView vector(std::vector<double>& values) {
        return {values.data(), values.size()};
    }

    [[nodiscard]] ConstDenseMatrixView
    row_major(const std::vector<double>& values, std::size_t rows, std::size_t columns) {
        return ConstDenseMatrixView::row_major(values.data(), rows, columns);
    }

    [[nodiscard]] double linf_difference(const std::vector<double>& left, const std::vector<double>& right) {
        TERMIN_QOPT_CHECK(left.size() == right.size());
        double result = 0.0;
        for (std::size_t index = 0; index < left.size(); ++index) {
            result = std::max(result, std::abs(left[index] - right[index]));
        }
        return result;
    }

    void test_shared_oracle() {
        for (const OracleEqualityQpCase& test_case : equality_qp_oracle_cases()) {
            std::vector<double> primal(test_case.variables, 123.0);
            std::vector<double> dual(test_case.constraints, 456.0);
            const EqualityQpProblemView problem{
                row_major(test_case.hessian, test_case.variables, test_case.variables),
                const_vector(test_case.gradient),
                row_major(test_case.equalities, test_case.constraints, test_case.variables),
                const_vector(test_case.equality_targets),
            };
            const QpSolveResult result = solve_equality_qp(problem, {vector(primal), vector(dual)});

            TERMIN_QOPT_CHECK(qp_status_name(result.status) == test_case.status);
            if (result.status == QpStatus::Optimal) {
                TERMIN_QOPT_CHECK(linf_difference(primal, test_case.expected_primal) <= test_case.primal_linf);
                TERMIN_QOPT_CHECK(result.stationarity_linf <= test_case.stationarity_linf);
                TERMIN_QOPT_CHECK(result.equality_linf <= test_case.equality_linf);
            } else {
                TERMIN_QOPT_CHECK(std::ranges::all_of(primal, [](double value) { return value == 123.0; }));
                TERMIN_QOPT_CHECK(std::ranges::all_of(dual, [](double value) { return value == 456.0; }));
            }
        }
    }

    void test_redundant_equalities_and_minimum_norm_dual() {
        const std::vector<double> hessian{2.0};
        const std::vector<double> gradient{-4.0};
        const std::vector<double> equalities{1.0, 2.0};
        const std::vector<double> targets{3.0, 6.0};
        std::vector<double> primal(1);
        std::vector<double> dual(2);

        const QpSolveResult result = solve_equality_qp(
            {
                row_major(hessian, 1, 1),
                const_vector(gradient),
                row_major(equalities, 2, 1),
                const_vector(targets),
            },
            {vector(primal), vector(dual)});

        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(result.constraint_rank == 1);
        TERMIN_QOPT_CHECK(std::abs(primal[0] - 3.0) <= 1e-10);
        TERMIN_QOPT_CHECK(result.stationarity_linf <= 1e-10);
        TERMIN_QOPT_CHECK(result.equality_linf <= 1e-10);
    }

    void test_constraint_row_scaling_does_not_change_the_solution() {
        const std::vector<double> hessian{
            2.0,
            0.0,
            0.0,
            4.0,
        };
        const std::vector<double> gradient{-2.0, -8.0};
        const std::vector<double> equalities{
            1.0e-12,
            1.0e-12,
            1.0e12,
            -1.0e12,
        };
        const std::vector<double> targets{3.0e-12, -1.0e12};
        std::vector<double> primal(2);
        std::vector<double> dual(2);

        const QpSolveResult result = solve_equality_qp(
            {
                row_major(hessian, 2, 2),
                const_vector(gradient),
                row_major(equalities, 2, 2),
                const_vector(targets),
            },
            {vector(primal), vector(dual)});

        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(std::abs(primal[0] - 1.0) <= 1e-10);
        TERMIN_QOPT_CHECK(std::abs(primal[1] - 2.0) <= 1e-10);
        TERMIN_QOPT_CHECK(result.stationarity_linf <= 1e-10);
        TERMIN_QOPT_CHECK(result.equality_linf / 1.0e12 <= 1.0e-12);
    }

    void test_strided_views() {
        const std::vector<double> hessian{
            2.0,
            0.0,
            -100.0,
            0.0,
            2.0,
            -100.0,
        };
        const std::vector<double> gradient_storage{-2.0, -100.0, -6.0};
        const std::vector<double> equalities{1.0, 1.0};
        const std::vector<double> targets{1.0};
        std::vector<double> primal_storage(4, -100.0);
        std::vector<double> dual_storage(1);

        const QpSolveResult result = solve_equality_qp(
            {
                {hessian.data(), 2, 2, 3, 1},
                {gradient_storage.data(), 2, 2},
                row_major(equalities, 1, 2),
                const_vector(targets),
            },
            {
                {primal_storage.data() + 1, 2, 2},
                vector(dual_storage),
            });

        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(std::abs(primal_storage[1] + 0.5) <= 1e-10);
        TERMIN_QOPT_CHECK(std::abs(primal_storage[3] - 1.5) <= 1e-10);
    }

    void test_input_output_aliasing_uses_snapshot_semantics() {
        const std::vector<double> hessian{2.0};
        std::vector<double> gradient_and_primal{-4.0};
        const std::vector<double> no_values;

        const QpSolveResult result = solve_equality_qp(
            {
                row_major(hessian, 1, 1),
                const_vector(gradient_and_primal),
                row_major(no_values, 0, 1),
                const_vector(no_values),
            },
            {
                vector(gradient_and_primal),
                {nullptr, 0, 1},
            });

        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(std::abs(gradient_and_primal[0] - 2.0) <= 1e-10);
    }

    void test_invalid_inputs_are_diagnostic_and_do_not_write_outputs() {
        const std::vector<double> no_values;
        const std::vector<double> gradient{0.0, 0.0};
        const std::vector<double> asymmetric_hessian{
            1.0,
            1.0,
            0.0,
            1.0,
        };
        std::vector<double> primal(2, 123.0);

        QpSolveResult result = solve_equality_qp(
            {
                row_major(asymmetric_hessian, 2, 2),
                const_vector(gradient),
                row_major(no_values, 0, 2),
                const_vector(no_values),
            },
            {vector(primal), {nullptr, 0, 1}});
        TERMIN_QOPT_CHECK(result.status == QpStatus::InvalidInput);
        TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::NonSymmetricHessian);

        const std::vector<double> non_finite_hessian{
            1.0,
            0.0,
            0.0,
            std::numeric_limits<double>::quiet_NaN(),
        };
        result = solve_equality_qp(
            {
                row_major(non_finite_hessian, 2, 2),
                const_vector(gradient),
                row_major(no_values, 0, 2),
                const_vector(no_values),
            },
            {vector(primal), {nullptr, 0, 1}});
        TERMIN_QOPT_CHECK(result.status == QpStatus::InvalidInput);
        TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::NonFiniteInput);

        result = solve_equality_qp(
            {
                row_major(asymmetric_hessian, 2, 2),
                {gradient.data(), gradient.size(), 0},
                row_major(no_values, 0, 2),
                const_vector(no_values),
            },
            {vector(primal), {nullptr, 0, 1}});
        TERMIN_QOPT_CHECK(result.status == QpStatus::InvalidInput);
        TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::InvalidStride);
        TERMIN_QOPT_CHECK(std::ranges::all_of(primal, [](double value) { return value == 123.0; }));
    }

    void test_nonconvex_and_overlapping_outputs() {
        const std::vector<double> negative_hessian{-1.0};
        const std::vector<double> gradient{0.0};
        const std::vector<double> no_values;
        std::vector<double> primal(1);

        QpSolveResult result = solve_equality_qp(
            {
                row_major(negative_hessian, 1, 1),
                const_vector(gradient),
                row_major(no_values, 0, 1),
                const_vector(no_values),
            },
            {vector(primal), {nullptr, 0, 1}});
        TERMIN_QOPT_CHECK(result.status == QpStatus::NonConvex);
        TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::NegativeCurvature);

        const std::vector<double> positive_hessian{1.0};
        const std::vector<double> equality{1.0};
        const std::vector<double> target{0.0};
        result = solve_equality_qp(
            {
                row_major(positive_hessian, 1, 1),
                const_vector(gradient),
                row_major(equality, 1, 1),
                const_vector(target),
            },
            {vector(primal), vector(primal)});
        TERMIN_QOPT_CHECK(result.status == QpStatus::InvalidInput);
        TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::OverlappingOutputs);
    }

    void test_factorization_cache_reuses_only_exact_coefficients() {
        std::vector<double> hessian{
            4.0,
            1.0,
            1.0,
            3.0,
        };
        std::vector<double> equalities{1.0, -1.0};
        std::vector<double> gradient{-2.0, 1.0};
        std::vector<double> targets{0.5};
        std::vector<double> cached_primal(2);
        std::vector<double> cached_dual(1);
        std::vector<double> reference_primal(2);
        std::vector<double> reference_dual(1);
        EqualityQpFactorizationCache cache;

        const auto solve_cached = [&]() {
            return cache.solve(
                {
                    row_major(hessian, 2, 2),
                    const_vector(gradient),
                    row_major(equalities, 1, 2),
                    const_vector(targets),
                },
                {vector(cached_primal), vector(cached_dual)});
        };
        const auto solve_reference = [&]() {
            return solve_equality_qp(
                {
                    row_major(hessian, 2, 2),
                    const_vector(gradient),
                    row_major(equalities, 1, 2),
                    const_vector(targets),
                },
                {vector(reference_primal), vector(reference_dual)});
        };

        TERMIN_QOPT_CHECK(solve_cached().status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(solve_reference().status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(linf_difference(cached_primal, reference_primal) <= 1e-12);
        TERMIN_QOPT_CHECK(linf_difference(cached_dual, reference_dual) <= 1e-12);

        gradient = {3.0, -4.0};
        targets[0] = -0.25;
        TERMIN_QOPT_CHECK(solve_cached().status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(solve_reference().status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(linf_difference(cached_primal, reference_primal) <= 1e-12);
        TERMIN_QOPT_CHECK(linf_difference(cached_dual, reference_dual) <= 1e-12);
        EqualityQpFactorizationCounters counters = cache.counters();
        TERMIN_QOPT_CHECK(counters.factorizations == 1);
        TERMIN_QOPT_CHECK(counters.reuse_hits == 1);

        hessian[0] += 0.5;
        TERMIN_QOPT_CHECK(solve_cached().status == QpStatus::Optimal);
        counters = cache.counters();
        TERMIN_QOPT_CHECK(counters.factorizations == 2);
        TERMIN_QOPT_CHECK(counters.reuse_hits == 1);

        equalities[1] += 0.25;
        TERMIN_QOPT_CHECK(solve_cached().status == QpStatus::Optimal);
        counters = cache.counters();
        TERMIN_QOPT_CHECK(counters.factorizations == 3);
        TERMIN_QOPT_CHECK(counters.reuse_hits == 1);

        cache.clear();
        TERMIN_QOPT_CHECK(solve_cached().status == QpStatus::Optimal);
        counters = cache.counters();
        TERMIN_QOPT_CHECK(counters.factorizations == 4);
    }

    void test_factorization_cache_preserves_rhs_diagnostics() {
        const std::vector<double> hessian{2.0};
        const std::vector<double> equalities{1.0, 2.0};
        const std::vector<double> gradient{-4.0};
        std::vector<double> targets{3.0, 6.0};
        std::vector<double> primal(1, 123.0);
        std::vector<double> dual(2, 456.0);
        EqualityQpFactorizationCache cache;

        const auto solve = [&]() {
            return cache.solve(
                {
                    row_major(hessian, 1, 1),
                    const_vector(gradient),
                    row_major(equalities, 2, 1),
                    const_vector(targets),
                },
                {vector(primal), vector(dual)});
        };
        TERMIN_QOPT_CHECK(solve().status == QpStatus::Optimal);

        targets[1] = 7.0;
        primal[0] = 123.0;
        std::fill(dual.begin(), dual.end(), 456.0);
        const QpSolveResult inconsistent = solve();
        TERMIN_QOPT_CHECK(inconsistent.status == QpStatus::Infeasible);
        TERMIN_QOPT_CHECK(inconsistent.diagnostic == QpDiagnostic::InconsistentEqualities);
        TERMIN_QOPT_CHECK(primal[0] == 123.0);
        TERMIN_QOPT_CHECK(std::ranges::all_of(dual, [](double value) { return value == 456.0; }));
        const EqualityQpFactorizationCounters counters = cache.counters();
        TERMIN_QOPT_CHECK(counters.factorizations == 1);
        TERMIN_QOPT_CHECK(counters.reuse_hits == 1);
    }

    void test_unconstrained_spectral_classification_matches_general_path() {
        struct Case {
            std::vector<double> hessian;
            std::vector<double> gradient;
            QpStatus status;
            QpDiagnostic diagnostic;
            std::size_t rank;
            std::vector<double> expected;
        };
        constexpr double cutoff = 1e-8;
        const QpTolerance tolerance{.absolute = cutoff, .relative = 0.0};
        const std::vector<Case> cases{
            {{4, 1, 1, 3}, {-1, 2}, QpStatus::Optimal, QpDiagnostic::None, 2, {5.0 / 11, -9.0 / 11}},
            {{2, 0, 0, 0}, {-4, 0}, QpStatus::Optimal, QpDiagnostic::None, 1, {2, 0}},
            {{2, 0, 0, 0}, {-4, 1}, QpStatus::Unbounded, QpDiagnostic::LinearDescentInNullspace, 1, {}},
            {{-1, 0, 0, 2}, {0, 0}, QpStatus::NonConvex, QpDiagnostic::NegativeCurvature, 0, {}},
            {{0.5 * cutoff, 0, 0, 1}, {0.5 * cutoff, 0}, QpStatus::Optimal, QpDiagnostic::None, 1, {0, 0}},
            {{0.5 * cutoff, 0, 0, 1},
             {1.5 * cutoff, 0},
             QpStatus::Unbounded,
             QpDiagnostic::LinearDescentInNullspace,
             1,
             {}},
            {{1.5 * cutoff, 0, 0, 1}, {-3 * cutoff, -2}, QpStatus::Optimal, QpDiagnostic::None, 2, {2, 2}},
            {{-0.5 * cutoff, 0, 0, 1}, {0, 0}, QpStatus::Optimal, QpDiagnostic::None, 1, {0, 0}},
            {{-1.5 * cutoff, 0, 0, 1}, {0, 0}, QpStatus::NonConvex, QpDiagnostic::NegativeCurvature, 0, {}},
        };
        const std::vector<double> empty, zero_row{0, 0}, zero_target{0};
        for (const Case& test : cases) {
            EqualityQpFactorizationCache cache;
            const EqualityQpProblemView unconstrained{row_major(test.hessian, 2, 2),
                                                      const_vector(test.gradient),
                                                      row_major(empty, 0, 2),
                                                      const_vector(empty)};
            // One zero equality is redundant. It still exercises the general
            // SVD/nullspace path instead of the zero-row specialization.
            const EqualityQpProblemView general{row_major(test.hessian, 2, 2),
                                                const_vector(test.gradient),
                                                row_major(zero_row, 1, 2),
                                                const_vector(zero_target)};
            std::vector<double> reference(2, 123), dual(1, 456);
            const auto oracle = solve_equality_qp(general, {vector(reference), vector(dual)}, tolerance);
            TERMIN_QOPT_CHECK(oracle.status == test.status && oracle.diagnostic == test.diagnostic);
            for (int mode = 0; mode < 3; ++mode) {
                std::vector<double> actual(2, 123);
                const EqualityQpSolutionView output{vector(actual), {nullptr, 0, 1}};
                const auto result = mode == 0 ? solve_equality_qp(unconstrained, output, tolerance)
                                              : cache.solve(unconstrained, output, tolerance);
                TERMIN_QOPT_CHECK(result.status == test.status && result.diagnostic == test.diagnostic);
                TERMIN_QOPT_CHECK(result.constraint_rank == 0);
                TERMIN_QOPT_CHECK(result.reduced_hessian_rank == test.rank);
                if (result.status == QpStatus::Optimal) {
                    TERMIN_QOPT_CHECK(linf_difference(actual, test.expected) <= 1e-10);
                    TERMIN_QOPT_CHECK(linf_difference(actual, reference) <= 1e-10);
                    TERMIN_QOPT_CHECK(result.stationarity_linf <= cutoff);
                    TERMIN_QOPT_CHECK(result.equality_linf == 0.0);
                    TERMIN_QOPT_CHECK(dual[0] == 0.0);
                } else {
                    TERMIN_QOPT_CHECK(actual == std::vector<double>({123, 123}));
                    TERMIN_QOPT_CHECK(reference == actual && dual[0] == 456);
                }
            }
            TERMIN_QOPT_CHECK(cache.counters().factorizations == 1);
            TERMIN_QOPT_CHECK(cache.counters().reuse_hits == 1);
        }

        const EqualityQpProblemView empty_problem{
            row_major(empty, 0, 0), const_vector(empty), row_major(empty, 0, 0), const_vector(empty)};
        const EqualityQpSolutionView empty_output{{nullptr, 0, 1}, {nullptr, 0, 1}};
        EqualityQpFactorizationCache empty_cache;
        for (const auto result :
             {solve_equality_qp(empty_problem, empty_output), empty_cache.solve(empty_problem, empty_output)}) {
            TERMIN_QOPT_CHECK(result.status == QpStatus::InvalidInput);
            TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::DimensionMismatch);
        }
        TERMIN_QOPT_CHECK(empty_cache.counters().factorizations == 0);
    }

    void test_unconstrained_strided_aliasing() {
        for (bool cached : {false, true}) {
            for (bool alias_hessian : {false, true}) {
                EqualityQpFactorizationCache cache;
                for (int pass = 0; pass < 2; ++pass) {
                    std::vector<double> hessian{4, 1, 77, 1, 3, 77};
                    std::vector<double> gradient{-1, 77, 2, 77};
                    const EqualityQpProblemView problem{{hessian.data(), 2, 2, 3, 1},
                                                        {gradient.data(), 2, 2},
                                                        ConstDenseMatrixView::row_major(nullptr, 0, 2),
                                                        {nullptr, 0, 1}};
                    const DenseVectorView primal = alias_hessian ? DenseVectorView{hessian.data() + 1, 2, 3}
                                                                 : DenseVectorView{gradient.data(), 2, 2};
                    const EqualityQpSolutionView output{primal, {nullptr, 0, 1}};
                    const auto result = cached ? cache.solve(problem, output) : solve_equality_qp(problem, output);
                    TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
                    TERMIN_QOPT_CHECK(std::abs(primal[0] - 5.0 / 11) <= 1e-12);
                    TERMIN_QOPT_CHECK(std::abs(primal[1] + 9.0 / 11) <= 1e-12);
                    TERMIN_QOPT_CHECK(hessian[2] == 77 && hessian[5] == 77);
                    TERMIN_QOPT_CHECK(gradient[1] == 77 && gradient[3] == 77);
                }
                if (cached) {
                    TERMIN_QOPT_CHECK(cache.counters().factorizations == 1);
                    TERMIN_QOPT_CHECK(cache.counters().reuse_hits == 1);
                }
            }
        }
    }

    void test_cache_switches_constraint_modes_and_spectral_tolerance() {
        std::vector<double> hessian{0.5e-8, 0, 0, 1};
        const std::vector<double> gradient{-1e-9, -2}, empty, equalities{1, 0}, targets{0.75};
        QpTolerance tolerance{.absolute = 1e-8, .relative = 0.0};
        EqualityQpFactorizationCache cache;
        const auto solve = [&](bool constrained,
                               std::size_t factorizations,
                               std::size_t reuses,
                               std::size_t reduced_rank,
                               double expected_first) {
            const EqualityQpProblemView problem{row_major(hessian, 2, 2),
                                                const_vector(gradient),
                                                row_major(constrained ? equalities : empty, constrained ? 1 : 0, 2),
                                                const_vector(constrained ? targets : empty)};
            std::vector<double> primal(2, 123), reference(2, 123), dual(constrained ? 1 : 0),
                reference_dual(dual.size());
            const auto result = cache.solve(problem, {vector(primal), vector(dual)}, tolerance);
            const auto oracle = solve_equality_qp(problem, {vector(reference), vector(reference_dual)}, tolerance);
            TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal && oracle.status == result.status);
            TERMIN_QOPT_CHECK(result.diagnostic == oracle.diagnostic);
            TERMIN_QOPT_CHECK(result.constraint_rank == (constrained ? 1 : 0));
            TERMIN_QOPT_CHECK(result.reduced_hessian_rank == reduced_rank);
            TERMIN_QOPT_CHECK(std::abs(primal[0] - expected_first) <= 1e-12);
            TERMIN_QOPT_CHECK(std::abs(primal[1] - 2) <= 1e-12);
            TERMIN_QOPT_CHECK(linf_difference(primal, reference) <= 1e-12);
            TERMIN_QOPT_CHECK(linf_difference(dual, reference_dual) <= 1e-12);
            TERMIN_QOPT_CHECK(cache.counters().factorizations == factorizations);
            TERMIN_QOPT_CHECK(cache.counters().reuse_hits == reuses);
        };
        solve(true, 1, 0, 1, 0.75);
        solve(false, 2, 0, 1, 0.0);
        solve(false, 2, 1, 1, 0.0);
        tolerance.absolute = 1e-10;
        solve(false, 3, 1, 2, 0.2);
        hessian[0] = 2e-8;
        solve(false, 4, 1, 2, 0.05);
        solve(true, 5, 1, 1, 0.75);
        solve(false, 6, 1, 2, 0.05);
    }

    void test_homogeneous_batch_matches_cached_columns() {
        struct Case {
            std::vector<double> hessian;
            std::vector<double> equalities;
            std::vector<double> gradients;
            QpStatus status;
        };
        constexpr std::size_t variables = 3, columns = 2;
        const std::vector<double> spd{4, 1, 0, 1, 3, 1, 0, 1, 2};
        const std::vector<double> singular{2, 0, 0, 0, 0, 0, 0, 0, 0};
        const std::vector<double> gradients{-1, 4, 3, 0, 2, -3};
        const std::vector<Case> cases{
            {spd, {}, gradients, QpStatus::Optimal},
            {spd, {1, 1, 0, 0, 1, -1}, gradients, QpStatus::Optimal},
            {spd, {0.001, 0.001, 0, -3, -3, 0}, gradients, QpStatus::Optimal},
            {spd, {1, 0, 0, 0, 1, 0, 0, 0, 1}, gradients, QpStatus::Optimal},
            {singular, {0, 1, 0}, {-2, 4, 3, -1, 0, 0}, QpStatus::Optimal},
            // Both residuals are below tolerance. The maximum can come from either column.
            {singular, {0, 1, 0}, {-2, 4, 3, -1, 1e-12, 0}, QpStatus::Optimal},
            {singular, {0, 1, 0}, {-2, 4, 3, -1, 0, 1e-12}, QpStatus::Optimal},
            // The first gradient is large but has no component along the free null direction.
            // The second column must use its own tolerance, and its failure must roll back the batch.
            {singular, {0, 1, 0}, {1e6, 0.1, 3, -1, 0, 1e-7}, QpStatus::Unbounded},
            {{2, 0, 0, 0, 1, 0, 0, 0, -1}, {0, 1, 0}, gradients, QpStatus::NonConvex},
        };
        for (const Case& test : cases) {
            const std::size_t constraints = test.equalities.size() / variables;
            const auto hessian = row_major(test.hessian, variables, variables);
            const auto equalities = row_major(test.equalities, constraints, variables);
            const auto gradients_view = row_major(test.gradients, variables, columns);
            std::vector<double> primal_storage(variables * columns, 123);
            std::vector<double> dual_storage(constraints * columns, 456);
            const auto primal = DenseMatrixView::column_major(primal_storage.data(), variables, columns);
            const auto dual = DenseMatrixView::row_major(dual_storage.data(), constraints, columns);
            const auto batch = solve_homogeneous_equality_qp_batch(hessian, equalities, gradients_view, primal, dual);
            TERMIN_QOPT_CHECK(batch.status == test.status);

            EqualityQpFactorizationCache cache;
            const std::vector<double> targets(constraints, 0.0);
            std::vector<double> scalar_primal(variables), scalar_dual(constraints);
            double max_stationarity = 0.0;
            double max_equality = 0.0;
            for (std::size_t col = 0; col < columns; ++col) {
                const ConstDenseVectorView gradient{&gradients_view(0, col), variables, gradients_view.row_stride};
                const auto scalar = cache.solve({hessian, gradient, equalities, const_vector(targets)},
                                                {vector(scalar_primal), vector(scalar_dual)});
                if (scalar.status != QpStatus::Optimal) {
                    TERMIN_QOPT_CHECK(scalar.status == batch.status && scalar.diagnostic == batch.diagnostic);
                    TERMIN_QOPT_CHECK(batch.constraint_rank == scalar.constraint_rank);
                    TERMIN_QOPT_CHECK(batch.reduced_hessian_rank == scalar.reduced_hessian_rank);
                    if (batch.status == QpStatus::Unbounded) {
                        TERMIN_QOPT_CHECK(col == 1);
                    }
                    break;
                }
                if (batch.status == QpStatus::Optimal) {
                    max_stationarity = std::max(max_stationarity, scalar.stationarity_linf);
                    max_equality = std::max(max_equality, scalar.equality_linf);
                    TERMIN_QOPT_CHECK(batch.constraint_rank == scalar.constraint_rank);
                    TERMIN_QOPT_CHECK(batch.reduced_hessian_rank == scalar.reduced_hessian_rank);
                    for (std::size_t row = 0; row < variables; ++row) {
                        TERMIN_QOPT_CHECK(std::abs(primal(row, col) - scalar_primal[row]) < 1e-10);
                    }
                    for (std::size_t row = 0; row < constraints; ++row) {
                        TERMIN_QOPT_CHECK(std::abs(dual(row, col) - scalar_dual[row]) < 1e-10);
                    }
                } else {
                    TERMIN_QOPT_CHECK(col + 1 < columns);
                }
            }
            if (batch.status == QpStatus::Optimal) {
                TERMIN_QOPT_CHECK(std::abs(batch.stationarity_linf - max_stationarity) <= 2e-14);
                TERMIN_QOPT_CHECK(std::abs(batch.equality_linf - max_equality) <= 2e-14);
            } else {
                TERMIN_QOPT_CHECK(std::ranges::all_of(primal_storage, [](double v) { return v == 123; }));
                TERMIN_QOPT_CHECK(std::ranges::all_of(dual_storage, [](double v) { return v == 456; }));
            }
        }
    }

    void test_cached_spd_solve_recovers_after_overflowing_rhs() {
        const std::vector<double> hessian{0.25, 0, 0, 0.5};
        std::vector<double> gradient{1, -2};
        const EqualityQpProblemView problem{
            row_major(hessian, 2, 2), const_vector(gradient), ConstDenseMatrixView::row_major(nullptr, 0, 2), {}};
        EqualityQpFactorizationCache cache;
        const auto solve = [&](QpStatus expected) {
            double primal[]{123, 123};
            double reference[]{123, 123};
            const auto cached = cache.solve(problem, {{primal, 2}, {}});
            const auto spectral = solve_equality_qp(problem, {{reference, 2}, {}});
            TERMIN_QOPT_CHECK(cached.status == expected && spectral.status == expected);
            TERMIN_QOPT_CHECK(cached.diagnostic == spectral.diagnostic);
            if (expected == QpStatus::Optimal) {
                TERMIN_QOPT_CHECK(cached.reduced_hessian_rank == 2);
                TERMIN_QOPT_CHECK(std::abs(primal[0] - reference[0]) < 1e-12);
                TERMIN_QOPT_CHECK(std::abs(primal[1] - reference[1]) < 1e-12);
            } else {
                TERMIN_QOPT_CHECK(primal[0] == 123 && primal[1] == 123);
            }
        };
        solve(QpStatus::Optimal);
        gradient[0] = std::numeric_limits<double>::max();
        solve(QpStatus::NumericalFailure);
        gradient[0] = -3;
        solve(QpStatus::Optimal);
        TERMIN_QOPT_CHECK(cache.counters().factorizations == 1 && cache.counters().reuse_hits == 2);
    }

    void test_unconstrained_solvers_at_spectral_rank_and_symmetry_boundaries() {
        const QpTolerance tolerance{.absolute = 0, .relative = 1e-7, .symmetry = 0.125};
        using Matrix2 = std::array<double, 4>;
        // These eigenvalues are e and 2-e. At e=1.5e-7 both Cholesky pivots
        // exceed the spectral cutoff (~2e-7), but the smaller eigenvalue does not.
        const auto coupled = [](double e) -> Matrix2 {
            return {1, 1 - e, 1 - e, 1};
        };
        const Matrix2 nearly_orthogonal{1, 1 + 2e-8, 1, 1 - 2e-8};
        const Matrix2 mixed_directions{1, -1, 1, 1};
        struct Case {
            Matrix2 hessian;
            Matrix2 gradients;
            QpStatus status;
            std::size_t rank;
        };
        const Case cases[] = {
            {coupled(1.5e-7), nearly_orthogonal, QpStatus::Optimal, 1},
            {coupled(1.5e-7), mixed_directions, QpStatus::Unbounded, 1},
            {coupled(3e-7), mixed_directions, QpStatus::Optimal, 2},
            {coupled(0), nearly_orthogonal, QpStatus::Optimal, 1},
            {coupled(0), mixed_directions, QpStatus::Unbounded, 1},
            {coupled(-1.5e-7), nearly_orthogonal, QpStatus::Optimal, 1},
            {coupled(-3e-7), mixed_directions, QpStatus::NonConvex, 0},
            // Symmetrize at the allowed boundary and reject one ulp beyond it.
            {{2, 0.375, 0.125, 2}, mixed_directions, QpStatus::Optimal, 2},
            {{2, std::nextafter(0.375, 1.0), 0.125, 2}, mixed_directions, QpStatus::InvalidInput, 0},
        };
        const auto no_equalities = ConstDenseMatrixView::row_major(nullptr, 0, 2);
        EqualityQpFactorizationCache cache;
        for (const Case& test : cases) {
            const auto hessian = ConstDenseMatrixView::row_major(test.hessian.data(), 2, 2);
            const auto gradients = ConstDenseMatrixView::row_major(test.gradients.data(), 2, 2);
            Matrix2 storage{123, 123, 123, 123};
            const auto primal = DenseMatrixView::row_major(storage.data(), 2, 2);
            const auto batch = solve_homogeneous_equality_qp_batch(
                hessian, no_equalities, gradients, primal, DenseMatrixView::row_major(nullptr, 0, 2), tolerance);
            TERMIN_QOPT_CHECK(batch.status == test.status && batch.reduced_hessian_rank == test.rank);

            double max_residual = 0.0;
            double max_roundoff = 0.0;
            for (std::size_t col = 0; col < 2; ++col) {
                double reference[2]{};
                const EqualityQpProblemView problem{hessian, {&gradients(0, col), 2, 2}, no_equalities, {}};
                const auto scalar = solve_equality_qp(problem, {{reference, 2}, {}}, tolerance);
                double cached_primal[]{123, 123};
                const auto cached = cache.solve(problem, {{cached_primal, 2}, {}}, tolerance);
                TERMIN_QOPT_CHECK(cached.status == scalar.status && cached.diagnostic == scalar.diagnostic);
                TERMIN_QOPT_CHECK(cached.reduced_hessian_rank == scalar.reduced_hessian_rank);
                if (cached.status == QpStatus::Optimal) {
                    for (std::size_t row = 0; row < 2; ++row) {
                        TERMIN_QOPT_CHECK(std::abs(cached_primal[row] - reference[row]) <=
                                          2e-9 * std::max(1.0, std::abs(reference[row])));
                    }
                } else {
                    TERMIN_QOPT_CHECK(cached_primal[0] == 123 && cached_primal[1] == 123);
                }
                if (batch.status != QpStatus::Optimal) {
                    if (col == 0 && batch.status == QpStatus::Unbounded) {
                        TERMIN_QOPT_CHECK(scalar.status == QpStatus::Optimal);
                    } else {
                        TERMIN_QOPT_CHECK(scalar.status == batch.status && scalar.diagnostic == batch.diagnostic);
                    }
                    continue;
                }
                TERMIN_QOPT_CHECK(scalar.status == QpStatus::Optimal && scalar.reduced_hessian_rank == test.rank);
                for (std::size_t row = 0; row < 2; ++row) {
                    // The full-rank ill-conditioned case has a solution of order 1/e.
                    TERMIN_QOPT_CHECK(std::abs(primal(row, col) - reference[row]) <=
                                      2e-9 * std::max(1.0, std::abs(reference[row])));
                    double residual = gradients(row, col);
                    double scale = std::abs(residual);
                    for (std::size_t k = 0; k < 2; ++k) {
                        const double term = 0.5 * (hessian(row, k) + hessian(k, row)) * primal(k, col);
                        residual += term;
                        scale += std::abs(term);
                    }
                    max_residual = std::max(max_residual, std::abs(residual));
                    max_roundoff = std::max(max_roundoff, 4 * std::numeric_limits<double>::epsilon() * scale);
                }
            }
            if (batch.status == QpStatus::Optimal) {
                TERMIN_QOPT_CHECK(batch.equality_linf == 0.0);
                TERMIN_QOPT_CHECK(std::abs(batch.stationarity_linf - max_residual) <= max_roundoff);
                TERMIN_QOPT_CHECK(max_residual <= 1.01 * tolerance.relative);
            } else {
                TERMIN_QOPT_CHECK(std::ranges::all_of(storage, [](double v) { return v == 123; }));
            }
        }
    }

    void test_homogeneous_batch_snapshots_strided_gradients() {
        const std::vector<double> hessian{2, 0, 0, 4};
        std::vector<double> storage{-4, -10, 77, 4, 12, 77};
        const ConstDenseMatrixView gradient{storage.data(), 2, 2, 3, 1};
        // The first output column overwrites the second input column.
        const DenseMatrixView primal{storage.data() + 1, 2, 2, 3, -1};
        const auto result = solve_homogeneous_equality_qp_batch(row_major(hessian, 2, 2),
                                                                ConstDenseMatrixView::row_major(nullptr, 0, 2),
                                                                gradient,
                                                                primal,
                                                                DenseMatrixView::row_major(nullptr, 0, 2));
        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(linf_difference(storage, {5, 2, 77, -3, -1, 77}) < 1e-12);
    }

    void test_homogeneous_batch_rejects_invalid_inputs() {
        const std::vector<double> identity{1, 0, 0, 1}, equality{1, 0};
        const auto hessian = row_major(identity, 2, 2);
        const auto equalities = row_major(equality, 1, 2);
        std::vector<double> primal_storage(4, 123), dual_storage(2, 456);
        const auto primal = DenseMatrixView::row_major(primal_storage.data(), 2, 2);
        const auto dual = DenseMatrixView::row_major(dual_storage.data(), 1, 2);
        const auto check = [&](ConstDenseMatrixView coefficients,
                               ConstDenseMatrixView gradients,
                               DenseMatrixView primal_out,
                               DenseMatrixView dual_out,
                               QpDiagnostic expected) {
            const auto result =
                solve_homogeneous_equality_qp_batch(coefficients, equalities, gradients, primal_out, dual_out);
            TERMIN_QOPT_CHECK(result.status == QpStatus::InvalidInput && result.diagnostic == expected);
            TERMIN_QOPT_CHECK(std::ranges::all_of(primal_storage, [](double v) { return v == 123; }));
            TERMIN_QOPT_CHECK(std::ranges::all_of(dual_storage, [](double v) { return v == 456; }));
        };
        const std::vector<double> asymmetric{1, 1, 0, 1}, invalid{1, 0, 0, std::numeric_limits<double>::infinity()};
        check(row_major(asymmetric, 2, 2), hessian, primal, dual, QpDiagnostic::NonSymmetricHessian);
        check(hessian, row_major(invalid, 2, 2), primal, dual, QpDiagnostic::NonFiniteInput);
        check(hessian, {identity.data(), 2, 2, 0, 1}, primal, dual, QpDiagnostic::InvalidStride);
        check(hessian, row_major(identity, 2, 1), primal, dual, QpDiagnostic::DimensionMismatch);
        check(hessian, hessian, {primal_storage.data(), 2, 2, 1, 1}, dual, QpDiagnostic::OverlappingOutputs);
        check(hessian,
              hessian,
              primal,
              DenseMatrixView::row_major(primal_storage.data() + 1, 1, 2),
              QpDiagnostic::OverlappingOutputs);
        check(hessian,
              row_major(identity, 2, 0),
              DenseMatrixView::row_major(nullptr, 2, 0),
              DenseMatrixView::row_major(nullptr, 1, 0),
              QpDiagnostic::DimensionMismatch);
    }

} // namespace

int main() {
    test_shared_oracle();
    test_redundant_equalities_and_minimum_norm_dual();
    test_constraint_row_scaling_does_not_change_the_solution();
    test_strided_views();
    test_input_output_aliasing_uses_snapshot_semantics();
    test_invalid_inputs_are_diagnostic_and_do_not_write_outputs();
    test_nonconvex_and_overlapping_outputs();
    test_factorization_cache_reuses_only_exact_coefficients();
    test_factorization_cache_preserves_rhs_diagnostics();
    test_unconstrained_spectral_classification_matches_general_path();
    test_unconstrained_strided_aliasing();
    test_cache_switches_constraint_modes_and_spectral_tolerance();
    test_homogeneous_batch_matches_cached_columns();
    test_cached_spd_solve_recovers_after_overflowing_rhs();
    test_unconstrained_solvers_at_spectral_rank_and_symmetry_boundaries();
    test_homogeneous_batch_snapshots_strided_gradients();
    test_homogeneous_batch_rejects_invalid_inputs();
    return 0;
}
