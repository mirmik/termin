"""Generic editor tool for visualizing nearest mesh surface edges."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from tcbase import log
from tcbase._geom_native import Vec3
from tgfx._tgfx_native import Color4


_COLOR_CLICK = Color4(1.00, 1.00, 1.00, 1.00)
_COLOR_EDGE_POINT = Color4(1.00, 0.82, 0.10, 1.00)
_COLOR_EDGE = Color4(0.05, 0.95, 1.00, 1.00)
_COLOR_NORMAL = Color4(0.35, 1.00, 0.25, 1.00)


@dataclass
class _SurfaceEdgeDebugHit:
    entity_name: str
    click_point: tuple[float, float, float]
    edge_point: tuple[float, float, float]
    edge_a: tuple[float, float, float]
    edge_b: tuple[float, float, float]
    normal_end: tuple[float, float, float]
    triangle_index: int
    edge_indices: tuple[int, int]
    distance: float
    side: int


class SurfaceEdgeDebugTool:
    """Viewport click tool that draws TcMesh.find_surface_edge() results."""

    def __init__(self, editor) -> None:
        self._editor = editor
        self._enabled = False
        self._last_hit: _SurfaceEdgeDebugHit | None = None

    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._enabled == enabled:
            return
        self._enabled = enabled
        if enabled:
            self._editor.add_viewport_click_interceptor(self._on_viewport_click)
            self._editor.add_viewport_overlay_drawer(self._draw_overlay)
            log.info("[SurfaceEdgeDebugTool] enabled")
            return

        self._editor.remove_viewport_click_interceptor(self._on_viewport_click)
        self._editor.remove_viewport_overlay_drawer(self._draw_overlay)
        self._last_hit = None
        log.info("[SurfaceEdgeDebugTool] disabled")

    def toggle(self) -> None:
        self.set_enabled(not self._enabled)

    def _on_viewport_click(
        self,
        entity,
        x: float,
        y: float,
        has_world_point: bool,
        world_x: float,
        world_y: float,
        world_z: float,
        depth: float,
        view_depth: float,
        reproject_screen_error: float,
        reproject_depth_error: float,
        has_mesh_hit: bool,
        mesh_x: float,
        mesh_y: float,
        mesh_z: float,
        normal_x: float,
        normal_y: float,
        normal_z: float,
        triangle_index: int,
        index0: int,
        index1: int,
        index2: int,
    ) -> bool:
        if not self._enabled:
            return False
        if not has_mesh_hit:
            log.error("[SurfaceEdgeDebugTool] click ignored: no mesh hit")
            self._last_hit = None
            return True
        if not entity.valid():
            log.error("[SurfaceEdgeDebugTool] click ignored: picked entity is invalid")
            self._last_hit = None
            return True

        self._last_hit = self._find_edge_hit(
            entity,
            (float(mesh_x), float(mesh_y), float(mesh_z)),
            (float(normal_x), float(normal_y), float(normal_z)),
            int(triangle_index),
        )
        if self._last_hit is None:
            log.error(
                "[SurfaceEdgeDebugTool] surface edge not found: "
                f"screen=({x:.1f}, {y:.1f}) picked='{entity.name}' "
                f"tri={int(triangle_index)}"
            )
            return True

        hit = self._last_hit
        log.info(
            "[SurfaceEdgeDebugTool] surface edge: "
            f"picked='{hit.entity_name}' "
            f"click=({hit.click_point[0]:.3f}, {hit.click_point[1]:.3f}, {hit.click_point[2]:.3f}) "
            f"edge=({hit.edge_point[0]:.3f}, {hit.edge_point[1]:.3f}, {hit.edge_point[2]:.3f}) "
            f"tri={hit.triangle_index} edge_indices=({hit.edge_indices[0]}, {hit.edge_indices[1]}) "
            f"distance={hit.distance:.3f} side={hit.side}"
        )
        return True

    def _find_edge_hit(
        self,
        entity,
        mesh_point: tuple[float, float, float],
        mesh_normal: tuple[float, float, float],
        triangle_index: int,
    ) -> _SurfaceEdgeDebugHit | None:
        from termin.render_components import MeshRenderer

        renderer = entity.get_component(MeshRenderer)
        if renderer is None:
            log.error("[SurfaceEdgeDebugTool] edge query failed: picked entity has no MeshRenderer")
            return None

        mesh = renderer.mesh
        if mesh is None:
            log.error("[SurfaceEdgeDebugTool] edge query failed: MeshRenderer has no mesh")
            return None

        vertices = mesh.vertices
        if vertices is None:
            log.error("[SurfaceEdgeDebugTool] edge query failed: mesh has no CPU vertex data")
            return None

        pose = entity.transform.global_pose()
        metric = entity.transform.global_scale
        local_point = pose.inverse_transform_point(np.asarray(mesh_point, dtype=float))
        local_normal = pose.inverse_transform_vector(np.asarray(mesh_normal, dtype=float))
        local_up = pose.inverse_transform_vector(np.asarray((0.0, 0.0, 1.0), dtype=float))

        edge = mesh.find_surface_edge(
            triangle_index,
            _tuple3(local_point),
            _tuple3(local_normal),
            _tuple3(local_up),
            _tuple3(metric),
        )
        if edge is None:
            return None

        edge_indices = edge["indices"]
        index_a = int(edge_indices[0])
        index_b = int(edge_indices[1])
        if index_a < 0 or index_b < 0 or index_a >= vertices.shape[0] or index_b >= vertices.shape[0]:
            log.error(
                "[SurfaceEdgeDebugTool] edge query failed: "
                f"edge indices out of mesh vertex range ({index_a}, {index_b})"
            )
            return None
        local_edge_point = np.asarray(edge["point"], dtype=float)
        local_edge_a = np.asarray(vertices[index_a], dtype=float)
        local_edge_b = np.asarray(vertices[index_b], dtype=float)
        local_normal_vec = np.asarray(local_normal, dtype=float)
        normal_length = np.linalg.norm(local_normal_vec)
        if normal_length > 0.000001:
            local_normal_vec = local_normal_vec / normal_length
        local_normal_end = local_edge_point + local_normal_vec * 0.5

        return _SurfaceEdgeDebugHit(
            entity_name=entity.name,
            click_point=mesh_point,
            edge_point=_tuple3(pose.transform_point(local_edge_point)),
            edge_a=_tuple3(pose.transform_point(local_edge_a)),
            edge_b=_tuple3(pose.transform_point(local_edge_b)),
            normal_end=_tuple3(pose.transform_point(local_normal_end)),
            triangle_index=triangle_index,
            edge_indices=(index_a, index_b),
            distance=float(edge["distance"]),
            side=int(edge["side"]),
        )

    def _draw_overlay(self) -> None:
        if not self._enabled:
            return
        if self._last_hit is None:
            return

        from termin.visualization.render.immediate import ImmediateRenderer

        renderer = ImmediateRenderer.instance()
        hit = self._last_hit
        renderer.line(_vec3(hit.edge_a), _vec3(hit.edge_b), _COLOR_EDGE, False)
        renderer.line(_vec3(hit.edge_point), _vec3(hit.normal_end), _COLOR_NORMAL, False)
        renderer.sphere_wireframe(_vec3(hit.click_point), 0.055, _COLOR_CLICK, 8, False)
        renderer.sphere_wireframe(_vec3(hit.edge_point), 0.075, _COLOR_EDGE_POINT, 8, False)


def _tuple3(v) -> tuple[float, float, float]:
    return (float(v[0]), float(v[1]), float(v[2]))


def _vec3(point: tuple[float, float, float]) -> Vec3:
    return Vec3(point[0], point[1], point[2])
