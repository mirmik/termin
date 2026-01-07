"""
ActorCommand - base class for all actor commands.

Commands are actions that actors execute over time (move, attack, etc).
They have start_step and can be interrupted or finished.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.chronosquad.core.object_of_timeline import ObjectOfTimeline
    from termin.chronosquad.core.timeline import Timeline
    from termin.chronosquad.core.command_buffer import CommandBuffer


class ActorCommand(ABC):
    """
    Base class for actor commands.

    Commands have:
    - start_step: when the command starts
    - finish_step: when the command is expected to finish (can be infinite)
    - can be interrupted
    - execute_first_time() for initialization
    - execute() for ongoing execution
    """

    def __init__(self, start_step: int):
        self._start_step = start_step
        self._finish_step = 2**62  # Very large, effectively infinite

    @property
    def start_step(self) -> int:
        return self._start_step

    @property
    def finish_step(self) -> int:
        return self._finish_step

    def set_start_step(self, step: int) -> None:
        self._start_step = step

    def set_finish_step(self, step: int) -> None:
        self._finish_step = step

    def shift_by_start(self, new_start: int) -> None:
        """Shift command to start at new_start."""
        self._start_step = new_start

    def can_be_interrupted(self) -> bool:
        """Whether this command can be interrupted by another command."""
        return True

    def execute_first_time(self, actor: ObjectOfTimeline, timeline: Timeline) -> bool:
        """
        Called when command starts execution.

        Returns True if command is immediately finished.
        """
        return False

    def execute(self, actor: ObjectOfTimeline, timeline: Timeline) -> bool:
        """
        Called on each step while command is active.

        Returns True if command is finished.
        """
        return True

    def cancel_handler(self, command_buffer: CommandBuffer) -> None:
        """Called when command is cancelled (removed from queue before execution)."""
        pass

    def stop_handler(self, command_buffer: CommandBuffer) -> None:
        """Called when command is stopped (finished or interrupted)."""
        pass

    def demasked(self) -> bool:
        """Whether executing this command demasks the actor."""
        return True

    def hash_code(self) -> int:
        """Hash for deduplication."""
        return hash((type(self).__name__, self._start_step))

    def clone(self) -> ActorCommand:
        """Create a copy of this command."""
        raise NotImplementedError("Subclasses must implement clone()")

    def info(self) -> str:
        """Debug info."""
        return f"{type(self).__name__}(start={self._start_step})"
