"""Event dataclasses for the UI system.

Each event type wraps the parameters of a particular input event
into a single immutable structure, using ``tcbase`` enums for
button IDs and modifier keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True, slots=True)
class DragPayload:
    """Typed drag payload passed between source and drop target widgets."""
    kind: str
    data: Any


@dataclass(frozen=True, slots=True)
class DragEvent:
    """Drag/drop event with current cursor position and source payload."""
    x: float
    y: float
    payload: DragPayload
    source: object | None = None
    mods: int = 0
