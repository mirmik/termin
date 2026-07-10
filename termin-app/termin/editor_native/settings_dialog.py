"""Native editor settings dialog over the shared persistence controller."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Callable
import weakref

from termin.editor_core.settings_model import EditorSettingsController, EditorSettingsSnapshot
from termin.gui_native import DialogAction, Document, EdgeInsets, Rect, Size, WidgetRef

from .dialog_service import NativeDialogService


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
    status: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    apply_font_size: Callable[[float], None]
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
        )

    def apply_snapshot(self, snapshot: EditorSettingsSnapshot) -> None:
        self.text_editor.text = snapshot.text_editor
        self.slang_compiler.text = snapshot.slang_compiler
        self.font_size.value = snapshot.font_size
        self.font_size_small.value = snapshot.font_size_small
        self.mcp_enabled.checked = snapshot.mcp_server_enabled
        self.status.text = "MCP setting takes effect on the next editor start"

    def apply_live(self) -> None:
        snapshot = self.controller.validate(self.snapshot())
        self.apply_font_size(snapshot.font_size)
        self.status.text = f"Applied font size {snapshot.font_size:.0f}"
        self.request_render()

    def save(self) -> EditorSettingsSnapshot:
        snapshot = self.controller.save(self.snapshot())
        self.apply_font_size(snapshot.font_size)
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
    root.set_layout_spacing(2.0)
    root.add_fixed_child(document.create_label(label_text), 22.0)
    row = document.create_hstack("settings-path-row")
    row.set_layout_spacing(4.0)
    value = document.create_text_input()
    row.add_stretch_child(_ref(document, value))
    browse = document.create_button("Browse...")
    row.add_fixed_child(_ref(document, browse), 86.0)
    root.add_fixed_child(row, 30.0)
    return root, value, browse


def _spin_row(document: Document, label: str, minimum: float, maximum: float):
    row = document.create_hstack(f"settings-{label.lower().replace(' ', '-')}")
    row.set_layout_spacing(4.0)
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
) -> NativeSettingsDialog:
    root = document.create_vstack("native-settings-dialog")
    root.stable_id = "editor.settings"
    root.preferred_size = Size(560.0, 430.0)
    root.set_layout_padding(EdgeInsets(8.0, 8.0, 8.0, 8.0))
    root.set_layout_spacing(7.0)
    editor_row, text_editor, editor_browse = _path_row(document, "External Text Editor")
    root.add_fixed_child(editor_row, 56.0)
    slang_row, slang_compiler, slang_browse = _path_row(document, "Slang Compiler")
    root.add_fixed_child(slang_row, 56.0)
    font_row, font_size = _spin_row(document, "Font Size", 8.0, 32.0)
    root.add_fixed_child(font_row, 30.0)
    small_row, font_size_small = _spin_row(document, "Font Size (small)", 8.0, 24.0)
    root.add_fixed_child(small_row, 30.0)
    mcp_row = document.create_hstack("settings-mcp-row")
    mcp_row.set_layout_spacing(4.0)
    mcp_row.add_stretch_child(
        document.create_label("Enable local editor MCP server on startup")
    )
    mcp_enabled = document.create_checkbox(False)
    mcp_row.add_fixed_child(_ref(document, mcp_enabled), 28.0)
    root.add_fixed_child(mcp_row, 30.0)
    apply_button = document.create_button("Apply Font")
    root.add_fixed_child(_ref(document, apply_button), 32.0)
    status = document.create_status_bar("Settings")
    root.add_fixed_child(_ref(document, status), 24.0)
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
        status=status,
        viewport=viewport,
        request_render=request_render,
        apply_font_size=apply_font_size,
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
