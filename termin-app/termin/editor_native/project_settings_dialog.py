"""Native project settings dialog over the shared project settings controller."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable
import weakref

from termin.editor_core.project_settings_model import (
    ProjectSettingsController,
    ProjectSettingsSnapshot,
    RENDER_SYNC_MODES,
)
from termin.gui_native import DialogAction, Document, EdgeInsets, Rect, Size, WidgetRef

from .dialog_service import NativeDialogService


_logger = logging.getLogger(__name__)


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


def _row(document: Document, label: str, control, *, label_width: float = 150.0) -> WidgetRef:
    row = document.create_hstack(f"project-settings-{label.lower().replace(' ', '-')}")
    row.set_layout_spacing(4.0)
    row.add_fixed_child(document.create_label(label), label_width)
    row.add_stretch_child(_ref(document, control))
    return row


@dataclass
class NativeProjectSettingsDialog:
    document: Document
    controller: ProjectSettingsController
    dialog_service: NativeDialogService
    dialog: object
    render_sync: object
    build_output: object
    player_width: object
    player_height: object
    player_fullscreen: object
    ignored_paths: object
    status: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    _updating: bool = False
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native project settings dialog is closed")
        if self.dialog.open:
            return False
        try:
            self.apply_snapshot(self.controller.load())
        except RuntimeError as error:
            self.dialog_service.show_error("Project Settings", str(error))
            return False
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def snapshot(self) -> ProjectSettingsSnapshot:
        index = self.render_sync.selected_index
        if not 0 <= index < len(RENDER_SYNC_MODES):
            raise ValueError("render sync mode selection is invalid")
        return ProjectSettingsSnapshot(
            render_sync_mode=RENDER_SYNC_MODES[index],
            build_output_dir=self.build_output.text,
            player_width=int(self.player_width.value),
            player_height=int(self.player_height.value),
            player_fullscreen=bool(self.player_fullscreen.checked),
            ignored_resource_paths=tuple(
                line.strip() for line in self.ignored_paths.text.splitlines() if line.strip()
            ),
        )

    def apply_snapshot(self, snapshot: ProjectSettingsSnapshot) -> None:
        self._updating = True
        try:
            self.render_sync.selected_index = RENDER_SYNC_MODES.index(snapshot.render_sync_mode)
            self.build_output.text = snapshot.build_output_dir
            self.player_width.value = snapshot.player_width
            self.player_height.value = snapshot.player_height
            self.player_fullscreen.checked = snapshot.player_fullscreen
            self.ignored_paths.text = "\n".join(snapshot.ignored_resource_paths)
            self.status.text = "Project settings are stored in project_settings/project.json"
        finally:
            self._updating = False

    def apply_render_sync(self, index: int) -> None:
        if self._updating or not 0 <= index < len(RENDER_SYNC_MODES):
            return
        self.controller.set_render_sync_mode(RENDER_SYNC_MODES[index])
        self.status.text = "Render sync mode saved"
        self.request_render()

    def apply_player_window(self) -> None:
        if self._updating:
            return
        self.controller.set_player_window(
            int(self.player_width.value),
            int(self.player_height.value),
            self.player_fullscreen.checked,
        )
        self.status.text = "Player window saved"
        self.request_render()

    def save(self) -> ProjectSettingsSnapshot:
        snapshot = self.controller.save(self.snapshot())
        self.apply_snapshot(snapshot)
        self.status.text = "Saved"
        self.request_render()
        return snapshot

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


def build_native_project_settings_dialog(
    document: Document,
    controller: ProjectSettingsController,
    *,
    dialog_service: NativeDialogService,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
) -> NativeProjectSettingsDialog:
    root = document.create_vstack("native-project-settings")
    root.stable_id = "editor.project-settings"
    root.preferred_size = Size(620.0, 520.0)
    root.set_layout_padding(EdgeInsets(8.0, 8.0, 8.0, 8.0))
    root.set_layout_spacing(6.0)
    render_sync = document.create_combo_box()
    for mode in RENDER_SYNC_MODES:
        render_sync.add_item(mode.value.capitalize())
    root.add_fixed_child(_row(document, "Render Sync Mode", render_sync), 30.0)
    build_output = document.create_text_input()
    root.add_fixed_child(_row(document, "Build Output Dir", build_output), 30.0)
    width = document.create_spin_box()
    width.set_range(1.0, 16384.0)
    width.step = 16.0
    width.decimals = 0
    root.add_fixed_child(_row(document, "Player Width", width), 30.0)
    height = document.create_spin_box()
    height.set_range(1.0, 16384.0)
    height.step = 16.0
    height.decimals = 0
    root.add_fixed_child(_row(document, "Player Height", height), 30.0)
    fullscreen_row = document.create_hstack("project-settings-fullscreen")
    fullscreen_row.add_stretch_child(document.create_label("Player Fullscreen"))
    fullscreen = document.create_checkbox(False)
    fullscreen_row.add_fixed_child(_ref(document, fullscreen), 30.0)
    root.add_fixed_child(fullscreen_row, 30.0)
    root.add_fixed_child(document.create_label("Ignored Resource Paths"), 24.0)
    ignored = document.create_text_area()
    root.add_stretch_child(_ref(document, ignored))
    status = document.create_status_bar("Project settings")
    root.add_fixed_child(_ref(document, status), 24.0)
    dialog = document.create_dialog("Project Settings")
    dialog.actions = [DialogAction("close", "Close", is_default=True, is_cancel=True)]
    dialog.set_content(root)
    result = NativeProjectSettingsDialog(
        document,
        controller,
        dialog_service,
        dialog,
        render_sync,
        build_output,
        width,
        height,
        fullscreen,
        ignored,
        status,
        viewport,
        request_render,
    )
    weak_result = weakref.ref(result)

    def owner() -> NativeProjectSettingsDialog | None:
        return weak_result()

    render_sync.connect_changed(
        lambda index, _text: owner().apply_render_sync(index) if owner() is not None else None
    )
    width.connect_changed(
        lambda _value: owner().apply_player_window() if owner() is not None else None
    )
    height.connect_changed(
        lambda _value: owner().apply_player_window() if owner() is not None else None
    )
    fullscreen.connect_changed(
        lambda _value: owner().apply_player_window() if owner() is not None else None
    )

    def finished(_dialog_result) -> None:
        current = owner()
        if current is None:
            return
        try:
            current.save()
        except Exception as error:
            _logger.exception("Native project settings save failed")
            current.dialog_service.show_error("Project Settings", f"Save failed: {error}")

    dialog.connect_finished(finished)
    return result


def connect_project_settings_command(menu_bar, command_id: int, dialog) -> None:
    weak_dialog = weakref.ref(dialog)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        owner = weak_dialog()
        if activated_id == command_id and owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeProjectSettingsDialog",
    "build_native_project_settings_dialog",
    "connect_project_settings_command",
]
