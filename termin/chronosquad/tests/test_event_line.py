"""Tests for EventCard and EventLine."""

import pytest
from termin.chronosquad.core import EventCard, EventLine, TimeDirection


class TrackingCard(EventCard):
    """Event card that tracks all callbacks."""

    def __init__(self, start_step: int, finish_step: int | None = None):
        super().__init__(start_step, finish_step)
        self.events: list[str] = []

    def on_forward_enter(self, step: int, ctx) -> None:
        self.events.append(f"forward_enter:{step}")

    def on_forward_leave(self, step: int, ctx) -> None:
        self.events.append(f"forward_leave:{step}")

    def on_backward_enter(self, step: int, ctx) -> None:
        self.events.append(f"backward_enter:{step}")

    def on_backward_leave(self, step: int, ctx) -> None:
        self.events.append(f"backward_leave:{step}")

    def update(self, step: int, ctx) -> None:
        self.events.append(f"update:{step}")


class TestEventCard:
    def test_is_active_at(self):
        card = EventCard(10, 20)
        assert not card.is_active_at(9)
        assert card.is_active_at(10)
        assert card.is_active_at(15)
        assert card.is_active_at(20)
        assert not card.is_active_at(21)

    def test_single_step_card(self):
        card = EventCard(10)
        assert card.start_step == 10
        assert card.finish_step == 10
        assert card.is_active_at(10)
        assert not card.is_active_at(9)
        assert not card.is_active_at(11)


class TestEventLine:
    def test_add_and_count(self):
        line = EventLine()
        assert line.count() == 0

        line.add(EventCard(10, 20))
        assert line.count() == 1

        line.add(EventCard(30, 40))
        assert line.count() == 2

    def test_promote_forward(self):
        line = EventLine()
        card = TrackingCard(10, 20)
        line.add(card)

        # Move to step 10 - should enter
        line.promote(10, None)
        assert "forward_enter:10" in card.events
        assert "update:10" in card.events

        # Move to step 15 - should update
        card.events.clear()
        line.promote(15, None)
        assert "update:15" in card.events

        # Move to step 21 - should leave
        card.events.clear()
        line.promote(21, None)
        assert "forward_leave:21" in card.events

    def test_promote_backward(self):
        line = EventLine()
        card = TrackingCard(10, 20)
        line.add(card)

        # First go forward past the card
        line.promote(25, None)
        card.events.clear()

        # Now go backward into the card
        line.promote(15, None)
        assert "backward_enter:20" in card.events

        # Go backward out of the card
        card.events.clear()
        line.promote(5, None)
        # Leave is triggered at step 9 (first step outside range 10-20)
        assert "backward_leave:9" in card.events

    def test_active_cards(self):
        line = EventLine()
        card1 = EventCard(10, 20)
        card2 = EventCard(15, 25)
        line.add(card1)
        line.add(card2)

        line.promote(12, None)
        active = line.active_cards()
        assert len(active) == 1
        assert card1 in active

        line.promote(18, None)
        active = line.active_cards()
        assert len(active) == 2
        assert card1 in active
        assert card2 in active

        line.promote(22, None)
        active = line.active_cards()
        assert len(active) == 1
        assert card2 in active

    def test_drop_future(self):
        line = EventLine()
        line.add(EventCard(10, 20))
        line.add(EventCard(50, 60))
        line.add(EventCard(100, 110))

        line.promote(30, None)
        assert line.count() == 3

        line.drop_future()
        assert line.count() == 1  # Only card starting at 10 remains

    def test_copy(self):
        line = EventLine()
        line.add(EventCard(10, 20))
        line.promote(15, None)

        copy = line.copy()
        assert copy.count() == 1
        assert copy.current_step() == 15
        assert len(copy.active_cards()) == 1

        # Modifying copy shouldn't affect original
        copy.promote(25, None)
        assert line.current_step() == 15
        assert copy.current_step() == 25
