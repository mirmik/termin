#include <termin/physics_qopt/contact_friction.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <numbers>
#include <vector>

#include <termin/physics_qopt/dynamics.hpp>

namespace termin::physics_qopt {
    namespace {
        QpSolveResult invalid_result(QpDiagnostic diagnostic) noexcept {
            QpSolveResult result;
            result.status = QpStatus::InvalidInput;
            result.diagnostic = diagnostic;
            return result;
        }

        bool valid(ConstDenseVectorView view) noexcept {
            return view.empty() || (view.data != nullptr && view.stride > 0);
        }

        bool valid(DenseVectorView view) noexcept {
            return view.empty() || (view.data != nullptr && view.stride > 0);
        }

        bool valid(ConstDenseMatrixView view) noexcept {
            return view.empty() || (view.data != nullptr && view.row_stride > 0 && view.column_stride > 0);
        }

        bool finite(ConstDenseVectorView view) noexcept {
            for (std::size_t index = 0; index < view.size; ++index) {
                if (!std::isfinite(view[index])) {
                    return false;
                }
            }
            return true;
        }

        bool finite(ConstDenseMatrixView view) noexcept {
            for (std::size_t row = 0; row < view.rows; ++row) {
                for (std::size_t column = 0; column < view.columns; ++column) {
                    if (!std::isfinite(view(row, column))) {
                        return false;
                    }
                }
            }
            return true;
        }
    } // namespace

