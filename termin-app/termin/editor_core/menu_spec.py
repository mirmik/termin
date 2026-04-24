"""Menu specification data types — UI-framework agnostic.

These classes describe *what* menus and items exist, without depending on any
widget toolkit.  Qt and tcgui controllers each render a ``MenuSpec`` into their
own native menu widgets.
"""

from __future__ import annotations

import dataclasses
from typing import Callable


@dataclasses.dataclass
class MenuItemSpec:
    """A single menu item."""

    label: str
    on_click: Callable[[], None]
    shortcut: str | None = None
    is_checkable: bool = False
    """When True the item shows a check-mark driven by ``state_getter``."""
    state_getter: Callable[[], bool] | None = None
    """Called to read the current checked state (only when ``is_checkable``)."""
    handle_getter: Callable[[object], None] | None = None
    """Called once with the created toolkit-specific handle (QAction / MenuItem).

    The controller uses this so the outer code can hold a reference for later
    state updates (e.g. enabling/disabling Undo, toggling Play/Stop label).
    """


@dataclasses.dataclass
class MenuSpec:
    """A top-level menu (e.g. "File", "Edit")."""

    name: str
    items: list[MenuItemSpec | None]
    """``None`` entries represent separators."""
