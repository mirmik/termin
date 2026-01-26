"""
ColliderGizmoPass - Renders collider wireframes for editor visualization.

Draws wireframe representations of all ColliderComponents in the scene.
Uses WireframeRenderer with pre-built unit meshes for efficiency.
"""

from __future__ import annotations

from typing import List, Set, Tuple, TYPE_CHECKING

import numpy as np

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.editor.inspect_field import InspectField
from termin.visualization.render.wireframe import (
    WireframeRenderer,
    mat4_translate,
    mat4_scale,
    mat4_scale_uniform,
    mat4_from_rotation_matrix,
    rotation_matrix_align_z_to_axis,
)
from termin.colliders import BoxCollider, SphereCollider, CapsuleCollider
from termin.geombase import Vec3

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.visualization.render.framebuffer import FramebufferHandle
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


# Collider wireframe color (green)
COLLIDER_COLOR = (0.2, 0.9, 0.2, 1.0)


class ColliderGizmoPass(RenderFramePass):
    """
    Framegraph pass that renders collider wireframes.

    Iterates over scene.colliders and draws wireframe representation
    for each collider type (Box, Sphere, Capsule).
    """

    category = "Debug"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("input_res", "output_res")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
    }

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "ColliderGizmo",
        passthrough: bool = False,
    ):
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.output_res = output_res
        self.passthrough = passthrough
        self._renderer = WireframeRenderer()

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        return [(self.input_res, self.output_res)]

    def execute(self, ctx: "ExecuteContext") -> None:
        if self.passthrough:
            return

        if ctx.scene is None or not ctx.scene.colliders:
            return

        px, py, pw, ph = ctx.rect

        fb = ctx.writes_fbos.get(self.output_res)
        if fb is None:
            from termin._native import log
            log.warn(f"[ColliderGizmoPass] output '{self.output_res}' is None, skipping")
            return

        # Check type - must be FramebufferHandle
        from termin.graphics import FramebufferHandle
        if not isinstance(fb, FramebufferHandle):
            from termin._native import log
            log.warn(f"[ColliderGizmoPass] output '{self.output_res}' is {type(fb).__name__}, not FramebufferHandle, skipping")
            return

        ctx.graphics.bind_framebuffer(fb)
        ctx.graphics.set_viewport(0, 0, pw, ph)

        view = ctx.camera.get_view_matrix().to_numpy_f32()
        proj = ctx.camera.get_projection_matrix().to_numpy_f32()

        self._renderer.begin(ctx.graphics, view, proj, depth_test=False)
        self._draw_colliders(ctx.scene)
        self._renderer.end()

    def _draw_colliders(self, scene):
        """Draw wireframes for all colliders in the scene."""
        for comp in scene.colliders:
            if comp.entity is None or not comp.enabled:
                continue

            collider = comp._source_collider
            if collider is None:
                continue

            # Get world transform from entity
            entity_pose = comp.entity.transform.global_pose()

            if isinstance(collider, BoxCollider):
                self._draw_box(collider, entity_pose)
            elif isinstance(collider, SphereCollider):
                self._draw_sphere(collider, entity_pose)
            elif isinstance(collider, CapsuleCollider):
                self._draw_capsule(collider, entity_pose)

    def _draw_box(self, collider, entity_pose):
        """Draw wireframe box using unit box mesh."""
        # Get effective half-size (includes scale from collider.transform)
        hs = collider.effective_half_size()

        # Collider's local transform
        ct = collider.transform

        # Build model matrix: entity_pose * collider_transform * scale(2*half_size)
        # Unit box is -0.5 to +0.5, so we scale by full size (2 * half_size)

        # Collider rotation as 3x3 matrix
        collider_rot = _quat_to_matrix3(ct.ang)

        # Entity pose as 4x4 matrix
        entity_mat = _pose_to_matrix4(entity_pose)

        # Collider local transform (rotation + translation, scale is in effective_half_size)
        collider_translate = mat4_translate(ct.lin.x, ct.lin.y, ct.lin.z)
        collider_rotate = mat4_from_rotation_matrix(collider_rot)

        # Scale by box size (2 * half_size because unit box is -0.5 to +0.5)
        scale = mat4_scale(2.0 * hs.x, 2.0 * hs.y, 2.0 * hs.z)

        # Compose: entity * collider_translate * collider_rotate * scale
        local_transform = collider_translate @ collider_rotate @ scale
        model = entity_mat @ local_transform

        self._renderer.draw_box(model, COLLIDER_COLOR)

    def _draw_sphere(self, collider, entity_pose):
        """Draw wireframe sphere using 3 orthogonal circles."""
        # Get effective radius
        radius = collider.effective_radius()

        # Collider center in local space
        ct = collider.transform
        center_local = np.array([ct.lin.x, ct.lin.y, ct.lin.z], dtype=np.float32)

        # Transform center to world space (convert Vec3 to numpy)
        cw = entity_pose.transform_point(center_local)
        center_world = np.array([cw.x, cw.y, cw.z], dtype=np.float32)

        # Scale radius by entity's uniform scale
        entity_scale = min(entity_pose.scale.x, entity_pose.scale.y, entity_pose.scale.z)
        world_radius = radius * entity_scale

        # Draw 3 orthogonal circles
        # XY plane (normal = Z)
        model_xy = mat4_translate(center_world[0], center_world[1], center_world[2]) @ mat4_scale_uniform(world_radius)
        self._renderer.draw_circle(model_xy, COLLIDER_COLOR)

        # XZ plane (normal = Y) - rotate unit circle from XY to XZ
        rot_xz = np.array([
            [1, 0, 0],
            [0, 0, -1],
            [0, 1, 0],
        ], dtype=np.float32)
        model_xz = mat4_translate(center_world[0], center_world[1], center_world[2]) @ mat4_from_rotation_matrix(rot_xz) @ mat4_scale_uniform(world_radius)
        self._renderer.draw_circle(model_xz, COLLIDER_COLOR)

        # YZ plane (normal = X) - rotate unit circle from XY to YZ
        rot_yz = np.array([
            [0, 0, 1],
            [0, 1, 0],
            [-1, 0, 0],
        ], dtype=np.float32)
        model_yz = mat4_translate(center_world[0], center_world[1], center_world[2]) @ mat4_from_rotation_matrix(rot_yz) @ mat4_scale_uniform(world_radius)
        self._renderer.draw_circle(model_yz, COLLIDER_COLOR)

    def _draw_capsule(self, collider, entity_pose):
        """Draw wireframe capsule: 2 circles + 4 lines + 4 arcs."""
        # Get effective dimensions
        half_height = collider.effective_half_height()
        radius = collider.effective_radius()

        # Collider's local transform
        ct = collider.transform
        center = np.array([ct.lin.x, ct.lin.y, ct.lin.z], dtype=np.float32)

        # Capsule axis in collider local space (default is Z)
        axis_local = _quat_rotate(ct.ang, Vec3(0.0, 0.0, 1.0))
        axis = np.array([axis_local.x, axis_local.y, axis_local.z], dtype=np.float32)

        # Endpoints in collider's local space
        a_local = center - axis * half_height
        b_local = center + axis * half_height

        # Transform to world space (convert Vec3 to numpy)
        a_vec = entity_pose.transform_point(a_local)
        b_vec = entity_pose.transform_point(b_local)
        a_world = np.array([a_vec.x, a_vec.y, a_vec.z], dtype=np.float32)
        b_world = np.array([b_vec.x, b_vec.y, b_vec.z], dtype=np.float32)

        # Scale radius by entity's uniform scale
        entity_scale = min(entity_pose.scale.x, entity_pose.scale.y, entity_pose.scale.z)
        world_radius = radius * entity_scale

        # Axis in world space
        axis_world = b_world - a_world
        axis_len = np.linalg.norm(axis_world)
        if axis_len > 1e-6:
            axis_world = axis_world / axis_len

        # Build orthonormal basis for capsule
        tangent, bitangent = _build_basis(axis_world)

        # Draw circles at endpoints (perpendicular to axis)
        # Unit circle is in XY plane, we need to rotate it so Z becomes axis_world
        rot_to_axis = rotation_matrix_align_z_to_axis(axis_world)

        model_a = mat4_translate(a_world[0], a_world[1], a_world[2]) @ mat4_from_rotation_matrix(rot_to_axis) @ mat4_scale_uniform(world_radius)
        model_b = mat4_translate(b_world[0], b_world[1], b_world[2]) @ mat4_from_rotation_matrix(rot_to_axis) @ mat4_scale_uniform(world_radius)

        self._renderer.draw_circle(model_a, COLLIDER_COLOR)
        self._renderer.draw_circle(model_b, COLLIDER_COLOR)

        # Draw 4 connecting lines
        for i in range(4):
            angle = np.pi * i / 2  # 0, 90, 180, 270 degrees
            offset = world_radius * (np.cos(angle) * tangent + np.sin(angle) * bitangent)
            start = a_world + offset
            end = b_world + offset

            # Line from start to end
            line_vec = end - start
            line_len = np.linalg.norm(line_vec)
            if line_len > 1e-6:
                line_rot = rotation_matrix_align_z_to_axis(line_vec)
                model_line = mat4_translate(start[0], start[1], start[2]) @ mat4_from_rotation_matrix(line_rot) @ mat4_scale(1, 1, line_len)
                self._renderer.draw_line(model_line, COLLIDER_COLOR)

        # Draw hemisphere arcs at each end
        # Arc is in XY plane from +X to -X via +Y
        # We need to orient it for each hemisphere

        for basis_vec, other_vec in [(tangent, bitangent), (bitangent, -tangent)]:
            # Arc at start (pointing away from end, i.e., -axis direction)
            # Rotate arc so: +X -> basis_vec, +Y -> -axis_world
            arc_rot_a = np.column_stack([basis_vec, -axis_world, other_vec]).astype(np.float32)
            model_arc_a = mat4_translate(a_world[0], a_world[1], a_world[2]) @ mat4_from_rotation_matrix(arc_rot_a) @ mat4_scale_uniform(world_radius)
            self._renderer.draw_arc(model_arc_a, COLLIDER_COLOR)

            # Arc at end (pointing away from start, i.e., +axis direction)
            arc_rot_b = np.column_stack([basis_vec, axis_world, -other_vec]).astype(np.float32)
            model_arc_b = mat4_translate(b_world[0], b_world[1], b_world[2]) @ mat4_from_rotation_matrix(arc_rot_b) @ mat4_scale_uniform(world_radius)
            self._renderer.draw_arc(model_arc_b, COLLIDER_COLOR)


