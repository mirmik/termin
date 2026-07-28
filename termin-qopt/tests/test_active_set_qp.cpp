#include <termin/qopt/qopt.hpp>

#include "qp_oracle_cases.hpp"
#include "test_check.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <ranges>
#include <string_view>
#include <vector>

namespace {

using namespace termin::qopt;

[[nodiscard]] ConstDenseVectorView
const_vector(const std::vector<double> &values) {
  return {values.data(), values.size()};
}

[[nodiscard]] DenseVectorView vector(std::vector<double> &values) {
  return {values.data(), values.size()};
}

[[nodiscard]] ConstDenseMatrixView row_major(const std::vector<double> &values,
                                             std::size_t rows,
                                             std::size_t columns) {
  return ConstDenseMatrixView::row_major(values.data(), rows, columns);
}

[[nodiscard]] double linf_difference(const std::vector<double> &left,
                                     const std::vector<double> &right) {
  TERMIN_QOPT_CHECK(left.size() == right.size());
  double result = 0.0;
  for (std::size_t index = 0; index < left.size(); ++index) {
    result = std::max(result, std::abs(left[index] - right[index]));
  }
  return result;
}

[[nodiscard]] bool all_equal(const std::vector<double> &values,
                             double expected) {
  return std::ranges::all_of(
      values, [expected](double value) { return value == expected; });
}

void test_shared_oracle() {
  const std::vector<double> no_values;
  for (const OracleActiveSetQpCase &test_case : active_set_qp_oracle_cases()) {
    std::vector<double> primal(test_case.variables, 123.0);
    std::vector<double> equality_dual(test_case.equalities_count, 456.0);
    std::vector<double> inequality_dual(test_case.inequalities_count, 789.0);
    const QpSolveResult result = solve_active_set_qp(
        {
            row_major(test_case.hessian, test_case.variables,
                      test_case.variables),
            const_vector(test_case.gradient),
            row_major(test_case.equalities, test_case.equalities_count,
                      test_case.variables),
            const_vector(test_case.equality_targets),
            row_major(test_case.inequalities, test_case.inequalities_count,
                      test_case.variables),
            const_vector(test_case.inequality_limits),
            const_vector(no_values),
            const_vector(no_values),
        },
        {
            vector(primal),
            vector(equality_dual),
            vector(inequality_dual),
            {nullptr, 0, 1},
            {nullptr, 0, 1},
        });

    TERMIN_QOPT_CHECK(qp_status_name(result.status) == test_case.status);
    if (result.status == QpStatus::Optimal) {
      TERMIN_QOPT_CHECK(linf_difference(primal, test_case.expected_primal) <=
                        test_case.primal_linf);
      TERMIN_QOPT_CHECK(result.stationarity_linf <=
                        test_case.stationarity_linf);
      TERMIN_QOPT_CHECK(result.equality_linf <= test_case.equality_linf);
      TERMIN_QOPT_CHECK(result.inequality_linf <= test_case.inequality_linf);
      TERMIN_QOPT_CHECK(result.dual_linf <= test_case.dual_linf);
      TERMIN_QOPT_CHECK(result.complementarity_linf <=
                        test_case.complementarity_linf);
    } else {
      TERMIN_QOPT_CHECK(all_equal(primal, 123.0));
      TERMIN_QOPT_CHECK(all_equal(equality_dual, 456.0));
      TERMIN_QOPT_CHECK(all_equal(inequality_dual, 789.0));
    }
  }
}

void test_bounds_and_full_duals() {
  const std::vector<double> hessian{2.0, 0.0, 0.0, 2.0};
  const std::vector<double> gradient{-4.0, 4.0};
  const std::vector<double> no_values;
  const std::vector<double> lower{-std::numeric_limits<double>::infinity(),
                                  -1.0};
  const std::vector<double> upper{1.0, std::numeric_limits<double>::infinity()};
  std::vector<double> primal(2);
  std::vector<double> lower_dual(2);
  std::vector<double> upper_dual(2);

  const QpSolveResult result = solve_active_set_qp(
      {
          row_major(hessian, 2, 2),
          const_vector(gradient),
          row_major(no_values, 0, 2),
          const_vector(no_values),
          row_major(no_values, 0, 2),
          const_vector(no_values),
          const_vector(lower),
          const_vector(upper),
      },
      {
          vector(primal),
          {nullptr, 0, 1},
          {nullptr, 0, 1},
          vector(lower_dual),
          vector(upper_dual),
      });

  TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
  TERMIN_QOPT_CHECK(std::abs(primal[0] - 1.0) <= 1e-9);
  TERMIN_QOPT_CHECK(std::abs(primal[1] + 1.0) <= 1e-9);
  TERMIN_QOPT_CHECK(std::abs(upper_dual[0] - 2.0) <= 1e-9);
  TERMIN_QOPT_CHECK(std::abs(lower_dual[1] - 2.0) <= 1e-9);
  TERMIN_QOPT_CHECK(lower_dual[0] == 0.0);
  TERMIN_QOPT_CHECK(upper_dual[1] == 0.0);
}

void test_warm_start_can_drop_an_incorrect_constraint() {
  const std::vector<double> hessian{2.0};
  const std::vector<double> gradient{0.0};
  const std::vector<double> no_values;
  const std::vector<double> upper{0.5};
  const std::vector<double> warm_primal{0.5};
  const std::vector<double> active_upper{1.0};
  std::vector<double> primal(1);
  std::vector<double> upper_dual(1);

  const QpSolveResult result = solve_active_set_qp(
      {
          row_major(hessian, 1, 1),
          const_vector(gradient),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          const_vector(no_values),
          const_vector(upper),
      },
      {
          vector(primal),
          {nullptr, 0, 1},
          {nullptr, 0, 1},
          {nullptr, 0, 1},
          vector(upper_dual),
      },
      {
          const_vector(warm_primal),
          const_vector(no_values),
          const_vector(no_values),
          const_vector(active_upper),
      });

  TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
  TERMIN_QOPT_CHECK(std::abs(primal[0]) <= 1e-10);
  TERMIN_QOPT_CHECK(upper_dual[0] == 0.0);
  TERMIN_QOPT_CHECK(result.active_set_size == 0);
}

void test_linear_recession_is_blocked_or_reported_unbounded() {
  const std::vector<double> hessian{0.0};
  const std::vector<double> gradient{-1.0};
  const std::vector<double> no_values;
  const std::vector<double> upper_row{1.0};
  const std::vector<double> upper_limit{1.0};
  std::vector<double> primal(1, 123.0);
  std::vector<double> dual(1, 456.0);

  QpSolveResult result = solve_active_set_qp(
      {
          row_major(hessian, 1, 1),
          const_vector(gradient),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          row_major(upper_row, 1, 1),
          const_vector(upper_limit),
          const_vector(no_values),
          const_vector(no_values),
      },
      {
          vector(primal),
          {nullptr, 0, 1},
          vector(dual),
          {nullptr, 0, 1},
          {nullptr, 0, 1},
      });
  TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
  TERMIN_QOPT_CHECK(std::abs(primal[0] - 1.0) <= 1e-9);
  TERMIN_QOPT_CHECK(std::abs(dual[0] - 1.0) <= 1e-9);

  const std::vector<double> lower_row{-1.0};
  const std::vector<double> lower_limit{0.0};
  primal[0] = 123.0;
  dual[0] = 456.0;
  result = solve_active_set_qp(
      {
          row_major(hessian, 1, 1),
          const_vector(gradient),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          row_major(lower_row, 1, 1),
          const_vector(lower_limit),
          const_vector(no_values),
          const_vector(no_values),
      },
      {
          vector(primal),
          {nullptr, 0, 1},
          vector(dual),
          {nullptr, 0, 1},
          {nullptr, 0, 1},
      });
  TERMIN_QOPT_CHECK(result.status == QpStatus::Unbounded);
  TERMIN_QOPT_CHECK(all_equal(primal, 123.0));
  TERMIN_QOPT_CHECK(all_equal(dual, 456.0));
}

void test_inconsistent_bounds_are_infeasible() {
  const std::vector<double> hessian{2.0};
  const std::vector<double> gradient{0.0};
  const std::vector<double> no_values;
  const std::vector<double> lower{1.0};
  const std::vector<double> upper{0.0};
  std::vector<double> primal(1, 123.0);
  std::vector<double> lower_dual(1, 456.0);
  std::vector<double> upper_dual(1, 789.0);

  const QpSolveResult result = solve_active_set_qp(
      {
          row_major(hessian, 1, 1),
          const_vector(gradient),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          const_vector(lower),
          const_vector(upper),
      },
      {
          vector(primal),
          {nullptr, 0, 1},
          {nullptr, 0, 1},
          vector(lower_dual),
          vector(upper_dual),
      });

  TERMIN_QOPT_CHECK(result.status == QpStatus::Infeasible);
  TERMIN_QOPT_CHECK(result.diagnostic ==
                    QpDiagnostic::InconsistentInequalities);
  TERMIN_QOPT_CHECK(all_equal(primal, 123.0));
  TERMIN_QOPT_CHECK(all_equal(lower_dual, 456.0));
  TERMIN_QOPT_CHECK(all_equal(upper_dual, 789.0));
}

void test_invalid_warm_start_and_iteration_limit_do_not_write() {
  const std::vector<double> hessian{2.0};
  const std::vector<double> gradient{-2.0};
  const std::vector<double> no_values;
  const std::vector<double> inequality{1.0};
  const std::vector<double> limit{0.5};
  const std::vector<double> invalid_warm{1.0};
  std::vector<double> primal(1, 123.0);
  std::vector<double> dual(1, 456.0);

  QpSolveResult result = solve_active_set_qp(
      {
          row_major(hessian, 1, 1),
          const_vector(gradient),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          row_major(inequality, 1, 1),
          const_vector(limit),
          const_vector(no_values),
          const_vector(no_values),
      },
      {
          vector(primal),
          {nullptr, 0, 1},
          vector(dual),
          {nullptr, 0, 1},
          {nullptr, 0, 1},
      },
      {const_vector(invalid_warm), {}, {}, {}});
  TERMIN_QOPT_CHECK(result.status == QpStatus::InvalidInput);
  TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::InvalidWarmStart);
  TERMIN_QOPT_CHECK(all_equal(primal, 123.0));

