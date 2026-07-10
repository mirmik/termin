"""Native Scene Manager viewer and action dialog."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import weakref

from termin.editor_core.scene_manager_model import (
    SceneManagerController,
    SceneManagerSnapshot,
    SceneMode,
)
from termin.gui_native import DialogAction, Document, EdgeInsets, Rect, Size, WidgetRef

from .dialog_service import NativeDialogService


def _ref(document: Document, widget) -> WidgetRef:
    return widget if isinstance(widget, WidgetRef) else document.ref(widget.handle)


@dataclass
class NativeSceneManagerDialog:
    document: Document
    controller: SceneManagerController
    dialog_service: NativeDialogService
    dialog: object
    scenes: object
    details: object
    status: object
    action_buttons: tuple[object, ...]
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    snapshot: SceneManagerSnapshot | None = None
    _updating: bool = False
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native Scene Manager dialog is closed")
        if self.dialog.open:
            return False
        self.apply_snapshot(self.controller.refresh())
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def apply_snapshot(self, snapshot: SceneManagerSnapshot) -> None:
        self.snapshot = snapshot
        self._updating = True
        try:
            self.scenes.clear()
            selected_index = -1
            for index, scene in enumerate(snapshot.scenes):
                self.scenes.add_item(
                    f"{scene.display_name} | {scene.mode} | {scene.entity_count} | {scene.handle}"
                )
                if scene.name == snapshot.selected_name:
                    selected_index = index
            self.scenes.selected_index = selected_index
            selected = self.selected_scene()
            self.details.text = "" if selected is None else selected.details
            self.status.set_text(
                f"Scenes: {len(snapshot.scenes)} | Entities: {snapshot.total_entities} | "
                f"Playing: {snapshot.playing_count}"
            )
            for button in self.action_buttons:
                button.widget.enabled = selected is not None
            self.action_buttons[5].widget.enabled = selected is not None and self.controller.can_render_attach
            self.action_buttons[6].widget.enabled = selected is not None and self.controller.can_render_detach
            self.action_buttons[7].widget.enabled = selected is not None and self.controller.can_editor_attach
            self.action_buttons[8].widget.enabled = self.controller.can_editor_detach
        finally:
            self._updating = False
        self.request_render()

    def selected_scene(self):
        if self.snapshot is None or self.snapshot.selected_name is None:
            return None
        return next(
            (item for item in self.snapshot.scenes if item.name == self.snapshot.selected_name),
            None,
        )

    def select(self, index: int) -> None:
        if self._updating or self.snapshot is None:
            return
        name = self.snapshot.scenes[index].name if 0 <= index < len(self.snapshot.scenes) else None
        self.perform(lambda: self.controller.select(name))

    def perform(self, action) -> None:
        try:
            self.apply_snapshot(action())
        except Exception as error:
            self.dialog_service.show_error("Scene Manager", str(error))

    def duplicate(self) -> None:
        selected = self.selected_scene()
        if selected is None:
            return
        owner = weakref.ref(self)

        def accepted(value: str | None) -> None:
            current = owner()
            if current is not None and value is not None:
                current.perform(lambda: current.controller.duplicate_selected(value))

        self.dialog_service.show_input(
            "Duplicate Scene",
            f"Enter name for copy of '{selected.name}':",
            f"{selected.name}_copy",
            accepted,
        )

    def unload(self) -> None:
        selected = self.selected_scene()
        if selected is None:
            return
        owner = weakref.ref(self)

        def accepted(value: str | None) -> None:
            current = owner()
            if current is not None and value == "Unload":
                current.perform(current.controller.unload_selected)

        self.dialog_service.show_choice(
            "Confirm Unload",
            f"Close scene '{selected.name}'? Unsaved changes will be lost.",
            ["Unload", "Cancel"],
            accepted,
            default="Cancel",
            cancel="Cancel",
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


def build_native_scene_manager_dialog(document, controller, *, dialog_service, viewport, request_render):
    root = document.create_vstack("native-scene-manager")
    root.stable_id = "editor.scene-manager"
    root.preferred_size = Size(860.0, 610.0)
    root.set_layout_padding(EdgeInsets(8.0, 8.0, 8.0, 8.0))
    root.set_layout_spacing(5.0)
    scenes = document.create_combo_box()
    root.add_fixed_child(_ref(document, scenes), 30.0)
    details = document.create_text_area()
    root.add_stretch_child(_ref(document, details))
    status = document.create_button("")
    status.widget.enabled = False
    root.add_fixed_child(_ref(document, status), 24.0)
    action_row = document.create_hstack("scene-manager-actions")
    action_row.set_layout_spacing(4.0)
    labels = (
        "Unload", "Duplicate", "Inactive", "Stop", "Play",
        "Render Attach", "Render Detach", "Editor Attach", "Editor Detach", "Refresh",
    )
    buttons = tuple(document.create_button(label) for label in labels)
    for button in buttons:
        action_row.add_stretch_child(_ref(document, button))
    root.add_fixed_child(action_row, 34.0)
    dialog = document.create_dialog("Scene Manager")
    dialog.actions = [DialogAction("close", "Close", is_default=True, is_cancel=True)]
    dialog.set_content(root)
    result = NativeSceneManagerDialog(
        document, controller, dialog_service, dialog, scenes, details, status,
        buttons[:9], viewport, request_render,
    )
    owner = weakref.ref(result)
    scenes.connect_changed(
        lambda index, _text: owner().select(index) if owner() is not None else None
    )
    actions = (
        lambda value: value.unload(),
        lambda value: value.duplicate(),
        lambda value: value.perform(lambda: value.controller.set_selected_mode(SceneMode.INACTIVE)),
        lambda value: value.perform(lambda: value.controller.set_selected_mode(SceneMode.STOP)),
        lambda value: value.perform(lambda: value.controller.set_selected_mode(SceneMode.PLAY)),
        lambda value: value.perform(value.controller.render_attach_selected),
        lambda value: value.perform(value.controller.render_detach_selected),
        lambda value: value.perform(value.controller.editor_attach_selected),
        lambda value: value.perform(value.controller.editor_detach),
        lambda value: value.perform(value.controller.refresh),
    )
    for button, action in zip(buttons, actions, strict=True):
        button.connect_clicked(
            lambda selected=action: selected(owner()) if owner() is not None else None
        )
    return result


def connect_scene_manager_command(menu_bar, command_id: int, dialog) -> None:
    owner = weakref.ref(dialog)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        current = owner()
        if activated_id == command_id and current is not None:
            current.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeSceneManagerDialog", "build_native_scene_manager_dialog",
    "connect_scene_manager_command",
]
