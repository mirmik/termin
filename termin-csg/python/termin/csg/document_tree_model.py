"""Tree projection for procedural CSG documents."""

from __future__ import annotations

from dataclasses import dataclass, field

from termin.csg.document_eval import extrude_vector_for_operation
from termin.csg.procedural_document import ProceduralMeshDocument


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


def _operation_node(document: ProceduralMeshDocument, operation, visited: set[str]) -> DocumentTreeNode:
    visited.add(operation.id)
    if operation.kind == "extrude":
        source_sketch_id = str(operation.params.get("source_sketch_id", ""))
        sketch = document.find_sketch(source_sketch_id) if source_sketch_id else None
        param_text = ""
        if sketch is not None:
            vector = extrude_vector_for_operation(sketch, operation)
            param_text = f" vector={_format_vec3(vector)}"
        node = DocumentTreeNode(
            text=f"[Extrude] {operation.name}{param_text} inputs={len(operation.inputs)}",
            kind="operation",
            item_id=operation.id,
        )
        if sketch is not None:
            node.children.append(_sketch_node(sketch))
        return node

    if operation.kind in ("union", "subtract", "intersect"):
        node = DocumentTreeNode(
            text=f"[{_operation_label(operation.kind)}] {operation.name} inputs={len(operation.inputs)}",
            kind="operation",
            item_id=operation.id,
        )
        for input_id in operation.inputs:
            child = document.find_operation(input_id)
            if child is None:
                node.children.append(DocumentTreeNode(f"[Missing Operation] {input_id}", "info", input_id))
            elif child.id in visited:
                node.children.append(DocumentTreeNode(f"[Cycle] {child.name} {_short_id(child.id)}", "info", child.id))
            else:
                node.children.append(_operation_node(document, child, visited.copy()))
        return node

    return DocumentTreeNode(
        text=f"[Unknown] {operation.name} kind={operation.kind} inputs={len(operation.inputs)}",
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
        node.children.append(
            DocumentTreeNode(
                text=f"[Contour] {contour.name} {_short_id(contour.id)} points={len(contour.points)}",
                kind="contour",
                item_id=contour.id,
            )
        )
    return node


def _short_id(value: str) -> str:
    if len(value) <= 10:
        return value
    return value[:10]


def _format_vec3(value: tuple[float, float, float]) -> str:
    return f"({value[0]:.2f},{value[1]:.2f},{value[2]:.2f})"


__all__ = [
    "DocumentTreeNode",
    "build_document_tree",
    "document_summary",
]
