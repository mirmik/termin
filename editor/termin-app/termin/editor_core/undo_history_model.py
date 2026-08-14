"""Toolkit-neutral snapshots for the editor undo/redo history."""

from __future__ import annotations

from dataclasses import dataclass

from termin.editor_core.signal import Signal
from termin.editor_core.undo_stack import UndoCommand, UndoStack


@dataclass(frozen=True)
class UndoHistoryEntry:
    index: int
    text: str


@dataclass(frozen=True)
class UndoHistorySnapshot:
    done: tuple[UndoHistoryEntry, ...]
    undone: tuple[UndoHistoryEntry, ...]


def _entries(commands: list[UndoCommand]) -> tuple[UndoHistoryEntry, ...]:
    return tuple(
        UndoHistoryEntry(index, command.text or command.__class__.__name__)
        for index, command in enumerate(commands)
    )


class UndoHistoryController:
    def __init__(self, undo_stack: UndoStack) -> None:
        self._undo_stack = undo_stack
        self.changed = Signal()

    @property
    def snapshot(self) -> UndoHistorySnapshot:
        return UndoHistorySnapshot(
            done=_entries(self._undo_stack.done_commands),
            undone=_entries(self._undo_stack.undone_commands),
        )

    def refresh(self) -> UndoHistorySnapshot:
        snapshot = self.snapshot
        self.changed.emit(snapshot)
        return snapshot


__all__ = ["UndoHistoryController", "UndoHistoryEntry", "UndoHistorySnapshot"]
