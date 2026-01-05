"""ClickController - handles click input and issues movement commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.component import InputComponent
from termin.visualization.core.input_events import MouseButtonEvent
from termin.visualization.platform.backends.base import MouseButton, Action
from termin.chronosquad.core import Vec3

if TYPE_CHECKING:
    from .object_controller import ObjectController
    from .chronosphere_controller import ChronosphereController


class ClickController(InputComponent):
    """
    Handles click input and commands object movement.

    On left click, raycasts to find world position and moves
    the object to that location.
    """

    def __init__(
        self,
        enabled: bool = True,
        move_speed: float = 5.0,
    ):
        super().__init__(enabled=enabled)
        self._move_speed = move_speed
        self._object_controller: ObjectController | None = None
        self._chronosphere_controller: ChronosphereController | None = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Find controllers if not yet initialized."""
        if self._initialized:
            return
        self._find_controllers()
        self._initialized = True

    def _find_controllers(self) -> None:
        """Find ObjectController and ChronosphereController in scene."""
        if self._scene is None:
            return

        from .object_controller import ObjectController
        from .chronosphere_controller import ChronosphereController

        for entity in self._scene.entities:
            if self._object_controller is None:
                ctrl = entity.get_component(ObjectController)
                if ctrl is not None:
                    self._object_controller = ctrl
                    log.info(f"[ClickController] Found ObjectController on '{entity.name}'")

            if self._chronosphere_controller is None:
                ctrl = entity.get_component(ChronosphereController)
                if ctrl is not None:
                    self._chronosphere_controller = ctrl
                    log.info(f"[ClickController] Found ChronosphereController on '{entity.name}'")

    def on_mouse_button(self, event: MouseButtonEvent) -> None:
        """Handle mouse button events."""
        try:
            # Only on left click press
            if event.button != MouseButton.LEFT or event.action != Action.PRESS:
                return

            self._ensure_initialized()

            # Get ray from cursor position
            ray = event.viewport.screen_point_to_ray(event.x, event.y)
            if ray is None:
                return

            # Raycast scene
            scene = event.viewport.scene
            hit = scene.raycast(ray)
            if hit is None:
                return

            # Convert hit point to Vec3 if needed
            point = hit.collider_point
            if not isinstance(point, Vec3):
                # numpy array or list
                point = Vec3(float(point[0]), float(point[1]), float(point[2]))

            # Move to hit point
            self.move_to(point)
        except Exception as e:
            log.error(f"[ClickController] Error in on_mouse_button: {e}")

    def move_to(self, target: Vec3) -> None:
        """
        Command the object to move to target position.
        """
        if self._object_controller is None:
            log.warning("[ClickController] No ObjectController found")
            return

        chrono_obj = self._object_controller.chrono_object
        if chrono_obj is None:
            log.warning("[ClickController] ObjectController has no chrono object")
            return

        current_pos = chrono_obj.local_position
        log.info(
            f"[ClickController] Moving '{chrono_obj.name}' from "
            f"({current_pos.x:.1f}, {current_pos.y:.1f}, {current_pos.z:.1f}) to "
            f"({target.x:.1f}, {target.y:.1f}, {target.z:.1f}) "
            f"at speed {self._move_speed}"
        )

        chrono_obj.move_to(target, self._move_speed)
