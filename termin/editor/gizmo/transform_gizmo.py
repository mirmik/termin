"""
TransformGizmo — standard translate/rotate gizmo for entity transforms.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, TYPE_CHECKING

import numpy as np

from termin.editor.gizmo.base import (
    Gizmo,
    GizmoCollider,
    AxisConstraint,
    PlaneConstraint,
    AngleConstraint,
    CylinderGeometry,
    TorusGeometry,
    QuadGeometry,
    _build_basis,
)

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
    from termin.visualization.render.immediate import ImmediateRenderer
    from termin.visualization.render.solid_primitives import SolidPrimitiveRenderer
    from termin.visualization.platform.backends.base import GraphicsBackend


class TransformElement(Enum):
    """Identifiers for transform gizmo parts."""
    TRANSLATE_X = auto()
    TRANSLATE_Y = auto()
    TRANSLATE_Z = auto()
    TRANSLATE_XY = auto()
    TRANSLATE_XZ = auto()
    TRANSLATE_YZ = auto()
    ROTATE_X = auto()
    ROTATE_Y = auto()
    ROTATE_Z = auto()


# Colors
AXIS_COLORS = {
    "x": (0.9, 0.2, 0.2, 1.0),  # Red
    "y": (0.2, 0.9, 0.2, 1.0),  # Green
    "z": (0.2, 0.2, 0.9, 1.0),  # Blue
}
# Plane colors: blend of the two axis colors
PLANE_COLORS = {
    "xy": (0.9, 0.9, 0.2, 1.0),  # Yellow (R+G)
    "xz": (0.9, 0.2, 0.9, 1.0),  # Magenta (R+B)
    "yz": (0.2, 0.9, 0.9, 1.0),  # Cyan (G+B)
}
HOVER_COLOR = (1.0, 0.7, 0.2, 1.0)  # Orange
ACTIVE_COLOR = (1.0, 1.0, 1.0, 1.0)  # White
PLANE_ALPHA = 0.3


class TransformGizmo(Gizmo):
    """
    Transform gizmo for translate and rotate operations.

    Supports:
    - Translation along X, Y, Z axes (arrows)
    - Translation in XY, XZ, YZ planes (quads)
    - Rotation around X, Y, Z axes (rings)
    """

    def __init__(
        self,
        size: float = 1.5,
        on_transform_changed: Callable[[], None] | None = None,
    ):
        self.visible = True
        self.size = size
        self._on_transform_changed = on_transform_changed

        # Target entity
        self._target: "Entity | None" = None
        self._target_position: np.ndarray = np.zeros(3, dtype=np.float32)

        # Screen scale (adjusted based on camera distance)
        self._screen_scale: float = 1.0

        # Orientation mode: "local" or "world"
        self._orientation_mode: str = "local"

        # Hover/active state
        self._hovered_element: TransformElement | None = None
        self._active_element: TransformElement | None = None

        # Geometry parameters (scaled)
        self._arrow_length = 1.0
        self._shaft_radius = 0.02
        self._head_radius = 0.06
        self._head_length_ratio = 0.2
        self._ring_major_radius = 0.75
        self._ring_minor_radius = 0.02
        self._plane_offset = 0.25
        self._plane_size = 0.2
        self._pick_tolerance = 0.03

        # Translation drag state
        self._grab_offset: np.ndarray | None = None
        self._drag_axis: np.ndarray | None = None  # Fixed axis direction during drag
        self._drag_center: np.ndarray | None = None  # Fixed center position during drag

        # Rotation drag state
        self._rot_start_angle: float = 0.0
        self._rot_start_quat: np.ndarray | None = None
        self._rot_vec0: np.ndarray | None = None  # Initial reference vector for rotation
        self._rot_axis: np.ndarray | None = None  # Fixed rotation axis during drag

        # Undo support
        self._drag_start_pose = None
        self._undo_handler: Callable | None = None

    @property
    def target(self) -> "Entity | None":
        return self._target

    @target.setter
    def target(self, entity: "Entity | None") -> None:
        self._target = entity
        if entity is not None:
            self._update_position()

    def set_screen_scale(self, scale: float) -> None:
        """Set screen scale factor."""
        self._screen_scale = scale

    def set_orientation_mode(self, mode: str) -> None:
        """Set orientation mode ('local' or 'world')."""
        self._orientation_mode = mode

    def set_undo_handler(self, handler: Callable) -> None:
        """Set undo command handler."""
        self._undo_handler = handler

    def _update_position(self) -> None:
        """Update cached position from target."""
        if self._target is not None:
            pose = self._target.transform.global_pose()
            self._target_position = np.array(pose.lin, dtype=np.float32)

    def _get_position(self) -> np.ndarray:
        """Get gizmo center position."""
        if self._target is not None:
            self._update_position()
        return self._target_position

    def _get_world_axis(self, axis: str) -> np.ndarray:
        """Get axis direction in world space."""
        base = {
            "x": np.array([1, 0, 0], dtype=np.float32),
            "y": np.array([0, 1, 0], dtype=np.float32),
            "z": np.array([0, 0, 1], dtype=np.float32),
        }[axis]

        if self._orientation_mode == "world" or self._target is None:
            return base

        # Local orientation: rotate by entity's rotation
        pose = self._target.transform.global_pose()
        quat = np.array(pose.ang, dtype=np.float32)
        return _quat_rotate(quat, base)

    def _get_color(self, axis: str, element: TransformElement) -> tuple:
        """Get color for axis, considering hover/active state."""
        if self._active_element == element:
            return ACTIVE_COLOR
        if self._hovered_element == element:
            return HOVER_COLOR
        return AXIS_COLORS[axis]

    def _get_plane_color(self, plane: str, element: TransformElement) -> tuple:
        """Get color for plane handle."""
        if self._active_element == element:
            r, g, b, _ = ACTIVE_COLOR
        elif self._hovered_element == element:
            r, g, b, _ = HOVER_COLOR
        else:
            r, g, b, _ = PLANE_COLORS[plane]
        return (r, g, b, PLANE_ALPHA)

    def _scaled(self, value: float) -> float:
        """Scale value by size and screen scale."""
        return value * self.size * self._screen_scale

    # ============================================================
    # Gizmo Interface
    # ============================================================

    @property
    def uses_solid_renderer(self) -> bool:
        """Use efficient SolidPrimitiveRenderer."""
        return True

    def draw_solid(
        self,
        renderer: "SolidPrimitiveRenderer",
        graphics: "GraphicsBackend",
        view: np.ndarray,
        proj: np.ndarray,
    ) -> None:
        """Draw opaque gizmo geometry using efficient GPU meshes."""
        if not self.visible or self._target is None:
            return

        origin = self._get_position()

        # Draw translation arrows
        for axis, element in [
            ("x", TransformElement.TRANSLATE_X),
            ("y", TransformElement.TRANSLATE_Y),
            ("z", TransformElement.TRANSLATE_Z),
        ]:
            axis_dir = self._get_world_axis(axis)
            color = self._get_color(axis, element)
            renderer.draw_arrow(
                origin=origin,
                direction=axis_dir,
                length=self._scaled(self._arrow_length),
                color=color,
                shaft_radius=self._scaled(self._shaft_radius),
                head_radius=self._scaled(self._head_radius),
                head_length_ratio=self._head_length_ratio,
            )

        # Draw rotation rings
        for axis, element in [
            ("x", TransformElement.ROTATE_X),
            ("y", TransformElement.ROTATE_Y),
            ("z", TransformElement.ROTATE_Z),
        ]:
            ring_axis = self._get_world_axis(axis)
            color = self._get_color(axis, element)

            # Build model matrix for torus
            # Unit torus has axis=Z, major_radius=1
            # We need to rotate it so Z aligns with ring_axis
            rot = _rotation_align_z_to(ring_axis)
            scale = self._scaled(self._ring_major_radius)
            model = _compose_trs(origin, rot, scale)
            renderer.draw_torus(model, color)

    def draw_transparent_solid(
        self,
        renderer: "SolidPrimitiveRenderer",
        graphics: "GraphicsBackend",
        view: np.ndarray,
        proj: np.ndarray,
    ) -> None:
        """Draw transparent gizmo geometry using efficient GPU meshes."""
        if not self.visible or self._target is None:
            return

        origin = self._get_position()

        axis_x = self._get_world_axis("x")
        axis_y = self._get_world_axis("y")
        axis_z = self._get_world_axis("z")
        off = self._scaled(self._plane_offset)
        sz = self._scaled(self._plane_size)

        for plane, element, a1, a2 in [
            ("xy", TransformElement.TRANSLATE_XY, axis_x, axis_y),
            ("xz", TransformElement.TRANSLATE_XZ, axis_z, axis_x),
            ("yz", TransformElement.TRANSLATE_YZ, axis_y, axis_z),
        ]:
            color = self._get_plane_color(plane, element)
            # Unit quad is from (0,0,0) to (1,1,0) in XY plane
            # We need to position it at origin + offset and scale by sz
            p0 = origin + a1 * off + a2 * off

            # Build rotation: X -> a1, Y -> a2
            rot = np.column_stack([a1, a2, np.cross(a1, a2)]).astype(np.float32)
            model = _compose_trs(p0, rot, sz)
            renderer.draw_quad(model, color)

    def draw(self, renderer: "ImmediateRenderer") -> None:
        """Legacy draw method - not used when uses_solid_renderer=True."""
        pass

    def draw_transparent(self, renderer: "ImmediateRenderer") -> None:
        """Legacy draw method - not used when uses_solid_renderer=True."""
        pass

    def get_colliders(self) -> list[GizmoCollider]:
        """Get colliders for all gizmo elements."""
        if not self.visible or self._target is None:
            return []

        colliders = []
        origin = self._get_position()
        tol = self._scaled(self._pick_tolerance)

        # Translation arrows (cylinders)
        for axis, element in [
            ("x", TransformElement.TRANSLATE_X),
            ("y", TransformElement.TRANSLATE_Y),
            ("z", TransformElement.TRANSLATE_Z),
        ]:
            axis_dir = self._get_world_axis(axis)
            arrow_len = self._scaled(self._arrow_length)
            shaft_end = origin + axis_dir * (arrow_len * (1 - self._head_length_ratio))
            tip = origin + axis_dir * arrow_len

            # Shaft
            colliders.append(GizmoCollider(
                id=element,
                geometry=CylinderGeometry(
                    start=origin.copy(),
                    end=shaft_end,
                    radius=self._scaled(self._shaft_radius) + tol,
                ),
                constraint=AxisConstraint(origin=origin.copy(), axis=axis_dir.copy()),
            ))
            # Head
            colliders.append(GizmoCollider(
                id=element,
                geometry=CylinderGeometry(
                    start=shaft_end,
                    end=tip,
                    radius=self._scaled(self._head_radius) + tol,
                ),
                constraint=AxisConstraint(origin=origin.copy(), axis=axis_dir.copy()),
            ))

        # Rotation rings (tori)
        for axis, element in [
            ("x", TransformElement.ROTATE_X),
            ("y", TransformElement.ROTATE_Y),
            ("z", TransformElement.ROTATE_Z),
        ]:
            ring_axis = self._get_world_axis(axis)
            colliders.append(GizmoCollider(
                id=element,
                geometry=TorusGeometry(
                    center=origin.copy(),
                    axis=ring_axis.copy(),
                    major_radius=self._scaled(self._ring_major_radius),
                    minor_radius=self._scaled(self._ring_minor_radius) + tol,
                ),
                constraint=AngleConstraint(center=origin.copy(), axis=ring_axis.copy()),
            ))

        # Plane handles (quads)
        axis_x = self._get_world_axis("x")
        axis_y = self._get_world_axis("y")
        axis_z = self._get_world_axis("z")
        off = self._scaled(self._plane_offset)
        sz = self._scaled(self._plane_size)

        for plane, element, a1, a2, normal in [
            ("xy", TransformElement.TRANSLATE_XY, axis_x, axis_y, axis_z),
            ("xz", TransformElement.TRANSLATE_XZ, axis_z, axis_x, axis_y),  # swapped to get +Y normal
            ("yz", TransformElement.TRANSLATE_YZ, axis_y, axis_z, axis_x),
        ]:
            p0 = origin + a1 * off + a2 * off
            p1 = origin + a1 * (off + sz) + a2 * off
            p2 = origin + a1 * (off + sz) + a2 * (off + sz)
            p3 = origin + a1 * off + a2 * (off + sz)

            colliders.append(GizmoCollider(
                id=element,
                geometry=QuadGeometry(
                    p0=p0, p1=p1, p2=p2, p3=p3,
                    normal=normal.copy(),
                ),
                constraint=PlaneConstraint(origin=origin.copy(), normal=normal.copy()),
            ))

        return colliders

    def on_hover_enter(self, collider_id) -> None:
        if isinstance(collider_id, TransformElement):
            self._hovered_element = collider_id

    def on_hover_exit(self, collider_id) -> None:
        if self._hovered_element == collider_id:
            self._hovered_element = None

    def on_click(self, collider_id, hit_position: np.ndarray | None) -> None:
        if not isinstance(collider_id, TransformElement):
            return

        self._active_element = collider_id

        # Save start pose for undo
        if self._target is not None:
            self._drag_start_pose = self._target.transform.local_pose().copy()

        origin = self._get_position()

        # Save fixed center position for all drag types
        self._drag_center = origin.copy()

        # For translation, compute grab offset and save fixed axis
        if self._is_translate_element(collider_id):
            axis = self._get_axis_for_element(collider_id)
            self._drag_axis = self._get_world_axis(axis).copy()
            if hit_position is not None:
                self._grab_offset = origin - hit_position
            else:
                self._grab_offset = np.zeros(3, dtype=np.float32)

        # For plane translation
        if self._is_plane_element(collider_id):
            if hit_position is not None:
                self._grab_offset = origin - hit_position
            else:
                self._grab_offset = np.zeros(3, dtype=np.float32)

        # For rotation, save initial rotation state, axis, and reference vector
        if self._is_rotate_element(collider_id):
            if self._target is not None:
                pose = self._target.transform.global_pose()
                self._rot_start_quat = np.array(pose.ang, dtype=np.float32)
            self._rot_start_angle = 0.0

            # Save fixed rotation axis
            axis = self._get_axis_for_element(collider_id)
            axis_dir = self._get_world_axis(axis)
            self._rot_axis = axis_dir.copy()

            # Compute initial reference vector (rot_vec0)
            if hit_position is not None:
                v0 = hit_position - origin
                # Project onto plane perpendicular to rotation axis
                v0 = v0 - axis_dir * np.dot(v0, axis_dir)
                norm_v0 = np.linalg.norm(v0)

                if norm_v0 > 1e-6:
                    self._rot_vec0 = v0 / norm_v0
                else:
                    # Hit center - use arbitrary vector in plane
                    tangent, _ = _build_basis(axis_dir)
                    self._rot_vec0 = tangent.copy()
            else:
                self._rot_vec0 = None

    def on_drag(self, collider_id, position: np.ndarray, delta: np.ndarray) -> None:
        if self._target is None:
            return

        if not isinstance(collider_id, TransformElement):
            return

        if self._is_translate_element(collider_id) or self._is_plane_element(collider_id):
            self._apply_translation(position)
        elif self._is_rotate_element(collider_id):
            self._apply_rotation(collider_id, position)

        if self._on_transform_changed is not None:
            self._on_transform_changed()

    def on_release(self, collider_id) -> None:
        self._active_element = None
        self._commit_undo()
        self._drag_start_pose = None
        self._grab_offset = None
        self._drag_axis = None
        self._drag_center = None
        self._rot_start_quat = None
        self._rot_vec0 = None
        self._rot_axis = None

    # ============================================================
    # Transform Application
    # ============================================================

    def _apply_translation(self, projected_position: np.ndarray) -> None:
        """Apply translation to target entity."""
        from termin.geombase import Pose3

        # Apply grab offset to get actual position
        if self._grab_offset is not None:
            new_position = projected_position + self._grab_offset
        else:
            new_position = projected_position

        old_pose = self._target.transform.global_pose()
        new_pose = Pose3(lin=new_position, ang=old_pose.ang)

        self._target.transform.relocate_global(new_pose)

    def _apply_rotation(self, element: TransformElement, plane_hit: np.ndarray) -> None:
        """Apply rotation to target entity."""
        from termin.geombase import Pose3

        if self._rot_start_quat is None or self._rot_vec0 is None or self._rot_axis is None:
            return

        # Use fixed center and axis saved at drag start (not current values!)
        origin = self._drag_center if self._drag_center is not None else self._get_position()
        axis_dir = self._rot_axis

        # Compute current vector from center to hit point
        v1 = plane_hit - origin
        # Project onto plane perpendicular to axis
        v1 = v1 - axis_dir * np.dot(v1, axis_dir)
        norm_v1 = np.linalg.norm(v1)
        if norm_v1 < 1e-6:
            return
        v1 = v1 / norm_v1

        # Compute angle between initial reference vector and current vector
        dot = float(np.clip(np.dot(self._rot_vec0, v1), -1.0, 1.0))
        cross = np.cross(self._rot_vec0, v1)
        sin_angle = np.linalg.norm(cross)
        sign = np.sign(np.dot(cross, axis_dir))
        if sign == 0.0:
            sign = 1.0

        angle = float(np.arctan2(sin_angle, dot)) * sign

        # Build rotation quaternion
        half = angle * 0.5
        s = np.sin(half)
        c = np.cos(half)
        dq = np.array([axis_dir[0] * s, axis_dir[1] * s, axis_dir[2] * s, c], dtype=np.float32)

        # Apply to start rotation
        new_quat = _quat_mul(dq, self._rot_start_quat)
        norm_q = np.linalg.norm(new_quat)
        if norm_q > 0.0:
            new_quat /= norm_q

        new_pose = Pose3(lin=origin, ang=new_quat)
        self._target.transform.relocate_global(new_pose)

    def _commit_undo(self) -> None:
        """Commit transform change to undo stack."""
        if self._undo_handler is None or self._target is None:
            return
        if self._drag_start_pose is None:
            return

        from termin.editor.editor_commands import TransformEditCommand

        tf = self._target.transform
        end_pose = tf.local_pose()

        # Check if anything changed
        if (
            np.allclose(end_pose.lin, self._drag_start_pose.lin) and
            np.allclose(end_pose.ang, self._drag_start_pose.ang) and
            np.allclose(end_pose.scale, self._drag_start_pose.scale)
        ):
            return

        cmd = TransformEditCommand(
            transform=tf,
            old_pose=self._drag_start_pose,
            new_pose=end_pose,
        )
        self._undo_handler(cmd, False)

    # ============================================================
    # Helpers
    # ============================================================

    @staticmethod
    def _is_translate_element(element: TransformElement) -> bool:
        return element in (
            TransformElement.TRANSLATE_X,
            TransformElement.TRANSLATE_Y,
            TransformElement.TRANSLATE_Z,
        )

    @staticmethod
    def _is_plane_element(element: TransformElement) -> bool:
        return element in (
            TransformElement.TRANSLATE_XY,
            TransformElement.TRANSLATE_XZ,
            TransformElement.TRANSLATE_YZ,
        )

    @staticmethod
    def _is_rotate_element(element: TransformElement) -> bool:
        return element in (
            TransformElement.ROTATE_X,
            TransformElement.ROTATE_Y,
            TransformElement.ROTATE_Z,
        )

    @staticmethod
    def _get_axis_for_element(element: TransformElement) -> str:
        axis_map = {
            TransformElement.TRANSLATE_X: "x",
            TransformElement.TRANSLATE_Y: "y",
            TransformElement.TRANSLATE_Z: "z",
            TransformElement.ROTATE_X: "x",
            TransformElement.ROTATE_Y: "y",
            TransformElement.ROTATE_Z: "z",
        }
        return axis_map.get(element, "x")


# ============================================================
# Quaternion Utilities
# ============================================================

def _quat_rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate vector by quaternion (x, y, z, w)."""
    qv = q[:3]
    qw = q[3]
    t = 2.0 * np.cross(qv, v)
    return v + qw * t + np.cross(qv, t)


