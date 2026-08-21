"""A tiny two-room game built around WorldController scene transitions."""

from __future__ import annotations

import os

from tcbase import Action, Key, log
from termin.engine import WorldController, require_world_context, world_context
from termin.geombase import Vec3
from termin.input import InputComponent
from termin.inspect import InspectField


_PREFIX = "[PortalWalk]"
_EXPECTED_FIRST_TRIP = ["Sunset Yard", "Blue Workshop", "Sunset Yard"]
_AUTOPLAY_ENV = "TERMIN_PORTAL_WALK_AUTOPLAY"


def _event(message: str) -> None:
    log.info(f"{_PREFIX} {message}")


class PortalWalkDirector(WorldController):
    """Keep session-wide progress while rooms become active and inactive."""

    def __init__(self) -> None:
        self.context = None
        self.route: list[str] = []
        self.starts: dict[str, int] = {}
        self.first_round_trip_completed = False
        self.autoplay = os.environ.get(_AUTOPLAY_ENV, "") == "1"
        _event(f"controller:create autoplay={self.autoplay}")

    def start(self, context) -> None:
        self.context = context
        _event("controller:start")

    def stop(self, context) -> None:
        if context != self.context:
            raise RuntimeError("PortalWalkDirector.stop received another WorldContext")
        status = "PASS" if self.first_round_trip_completed else "INCOMPLETE"
        _event(f"controller:stop status={status} route={self.route}")
        self.context = None

    def note_start(self, room_name: str) -> None:
        count = self.starts.get(room_name, 0) + 1
        self.starts[room_name] = count
        _event(f"room:{room_name}:start count={count}")
        if count != 1:
            raise RuntimeError(f"room '{room_name}' component started more than once")

    def note_active(
        self,
        room_name: str,
        activation_count: int,
        distance_travelled: float,
    ) -> None:
        if self.context is None:
            raise RuntimeError("room activated without a running WorldController")
        if self.context.primary_scene is None:
            raise RuntimeError(f"room '{room_name}' activated without a primary scene")

        self.route.append(room_name)
        _event(
            f"room:{room_name}:active activation={activation_count} "
            f"distance={distance_travelled:.2f} "
            f"catalog={list(self.context.scene_identities)}"
        )

        if len(self.route) <= len(_EXPECTED_FIRST_TRIP):
            expected = _EXPECTED_FIRST_TRIP[: len(self.route)]
            if self.route != expected:
                raise RuntimeError(
                    f"unexpected room route {self.route}; expected prefix {expected}"
                )

        if self.route == _EXPECTED_FIRST_TRIP:
            if activation_count != 2:
                raise RuntimeError("Sunset Yard was recreated instead of reactivated")
            if distance_travelled <= 0.0:
                raise RuntimeError("Sunset Yard did not retain its local player state")
            if self.starts != {"Sunset Yard": 1, "Blue Workshop": 1}:
                raise RuntimeError(f"unexpected component starts: {self.starts}")
            self.first_round_trip_completed = True
            _event(
                "PASS round-trip=Sunset Yard->Blue Workshop->Sunset Yard; "
                "controller and inactive room state retained"
            )

    def note_inactive(self, room_name: str, distance_travelled: float) -> None:
        _event(f"room:{room_name}:inactive distance={distance_travelled:.2f}")

    def travel(self, room_name: str, next_scene: str) -> bool:
        if self.context is None:
            raise RuntimeError("travel requested without a running WorldController")
        accepted = self.context.transition_to(next_scene)
        _event(
            f"portal:{room_name}->{next_scene} accepted={accepted} "
            f"catalog={list(self.context.scene_identities)}"
        )
        return accepted


