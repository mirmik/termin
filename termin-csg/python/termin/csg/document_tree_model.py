"""Tree projection for procedural CSG documents."""

from __future__ import annotations

from dataclasses import dataclass, field

from termin.csg.document_eval import extrude_vector_for_operation
from termin.csg.procedural_document import (
    CONTOUR_ROLE_HOLE,
    CONTOUR_ROLE_OUTER,
    PRIMITIVE_OPERATION_KIND,
    ProceduralMeshDocument,
)


@dataclass
class DocumentTreeNode:
    text: str
    kind: str
    item_id: str
    children: list["DocumentTreeNode"] = field(default_factory=list)


def build_document_tree(document: ProceduralMeshDocument) -> list[DocumentTreeNode]:
    """Return the user-facing tree layout for a procedural document."""

    used_sketch_ids = document.used_source_sketch_ids()
    used_operation_ids = document.used_input_operation_ids()
    roots: list[DocumentTreeNode] = []
    for operation in document.operations:
        if operation.id not in used_operation_ids:
            roots.append(_operation_node(document, operation, set()))

    for item in document.items:
        if item.id not in used_sketch_ids:
            roots.append(_sketch_node(item))

    if not roots:
        roots.append(DocumentTreeNode("<empty>", "info", "empty"))
    return roots


def document_summary(document: ProceduralMeshDocument) -> str:
    return (
        f"Document v{document.version}: sketches={len(document.items)}, "
        f"contours={document.contour_count()}, operations={len(document.operations)}"
    )


def _operation_node(
    document: ProceduralMeshDocument,
    operation,
    visited: set[str],
    input_role: str = "",
) -> DocumentTreeNode:
    visited.add(operation.id)
    if operation.kind == "extrude":
        source_sketch_id = str(operation.params.get("source_sketch_id", ""))
        sketch = document.find_sketch(source_sketch_id) if source_sketch_id else None
        param_text = ""
        if sketch is not None:
            vector = extrude_vector_for_operation(sketch, operation)
            param_text = f" vector={_format_vec3(vector)}"
        node = DocumentTreeNode(
            text=_with_input_role(
                f"[Extrude] {operation.name}{param_text} inputs={len(operation.inputs)}",
                input_role,
            ),
            kind="operation",
            item_id=operation.id,
        )
        if sketch is not None:
            node.children.append(_sketch_node(sketch))
        return node

    if operation.kind == PRIMITIVE_OPERATION_KIND:
        primitive_kind = str(operation.params.get("primitive_kind", ""))
        node = DocumentTreeNode(
            text=_with_input_role(
                f"[{_primitive_label(primitive_kind)}] {operation.name}{_primitive_param_text(operation)}",
                input_role,
            ),
            kind="operation",
            item_id=operation.id,
        )
        return node

    if operation.kind in ("union", "subtract", "intersect"):
        node = DocumentTreeNode(
            text=_with_input_role(
                f"[{_operation_label(operation.kind)}] {operation.name} inputs={len(operation.inputs)}",
                input_role,
            ),
            kind="operation",
            item_id=operation.id,
        )
        for index, input_id in enumerate(operation.inputs):
            child_role = _boolean_input_role(operation.kind, index)
            child = document.find_operation(input_id)
            if child is None:
                node.children.append(DocumentTreeNode(f"{child_role} [Missing Operation] {input_id}", "info", input_id))
            elif child.id in visited:
                node.children.append(DocumentTreeNode(f"{child_role} [Cycle] {child.name} {_short_id(child.id)}", "info", child.id))
            else:
                node.children.append(_operation_node(document, child, visited.copy(), child_role))
        return node

    return DocumentTreeNode(
        text=_with_input_role(
            f"[Unknown] {operation.name} kind={operation.kind} inputs={len(operation.inputs)}",
            input_role,
        ),
        kind="operation",
        item_id=operation.id,
    )


def _operation_label(kind: str) -> str:
    if kind == "union":
        return "Union"
    if kind == "subtract":
        return "Subtract"
    if kind == "intersect":
        return "Intersect"
    return kind


def _boolean_input_role(kind: str, index: int) -> str:
    if kind == "subtract":
        if index == 0:
            return "[Base]"
        return "[Cut]"
    return "[Input]"


def _with_input_role(text: str, input_role: str) -> str:
    if not input_role:
        return text
    return f"{input_role} {text}"


def _primitive_label(kind: str) -> str:
    if kind == "box":
        return "Box"
    if kind == "sphere":
        return "Sphere"
    if kind == "cylinder":
        return "Cylinder"
    if kind == "cone":
        return "Cone"
    return "Primitive"


def _primitive_param_text(operation) -> str:
    params = operation.params
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


def _sketch_node(sketch) -> DocumentTreeNode:
    node = DocumentTreeNode(
        text=f"[Sketch] {sketch.name} {_short_id(sketch.id)} contours={len(sketch.contours)}",
        kind="sketch",
        item_id=sketch.id,
    )
    node.children.append(
        DocumentTreeNode(
            text=(
                "[Plane] "
                f"origin={_format_vec3(sketch.plane.origin)} "
                f"normal={_format_vec3(sketch.plane.normal)}"
            ),
            kind="plane",
            item_id=sketch.id,
        )
    )
    for contour in sketch.contours:
        if contour.role == CONTOUR_ROLE_OUTER:
            node.children.append(_contour_node(sketch, contour))
    for contour in sketch.contours:
        if contour.role == CONTOUR_ROLE_HOLE and _hole_parent_outer(sketch, contour) is None:
            node.children.append(_orphan_hole_node(contour))
    return node


def _contour_node(sketch, contour) -> DocumentTreeNode:
    node = DocumentTreeNode(
        text=f"[Outer] {contour.name} {_short_id(contour.id)} points={len(contour.points)}",
        kind="contour",
        item_id=contour.id,
    )
    for hole in sketch.hole_contours_for_outer(contour.id):
        node.children.append(
            DocumentTreeNode(
                text=f"[Hole] {hole.name} {_short_id(hole.id)} points={len(hole.points)}",
                kind="contour",
                item_id=hole.id,
            )
        )
    return node


def _orphan_hole_node(contour) -> DocumentTreeNode:
    return DocumentTreeNode(
        text=(
            f"[Hole: missing outer] {contour.name} {_short_id(contour.id)} "
            f"parent={_short_id(str(contour.parent_contour_id or ''))} points={len(contour.points)}"
        ),
        kind="contour",
        item_id=contour.id,
    )


def _hole_parent_outer(sketch, contour):
    parent = sketch.find_contour(str(contour.parent_contour_id or ""))
    if parent is None or parent.role != CONTOUR_ROLE_OUTER:
        return None
    return parent


def _short_id(value: str) -> str:
    if len(value) <= 10:
        return value
    return value[:10]


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


__all__ = [
    "DocumentTreeNode",
    "build_document_tree",
    "document_summary",
]