  ActiveSetQpOptions options;
  options.max_iterations = 1;
  result = solve_active_set_qp(
      {
          row_major(hessian, 1, 1),
          const_vector(gradient),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          row_major(inequality, 1, 1),
          const_vector(limit),
          const_vector(no_values),
          const_vector(no_values),
      },
      {
          vector(primal),
          {nullptr, 0, 1},
          vector(dual),
          {nullptr, 0, 1},
          {nullptr, 0, 1},
      },
      {}, options);
  TERMIN_QOPT_CHECK(result.status == QpStatus::NumericalFailure);
  TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::IterationLimit);
  TERMIN_QOPT_CHECK(all_equal(primal, 123.0));
  TERMIN_QOPT_CHECK(all_equal(dual, 456.0));
}

void test_nonconvexity_and_output_overlap_are_rejected() {
  const std::vector<double> negative_hessian{-1.0};
  const std::vector<double> gradient{0.0};
  const std::vector<double> no_values;
  const std::vector<double> upper{1.0};
  std::vector<double> output(1, 123.0);

  QpSolveResult result = solve_active_set_qp(
      {
          row_major(negative_hessian, 1, 1),
          const_vector(gradient),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          const_vector(no_values),
          const_vector(upper),
      },
      {
          vector(output),
          {nullptr, 0, 1},
          {nullptr, 0, 1},
          {nullptr, 0, 1},
          vector(output),
      });
  TERMIN_QOPT_CHECK(result.status == QpStatus::InvalidInput);
  TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::OverlappingOutputs);

  std::vector<double> upper_dual(1);
  result = solve_active_set_qp(
      {
          row_major(negative_hessian, 1, 1),
          const_vector(gradient),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          row_major(no_values, 0, 1),
          const_vector(no_values),
          const_vector(no_values),
          const_vector(upper),
      },
      {
          vector(output),
          {nullptr, 0, 1},
          {nullptr, 0, 1},
          {nullptr, 0, 1},
          vector(upper_dual),
      });
  TERMIN_QOPT_CHECK(result.status == QpStatus::NonConvex);
  TERMIN_QOPT_CHECK(result.diagnostic == QpDiagnostic::NegativeCurvature);
}

