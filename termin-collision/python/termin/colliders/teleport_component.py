"""Teleport component owned by the collision package."""

from __future__ import annotations

from tcbase import Action, MouseButton
from termin.collision import CollisionWorld
from termin.input import InputComponent, MouseButtonEvent

__all__ = ["TeleportComponent"]


class TeleportComponent(InputComponent):
    """
    Teleport the owning entity to a clicked collider hit point.

    Left mouse press is raycast against the viewport scene. Hits on the owning
    entity are ignored.
    """

    def on_mouse_button(self, event: MouseButtonEvent):
        if event.button != MouseButton.LEFT or event.action != Action.PRESS:
            return

        if self.entity is None:
            return

        ray = event.viewport.screen_point_to_ray(event.x, event.y)
        if ray is None:
            return

        scene = event.viewport.scene
        hit = CollisionWorld.raycast_scene(scene, ray)
        if not hit.valid:
            return

        if hit.entity is self.entity:
            return

        from termin.geombase import Pose3

        old_pose = self.entity.transform.global_pose()
        new_pose = Pose3(lin=hit.collider_point, ang=old_pose.ang)
        self.entity.transform.relocate_global(new_pose)