    QpSolveResult solve_contact_friction(ContactFrictionProblemView problem,
                                         ContactFrictionSolutionView solution,
                                         ContactFrictionOptions options) noexcept {
        const std::size_t dofs = problem.normal_projected_velocity.size;
        const std::size_t contacts = problem.normal_impulse.size;
        const std::size_t normal_constraints = problem.minimum_normal_velocity.size;
        const std::size_t tangents = contacts * 2;
        const std::size_t variables = contacts * 3;
        const std::size_t bilateral = problem.bilateral_jacobian.rows;
        if (problem.mass.rows != dofs || problem.mass.columns != dofs || problem.bilateral_jacobian.columns != dofs ||
            problem.normal_jacobian.rows != normal_constraints || problem.normal_jacobian.columns != dofs ||
            problem.contact_normal_jacobian.rows != contacts || problem.contact_normal_jacobian.columns != dofs ||
            problem.contact_normal_rows.size() != contacts || problem.tangent_jacobian.rows != tangents ||
            problem.tangent_jacobian.columns != dofs || problem.friction_coefficient.size != contacts ||
            solution.velocity.size != dofs || solution.tangent_impulse.size != tangents ||
            (!solution.normal_impulse.empty() && solution.normal_impulse.size != contacts) ||
            (!solution.friction_work.empty() && solution.friction_work.size != contacts) ||
            (!solution.bilateral_impulse.empty() && solution.bilateral_impulse.size != bilateral)) {
            return invalid_result(QpDiagnostic::DimensionMismatch);
        }
        if (!valid(problem.mass) || !valid(problem.bilateral_jacobian) || !valid(problem.normal_projected_velocity) ||
            !valid(problem.normal_jacobian) || !valid(problem.minimum_normal_velocity) ||
            !valid(problem.contact_normal_jacobian) ||
            (contacts != 0 && problem.contact_normal_rows.data() == nullptr) || !valid(problem.tangent_jacobian) ||
            !valid(problem.normal_impulse) || !valid(problem.friction_coefficient) || !valid(solution.velocity) ||
            !valid(solution.tangent_impulse) || !valid(solution.normal_impulse) || !valid(solution.friction_work) ||
            !valid(solution.bilateral_impulse)) {
            return invalid_result(QpDiagnostic::NullData);
        }
        if (options.cone_facets < 4 || options.cone_facets % 2 != 0) {
            return invalid_result(QpDiagnostic::InvalidOptions);
        }
        if (!finite(problem.mass) || !finite(problem.bilateral_jacobian) ||
            !finite(problem.normal_projected_velocity) || !finite(problem.normal_jacobian) ||
            !finite(problem.minimum_normal_velocity) || !finite(problem.contact_normal_jacobian) ||
            !finite(problem.tangent_jacobian) || !finite(problem.normal_impulse) ||
            !finite(problem.friction_coefficient)) {
            return invalid_result(QpDiagnostic::NonFiniteInput);
        }
        std::vector<double> base_normal_impulse(contacts);
        std::vector<bool> normal_row_claimed(normal_constraints, false);
        for (std::size_t contact = 0; contact < contacts; ++contact) {
            const std::size_t normal_row = problem.contact_normal_rows[contact];
            if (normal_row >= normal_constraints || normal_row_claimed[normal_row]) {
                return invalid_result(QpDiagnostic::DimensionMismatch);
            }
            normal_row_claimed[normal_row] = true;
            for (std::size_t dof = 0; dof < dofs; ++dof) {
                const double contact_coefficient = problem.contact_normal_jacobian(contact, dof);
                const double global_coefficient = problem.normal_jacobian(normal_row, dof);
                const double scale = std::max({1.0, std::abs(contact_coefficient), std::abs(global_coefficient)});
                if (std::abs(contact_coefficient - global_coefficient) > options.qp.active_tolerance * scale) {
                    return invalid_result(QpDiagnostic::DimensionMismatch);
                }
            }
            if (problem.normal_impulse[contact] < -options.qp.active_tolerance ||
                problem.friction_coefficient[contact] < 0.0) {
                return invalid_result(QpDiagnostic::InvalidBounds);
            }
            // The preceding unilateral solve is feasible only up to the QP
            // tolerance. Preserve the physical non-negative impulse invariant
            // at the boundary passed to the friction solve.
            base_normal_impulse[contact] = std::max(problem.normal_impulse[contact], 0.0);
        }
        for (std::size_t row = 0; row < normal_constraints; ++row) {
            double normal_velocity = 0.0;
            for (std::size_t dof = 0; dof < dofs; ++dof) {
                normal_velocity += problem.normal_jacobian(row, dof) * problem.normal_projected_velocity[dof];
            }
            if (normal_velocity + options.qp.active_tolerance < problem.minimum_normal_velocity[row]) {
                return invalid_result(QpDiagnostic::InvalidWarmStart);
            }
        }

        try {
            std::vector<double> output_velocity(dofs);
            std::vector<double> output_impulse(tangents, 0.0);
            std::vector<double> output_normal_impulse(contacts, 0.0);
            std::vector<double> variable_impulse(variables, 0.0);
            if (contacts == 0) {
                for (std::size_t dof = 0; dof < dofs; ++dof) {
                    output_velocity[dof] = problem.normal_projected_velocity[dof];
                }
                for (std::size_t dof = 0; dof < dofs; ++dof) {
                    solution.velocity[dof] = output_velocity[dof];
                }
                for (std::size_t row = 0; row < solution.bilateral_impulse.size; ++row) {
                    solution.bilateral_impulse[row] = 0.0;
                }
                QpSolveResult result;
                result.status = QpStatus::Optimal;
                return result;
            }

            bool any_capacity = false;
            for (std::size_t contact = 0; contact < contacts; ++contact) {
                any_capacity |= base_normal_impulse[contact] > 0.0 && problem.friction_coefficient[contact] > 0.0;
            }
            if (!any_capacity) {
                for (std::size_t dof = 0; dof < dofs; ++dof) {
                    solution.velocity[dof] = problem.normal_projected_velocity[dof];
                }
                for (std::size_t tangent = 0; tangent < tangents; ++tangent) {
                    solution.tangent_impulse[tangent] = 0.0;
                }
                for (std::size_t contact = 0; contact < solution.normal_impulse.size; ++contact) {
                    solution.normal_impulse[contact] = base_normal_impulse[contact];
                }
                for (std::size_t contact = 0; contact < solution.friction_work.size; ++contact) {
                    solution.friction_work[contact] = 0.0;
                }
                for (std::size_t row = 0; row < solution.bilateral_impulse.size; ++row) {
                    solution.bilateral_impulse[row] = 0.0;
                }
                QpSolveResult result;
                result.status = QpStatus::Optimal;
                return result;
            }

            // K maps variable impulses to bilateral-compatible velocity
            // corrections: delta_v = K * p.
            std::vector<double> response(dofs * variables, 0.0);
            std::vector<double> bilateral_response(bilateral * variables, 0.0);
            std::vector<double> load(dofs, 0.0);
            std::vector<double> correction(dofs, 0.0);
            std::vector<double> equality_reaction(bilateral, 0.0);
            std::vector<double> zero_rhs(bilateral, 0.0);
            for (std::size_t variable = 0; variable < variables; ++variable) {
                const std::size_t contact = variable / 3;
                const std::size_t axis = variable % 3;
                for (std::size_t dof = 0; dof < dofs; ++dof) {
                    load[dof] = axis == 0 ? problem.contact_normal_jacobian(contact, dof)
                                          : problem.tangent_jacobian(contact * 2 + axis - 1, dof);
                }
                const QpSolveResult response_result = solve_constrained_dynamics(
                    {
                        problem.mass,
                        {load.data(), load.size(), 1},
                        problem.bilateral_jacobian,
                        {zero_rhs.data(), zero_rhs.size(), 1},
                    },
                    {
                        {correction.data(), correction.size(), 1},
                        {equality_reaction.data(), equality_reaction.size(), 1},
                    },
                    options.qp.tolerance);
                if (response_result.status != QpStatus::Optimal) {
                    return response_result;
                }
                for (std::size_t dof = 0; dof < dofs; ++dof) {
                    response[dof * variables + variable] = correction[dof];
                }
                for (std::size_t row = 0; row < bilateral; ++row) {
                    bilateral_response[row * variables + variable] = equality_reaction[row];
                }
            }

            std::vector<double> hessian(variables * variables, 0.0);
            std::vector<double> gradient(variables, 0.0);
            for (std::size_t row = 0; row < variables; ++row) {
                const std::size_t contact = row / 3;
                const std::size_t axis = row % 3;
                for (std::size_t dof = 0; dof < dofs; ++dof) {
                    const double jacobian = axis == 0 ? problem.contact_normal_jacobian(contact, dof)
                                                      : problem.tangent_jacobian(contact * 2 + axis - 1, dof);
                    gradient[row] += jacobian * problem.normal_projected_velocity[dof];
                }
                for (std::size_t column = 0; column < variables; ++column) {
                    for (std::size_t dof = 0; dof < dofs; ++dof) {
                        const double jacobian = axis == 0 ? problem.contact_normal_jacobian(contact, dof)
                                                          : problem.tangent_jacobian(contact * 2 + axis - 1, dof);
                        hessian[row * variables + column] += jacobian * response[dof * variables + column];
                    }
                }
            }
            for (std::size_t row = 0; row < variables; ++row) {
                for (std::size_t column = row + 1; column < variables; ++column) {
                    const double symmetric =
                        0.5 * (hessian[row * variables + column] + hessian[column * variables + row]);
                    hessian[row * variables + column] = symmetric;
                    hessian[column * variables + row] = symmetric;
                }
            }

            std::vector<bool> supporting_contact(contacts, false);
            std::vector<bool> supporting_normal_row(normal_constraints, false);
            std::size_t equality_rows = 0;
            for (std::size_t contact = 0; contact < contacts; ++contact) {
                supporting_contact[contact] = base_normal_impulse[contact] > options.qp.active_tolerance;
                if (supporting_contact[contact]) {
                    supporting_normal_row[problem.contact_normal_rows[contact]] = true;
                    ++equality_rows;
                }
            }

            std::vector<double> equalities(equality_rows * variables, 0.0);
            std::vector<double> equality_targets(equality_rows, 0.0);
            std::size_t equality_row = 0;
            for (std::size_t contact = 0; contact < contacts; ++contact) {
                if (!supporting_contact[contact]) {
                    continue;
                }
                for (std::size_t variable = 0; variable < variables; ++variable) {
                    for (std::size_t dof = 0; dof < dofs; ++dof) {
                        equalities[equality_row * variables + variable] +=
                            problem.contact_normal_jacobian(contact, dof) * response[dof * variables + variable];
                    }
                }
                ++equality_row;
            }

            const std::size_t polygon_rows = contacts * options.cone_facets;
            const std::size_t inequality_rows = normal_constraints - equality_rows + contacts + polygon_rows;
            std::vector<double> inequalities(inequality_rows * variables, 0.0);
            std::vector<double> limits(inequality_rows, 0.0);
            std::size_t inequality_row = 0;
            for (std::size_t row = 0; row < normal_constraints; ++row) {
                if (supporting_normal_row[row]) {
                    continue;
                }
                double normal_velocity = 0.0;
                for (std::size_t dof = 0; dof < dofs; ++dof) {
                    normal_velocity += problem.normal_jacobian(row, dof) * problem.normal_projected_velocity[dof];
                }
                limits[inequality_row] = normal_velocity - problem.minimum_normal_velocity[row];
                for (std::size_t variable = 0; variable < variables; ++variable) {
                    for (std::size_t dof = 0; dof < dofs; ++dof) {
                        inequalities[inequality_row * variables + variable] -=
                            problem.normal_jacobian(row, dof) * response[dof * variables + variable];
                    }
                }
                ++inequality_row;
            }

            for (std::size_t contact = 0; contact < contacts; ++contact) {
                const std::size_t lower_row = inequality_row++;
                inequalities[lower_row * variables + contact * 3] = -1.0;
                limits[lower_row] = base_normal_impulse[contact];
                const double radius = problem.friction_coefficient[contact] * base_normal_impulse[contact];
                const double polygon_limit =
                    radius * std::cos(std::numbers::pi / static_cast<double>(options.cone_facets));
                for (std::size_t facet = 0; facet < options.cone_facets; ++facet) {
                    const std::size_t row = inequality_row++;
                    const double angle = (static_cast<double>(facet) + 0.5) * 2.0 * std::numbers::pi /
                                         static_cast<double>(options.cone_facets);
                    inequalities[row * variables + contact * 3] =
                        -problem.friction_coefficient[contact] *
                        std::cos(std::numbers::pi / static_cast<double>(options.cone_facets));
                    inequalities[row * variables + contact * 3 + 1] = std::cos(angle);
                    inequalities[row * variables + contact * 3 + 2] = std::sin(angle);
                    limits[row] = polygon_limit;
                }
            }

            std::vector<double> equality_dual(equality_rows, 0.0);
            std::vector<double> inequality_dual(inequality_rows, 0.0);
            const QpSolveResult result = solve_active_set_qp(
                {
                    ConstDenseMatrixView::row_major(hessian.data(), variables, variables),
                    {gradient.data(), gradient.size(), 1},
                    ConstDenseMatrixView::row_major(equalities.data(), equality_rows, variables),
                    {equality_targets.data(), equality_targets.size(), 1},
                    ConstDenseMatrixView::row_major(inequalities.data(), inequality_rows, variables),
                    {limits.data(), limits.size(), 1},
                    {},
                    {},
                },
                {
                    {variable_impulse.data(), variable_impulse.size(), 1},
                    {equality_dual.data(), equality_dual.size(), 1},
                    {inequality_dual.data(), inequality_dual.size(), 1},
                    {},
                    {},
                },
                {},
                options.qp);
            if (result.status != QpStatus::Optimal) {
                return result;
            }

            for (std::size_t dof = 0; dof < dofs; ++dof) {
                output_velocity[dof] = problem.normal_projected_velocity[dof];
                for (std::size_t variable = 0; variable < variables; ++variable) {
                    output_velocity[dof] += response[dof * variables + variable] * variable_impulse[variable];
                }
            }
            for (std::size_t contact = 0; contact < contacts; ++contact) {
                output_normal_impulse[contact] = base_normal_impulse[contact] + variable_impulse[contact * 3];
                output_impulse[contact * 2] = variable_impulse[contact * 3 + 1];
                output_impulse[contact * 2 + 1] = variable_impulse[contact * 3 + 2];
            }
            std::vector<double> contact_work(contacts, 0.0);
            for (std::size_t contact = 0; contact < contacts; ++contact) {
                for (std::size_t axis = 0; axis < 2; ++axis) {
                    const std::size_t tangent = contact * 2 + axis;
                    double final_tangent_velocity = 0.0;
                    for (std::size_t dof = 0; dof < dofs; ++dof) {
                        final_tangent_velocity += problem.tangent_jacobian(tangent, dof) * output_velocity[dof];
                    }
                    contact_work[contact] +=
                        0.5 * (gradient[contact * 3 + axis + 1] + final_tangent_velocity) * output_impulse[tangent];
                }
            }
            for (std::size_t dof = 0; dof < dofs; ++dof) {
                solution.velocity[dof] = output_velocity[dof];
            }
            for (std::size_t tangent = 0; tangent < tangents; ++tangent) {
                solution.tangent_impulse[tangent] = output_impulse[tangent];
            }
            if (!solution.normal_impulse.empty()) {
                for (std::size_t contact = 0; contact < contacts; ++contact) {
                    solution.normal_impulse[contact] = output_normal_impulse[contact];
                }
            }
            if (!solution.friction_work.empty()) {
                for (std::size_t contact = 0; contact < contacts; ++contact) {
                    solution.friction_work[contact] = contact_work[contact];
                }
            }
            if (!solution.bilateral_impulse.empty()) {
                for (std::size_t row = 0; row < bilateral; ++row) {
                    double impulse = 0.0;
                    for (std::size_t variable = 0; variable < variables; ++variable) {
                        impulse += bilateral_response[row * variables + variable] * variable_impulse[variable];
                    }
                    solution.bilateral_impulse[row] = impulse;
                }
            }
            return result;
        } catch (const std::exception& error) {
            std::fprintf(stderr, "[termin-qopt] contact friction solve failed: %s\n", error.what());
        } catch (...) {
            std::fprintf(stderr,
                         "[termin-qopt] contact friction solve failed with an "
                         "unknown exception\n");
        }
        QpSolveResult result;
        result.status = QpStatus::NumericalFailure;
        result.diagnostic = QpDiagnostic::DecompositionFailure;
        return result;
    }

} // namespace termin::physics_qopt
