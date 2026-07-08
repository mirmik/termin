"""UI-agnostic editor core.

This package holds editor business logic that is independent from any UI
framework. The tcgui frontend delegates to these models and services.

No module in this package may import tcgui or any other UI framework.
"""

from pathlib import Path

from .menu_spec import MenuItemSpec, MenuSpec
from .menu_bar_model import (
    DebugMenuActions,
    EditMenuActions,
    EditorMenuActions,
    EditorMenuHandleSetters,
    EditorMenuSpecConfig,
    EditorMenuStateGetters,
    FileMenuActions,
    GameMenuActions,
    HelpMenuActions,
    NavigationMenuActions,
    SceneMenuActions,
    ViewMenuActions,
    build_editor_menu_spec,
)


def scene_name_from_file_path(file_path: str) -> str:
    """Return the scene manager slot name for a scene file path."""
    return Path(file_path).stem


__all__ = [
    "MenuItemSpec",
    "MenuSpec",
    "DebugMenuActions",
    "EditMenuActions",
    "EditorMenuActions",
    "EditorMenuHandleSetters",
    "EditorMenuSpecConfig",
    "EditorMenuStateGetters",
    "FileMenuActions",
    "GameMenuActions",
    "HelpMenuActions",
    "NavigationMenuActions",
    "SceneMenuActions",
    "ViewMenuActions",
    "build_editor_menu_spec",
    "scene_name_from_file_path",
]