class PortalWalker(InputComponent):
    """Move a pawn with WASD/arrows and enter a portal at one side of a room."""

    component_category = "Gameplay"
    inspect_fields = {
        "room_name": InspectField(path="room_name", label="Room", kind="string"),
        "next_scene": InspectField(
            path="next_scene", label="Destination Scene", kind="string"
        ),
        "spawn_x": InspectField(
            path="spawn_x", label="Spawn X", kind="float", step=0.1
        ),
        "portal_x": InspectField(
            path="portal_x", label="Portal X", kind="float", step=0.1
        ),
        "move_speed": InspectField(
            path="move_speed",
            label="Move Speed",
            kind="float",
            min=0.1,
            max=20.0,
            step=0.1,
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self.room_name = ""
        self.next_scene = ""
        self.spawn_x = 0.0
        self.portal_x = 0.0
        self.move_speed = 3.2
        self.activation_count = 0
        self.distance_travelled = 0.0
        self._pressed_keys: set[int] = set()
        self._transition_requested = False

    def _controller(self) -> PortalWalkDirector:
        context = require_world_context(self.scene, f"PortalWalker[{self.room_name}]")
        controller = context.controller
        if controller is None or not isinstance(controller, PortalWalkDirector):
            raise RuntimeError("PortalWalker requires PortalWalkDirector")
        return controller

    def start(self) -> None:
        self._controller().note_start(self.room_name)

    def on_scene_active(self) -> None:
        context = world_context(self.scene)
        if not context.valid:
            return
        self.activation_count += 1
        self._pressed_keys.clear()
        self._transition_requested = False
        position = self.entity.transform.local_position()
        self.entity.transform.set_local_position(Vec3(self.spawn_x, position.y, position.z))
        self._controller().note_active(
            self.room_name,
            self.activation_count,
            self.distance_travelled,
        )

    def on_scene_inactive(self) -> None:
        context = world_context(self.scene)
        if not context.valid:
            return
        self._pressed_keys.clear()
        self._controller().note_inactive(self.room_name, self.distance_travelled)

    def on_key(self, event) -> None:
        movement_keys = {
            Key.A.value,
            Key.D.value,
            Key.S.value,
            Key.W.value,
            Key.LEFT.value,
            Key.RIGHT.value,
            Key.DOWN.value,
            Key.UP.value,
        }
        if event.key not in movement_keys:
            return
        if event.action == Action.RELEASE.value:
            self._pressed_keys.discard(event.key)
        else:
            self._pressed_keys.add(event.key)
        event.handled = True

    def update(self, dt: float) -> None:
        if self._transition_requested:
            return

        controller = self._controller()
        if controller.autoplay and controller.first_round_trip_completed:
            return
        x_axis = self._axis(Key.A, Key.LEFT, Key.D, Key.RIGHT)
        y_axis = self._axis(Key.S, Key.DOWN, Key.W, Key.UP)
        if controller.autoplay:
            x_axis = 1.0 if self.portal_x > self.spawn_x else -1.0
            y_axis = 0.0

        length_squared = x_axis * x_axis + y_axis * y_axis
        if length_squared > 1.0:
            scale = length_squared ** -0.5
            x_axis *= scale
            y_axis *= scale
        if x_axis == 0.0 and y_axis == 0.0:
            return

        position = self.entity.transform.local_position()
        step = self.move_speed * max(dt, 0.0)
        next_x = min(max(position.x + x_axis * step, -4.25), 4.25)
        next_y = min(max(position.y + y_axis * step, -2.55), 2.55)
        self.entity.transform.set_local_position(Vec3(next_x, next_y, position.z))
        self.distance_travelled += (
            (next_x - position.x) ** 2 + (next_y - position.y) ** 2
        ) ** 0.5

        reached_portal = (
            next_x >= self.portal_x
            if self.portal_x > self.spawn_x
            else next_x <= self.portal_x
        )
        if not reached_portal:
            return
        self._transition_requested = controller.travel(self.room_name, self.next_scene)
        if not self._transition_requested:
            log.error(
                f"{_PREFIX} portal transition "
                f"{self.room_name}->{self.next_scene} was rejected"
            )

    def _axis(
        self,
        negative: Key,
        negative_alt: Key,
        positive: Key,
        positive_alt: Key,
    ) -> float:
        value = 0.0
        if negative.value in self._pressed_keys or negative_alt.value in self._pressed_keys:
            value -= 1.0
        if positive.value in self._pressed_keys or positive_alt.value in self._pressed_keys:
            value += 1.0
        return value


__all__ = ["PortalWalkDirector", "PortalWalker"]
