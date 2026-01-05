"""ChronoSphere - collection of timelines."""

from __future__ import annotations
from typing import Callable
from .timeline import Timeline, GAME_FREQUENCY


class ChronoSphere:
    """
    Container for all timelines in the game.

    Manages:
    - Current active timeline
    - Group of timelines updated together
    - Time multiplier and pause mode
    - Timeline switching
    """

    def __init__(self):
        self._timelines: dict[str, Timeline] = {}
        self._current_timeline: Timeline | None = None
        self._current_group: list[Timeline] = []

        # Time control
        self._time_multiplier: float = 1.0
        self._target_time_multiplier: float = 1.0
        self._pause_mode: bool = False
        self._target_time_in_pause: float = 0.0

        # Selected object
        self._selected_object_name: str | None = None

        # Callbacks
        self._on_timeline_added: list[Callable[[Timeline], None]] = []
        self._on_timeline_removed: list[Callable[[Timeline], None]] = []
        self._on_current_changed: list[Callable[[Timeline], None]] = []
        self._on_selected_changed: list[Callable[[str | None], None]] = []

    @property
    def current_timeline(self) -> Timeline | None:
        return self._current_timeline

    @property
    def time_multiplier(self) -> float:
        return self._time_multiplier

    @property
    def target_time_multiplier(self) -> float:
        return self._target_time_multiplier

    @target_time_multiplier.setter
    def target_time_multiplier(self, value: float) -> None:
        self._target_time_multiplier = value

    @property
    def is_paused(self) -> bool:
        return self._pause_mode

    @property
    def timelines_count(self) -> int:
        return len(self._timelines)

    def timelines(self) -> dict[str, Timeline]:
        return self._timelines

    def timelines_list(self) -> list[Timeline]:
        return list(self._timelines.values())

    # Timeline management

    def add_timeline(self, timeline: Timeline) -> None:
        """Add a timeline to the chronosphere."""
        name = timeline.name
        if name in self._timelines:
            return
        self._timelines[name] = timeline
        for cb in self._on_timeline_added:
            cb(timeline)

    def remove_timeline(self, timeline: Timeline) -> None:
        """Remove a timeline."""
        if timeline.name in self._timelines:
            del self._timelines[timeline.name]
            if timeline in self._current_group:
                self._current_group.remove(timeline)
            for cb in self._on_timeline_removed:
                cb(timeline)

    def get_timeline(self, name: str) -> Timeline | None:
        """Get timeline by name."""
        return self._timelines.get(name)

    def create_timeline(self, name: str) -> Timeline:
        """Create and add a new timeline."""
        tl = Timeline(name)
        self.add_timeline(tl)
        return tl

    def create_copy_of_current(self, new_name: str | None = None) -> Timeline:
        """Create a copy of current timeline."""
        if self._current_timeline is None:
            raise ValueError("No current timeline")
        copy = self._current_timeline.copy(new_name)
        self.add_timeline(copy)
        return copy

    def set_current_timeline(self, timeline: Timeline) -> None:
        """Set the active timeline."""
        if timeline.name not in self._timelines:
            self.add_timeline(timeline)

        old = self._current_timeline
        self._current_timeline = timeline

        # Update current group
        if old in self._current_group:
            self._current_group.remove(old)
        if timeline not in self._current_group:
            self._current_group.append(timeline)

        self._target_time_in_pause = timeline.current_time

        for cb in self._on_current_changed:
            cb(timeline)

    def set_current_by_name(self, name: str) -> None:
        """Set current timeline by name."""
        tl = self.get_timeline(name)
        if tl:
            self.set_current_timeline(tl)

    # Current group management

    def add_to_group(self, timeline: Timeline) -> None:
        """Add timeline to current update group."""
        if timeline not in self._current_group:
            self._current_group.append(timeline)

    def remove_from_group(self, timeline: Timeline) -> None:
        """Remove timeline from current update group."""
        if timeline in self._current_group:
            self._current_group.remove(timeline)

    def clear_group(self) -> None:
        """Clear current update group."""
        self._current_group.clear()

    # Time control

    def set_time_multiplier(self, multiplier: float) -> None:
        """Set current time multiplier."""
        self._time_multiplier = multiplier

    def set_target_time_multiplier(self, multiplier: float) -> None:
        """Set target time multiplier (for smooth transition)."""
        self._target_time_multiplier = multiplier

    def time_reverse_immediate(self) -> None:
        """Immediately reverse time direction."""
        self._target_time_multiplier = -self._target_time_multiplier
        self._time_multiplier = -self._time_multiplier

    def modify_target_time_in_pause_mode(self, delta_time: float) -> None:
        """Modify target time in pause mode (for time scrubbing)."""
        self._target_time_in_pause += delta_time

    def pause(self) -> None:
        """Toggle pause mode."""
        self.set_pause(not self._pause_mode)

    def toggle_pause(self) -> None:
        """Toggle pause mode (alias for pause())."""
        self.pause()

    def set_pause(self, paused: bool) -> None:
        """Set pause mode."""
        if paused and not self._pause_mode:
            # Entering pause
            self._pause_mode = True
            if self._current_timeline:
                self._target_time_in_pause = self._current_timeline.current_time
            self._target_time_multiplier = 0.0
        elif not paused and self._pause_mode:
            # Leaving pause
            self._pause_mode = False
            self._target_time_multiplier = 1.0

    # Selection

    def select(self, object_name: str | None) -> None:
        """Select an object by name."""
        if self._selected_object_name != object_name:
            self._selected_object_name = object_name
            for cb in self._on_selected_changed:
                cb(object_name)

    @property
    def selected_object_name(self) -> str | None:
        return self._selected_object_name

    # Update

    def update(self, delta_time: float) -> None:
        """Update all timelines in current group."""
        if self._pause_mode:
            # In pause mode, smoothly approach target time
            if self._current_timeline:
                current = self._current_timeline.current_time
                target = self._target_time_in_pause
                diff = target - current
                self._promote_delta(diff * 0.04 + delta_time * self._time_multiplier)
                self._target_time_in_pause += delta_time * self._time_multiplier
        else:
            self._promote_delta(delta_time * self._time_multiplier)

        # Smooth multiplier transition
        self._time_multiplier += (self._target_time_multiplier - self._time_multiplier) * 0.06

    def _promote_delta(self, delta_time: float) -> None:
        """Promote all timelines in group by delta time."""
        for tl in self._current_group:
            tl.promote_delta(delta_time)

    # Callbacks

    def on_timeline_added(self, callback: Callable[[Timeline], None]) -> None:
        self._on_timeline_added.append(callback)

    def on_timeline_removed(self, callback: Callable[[Timeline], None]) -> None:
        self._on_timeline_removed.append(callback)

    def on_current_changed(self, callback: Callable[[Timeline], None]) -> None:
        self._on_current_changed.append(callback)

    def on_selected_changed(self, callback: Callable[[str | None], None]) -> None:
        self._on_selected_changed.append(callback)

    # Info

    def info(self) -> str:
        lines = [
            f"ChronoSphere",
            f"  Timelines: {len(self._timelines)}",
            f"  Current: {self._current_timeline.name if self._current_timeline else 'None'}",
            f"  Group size: {len(self._current_group)}",
            f"  Time multiplier: {self._time_multiplier:.2f}",
            f"  Target multiplier: {self._target_time_multiplier:.2f}",
            f"  Paused: {self._pause_mode}",
        ]
        return "\n".join(lines)
