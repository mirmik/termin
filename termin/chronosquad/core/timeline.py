"""
Timeline - main container for time-reversible game state.

A Timeline contains objects and can move forward/backward in time.
It can be copied to create alternative timeline branches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .event_line import EventLine, TimeDirection

if TYPE_CHECKING:
    from .object_of_timeline import ObjectOfTimeline


# Steps per second (game frequency)
GAME_FREQUENCY: float = 100.0


class Timeline:
    """
    Container for all game objects with time management.

    Supports:
    - Moving forward/backward in time (promote)
    - Copying to create alternative branches
    - Object management
    """

    def __init__(self, name: str = "Timeline"):
        self._name = name
        self._current_step: int = 0
        self._current_time: float = 0.0

        # Objects in this timeline
        self._objects: dict[str, ObjectOfTimeline] = {}
        self._objects_list: list[ObjectOfTimeline] = []

        # Global events (not tied to specific objects)
        self._global_events: EventLine[Timeline] = EventLine()

        # Time boundaries
        self._last_positive_step: int = 0
        self._last_negative_step: int = 0
        self._is_reversed_pass: bool = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def current_step(self) -> int:
        return self._current_step

    @property
    def current_time(self) -> float:
        return self._current_time

    @property
    def is_reversed(self) -> bool:
        return self._is_reversed_pass

    @property
    def objects(self) -> list[ObjectOfTimeline]:
        return self._objects_list

    def add_object(self, obj: ObjectOfTimeline) -> None:
        """Add an object to the timeline."""
        name = obj.name
        if name in self._objects:
            if self._objects[name] is obj:
                return
            raise ValueError(f"Object with name '{name}' already exists")

        self._objects[name] = obj
        self._objects_list.append(obj)
        obj._timeline = self

    def remove_object(self, obj: ObjectOfTimeline) -> None:
        """Remove an object from the timeline."""
        name = obj.name
        if name in self._objects:
            del self._objects[name]
            self._objects_list.remove(obj)
            obj._timeline = None

    def get_object(self, name: str) -> ObjectOfTimeline | None:
        """Get object by name."""
        return self._objects.get(name)

    def has_object(self, name: str) -> bool:
        return name in self._objects

    def promote(self, target_step: int) -> None:
        """
        Move timeline to target_step, processing all intermediate steps.
        """
        if target_step == self._current_step:
            return

        direction = TimeDirection.Forward if target_step > self._current_step else TimeDirection.Backward
        step_delta = 1 if direction == TimeDirection.Forward else -1

        while self._current_step != target_step:
            self._current_step += step_delta
            self._do_step(direction)

        self._current_time = self._current_step / GAME_FREQUENCY

    def promote_delta(self, delta_time: float) -> None:
        """Move timeline by delta seconds."""
        target_step = int((self._current_time + delta_time) * GAME_FREQUENCY)
        self.promote(target_step)

    def _do_step(self, direction: TimeDirection) -> None:
        """Process a single time step."""
        step = self._current_step

        # Update time boundaries
        if direction == TimeDirection.Forward:
            if step > self._last_positive_step:
                self._last_positive_step = step
        else:
            if step < self._last_negative_step:
                self._last_negative_step = step

        # Promote all objects
        for obj in self._objects_list:
            obj.promote(step)

        # Promote global events
        self._global_events.promote(step, self)

    def add_global_event(self, event) -> None:
        """Add a global event (not tied to an object)."""
        self._global_events.add(event)

    def set_reversed(self, value: bool) -> None:
        """Set whether this timeline is in reversed pass mode."""
        self._is_reversed_pass = value

    def is_present(self) -> bool:
        """Check if we're at the present moment (latest step)."""
        if self._is_reversed_pass:
            return self._current_step == self._last_negative_step
        return self._current_step == self._last_positive_step

    def is_past(self) -> bool:
        return not self.is_present()

    def drop_to_current(self) -> None:
        """
        Drop future events - make current state the 'present'.
        Used when editing the past to branch the timeline.
        """
        for obj in self._objects_list:
            obj.drop_to_current()

        self._global_events.drop_future()
        self._last_positive_step = self._current_step
        self._last_negative_step = self._current_step

    def copy(self, new_name: str | None = None) -> Timeline:
        """
        Create a copy of this timeline for branching.
        """
        if new_name is None:
            new_name = f"{self._name}_copy"

        new_tl = Timeline(new_name)
        new_tl._current_step = self._current_step
        new_tl._current_time = self._current_time
        new_tl._last_positive_step = self._last_positive_step
        new_tl._last_negative_step = self._last_negative_step
        new_tl._is_reversed_pass = self._is_reversed_pass

        # Copy objects
        for obj in self._objects_list:
            new_obj = obj.copy(new_tl)
            new_tl.add_object(new_obj)

        # Copy global events
        new_tl._global_events = self._global_events.copy()

        return new_tl

    def info(self) -> str:
        """Return debug info about timeline state."""
        lines = [
            f"Timeline: {self._name}",
            f"  Current step: {self._current_step}",
            f"  Current time: {self._current_time:.2f}s",
            f"  Last positive: {self._last_positive_step}",
            f"  Last negative: {self._last_negative_step}",
            f"  Reversed: {self._is_reversed_pass}",
            f"  Objects: {len(self._objects_list)}",
            f"  Global events: {self._global_events.count()}",
        ]
        return "\n".join(lines)
