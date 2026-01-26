"""Input event structures.

Re-exports C++ event classes from _entity_native module.
These structures are used for input event dispatch between
the platform layer and C++ components.

Классы событий:
    MouseButtonEvent: событие нажатия/отпускания кнопки мыши
    MouseMoveEvent: событие перемещения мыши
    ScrollEvent: событие прокрутки колеса мыши
    KeyEvent: событие клавиатуры

Константы:
    MouseButton.Left/Right/Middle: кнопки мыши (0, 1, 2)
    Action.Release/Press/Repeat: действия (0, 1, 2)
    Mods.Shift/Ctrl/Alt/Super: модификаторы (1, 2, 4, 8)

Все события содержат поле viewport типа TcViewport (Viewport).
"""

from __future__ import annotations

# Import C++ event classes
from termin.entity._entity_native import (
    MouseButtonEvent,
    MouseMoveEvent,
    ScrollEvent,
    KeyEvent,
    MouseButton,
    Action,
    Mods,
)

# Re-export Viewport for type hints
from termin.viewport import Viewport

__all__ = [
    "MouseButtonEvent",
    "MouseMoveEvent",
    "ScrollEvent",
    "KeyEvent",
    "MouseButton",
    "Action",
    "Mods",
    "Viewport",
]
