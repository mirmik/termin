"""Toolkit-neutral state owner for the editor Python console."""

from __future__ import annotations

from dataclasses import dataclass

from termin.editor_core.python_executor import EditorPythonExecutor
from termin.editor_core.signal import Signal


@dataclass(frozen=True)
class PythonConsoleSnapshot:
    transcript: str
    prompt: str


class PythonConsoleController:
    def __init__(self, executor: EditorPythonExecutor) -> None:
        self._executor = executor
        self._transcript = "Python console ready.\n"
        self._prompt = ">>>"
        self.changed = Signal()

    @property
    def snapshot(self) -> PythonConsoleSnapshot:
        return PythonConsoleSnapshot(self._transcript, self._prompt)

    def execute(self, text: str) -> PythonConsoleSnapshot:
        if not text.strip() and self._prompt == ">>>":
            return self.snapshot
        self._append(f"{self._prompt} {text}")
        result = self._executor.execute_repl_line(text)
        self._append(result.output)
        self._append(result.error)
        self._prompt = "..." if result.wants_more else ">>>"
        return self._publish()

    def clear(self) -> PythonConsoleSnapshot:
        self._transcript = ""
        return self._publish()

    def _append(self, text: str) -> None:
        if not text:
            return
        if self._transcript and not self._transcript.endswith("\n"):
            self._transcript += "\n"
        self._transcript += text.rstrip("\n") + "\n"

    def _publish(self) -> PythonConsoleSnapshot:
        snapshot = self.snapshot
        self.changed.emit(snapshot)
        return snapshot


__all__ = ["PythonConsoleController", "PythonConsoleSnapshot"]
