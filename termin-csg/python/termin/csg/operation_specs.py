"""Declarative operation metadata for procedural CSG documents."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

OPERATION_KIND_EXTRUDE = "extrude"
PRIMITIVE_OPERATION_KIND = "primitive"
BOOLEAN_OPERATION_KINDS = {"union", "subtract", "intersect"}
PRIMITIVE_KINDS = {"box", "sphere", "cylinder", "cone"}


@dataclass(frozen=True)
class OperationParamSpec:
    key: str
    label: str
    kind: str
    default: Any
    min_value: float | None = None
    max_value: float | None = None


@dataclass(frozen=True)
class OperationSpec:
    kind: str
    label: str
    default_params: dict
    param_schema: tuple[OperationParamSpec, ...]
    input_policy: str
    context_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class PrimitiveSpec:
    kind: str
    label: str
    default_params: dict
    param_schema: tuple[OperationParamSpec, ...]


def operation_transform_defaults() -> dict:
    return {
        "center": [0.0, 0.0, 0.0],
        "rotation": [0.0, 0.0, 0.0],
    }


def extrude_default_params(vector: tuple[float, float, float]) -> dict:
    return {
        "vector": [float(vector[0]), float(vector[1]), float(vector[2])],
        "mode": "new_body",
        **operation_transform_defaults(),
    }


def primitive_default_params(kind: str) -> dict:
    spec = primitive_spec(kind)
    if spec is None:
        return {}
    params = deepcopy(spec.default_params)
    params["primitive_kind"] = spec.kind
    params.update(operation_transform_defaults())
    return params


def primitive_spec(kind: str) -> PrimitiveSpec | None:
    return PRIMITIVE_SPECS_BY_KIND.get(str(kind))


def operation_spec(kind: str) -> OperationSpec | None:
    return OPERATION_SPECS_BY_KIND.get(str(kind))


def boolean_operation_label(kind: str) -> str:
    spec = operation_spec(kind)
    if spec is None:
        return str(kind).capitalize()
    return spec.label


def primitive_label(kind: str) -> str:
    spec = primitive_spec(kind)
    if spec is None:
        return str(kind).capitalize()
    return spec.label


def boolean_input_role(kind: str, index: int) -> str:
    if kind == "subtract":
        if index == 0:
            return "[Base]"
        return "[Cut]"
    return "[Input]"


def primitive_param_summary(params: dict) -> str:
    kind = str(params.get("primitive_kind", ""))
    if kind == "box":
        return f" size={_format_vec3(_param_vec3(params, 'size', (1.0, 1.0, 1.0)))}"
    if kind == "sphere":
        return f" radius={_param_float(params, 'radius', 0.5):.2f}"
    if kind == "cylinder":
        return (
            f" radius={_param_float(params, 'radius', 0.5):.2f}"
            f" height={_param_float(params, 'height', 1.0):.2f}"
        )
    if kind == "cone":
        return (
            f" r0={_param_float(params, 'radius_low', 0.5):.2f}"
            f" r1={_param_float(params, 'radius_high', 0.0):.2f}"
            f" height={_param_float(params, 'height', 1.0):.2f}"
        )
    return ""


def ordered_boolean_operation_specs() -> tuple[OperationSpec, ...]:
    return (
        OPERATION_SPECS_BY_KIND["union"],
        OPERATION_SPECS_BY_KIND["subtract"],
        OPERATION_SPECS_BY_KIND["intersect"],
    )


def ordered_primitive_specs() -> tuple[PrimitiveSpec, ...]:
    return (
        PRIMITIVE_SPECS_BY_KIND["box"],
        PRIMITIVE_SPECS_BY_KIND["sphere"],
        PRIMITIVE_SPECS_BY_KIND["cylinder"],
        PRIMITIVE_SPECS_BY_KIND["cone"],
    )


def _format_vec3(value: tuple[float, float, float]) -> str:
    return f"({value[0]:.2f},{value[1]:.2f},{value[2]:.2f})"


def _param_float(params: dict, key: str, default: float) -> float:
    try:
        return float(params.get(key, default))
    except Exception:
        return float(default)


def _param_vec3(params: dict, key: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    value = params.get(key, default)
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return default


_TRANSFORM_PARAM_SCHEMA = (
    OperationParamSpec("center", "Center", "vec3", [0.0, 0.0, 0.0]),
    OperationParamSpec("rotation", "Rotation", "vec3", [0.0, 0.0, 0.0]),
)

PRIMITIVE_SPECS_BY_KIND = {
    "box": PrimitiveSpec(
        kind="box",
        label="Box",
        default_params={
            "size": [1.0, 1.0, 1.0],
            "centered": True,
        },
        param_schema=(
            OperationParamSpec("size", "Size", "vec3", [1.0, 1.0, 1.0], min_value=0.001),
            OperationParamSpec("centered", "Centered", "bool", True),
            *_TRANSFORM_PARAM_SCHEMA,
        ),
    ),
    "sphere": PrimitiveSpec(
        kind="sphere",
        label="Sphere",
        default_params={
            "radius": 0.5,
            "circular_segments": 32,
        },
        param_schema=(
            OperationParamSpec("radius", "Radius", "float", 0.5, min_value=0.001),
            OperationParamSpec("circular_segments", "Segments", "int", 32, min_value=3.0, max_value=256.0),
            *_TRANSFORM_PARAM_SCHEMA,
        ),
    ),
    "cylinder": PrimitiveSpec(
        kind="cylinder",
        label="Cylinder",
        default_params={
            "radius": 0.5,
            "height": 1.0,
            "circular_segments": 32,
            "centered": True,
        },
        param_schema=(
            OperationParamSpec("radius", "Radius", "float", 0.5, min_value=0.001),
            OperationParamSpec("height", "Height", "float", 1.0, min_value=0.001),
            OperationParamSpec("circular_segments", "Segments", "int", 32, min_value=3.0, max_value=256.0),
            OperationParamSpec("centered", "Centered", "bool", True),
            *_TRANSFORM_PARAM_SCHEMA,
        ),
    ),
    "cone": PrimitiveSpec(
        kind="cone",
        label="Cone",
        default_params={
            "radius_low": 0.5,
            "radius_high": 0.0,
            "height": 1.0,
            "circular_segments": 32,
            "centered": True,
        },
        param_schema=(
            OperationParamSpec("radius_low", "Radius low", "float", 0.5, min_value=0.001),
            OperationParamSpec("radius_high", "Radius high", "float", 0.0, min_value=0.0),
            OperationParamSpec("height", "Height", "float", 1.0, min_value=0.001),
            OperationParamSpec("circular_segments", "Segments", "int", 32, min_value=3.0, max_value=256.0),
            OperationParamSpec("centered", "Centered", "bool", True),
            *_TRANSFORM_PARAM_SCHEMA,
        ),
    ),
}

OPERATION_SPECS_BY_KIND = {
    OPERATION_KIND_EXTRUDE: OperationSpec(
        kind=OPERATION_KIND_EXTRUDE,
        label="Extrude",
        default_params={
            "vector": [0.0, 0.0, 1.0],
            "mode": "new_body",
            **operation_transform_defaults(),
        },
        param_schema=(
            OperationParamSpec("vector", "Vector", "vec3", [0.0, 0.0, 1.0]),
            *_TRANSFORM_PARAM_SCHEMA,
        ),
        input_policy="sketch_outer_contours",
        context_actions=("add_outer_contour",),
    ),
    PRIMITIVE_OPERATION_KIND: OperationSpec(
        kind=PRIMITIVE_OPERATION_KIND,
        label="Primitive",
        default_params={},
        param_schema=(),
        input_policy="none",
    ),
    "union": OperationSpec(
        kind="union",
        label="Union",
        default_params=operation_transform_defaults(),
        param_schema=_TRANSFORM_PARAM_SCHEMA,
        input_policy="two_or_more_operations",
    ),
    "subtract": OperationSpec(
        kind="subtract",
        label="Subtract",
        default_params=operation_transform_defaults(),
        param_schema=_TRANSFORM_PARAM_SCHEMA,
        input_policy="base_then_cutters",
    ),
    "intersect": OperationSpec(
        kind="intersect",
        label="Intersect",
        default_params=operation_transform_defaults(),
        param_schema=_TRANSFORM_PARAM_SCHEMA,
        input_policy="two_or_more_operations",
    ),
}


__all__ = [
    "BOOLEAN_OPERATION_KINDS",
    "OPERATION_KIND_EXTRUDE",
    "OPERATION_SPECS_BY_KIND",
    "OperationParamSpec",
    "OperationSpec",
    "PRIMITIVE_KINDS",
    "PRIMITIVE_OPERATION_KIND",
    "PRIMITIVE_SPECS_BY_KIND",
    "PrimitiveSpec",
    "boolean_input_role",
    "boolean_operation_label",
    "extrude_default_params",
    "operation_spec",
    "operation_transform_defaults",
    "ordered_boolean_operation_specs",
    "ordered_primitive_specs",
    "primitive_default_params",
    "primitive_label",
    "primitive_param_summary",
    "primitive_spec",
]
