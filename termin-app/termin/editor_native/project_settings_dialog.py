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
from termin.gui_native import DialogAction, Document, Rect, Size, WidgetRef

from .dialog_service import NativeDialogService
from .metrics import EDITOR_UI_METRICS


_logger = logging.getLogger(__name__)


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


def _row(document: Document, label: str, control) -> WidgetRef:
    row = document.create_hstack(f"project-settings-{label.lower().replace(' ', '-')}")
    row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    row.add_fixed_child(document.create_label(label), EDITOR_UI_METRICS.form_label)
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
    player_vsync: object
    ignored_paths: object
    render_phases: object
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
            player_vsync=bool(self.player_vsync.checked),
            ignored_resource_paths=tuple(
                line.strip() for line in self.ignored_paths.text.splitlines() if line.strip()
            ),
            render_phase_names=tuple(self.render_phases.text.split("\n")),
        )

    def apply_snapshot(self, snapshot: ProjectSettingsSnapshot) -> None:
        self._updating = True
        try:
            self.render_sync.selected_index = RENDER_SYNC_MODES.index(snapshot.render_sync_mode)
            self.build_output.text = snapshot.build_output_dir
            self.player_width.value = snapshot.player_width
            self.player_height.value = snapshot.player_height
            self.player_fullscreen.checked = snapshot.player_fullscreen
            self.player_vsync.checked = snapshot.player_vsync
            self.ignored_paths.text = "\n".join(snapshot.ignored_resource_paths)
            self.render_phases.text = "\n".join(snapshot.render_phase_names)
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
            self.player_vsync.checked,
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
    root.set_layout_padding(EDITOR_UI_METRICS.dialog_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.dialog_spacing)
    render_sync = document.create_combo_box()
    for mode in RENDER_SYNC_MODES:
        render_sync.add_item(mode.value.capitalize())
    root.add_fixed_child(_row(document, "Render Sync Mode", render_sync), EDITOR_UI_METRICS.field_row)
    build_output = document.create_text_input()
    root.add_fixed_child(_row(document, "Build Output Dir", build_output), EDITOR_UI_METRICS.field_row)
    width = document.create_spin_box()
    width.set_range(1.0, 16384.0)
    width.step = 16.0
    width.decimals = 0
    root.add_fixed_child(_row(document, "Player Width", width), EDITOR_UI_METRICS.field_row)
    height = document.create_spin_box()
    height.set_range(1.0, 16384.0)
    height.step = 16.0
    height.decimals = 0
    root.add_fixed_child(_row(document, "Player Height", height), EDITOR_UI_METRICS.field_row)
    fullscreen_row = document.create_hstack("project-settings-fullscreen")
    fullscreen_row.add_stretch_child(document.create_label("Player Fullscreen"))
    fullscreen = document.create_checkbox(False)
    fullscreen_row.add_fixed_child(_ref(document, fullscreen), 30.0)
    root.add_fixed_child(fullscreen_row, EDITOR_UI_METRICS.field_row)
    vsync_row = document.create_hstack("project-settings-vsync")
    vsync_row.add_stretch_child(document.create_label("Player VSync"))
    vsync = document.create_checkbox(True)
    vsync_row.add_fixed_child(_ref(document, vsync), 30.0)
    root.add_fixed_child(vsync_row, EDITOR_UI_METRICS.field_row)
    root.add_fixed_child(document.create_label("Ignored Resource Paths"), EDITOR_UI_METRICS.section_row)
    ignored = document.create_text_area()
    root.add_fixed_child(_ref(document, ignored), 120.0)
    root.add_fixed_child(
        document.create_label("Project Render Phases (bits 16-63; one indexed slot per line)"),
        EDITOR_UI_METRICS.section_row,
    )
    render_phases = document.create_text_area()
    root.add_stretch_child(_ref(document, render_phases))
    status = document.create_status_bar("Project settings")
    root.add_fixed_child(_ref(document, status), EDITOR_UI_METRICS.status_row)
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
        vsync,
        ignored,
        render_phases,
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
    vsync.connect_changed(
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
