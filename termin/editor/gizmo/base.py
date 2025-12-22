"""
Base classes for the unified gizmo system.

Architecture:
- Gizmo: декларативный объект, умеет рисовать себя и объявлять colliders
- GizmoCollider: геометрия + constraint для picking/drag
- DragConstraint: как проецировать движение мыши при drag
- GizmoManager: управляет всеми гизмо, raycast, вычисляет drag
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.render.immediate import ImmediateRenderer
    from termin.visualization.render.solid_primitives import SolidPrimitiveRenderer
    from termin.visualization.platform.backends.base import GraphicsBackend


# ============================================================
# Drag Constraints
# ============================================================

class DragConstraint(ABC):
    """Base class for drag constraints."""
    pass


@dataclass
class AxisConstraint(DragConstraint):
    """Constrain drag to a single axis."""
    origin: np.ndarray
    axis: np.ndarray  # normalized direction


@dataclass
class PlaneConstraint(DragConstraint):
    """Constrain drag to a plane."""
    origin: np.ndarray
    normal: np.ndarray  # normalized


@dataclass
class RadiusConstraint(DragConstraint):
    """Constrain drag to change radius from center."""
    center: np.ndarray


@dataclass
class AngleConstraint(DragConstraint):
    """Constrain drag to rotation around axis."""
    center: np.ndarray
    axis: np.ndarray  # normalized rotation axis


@dataclass
class NoDrag(DragConstraint):
    """No drag - click only."""
    pass


# ============================================================
# Collider Geometry
# ============================================================

class ColliderGeometry(ABC):
    """Base class for collider geometry."""

    @abstractmethod
    def ray_intersect(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> float | None:
        """
        Test ray intersection.

        Returns:
            Distance along ray (t) or None if no hit.
        """
        ...


@dataclass
class SphereGeometry(ColliderGeometry):
    """Sphere collider."""
    center: np.ndarray
    radius: float

    def ray_intersect(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> float | None:
        oc = ray_origin - self.center
        a = np.dot(ray_dir, ray_dir)
        b = 2.0 * np.dot(oc, ray_dir)
        c = np.dot(oc, oc) - self.radius * self.radius

        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return None

        sqrt_disc = np.sqrt(discriminant)
        t1 = (-b - sqrt_disc) / (2 * a)
        t2 = (-b + sqrt_disc) / (2 * a)

        if t1 >= 0:
            return t1
        if t2 >= 0:
            return t2
        return None


@dataclass
class CylinderGeometry(ColliderGeometry):
    """Cylinder collider (finite, capped)."""
    start: np.ndarray
    end: np.ndarray
    radius: float

    def ray_intersect(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> float | None:
        cyl_axis = self.end - self.start
        cyl_length = np.linalg.norm(cyl_axis)
        if cyl_length < 1e-6:
            return None
        cyl_axis = cyl_axis / cyl_length

        delta = ray_origin - self.start

        ray_dot_axis = np.dot(ray_dir, cyl_axis)
        delta_dot_axis = np.dot(delta, cyl_axis)

        d_perp = ray_dir - ray_dot_axis * cyl_axis
        delta_perp = delta - delta_dot_axis * cyl_axis

        a = np.dot(d_perp, d_perp)
        b = 2.0 * np.dot(d_perp, delta_perp)
        c = np.dot(delta_perp, delta_perp) - self.radius * self.radius

        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return None

        if a < 1e-10:
            if c <= 0:
                return 0.0
            return None

        sqrt_disc = np.sqrt(discriminant)
        t1 = (-b - sqrt_disc) / (2 * a)
        t2 = (-b + sqrt_disc) / (2 * a)

        for t in [t1, t2]:
            if t < 0:
                continue
            hit_point = ray_origin + ray_dir * t
            proj = np.dot(hit_point - self.start, cyl_axis)
            if 0 <= proj <= cyl_length:
                return t

        return None


@dataclass
class TorusGeometry(ColliderGeometry):
    """Torus collider (for rotation rings)."""
    center: np.ndarray
    axis: np.ndarray  # normalized
    major_radius: float
    minor_radius: float

    def ray_intersect(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> float | None:
        # Simplified: intersect with plane, check if in annulus
        tangent, bitangent = _build_basis(self.axis)
        to_local = np.array([tangent, bitangent, self.axis], dtype=np.float32)

        local_origin = to_local @ (ray_origin - self.center)
        local_dir = to_local @ ray_dir

        if abs(local_dir[2]) < 1e-6:
            if abs(local_origin[2]) > self.minor_radius:
                return None
            return None

        t_plane = -local_origin[2] / local_dir[2]
        if t_plane < 0:
            return None

        hit_local = local_origin + local_dir * t_plane
        dist_from_center = np.sqrt(hit_local[0]**2 + hit_local[1]**2)

        if abs(dist_from_center - self.major_radius) <= self.minor_radius:
            return t_plane

        # Check slightly above/below for minor radius
        for dz in [-self.minor_radius * 0.5, self.minor_radius * 0.5]:
            if abs(local_dir[2]) < 1e-6:
                continue
            t_off = -(local_origin[2] - dz) / local_dir[2]
            if t_off < 0:
                continue
            hit = local_origin + local_dir * t_off
            dist = np.sqrt(hit[0]**2 + hit[1]**2)
            if abs(dist - self.major_radius) <= self.minor_radius:
                return t_off

        return None


@dataclass
class QuadGeometry(ColliderGeometry):
    """Quad collider (for plane handles)."""
    p0: np.ndarray
    p1: np.ndarray
    p2: np.ndarray
    p3: np.ndarray
    normal: np.ndarray

    def ray_intersect(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> float | None:
        denom = np.dot(ray_dir, self.normal)
        if abs(denom) < 1e-6:
            return None

        t = np.dot(self.p0 - ray_origin, self.normal) / denom
        if t < 0:
            return None

        hit = ray_origin + ray_dir * t

        def same_side(edge_start, edge_end, point, n):
            edge = edge_end - edge_start
            to_point = point - edge_start
            cross = np.cross(edge, to_point)
            return np.dot(cross, n) >= 0

        if (same_side(self.p0, self.p1, hit, self.normal) and
            same_side(self.p1, self.p2, hit, self.normal) and
            same_side(self.p2, self.p3, hit, self.normal) and
            same_side(self.p3, self.p0, hit, self.normal)):
            return t

        return None


# ============================================================
# GizmoCollider
# ============================================================

@dataclass
class GizmoCollider:
    """
    Collider for gizmo picking.

    Attributes:
        id: Identifier for the gizmo to know which collider was hit
        geometry: Shape for ray intersection
        constraint: How to project mouse movement during drag
    """
    id: Any
    geometry: ColliderGeometry
    constraint: DragConstraint


# ============================================================
# Gizmo Base Class
# ============================================================

class Gizmo(ABC):
    """
    Abstract base class for all gizmos.

    A gizmo is an interactive 3D widget that:
    - Draws itself using ImmediateRenderer
    - Declares colliders for picking
    - Receives events when colliders are clicked/dragged
    """

    visible: bool = True

    def draw(self, renderer: "ImmediateRenderer") -> None:
        """
        Draw opaque gizmo geometry using ImmediateRenderer.

        Called every frame. Add primitives to the renderer.
        Override this for opaque geometry (arrows, rings, spheres).

        NOTE: Prefer implementing draw_solid() for better performance.
        """
        pass

    def draw_solid(
        self,
        renderer: "SolidPrimitiveRenderer",
        graphics: "GraphicsBackend",
        view: np.ndarray,
        proj: np.ndarray,
    ) -> None:
        """
        Draw opaque gizmo geometry using SolidPrimitiveRenderer.

        More efficient than draw() - uses pre-built GPU meshes.
        If implemented, this is called instead of draw().
        """
        pass

    def draw_transparent(self, renderer: "ImmediateRenderer") -> None:
        """
        Draw transparent gizmo geometry.

        Called after opaque pass. Override for transparent geometry (plane quads).
        """
        pass

    def draw_transparent_solid(
        self,
        renderer: "SolidPrimitiveRenderer",
        graphics: "GraphicsBackend",
        view: np.ndarray,
        proj: np.ndarray,
    ) -> None:
        """
        Draw transparent gizmo geometry using SolidPrimitiveRenderer.

        More efficient than draw_transparent().
        If implemented, this is called instead of draw_transparent().
        """
        pass

    @property
    def uses_solid_renderer(self) -> bool:
        """Return True if this gizmo uses SolidPrimitiveRenderer."""
        return False

    @abstractmethod
    def get_colliders(self) -> list[GizmoCollider]:
        """
        Get colliders for picking.

        Called when checking for mouse interaction.
        """
        ...

    def on_hover_enter(self, collider_id: Any) -> None:
        """Called when mouse starts hovering over a collider."""
        pass

    def on_hover_exit(self, collider_id: Any) -> None:
        """Called when mouse stops hovering over a collider."""
        pass

    def on_click(self, collider_id: Any, hit_position: np.ndarray | None) -> None:
        """
        Called when a collider is clicked (mouse down).

        Args:
            collider_id: Which collider was clicked
            hit_position: Projected position on the constraint (for computing grab offset)
        """
        pass

    def on_drag(self, collider_id: Any, position: np.ndarray, delta: np.ndarray) -> None:
        """
        Called during drag with projected position.

        Args:
            collider_id: Which collider is being dragged
            position: New position (projected according to constraint)
            delta: Change from last position
        """
        pass

    def on_release(self, collider_id: Any) -> None:
        """Called when drag ends (mouse up)."""
        pass


# ============================================================
# Utility
# ============================================================

def _build_basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build orthonormal basis from axis (tangent, bitangent)."""
    axis = np.asarray(axis, dtype=np.float32)
    if abs(axis[0]) < 0.9:
        tangent = np.cross(axis, np.array([1, 0, 0], dtype=np.float32))
    else:
        tangent = np.cross(axis, np.array([0, 1, 0], dtype=np.float32))
    tangent = tangent / np.linalg.norm(tangent)
    bitangent = np.cross(axis, tangent)
    return tangent, bitangent
