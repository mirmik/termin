"""Simple event system for observer pattern."""

from __future__ import annotations

from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Event(Generic[T]):
    """
    Simple event class for observer pattern.

    Usage:
        event = Event()
        event += handler          # subscribe
        event -= handler          # unsubscribe
        event.emit(data)          # notify all subscribers
        event.clear()             # remove all subscribers

    Example:
        on_entity_added: Event[Entity] = Event()
        on_entity_added += lambda e: print(f"Added: {e.name}")
        on_entity_added.emit(entity)
    """

    def __init__(self):
        self._handlers: list[Callable[[T], None]] = []

    def __iadd__(self, handler: Callable[[T], None]) -> "Event[T]":
        """Subscribe to event: event += handler"""
        if handler not in self._handlers:
            self._handlers.append(handler)
        return self

    def __isub__(self, handler: Callable[[T], None]) -> "Event[T]":
        """Unsubscribe from event: event -= handler"""
        if handler in self._handlers:
            self._handlers.remove(handler)
        return self

    def emit(self, value: T) -> None:
        """Notify all subscribers."""
        for handler in list(self._handlers):
            handler(value)

    def clear(self) -> None:
        """Remove all subscribers."""
        self._handlers.clear()

    def __len__(self) -> int:
        """Number of subscribers."""
        return len(self._handlers)

    def __bool__(self) -> bool:
        """True if has any subscribers."""
        return len(self._handlers) > 0
