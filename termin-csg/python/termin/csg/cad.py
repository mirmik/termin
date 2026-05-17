"""Small script-CAD layer for quick CSG experiments.

The API is intentionally tiny for now:

    from termin.csg.cad import *
    draw(box(2, 2, 2, center=True) - sphere(1.15).up(0.25))
"""

import math

from termin.csg import (
    Solid,
    extrude as _extrude,
    make_box,
    make_cone,
    make_cylinder,
    make_sphere,
    to_mesh3,
)


def _xy(point):
    x, y = point
    return (float(x), float(y))


def _normalize_points(points):
    result = tuple(_xy(point) for point in points)
    if len(result) < 3:
        raise ValueError("Contour requires at least three points")
    return result


def _as_contour(value):
    if type(value) is Contour:
        return value
    return Contour(value)


class Contour:
    """2D polygon in the local XY plane.

    The contour can carry holes and can be extruded along +Z into a Solid.
    Winding is normalized by Manifold/Clipper2 in the native layer.
    """

    def __init__(self, points, holes=None):
        self.points = _normalize_points(points)
        hole_items = () if holes is None else holes
        self.holes = tuple(_normalize_points(hole) for hole in hole_items)

    def hole(self, hole):
        hole_contour = _as_contour(hole)
        return Contour(self.points, self.holes + (hole_contour.points,) + hole_contour.holes)

    def extrude(self, height):
        return _extrude(self.points, float(height), holes=self.holes)

    def move(self, x=0.0, y=0.0):
        dx = float(x)
        dy = float(y)
        return Contour(
            ((px + dx, py + dy) for px, py in self.points),
            holes=(((px + dx, py + dy) for px, py in hole) for hole in self.holes),
        )

    def right(self, value):
        return self.move(float(value), 0.0)

    def forward(self, value):
        return self.move(0.0, float(value))

    def mX(self, value):
        return self.right(value)

    def mY(self, value):
        return self.forward(value)

    def scale(self, x, y=None):
        sx = float(x)
        sy = sx if y is None else float(y)
        return Contour(
            ((px * sx, py * sy) for px, py in self.points),
            holes=(((px * sx, py * sy) for px, py in hole) for hole in self.holes),
        )

    def rotate(self, degrees):
        angle = math.radians(float(degrees))
        c = math.cos(angle)
        s = math.sin(angle)
        return Contour(
            ((px * c - py * s, px * s + py * c) for px, py in self.points),
            holes=(((px * c - py * s, px * s + py * c) for px, py in hole) for hole in self.holes),
        )

    def rZ(self, degrees):
        return self.rotate(degrees)

    def __sub__(self, other):
        return self.hole(other)

    def __repr__(self):
        return f"Contour(points={len(self.points)}, holes={len(self.holes)})"


def box(x, y=None, z=None, *, center=True):
    """Create an axis-aligned box.

    If only ``x`` is passed the box is a cube. ``center=True`` matches the
    common script-CAD convention: the primitive is centered at the origin.
    """
    yy = x if y is None else y
    zz = x if z is None else z
    return make_box(float(x), float(yy), float(zz), bool(center))


def sphere(radius, *, segments=32):
    """Create a sphere centered at the origin.

    The positional argument is a radius, matching Manifold and most geometry
    APIs. Use ``sphere(d / 2)`` when working from a desired diameter.
    """
    return make_sphere(float(radius), int(segments))


def cylinder(radius, height, *, segments=32, center=True):
    """Create a Z-axis cylinder."""
    return make_cylinder(float(radius), float(height), int(segments), bool(center))


def cone(radius_low, radius_high=0.0, height=1.0, *, segments=32, center=True):
    """Create a Z-axis cone or truncated cone."""
    return make_cone(
        float(radius_low),
        float(radius_high),
        float(height),
        int(segments),
        bool(center),
    )


def contour(points):
    """Create a 2D contour from ``(x, y)`` points in the local XY plane."""
    return Contour(points)


def polygon(points):
    """Alias for contour()."""
    return Contour(points)


def rect(x, y=None, *, center=True):
    """Create a rectangular 2D contour."""
    yy = x if y is None else y
    fx = float(x)
    fy = float(yy)
    if center:
        hx = fx * 0.5
        hy = fy * 0.5
        return Contour(((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)))
    return Contour(((0.0, 0.0), (fx, 0.0), (fx, fy), (0.0, fy)))


def circle(radius, *, segments=64):
    """Create a regular polygon approximating a circle."""
    r = float(radius)
    count = int(segments)
    if count < 3:
        raise ValueError("circle() requires at least three segments")
    return Contour(
        (
            (
                math.cos((2.0 * math.pi * index) / count) * r,
                math.sin((2.0 * math.pi * index) / count) * r,
            )
            for index in range(count)
        )
    )


def extrude(profile, height, *, holes=None):
    """Extrude a Contour or a raw point list along +Z."""
    if type(profile) is Contour:
        if holes is not None:
            raise ValueError("holes must be attached to Contour with .hole() or '-'")
        return profile.extrude(height)
    return _extrude(profile, float(height), holes=holes)


def translate(solid, x=0.0, y=0.0, z=0.0):
    """Return a translated copy of ``solid``."""
    return solid.move(x, y, z)


def scale(solid, x, y=None, z=None):
    """Return a scaled copy of ``solid``."""
    return solid.scale(x, y, z)


def rotate(solid, x=0.0, y=0.0, z=0.0):
    """Return a rotated copy of ``solid``. Angles are in degrees."""
    return solid.rotate(x, y, z)


def draw(*solids, title="termin-csg", show_wireframe=True):
    """Open a lightweight preview window for one or more solids.

    This is a termin-graphics/tcgui preview path, not a scene component path:
    no Entity, MeshComponent, or MeshRenderer is created.
    """
    from termin.csg.preview import draw_solids

    return draw_solids(*solids, title=title, show_wireframe=show_wireframe)


def mesh(solid, name="csg", *, flat_shading=False):
    """Convert a solid to a CPU Mesh3 for lower-level experiments."""
    if type(solid) is not Solid:
        raise TypeError("mesh() expects termin.csg.Solid")
    return to_mesh3(solid, name, flat_shading=bool(flat_shading))


__all__ = [
    "Contour",
    "box",
    "circle",
    "cone",
    "contour",
    "cylinder",
    "draw",
    "extrude",
    "mesh",
    "polygon",
    "rect",
    "rotate",
    "scale",
    "sphere",
    "translate",
]
