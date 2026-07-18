"""Native editor settings dialog over the shared persistence controller."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable
import weakref

from termin.editor_core.settings_model import EditorSettingsController, EditorSettingsSnapshot
from termin.gui_native import DialogAction, Document, Rect, Size, WidgetRef

from .dialog_service import NativeDialogService
from .metrics import EDITOR_UI_METRICS


_logger = logging.getLogger(__name__)


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


@dataclass
class NativeSettingsDialog:
    document: Document
    controller: EditorSettingsController
    dialog_service: NativeDialogService
    dialog: object
    root: WidgetRef
    text_editor: object
    slang_compiler: object
    font_size: object
    font_size_small: object
    mcp_enabled: object
    vsync_enabled: object
    fps_limit: object
    render_only_active_display: object
    status: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    apply_font_size: Callable[[float], None]
    apply_render_only_active_display: Callable[[bool], None]
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native settings dialog is closed")
        if self.dialog.open:
            return False
        self.apply_snapshot(self.controller.load())
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def snapshot(self) -> EditorSettingsSnapshot:
        return EditorSettingsSnapshot(
            text_editor=self.text_editor.text,
            slang_compiler=self.slang_compiler.text,
            font_size=self.font_size.value,
            font_size_small=self.font_size_small.value,
            mcp_server_enabled=self.mcp_enabled.checked,
            vsync_enabled=self.vsync_enabled.checked,
            fps_limit=self.fps_limit.value,
            render_only_active_display=self.render_only_active_display.checked,
        )

    def apply_snapshot(self, snapshot: EditorSettingsSnapshot) -> None:
        self.text_editor.text = snapshot.text_editor
        self.slang_compiler.text = snapshot.slang_compiler
        self.font_size.value = snapshot.font_size
        self.font_size_small.value = snapshot.font_size_small
        self.mcp_enabled.checked = snapshot.mcp_server_enabled
        self.vsync_enabled.checked = snapshot.vsync_enabled
        self.fps_limit.value = snapshot.fps_limit
        self.render_only_active_display.checked = snapshot.render_only_active_display
        self.status.text = "VSync, FPS limit, and MCP startup changes apply after restart"

    def apply_live(self) -> None:
        snapshot = self.controller.validate(self.snapshot())
        self.apply_font_size(snapshot.font_size)
        self.status.text = f"Applied font size {snapshot.font_size:.0f}"
        self.request_render()

    def save(self) -> EditorSettingsSnapshot:
        snapshot = self.controller.save(self.snapshot())
        self.apply_font_size(snapshot.font_size)
        self.apply_render_only_active_display(snapshot.render_only_active_display)
        self.request_render()
        return snapshot

    def browse_text_editor(self) -> None:
        self.dialog_service.show_open_file(
            "Select Text Editor",
            str(Path.home()),
            "Executables | *",
            lambda path: self._set_path(self.text_editor, path),
        )

    def browse_slang_compiler(self) -> None:
        self.dialog_service.show_open_file(
            "Select slangc",
            str(Path.home()),
            "Executables | *",
            lambda path: self._set_path(self.slang_compiler, path),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)

    def _set_path(self, control, path: str | None) -> None:
        if path:
            control.text = path
            self.request_render()


def _path_row(document: Document, label_text: str):
    root = document.create_vstack(f"settings-{label_text.lower().replace(' ', '-')}")
    root.set_layout_spacing(EDITOR_UI_METRICS.compact_spacing)
    root.add_fixed_child(document.create_label(label_text), EDITOR_UI_METRICS.compact_status_row)
    row = document.create_hstack("settings-path-row")
    row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    value = document.create_text_input()
    row.add_stretch_child(_ref(document, value))
    browse = document.create_button("Browse...")
    row.add_fixed_child(_ref(document, browse), 86.0)
    root.add_fixed_child(row, EDITOR_UI_METRICS.field_row)
    return root, value, browse


def _spin_row(document: Document, label: str, minimum: float, maximum: float):
    row = document.create_hstack(f"settings-{label.lower().replace(' ', '-')}")
    row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    row.add_stretch_child(document.create_label(label))
    spin = document.create_spin_box()
    spin.set_range(minimum, maximum)
    spin.step = 1.0
    spin.decimals = 0
    row.add_fixed_child(_ref(document, spin), 100.0)
    return row, spin


def build_native_settings_dialog(
    document: Document,
    controller: EditorSettingsController,
    *,
    dialog_service: NativeDialogService,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
    apply_font_size: Callable[[float], None],
    apply_render_only_active_display: Callable[[bool], None],
) -> NativeSettingsDialog:
    root = document.create_vstack("native-settings-dialog")
    root.stable_id = "editor.settings"
    root.preferred_size = Size(560.0, 550.0)
    root.set_layout_padding(EDITOR_UI_METRICS.dialog_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.dialog_spacing)
    editor_row, text_editor, editor_browse = _path_row(document, "External Text Editor")
    path_row_height = (
        EDITOR_UI_METRICS.compact_status_row
        + EDITOR_UI_METRICS.compact_spacing
        + EDITOR_UI_METRICS.field_row
    )
    root.add_fixed_child(editor_row, path_row_height)
    slang_row, slang_compiler, slang_browse = _path_row(document, "Slang Compiler")
    root.add_fixed_child(slang_row, path_row_height)
    font_row, font_size = _spin_row(document, "Font Size", 8.0, 32.0)
    root.add_fixed_child(font_row, EDITOR_UI_METRICS.field_row)
    small_row, font_size_small = _spin_row(document, "Font Size (small)", 8.0, 24.0)
    root.add_fixed_child(small_row, EDITOR_UI_METRICS.field_row)
    vsync_row = document.create_hstack("settings-vsync-row")
    vsync_row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    vsync_row.add_stretch_child(
        document.create_label("Enable VSync (applies after editor restart)")
    )
    vsync_enabled = document.create_checkbox(True)
    vsync_row.add_fixed_child(_ref(document, vsync_enabled), 28.0)
    root.add_fixed_child(vsync_row, EDITOR_UI_METRICS.field_row)
    fps_limit_row, fps_limit = _spin_row(
        document,
        "FPS Limit (0 = Unlimited, applies after restart)",
        0.0,
        1000.0,
    )
    root.add_fixed_child(fps_limit_row, EDITOR_UI_METRICS.field_row)
    active_display_row = document.create_hstack("settings-active-display-rendering-row")
    active_display_row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    active_display_row.add_stretch_child(
        document.create_label("Render only selected display tab")
    )
    render_only_active_display = document.create_checkbox(True)
    active_display_row.add_fixed_child(_ref(document, render_only_active_display), 28.0)
    root.add_fixed_child(active_display_row, EDITOR_UI_METRICS.field_row)
    mcp_row = document.create_hstack("settings-mcp-row")
    mcp_row.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    mcp_row.add_stretch_child(
        document.create_label("Enable local editor MCP server on startup")
    )
    mcp_enabled = document.create_checkbox(False)
    mcp_row.add_fixed_child(_ref(document, mcp_enabled), 28.0)
    root.add_fixed_child(mcp_row, EDITOR_UI_METRICS.field_row)
    apply_button = document.create_button("Apply Font")
    root.add_fixed_child(_ref(document, apply_button), EDITOR_UI_METRICS.field_row)
    status = document.create_status_bar("Settings")
    root.add_fixed_child(_ref(document, status), EDITOR_UI_METRICS.status_row)
    dialog = document.create_dialog("Settings")
    dialog.actions = [
        DialogAction("ok", "OK", is_default=True),
        DialogAction("cancel", "Cancel", is_cancel=True),
    ]
    dialog.set_content(root)
    result = NativeSettingsDialog(
        document=document,
        controller=controller,
        dialog_service=dialog_service,
        dialog=dialog,
        root=root,
        text_editor=text_editor,
        slang_compiler=slang_compiler,
        font_size=font_size,
        font_size_small=font_size_small,
        mcp_enabled=mcp_enabled,
        vsync_enabled=vsync_enabled,
        fps_limit=fps_limit,
        render_only_active_display=render_only_active_display,
        status=status,
        viewport=viewport,
        request_render=request_render,
        apply_font_size=apply_font_size,
        apply_render_only_active_display=apply_render_only_active_display,
    )
    weak_result = weakref.ref(result)

    def owner() -> NativeSettingsDialog | None:
        return weak_result()

    editor_browse.connect_clicked(
        lambda: owner().browse_text_editor() if owner() is not None else None
    )
    slang_browse.connect_clicked(
        lambda: owner().browse_slang_compiler() if owner() is not None else None
    )
    apply_button.connect_clicked(lambda: owner().apply_live() if owner() is not None else None)

    def finished(dialog_result) -> None:
        current = owner()
        if current is None or dialog_result.action_id != "ok":
            return
        try:
            current.save()
        except Exception as error:
            _logger.exception("Native settings save failed")
            current.status.text = f"Save failed: {error}"

    dialog.connect_finished(finished)
    return result


def connect_settings_command(menu_bar, command_id: int, dialog: NativeSettingsDialog) -> None:
    weak_dialog = weakref.ref(dialog)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        if activated_id != command_id:
            return
        owner = weak_dialog()
        if owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = ["NativeSettingsDialog", "build_native_settings_dialog", "connect_settings_command"]
