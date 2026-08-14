from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def cpp_string(value: str) -> str:
    return json.dumps(value)


def cpp_float(value: float) -> str:
    encoded = repr(float(value))
    return encoded if "." in encoded or "e" in encoded else f"{encoded}.0"


def cpp_vector(values: list[float]) -> str:
    return "{" + ", ".join(cpp_float(value) for value in values) + "}"


def flatten(matrix: list[list[float]]) -> list[float]:
    return [value for row in matrix for value in row]


def encode_equality_case(case: dict[str, Any]) -> str:
    problem = case["input"]
    expected = case["expected"]
    variables = len(problem["H"])
    constraints = len(problem["A_eq"])
    tolerances = expected.get("tolerances", {})
    return "\n".join(
        [
            "        {",
            f"            {cpp_string(case['id'])},",
            f"            {cpp_string(expected['status'])},",
            f"            {variables},",
            f"            {constraints},",
            f"            {cpp_vector(flatten(problem['H']))},",
            f"            {cpp_vector(problem['g'])},",
            f"            {cpp_vector(flatten(problem['A_eq']))},",
            f"            {cpp_vector(problem['b_eq'])},",
            f"            {cpp_vector(expected.get('primal', []))},",
            f"            {cpp_float(tolerances.get('primal_linf', 0.0))},",
            f"            {cpp_float(tolerances.get('stationarity_linf', 0.0))},",
            f"            {cpp_float(tolerances.get('equality_linf', 0.0))},",
            "        },",
        ]
    )


def encode_active_set_case(case: dict[str, Any]) -> str:
    problem = case["input"]
    expected = case["expected"]
    variables = len(problem["H"])
    equalities = len(problem["A_eq"])
    inequalities = len(problem["C"])
    tolerances = expected.get("tolerances", {})
    return "\n".join(
        [
            "        {",
            f"            {cpp_string(case['id'])},",
            f"            {cpp_string(expected['status'])},",
            f"            {variables},",
            f"            {equalities},",
            f"            {inequalities},",
            f"            {cpp_vector(flatten(problem['H']))},",
            f"            {cpp_vector(problem['g'])},",
            f"            {cpp_vector(flatten(problem['A_eq']))},",
            f"            {cpp_vector(problem['b_eq'])},",
            f"            {cpp_vector(flatten(problem['C']))},",
            f"            {cpp_vector(problem['d'])},",
            f"            {cpp_vector(expected.get('primal', []))},",
            f"            {cpp_float(tolerances.get('primal_linf', 0.0))},",
            f"            {cpp_float(tolerances.get('stationarity_linf', 0.0))},",
            f"            {cpp_float(tolerances.get('equality_linf', 0.0))},",
            f"            {cpp_float(tolerances.get('inequality_linf', 0.0))},",
            f"            {cpp_float(tolerances.get('dual_linf', 0.0))},",
            f"            {cpp_float(tolerances.get('complementarity_linf', 0.0))},",
            "        },",
        ]
    )

def encode_matrix(matrix: list[list[float]]) -> str:
    rows = len(matrix)
    columns = len(matrix[0]) if rows else 0
    return (
        "{"
        f"{rows}, {columns}, {cpp_vector(flatten(matrix))}"
        "}"
    )


def encode_nullspace_case(case: dict[str, Any]) -> str:
    expected = case["expected"]
    return (
        "{"
        f"{cpp_string(case['id'])}, "
        f"{encode_matrix(case['matrix'])}, "
        f"{cpp_float(case['rank_tolerance']['absolute'])}, "
        f"{expected['rank']}, {expected['nullity']}, "
        f"{cpp_float(expected['residual_linf'])}, "
        f"{cpp_float(expected['orthogonality_linf'])}"
        "},"
    )


def encode_hqp_level(level: dict[str, Any]) -> str:
    tasks = []
    for task in level["tasks"]:
        tasks.append(
            "{"
            f"{encode_matrix(task['J'])}, {cpp_vector(task['target'])}, "
            f"{encode_matrix(task.get('weight', []))}"
            "}"
        )
    equalities = [
        "{" + f"{encode_matrix(item['A'])}, {cpp_vector(item['b'])}" + "}"
        for item in level["equalities"]
    ]
    inequalities = [
        "{" + f"{encode_matrix(item['C'])}, {cpp_vector(item['d'])}" + "}"
        for item in level["inequalities"]
    ]
    return (
        "{"
        f"{level['priority']}, "
        "{" + ", ".join(tasks) + "}, "
        "{" + ", ".join(equalities) + "}, "
        "{" + ", ".join(inequalities) + "}"
        "}"
    )


