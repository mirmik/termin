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
    to_mesh3,
    to_tc_mesh,
    unite,
)
from termin.csg._csg_native import _extrude_pairs, _extrude_points  # noqa: E402


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
    "Solid",
    "extrude",
    "intersect",
    "make_box",
    "make_cone",
    "make_cylinder",
    "make_sphere",
    "subtract",
    "to_mesh3",
    "to_tc_mesh",
    "unite",
]
