"""Prefab editing toolbar presentation for EditorWindowTcgui."""

from __future__ import annotations


class PrefabToolbarController:
    def __init__(self) -> None:
        self._prefab_toolbar = None
        self._prefab_toolbar_label = None
        self._play_button = None

    def set_widgets(
        self,
        *,
        prefab_toolbar,
        prefab_toolbar_label,
        play_button,
    ) -> None:
        self._prefab_toolbar = prefab_toolbar
        self._prefab_toolbar_label = prefab_toolbar_label
        self._play_button = play_button

    def set_editing(self, is_editing: bool, prefab_name: str | None) -> None:
        if self._prefab_toolbar is not None:
            self._prefab_toolbar.visible = is_editing
        if is_editing and self._prefab_toolbar_label is not None:
            self._prefab_toolbar_label.text = f"Editing Prefab: {prefab_name or ''}"
        if self._play_button is not None:
            self._play_button.enabled = not is_editing
