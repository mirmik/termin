"""
ImmediateGizmoRenderer - Immediate mode transform gizmo rendering.

Renders translation arrows and rotation rings using ImmediateRenderer,
with mathematical raycast picking instead of ID buffer.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np

from termin.visualization.render.immediate import ImmediateRenderer

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
    from termin.visualization.platform.backends.base import GraphicsBackend


def closest_point_on_axis_from_ray(axis_point, axis_dir, ray_origin, ray_dir):
    """
    Find closest point on line (axis_point + t * axis_dir) to ray (ray_origin + s * ray_dir).
    Returns parameter t and the point itself.
    """
    p = np.asarray(axis_point, dtype=np.float32)
    a = np.asarray(axis_dir, dtype=np.float32)
    o = np.asarray(ray_origin, dtype=np.float32)
    d = np.asarray(ray_dir, dtype=np.float32)

    a_norm = np.linalg.norm(a)
    if a_norm == 0:
        return 0.0, p.copy()
    a /= a_norm

    d_norm = np.linalg.norm(d)
    if d_norm == 0:
        return 0.0, p.copy()
    d /= d_norm

    w0 = p - o
    a_dot_d = np.dot(a, d)
    denom = 1.0 - a_dot_d * a_dot_d

    if float(np.abs(denom)) < 1e-6:
        t = -np.dot(w0, a)
        return t, p + a * t

    w0_dot_d = np.dot(w0, d)
    w0_dot_a = np.dot(w0, a)

    t = (a_dot_d * w0_dot_d - w0_dot_a) / denom
    point_on_axis = p + a * t
    return t, point_on_axis


class GizmoElement(Enum):
    """Gizmo element types for picking."""
    NONE = auto()
    TRANSLATE_X = auto()
    TRANSLATE_Y = auto()
    TRANSLATE_Z = auto()
    TRANSLATE_XY = auto()  # Plane handles
    TRANSLATE_XZ = auto()
    TRANSLATE_YZ = auto()
    ROTATE_X = auto()
    ROTATE_Y = auto()
    ROTATE_Z = auto()


# Colors for each axis
AXIS_COLORS = {
    "x": (1.0, 0.2, 0.2, 1.0),
    "y": (0.2, 1.0, 0.2, 1.0),
    "z": (0.2, 0.4, 1.0, 1.0),
}

# Highlighted colors
AXIS_COLORS_HIGHLIGHT = {
    "x": (1.0, 0.6, 0.6, 1.0),
    "y": (0.6, 1.0, 0.6, 1.0),
    "z": (0.6, 0.7, 1.0, 1.0),
}

# Colors for plane handles (blend of two axes, semi-transparent)
PLANE_COLORS = {
    "xy": (0.8, 0.8, 0.2, 0.5),
    "xz": (0.8, 0.4, 0.6, 0.5),
    "yz": (0.2, 0.8, 0.8, 0.5),
}

PLANE_COLORS_HIGHLIGHT = {
    "xy": (1.0, 1.0, 0.4, 0.7),
    "xz": (1.0, 0.6, 0.8, 0.7),
    "yz": (0.4, 1.0, 1.0, 0.7),
}


class ImmediateGizmoRenderer:
    """
    Renders a transform gizmo using ImmediateRenderer.

    Features:
    - Solid arrows for translation (X, Y, Z)
    - Solid tori for rotation (X, Y, Z)
    - Mathematical raycast picking
    - Highlight on hover
    """

    def __init__(
        self,
        size: float = 1.5,
        shaft_radius: float = 0.03,
        head_radius: float = 0.07,
        ring_major_radius: float = 1.25,
        ring_minor_radius: float = 0.02,
    ):
        self._renderer = ImmediateRenderer()

        # Base gizmo dimensions (before screen scale)
        self._base_size = size
        self._base_shaft_radius = shaft_radius
        self._base_head_radius = head_radius
        self._base_ring_major_radius = ring_major_radius
        self._base_ring_minor_radius = ring_minor_radius
        self._base_head_length_ratio = 0.25
        self._base_pick_tolerance = 0.08
        self._base_plane_offset = 0.1   # Distance from origin to plane quad
        self._base_plane_size = 0.25    # Size of the plane quad

        # Current screen scale (updated each frame)
        self._screen_scale = 1.0

        # Effective dimensions (computed from base * screen_scale)
        self._update_dimensions()

        # Target entity (gizmo reads position/rotation from here)
        self.target: "Entity | None" = None

        # Orientation mode: "local" = follow target rotation, "global" = world axes
        self.orientation_mode: str = "local"

        # State
        self.visible = True
        self.hovered_element: GizmoElement = GizmoElement.NONE
        self.active_element: GizmoElement = GizmoElement.NONE

    def _update_dimensions(self) -> None:
        """Update effective dimensions based on screen scale."""
        s = self._screen_scale
        self.size = self._base_size * s
        self.shaft_radius = self._base_shaft_radius * self.size
        self.head_radius = self._base_head_radius * self.size
        self.ring_major_radius = self._base_ring_major_radius * self.size
        self.ring_minor_radius = self._base_ring_minor_radius * self.size
        self.arrow_length = self.size
        self.head_length_ratio = self._base_head_length_ratio
        self.pick_tolerance = self._base_pick_tolerance * self.size
        self.plane_offset = self._base_plane_offset * self.size
        self.plane_size = self._base_plane_size * self.size

    def set_screen_scale(self, scale: float) -> None:
        """Set screen-space scale factor."""
        if abs(self._screen_scale - scale) > 1e-6:
            self._screen_scale = scale
            self._update_dimensions()

    def _get_position(self) -> np.ndarray:
        """Get gizmo position from target."""
        if self.target is None:
            return np.zeros(3, dtype=np.float32)
        return np.asarray(self.target.transform.global_pose().lin, dtype=np.float32)

    def _get_rotation(self) -> np.ndarray:
        """Get gizmo rotation based on orientation mode."""
        if self.orientation_mode == "global" or self.target is None:
            return np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)  # identity
        return np.asarray(self.target.transform.global_pose().ang, dtype=np.float32)

    def _quat_to_matrix(self, q: np.ndarray) -> np.ndarray:
        """Convert quaternion (x, y, z, w) to 3x3 rotation matrix."""
        x, y, z, w = q
        return np.array([
            [1 - 2*y*y - 2*z*z, 2*x*y - 2*z*w, 2*x*z + 2*y*w],
            [2*x*y + 2*z*w, 1 - 2*x*x - 2*z*z, 2*y*z - 2*x*w],
            [2*x*z - 2*y*w, 2*y*z + 2*x*w, 1 - 2*x*x - 2*y*y],
        ], dtype=np.float32)

    def _get_world_axis(self, axis: str) -> np.ndarray:
        """Get world-space axis direction."""
        rot = self._quat_to_matrix(self._get_rotation())
        if axis == "x":
            return rot[:, 0]
        elif axis == "y":
            return rot[:, 1]
        else:
            return rot[:, 2]

    def _get_color(self, axis: str, element: GizmoElement) -> tuple:
        """Get color for an axis, considering hover/active state."""
        is_active = self.active_element == element
        is_hovered = self.hovered_element == element and not is_active
        if is_active or is_hovered:
            return AXIS_COLORS_HIGHLIGHT[axis]
        return AXIS_COLORS[axis]

    def _get_plane_color(self, plane: str, element: GizmoElement) -> tuple:
        """Get color for a plane handle, considering hover/active state."""
        is_active = self.active_element == element
        is_hovered = self.hovered_element == element and not is_active
        if is_active or is_hovered:
            return PLANE_COLORS_HIGHLIGHT[plane]
        return PLANE_COLORS[plane]

    def begin(self) -> None:
        """Start accumulating gizmo geometry (no-op, drawing done in flush)."""
        pass

    def draw(self) -> None:
        """Draw the gizmo geometry (no-op, drawing done in flush)."""
        pass

    def flush(
        self,
        graphics: "GraphicsBackend",
        view_matrix: np.ndarray,
        proj_matrix: np.ndarray,
    ) -> None:
        """Render gizmo geometry in two passes: opaque then transparent."""
        if not self.visible or self.target is None:
            return

        origin = self._get_position()

        # === Pass 1: Opaque geometry (arrows, rings) ===
        self._renderer.begin()

        # Draw translation arrows
        for axis, element in [
            ("x", GizmoElement.TRANSLATE_X),
            ("y", GizmoElement.TRANSLATE_Y),
            ("z", GizmoElement.TRANSLATE_Z),
        ]:
            direction = self._get_world_axis(axis)
            color = self._get_color(axis, element)
            self._renderer.arrow_solid(
                origin=origin,
                direction=direction,
                length=self.arrow_length,
                color=color,
                shaft_radius=self.shaft_radius,
                head_radius=self.head_radius,
                head_length_ratio=self.head_length_ratio,
                segments=16,
            )

        # Draw rotation rings
        for axis, element in [
            ("x", GizmoElement.ROTATE_X),
            ("y", GizmoElement.ROTATE_Y),
            ("z", GizmoElement.ROTATE_Z),
        ]:
            ring_axis = self._get_world_axis(axis)
            color = self._get_color(axis, element)
            self._renderer.torus_solid(
                center=origin,
                axis=ring_axis,
                major_radius=self.ring_major_radius,
                minor_radius=self.ring_minor_radius,
                color=color,
                major_segments=48,
                minor_segments=8,
            )

        self._renderer.flush(
            graphics=graphics,
            view_matrix=view_matrix,
            proj_matrix=proj_matrix,
            depth_test=True,
            blend=False,  # Opaque pass
        )

        # === Pass 2: Transparent geometry (plane quads) ===
        self._renderer.begin()

        axis_x = self._get_world_axis("x")
        axis_y = self._get_world_axis("y")
        axis_z = self._get_world_axis("z")
        off = self.plane_offset
        sz = self.plane_size

        for plane, element, a1, a2 in [
            ("xy", GizmoElement.TRANSLATE_XY, axis_x, axis_y),
            ("xz", GizmoElement.TRANSLATE_XZ, axis_x, axis_z),
            ("yz", GizmoElement.TRANSLATE_YZ, axis_y, axis_z),
        ]:
            color = self._get_plane_color(plane, element)
            # Quad corners
            p0 = origin + a1 * off + a2 * off
            p1 = origin + a1 * (off + sz) + a2 * off
            p2 = origin + a1 * (off + sz) + a2 * (off + sz)
            p3 = origin + a1 * off + a2 * (off + sz)
            self._renderer.quad(p0, p1, p2, p3, color)

        self._renderer.flush(
            graphics=graphics,
            view_matrix=view_matrix,
            proj_matrix=proj_matrix,
            depth_test=True,
            blend=True,  # Transparent pass
        )

        # Restore default state
        graphics.set_blend(False)

    # ============================================================
    # Raycast picking
    # ============================================================

    def pick(self, ray_origin: np.ndarray, ray_direction: np.ndarray) -> GizmoElement:
        """
        Pick gizmo element using ray intersection.

        Args:
            ray_origin: Ray origin in world space
            ray_direction: Normalized ray direction

        Returns:
            GizmoElement that was hit, or NONE
        """
        if not self.visible or self.target is None:
            return GizmoElement.NONE

        ray_origin = np.asarray(ray_origin, dtype=np.float32)
        ray_direction = np.asarray(ray_direction, dtype=np.float32)

        best_t = float("inf")
        best_element = GizmoElement.NONE

        center = self._get_position()

        # Test translation arrows (as cylinders + cones)
        for axis, element in [
            ("x", GizmoElement.TRANSLATE_X),
            ("y", GizmoElement.TRANSLATE_Y),
            ("z", GizmoElement.TRANSLATE_Z),
        ]:
            axis_dir = self._get_world_axis(axis)
            shaft_end = center + axis_dir * (self.arrow_length * (1 - self.head_length_ratio))
            tip = center + axis_dir * self.arrow_length

            # Test shaft cylinder
            t = self._ray_cylinder_intersect(
                ray_origin, ray_direction,
                center, shaft_end,
                self.shaft_radius + self.pick_tolerance
            )
            if t is not None and t < best_t:
                best_t = t
                best_element = element

            # Test head cone (approximate as cylinder for simplicity)
            t = self._ray_cylinder_intersect(
                ray_origin, ray_direction,
                shaft_end, tip,
                self.head_radius + self.pick_tolerance
            )
            if t is not None and t < best_t:
                best_t = t
                best_element = element

        # Test rotation rings (as tori)
        for axis, element in [
            ("x", GizmoElement.ROTATE_X),
            ("y", GizmoElement.ROTATE_Y),
            ("z", GizmoElement.ROTATE_Z),
        ]:
            ring_axis = self._get_world_axis(axis)
            t = self._ray_torus_intersect(
                ray_origin, ray_direction,
                center, ring_axis,
                self.ring_major_radius,
                self.ring_minor_radius + self.pick_tolerance
            )
            if t is not None and t < best_t:
                best_t = t
                best_element = element

        # Test plane handles (quads)
        axis_x = self._get_world_axis("x")
        axis_y = self._get_world_axis("y")
        axis_z = self._get_world_axis("z")
        off = self.plane_offset
        sz = self.plane_size

        for plane, element, a1, a2, normal in [
            ("xy", GizmoElement.TRANSLATE_XY, axis_x, axis_y, axis_z),
            ("xz", GizmoElement.TRANSLATE_XZ, axis_z, axis_x, axis_y),  # Swapped to fix winding
            ("yz", GizmoElement.TRANSLATE_YZ, axis_y, axis_z, axis_x),
        ]:
            # Quad corners
            p0 = center + a1 * off + a2 * off
            p1 = center + a1 * (off + sz) + a2 * off
            p2 = center + a1 * (off + sz) + a2 * (off + sz)
            p3 = center + a1 * off + a2 * (off + sz)

            t = self._ray_quad_intersect(ray_origin, ray_direction, p0, p1, p2, p3, normal)
            if t is not None and t < best_t:
                best_t = t
                best_element = element

        return best_element

    def _ray_cylinder_intersect(
        self,
        ray_origin: np.ndarray,
        ray_dir: np.ndarray,
        cyl_start: np.ndarray,
        cyl_end: np.ndarray,
        radius: float,
    ) -> float | None:
        """
        Ray-cylinder intersection.

        Returns distance t along ray, or None if no hit.
        """
        cyl_axis = cyl_end - cyl_start
        cyl_length = np.linalg.norm(cyl_axis)
        if cyl_length < 1e-6:
            return None
        cyl_axis = cyl_axis / cyl_length

        # Vector from cylinder start to ray origin
        delta = ray_origin - cyl_start

        # Project out the cylinder axis component
        # d_perp = ray_dir - (ray_dir . cyl_axis) * cyl_axis
        ray_dot_axis = np.dot(ray_dir, cyl_axis)
        delta_dot_axis = np.dot(delta, cyl_axis)

        d_perp = ray_dir - ray_dot_axis * cyl_axis
        delta_perp = delta - delta_dot_axis * cyl_axis

        a = np.dot(d_perp, d_perp)
        b = 2.0 * np.dot(d_perp, delta_perp)
        c = np.dot(delta_perp, delta_perp) - radius * radius

        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return None

        if a < 1e-10:
            # Ray parallel to cylinder axis
            if c <= 0:
                # Ray inside cylinder
                return 0.0
            return None

        sqrt_disc = np.sqrt(discriminant)
        t1 = (-b - sqrt_disc) / (2 * a)
        t2 = (-b + sqrt_disc) / (2 * a)

        for t in [t1, t2]:
            if t < 0:
                continue
            # Check if hit point is within cylinder height
            hit_point = ray_origin + ray_dir * t
            proj = np.dot(hit_point - cyl_start, cyl_axis)
            if 0 <= proj <= cyl_length:
                return t

        return None

    def _ray_torus_intersect(
        self,
        ray_origin: np.ndarray,
        ray_dir: np.ndarray,
        torus_center: np.ndarray,
        torus_axis: np.ndarray,
        major_radius: float,
        minor_radius: float,
    ) -> float | None:
        """
        Approximate ray-torus intersection by sampling points on the torus.

        Full quartic solution is complex, so we use a simplified approach:
        test intersection with the torus as a thick circle (annulus).
        """
        # Transform ray to torus local space
        # Z-axis aligned with torus axis
        tangent, bitangent = self._renderer._build_basis(torus_axis)

        # Local space transform
        to_local = np.array([tangent, bitangent, torus_axis], dtype=np.float32)

        local_origin = to_local @ (ray_origin - torus_center)
        local_dir = to_local @ ray_dir

        # Intersect with the plane z=0 (the plane of the torus)
        if abs(local_dir[2]) < 1e-6:
            # Ray parallel to torus plane
            if abs(local_origin[2]) > minor_radius:
                return None
            # Ray in plane - would need more complex logic
            return None

        t_plane = -local_origin[2] / local_dir[2]
        if t_plane < 0:
            return None

        hit_local = local_origin + local_dir * t_plane
        # Distance from torus center axis in the plane
        dist_from_center = np.sqrt(hit_local[0]**2 + hit_local[1]**2)

        # Check if within torus ring
        if abs(dist_from_center - major_radius) <= minor_radius:
            return t_plane

        # Also check a small height range for the minor radius
        for dz in [-minor_radius * 0.5, minor_radius * 0.5]:
            if abs(local_dir[2]) < 1e-6:
                continue
            t_off = -(local_origin[2] - dz) / local_dir[2]
            if t_off < 0:
                continue
            hit = local_origin + local_dir * t_off
            dist = np.sqrt(hit[0]**2 + hit[1]**2)
            if abs(dist - major_radius) <= minor_radius:
                return t_off

        return None

    def _ray_quad_intersect(
        self,
        ray_origin: np.ndarray,
        ray_dir: np.ndarray,
        p0: np.ndarray,
        p1: np.ndarray,
        p2: np.ndarray,
        p3: np.ndarray,
        normal: np.ndarray,
    ) -> float | None:
        """
        Ray-quad intersection.

        Tests if ray hits the quad defined by p0, p1, p2, p3.
        Returns distance t along ray, or None if no hit.
        """
        # Intersect ray with plane
        denom = np.dot(ray_dir, normal)
        if abs(denom) < 1e-6:
            return None

        t = np.dot(p0 - ray_origin, normal) / denom
        if t < 0:
            return None

        # Hit point on plane
        hit = ray_origin + ray_dir * t

        # Check if hit point is inside quad using cross products
        # All cross products should point in the same direction as normal
        def same_side(edge_start, edge_end, point, n):
            edge = edge_end - edge_start
            to_point = point - edge_start
            cross = np.cross(edge, to_point)
            return np.dot(cross, n) >= 0

        if (same_side(p0, p1, hit, normal) and
            same_side(p1, p2, hit, normal) and
            same_side(p2, p3, hit, normal) and
            same_side(p3, p0, hit, normal)):
            return t

        return None

    # ============================================================
    # Utility
    # ============================================================

    def get_axis_for_element(self, element: GizmoElement) -> str | None:
        """Get axis name ('x', 'y', 'z') for a gizmo element."""
        axis_map = {
            GizmoElement.TRANSLATE_X: "x",
            GizmoElement.TRANSLATE_Y: "y",
            GizmoElement.TRANSLATE_Z: "z",
            GizmoElement.ROTATE_X: "x",
            GizmoElement.ROTATE_Y: "y",
            GizmoElement.ROTATE_Z: "z",
        }
        return axis_map.get(element)

    def is_translate_element(self, element: GizmoElement) -> bool:
        """Check if element is a translation arrow (single axis)."""
        return element in (GizmoElement.TRANSLATE_X, GizmoElement.TRANSLATE_Y, GizmoElement.TRANSLATE_Z)

    def is_plane_translate_element(self, element: GizmoElement) -> bool:
        """Check if element is a plane translation handle."""
        return element in (GizmoElement.TRANSLATE_XY, GizmoElement.TRANSLATE_XZ, GizmoElement.TRANSLATE_YZ)

    def is_rotate_element(self, element: GizmoElement) -> bool:
        """Check if element is a rotation ring."""
        return element in (GizmoElement.ROTATE_X, GizmoElement.ROTATE_Y, GizmoElement.ROTATE_Z)

    def get_world_axis_direction(self, element: GizmoElement) -> np.ndarray | None:
        """Get world-space axis direction for an element."""
        axis = self.get_axis_for_element(element)
        if axis is None:
            return None
        return self._get_world_axis(axis)

    def get_plane_axes(self, element: GizmoElement) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        """Get world-space axes for a plane element (axis1, axis2, normal)."""
        if element == GizmoElement.TRANSLATE_XY:
            return self._get_world_axis("x"), self._get_world_axis("y"), self._get_world_axis("z")
        elif element == GizmoElement.TRANSLATE_XZ:
            return self._get_world_axis("x"), self._get_world_axis("z"), self._get_world_axis("y")
        elif element == GizmoElement.TRANSLATE_YZ:
            return self._get_world_axis("y"), self._get_world_axis("z"), self._get_world_axis("x")
        return None


# ============================================================
# Controller
# ============================================================

class ImmediateGizmoController:
    """
    Controller for immediate mode gizmo.

    Uses raycast picking instead of ID buffer.
    """

    def __init__(
        self,
        scene,
        editor_entities=None,
        undo_handler=None,
        size: float = 1.5,
    ):
        self.scene = scene
        self.editor_entities = editor_entities
        self._undo_handler = undo_handler

        # Create immediate gizmo renderer
        self.gizmo_renderer = ImmediateGizmoRenderer(size=size)

        # Target entity
        self.target: "Entity | None" = None

        # Dragging state
        self.dragging: bool = False
        self.drag_mode: str | None = None  # "move" or "rotate"
        self.active_axis: str | None = None

        # Transform state for undo
        self._drag_transform = None
        self._start_pose = None

        # Translation drag state
        self.axis_vec: np.ndarray | None = None
        self.axis_point: np.ndarray | None = None
        self.grab_offset: np.ndarray | None = None
        self.start_target_pos: np.ndarray | None = None

        # Rotation drag state
        self.start_target_ang: np.ndarray | None = None
        self.rot_axis: np.ndarray | None = None
        self.rot_plane_origin: np.ndarray | None = None
        self.rot_vec0: np.ndarray | None = None

        # Plane drag state
        self.plane_normal: np.ndarray | None = None
        self.plane_origin: np.ndarray | None = None
        self.plane_grab_offset: np.ndarray | None = None

        # Callbacks
        self._on_transform_dragging: "Callable[[], None] | None" = None

    def set_undo_command_handler(self, handler):
        """Register undo command handler."""
        self._undo_handler = handler

    def set_on_transform_dragging(self, callback):
        """Register callback for transform dragging."""
        self._on_transform_dragging = callback

    def set_target(self, target_entity, viewport=None) -> None:
        """Set target entity for gizmo."""
        if target_entity is not None and not target_entity.pickable:
            target_entity = None

        self._end_drag()
        self.target = target_entity
        self.gizmo_renderer.target = target_entity

        if self.target is None:
            self.gizmo_renderer.visible = False
            return

        self.gizmo_renderer.visible = True

        # Rescale gizmo once when target changes
        if viewport is not None:
            self.update_screen_scale(viewport)

    def set_visible(self, visible: bool) -> None:
        """Show or hide gizmo."""
        self.gizmo_renderer.visible = visible

    def is_dragging(self) -> bool:
        """Check if gizmo is in drag mode."""
        return self.dragging

    def recreate_gizmo(self, scene, editor_entities=None) -> None:
        """Recreate gizmo in new scene. Clears all references to old scene entities."""
        self.scene = scene
        self.editor_entities = editor_entities
        self._end_drag()
        # Clear target reference (entity from old scene)
        self.target = None
        self.gizmo_renderer.target = None
        self.gizmo_renderer.visible = False

    def helper_geometry_entities(self) -> list:
        """Return empty list - immediate gizmo has no entity geometry."""
        return []

    def update_screen_scale(self, viewport) -> None:
        """Update gizmo screen scale based on camera distance."""
        if viewport is None or viewport.camera is None or self.target is None:
            return
        camera = viewport.camera
        if camera.entity is None:
            return
        camera_pos = camera.entity.transform.global_pose().lin
        gizmo_pos = self.target.transform.global_pose().lin
        distance = np.linalg.norm(camera_pos - gizmo_pos)
        screen_scale = max(0.1, distance * 0.1)
        self.gizmo_renderer.set_screen_scale(screen_scale)

    # ============================================================
    # Picking (raycast-based)
    # ============================================================

    def handle_pick_press_with_ray(
        self,
        ray_origin: np.ndarray,
        ray_direction: np.ndarray,
        viewport,
        x: float,
        y: float,
    ) -> bool:
        """
        Handle pick press using ray intersection.

        Args:
            ray_origin: World-space ray origin
            ray_direction: Normalized ray direction
            viewport: Viewport for drag operations
            x, y: Screen coordinates for drag operations

        Returns:
            True if gizmo was hit and drag started
        """
        if not self.gizmo_renderer.visible or self.target is None:
            return False

        element = self.gizmo_renderer.pick(ray_origin, ray_direction)
        if element == GizmoElement.NONE:
            return False

        if self.gizmo_renderer.is_translate_element(element):
            axis = self.gizmo_renderer.get_axis_for_element(element)
            self._start_translate(axis, viewport, x, y)
            return True
        elif self.gizmo_renderer.is_plane_translate_element(element):
            self._start_plane_translate(element, viewport, x, y)
            return True
        elif self.gizmo_renderer.is_rotate_element(element):
            axis = self.gizmo_renderer.get_axis_for_element(element)
            self._start_rotate(axis, viewport, x, y)
            return True

        return False

    def handle_pick_press_with_color(
        self,
        x: float,
        y: float,
        viewport,
        picked_color,
    ) -> bool:
        """
        Legacy interface for compatibility with entity-based picking.

        For immediate gizmo, we use raycast instead. This method generates
        a ray from screen coordinates and calls handle_pick_press_with_ray.
        """
        if not self.gizmo_renderer.visible or self.target is None:
            return False

        # Generate ray from screen coordinates
        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            return False

        return self.handle_pick_press_with_ray(
            ray.origin, ray.direction, viewport, x, y
        )

    def update_hover(self, ray_origin: np.ndarray, ray_direction: np.ndarray) -> None:
        """Update hover state based on ray."""
        if not self.gizmo_renderer.visible:
            self.gizmo_renderer.hovered_element = GizmoElement.NONE
            return

        element = self.gizmo_renderer.pick(ray_origin, ray_direction)
        self.gizmo_renderer.hovered_element = element

    # ============================================================
    # Drag operations
    # ============================================================

    def _start_translate(self, axis: str, viewport, x: float, y: float) -> None:
        """Start translation drag."""
        self.dragging = True
        self.drag_mode = "move"
        self.active_axis = axis
        self.gizmo_renderer.active_element = getattr(GizmoElement, f"TRANSLATE_{axis.upper()}")

        global_pose = self.target.transform.global_pose()
        self.start_target_pos = global_pose.lin.copy()

        self._drag_transform = self.target.transform
        # Store LOCAL pose for undo (not global!)
        self._start_pose = self.target.transform.local_pose().copy()

        self.axis_vec = self.gizmo_renderer._get_world_axis(axis)
        self.axis_point = self.start_target_pos.copy()

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            self._end_drag()
            return

        _, axis_hit_point = closest_point_on_axis_from_ray(
            axis_point=self.axis_point,
            axis_dir=self.axis_vec,
            ray_origin=ray.origin,
            ray_dir=ray.direction,
        )
        self.grab_offset = self.start_target_pos - axis_hit_point

    def _start_plane_translate(self, element: GizmoElement, viewport, x: float, y: float) -> None:
        """Start plane translation drag."""
        self.dragging = True
        self.drag_mode = "plane_move"
        self.gizmo_renderer.active_element = element

        global_pose = self.target.transform.global_pose()
        self.start_target_pos = global_pose.lin.copy()

        self._drag_transform = self.target.transform
        # Store LOCAL pose for undo (not global!)
        self._start_pose = self.target.transform.local_pose().copy()

        # Get plane axes and normal
        plane_axes = self.gizmo_renderer.get_plane_axes(element)
        if plane_axes is None:
            self._end_drag()
            return
        _, _, self.plane_normal = plane_axes
        self.plane_origin = self.start_target_pos.copy()

        # Find initial hit point on plane
        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            self._end_drag()
            return

        hit = self._ray_plane_hit(ray, self.plane_origin, self.plane_normal)
        if hit is None:
            self._end_drag()
            return

        self.plane_grab_offset = self.start_target_pos - hit

    def _start_rotate(self, axis: str, viewport, x: float, y: float) -> None:
        """Start rotation drag."""
        self.dragging = True
        self.drag_mode = "rotate"
        self.active_axis = axis
        self.gizmo_renderer.active_element = getattr(GizmoElement, f"ROTATE_{axis.upper()}")

        global_pose = self.target.transform.global_pose()
        self.start_target_pos = global_pose.lin.copy()
        self.start_target_ang = global_pose.ang.copy()

        self._drag_transform = self.target.transform
        # Store LOCAL pose for undo (not global!)
        self._start_pose = self.target.transform.local_pose().copy()

        self.rot_axis = self.gizmo_renderer._get_world_axis(axis)
        self.rot_plane_origin = self.start_target_pos.copy()

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            self._end_drag()
            return

        hit = self._ray_plane_intersection(ray, self.rot_plane_origin, self.rot_axis)
        if hit is None:
            self._end_drag()
            return

        v0 = hit - self.rot_plane_origin
        norm_v0 = np.linalg.norm(v0)
        if norm_v0 < 1e-6:
            # Hit center - use arbitrary vector in plane
            tmp = np.array([1.0, 0.0, 0.0], dtype=np.float32)
            if abs(np.dot(tmp, self.rot_axis)) > 0.9:
                tmp = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            v0 = tmp - self.rot_axis * np.dot(tmp, self.rot_axis)
            norm_v0 = np.linalg.norm(v0)
            if norm_v0 < 1e-6:
                self._end_drag()
                return
        self.rot_vec0 = v0 / norm_v0

    def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float) -> None:
        """Handle mouse move during drag."""
        if not self.dragging or self.target is None:
            return

        if self.drag_mode == "move":
            self._update_translate(viewport, x, y)
        elif self.drag_mode == "plane_move":
            self._update_plane_translate(viewport, x, y)
        elif self.drag_mode == "rotate":
            self._update_rotate(viewport, x, y)

    def on_mouse_button(self, viewport, button, action, mods) -> None:
        """Handle mouse button release."""
        if button != 0:
            return
        if action == 0:  # Release
            self._end_drag()

    def _update_translate(self, viewport, x: float, y: float) -> None:
        """Update translation during drag."""
        from termin.geombase import Pose3

        if self.axis_vec is None or self.axis_point is None or self.grab_offset is None:
            return

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            return

        _, axis_point_now = closest_point_on_axis_from_ray(
            axis_point=self.axis_point,
            axis_dir=self.axis_vec,
            ray_origin=ray.origin,
            ray_dir=ray.direction,
        )
        new_pos = axis_point_now + self.grab_offset

        old_pose = self.target.transform.global_pose()
        new_pose = Pose3(lin=new_pos, ang=old_pose.ang)
        self.target.transform.relocate_global(new_pose)

        if self._on_transform_dragging is not None:
            self._on_transform_dragging()

    def _update_plane_translate(self, viewport, x: float, y: float) -> None:
        """Update plane translation during drag."""
        from termin.geombase import Pose3

        if self.plane_normal is None or self.plane_origin is None or self.plane_grab_offset is None:
            return

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            return

        hit = self._ray_plane_hit(ray, self.plane_origin, self.plane_normal)
        if hit is None:
            return

        new_pos = hit + self.plane_grab_offset

        old_pose = self.target.transform.global_pose()
        new_pose = Pose3(lin=new_pos, ang=old_pose.ang)
        self.target.transform.relocate_global(new_pose)

        if self._on_transform_dragging is not None:
            self._on_transform_dragging()

    def _ray_plane_hit(self, ray, plane_origin: np.ndarray, plane_normal: np.ndarray) -> np.ndarray | None:
        """Intersect ray with plane, return hit point or None."""
        denom = np.dot(ray.direction, plane_normal)
        if abs(denom) < 1e-6:
            return None
        t = np.dot(plane_origin - ray.origin, plane_normal) / denom
        if t < 0:
            return None
        return ray.origin + ray.direction * t

    def _update_rotate(self, viewport, x: float, y: float) -> None:
        """Update rotation during drag."""
        from termin.geombase import Pose3
        from termin.util import qmul

        if (
            self.start_target_ang is None
            or self.rot_axis is None
            or self.rot_plane_origin is None
            or self.rot_vec0 is None
        ):
            return

        ray = viewport.screen_point_to_ray(x, y)
        if ray is None:
            return

        hit = self._ray_plane_intersection(ray, self.rot_plane_origin, self.rot_axis)
        if hit is None:
            return

        v1 = hit - self.rot_plane_origin
        norm_v1 = np.linalg.norm(v1)
        if norm_v1 < 1e-6:
            return
        v1 = v1 / norm_v1

        # Compute angle
        dot = float(np.clip(np.dot(self.rot_vec0, v1), -1.0, 1.0))
        cross = np.cross(self.rot_vec0, v1)
        sin_angle = np.linalg.norm(cross)
        cos_angle = dot
        sign = np.sign(np.dot(cross, self.rot_axis))
        if sign == 0.0:
            sign = 1.0

        angle = float(np.arctan2(sin_angle, cos_angle)) * sign

        # Build quaternion
        axis = self.rot_axis / np.linalg.norm(self.rot_axis)
        half = angle * 0.5
        s = np.sin(half)
        c = np.cos(half)
        dq = np.array([axis[0] * s, axis[1] * s, axis[2] * s, c], dtype=np.float32)

        new_ang = qmul(dq, self.start_target_ang)
        norm_q = np.linalg.norm(new_ang)
        if norm_q > 0.0:
            new_ang /= norm_q

        new_pose = Pose3(lin=self.start_target_pos, ang=new_ang)
        self.target.transform.relocate_global(new_pose)

        if self._on_transform_dragging is not None:
            self._on_transform_dragging()

    def _end_drag(self) -> None:
        """End drag and commit to undo."""
        if self.dragging:
            self._commit_drag_to_undo()

        self.dragging = False
        self.drag_mode = None
        self.active_axis = None
        self.gizmo_renderer.active_element = GizmoElement.NONE

        self.axis_vec = None
        self.axis_point = None
        self.grab_offset = None
        self.start_target_pos = None

        self.start_target_ang = None
        self.rot_axis = None
        self.rot_plane_origin = None
        self.rot_vec0 = None

        self.plane_normal = None
        self.plane_origin = None
        self.plane_grab_offset = None

        self._drag_transform = None
        self._start_pose = None

    def _commit_drag_to_undo(self) -> None:
        """Commit transform change to undo stack."""
        if self._undo_handler is None:
            return
        if self._drag_transform is None or self._start_pose is None:
            return

        from termin.editor.editor_commands import TransformEditCommand

        tf = self._drag_transform
        end_pose = tf.local_pose()

        # Check if anything changed (position, rotation, or scale)
        if (
            np.allclose(end_pose.lin, self._start_pose.lin)
            and np.allclose(end_pose.ang, self._start_pose.ang)
            and np.allclose(end_pose.scale, self._start_pose.scale)
        ):
            return

        # _start_pose is already a GeneralPose3 (from local_pose().copy())
        cmd = TransformEditCommand(
            transform=tf,
            old_pose=self._start_pose,
            new_pose=end_pose,
        )
        self._undo_handler(cmd, False)

    @staticmethod
    def _ray_plane_intersection(ray, plane_origin: np.ndarray, plane_normal: np.ndarray):
        """Ray-plane intersection."""
        n = np.asarray(plane_normal, dtype=np.float32)
        n_norm = np.linalg.norm(n)
        if n_norm == 0.0:
            return None
        n = n / n_norm

        ro = np.asarray(ray.origin, dtype=np.float32)
        rd = np.asarray(ray.direction, dtype=np.float32)

        denom = float(np.dot(rd, n))
        if abs(denom) < 1e-6:
            return None

        t = float(np.dot(plane_origin - ro, n) / denom)
        return ro + rd * t
