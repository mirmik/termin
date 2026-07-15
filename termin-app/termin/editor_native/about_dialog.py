"""Native About Termin dialog."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Callable
import weakref

from termin.editor_core.about_model import EditorAboutInfo
from termin.gui_native import DialogAction, Document, Rect, RichTextModel, Size, WidgetRef

from .metrics import EDITOR_UI_METRICS


@dataclass
class NativeAboutDialog:
    document: Document
    info: EditorAboutInfo
    dialog: object
    root: WidgetRef
    content_model: RichTextModel
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native About dialog is closed")
        if self.dialog.open:
            return False
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


def build_native_about_dialog(
    document: Document,
    info: EditorAboutInfo,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
) -> NativeAboutDialog:
    root = document.create_vstack("native-about-dialog")
    root.stable_id = "editor.about"
    root.preferred_size = Size(520.0, 280.0)
    root.set_layout_padding(EDITOR_UI_METRICS.dialog_insets)
    model = RichTextModel()
    model.set_html(
        "<b>Termin Editor</b><br>"
        "A suspiciously practical editor for projects that keep moving.<br><br>"
        f"<b>Version:</b> {escape(info.version)}<br>"
        f"<b>TERMIN_BACKEND:</b> {escape(info.configured_backend)}<br>"
        f"<b>Active backend:</b> {escape(info.active_backend)}"
    )
    view = document.create_rich_text_view(model)
    root.add_stretch_child(document.ref(view.handle))
    dialog = document.create_dialog("About Termin")
    dialog.actions = [DialogAction("ok", "OK", is_default=True, is_cancel=True)]
    dialog.set_content(root)
    return NativeAboutDialog(document, info, dialog, root, model, viewport, request_render)


def connect_about_command(menu_bar, command_id: int, dialog: NativeAboutDialog) -> None:
    weak_dialog = weakref.ref(dialog)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        if activated_id != command_id:
            return
        owner = weak_dialog()
        if owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = ["NativeAboutDialog", "build_native_about_dialog", "connect_about_command"]
