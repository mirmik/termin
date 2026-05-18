"""Debug rendering helpers for termin.csg.Solid objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from tcbase._geom_native import Vec3
from tgfx._tgfx_native import Color4

from termin.csg import Solid, to_mesh3

Vec3Data = tuple[float, float, float]
PointTransform = Callable[[Vec3Data], Vec3Data]


@dataclass
class SolidRenderStyle:
    fill_color: Color4
    edge_color: Color4
    depth_test: bool = True


def draw_solid(
    renderer,
    solid: Solid,
    style: SolidRenderStyle,
    point_transform: PointTransform | None = None,
) -> None:
    """Draw a CSG solid as filled triangles plus triangle wireframe.

    The solid is converted to Mesh3 through termin-csg. `point_transform` is an
    optional local-to-world transform for callers that keep their CSG document
    in a sketch-local coordinate system.
    """

    mesh = to_mesh3(solid, "csg-debug-solid", "", True)
    mesh_vertices = np.asarray(mesh.vertices, dtype=np.float32).reshape(-1, 3)
    vertices = [_transform_vertex(vertex, point_transform) for vertex in mesh_vertices]
    triangles = np.asarray(mesh.triangles, dtype=np.uint32).reshape(-1)
    for i in range(0, len(triangles), 3):
        a = int(triangles[i])
        b = int(triangles[i + 1])
        c = int(triangles[i + 2])
        renderer.triangle(
            _vec3(vertices[a]),
            _vec3(vertices[b]),
            _vec3(vertices[c]),
            style.fill_color,
            style.depth_test,
        )
        renderer.line(_vec3(vertices[a]), _vec3(vertices[b]), style.edge_color, style.depth_test)
        renderer.line(_vec3(vertices[b]), _vec3(vertices[c]), style.edge_color, style.depth_test)
        renderer.line(_vec3(vertices[c]), _vec3(vertices[a]), style.edge_color, style.depth_test)


def _transform_vertex(vertex, point_transform: PointTransform | None) -> Vec3Data:
    point = (float(vertex[0]), float(vertex[1]), float(vertex[2]))
    if point_transform is None:
        return point
    return point_transform(point)


def _vec3(point: Vec3Data) -> Vec3:
    return Vec3(point[0], point[1], point[2])
