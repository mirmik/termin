"""Small script-CAD layer for quick CSG experiments.

The API is intentionally tiny for now:

    from termin.csg.cad import *
    draw(box(2, 2, 2, center=True) - sphere(1.15).up(0.25))
"""

from termin.csg import Solid, make_box, make_cone, make_cylinder, make_sphere, to_mesh3


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


def mesh(solid, name="csg"):
    """Convert a solid to a CPU Mesh3 for lower-level experiments."""
    if type(solid) is not Solid:
        raise TypeError("mesh() expects termin.csg.Solid")
    return to_mesh3(solid, name)


__all__ = [
    "box",
    "cone",
    "cylinder",
    "draw",
    "mesh",
    "rotate",
    "scale",
    "sphere",
    "translate",
]
