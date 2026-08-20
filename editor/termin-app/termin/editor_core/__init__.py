"""UI-agnostic editor core.

This package holds editor business logic that is independent from any UI
framework. The native frontend delegates to these models and services.

No module in this package may import tcgui or any other UI framework.
"""

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
]
