from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from termin.linalg.solve import solve_qp_active_set, solve_qp_equalities
from termin.linalg.subspaces import nullspace_basis_qr, nullspace_basis_svd
from termin.robot.hqsolver import (
    EqualityConstraint,
    HQPSolver,
    InequalityConstraint,
    Level,
    QuadraticTask,
)


ORACLE_PATH = Path(__file__).with_name("oracle") / "solver_oracle.json"
EXPECTED_QP_STATUSES = {"optimal", "infeasible", "unbounded", "invalid_input"}


def load_solver_oracle() -> dict[str, Any]:
    with ORACLE_PATH.open(encoding="utf-8") as stream:
        document = json.load(stream)
    validate_oracle_structure(document)
    return document


def validate_oracle_structure(document: dict[str, Any]) -> None:
    if document["schema_version"] != 1:
        raise ValueError(f"Unsupported solver oracle schema: {document['schema_version']}")

    case_ids = [
        case["id"]
        for section in ("qp_cases", "nullspace_cases", "hqp_cases")
        for case in document[section]
    ]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Solver oracle case IDs must be globally unique")

    for case in document["qp_cases"]:
        status = case["expected"]["status"]
        if status not in EXPECTED_QP_STATUSES:
            raise ValueError(f"{case['id']}: unsupported expected status {status}")
        errors = qp_dimension_errors(case["input"])
        if status == "invalid_input":
            if case["expected"]["error"] not in errors:
                raise ValueError(f"{case['id']}: expected structural error was not reproduced")
        elif errors:
            raise ValueError(f"{case['id']}: structurally invalid QP: {errors}")


def _matrix(values: list[list[float]], columns: int) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.size == 0:
        return np.zeros((0, columns), dtype=float)
    return result


def qp_arrays(problem: dict[str, Any]) -> tuple[np.ndarray, ...]:
    hessian = np.asarray(problem["H"], dtype=float)
    variables = hessian.shape[0] if hessian.ndim == 2 else 0
    return (
        hessian,
        np.asarray(problem["g"], dtype=float),
        _matrix(problem["A_eq"], variables),
        np.asarray(problem["b_eq"], dtype=float),
        _matrix(problem["C"], variables),
        np.asarray(problem["d"], dtype=float),
    )


def qp_dimension_errors(problem: dict[str, Any]) -> set[str]:
    hessian, gradient, equalities, equality_bounds, inequalities, inequality_bounds = qp_arrays(problem)
    errors: set[str] = set()

    if hessian.ndim != 2 or hessian.shape[0] != hessian.shape[1]:
        errors.add("hessian_not_square")
        return errors

    variables = hessian.shape[0]
    if gradient.shape != (variables,):
        errors.add("gradient_dimension_mismatch")
    if equalities.shape[1:] != (variables,) or equality_bounds.shape != (equalities.shape[0],):
        errors.add("equality_dimension_mismatch")
    if inequalities.shape[1:] != (variables,) or inequality_bounds.shape != (inequalities.shape[0],):
        errors.add("inequality_dimension_mismatch")
    return errors


