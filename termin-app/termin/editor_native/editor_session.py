"""Explicit lifetime boundary for one production native editor frontend."""

from __future__ import annotations

from collections.abc import Callable


class EditorSession:
    """Own the engine loop connection and all frontend teardown work."""

    def __init__(self, loop_connection, close_editor: Callable[[], None]) -> None:
        self._loop_connection = loop_connection
        self._close_editor = close_editor
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        loop_connection = self._loop_connection
        self._loop_connection = None
        close_editor = self._close_editor
        self._close_editor = None

        loop_connection.detach()
        close_editor()


__all__ = ["EditorSession"]
