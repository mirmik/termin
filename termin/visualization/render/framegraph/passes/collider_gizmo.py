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

        for comp in scene.colliders:
            if comp.entity is None or not comp.enabled:
                continue

            collider = comp._source_collider
            if collider is None:
                continue

            # Get world transform
            pose = comp.entity.transform.global_pose()

            if isinstance(collider, BoxCollider):
                self._draw_box(collider, pose, COLLIDER_COLOR)
            elif isinstance(collider, SphereCollider):
                self._draw_sphere(collider, pose, COLLIDER_COLOR)
            elif isinstance(collider, CapsuleCollider):
                self._draw_capsule(collider, pose, COLLIDER_COLOR)

    def _draw_box(self, collider, pose, color):
        """Draw wireframe box."""

        # Get local AABB corners
        center = collider.local_center
        hs = collider.half_size

        # 8 corners in local space
        corners_local = [
            np.array([center.x + dx * hs.x, center.y + dy * hs.y, center.z + dz * hs.z])
            for dx in [-1, 1] for dy in [-1, 1] for dz in [-1, 1]
        ]

        # Transform to world space (via collider's pose, then entity's pose)
        corners_world = []
        for c in corners_local:
            # First apply collider's local pose
            c_collider = collider.pose.transform_point(c)
            # Then apply entity's world pose
            c_world = pose.transform_point(c_collider)
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

    def _draw_sphere(self, collider, pose, color):
        """Draw wireframe sphere."""
        # Transform center to world space
        lc = collider.local_center
        center_local = np.array([lc.x, lc.y, lc.z])
        center_world = pose.transform_point(center_local)
        self._renderer.sphere_wireframe(center_world, collider.radius, color)

    def _draw_capsule(self, collider, pose, color):
        """Draw wireframe capsule."""
        # Transform endpoints to world space
        la, lb = collider.local_a, collider.local_b
        a_world = pose.transform_point(np.array([la.x, la.y, la.z]))
        b_world = pose.transform_point(np.array([lb.x, lb.y, lb.z]))
        self._renderer.capsule_wireframe(a_world, b_world, collider.radius, color)
