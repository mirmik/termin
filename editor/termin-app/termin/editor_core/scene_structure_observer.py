"""Coalescing bridge from scene events to hierarchy rebuilds."""

from __future__ import annotations

from collections.abc import Callable
import logging


_logger = logging.getLogger(__name__)


class SceneStructureObserver:
    """Observe one scene and defer hierarchy mutation to the UI poll boundary."""

    def __init__(self, rebuild: Callable[[], object], request_update: Callable[[], None]) -> None:
        self._rebuild = rebuild
        self._request_update = request_update
        self._subscription = None
        self._pending = False

    @property
    def pending(self) -> bool:
        return self._pending

    def set_scene(self, scene) -> None:
        self.close()
        if scene is None:
            return
        try:
            self._subscription = scene.subscribe_event(
                "tc.scene.structure_changed",
                self._on_structure_changed,
            )
        except Exception:
            _logger.exception("Failed to subscribe native hierarchy to scene structure events")

    def _on_structure_changed(self, _event) -> None:
        self._pending = True
        self._request_update()

    def poll(self) -> bool:
        if not self._pending:
            return False
        self._pending = False
        try:
            self._rebuild()
        except Exception:
            _logger.exception("Failed to rebuild native scene hierarchy")
            return False
        self._request_update()
        return True

    def close(self) -> None:
        subscription = self._subscription
        self._subscription = None
        self._pending = False
        if subscription is None:
            return
        try:
            subscription.unsubscribe()
        except Exception:
            _logger.exception("Failed to unsubscribe native hierarchy from scene events")


__all__ = ["SceneStructureObserver"]
