"""Supported project-extension surface for the native editor frontend."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging

from termin.gui_native import CommandModel, MenuBarEntry


_logger = logging.getLogger(__name__)


@dataclass
class NativeProjectEditorContext:
    """Public context passed to project ``InitScript.py`` files.

    Project extensions use this facade instead of reaching into the native
    editor shell, viewport or inspector implementations. The facade owns menu
    registrations and delegates toolkit-neutral viewport tools to the same hub
    used by built-in component extensions.
    """

    document: object
    menu_bar: object
    dialog_service: object
    viewport: Callable[[], object]
    request_render: Callable[[], None]
    extension_context: object
    get_scene: Callable[[], object | None]
    get_selected_entity: Callable[[], object | None]
    select_scene_object: Callable[[object | None], None]
    frontend: str = field(default="native", init=False)
    _menu_models: list[CommandModel] = field(default_factory=list, init=False)
    _menu_connections: list[object] = field(default_factory=list, init=False)
    _single_click_interceptor: Callable[[object], bool] | None = field(
        default=None,
        init=False,
    )

    @property
    def scene(self):
        return self.get_scene()

    @property
    def selected_entity(self):
        return self.get_selected_entity()

    def add_project_menu(
        self,
        stable_id: str,
        label: str,
        model: CommandModel,
        on_activated: Callable[[int, object], None],
    ) -> int:
        if not stable_id or not label:
            raise ValueError("project menu stable_id and label must not be empty")
        entries = list(self.menu_bar.entries)
        if any(entry.stable_id == stable_id for entry in entries):
            raise ValueError(f"project menu is already registered: {stable_id}")
        menu_index = len(entries)
        entries.append(MenuBarEntry(stable_id, label, model))
        self.menu_bar.entries = entries

        def activated(index: int, command_id: int, command) -> None:
            if index == menu_index:
                on_activated(command_id, command)

        self._menu_models.append(model)
        self._menu_connections.append(self.menu_bar.connect_activated(activated))
        self.request_render()
        return menu_index

    def show_dialog(self, dialog) -> bool:
        shown = bool(dialog.show(self.viewport()))
        if shown:
            self.request_render()
        return shown

    def show_error(self, title: str, message: str) -> None:
        self.dialog_service.show_error(title, message)

    def set_viewport_click_interceptor(
        self,
        callback: Callable[[object], bool] | None,
    ) -> None:
        previous = self._single_click_interceptor
        if previous is not None:
            self.extension_context.remove_viewport_click_interceptor(previous)
        self._single_click_interceptor = callback
        if callback is not None:
            self.extension_context.add_viewport_click_interceptor(callback)

    def add_viewport_click_interceptor(self, callback: Callable[[object], bool]) -> None:
        self.extension_context.add_viewport_click_interceptor(callback)

    def remove_viewport_click_interceptor(self, callback: Callable[[object], bool]) -> None:
        self.extension_context.remove_viewport_click_interceptor(callback)

    def add_viewport_overlay_drawer(self, callback: Callable[[], None]) -> None:
        self.extension_context.add_viewport_overlay_drawer(callback)

    def remove_viewport_overlay_drawer(self, callback: Callable[[], None]) -> None:
        self.extension_context.remove_viewport_overlay_drawer(callback)

    def begin_viewport_tool(self) -> None:
        self.extension_context.begin_viewport_tool()

    def end_viewport_tool(self) -> None:
        self.extension_context.end_viewport_tool()

    def request_viewport_update(self) -> None:
        self.request_render()

    def select_entity(self, entity: object | None) -> None:
        self.select_scene_object(entity)


__all__ = ["NativeProjectEditorContext"]