def encode_hqp_case(case: dict[str, Any]) -> str:
    expected = case["expected"]
    return (
        "{"
        f"{cpp_string(case['id'])}, {case['n_variables']}, "
        "{" + ", ".join(encode_hqp_level(level) for level in case["levels"]) + "}, "
        f"{cpp_string(expected['status'])}, "
        f"{cpp_vector(expected.get('primal', []))}, "
        f"{cpp_float(expected.get('primal_linf', 0.0))}, "
        f"{cpp_vector(expected.get('level_task_residual_l2', []))}, "
        f"{cpp_float(expected.get('level_residual_tolerance', 0.0))}"
        "},"
    )


def generate(document: dict[str, Any]) -> str:
    equality_cases = [
        case
        for case in document["qp_cases"]
        if not case["input"]["C"]
    ]
    encoded_equality_cases = "\n".join(
        encode_equality_case(case) for case in equality_cases
    )
    encoded_active_set_cases = "\n".join(
        encode_active_set_case(case) for case in document["qp_cases"]
    )
    encoded_nullspace_cases = "\n".join(
        "        " + encode_nullspace_case(case)
        for case in document["nullspace_cases"]
    )
    encoded_hqp_cases = "\n".join(
        "        " + encode_hqp_case(case)
        for case in document["hqp_cases"]
    )
    return f"""#pragma once

#include <cstddef>
#include <string_view>
#include <vector>

struct OracleEqualityQpCase {{
    std::string_view id;
    std::string_view status;
    std::size_t variables;
    std::size_t constraints;
    std::vector<double> hessian;
    std::vector<double> gradient;
    std::vector<double> equalities;
    std::vector<double> equality_targets;
    std::vector<double> expected_primal;
    double primal_linf;
    double stationarity_linf;
    double equality_linf;
}};

inline std::vector<OracleEqualityQpCase> equality_qp_oracle_cases() {{
    return {{
{encoded_equality_cases}
    }};
}}

struct OracleActiveSetQpCase {{
    std::string_view id;
    std::string_view status;
    std::size_t variables;
    std::size_t equalities_count;
    std::size_t inequalities_count;
    std::vector<double> hessian;
    std::vector<double> gradient;
    std::vector<double> equalities;
    std::vector<double> equality_targets;
    std::vector<double> inequalities;
    std::vector<double> inequality_limits;
    std::vector<double> expected_primal;
    double primal_linf;
    double stationarity_linf;
    double equality_linf;
    double inequality_linf;
    double dual_linf;
    double complementarity_linf;
}};

inline std::vector<OracleActiveSetQpCase> active_set_qp_oracle_cases() {{
    return {{
{encoded_active_set_cases}
    }};
}}

struct OracleDenseMatrix {{
    std::size_t rows;
    std::size_t columns;
    std::vector<double> values;
}};

struct OracleNullspaceCase {{
    std::string_view id;
    OracleDenseMatrix matrix;
    double absolute_tolerance;
    std::size_t expected_rank;
    std::size_t expected_nullity;
    double residual_linf;
    double orthogonality_linf;
}};

inline std::vector<OracleNullspaceCase> nullspace_oracle_cases() {{
    return {{
{encoded_nullspace_cases}
    }};
}}

struct OracleHqpTask {{
    OracleDenseMatrix jacobian;
    std::vector<double> target;
    OracleDenseMatrix weight;
}};

struct OracleHqpConstraint {{
    OracleDenseMatrix matrix;
    std::vector<double> target;
}};

struct OracleHqpLevel {{
    int priority;
    std::vector<OracleHqpTask> tasks;
    std::vector<OracleHqpConstraint> equalities;
    std::vector<OracleHqpConstraint> inequalities;
}};

struct OracleHqpCase {{
    std::string_view id;
    std::size_t variables;
    std::vector<OracleHqpLevel> levels;
    std::string_view status;
    std::vector<double> expected_primal;
    double primal_linf;
    std::vector<double> expected_level_residuals;
    double level_residual_tolerance;
}};

inline std::vector<OracleHqpCase> hqp_oracle_cases() {{
    return {{
{encoded_hqp_cases}
    }};
}}
"""


def main() -> None:
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    with input_path.open(encoding="utf-8") as stream:
        document = json.load(stream)
    output_path.write_text(generate(document), encoding="utf-8")


if __name__ == "__main__":
    main()
