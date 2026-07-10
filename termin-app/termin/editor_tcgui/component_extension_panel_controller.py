"""Component editor extension panel lifecycle for EditorWindowTcgui."""

from __future__ import annotations

from typing import Callable

from tcbase import log
from termin.editor_core.component_editor_extension import (
    ComponentEditorExtensionSession,
    ComponentExtensionPresentation,
)


class ComponentExtensionPanelController:
    def __init__(
        self,
        *,
        get_editor: Callable[[], object],
        get_left_tabs: Callable[[], object | None],
        get_inspector_controller: Callable[[], object | None],
    ) -> None:
        self._get_editor = get_editor
        self._get_left_tabs = get_left_tabs
        self._get_inspector_controller = get_inspector_controller
        self._left_tab_index = -1
        self._session = ComponentEditorExtensionSession(
            editor=get_editor,
            presenter=self._build_presentation,
            present=self._present,
            clear_presentation=self._clear_presentation,
        )

    def select_component(self, entity, component_ref) -> None:
        type_name = component_ref.type_name
        self._session.select_component(entity, component_ref, type_name)

    def clear(self) -> None:
        self._session.clear()

    @staticmethod
    def _build_presentation(extension, _type_name: str) -> ComponentExtensionPresentation:
        return ComponentExtensionPresentation(
            right_panel=extension.build_panel(),
            left_panel=extension.build_left_panel(),
        )

    def _present(self, type_name: str, presentation: ComponentExtensionPresentation) -> None:
        self._set_left_panel(self._left_tab_title(type_name), presentation.left_panel)
        inspector_controller = self._get_inspector_controller()
        if inspector_controller is not None:
            inspector_controller.set_component_extension_panel(presentation.right_panel)

    def _clear_presentation(self) -> None:
        self._clear_left_panel()
        inspector_controller = self._get_inspector_controller()
        if inspector_controller is not None:
            inspector_controller.clear_component_extension_panel()

    def _set_left_panel(self, title: str, panel) -> None:
        self._clear_left_panel()
        if panel is None:
            return
        left_tabs = self._get_left_tabs()
        if left_tabs is None:
            log.error(
                "[ComponentExtensionPanelController] cannot attach component left "
                "panel before left tabs exist"
            )
            return
        left_tabs.add_tab(title, panel)
        self._left_tab_index = len(left_tabs.pages) - 1
        left_tabs.selected_index = self._left_tab_index
        if left_tabs._ui is not None:
            left_tabs._ui.request_layout()

    def _clear_left_panel(self) -> None:
        left_tabs = self._get_left_tabs()
        if left_tabs is None:
            self._left_tab_index = -1
            return
        if 0 <= self._left_tab_index < len(left_tabs.pages):
            left_tabs.remove_tab(self._left_tab_index)
            if left_tabs.pages:
                left_tabs.selected_index = min(left_tabs.selected_index, len(left_tabs.pages) - 1)
        self._left_tab_index = -1
        if left_tabs._ui is not None:
            left_tabs._ui.request_layout()

    def _left_tab_title(self, type_name: str) -> str:
        if type_name == "ProceduralMeshComponent":
            return "CSG"
        if type_name.endswith("Component"):
            return type_name[:-9]
        return type_name
