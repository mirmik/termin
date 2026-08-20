"""WorldController multi-scene navigation acceptance components."""

from __future__ import annotations

from tcbase import log
from termin.engine import WorldController, require_world_context, world_context
from termin.inspect import InspectField
from termin.scene import PythonComponent


_PREFIX = "[SceneCycleAcceptance]"
_EXPECTED_ROUTE = ["Alpha", "Beta", "Gamma", "Alpha"]


def _event(message: str) -> None:
    log.info(f"{_PREFIX} {message}")


class SceneCycleDirector(WorldController):
    """Persist across scene switches and verify one complete lazy cycle."""

    def __init__(self) -> None:
        self.context = None
        self.route: list[str] = []
        self.starts: dict[str, int] = {}
        self.completed = False
        _event("controller:create")

    def start(self, context) -> None:
        self.context = context
        _event("controller:start")

    def stop(self, context) -> None:
        if context != self.context:
            raise RuntimeError("WorldController.stop received another WorldContext")
        status = "PASS" if self.completed else "INCOMPLETE"
        _event(f"controller:stop status={status} route={self.route}")
        self.context = None

    def note_start(self, label: str) -> None:
        count = self.starts.get(label, 0) + 1
        self.starts[label] = count
        _event(f"probe:{label}:start count={count}")
        if count != 1:
            raise RuntimeError(f"scene '{label}' component started more than once")

    def note_active(self, label: str, activation_count: int, updates: int) -> None:
        if self.context is None:
            raise RuntimeError("scene activated without a running WorldController")
        primary = self.context.primary_scene
        if primary is None:
            raise RuntimeError(f"scene '{label}' activated without a primary scene")

        self.route.append(label)
        catalog = list(self.context.scene_identities)
        _event(
            f"probe:{label}:active activation={activation_count} "
            f"updates={updates} catalog={catalog}"
        )

        if len(self.route) <= len(_EXPECTED_ROUTE):
            expected = _EXPECTED_ROUTE[: len(self.route)]
            if self.route != expected:
                raise RuntimeError(
                    f"unexpected scene route {self.route}; expected prefix {expected}"
                )

        if self.route == _EXPECTED_ROUTE:
            if activation_count != 2:
                raise RuntimeError("Alpha did not preserve its component instance")
            if updates <= 0:
                raise RuntimeError("Alpha did not preserve scene-local update state")
            if self.starts != {"Alpha": 1, "Beta": 1, "Gamma": 1}:
                raise RuntimeError(f"unexpected component starts: {self.starts}")
            self.completed = True
            _event(
                "PASS route=Alpha->Beta->Gamma->Alpha; "
                "controller and Alpha scene state retained"
            )

    def note_inactive(self, label: str, updates: int) -> None:
        _event(f"probe:{label}:inactive updates={updates}")

    def advance(self, label: str, next_scene: str) -> bool:
        if self.completed:
            return False
        if self.context is None:
            raise RuntimeError("transition requested without a running WorldController")
        accepted = self.context.transition_to(next_scene)
        _event(
            f"transition:{label}->{next_scene} accepted={accepted} "
            f"catalog={list(self.context.scene_identities)}"
        )
        return accepted


class SceneCycleProbe(PythonComponent):
    """Request the next scene and retain local state while inactive."""

    component_category = "Acceptance"
    inspect_fields = {
        "label": InspectField(path="label", label="Label", kind="string"),
        "next_scene": InspectField(
            path="next_scene", label="Next Scene", kind="string"
        ),
        "delay_seconds": InspectField(
            path="delay_seconds",
            label="Delay Seconds",
            kind="float",
            min=0.1,
            max=30.0,
            step=0.1,
        ),
    }

    def __init__(self) -> None:
        super().__init__()
        self.label = ""
        self.next_scene = ""
        self.delay_seconds = 2.0
        self.activation_count = 0
        self.total_updates = 0
        self._active_seconds = 0.0
        self._request_seconds = 0.0
        self._transition_requested = False
        self._timeout_reported = False

    def _controller(self) -> SceneCycleDirector:
        context = require_world_context(self.scene, f"SceneCycleProbe[{self.label}]")
        controller = context.controller
        if controller is None:
            raise RuntimeError("SceneCycleProbe requires SceneCycleDirector")
        return controller

    def start(self) -> None:
        self._controller().note_start(self.label)

    def on_scene_active(self) -> None:
        context = world_context(self.scene)
        if not context.valid:
            return
        self.activation_count += 1
        self._active_seconds = 0.0
        self._request_seconds = 0.0
        self._transition_requested = False
        self._timeout_reported = False
        self._controller().note_active(
            self.label,
            self.activation_count,
            self.total_updates,
        )

    def on_scene_inactive(self) -> None:
        context = world_context(self.scene)
        if not context.valid:
            return
        self._controller().note_inactive(self.label, self.total_updates)

    def update(self, dt: float) -> None:
        self.total_updates += 1
        if self._controller().completed:
            return
        if self._transition_requested:
            self._request_seconds += dt
            if self._request_seconds >= 4.0 and not self._timeout_reported:
                self._timeout_reported = True
                log.error(
                    f"{_PREFIX} FAIL transition from {self.label} did not commit"
                )
            return

        self._active_seconds += dt
        if self._active_seconds < self.delay_seconds:
            return
        self._transition_requested = self._controller().advance(
            self.label,
            self.next_scene,
        )
        if not self._transition_requested:
            log.error(
                f"{_PREFIX} FAIL transition request "
                f"{self.label}->{self.next_scene} was rejected"
            )


__all__ = ["SceneCycleDirector", "SceneCycleProbe"]