void test_deterministic_2d_corpus_against_active_subset_oracle() {
  const std::vector<double> hessian{2.0, 0.3, 0.3, 1.5};
  const std::vector<double> inequalities{
      1.0, 0.0, -1.0, 0.0, 0.0, 1.0, 0.0, -1.0, 1.0, 1.0,
  };
  const std::vector<double> limits{1.0, 1.0, 1.0, 1.0, 1.2};
  const std::vector<double> no_values;

  for (int gx = -4; gx <= 4; gx += 2) {
    for (int gy = -3; gy <= 3; gy += 2) {
      const std::vector<double> gradient{static_cast<double>(gx),
                                         static_cast<double>(gy)};
      std::vector<double> expected;
      double expected_objective = std::numeric_limits<double>::infinity();

      for (std::size_t mask = 0; mask < (std::size_t{1} << 5); ++mask) {
        std::vector<double> active_rows;
        std::vector<double> active_limits;
        std::vector<std::size_t> active_indices;
        for (std::size_t row = 0; row < 5; ++row) {
          if ((mask & (std::size_t{1} << row)) == 0) {
            continue;
          }
          active_rows.push_back(inequalities[row * 2]);
          active_rows.push_back(inequalities[row * 2 + 1]);
          active_limits.push_back(limits[row]);
          active_indices.push_back(row);
        }

        std::vector<double> candidate(2);
        std::vector<double> dual(active_indices.size());
        const QpSolveResult subset = solve_equality_qp(
            {
                row_major(hessian, 2, 2),
                const_vector(gradient),
                row_major(active_rows, active_indices.size(), 2),
                const_vector(active_limits),
            },
            {vector(candidate), vector(dual)});
        if (subset.status != QpStatus::Optimal ||
            std::ranges::any_of(dual,
                                [](double value) { return value < -1e-9; })) {
          continue;
        }

        bool feasible = true;
        for (std::size_t row = 0; row < 5; ++row) {
          const double value = inequalities[row * 2] * candidate[0] +
                               inequalities[row * 2 + 1] * candidate[1];
          feasible = feasible && value <= limits[row] + 1e-9;
        }
        if (!feasible) {
          continue;
        }

        const double objective =
            candidate[0] * candidate[0] + 0.3 * candidate[0] * candidate[1] +
            0.75 * candidate[1] * candidate[1] + gradient[0] * candidate[0] +
            gradient[1] * candidate[1];
        if (objective < expected_objective) {
          expected_objective = objective;
          expected = candidate;
        }
      }
      TERMIN_QOPT_CHECK(expected.size() == 2);

      std::vector<double> primal(2);
      std::vector<double> dual(5);
      const QpSolveResult result = solve_active_set_qp(
          {
              row_major(hessian, 2, 2),
              const_vector(gradient),
              row_major(no_values, 0, 2),
              const_vector(no_values),
              row_major(inequalities, 5, 2),
              const_vector(limits),
              const_vector(no_values),
              const_vector(no_values),
          },
          {
              vector(primal),
              {nullptr, 0, 1},
              vector(dual),
              {nullptr, 0, 1},
              {nullptr, 0, 1},
          });
      TERMIN_QOPT_CHECK(result.status == QpStatus::Optimal);
      TERMIN_QOPT_CHECK(linf_difference(primal, expected) <= 1e-8);
      TERMIN_QOPT_CHECK(result.stationarity_linf <= 1e-9);
      TERMIN_QOPT_CHECK(result.inequality_linf <= 1e-9);
      TERMIN_QOPT_CHECK(result.dual_linf <= 1e-9);
      TERMIN_QOPT_CHECK(result.complementarity_linf <= 1e-9);
    }
  }
}

} // namespace

int main() {
  test_shared_oracle();
  test_bounds_and_full_duals();
  test_warm_start_can_drop_an_incorrect_constraint();
  test_linear_recession_is_blocked_or_reported_unbounded();
  test_inconsistent_bounds_are_infeasible();
  test_invalid_warm_start_and_iteration_limit_do_not_write();
  test_nonconvexity_and_output_overlap_are_rejected();
  test_deterministic_2d_corpus_against_active_subset_oracle();
  return 0;
}
