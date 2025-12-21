"""Input event structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.core.viewport import Viewport


@dataclass
class MouseButtonEvent:
    """Mouse button press/release event."""
    viewport: "Viewport"
    x: float
    y: float
    button: int
    action: int
    mods: int


@dataclass
class MouseMoveEvent:
    """Mouse movement event."""
    viewport: "Viewport"
    x: float
    y: float
    dx: float
    dy: float


@dataclass
class ScrollEvent:
    """Mouse scroll event."""
    viewport: "Viewport"
    x: float
    y: float
    xoffset: float
    yoffset: float


@dataclass
class KeyEvent:
    """Keyboard event."""
    viewport: "Viewport"
    key: int
    scancode: int
    action: int
    mods: int