# ============================================================
# Helper functions (module-level to avoid repeated imports)
# ============================================================

def _quat_to_matrix3(q) -> np.ndarray:
    """Convert quaternion to 3x3 rotation matrix."""
    # q is assumed to have x, y, z, w attributes
    x, y, z, w = q.x, q.y, q.z, q.w

    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z

    return np.array([
        [1 - 2*(yy + zz), 2*(xy - wz), 2*(xz + wy)],
        [2*(xy + wz), 1 - 2*(xx + zz), 2*(yz - wx)],
        [2*(xz - wy), 2*(yz + wx), 1 - 2*(xx + yy)],
    ], dtype=np.float32)


def _quat_rotate(q, v: Vec3) -> Vec3:
    """Rotate vector by quaternion."""
    return q.rotate(v)


def _pose_to_matrix4(pose) -> np.ndarray:
    """Convert Pose to 4x4 transformation matrix."""
    # Get rotation matrix
    rot = _quat_to_matrix3(pose.ang)

    # Apply scale to rotation
    scale = pose.scale
    rot[:, 0] *= scale.x
    rot[:, 1] *= scale.y
    rot[:, 2] *= scale.z

    # Build 4x4 matrix
    m = np.eye(4, dtype=np.float32)
    m[:3, :3] = rot
    m[0, 3] = pose.lin.x
    m[1, 3] = pose.lin.y
    m[2, 3] = pose.lin.z

    return m


def _build_basis(axis: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Build orthonormal basis from axis direction. Returns (tangent, bitangent)."""
    up = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    if abs(np.dot(axis, up)) > 0.99:
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    tangent = np.cross(axis, up)
    tangent = tangent / np.linalg.norm(tangent)
    bitangent = np.cross(axis, tangent)

    return tangent, bitangent
