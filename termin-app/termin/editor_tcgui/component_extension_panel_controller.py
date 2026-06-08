"""Component editor extension panel lifecycle for EditorWindowTcgui."""

from __future__ import annotations

from typing import Callable

from tcbase import log


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
        self._active_extension = None
        self._left_tab_index = -1

    def select_component(self, entity, component_ref) -> None:
        self.clear()
        type_name = component_ref.type_name
        from termin.editor_tcgui.component_editor_extension import (
            create_component_editor_extension,
        )

        extension = create_component_editor_extension(type_name)
        if extension is None:
            return

        try:
            extension.attach(self._get_editor(), entity, component_ref)
            panel = extension.build_panel()
            left_panel = extension.build_left_panel()
        except Exception as e:
            log.error(
                "[ComponentExtensionPanelController] component editor extension attach failed "
                f"for '{type_name}': {e}"
            )
            self._detach_after_attach_error(extension, type_name)
            return

        self._active_extension = extension
        self._set_left_panel(self._left_tab_title(type_name), left_panel)
        inspector_controller = self._get_inspector_controller()
        if inspector_controller is not None:
            inspector_controller.set_component_extension_panel(panel)

    def clear(self) -> None:
        extension = self._active_extension
        self._active_extension = None
        self._clear_left_panel()
        inspector_controller = self._get_inspector_controller()
        if inspector_controller is not None:
            inspector_controller.clear_component_extension_panel()
        if extension is None:
            return
        try:
            extension.detach()
        except Exception as e:
            log.error(
                "[ComponentExtensionPanelController] component editor extension detach "
                f"failed: {e}"
            )

    def _detach_after_attach_error(self, extension, type_name: str) -> None:
        try:
            extension.detach()
        except Exception as detach_error:
            log.error(
                "[ComponentExtensionPanelController] component editor extension detach failed "
                f"after attach error for '{type_name}': {detach_error}"
            )

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
