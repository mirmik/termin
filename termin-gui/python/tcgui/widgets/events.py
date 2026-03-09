"""Event dataclasses for the UI system.

Each event type wraps the parameters of a particular input event
into a single immutable structure, using ``tcbase`` enums for
button IDs and modifier keys.
"""

from __future__ import annotations

from dataclasses import dataclass

from tcbase import Key, MouseButton, Mods


@dataclass(frozen=True, slots=True)
class MouseEvent:
    """Mouse button / position event (down, up, move)."""
    x: float
    y: float
    button: MouseButton = MouseButton.LEFT
    mods: int = 0  # bitmask of Mods values

    @property
    def shift(self) -> bool:
        return bool(self.mods & Mods.SHIFT.value)

    @property
    def ctrl(self) -> bool:
        return bool(self.mods & Mods.CTRL.value)

    @property
    def alt(self) -> bool:
        return bool(self.mods & Mods.ALT.value)


@dataclass(frozen=True, slots=True)
class MouseWheelEvent:
    """Mouse wheel / scroll event."""
    dx: float
    dy: float
    x: float  # cursor x at scroll time
    y: float  # cursor y at scroll time


@dataclass(frozen=True, slots=True)
class KeyEvent:
    """Keyboard key-down event."""
    key: Key
    mods: int = 0  # bitmask of Mods values

    @property
    def shift(self) -> bool:
        return bool(self.mods & Mods.SHIFT.value)

    @property
    def ctrl(self) -> bool:
        return bool(self.mods & Mods.CTRL.value)

    @property
    def alt(self) -> bool:
        return bool(self.mods & Mods.ALT.value)


@dataclass(frozen=True, slots=True)
class TextEvent:
    """Text input event (character/string entered)."""
    text: str
