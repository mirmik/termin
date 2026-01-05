"""ChronoSquad menu for editor."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMenuBar, QMenu

_chronosphere_viewer = None
_menu: "QMenu | None" = None


def install_menu() -> None:
    """Install ChronoSquad menu into editor."""
    from termin.editor.editor_window import EditorWindow

    editor = EditorWindow.instance()
    if editor is None:
        print("[ChronoSquad] EditorWindow not found")
        return

    global _menu
    if _menu is not None:
        return  # Already installed

    menu_bar = editor.menuBar()
    _menu = menu_bar.addMenu("ChronoSquad")

    # Chronosphere Viewer
    viewer_action = _menu.addAction("Chronosphere Viewer...")
    viewer_action.triggered.connect(_show_chronosphere_viewer)

    print("[ChronoSquad] Menu installed")


def uninstall_menu() -> None:
    """Remove ChronoSquad menu from editor."""
    from termin.editor.editor_window import EditorWindow

    global _menu, _chronosphere_viewer

    if _menu is None:
        return

    editor = EditorWindow.instance()
    if editor is not None:
        menu_bar = editor.menuBar()
        menu_bar.removeAction(_menu.menuAction())

    _menu = None

    if _chronosphere_viewer is not None:
        _chronosphere_viewer.close()
        _chronosphere_viewer = None


def _show_chronosphere_viewer():
    """Show the Chronosphere Viewer window."""
    from .chronosphere_viewer import ChronosphereViewer

    global _chronosphere_viewer

    if _chronosphere_viewer is None:
        _chronosphere_viewer = ChronosphereViewer()

    _chronosphere_viewer.show()
    _chronosphere_viewer.raise_()
    _chronosphere_viewer.refresh()


def _get_chronosphere_controller():
    """Find ChronosphereController in current scene."""
    from termin.editor.editor_window import EditorWindow
    from termin.chronosquad.controllers import ChronosphereController

    editor = EditorWindow.instance()
    if editor is None:
        return None

    scene = editor.world_persistence.scene
    if scene is None:
        return None

    for entity in scene.entities:
        ctrl = entity.get_component(ChronosphereController)
        if ctrl is not None:
            return ctrl

    return None
