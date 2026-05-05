import importlib.util
from pathlib import Path


_MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "termin"
    / "editor_core"
    / "framegraph_debugger_model.py"
)
_SPEC = importlib.util.spec_from_file_location("framegraph_debugger_model_source", _MODEL_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
FramegraphDebuggerModel = _MODULE.FramegraphDebuggerModel


class _Pipeline:
    def __init__(self, name):
        self.name = name
        self.passes = []
        self.removed = []

    def remove_passes_by_name(self, name):
        self.removed.append(name)
        before = len(self.passes)
        self.passes = [p for p in self.passes if p.pass_name != name]
        return before - len(self.passes)


class _Pass:
    pass_name = "FrameDebugger"


class _Capture:
    def __init__(self):
        self.reset = False

    def reset_capture(self):
        self.reset = True


class _Core:
    def __init__(self):
        self.capture = _Capture()


class _Viewport:
    managed_by_scene_pipeline = ""
    scene = None

    def __init__(self, pipeline):
        self.pipeline = pipeline


def test_disconnect_removes_debugger_from_all_known_pipelines():
    connected = _Pipeline("connected")
    current = _Pipeline("current")
    connected.passes = [_Pass()]
    current.passes = [_Pass()]

    model = FramegraphDebuggerModel(None, _Core())
    model._connected_pipeline = connected
    model._current_viewport = _Viewport(current)
    model._viewports_list = [(model._current_viewport, "Viewport")]

    model.disconnect()

    assert connected.passes == []
    assert current.passes == []
    assert connected.removed == ["FrameDebugger"]
    assert current.removed == ["FrameDebugger"]
    assert model.core.capture.reset is True