def run_python_qp(problem: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    hessian, gradient, equalities, equality_bounds, inequalities, inequality_bounds = qp_arrays(problem)
    if inequalities.shape[0] == 0:
        primal, equality_dual = solve_qp_equalities(
            hessian,
            gradient,
            equalities,
            equality_bounds,
        )
        return primal, equality_dual, np.zeros(0)

    primal, equality_dual, active_dual, active, _iterations = solve_qp_active_set(
        hessian,
        gradient,
        equalities,
        equality_bounds,
        inequalities,
        inequality_bounds,
    )
    inequality_dual = np.zeros(inequalities.shape[0])
    inequality_dual[active] = active_dual
    return primal, equality_dual, inequality_dual


def qp_optimal_residuals(
    problem: dict[str, Any],
    primal: np.ndarray,
    equality_dual: np.ndarray,
    inequality_dual: np.ndarray,
) -> dict[str, float]:
    hessian, gradient, equalities, equality_bounds, inequalities, inequality_bounds = qp_arrays(problem)
    stationarity = hessian @ primal + gradient
    if equalities.shape[0]:
        stationarity = stationarity + equalities.T @ equality_dual
    if inequalities.shape[0]:
        stationarity = stationarity + inequalities.T @ inequality_dual

    equality_residual = equalities @ primal - equality_bounds
    inequality_slack = inequalities @ primal - inequality_bounds
    complementarity = inequality_dual * inequality_slack
    return {
        "stationarity_linf": _linf(stationarity),
        "equality_linf": _linf(equality_residual),
        "inequality_linf": max(0.0, _max(inequality_slack)),
        "dual_linf": max(0.0, _max(-inequality_dual)),
        "complementarity_linf": _linf(complementarity),
    }


def validate_nonoptimal_certificate(case: dict[str, Any]) -> None:
    problem = case["input"]
    expected = case["expected"]
    status = expected["status"]

    if status == "invalid_input":
        assert expected["error"] in qp_dimension_errors(problem)
        return

    hessian, gradient, equalities, equality_bounds, inequalities, inequality_bounds = qp_arrays(problem)
    certificate = expected["certificate"]
    tolerance = certificate["residual_linf"]

    if certificate["kind"] == "equality_inconsistency":
        dual = np.asarray(certificate["dual"], dtype=float)
        assert _linf(equalities.T @ dual) <= tolerance
        assert abs(float(equality_bounds @ dual)) >= certificate["separation_min"]
    elif certificate["kind"] == "inequality_farkas":
        dual = np.asarray(certificate["dual"], dtype=float)
        assert _max(-dual) <= tolerance
        assert _linf(inequalities.T @ dual) <= tolerance
        assert float(inequality_bounds @ dual) <= -certificate["separation_min"]
    elif certificate["kind"] == "recession_direction":
        direction = np.asarray(certificate["direction"], dtype=float)
        assert _linf(hessian @ direction) <= tolerance
        assert _linf(equalities @ direction) <= tolerance
        assert _max(inequalities @ direction) <= tolerance
        assert float(gradient @ direction) <= -certificate["descent_min"]
    else:
        raise AssertionError(f"{case['id']}: unknown certificate kind {certificate['kind']}")


def nullspace_bases(case: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(case["matrix"], dtype=float)
    absolute_tolerance = case["rank_tolerance"]["absolute"]
    return (
        nullspace_basis_svd(matrix, atol=absolute_tolerance),
        nullspace_basis_qr(matrix, atol=absolute_tolerance),
    )


def nullspace_residuals(matrix: np.ndarray, basis: np.ndarray) -> dict[str, float]:
    identity = np.eye(basis.shape[1])
    return {
        "residual_linf": _linf(matrix @ basis),
        "orthogonality_linf": _linf(basis.T @ basis - identity),
    }


def run_python_hqp(case: dict[str, Any]) -> tuple[np.ndarray, list[float]]:
    solver = HQPSolver(n_vars=case["n_variables"])
    levels: list[Level] = []

    for encoded_level in case["levels"]:
        level = Level(priority=encoded_level["priority"])
        for task in encoded_level["tasks"]:
            weight = task.get("weight")
            level.add_task(
                QuadraticTask(
                    np.asarray(task["J"], dtype=float),
                    np.asarray(task["target"], dtype=float),
                    None if weight is None else np.asarray(weight, dtype=float),
                )
            )
        for equality in encoded_level["equalities"]:
            level.add_equality(
                EqualityConstraint(
                    np.asarray(equality["A"], dtype=float),
                    np.asarray(equality["b"], dtype=float),
                )
            )
        for inequality in encoded_level["inequalities"]:
            level.add_inequality(
                InequalityConstraint(
                    np.asarray(inequality["C"], dtype=float),
                    np.asarray(inequality["d"], dtype=float),
                )
            )
        solver.add_level(level)
        levels.append(level)

    primal = solver.solve()
    residuals = []
    for level in levels:
        blocks = [task.J @ primal - task.v for task in level.tasks]
        residuals.append(float(np.linalg.norm(np.concatenate(blocks))) if blocks else 0.0)
        for equality in level.equalities:
            assert _linf(equality.A @ primal - equality.b) <= 1e-8
        for inequality in level.inequalities:
            assert _max(inequality.C @ primal - inequality.d) <= 1e-8
    return primal, residuals


def _linf(values: np.ndarray) -> float:
    return float(np.max(np.abs(values))) if values.size else 0.0


def _max(values: np.ndarray) -> float:
    return float(np.max(values)) if values.size else 0.0