def _quat_mul(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Multiply two quaternions (x, y, z, w)."""
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return np.array([
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
    ], dtype=np.float32)


# ============================================================
# Matrix Utilities for SolidPrimitiveRenderer
# ============================================================

def _rotation_align_z_to(target: np.ndarray) -> np.ndarray:
    """Build 3x3 rotation matrix that rotates Z axis to target direction."""
    target = np.asarray(target, dtype=np.float32)
    length = np.linalg.norm(target)
    if length < 1e-6:
        return np.eye(3, dtype=np.float32)

    z_new = target / length

    up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    if abs(np.dot(z_new, up)) > 0.99:
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    x_new = np.cross(up, z_new)
    x_new = x_new / np.linalg.norm(x_new)
    y_new = np.cross(z_new, x_new)

    return np.column_stack([x_new, y_new, z_new]).astype(np.float32)


def _compose_trs(translate: np.ndarray, rotate: np.ndarray, scale: float) -> np.ndarray:
    """Compose 4x4 TRS matrix from translation, 3x3 rotation, and uniform scale."""
    m = np.eye(4, dtype=np.float32)

    # Apply scale to rotation columns
    m[:3, 0] = rotate[:, 0] * scale
    m[:3, 1] = rotate[:, 1] * scale
    m[:3, 2] = rotate[:, 2] * scale

    # Translation
    m[0, 3] = translate[0]
    m[1, 3] = translate[1]
    m[2, 3] = translate[2]

    return m
