import importlib.util
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "termin-gui" / "python"))

_DIALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "termin"
    / "editor_tcgui"
    / "dialogs"
    / "framegraph_debugger.py"
)
_SPEC = importlib.util.spec_from_file_location("tcgui_framegraph_debugger_source", _DIALOG_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
_FramegraphDebuggerHandle = _MODULE._FramegraphDebuggerHandle


class _Signal:
    def __init__(self):
        self.disconnected = []

    def connect(self, callback):
        pass

    def disconnect(self, callback):
        self.disconnected.append(callback)


class _Model:
    def __init__(self):
        self.disconnect_count = 0
        self.lists_changed = _Signal()
        self.selection_changed = _Signal()
        self.info_changed = _Signal()
        self.capture_updated = _Signal()
        self.preview_params_changed = _Signal()
        self.hdr_stats_changed = _Signal()

    def disconnect(self):
        self.disconnect_count += 1


class _WindowUI:
    def __init__(self):
        self.close_count = 0
        self.close_window = self._close
        self.on_empty = None
        self.on_destroy = None
        self.root = object()

    def _close(self):
        self.close_count += 1


def test_window_destroy_tears_down_without_native_close_recursion():
    model = _Model()
    handle = _FramegraphDebuggerHandle(model)
    window_ui = _WindowUI()
    handle.window_ui = window_ui
    handle._native_close = window_ui.close_window
    handle.visible = True

    handle._on_window_destroyed()
    handle._on_window_destroyed()

    assert model.disconnect_count == 1
    assert window_ui.close_count == 0
    assert handle.visible is False
    assert window_ui.on_empty is None
    assert window_ui.on_destroy is None


def test_close_tears_down_and_closes_native_window_once():
    model = _Model()
    handle = _FramegraphDebuggerHandle(model)
    window_ui = _WindowUI()
    handle.window_ui = window_ui
    handle._native_close = window_ui.close_window
    handle.visible = True

    handle.close()
    handle.close()

    assert model.disconnect_count == 1
    assert window_ui.close_count == 1
    assert handle.visible is False
