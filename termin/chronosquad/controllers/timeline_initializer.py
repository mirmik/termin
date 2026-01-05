"""TimelineInitializer - creates Timeline from scene entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.chronosquad.core import Timeline
from termin.visualization.core.python_component import PythonComponent

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class TimelineInitializer(PythonComponent):
    """
    Creates Timeline from scene entities.

    Only responsible for:
    1. Scan scene for entities with ObjectController
    2. Ask each ObjectController to create its ObjectOfTimeline
    3. Return the created Timeline

    Does NOT bind controllers - that's ChronosphereController's job.
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled=enabled)
        self._timeline_name: str = "Original"

    def create_timeline(self, scene: "Scene") -> Timeline:
        """
        Create Timeline from scene entities.

        Args:
            scene: Scene containing entities with ObjectController

        Returns:
            Created Timeline with all objects
        """
        from .object_controller import ObjectController

        log.info(f"[TimelineInitializer] Creating timeline '{self._timeline_name}'...")
        timeline = Timeline(self._timeline_name)

        object_count = 0
        for entity in scene.entities:
            objctr = entity.get_component(ObjectController)
            if objctr is not None:
                log.info(f"[TimelineInitializer] Found ObjectController on '{entity.name}', creating object...")
                obj = objctr.create_object()
                timeline.add_object(obj)
                log.info(f"[TimelineInitializer] Added object '{obj.name}' to timeline (pos={obj.local_position})")
                object_count += 1

        log.info(f"[TimelineInitializer] Timeline '{self._timeline_name}' created with {object_count} objects")
        return timeline
