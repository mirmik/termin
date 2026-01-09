"""
GizmoManager — manages all gizmos, handles raycast and drag projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from termin.editor.gizmo.base import (
    Gizmo,
    GizmoCollider,
    AxisConstraint,
    PlaneConstraint,
    AngleConstraint,
    RadiusConstraint,
    NoDrag,
)

if TYPE_CHECKING:
    from termin.visualization.render.immediate import ImmediateRenderer
    from termin.visualization.render.solid_primitives import SolidPrimitiveRenderer
    from termin.visualization.platform.backends.base import GraphicsBackend


@dataclass
class GizmoHit:
    """Result of a gizmo raycast."""
    gizmo: Gizmo
    collider: GizmoCollider
    t: float  # distance along ray


class GizmoManager:
    """
    Manages all active gizmos.

    Responsibilities:
    - Collect and render all gizmos
    - Raycast for picking
    - Project mouse movement according to constraints
    - Route events to gizmos
    """

    def __init__(self):
        self._gizmos: list[Gizmo] = []
        self._renderer: "ImmediateRenderer | None" = None

        # Solid renderer cache per GL context
        self._solid_renderers: dict[int, "SolidPrimitiveRenderer"] = {}

        # Drag state
        self._active_gizmo: Gizmo | None = None
        self._active_collider: GizmoCollider | None = None
        self._drag_start_ray_origin: np.ndarray | None = None
        self._drag_start_ray_dir: np.ndarray | None = None
        self._last_drag_position: np.ndarray | None = None

        # Hover state
        self._hovered_gizmo: Gizmo | None = None
        self._hovered_collider_id = None

    @property
    def is_dragging(self) -> bool:
        return self._active_gizmo is not None

    def add_gizmo(self, gizmo: Gizmo) -> None:
        """Add a gizmo to the manager."""
        if gizmo not in self._gizmos:
            self._gizmos.append(gizmo)

    def remove_gizmo(self, gizmo: Gizmo) -> None:
        """Remove a gizmo from the manager."""
        if gizmo in self._gizmos:
            self._gizmos.remove(gizmo)
            if self._active_gizmo is gizmo:
                self._end_drag()
            if self._hovered_gizmo is gizmo:
                self._hovered_gizmo = None
                self._hovered_collider_id = None

    def clear(self) -> None:
        """Remove all gizmos."""
        self._end_drag()
        self._gizmos.clear()
        self._hovered_gizmo = None
        self._hovered_collider_id = None

    # ============================================================
    # Rendering
    # ============================================================

    def _ensure_solid_renderer(self, context_key: int) -> "SolidPrimitiveRenderer":
        """Get or create SolidPrimitiveRenderer for the given GL context.

        VAOs are not shared across GL contexts, so we cache per context_key.
        """
        if context_key not in self._solid_renderers:
            from termin.visualization.render.solid_primitives import SolidPrimitiveRenderer
            self._solid_renderers[context_key] = SolidPrimitiveRenderer()
        return self._solid_renderers[context_key]

    def render(
        self,
        renderer: "ImmediateRenderer",
        graphics: "GraphicsBackend",
        view_matrix: np.ndarray,
        proj_matrix: np.ndarray,
        context_key: int = 0,
    ) -> None:
        """Render all visible gizmos."""
        self._renderer = renderer

        # Separate gizmos by renderer type
        solid_gizmos = []
        immediate_gizmos = []
        for gizmo in self._gizmos:
            if gizmo.visible:
                if gizmo.uses_solid_renderer:
                    solid_gizmos.append(gizmo)
                else:
                    immediate_gizmos.append(gizmo)

        # Pass 1: Opaque geometry

        # Solid renderer gizmos (efficient GPU meshes)
        if solid_gizmos:
            solid_renderer = self._ensure_solid_renderer(context_key)
            solid_renderer.begin(graphics, view_matrix, proj_matrix, depth_test=True, blend=False)
            for gizmo in solid_gizmos:
                gizmo.draw_solid(solid_renderer, graphics, view_matrix, proj_matrix)
            solid_renderer.end()

        # Immediate renderer gizmos (legacy, generates geometry each frame)
        if immediate_gizmos:
            renderer.begin()
            for gizmo in immediate_gizmos:
                gizmo.draw(renderer)
            renderer.flush(
                graphics=graphics,
                view_matrix=view_matrix,
                proj_matrix=proj_matrix,
                depth_test=True,
                blend=False,
            )

        # Pass 2: Transparent geometry

        # Solid renderer transparent
        if solid_gizmos:
            solid_renderer = self._ensure_solid_renderer(context_key)
            solid_renderer.begin(graphics, view_matrix, proj_matrix, depth_test=True, blend=True)
            for gizmo in solid_gizmos:
                gizmo.draw_transparent_solid(solid_renderer, graphics, view_matrix, proj_matrix)
            solid_renderer.end()

        # Immediate renderer transparent
        if immediate_gizmos:
            renderer.begin()
            for gizmo in immediate_gizmos:
                gizmo.draw_transparent(renderer)
            renderer.flush(
                graphics=graphics,
                view_matrix=view_matrix,
                proj_matrix=proj_matrix,
                depth_test=True,
                blend=True,
            )

        # Restore default state
        graphics.set_blend(False)

    # ============================================================
    # Picking
    # ============================================================

    def raycast(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> GizmoHit | None:
        """
        Raycast against all gizmo colliders.

        Returns the closest hit, or None.
        """
        ray_origin = np.asarray(ray_origin, dtype=np.float32)
        ray_dir = np.asarray(ray_dir, dtype=np.float32)

        best_hit: GizmoHit | None = None

        for gizmo in self._gizmos:
            if not gizmo.visible:
                continue

            for collider in gizmo.get_colliders():
                t = collider.geometry.ray_intersect(ray_origin, ray_dir)
                if t is not None:
                    if best_hit is None or t < best_hit.t:
                        best_hit = GizmoHit(gizmo, collider, t)

        return best_hit

    # ============================================================
    # Mouse Events
    # ============================================================

    def on_mouse_move(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> bool:
        """
        Handle mouse move.

        Returns True if a gizmo is being dragged.
        """
        ray_origin = np.asarray(ray_origin, dtype=np.float32)
        ray_dir = np.asarray(ray_dir, dtype=np.float32)

        if self._active_gizmo is not None:
            self._update_drag(ray_origin, ray_dir)
            return True

        # Update hover state
        hit = self.raycast(ray_origin, ray_dir)
        new_hovered = hit.gizmo if hit else None
        new_collider_id = hit.collider.id if hit else None

        if self._hovered_gizmo != new_hovered or self._hovered_collider_id != new_collider_id:
            # Exit old hover
            if self._hovered_gizmo is not None:
                self._hovered_gizmo.on_hover_exit(self._hovered_collider_id)

            # Enter new hover
            self._hovered_gizmo = new_hovered
            self._hovered_collider_id = new_collider_id

            if self._hovered_gizmo is not None:
                self._hovered_gizmo.on_hover_enter(self._hovered_collider_id)

        return False

    def on_mouse_down(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> bool:
        """
        Handle mouse down.

        Returns True if a gizmo was hit and drag started.
        """
        ray_origin = np.asarray(ray_origin, dtype=np.float32)
        ray_dir = np.asarray(ray_dir, dtype=np.float32)

        hit = self.raycast(ray_origin, ray_dir)
        if hit is None:
            return False

        self._active_gizmo = hit.gizmo
        self._active_collider = hit.collider
        self._drag_start_ray_origin = ray_origin.copy()
        self._drag_start_ray_dir = ray_dir.copy()

        # Compute initial drag position
        self._last_drag_position = self._project_ray_to_constraint(
            ray_origin, ray_dir, hit.collider.constraint
        )

        hit.gizmo.on_click(hit.collider.id, self._last_drag_position)

        return True

    def on_mouse_up(self) -> bool:
        """
        Handle mouse up.

        Returns True if a drag was ended.
        """
        if self._active_gizmo is None:
            return False

        self._active_gizmo.on_release(self._active_collider.id)
        self._end_drag()
        return True

    def _end_drag(self) -> None:
        """End current drag."""
        self._active_gizmo = None
        self._active_collider = None
        self._drag_start_ray_origin = None
        self._drag_start_ray_dir = None
        self._last_drag_position = None

    def _update_drag(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> None:
        """Update drag with new ray."""
        if self._active_gizmo is None or self._active_collider is None:
            return

        constraint = self._active_collider.constraint

        if isinstance(constraint, NoDrag):
            return

        new_position = self._project_ray_to_constraint(ray_origin, ray_dir, constraint)
        if new_position is None:
            return

        delta = np.zeros(3, dtype=np.float32)
        if self._last_drag_position is not None:
            delta = new_position - self._last_drag_position

        self._last_drag_position = new_position.copy()

        self._active_gizmo.on_drag(
            self._active_collider.id,
            new_position,
            delta,
        )

    def _project_ray_to_constraint(
        self,
        ray_origin: np.ndarray,
        ray_dir: np.ndarray,
        constraint,
    ) -> np.ndarray | None:
        """Project ray onto constraint, return position."""

        if isinstance(constraint, AxisConstraint):
            return self._closest_point_on_axis(
                ray_origin, ray_dir,
                constraint.origin, constraint.axis
            )

        elif isinstance(constraint, PlaneConstraint):
            return self._ray_plane_intersect(
                ray_origin, ray_dir,
                constraint.origin, constraint.normal
            )

        elif isinstance(constraint, AngleConstraint):
            # For rotation, return point on plane (angle computed by gizmo)
            return self._ray_plane_intersect(
                ray_origin, ray_dir,
                constraint.center, constraint.axis
            )

        elif isinstance(constraint, RadiusConstraint):
            # Project to plane through center perpendicular to view
            # For simplicity, use XZ plane through center
            return self._ray_plane_intersect(
                ray_origin, ray_dir,
                constraint.center, np.array([0, 1, 0], dtype=np.float32)
            )

        elif isinstance(constraint, NoDrag):
            return None

        return None

    @staticmethod
    def _closest_point_on_axis(
        ray_origin: np.ndarray,
        ray_dir: np.ndarray,
        axis_point: np.ndarray,
        axis_dir: np.ndarray,
    ) -> np.ndarray:
        """Find closest point on axis to ray."""
        # From the old gizmo code
        w0 = axis_point - ray_origin
        a = np.dot(axis_dir, axis_dir)
        b = np.dot(axis_dir, ray_dir)
        c = np.dot(ray_dir, ray_dir)
        d = np.dot(axis_dir, w0)
        e = np.dot(ray_dir, w0)

        denom = a * c - b * b
        if abs(denom) < 1e-10:
            # Parallel
            return axis_point.copy()

        s = (b * e - c * d) / denom
        return axis_point + axis_dir * s

    @staticmethod
    def _ray_plane_intersect(
        ray_origin: np.ndarray,
        ray_dir: np.ndarray,
        plane_origin: np.ndarray,
        plane_normal: np.ndarray,
    ) -> np.ndarray | None:
        """Intersect ray with plane."""
        denom = np.dot(ray_dir, plane_normal)
        if abs(denom) < 1e-6:
            return None

        t = np.dot(plane_origin - ray_origin, plane_normal) / denom
        return ray_origin + ray_dir * t
