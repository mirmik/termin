"""Bounded UI-neutral editor/build log."""

from __future__ import annotations

from .signal import Signal


class EditorLogModel:
    def __init__(self, *, max_lines: int = 2000) -> None:
        if max_lines < 1:
            raise ValueError("max_lines must be positive")
        self.changed = Signal()
        self._max_lines = max_lines
        self._lines: list[str] = []

    @property
    def text(self) -> str:
        return "\n".join(self._lines)

    def append(self, message: str) -> None:
        self._lines.extend(str(message).splitlines() or [""])
        del self._lines[:-self._max_lines]
        self.changed.emit(self.text)

    def clear(self) -> None:
        self._lines.clear()
        self.changed.emit("")


__all__ = ["EditorLogModel"]
