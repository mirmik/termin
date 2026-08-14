#include <termin/qopt/hqp.hpp>
#include <termin/qopt/subspaces.hpp>

#include "qp_oracle_cases.hpp"
#include "test_check.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

using namespace termin::qopt;

namespace {

    [[nodiscard]] ConstDenseMatrixView view(const OracleDenseMatrix& matrix) {
        return ConstDenseMatrixView::row_major(matrix.values.data(), matrix.rows, matrix.columns);
    }

    [[nodiscard]] ConstDenseVectorView view(const std::vector<double>& vector) {
        return {vector.data(), vector.size(), 1};
    }

    [[nodiscard]] double linf_difference(const std::vector<double>& first, const std::vector<double>& second) {
        double result = 0.0;
        for (std::size_t index = 0; index < first.size(); ++index) {
            result = std::max(result, std::abs(first[index] - second[index]));
        }
        return result;
    }

} // namespace

int main() {
    for (const OracleNullspaceCase& oracle : nullspace_oracle_cases()) {
        for (const NullspaceMethod method : {
                 NullspaceMethod::RankRevealingQr,
                 NullspaceMethod::Svd,
             }) {
            std::vector<double> basis(oracle.matrix.columns * oracle.matrix.columns, -77.0);
            const NullspaceResult result = write_nullspace_basis(
                view(oracle.matrix),
                DenseMatrixView::row_major(basis.data(), oracle.matrix.columns, oracle.matrix.columns),
                {
                    .method = method,
                    .tolerance =
                        {
                            .absolute = oracle.absolute_tolerance,
                            .relative = 0.0,
                            .symmetry = 1e-10,
                        },
                });
            TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
            TERMIN_QOPT_CHECK(result.rank == oracle.expected_rank);
            TERMIN_QOPT_CHECK(result.nullity == oracle.expected_nullity);
            TERMIN_QOPT_CHECK(result.residual_linf <= oracle.residual_linf);
            TERMIN_QOPT_CHECK(result.orthogonality_linf <= oracle.orthogonality_linf);
            for (std::size_t column = result.nullity; column < oracle.matrix.columns; ++column) {
                for (std::size_t row = 0; row < oracle.matrix.columns; ++row) {
                    TERMIN_QOPT_CHECK(basis[row * oracle.matrix.columns + column] == 0.0);
                }
            }
        }
    }

    const std::vector<double> projector_matrix{
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
    };
    std::vector<double> projector(9);
    const NullspaceResult projector_result =
        write_nullspace_projector(ConstDenseMatrixView::row_major(projector_matrix.data(), 2, 3),
                                  DenseMatrixView::row_major(projector.data(), 3, 3));
    TERMIN_QOPT_CHECK(projector_result.status == QpStatus::Optimal);
    TERMIN_QOPT_CHECK(std::abs(projector[8] - 1.0) < 1e-12);
    TERMIN_QOPT_CHECK(std::abs(projector[0]) < 1e-12);
    TERMIN_QOPT_CHECK(write_nullspace_basis(ConstDenseMatrixView::row_major(projector_matrix.data(), 2, 3),
                                            DenseMatrixView::row_major(projector.data(), 2, 3))
                          .diagnostic == QpDiagnostic::DimensionMismatch);

    for (const OracleHqpCase& oracle : hqp_oracle_cases()) {
        HierarchicalQpSolver solver(oracle.variables);
        for (const OracleHqpLevel& encoded_level : oracle.levels) {
            const HqpLevelRegistrationResult level = solver.add_level(encoded_level.priority);
            TERMIN_QOPT_CHECK(level.ok());
            for (const OracleHqpTask& task : encoded_level.tasks) {
                TERMIN_QOPT_CHECK(solver.add_task(level.handle,
                                                  {
                                                      view(task.jacobian),
                                                      view(task.target),
                                                      view(task.weight),
                                                  }) == HqpDiagnostic::None);
            }
            for (const OracleHqpConstraint& equality : encoded_level.equalities) {
                TERMIN_QOPT_CHECK(solver.add_equality(level.handle, {view(equality.matrix), view(equality.target)}) ==
                                  HqpDiagnostic::None);
            }
            for (const OracleHqpConstraint& inequality : encoded_level.inequalities) {
                TERMIN_QOPT_CHECK(
                    solver.add_inequality(level.handle, {view(inequality.matrix), view(inequality.target)}) ==
                    HqpDiagnostic::None);
            }
        }

        std::vector<double> primal(oracle.variables);
        std::vector<double> residuals(oracle.levels.size());
        const HqpSolveResult result = solver.solve({
            {primal.data(), primal.size(), 1},
            {residuals.data(), residuals.size(), 1},
        });
        TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
        TERMIN_QOPT_CHECK(result.levels_solved == oracle.levels.size());
        TERMIN_QOPT_CHECK(result.priority_violation_linf <= oracle.level_residual_tolerance);
        TERMIN_QOPT_CHECK(linf_difference(primal, oracle.expected_primal) <= oracle.primal_linf);
        TERMIN_QOPT_CHECK(linf_difference(residuals, oracle.expected_level_residuals) <=
                          oracle.level_residual_tolerance);
    }

    HierarchicalQpSolver overconstrained(1);
    const auto high = overconstrained.add_level(0);
    const auto low = overconstrained.add_level(1);
    TERMIN_QOPT_CHECK(high.ok());
    TERMIN_QOPT_CHECK(low.ok());
    TERMIN_QOPT_CHECK(overconstrained.add_level(1).diagnostic == HqpDiagnostic::DuplicatePriority);
    const double one[] = {1.0};
    const double zero[] = {0.0};
    TERMIN_QOPT_CHECK(overconstrained.add_task(high.handle,
                                               {
                                                   ConstDenseMatrixView::row_major(one, 1, 1),
                                                   {zero, 1, 1},
                                                   {},
                                               }) == HqpDiagnostic::None);
    TERMIN_QOPT_CHECK(overconstrained.add_equality(low.handle,
                                                   {
                                                       ConstDenseMatrixView::row_major(one, 1, 1),
                                                       {one, 1, 1},
                                                   }) == HqpDiagnostic::None);
    double failed_primal = 42.0;
    double failed_residuals[] = {42.0, 42.0};
    const HqpSolveResult failed = overconstrained.solve({
        {&failed_primal, 1, 1},
        {failed_residuals, 2, 1},
    });
    TERMIN_QOPT_CHECK(failed.status == QpStatus::Infeasible);
    TERMIN_QOPT_CHECK(failed.diagnostic == HqpDiagnostic::LevelSolveFailure);
    TERMIN_QOPT_CHECK(failed.failed_level == 1);
    TERMIN_QOPT_CHECK(failed_primal == 42.0);
    TERMIN_QOPT_CHECK(failed_residuals[0] == 42.0);

    HierarchicalQpSolver semidefinite_weight(2);
    const auto weighted_high = semidefinite_weight.add_level(0);
    const auto weighted_low = semidefinite_weight.add_level(1);
    const double identity[] = {
        1.0,
        0.0,
        0.0,
        1.0,
    };
    const double high_target[] = {1.0, 99.0};
    const double high_weight[] = {
        1.0,
        0.0,
        0.0,
        0.0,
    };
    const double low_target[] = {8.0, 3.0};
    TERMIN_QOPT_CHECK(semidefinite_weight.add_task(weighted_high.handle,
                                                   {
                                                       ConstDenseMatrixView::row_major(identity, 2, 2),
                                                       {high_target, 2, 1},
                                                       ConstDenseMatrixView::row_major(high_weight, 2, 2),
                                                   }) == HqpDiagnostic::None);
    TERMIN_QOPT_CHECK(semidefinite_weight.add_task(weighted_low.handle,
                                                   {
                                                       ConstDenseMatrixView::row_major(identity, 2, 2),
                                                       {low_target, 2, 1},
                                                       {},
                                                   }) == HqpDiagnostic::None);
    double weighted_primal[2] = {};
    double weighted_residuals[2] = {};
    const HqpSolveResult weighted_result = semidefinite_weight.solve({
        {weighted_primal, 2, 1},
        {weighted_residuals, 2, 1},
    });
    TERMIN_QOPT_CHECK(weighted_result.status == QpStatus::Optimal);
    TERMIN_QOPT_CHECK(std::abs(weighted_primal[0] - 1.0) < 1e-10);
    TERMIN_QOPT_CHECK(std::abs(weighted_primal[1] - 3.0) < 1e-10);

    return 0;
}
