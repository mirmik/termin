"""UI-agnostic editor core.

This package holds editor business logic that is independent from any UI
framework. Qt and tcgui views both delegate to these models and services.

No module in this package may import Qt, tcgui, or any other UI framework.
"""

from pathlib import Path

from .menu_spec import MenuItemSpec, MenuSpec
from .menu_bar_model import build_editor_menu_spec


def scene_name_from_file_path(file_path: str) -> str:
    """Return the scene manager slot name for a scene file path."""
    return Path(file_path).stem


__all__ = [
    "MenuItemSpec",
    "MenuSpec",
    "build_editor_menu_spec",
    "scene_name_from_file_path",
]
