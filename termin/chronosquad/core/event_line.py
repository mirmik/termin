"""
Event system for time-reversible game logic.

EventCard - base class for events that happen at specific time steps.
EventLine - container for EventCards with forward/backward time support.
"""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar, Callable
from dataclasses import dataclass, field


class TimeDirection(Enum):
    Forward = 1
    Backward = -1


T = TypeVar('T')


class EventCard(Generic[T]):
    """
    Base class for events that occur within a time range.

    Events have start_step and finish_step. When timeline crosses these
    boundaries, appropriate callbacks are triggered.
    """

    def __init__(self, start_step: int, finish_step: int | None = None):
        self.start_step = start_step
        self.finish_step = finish_step if finish_step is not None else start_step

    def on_forward_enter(self, current_step: int, context: T) -> None:
        """Called when entering event range while moving forward in time."""
        pass

    def on_forward_leave(self, current_step: int, context: T) -> None:
        """Called when leaving event range while moving forward in time."""
        pass

    def on_backward_enter(self, current_step: int, context: T) -> None:
        """Called when entering event range while moving backward in time."""
        pass

    def on_backward_leave(self, current_step: int, context: T) -> None:
        """Called when leaving event range while moving backward in time."""
        pass

    def on_enter(self, current_step: int, context: T) -> None:
        """Called when entering event range (any direction)."""
        pass

    def on_leave(self, current_step: int, context: T) -> None:
        """Called when leaving event range (any direction)."""
        pass

    def update(self, current_step: int, context: T) -> None:
        """Called every step while event is active."""
        pass

    def is_active_at(self, step: int) -> bool:
        """Check if event is active at given step."""
        return self.start_step <= step <= self.finish_step

    def hash_code(self) -> int:
        """Return hash for event comparison."""
        return hash((self.start_step, self.finish_step, type(self).__name__))

    def copy(self) -> EventCard[T]:
        """Create a copy of this event."""
        new_card = type(self).__new__(type(self))
        new_card.start_step = self.start_step
        new_card.finish_step = self.finish_step
        return new_card


class EventLine(Generic[T]):
    """
    Container for EventCards with forward/backward time promotion.

    Tracks which events are currently active and triggers appropriate
    callbacks when events enter/leave active state.
    """

    def __init__(self):
        self._cards: list[EventCard[T]] = []
        self._active: set[int] = set()  # indices of active cards
        self._current_step: int = 0

    def add(self, card: EventCard[T]) -> None:
        """Add an event card."""
        self._cards.append(card)
        # Check if it should be immediately active
        if card.is_active_at(self._current_step):
            self._active.add(len(self._cards) - 1)

    def remove(self, card: EventCard[T]) -> None:
        """Remove an event card."""
        try:
            idx = self._cards.index(card)
            self._cards.pop(idx)
            self._active.discard(idx)
            # Reindex active set
            self._active = {i if i < idx else i - 1 for i in self._active if i != idx}
        except ValueError:
            pass

    def promote(self, target_step: int, context: T) -> None:
        """
        Move to target_step, triggering enter/leave callbacks.
        """
        if target_step == self._current_step:
            # Just update active cards
            for idx in self._active:
                self._cards[idx].update(self._current_step, context)
            return

        direction = TimeDirection.Forward if target_step > self._current_step else TimeDirection.Backward
        step_delta = 1 if direction == TimeDirection.Forward else -1

        while self._current_step != target_step:
            self._current_step += step_delta
            self._process_step(self._current_step, direction, context)

    def _process_step(self, step: int, direction: TimeDirection, context: T) -> None:
        """Process a single step, triggering callbacks."""
        entered: list[EventCard[T]] = []
        left: list[EventCard[T]] = []

        for idx, card in enumerate(self._cards):
            was_active = idx in self._active
            is_active = card.is_active_at(step)

            if is_active and not was_active:
                self._active.add(idx)
                entered.append(card)
            elif was_active and not is_active:
                self._active.discard(idx)
                left.append(card)

        # Trigger enter callbacks
        for card in entered:
            if direction == TimeDirection.Forward:
                card.on_forward_enter(step, context)
            else:
                card.on_backward_enter(step, context)
            card.on_enter(step, context)

        # Trigger leave callbacks
        for card in left:
            if direction == TimeDirection.Forward:
                card.on_forward_leave(step, context)
            else:
                card.on_backward_leave(step, context)
            card.on_leave(step, context)

        # Update active cards
        for idx in self._active:
            self._cards[idx].update(step, context)

    def active_cards(self) -> list[EventCard[T]]:
        """Return list of currently active cards."""
        return [self._cards[idx] for idx in self._active]

    def current_step(self) -> int:
        return self._current_step

    def count(self) -> int:
        return len(self._cards)

    def drop_future(self) -> None:
        """Remove all cards that start after current step."""
        to_remove = []
        for idx, card in enumerate(self._cards):
            if card.start_step > self._current_step:
                to_remove.append(idx)

        for idx in reversed(to_remove):
            self._cards.pop(idx)
            self._active.discard(idx)

    def copy(self) -> EventLine[T]:
        """Create a deep copy of this event line."""
        new_line = EventLine[T]()
        new_line._current_step = self._current_step
        new_line._cards = [card.copy() for card in self._cards]
        new_line._active = self._active.copy()
        return new_line
