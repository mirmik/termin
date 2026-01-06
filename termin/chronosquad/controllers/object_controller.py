"""ObjectController - binds Entity to ObjectOfTimeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin._native import log
from termin.visualization.core.python_component import PythonComponent
from termin.chronosquad.core import (
    ObjectOfTimeline,
    Timeline,
)
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.entity import Entity


class ObjectController(PythonComponent):
    """
    Component that binds an Entity to an ObjectOfTimeline.

    Two-phase lifecycle:
    1. Template phase: Entity acts as a template, create_object() creates ObjectOfTimeline
    2. Runtime phase: bind() connects to Timeline, update() syncs Entity transform

    Animation is handled separately by AnimationController.
    """
    
    inspect_fields = {
        "selectable": InspectField(
            path="selectable",
            label="Selectable",
            kind="bool",
        )
    }

    def __init__(
        self,
        enabled: bool = True
    ):
        super().__init__(enabled=enabled)
        self.selectable: bool = False

        # Runtime binding
        self._timeline: Timeline | None = None
        self._object_name: str | None = None

    # =========================================================================
    # Phase 1: Template - create ObjectOfTimeline from Entity
    # =========================================================================

    def create_object(self) -> ObjectOfTimeline:
        """
        Create ObjectOfTimeline using Entity as template.

        Called by TimelineInitializer during initialization phase.
        """
        if self.entity is None:
            raise RuntimeError("ObjectController must be attached to Entity")

        name = self.entity.name
        obj = ObjectOfTimeline(name)

        # Copy transform from Entity
        obj.set_local_pose(self.entity.transform.local_pose())

        return obj

    # =========================================================================
    # Phase 2: Runtime - bind to Timeline and sync
    # =========================================================================

    def bind(self, timeline: Timeline) -> None:
        """
        Bind to a Timeline.

        After binding, update() will sync Entity transform from ObjectOfTimeline.
        """
        self._timeline = timeline
        if self.entity:
            self._object_name = self.entity.name
            chrono_obj = self.chrono_object
            if chrono_obj:
                log.info(f"[ObjectController] '{self._object_name}' bound to chrono object (pos={chrono_obj.local_position})")
            else:
                log.warning(f"[ObjectController] '{self._object_name}' bound but chrono object not found in timeline")

    def unbind(self) -> None:
        """Unbind from current Timeline."""
        log.info(f"[ObjectController] '{self._object_name}' unbound")
        self._timeline = None

    @property
    def timeline(self) -> Timeline | None:
        return self._timeline

    @property
    def chrono_object(self) -> ObjectOfTimeline | None:
        """Get the bound ObjectOfTimeline."""
        if self._timeline is None or self._object_name is None:
            return None
        return self._timeline.get_object(self._object_name)

    def update(self, dt: float) -> None:
        """Sync Entity transform from ObjectOfTimeline."""
        obj = self.chrono_object
        if obj is None:
            return

        if self.entity is None:
            return

        # Update Entity transform from chrono object
        transform = self.entity.transform
        pos = obj.local_position
        rot = obj.local_rotation

        transform.set_local_position(pos)
        transform.set_local_rotation(rot)

    # =========================================================================
    # Utilities
    # =========================================================================

    def is_bound(self) -> bool:
        """Check if bound to a timeline."""
        return self._timeline is not None and self.chrono_object is not None
