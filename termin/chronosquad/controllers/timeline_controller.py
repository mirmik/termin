"""TimelineController - manages binding between scene and Timeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from termin._native import log
from termin.visualization.core.python_component import PythonComponent
from termin.chronosquad.core import Timeline, ChronoSphere

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from .object_controller import ObjectController


class TimelineController(PythonComponent):
    """
    Manages binding between scene Entities and a Timeline.

    Responsibilities:
    - Holds reference to bound Timeline
    - Finds and binds all ObjectControllers in scene
    - Handles timeline switching (rebinding to different Timeline)
    """

    inspect_fields: Dict[str, Any] = {}

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._timeline: Timeline | None = None
        self._object_controllers: List[ObjectController] = []

    @property
    def timeline(self) -> Timeline | None:
        return self._timeline

    def bind(self, timeline: Timeline) -> None:
        """
        Bind to a Timeline.

        Finds all ObjectControllers in scene and binds them to this timeline.
        """
        log.info(f"[TimelineController] Binding to timeline '{timeline.name}'...")
        self._timeline = timeline
        self._bind_all_controllers()
        log.info(f"[TimelineController] Bound {len(self._object_controllers)} ObjectControllers")

    def unbind(self) -> None:
        """Unbind from current Timeline."""
        log.info("[TimelineController] Unbinding from timeline...")
        for objctr in self._object_controllers:
            objctr.unbind()
        self._timeline = None
        log.info("[TimelineController] Unbound")

    def rebind(self, new_timeline: Timeline) -> None:
        """
        Switch to a different Timeline.

        All ObjectControllers will rebind to objects in the new timeline.
        """
        log.info(f"[TimelineController] Rebinding to timeline '{new_timeline.name}'...")
        self._timeline = new_timeline
        for objctr in self._object_controllers:
            objctr.bind(new_timeline)
        log.info(f"[TimelineController] Rebound {len(self._object_controllers)} ObjectControllers")

    def _bind_all_controllers(self) -> None:
        """Find and bind all ObjectControllers in scene."""
        if self._scene is None or self._timeline is None:
            log.warning("[TimelineController] Cannot bind: scene or timeline is None")
            return

        from .object_controller import ObjectController

        self._object_controllers.clear()

        for entity in self._scene.entities:
            objctr = entity.get_component(ObjectController)
            if objctr is not None:
                log.info(f"[TimelineController] Binding ObjectController on '{entity.name}'...")
                objctr.bind(self._timeline)
                self._object_controllers.append(objctr)

    def get_object_controller(self, name: str) -> ObjectController | None:
        """Get ObjectController by entity name."""
        for objctr in self._object_controllers:
            if objctr.entity and objctr.entity.name == name:
                return objctr
        return None

    @property
    def object_controllers(self) -> List[ObjectController]:
        return self._object_controllers

    def on_added(self, scene) -> None:
        """Called when added to scene."""
        super().on_added(scene)
        # If already bound to timeline, bind controllers
        if self._timeline is not None:
            self._bind_all_controllers()
