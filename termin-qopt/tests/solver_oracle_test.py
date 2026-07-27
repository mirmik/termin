import numpy as np
import pytest

from solver_oracle import (
    load_solver_oracle,
    nullspace_bases,
    nullspace_residuals,
    qp_optimal_residuals,
    run_python_hqp,
    run_python_qp,
    validate_nonoptimal_certificate,
)


ORACLE = load_solver_oracle()
OPTIMAL_QP_CASES = [
    case for case in ORACLE["qp_cases"] if case["expected"]["status"] == "optimal"
]
NONOPTIMAL_QP_CASES = [
    case for case in ORACLE["qp_cases"] if case["expected"]["status"] != "optimal"
]


@pytest.mark.parametrize("case", OPTIMAL_QP_CASES, ids=lambda case: case["id"])
def test_python_qp_satisfies_oracle(case):
    primal, equality_dual, inequality_dual = run_python_qp(case["input"])
    expected = case["expected"]

    assert np.max(np.abs(primal - expected["primal"])) <= expected["tolerances"]["primal_linf"]
    residuals = qp_optimal_residuals(case["input"], primal, equality_dual, inequality_dual)
    for residual, value in residuals.items():
        assert value <= expected["tolerances"][residual], f"{residual}={value}"


@pytest.mark.parametrize("case", NONOPTIMAL_QP_CASES, ids=lambda case: case["id"])
def test_nonoptimal_qp_status_has_independent_certificate(case):
    validate_nonoptimal_certificate(case)


@pytest.mark.parametrize("case", ORACLE["nullspace_cases"], ids=lambda case: case["id"])
def test_python_nullspace_bases_satisfy_oracle(case):
    matrix = np.asarray(case["matrix"], dtype=float)
    expected = case["expected"]
    svd_basis, qr_basis = nullspace_bases(case)

    for basis in (svd_basis, qr_basis):
        assert basis.shape == (matrix.shape[1], expected["nullity"])
        residuals = nullspace_residuals(matrix, basis)
        assert residuals["residual_linf"] <= expected["residual_linf"]
        assert residuals["orthogonality_linf"] <= expected["orthogonality_linf"]

    assert np.max(np.abs(svd_basis @ svd_basis.T - qr_basis @ qr_basis.T)) <= 1e-8
    assert matrix.shape[1] - expected["nullity"] == expected["rank"]


@pytest.mark.parametrize("case", ORACLE["hqp_cases"], ids=lambda case: case["id"])
def test_python_hqp_satisfies_oracle(case):
    primal, level_residuals = run_python_hqp(case)
    expected = case["expected"]

    assert np.max(np.abs(primal - expected["primal"])) <= expected["primal_linf"]
    assert np.max(
        np.abs(np.asarray(level_residuals) - expected["level_task_residual_l2"])
    ) <= expected["level_residual_tolerance"]
