import gc
import weakref

from termin.editor_core.audio_debugger_model import AudioDebuggerController
from termin.editor_core.undo_history_model import UndoHistoryController
from termin.editor_core.undo_stack import UndoCommand, UndoStack
from termin.editor_native.diagnostic_dialogs import (
    build_native_audio_debugger_dialog,
    build_native_undo_history_dialog,
)
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import Document, Rect

from test_editor_diagnostic_models import _AudioEngine


class _Command(UndoCommand):
    def do(self) -> None:
        pass

    def undo(self) -> None:
        pass


def test_native_undo_history_dialog_refreshes_reopens_and_releases():
    document = Document()
    stack = UndoStack()
    stack.push(_Command("rename entity"))
    renders = []
    dialog = build_native_undo_history_dialog(
        document,
        UndoHistoryController(stack),
        viewport=lambda: Rect(0.0, 0.0, 800.0, 600.0),
        request_render=lambda: renders.append(True),
    )

    assert dialog.show()
    root = dialog.dialog.widget.children[0]
    assert root.children[-1].bounds.height == EDITOR_UI_METRICS.field_row
    assert "rename entity" in dialog.done_model.text
    stack.undo()
    dialog.refresh()
    assert "rename entity" in dialog.undone_model.text
    assert dialog.dialog.activate("close")
    assert dialog.show()

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    reference = weakref.ref(dialog)
    del dialog
    gc.collect()
    assert reference() is None
    assert renders


def test_native_audio_debugger_dialog_refreshes_reopens_and_releases():
    document = Document()
    renders = []
    dialog = build_native_audio_debugger_dialog(
        document,
        AudioDebuggerController(_AudioEngine()),
        viewport=lambda: Rect(0.0, 0.0, 800.0, 600.0),
        request_render=lambda: renders.append(True),
    )

    assert dialog.show()
    root = dialog.dialog.widget.children[0]
    assert root.children[0].bounds.height == EDITOR_UI_METRICS.compact_row
    assert root.children[-1].bounds.height == EDITOR_UI_METRICS.field_row
    assert "2 / 3" in dialog.status.text
    assert "Ch 2  Paused" in dialog.channels_model.text
    assert dialog.dialog.activate("close")
    assert dialog.show()

    dialog.close()
    assert not document.is_alive(dialog.dialog.handle)
    reference = weakref.ref(dialog)
    del dialog
    gc.collect()
    assert reference() is None
    assert renders
