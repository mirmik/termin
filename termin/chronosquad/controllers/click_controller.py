"""ClickController - handles click input and issues movement commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.component import InputComponent
from termin.visualization.core.input_events import MouseButtonEvent
from termin.visualization.platform.backends.base import MouseButton, Action as InputAction
from termin.chronosquad.core import Vec3

from termin.chronosquad.controllers.object_controller import ObjectController
from termin.chronosquad.controllers.action.action_component import ClickInfo
from termin.chronosquad.controllers.action_server_component import ActionServerComponent

if TYPE_CHECKING:
    from termin.chronosquad.controllers.object_controller import ObjectController
    from termin.chronosquad.controllers.chronosphere_controller import ChronosphereController


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
        self._chronosphere_controller: ChronosphereController | None = None
        self._initialized = False
        self._selected_actor: ObjectController | None = None

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

        from .chronosphere_controller import ChronosphereController

        for entity in self._scene.entities:
            if self._chronosphere_controller is None:
                ctrl = entity.get_component(ChronosphereController)
                if ctrl is not None:
                    self._chronosphere_controller = ctrl
                    log.info(f"[ClickController] Found ChronosphereController on '{entity.name}'")

    def on_mouse_button(self, event: MouseButtonEvent) -> None:
        """Handle mouse button events."""
        try:
            # Only on left click press
            if event.button != MouseButton.LEFT or event.action != InputAction.PRESS:
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

            # Check if ActionServerComponent is charged - handle action click first
            server = ActionServerComponent.instance()
            if server is not None and server.is_charged():
                self._handle_action_click(hit, event, server)
                return

            hitted_entity = hit.entity
            layer = hitted_entity.layer

            layer_name = scene.get_layer_name(layer)

            if layer == 0:
                self.hit_ground(hit)

            elif layer_name == "Actor":
                self.hit_actor(hitted_entity, hit)

        except Exception as e:
            log.error(f"[ClickController] Error in on_mouse_button: {e}")

    def hit_actor(self, entity, hit) -> None:
        """Handle hit on actor layer."""
        log.info("[ClickController] Hit actor - no action taken")

        object_controller = None 

        for parent in entity.ancestors():
            object_controller = parent.get_component(ObjectController)
            if object_controller is not None and object_controller.selectable:
                break
            object_controller = None

        if object_controller is None:
            log.info("[ClickController] Hit actor has no ObjectController")
            return
        
        log.info(f"[ClickController] Selecting actor '{object_controller.entity.name}'")
        self._select_actor(object_controller)

    def _select_actor(self, object_controller: ObjectController) -> None:
        """Select the given actor."""
        if self._selected_actor is not None:
            log.info(f"[ClickController] Deselecting actor '{self._selected_actor.entity.name}'")
        self._selected_actor = object_controller
        log.info(f"[ClickController] Selected actor '{self._selected_actor.entity.name}'")

    def hit_ground(self, hit) -> None:        
        """Handle hit on ground layer."""
        # Convert hit point to Vec3 if needed
        point = hit.collider_point

        if not isinstance(point, Vec3):
            # numpy array or list
            point = Vec3(float(point[0]), float(point[1]), float(point[2]))

        # Move to hit point
        self.move_to(point)

    def move_to(self, target: Vec3) -> None:
        """
        Command the object to move to target position.
        """
        if self._selected_actor is None:
            log.warning("[ClickController] No actor selected to move")
            return

        chrono_obj = self._selected_actor.chrono_object
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

    def _handle_action_click(self, hit, event: MouseButtonEvent, server: ActionServerComponent) -> None:
        """
        Handle click when action is charged.

        Creates ClickInfo and passes to ActionServerComponent.
        """
        # Get world position from hit
        point = hit.collider_point
        if not isinstance(point, Vec3):
            point = Vec3(float(point[0]), float(point[1]), float(point[2]))

        # Get hit normal
        normal = hit.normal if hasattr(hit, 'normal') else Vec3(0, 0, 1)
        if not isinstance(normal, Vec3):
            normal = Vec3(float(normal[0]), float(normal[1]), float(normal[2]))

        # Create ClickInfo
        click_info = ClickInfo(
            world_position=point,
            screen_position=(event.x, event.y),
            target_object=None,  # TODO: get ObjectOfTimeline from entity
            hit_normal=normal,
            frame_name="",  # TODO: get frame name for ReferencedPoint
        )

        # Apply to action server component
        success = server.apply_click(click_info)
        if success:
            log.info("[ClickController] Action applied successfully")
        else:
            log.info("[ClickController] Action failed to apply")

    def on_key(self, event) -> None:
        """Handle key events."""
        if self._selected_actor is None:
            return
        
        ok = self._selected_actor.activate_action_with_shortcut(event.key)