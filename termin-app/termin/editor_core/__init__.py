"""UI-agnostic editor core.

This package holds editor business logic that is independent from any UI
framework. Qt and tcgui views both delegate to these models and services.

No module in this package may import Qt, tcgui, or any other UI framework.
"""

from .menu_spec import MenuItemSpec, MenuSpec
from .menu_bar_model import build_editor_menu_spec

__all__ = [
    "MenuItemSpec",
    "MenuSpec",
    "build_editor_menu_spec",
]
