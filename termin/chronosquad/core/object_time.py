"""Object time management - broken time and time modifiers."""

from __future__ import annotations
from .event_line import EventCard, TimeDirection
from .timeline import GAME_FREQUENCY


class TimeModifier(EventCard[None]):
    """Base class for time modifiers (freeze, haste, etc.)."""

    def time_offset(self, step: int) -> int:
        """Time offset at given step."""
        return 0

    def time_offset_on_finish(self) -> int:
        """Final time offset when modifier ends."""
        return 0

    def multiplier(self) -> float:
        """Time speed multiplier."""
        return 1.0

    def copy(self) -> TimeModifier:
        return TimeModifier(self.start_step, self.finish_step)


class TimeFreeze(TimeModifier):
    """Freezes object's local time."""

    def __init__(self, start_step: int, finish_step: int):
        super().__init__(start_step, finish_step)
        self._mul = -1

    def time_offset(self, step: int) -> int:
        from_start = step - self.start_step
        return from_start * self._mul

    def time_offset_on_finish(self) -> int:
        from_start = self.finish_step - self.start_step
        return from_start * self._mul

    def multiplier(self) -> float:
        return float(self._mul)

    def copy(self) -> TimeFreeze:
        return TimeFreeze(self.start_step, self.finish_step)


class TimeHaste(TimeModifier):
    """Speeds up object's local time."""

    def __init__(self, start_step: int, finish_step: int, speed: float = 2.0):
        super().__init__(start_step, finish_step)
        self._speed = speed

    def time_offset(self, step: int) -> int:
        from_start = step - self.start_step
        return int(from_start * (self._speed - 1))

    def time_offset_on_finish(self) -> int:
        from_start = self.finish_step - self.start_step
        return int(from_start * (self._speed - 1))

    def multiplier(self) -> float:
        return self._speed

    def copy(self) -> TimeHaste:
        return TimeHaste(self.start_step, self.finish_step, self._speed)


class ObjectTime:
    """
    Manages object's personal time relative to timeline.

    Timeline time (global) -> Broken time (personal) -> Local time (with modifiers)

    "Broken time" always increases even when object travels back in time.
    This allows objects to have continuous personal history.
    """

    def __init__(self):
        self._timeline_zero: int = 0
        self._broken_timeline_zero: int = 0
        self._non_finished_offset: int = 0
        self._finished_offset: int = 0
        self._is_reversed: bool = False
        self._modifiers: list[TimeModifier] = []
        self._active_modifiers: list[TimeModifier] = []

    def copy(self) -> ObjectTime:
        ot = ObjectTime()
        ot._timeline_zero = self._timeline_zero
        ot._broken_timeline_zero = self._broken_timeline_zero
        ot._non_finished_offset = self._non_finished_offset
        ot._finished_offset = self._finished_offset
        ot._is_reversed = self._is_reversed
        ot._modifiers = [m.copy() for m in self._modifiers]
        ot._active_modifiers = []
        return ot

    @property
    def timeline_zero(self) -> int:
        return self._timeline_zero

    @property
    def broken_timeline_zero(self) -> int:
        return self._broken_timeline_zero

    @property
    def is_reversed(self) -> bool:
        return self._is_reversed

    @property
    def offset(self) -> int:
        return self._non_finished_offset + self._finished_offset

    def set_reference_point(
        self,
        new_timeline_zero: int,
        new_direction_is_reversed: bool,
        offset: int = 0,
    ) -> None:
        """Set new time reference point (when object reverses direction)."""
        dist = new_timeline_zero - self._timeline_zero - offset
        broken_dist = -dist if self._is_reversed else dist
        self._broken_timeline_zero += broken_dist
        self._timeline_zero = new_timeline_zero
        self._is_reversed = new_direction_is_reversed

    def timeline_to_broken(self, timeline_step: int) -> int:
        """Convert timeline step to broken (personal) step."""
        dist = timeline_step - self._timeline_zero
        broken_dist = -dist if self._is_reversed else dist
        return broken_dist + self._broken_timeline_zero

    def broken_to_timeline(self, broken_step: int) -> int:
        """Convert broken step back to timeline step."""
        broken_dist = broken_step - self._broken_timeline_zero
        dist = -broken_dist if self._is_reversed else broken_dist
        return self._timeline_zero + dist

    def timeline_to_local(self, timeline_step: int) -> int:
        """Convert timeline step to local time (with modifiers)."""
        broken_step = self.timeline_to_broken(timeline_step)
        return self._non_finished_offset + self._finished_offset + broken_step

    def timeline_to_local_time(self, timeline_time: float) -> float:
        """Convert timeline time (seconds) to local time."""
        step = int(timeline_time * GAME_FREQUENCY)
        local_step = self.timeline_to_local(step)
        return local_step / GAME_FREQUENCY

    def add_modifier(self, modifier: TimeModifier) -> None:
        """Add a time modifier."""
        self._modifiers.append(modifier)

    def promote(self, timeline_step: int) -> None:
        """Update modifiers for current timeline step."""
        broken_step = self.timeline_to_broken(timeline_step)

        new_active: list[TimeModifier] = []
        for mod in self._modifiers:
            if mod.is_active_at(broken_step):
                new_active.append(mod)

        # Handle modifiers that just ended (forward) or just started (backward)
        old_set = set(id(m) for m in self._active_modifiers)
        new_set = set(id(m) for m in new_active)

        # Modifiers that were active but aren't anymore
        for mod in self._active_modifiers:
            if id(mod) not in new_set:
                # Modifier ended - add its final offset
                self._finished_offset += mod.time_offset_on_finish()

        # Modifiers that weren't active but are now (going backward)
        for mod in new_active:
            if id(mod) not in old_set:
                if broken_step < mod.start_step:
                    # We're going backward into a modifier
                    self._finished_offset -= mod.time_offset_on_finish()

        self._active_modifiers = new_active
        self._update_offset(broken_step)

    def _update_offset(self, broken_step: int) -> None:
        """Update non-finished offset from active modifiers."""
        result = 0
        for mod in self._active_modifiers:
            result += mod.time_offset(broken_step)
        self._non_finished_offset = result

    def current_time_multiplier(self) -> float:
        """Get current time multiplier from all active modifiers."""
        result = 1.0
        for mod in self._active_modifiers:
            result *= mod.multiplier()
        return result

    def drop_to_current(self) -> None:
        """Drop future modifiers."""
        # Keep only modifiers that have started
        self._modifiers = [
            m for m in self._modifiers
            if m.start_step <= self._broken_timeline_zero
        ]

    def info(self) -> str:
        lines = [
            f"timeline_zero: {self._timeline_zero}",
            f"broken_timeline_zero: {self._broken_timeline_zero}",
            f"non_finished_offset: {self._non_finished_offset}",
            f"finished_offset: {self._finished_offset}",
            f"is_reversed: {self._is_reversed}",
            f"modifiers: {len(self._modifiers)}",
            f"active_modifiers: {len(self._active_modifiers)}",
        ]
        return "\n".join(lines)
