"""Native Undo History and Audio Debugger dialogs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import weakref

from termin.editor_core.audio_debugger_model import AudioDebuggerController, AudioDebuggerSnapshot
from termin.editor_core.undo_history_model import UndoHistoryController, UndoHistorySnapshot
from termin.gui_native import DialogAction, Document, Rect, RichTextModel, Size, WidgetRef

from .metrics import EDITOR_UI_METRICS


def _ref(document: Document, reference) -> WidgetRef:
    return reference if isinstance(reference, WidgetRef) else document.ref(reference.handle)


@dataclass
class NativeUndoHistoryDialog:
    document: Document
    controller: UndoHistoryController
    dialog: object
    done_model: RichTextModel
    undone_model: RichTextModel
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    changed_callback: Callable[[UndoHistorySnapshot], None]
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native Undo History dialog is closed")
        if self.dialog.open:
            return False
        self.apply_snapshot(self.controller.snapshot)
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def refresh(self) -> UndoHistorySnapshot:
        return self.controller.refresh()

    def apply_snapshot(self, snapshot: UndoHistorySnapshot) -> None:
        self.done_model.set_text(
            "\n".join(f"[undo #{entry.index}] {entry.text}" for entry in snapshot.done)
        )
        self.undone_model.set_text(
            "\n".join(f"[redo #{entry.index}] {entry.text}" for entry in snapshot.undone)
        )
        self.request_render()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.controller.changed.disconnect(self.changed_callback)
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


@dataclass
class NativeAudioDebuggerDialog:
    document: Document
    controller: AudioDebuggerController
    dialog: object
    status: object
    channels_model: RichTextModel
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native Audio Debugger dialog is closed")
        if self.dialog.open:
            return False
        self.refresh()
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def refresh(self) -> AudioDebuggerSnapshot:
        snapshot = self.controller.refresh()
        if not snapshot.initialized:
            self.status.text = "Not initialized | Master: — | Channels: —"
            self.channels_model.set_text("")
        else:
            self.status.text = (
                f"Initialized | Master: {snapshot.master_volume * 100:.0f}% | "
                f"Channels: {len(snapshot.channels)} / {snapshot.total_channels}"
            )
            self.channels_model.set_text(
                "\n".join(
                    f"Ch {channel.channel}  {'Paused' if channel.paused else 'Playing'}  "
                    f"Vol: {channel.volume * 100:.0f}%  Angle: {channel.angle}°  "
                    f"Dist: {channel.distance}"
                    for channel in snapshot.channels
                )
            )
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


def build_native_undo_history_dialog(
    document: Document,
    controller: UndoHistoryController,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
) -> NativeUndoHistoryDialog:
    root = document.create_vstack("native-undo-history")
    root.stable_id = "editor.undo-history"
    root.preferred_size = Size(760.0, 480.0)
    root.set_layout_padding(EDITOR_UI_METRICS.dialog_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.dialog_spacing)
    columns = document.create_hstack("undo-history-columns")
    # The wider gutter separates two peer history documents, not ordinary controls.
    columns.set_layout_spacing(8.0)
    done_model = RichTextModel()
    done = document.create_rich_text_view(done_model)
    done.placeholder = "No commands to undo"
    undone_model = RichTextModel()
    undone = document.create_rich_text_view(undone_model)
    undone.placeholder = "No commands to redo"
    columns.add_stretch_child(_ref(document, done))
    columns.add_stretch_child(_ref(document, undone))
    root.add_stretch_child(columns)
    refresh = document.create_button("Refresh")
    root.add_fixed_child(_ref(document, refresh), EDITOR_UI_METRICS.field_row)
    dialog = document.create_dialog("Undo/Redo Stack")
    dialog.actions = [DialogAction("close", "Close", is_cancel=True)]
    dialog.set_content(root)
    placeholder = lambda _snapshot: None
    result = NativeUndoHistoryDialog(
        document, controller, dialog, done_model, undone_model, viewport, request_render, placeholder
    )
    weak_result = weakref.ref(result)

    def changed(snapshot: UndoHistorySnapshot) -> None:
        owner = weak_result()
        if owner is not None:
            owner.apply_snapshot(snapshot)

    result.changed_callback = changed
    controller.changed.connect(changed)
    refresh.connect_clicked(lambda: weak_result().refresh() if weak_result() is not None else None)
    return result


def build_native_audio_debugger_dialog(
    document: Document,
    controller: AudioDebuggerController,
    *,
    viewport: Callable[[], Rect],
    request_render: Callable[[], None],
) -> NativeAudioDebuggerDialog:
    root = document.create_vstack("native-audio-debugger")
    root.stable_id = "editor.audio-debugger"
    root.preferred_size = Size(650.0, 440.0)
    root.set_layout_padding(EDITOR_UI_METRICS.dialog_insets)
    root.set_layout_spacing(EDITOR_UI_METRICS.dialog_spacing)
    status = document.create_status_bar("Audio status")
    root.add_fixed_child(_ref(document, status), EDITOR_UI_METRICS.compact_row)
    channels_model = RichTextModel()
    channels = document.create_rich_text_view(channels_model)
    channels.placeholder = "No active channels"
    root.add_stretch_child(_ref(document, channels))
    refresh = document.create_button("Refresh")
    root.add_fixed_child(_ref(document, refresh), EDITOR_UI_METRICS.field_row)
    dialog = document.create_dialog("Audio Debugger")
    dialog.actions = [DialogAction("close", "Close", is_cancel=True)]
    dialog.set_content(root)
    result = NativeAudioDebuggerDialog(
        document, controller, dialog, status, channels_model, viewport, request_render
    )
    weak_result = weakref.ref(result)
    refresh.connect_clicked(lambda: weak_result().refresh() if weak_result() is not None else None)
    return result


def connect_diagnostic_command(menu_bar, command_id: int, dialog) -> None:
    weak_dialog = weakref.ref(dialog)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        owner = weak_dialog()
        if activated_id == command_id and owner is not None:
            owner.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeAudioDebuggerDialog",
    "NativeUndoHistoryDialog",
    "build_native_audio_debugger_dialog",
    "build_native_undo_history_dialog",
    "connect_diagnostic_command",
]
