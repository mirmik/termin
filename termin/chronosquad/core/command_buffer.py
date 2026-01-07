"""
CommandBuffer - manages actor command queue.

Stores a list of commands sorted by start_step.
On each promote/execute, runs the current active command.
When a new command is added, can drop future commands (for player control)
or keep them (for AI replay).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.chronosquad.core.commands.actor_command import ActorCommand

if TYPE_CHECKING:
    from termin.chronosquad.core.object_of_timeline import ObjectOfTimeline
    from termin.chronosquad.core.timeline import Timeline


class CommandBuffer:
    """
    Command queue for an ObjectOfTimeline.

    Manages a list of commands and executes them in order.
    Supports timeline branching by dropping future commands when new ones are added.
    """

    def __init__(self, actor: ObjectOfTimeline):
        self._actor = actor
        self._commands: list[ActorCommand] = []
        self._current_index: int = -1
        self._promotion_step: int = -(2**62)

        # Track which commands were just added this frame
        self._commands_added: list[ActorCommand] = []

        # If controlled by AI, buffer is not dropped on new timeline branch
        self._controlled_by_ai: bool = False

        # Command marked as finished (by start_step) to avoid re-executing
        self._marked_finished_step: int = -(2**62)

    @property
    def actor(self) -> ObjectOfTimeline:
        return self._actor

    @property
    def current_command(self) -> ActorCommand | None:
        """Get current active command."""
        if self._current_index < 0 or self._current_index >= len(self._commands):
            return None
        cmd = self._commands[self._current_index]
        if cmd.start_step == self._marked_finished_step:
            return None
        return cmd

    def set_controlled_by_ai(self, value: bool) -> None:
        self._controlled_by_ai = value

    def clean(self) -> None:
        """Clear all commands."""
        self._commands.clear()
        self._current_index = -1
        self._commands_added.clear()
        self._marked_finished_step = -(2**62)

    def promote(self, local_step: int, timeline: Timeline) -> None:
        """
        Promote command buffer to local_step.

        Advances _current_index to point to the command active at local_step.
        """
        # Track which commands become newly active
        old_index = self._current_index

        # Find the command that should be active at local_step
        # (last command where start_step <= local_step)
        self._current_index = -1
        for i, cmd in enumerate(self._commands):
            if cmd.start_step <= local_step:
                self._current_index = i

        # Commands that became active
        if self._current_index > old_index and old_index >= 0:
            for i in range(old_index + 1, self._current_index + 1):
                self._commands_added.append(self._commands[i])
        elif self._current_index >= 0 and old_index < 0:
            for i in range(0, self._current_index + 1):
                self._commands_added.append(self._commands[i])

        self._promotion_step = local_step

    def execute(self, local_step: int, timeline: Timeline) -> None:
        """
        Execute current command.

        Called each frame to run the active command.
        Matches original C# CommandBuffer.Execute().
        """
        self.promote(local_step, timeline)

        current = self.current_command
        if current is None or current.start_step == self._marked_finished_step:
            # No active command - create IdleAnimatronic if needed
            if self._actor.current_animatronic_is_finished():
                from termin.chronosquad.core.animatronic import IdleAnimatronic, AnimationType

                idle_state = IdleAnimatronic(
                    start_step=local_step,
                    pose=self._actor.local_pose.copy(),
                    idle_animation=AnimationType.IDLE,
                )
                self._actor.add_animatronic(idle_state)

            self._commands_added.clear()
            return

        # Execute command
        finished = False
        if current in self._commands_added:
            finished = current.execute_first_time(self._actor, timeline)
            self._commands_added.remove(current)
        else:
            finished = current.execute(self._actor, timeline)

        if finished:
            self._mark_finished(current)

        self._commands_added.clear()

    def _mark_finished(self, command: ActorCommand) -> None:
        """Mark command as finished."""
        if command is None or command.start_step == self._marked_finished_step:
            return

        command.stop_handler(self)
        self._marked_finished_step = command.start_step

    def add_command(self, command: ActorCommand) -> None:
        """
        Add a new command.

        This is the main entry point for user commands.
        Drops future commands and adds the new one.
        """
        # Mark current as finished
        current = self.current_command
        if current is not None:
            self._mark_finished(current)

        # Drop commands after current
        if not self._controlled_by_ai:
            removed = self._drop_to_current()
            for cmd in removed:
                cmd.cancel_handler(self)

        # Add new command sorted by start_step
        self._add_sorted(command)

    def _drop_to_current(self) -> list[ActorCommand]:
        """Remove all commands after current index. Returns removed commands."""
        removed = []
        if self._current_index < 0:
            # Nothing active, clear all
            removed = self._commands[:]
            self._commands.clear()
            return removed

        # Keep commands up to and including current
        while len(self._commands) > self._current_index + 1:
            removed.append(self._commands.pop())

        return removed

    def _add_sorted(self, command: ActorCommand) -> None:
        """Add command maintaining sort order by start_step."""
        # Find insertion point
        insert_at = len(self._commands)
        for i, cmd in enumerate(self._commands):
            if cmd.start_step > command.start_step:
                insert_at = i
                break

        self._commands.insert(insert_at, command)

        # Update current index if needed
        if self._current_index >= 0 and insert_at <= self._current_index:
            self._current_index += 1

    def import_command(self, command: ActorCommand) -> None:
        """Import command without dropping future (for loading/copying)."""
        self._add_sorted(command)

    def copy(self, new_actor: ObjectOfTimeline) -> CommandBuffer:
        """Create a copy for a new timeline."""
        buf = CommandBuffer(new_actor)
        buf._controlled_by_ai = self._controlled_by_ai
        buf._marked_finished_step = self._marked_finished_step
        buf._promotion_step = self._promotion_step

        # Copy commands
        for cmd in self._commands:
            buf._commands.append(cmd.clone())

        # Recalculate current index
        buf._current_index = -1
        for i, cmd in enumerate(buf._commands):
            if cmd.start_step <= buf._promotion_step:
                buf._current_index = i

        return buf

    def drop_to_current_state(self) -> list[ActorCommand]:
        """Drop future commands (called on timeline branch)."""
        if self._controlled_by_ai:
            return []
        return self._drop_to_current()

    def info(self) -> str:
        """Debug info."""
        lines = [f"CommandBuffer: {len(self._commands)} commands, current_idx={self._current_index}"]
        for i, cmd in enumerate(self._commands):
            marker = " -> " if i == self._current_index else "    "
            lines.append(f"{marker}{cmd.info()}")
        return "\n".join(lines)
