from collections import Counter
from itertools import product
from math import sqrt

import pytest

from termin.editor_core.orientation_cube_geometry import build_orientation_cube


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b, strict=True))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def _ray_triangle(origin, direction, a, b, c):
    edge1, edge2 = _sub(b, a), _sub(c, a)
    p = _cross(direction, edge2)
    determinant = _dot(edge1, p)
    if abs(determinant) < 1e-9:
        return None
    delta = _sub(origin, a)
    u = _dot(delta, p) / determinant
    q = _cross(delta, edge1)
    v = _dot(direction, q) / determinant
    distance = _dot(edge2, q) / determinant
    if u < -1e-9 or v < -1e-9 or u + v > 1 + 1e-9 or distance < 0:
        return None
    return distance


def test_all_26_directions_hit_their_own_patch_first():
    patches = build_orientation_cube()
    assert len(patches) == len({p.key for p in patches}) == 26
    expected = {tuple(v / sqrt(sum(x * x for x in values)) for v in values)
                for values in product((-1, 0, 1), repeat=3) if any(values)}
    assert {p.direction for p in patches} == expected
    for target in patches:
        origin = tuple(4 * v for v in target.direction)
        direction = tuple(-v for v in target.direction)
        hits = []
        for patch in patches:
            for indices in patch.triangles:
                distance = _ray_triangle(origin, direction, *(patch.vertices[i] for i in indices))
                if distance is not None:
                    hits.append((distance, patch.key))
        nearest = min(distance for distance, _ in hits)
        assert {key for distance, key in hits if abs(distance - nearest) < 1e-8} == {target.key}


def test_mesh_is_closed_and_wound_outward():
    edges = Counter()
    for patch in build_orientation_cube():
        for ia, ib, ic in patch.triangles:
            a, b, c = (patch.vertices[i] for i in (ia, ib, ic))
            assert _dot(_cross(_sub(b, a), _sub(c, a)), patch.direction) > 0
            for edge in ((a, b), (b, c), (c, a)):
                edges[edge] += 1
    assert all(count == 1 and edges[(b, a)] == 1 for (a, b), count in edges.items())


def test_face_labels_are_outward_and_inside_face_bounds():
    patches = build_orientation_cube()
    faces = [p for p in patches if p.label]
    assert {p.label for p in faces} == {"N", "S", "E", "W", "TOP", "BOTTOM"}
    for patch in faces:
        assert patch.label_triangles
        for vertex in patch.label_vertices:
            assert _dot(vertex, patch.direction) == pytest.approx(1.002)
            assert all(abs(vertex[i]) < 0.76 for i in range(3) if patch.direction[i] == 0)
        for ia, ib, ic in patch.label_triangles:
            a, b, c = (patch.label_vertices[i] for i in (ia, ib, ic))
            assert _dot(_cross(_sub(b, a), _sub(c, a)), patch.direction) > 0
    assert next(p for p in faces if p.key == "NORTH").tooltip == "North (+Y)"


@pytest.mark.parametrize("half_extent,bevel", [(0, .2), (-1, .2), (float("inf"), .2),
                                             (1, 0), (1, 1), (1, float("nan"))])
def test_invalid_dimensions_are_rejected(half_extent, bevel):
    with pytest.raises(ValueError):
        build_orientation_cube(half_extent, bevel)
