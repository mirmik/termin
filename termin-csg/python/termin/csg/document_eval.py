"""Evaluate procedural CSG documents into renderable solids."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from tcbase import log
from tmesh import Mesh3

from termin.csg._csg_native import (
    Solid,
    _extrude_pairs,
    from_mesh3,
    intersect,
    make_box,
    make_cone,
    make_cylinder,
    make_sphere,
    subtract,
    to_mesh3,
    unite,
)
from termin.csg.procedural_document import (
    BOOLEAN_OPERATION_KINDS,
    CONTOUR_ROLE_HOLE,
    CONTOUR_ROLE_OUTER,
    OPERATION_KIND_WALL,
    PRIMITIVE_OPERATION_KIND,
    ProceduralMeshDocument,
    SketchItemDocument,
)

Vec2Data = tuple[float, float]
Vec3Data = tuple[float, float, float]
PointTransform = Callable[[Vec3Data], Vec3Data]


@dataclass
class EvaluatedSolid:
    operation_id: str
    contour_id: str
    solid: Solid
    point_transform: PointTransform


def evaluate_document(document: ProceduralMeshDocument) -> list[EvaluatedSolid]:
    """Build enabled document operations into CSG solids.

    Solids are evaluated in their operation-local coordinates. The attached
    point transform maps those coordinates back into document-local 3D space,
    preserving sketch plane placement. Callers may apply additional scene or
    entity transforms after this point.
    """

    operations_by_id = {operation.id: operation for operation in document.operations}
    operation_results: dict[str, list[EvaluatedSolid]] = {}
    visiting_operation_ids: set[str] = set()

    def evaluate_operation(operation) -> list[EvaluatedSolid] | None:
        cached_result = operation_results.get(operation.id)
        if cached_result is not None:
            return cached_result
        if not operation.enabled:
            log.error(
                "[ProceduralMeshDocument] cannot evaluate operation: "
                f"operation is disabled operation='{operation.id}'"
            )
            return None
        if operation.id in visiting_operation_ids:
            log.error(
                "[ProceduralMeshDocument] cannot evaluate operation: "
                f"cycle detected operation='{operation.id}'"
            )
            return None

        visiting_operation_ids.add(operation.id)
        if operation.kind == "extrude":
            result = _evaluate_extrude(document, operation)
        elif operation.kind == OPERATION_KIND_WALL:
            result = _evaluate_wall(document, operation)
        elif operation.kind == PRIMITIVE_OPERATION_KIND:
            result = _evaluate_primitive(operation)
        elif operation.kind in BOOLEAN_OPERATION_KINDS:
            result = _evaluate_boolean(
                operation,
                lambda input_id: evaluate_input_operation(operation.id, input_id),
            )
        else:
            log.error(
                "[ProceduralMeshDocument] cannot evaluate operation: "
                f"unknown kind '{operation.kind}' operation='{operation.id}'"
            )
            result = []
        visiting_operation_ids.remove(operation.id)
        if result is not None:
            operation_results[operation.id] = result
        return result

    def evaluate_input_operation(
        requester_operation_id: str,
        input_operation_id: str,
    ) -> list[EvaluatedSolid] | None:
        input_operation = operations_by_id.get(input_operation_id)
        if input_operation is None:
            log.error(
                "[ProceduralMeshDocument] cannot evaluate boolean operation: "
                f"input operation not found operation='{requester_operation_id}' input='{input_operation_id}'"
            )
            return None
        return evaluate_operation(input_operation)

    consumed_operation_ids = document.used_input_operation_ids()
    results: list[EvaluatedSolid] = []
    for operation in document.operations:
        if not operation.enabled or operation.id in consumed_operation_ids:
            continue
        evaluated_items = evaluate_operation(operation)
        if evaluated_items is not None:
            results.extend(evaluated_items)
    return results


def _evaluate_primitive(operation) -> list[EvaluatedSolid]:
    primitive_kind = str(operation.params.get("primitive_kind", ""))
    try:
        if primitive_kind == "box":
            size = _param_vec3(operation.params, "size", (1.0, 1.0, 1.0))
            solid = make_box(size[0], size[1], size[2], _param_bool(operation.params, "centered", True))
        elif primitive_kind == "sphere":
            solid = make_sphere(
                _param_float(operation.params, "radius", 0.5),
                _param_int(operation.params, "circular_segments", 32),
            )
        elif primitive_kind == "cylinder":
            solid = make_cylinder(
                _param_float(operation.params, "radius", 0.5),
                _param_float(operation.params, "height", 1.0),
                _param_int(operation.params, "circular_segments", 32),
                _param_bool(operation.params, "centered", True),
            )
        elif primitive_kind == "cone":
            solid = make_cone(
                _param_float(operation.params, "radius_low", 0.5),
                _param_float(operation.params, "radius_high", 0.0),
                _param_float(operation.params, "height", 1.0),
                _param_int(operation.params, "circular_segments", 32),
                _param_bool(operation.params, "centered", True),
            )
        else:
            log.error(
                "[ProceduralMeshDocument] cannot evaluate primitive operation: "
                f"unknown primitive kind '{primitive_kind}' operation='{operation.id}'"
            )
            return []
        solid = _apply_operation_transform_to_solid(solid, operation)
    except Exception as e:
        log.error(
            "[ProceduralMeshDocument] failed to evaluate primitive operation "
            f"operation='{operation.id}' kind='{primitive_kind}': {e}"
        )
        return []

    if solid.status != "No Error":
        log.error(
            "[ProceduralMeshDocument] primitive operation returned invalid solid "
            f"operation='{operation.id}' kind='{primitive_kind}' status='{solid.status}'"
        )
    return [
        EvaluatedSolid(
            operation_id=operation.id,
            contour_id="",
            solid=solid,
            point_transform=_identity_point_transform,
        )
    ]


def _evaluate_extrude(document: ProceduralMeshDocument, operation) -> list[EvaluatedSolid]:
    source_sketch_id = str(operation.params.get("source_sketch_id", ""))
    sketch = document.find_sketch(source_sketch_id)
    if sketch is None:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate extrude operation: "
            f"sketch not found '{source_sketch_id}'"
        )
        return []

    extrusion_vector = extrude_vector_for_operation(sketch, operation)
    if _norm(extrusion_vector) < 1.0e-9:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate extrude operation: "
            f"zero extrusion vector operation='{operation.id}'"
        )
        return []

    extrusion_length = _norm(extrusion_vector)
    point_transform = _compose_operation_point_transform(
        sketch_extrude_point_transform(sketch, extrusion_vector, extrusion_length),
        operation,
    )
    results: list[EvaluatedSolid] = []
    for contour in sketch.contours:
        if contour.role == CONTOUR_ROLE_HOLE:
            continue
        if contour.role != CONTOUR_ROLE_OUTER:
            log.error(
                "[ProceduralMeshDocument] cannot evaluate extrude operation: "
                f"invalid contour role '{contour.role}' contour='{contour.id}'"
            )
            continue
        if contour.id not in operation.inputs:
            continue
        holes = sketch.hole_contours_for_outer(contour.id)
        try:
            solid = _extrude_pairs(contour.points, extrusion_length, [hole.points for hole in holes])
        except Exception as e:
            log.error(
                "[ProceduralMeshDocument] failed to evaluate extrude "
                f"operation='{operation.id}' contour='{contour.id}': {e}"
            )
            continue
        results.append(
            EvaluatedSolid(
                operation_id=operation.id,
                contour_id=contour.id,
                solid=solid,
                point_transform=point_transform,
            )
        )
    return results


def _evaluate_wall(document: ProceduralMeshDocument, operation) -> list[EvaluatedSolid]:
    source_path_id = str(operation.params.get("source_path_id", ""))
    path_ref = document.find_path_ref(source_path_id)
    if path_ref is None:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate wall operation: "
            f"path not found '{source_path_id}' operation='{operation.id}'"
        )
        return []
    sketch, path = path_ref

    height = _param_float(operation.params, "height", 3.0)
    thickness = _param_float(operation.params, "thickness", 0.2)
    alignment = str(operation.params.get("alignment", "center"))
    if height <= 0.0 or thickness <= 0.0:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate wall operation: "
            f"height and thickness must be positive operation='{operation.id}'"
        )
        return []
    if alignment not in {"center", "left", "right"}:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate wall operation: "
            f"invalid alignment '{alignment}' operation='{operation.id}'"
        )
        return []

    profile = _wall_profile_from_path(path.points, thickness, alignment, operation.id)
    if not profile:
        return []

    extrusion_vector = (
        sketch.plane.normal[0] * height,
        sketch.plane.normal[1] * height,
        sketch.plane.normal[2] * height,
    )
    point_transform = _compose_operation_point_transform(
        sketch_extrude_point_transform(sketch, extrusion_vector, height),
        operation,
    )
    try:
        solid = _extrude_pairs(profile, height, [])
    except Exception as e:
        log.error(
            "[ProceduralMeshDocument] failed to evaluate wall "
            f"operation='{operation.id}' path='{path.id}': {e}"
        )
        return []

    if solid.status != "No Error":
        log.error(
            "[ProceduralMeshDocument] wall operation returned invalid solid "
            f"operation='{operation.id}' path='{path.id}' status='{solid.status}'"
        )
    return [
        EvaluatedSolid(
            operation_id=operation.id,
            contour_id=path.id,
            solid=solid,
            point_transform=point_transform,
        )
    ]


def _evaluate_boolean(
    operation,
    evaluate_input_operation: Callable[[str], list[EvaluatedSolid] | None],
) -> list[EvaluatedSolid]:
    operands: list[Solid] = []
    for input_id in operation.inputs:
        evaluated_items = evaluate_input_operation(input_id)
        if evaluated_items is None:
            return []
        operand = _combine_evaluated_solids(evaluated_items, operation.id, input_id)
        if operand is None:
            return []
        operands.append(operand)

    if len(operands) < 2:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate boolean operation: "
            f"need at least 2 operands operation='{operation.id}'"
        )
        return []

    try:
        result = _fold_boolean(operation.kind, operands)
    except Exception as e:
        log.error(
            "[ProceduralMeshDocument] failed to evaluate boolean "
            f"operation='{operation.id}' kind='{operation.kind}': {e}"
        )
        return []

    result = _apply_operation_transform_to_solid(result, operation)
    if result.status != "No Error":
        log.error(
            "[ProceduralMeshDocument] boolean operation returned invalid solid "
            f"operation='{operation.id}' kind='{operation.kind}' status='{result.status}'"
        )
    return [
        EvaluatedSolid(
            operation_id=operation.id,
            contour_id="",
            solid=result,
            point_transform=_identity_point_transform,
        )
    ]


def _combine_evaluated_solids(
    evaluated_items: list[EvaluatedSolid],
    operation_id: str,
    input_id: str,
) -> Solid | None:
    if not evaluated_items:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate boolean operation: "
            f"input operation produced no solids operation='{operation_id}' input='{input_id}'"
        )
        return None

    solids: list[Solid] = []
    for evaluated in evaluated_items:
        solid = _evaluated_solid_in_document_space(evaluated)
        if solid is None:
            return None
        solids.append(solid)

    result = solids[0]
    for solid in solids[1:]:
        result = unite(result, solid)
    return result


def _evaluated_solid_in_document_space(evaluated: EvaluatedSolid) -> Solid | None:
    try:
        mesh = to_mesh3(evaluated.solid, "csg-document-space", "", False)
        vertices = np.asarray(mesh.vertices, dtype=np.float32).reshape(-1, 3)
        transformed = np.array(
            [evaluated.point_transform((float(v[0]), float(v[1]), float(v[2]))) for v in vertices],
            dtype=np.float32,
        )
        triangles = np.asarray(mesh.triangles, dtype=np.uint32).reshape(-1, 3)
        if _mesh_signed_volume(transformed, triangles) < 0.0:
            triangles = np.ascontiguousarray(triangles[:, [0, 2, 1]], dtype=np.uint32)
        return from_mesh3(
            Mesh3(
                name="csg-document-space",
                vertices=np.ascontiguousarray(transformed, dtype=np.float32),
                triangles=np.ascontiguousarray(triangles, dtype=np.uint32),
            )
        )
    except Exception as e:
        log.error(
            "[ProceduralMeshDocument] failed to transform evaluated solid into document space "
            f"operation='{evaluated.operation_id}' contour='{evaluated.contour_id}': {e}"
        )
        return None


def _fold_boolean(kind: str, operands: list[Solid]) -> Solid:
    result = operands[0]
    if kind == "union":
        for operand in operands[1:]:
            result = unite(result, operand)
        return result
    if kind == "subtract":
        for operand in operands[1:]:
            result = subtract(result, operand)
        return result
    if kind == "intersect":
        for operand in operands[1:]:
            result = intersect(result, operand)
        return result
    raise ValueError(f"unsupported boolean operation kind '{kind}'")


def _identity_point_transform(point: Vec3Data) -> Vec3Data:
    return point


def _apply_operation_transform_to_solid(solid: Solid, operation) -> Solid:
    center, rotation = _operation_transform(operation)
    return solid.rotated(rotation[0], rotation[1], rotation[2]).translated(center[0], center[1], center[2])


def _compose_operation_point_transform(base_transform: PointTransform, operation) -> PointTransform:
    center, rotation = _operation_transform(operation)
    if _is_zero_vec3(center) and _is_zero_vec3(rotation):
        return base_transform

    def transform(point: Vec3Data) -> Vec3Data:
        return _v_add(_rotate_point_xyz(base_transform(point), rotation), center)

    return transform


def _operation_transform(operation) -> tuple[Vec3Data, Vec3Data]:
    center = _param_vec3(operation.params, "center", (0.0, 0.0, 0.0))
    rotation = _param_vec3(operation.params, "rotation", (0.0, 0.0, 0.0))
    return center, rotation


def _rotate_point_xyz(point: Vec3Data, rotation_degrees: Vec3Data) -> Vec3Data:
    rx, ry, rz = np.radians(np.asarray(rotation_degrees, dtype=np.float64))
    x, y, z = point
    cx = float(np.cos(rx))
    sx = float(np.sin(rx))
    y, z = (y * cx - z * sx, y * sx + z * cx)
    cy = float(np.cos(ry))
    sy = float(np.sin(ry))
    x, z = (x * cy + z * sy, -x * sy + z * cy)
    cz = float(np.cos(rz))
    sz = float(np.sin(rz))
    x, y = (x * cz - y * sz, x * sz + y * cz)
    return (float(x), float(y), float(z))


def _is_zero_vec3(value: Vec3Data) -> bool:
    return abs(value[0]) < 1.0e-12 and abs(value[1]) < 1.0e-12 and abs(value[2]) < 1.0e-12


def _v_add(a: Vec3Data, b: Vec3Data) -> Vec3Data:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _wall_profile_from_path(
    points: list[Vec2Data],
    thickness: float,
    alignment: str,
    operation_id: str,
) -> list[Vec2Data]:
    clean_points = _clean_path_points(points)
    if len(clean_points) < 2:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate wall operation: "
            f"path needs at least 2 unique points operation='{operation_id}'"
        )
        return []
    if alignment == "center":
        left_distance = thickness * 0.5
        right_distance = -thickness * 0.5
    elif alignment == "left":
        left_distance = thickness
        right_distance = 0.0
    else:
        left_distance = 0.0
        right_distance = -thickness

    left = _offset_open_polyline(clean_points, left_distance)
    right = _offset_open_polyline(clean_points, right_distance)
    profile = left + list(reversed(right))
    if abs(_signed_area_2d(profile)) < 1.0e-9:
        log.error(
            "[ProceduralMeshDocument] cannot evaluate wall operation: "
            f"wall profile has zero area operation='{operation_id}'"
        )
        return []
    if _signed_area_2d(profile) < 0.0:
        profile.reverse()
    return profile


def _clean_path_points(points: list[Vec2Data]) -> list[Vec2Data]:
    result: list[Vec2Data] = []
    for point in points:
        item = (float(point[0]), float(point[1]))
        if result and _distance_2d(result[-1], item) < 1.0e-9:
            continue
        result.append(item)
    return result


def _offset_open_polyline(points: list[Vec2Data], distance: float) -> list[Vec2Data]:
    if abs(distance) < 1.0e-12:
        return points[:]
    result: list[Vec2Data] = []
    segment_dirs = [_normalized_2d(_sub_2d(points[index + 1], points[index])) for index in range(len(points) - 1)]
    segment_normals = [(-direction[1], direction[0]) for direction in segment_dirs]
    for index, point in enumerate(points):
        if index == 0:
            result.append(_add_2d(point, _mul_2d(segment_normals[0], distance)))
            continue
        if index == len(points) - 1:
            result.append(_add_2d(point, _mul_2d(segment_normals[-1], distance)))
            continue
        prev_point = _add_2d(point, _mul_2d(segment_normals[index - 1], distance))
        next_point = _add_2d(point, _mul_2d(segment_normals[index], distance))
        intersection = _line_intersection_2d(prev_point, segment_dirs[index - 1], next_point, segment_dirs[index])
        if intersection is None or _distance_2d(point, intersection) > max(abs(distance) * 12.0, 1.0e-6):
            normal = _normalized_2d(_add_2d(segment_normals[index - 1], segment_normals[index]))
            if _length_2d(normal) < 1.0e-9:
                normal = segment_normals[index]
            result.append(_add_2d(point, _mul_2d(normal, distance)))
        else:
            result.append(intersection)
    return result


def _line_intersection_2d(
    point_a: Vec2Data,
    dir_a: Vec2Data,
    point_b: Vec2Data,
    dir_b: Vec2Data,
) -> Vec2Data | None:
    cross = _cross_2d(dir_a, dir_b)
    if abs(cross) < 1.0e-9:
        return None
    rel = _sub_2d(point_b, point_a)
    t = _cross_2d(rel, dir_b) / cross
    return _add_2d(point_a, _mul_2d(dir_a, t))


def _signed_area_2d(points: list[Vec2Data]) -> float:
    area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        area += point[0] * next_point[1] - next_point[0] * point[1]
    return area * 0.5


def _normalized_2d(value: Vec2Data) -> Vec2Data:
    length = _length_2d(value)
    if length < 1.0e-12:
        return (0.0, 0.0)
    return (value[0] / length, value[1] / length)


def _length_2d(value: Vec2Data) -> float:
    return (value[0] * value[0] + value[1] * value[1]) ** 0.5


def _distance_2d(a: Vec2Data, b: Vec2Data) -> float:
    return _length_2d(_sub_2d(a, b))


def _add_2d(a: Vec2Data, b: Vec2Data) -> Vec2Data:
    return (a[0] + b[0], a[1] + b[1])


def _sub_2d(a: Vec2Data, b: Vec2Data) -> Vec2Data:
    return (a[0] - b[0], a[1] - b[1])


def _mul_2d(a: Vec2Data, scale: float) -> Vec2Data:
    return (a[0] * scale, a[1] * scale)


def _cross_2d(a: Vec2Data, b: Vec2Data) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _mesh_signed_volume(vertices: np.ndarray, triangles: np.ndarray) -> float:
    volume = 0.0
    for triangle in triangles:
        a = vertices[int(triangle[0])]
        b = vertices[int(triangle[1])]
        c = vertices[int(triangle[2])]
        volume += float(np.dot(a, np.cross(b, c))) / 6.0
    return volume


def sketch_point_transform(sketch: SketchItemDocument):
    """Return operation-local to document-local transform for a sketch plane."""
    return sketch_extrude_point_transform(sketch, sketch.plane.normal, 1.0)


def extrude_vector_for_operation(sketch: SketchItemDocument, operation) -> Vec3Data:
    vector = operation.params.get("vector")
    if vector is not None:
        try:
            return (float(vector[0]), float(vector[1]), float(vector[2]))
        except Exception as e:
            log.error(
                "[ProceduralMeshDocument] invalid extrude vector "
                f"operation='{operation.id}': {e}"
            )
            return (0.0, 0.0, 0.0)

    height = float(operation.params.get("height", 1.0))
    return (
        sketch.plane.normal[0] * height,
        sketch.plane.normal[1] * height,
        sketch.plane.normal[2] * height,
    )


def sketch_extrude_point_transform(
    sketch: SketchItemDocument,
    extrusion_vector: Vec3Data,
    extrusion_length: float,
):
    """Return local XY + unit-Z extrude coordinates to document-local transform."""

    origin = sketch.plane.origin
    x_axis = sketch.plane.x_axis
    y_axis = sketch.plane.y_axis
    z_scale = 1.0 / extrusion_length

    def transform(point: Vec3Data) -> Vec3Data:
        z = point[2] * z_scale
        return (
            origin[0] + x_axis[0] * point[0] + y_axis[0] * point[1] + extrusion_vector[0] * z,
            origin[1] + x_axis[1] * point[0] + y_axis[1] * point[1] + extrusion_vector[1] * z,
            origin[2] + x_axis[2] * point[0] + y_axis[2] * point[1] + extrusion_vector[2] * z,
        )

    return transform


def _norm(value: Vec3Data) -> float:
    return (value[0] * value[0] + value[1] * value[1] + value[2] * value[2]) ** 0.5


def _param_float(params: dict, key: str, default: float) -> float:
    value = params.get(key, default)
    try:
        return float(value)
    except Exception as e:
        log.error(f"[ProceduralMeshDocument] invalid float parameter '{key}' value='{value}': {e}")
        return float(default)


def _param_int(params: dict, key: str, default: int) -> int:
    value = params.get(key, default)
    try:
        return int(value)
    except Exception as e:
        log.error(f"[ProceduralMeshDocument] invalid integer parameter '{key}' value='{value}': {e}")
        return int(default)


def _param_bool(params: dict, key: str, default: bool) -> bool:
    value = params.get(key, default)
    return bool(value)


def _param_vec3(params: dict, key: str, default: Vec3Data) -> Vec3Data:
    value = params.get(key, default)
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception as e:
        log.error(f"[ProceduralMeshDocument] invalid vec3 parameter '{key}' value='{value}': {e}")
        return default


__all__ = [
    "EvaluatedSolid",
    "evaluate_document",
    "extrude_vector_for_operation",
    "sketch_extrude_point_transform",
    "sketch_point_transform",
]
