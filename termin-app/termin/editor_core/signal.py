"""Signal — minimal pub/sub primitive for UI-agnostic models."""
from __future__ import annotations

from typing import Callable


class Signal:
    """Observable event. Listeners are plain callables.

    Iterating a copy inside ``emit`` makes it safe for listeners to
    disconnect themselves during dispatch.
    """

    _listeners: list[Callable]

    def __init__(self):
        self._listeners = []

    def connect(self, callback: Callable) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def disconnect(self, callback: Callable) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def emit(self, *args, **kwargs) -> None:
        for listener in list(self._listeners):
            listener(*args, **kwargs)
