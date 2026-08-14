"""Constructive solid geometry helpers built on Manifold."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_csg")

from termin.csg._csg_native import (  # noqa: E402
    Point2,
    Solid,
    intersect,
    make_box,
    make_cone,
    make_cylinder,
    make_sphere,
    subtract,
    from_mesh3,
    to_mesh3,
    to_tc_mesh,
    unite,
)
from termin.csg._csg_native import _extrude_pairs, _extrude_points  # noqa: E402
from termin.csg.procedural_document import (  # noqa: E402
    CONTOUR_ROLE_HOLE,
    CONTOUR_ROLE_OUTER,
    CONTOUR_ROLES,
    ContourDocument,
    OperationDocument,
    OPERATION_KIND_WALL,
    PRIMITIVE_KINDS,
    PRIMITIVE_OPERATION_KIND,
    ProceduralMeshDocument,
    ProceduralPlane,
    SketchItemDocument,
    SketchPathDocument,
)
from termin.csg.document_eval import EvaluatedSolid, evaluate_document  # noqa: E402
from termin.csg.document_mesh import document_to_mesh3, document_to_tc_mesh  # noqa: E402
from termin.csg.editor_controller import CsgEditorCommandResult, CsgEditorController  # noqa: E402
from termin.csg.operation_specs import (  # noqa: E402
    OPERATION_SPECS_BY_KIND,
    OperationParamSpec,
    OperationSpec,
    PRIMITIVE_SPECS_BY_KIND,
    PrimitiveSpec,
    operation_spec,
    ordered_boolean_operation_specs,
    ordered_primitive_specs,
    primitive_spec,
)


def _point2(value):
    if type(value) is Point2:
        return value
    x, y = value
    return Point2(float(x), float(y))


def extrude(outer, height, holes=None):
    """Extrude a 2D contour along +Z.

    ``outer`` and ``holes`` may contain either ``Point2`` objects or plain
    ``(x, y)`` pairs. The contours are interpreted in local XY coordinates.
    """
    outer_items = list(outer)
    hole_items = [] if holes is None else holes

    use_point_objects = False
    for p in outer_items:
        use_point_objects = type(p) is Point2
        break

    if use_point_objects:
        converted_outer = [_point2(p) for p in outer_items]
        converted_holes = [[_point2(p) for p in h] for h in hole_items]
        return _extrude_points(converted_outer, float(height), converted_holes)

    converted_outer = [(float(x), float(y)) for x, y in outer_items]
    converted_holes = [[(float(x), float(y)) for x, y in h] for h in hole_items]
    return _extrude_pairs(converted_outer, float(height), converted_holes)


__all__ = [
    "Point2",
    "ContourDocument",
    "CONTOUR_ROLE_HOLE",
    "CONTOUR_ROLE_OUTER",
    "CONTOUR_ROLES",
    "OperationDocument",
    "OPERATION_KIND_WALL",
    "PRIMITIVE_KINDS",
    "PRIMITIVE_OPERATION_KIND",
    "ProceduralMeshDocument",
    "ProceduralPlane",
    "SketchItemDocument",
    "SketchPathDocument",
    "EvaluatedSolid",
    "CsgEditorCommandResult",
    "CsgEditorController",
    "OPERATION_SPECS_BY_KIND",
    "OperationParamSpec",
    "OperationSpec",
    "PRIMITIVE_SPECS_BY_KIND",
    "PrimitiveSpec",
    "Solid",
    "document_to_mesh3",
    "document_to_tc_mesh",
    "evaluate_document",
    "extrude",
    "from_mesh3",
    "intersect",
    "make_box",
    "make_cone",
    "make_cylinder",
    "make_sphere",
    "subtract",
    "to_mesh3",
    "to_tc_mesh",
    "unite",
    "operation_spec",
    "ordered_boolean_operation_specs",
    "ordered_primitive_specs",
    "primitive_spec",
]
