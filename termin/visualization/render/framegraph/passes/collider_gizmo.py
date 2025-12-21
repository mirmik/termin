"""
ColliderGizmoPass - Renders collider wireframes for editor visualization.

Draws wireframe representations of all ColliderComponents in the scene.
"""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

import numpy as np

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.immediate import ImmediateRenderer

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.visualization.render.framebuffer import FramebufferHandle


# Collider wireframe color (green)
COLLIDER_COLOR = (0.2, 0.9, 0.2, 1.0)


class ColliderGizmoPass(RenderFramePass):
    """
    Framegraph pass that renders collider wireframes.

    Iterates over scene.colliders and draws wireframe representation
    for each collider type (Box, Sphere, Capsule).
    """

    def __init__(
        self,
        input_res: str = "color",
        output_res: str = "color",
        pass_name: str = "ColliderGizmo",
        enabled: bool = True,
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
        )
        self.input_res = input_res
        self.output_res = output_res
        self.enabled = enabled
        self._renderer = ImmediateRenderer()

    def _serialize_params(self) -> dict:
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
            "enabled": self.enabled,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "ColliderGizmoPass":
        return cls(
            input_res=data.get("input_res", "color"),
            output_res=data.get("output_res", "color"),
            pass_name=data.get("pass_name", "ColliderGizmo"),
            enabled=data.get("enabled", True),
        )

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        return [(self.input_res, self.output_res)]

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle | None"],
        writes_fbos: dict[str, "FramebufferHandle | None"],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        if not self.enabled:
            return

        if scene is None or not hasattr(scene, 'colliders') or not scene.colliders:
            return

        px, py, pw, ph = rect

        fb = writes_fbos.get(self.output_res)
        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()

        self._renderer.begin()
        self._draw_colliders(scene)
        self._renderer.flush(graphics, view, proj)

    def _draw_colliders(self, scene):
        """Draw wireframes for all colliders in the scene."""
        from termin.colliders import BoxCollider, SphereCollider, CapsuleCollider
        from termin.geombase import Vec3

        for comp in scene.colliders:
            if comp.entity is None or not comp.enabled:
                continue

            collider = comp._source_collider
            if collider is None:
                continue

            # Get world transform: entity_transform * collider.transform
            entity_pose = comp.entity.transform.global_pose()

            if isinstance(collider, BoxCollider):
                self._draw_box(collider, entity_pose, COLLIDER_COLOR)
            elif isinstance(collider, SphereCollider):
                self._draw_sphere(collider, entity_pose, COLLIDER_COLOR)
            elif isinstance(collider, CapsuleCollider):
                self._draw_capsule(collider, entity_pose, COLLIDER_COLOR)

    def _draw_box(self, collider, entity_pose, color):
        """Draw wireframe box."""
        # Get effective half-size (includes scale from collider.transform)
        hs = collider.effective_half_size()

        # Collider's local transform: center position + rotation + scale
        collider_transform = collider.transform

        # 8 corners in collider's local space (using scaled half-size)
        corners_local = [
            np.array([dx * hs.x, dy * hs.y, dz * hs.z])
            for dx in [-1, 1] for dy in [-1, 1] for dz in [-1, 1]
        ]

        # Transform to world space
        # 1. Apply collider's rotation and translation (scale already in effective_half_size)
        # 2. Apply entity's world pose (which includes entity scale)
        from termin.geombase import Vec3
        corners_world = []
        for c in corners_local:
            # Rotate by collider's orientation and add collider's center
            c_vec = Vec3(c[0], c[1], c[2])
            c_rotated = collider_transform.ang.rotate(c_vec)
            c_collider = np.array([
                c_rotated.x + collider_transform.lin.x,
                c_rotated.y + collider_transform.lin.y,
                c_rotated.z + collider_transform.lin.z
            ])
            # Apply entity's world pose
            c_world = entity_pose.transform_point(c_collider)
            corners_world.append(c_world)

        # Draw 12 edges
        # Bottom face: 0-1, 1-3, 3-2, 2-0
        # Top face: 4-5, 5-7, 7-6, 6-4
        # Vertical edges: 0-4, 1-5, 2-6, 3-7
        edges = [
            (0, 1), (1, 3), (3, 2), (2, 0),  # bottom (z=-1)
            (4, 5), (5, 7), (7, 6), (6, 4),  # top (z=+1)
            (0, 4), (1, 5), (2, 6), (3, 7),  # vertical
        ]

        for i, j in edges:
            self._renderer.line(corners_world[i], corners_world[j], color)

    def _draw_sphere(self, collider, entity_pose, color):
        """Draw wireframe sphere."""
        # Get effective radius (includes scale from collider.transform)
        radius = collider.effective_radius()

        # Collider center in local space
        collider_transform = collider.transform
        center_local = np.array([
            collider_transform.lin.x,
            collider_transform.lin.y,
            collider_transform.lin.z
        ])

        # Transform center to world space via entity pose
        center_world = entity_pose.transform_point(center_local)

        # Scale the radius by entity's uniform scale
        entity_scale = min(entity_pose.scale.x, entity_pose.scale.y, entity_pose.scale.z)
        world_radius = radius * entity_scale

        self._renderer.sphere_wireframe(center_world, world_radius, color)

    def _draw_capsule(self, collider, entity_pose, color):
        """Draw wireframe capsule."""
        from termin.geombase import Vec3
        # Get effective dimensions (includes scale from collider.transform)
        half_height = collider.effective_half_height()
        radius = collider.effective_radius()

        # Collider's local transform
        collider_transform = collider.transform
        center = collider_transform.lin
        axis_vec = collider_transform.ang.rotate(Vec3(0.0, 0.0, 1.0))
        axis = np.array([axis_vec.x, axis_vec.y, axis_vec.z])

        # Endpoints in collider's local space
        a_local = np.array([center.x, center.y, center.z]) - axis * half_height
        b_local = np.array([center.x, center.y, center.z]) + axis * half_height

        # Transform to world space via entity pose
        a_world = entity_pose.transform_point(a_local)
        b_world = entity_pose.transform_point(b_local)

        # Scale radius by entity's uniform scale (in the XY plane of the capsule)
        entity_scale = min(entity_pose.scale.x, entity_pose.scale.y, entity_pose.scale.z)
        world_radius = radius * entity_scale

        self._renderer.capsule_wireframe(a_world, b_world, world_radius, color)
