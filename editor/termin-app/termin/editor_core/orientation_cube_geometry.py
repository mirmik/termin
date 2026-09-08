"""Dependency-free mesh data for the editor's 26-direction navigation cube."""

from dataclasses import dataclass
from itertools import combinations, product
from math import isfinite, sqrt


Vec3 = tuple[float, float, float]
Triangle = tuple[int, int, int]


@dataclass(frozen=True)
class OrientationCubePatch:
    key: str
    direction: Vec3
    vertices: tuple[Vec3, ...]
    triangles: tuple[Triangle, ...]
    color: Vec3
    label: str
    tooltip: str
    label_vertices: tuple[Vec3, ...] = ()
    label_triangles: tuple[Triangle, ...] = ()


# Small block lettering keeps labels deterministic and independent of fonts,
# texture atlases, and the host UI toolkit.
_GLYPHS = {
    "N": ("10001", "11001", "10101", "10011", "10001"),
    "E": ("111", "100", "110", "100", "111"),
    "S": ("111", "100", "111", "001", "111"),
    "W": ("10001", "10001", "10101", "10101", "01010"),
    "T": ("111", "010", "010", "010", "010"),
    "O": ("111", "101", "101", "101", "111"),
    "P": ("111", "101", "111", "100", "100"),
    "B": ("110", "101", "110", "101", "110"),
    "M": ("10001", "11011", "10101", "10001", "10001"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    "+": ("000", "010", "111", "010", "000"),
    "-": ("000", "000", "111", "000", "000"),
}


def _dot(a: Vec3, b: Vec3) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _subtract(a: Vec3, b: Vec3) -> Vec3:
    return tuple(x - y for x, y in zip(a, b, strict=True))


def _label_mesh(normal: Vec3, half_extent: float, inset: float,
                lines: tuple[str, str]) -> tuple[tuple[Vec3, ...], tuple[Triangle, ...]]:
    # Vertical faces use world up. On horizontal faces north is the top of
    # the top label, and south the top of the bottom label.
    up = (0.0, normal[2], 0.0) if normal[2] else (0.0, 0.0, 1.0)
    right = _cross(up, normal)
    widths = [sum(len(_GLYPHS[c][0]) + 1 for c in line) - 1 for line in lines]
    cell = min(1.6 * inset / max(widths), 1.6 * inset / 12)
    vertices = []
    triangles = []
    for line_index, line in enumerate(lines):
        cursor = -widths[line_index] * cell / 2
        top = (5.5 - line_index * 7) * cell
        for char in line:
            glyph = _GLYPHS[char]
            for row, pattern in enumerate(glyph):
                for col, filled in enumerate(pattern):
                    if filled == "0":
                        continue
                    x, y = cursor + col * cell, top - row * cell
                    index = len(vertices)
                    for u, v in ((x, y - cell), (x + cell, y - cell),
                                 (x + cell, y), (x, y)):
                        vertices.append(tuple(normal[i] * half_extent * 1.002
                                              + right[i] * u + up[i] * v for i in range(3)))
                    triangles.extend(((index, index + 1, index + 2),
                                      (index, index + 2, index + 3)))
            cursor += (len(glyph[0]) + 1) * cell
    return tuple(vertices), tuple(triangles)


def build_orientation_cube(half_extent: float = 1.0,
                           bevel: float = 0.24) -> tuple[OrientationCubePatch, ...]:
    """Build a closed beveled cube, with one independently clickable patch per direction.

    ``bevel`` is the fraction of the half extent removed at each edge.
    North is +Y, east +X, and top +Z. Polygon winding faces outward.
    """
    if not isfinite(half_extent) or half_extent <= 0:
        raise ValueError("half_extent must be finite and positive")
    if not isfinite(bevel) or not 0 < bevel < 1:
        raise ValueError("bevel must lie strictly between zero and one")
    outer, inner = half_extent, half_extent * (1 - bevel)
    names = (("WEST", "EAST"), ("SOUTH", "NORTH"), ("BOTTOM", "TOP"))
    colors = ((0.68, 0.25, 0.23), (0.25, 0.58, 0.31), (0.25, 0.40, 0.73))
    patches = []
    for dimension in (1, 2, 3):
        for axes in combinations(range(3), dimension):
            for signs in product((-1, 1), repeat=dimension):
                signed = dict(zip(axes, signs, strict=True))
                direction = tuple(signed.get(axis, 0) / sqrt(dimension) for axis in range(3))
                # Names follow TOP_NORTH_EAST, matching camera preset names.
                key = "_".join(names[axis][signed[axis] > 0]
                               for axis in (2, 1, 0) if axis in signed)
                vertices = []
                if dimension == 1:
                    axis = axes[0]
                    free = [i for i in range(3) if i != axis]
                    for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                        point = [0.0, 0.0, 0.0]
                        point[axis] = outer * signed[axis]
                        point[free[0]], point[free[1]] = inner * a, inner * b
                        vertices.append(tuple(point))
                elif dimension == 2:
                    a, b = axes
                    free = next(i for i in range(3) if i not in signed)
                    for va, vb, vc in ((outer, inner, -inner), (inner, outer, -inner),
                                       (inner, outer, inner), (outer, inner, inner)):
                        point = [0.0, 0.0, 0.0]
                        point[a], point[b], point[free] = va * signed[a], vb * signed[b], vc
                        vertices.append(tuple(point))
                else:
                    for outer_axis in axes:
                        vertices.append(tuple((outer if i == outer_axis else inner) * signed[i]
                                              for i in range(3)))
                if _dot(_cross(_subtract(vertices[1], vertices[0]),
                               _subtract(vertices[2], vertices[0])), direction) < 0:
                    vertices.reverse()
                triangles = tuple((0, i, i + 1) for i in range(1, len(vertices) - 1))
                color = tuple(sum(colors[a][i] for a in axes) / dimension for i in range(3))
                label, label_vertices, label_triangles = "", (), ()
                if dimension == 1:
                    label = key if axes[0] == 2 else key[0]
                    axis_label = ("+" if signs[0] > 0 else "-") + "XYZ"[axes[0]]
                    label_vertices, label_triangles = _label_mesh(direction, outer, inner, (label, axis_label))
                tooltip = key.replace("_", " ").title() + " (" + ", ".join(
                    ("+" if signed[a] > 0 else "-") + "XYZ"[a] for a in (2, 1, 0) if a in signed) + ")"
                patches.append(OrientationCubePatch(key, direction, tuple(vertices), triangles,
                                                    color, label, tooltip, label_vertices, label_triangles))
    return tuple(patches)
