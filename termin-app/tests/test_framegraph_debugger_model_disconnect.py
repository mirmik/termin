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
FramegraphDebugTarget = _MODULE.FramegraphDebugTarget


class _Pipeline:
    def __init__(self, name):
        self.name = name
        self.passes = []
        self.removed = []
        self.fbos = {}

    def remove_passes_by_name(self, name):
        self.removed.append(name)
        before = len(self.passes)
        self.passes = [p for p in self.passes if p.pass_name != name]
        return before - len(self.passes)

    def get_fbo_keys(self):
        return list(self.fbos.keys())

    def get_fbo(self, key):
        return self.fbos[key]


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


class _Controller:
    def __init__(self, targets):
        self.targets = targets

    def get_framegraph_debug_targets_info(self):
        return self.targets


def test_disconnect_removes_debugger_from_all_known_pipelines():
    connected = _Pipeline("connected")
    current = _Pipeline("current")
    connected.passes = [_Pass()]
    current.passes = [_Pass()]

    model = FramegraphDebuggerModel(None, _Core())
    model._connected_pipeline = connected
    viewport = _Viewport(current)
    model._current_target = FramegraphDebugTarget(
        source=viewport,
        label="Viewport",
        get_pipeline=lambda: current,
    )
    model._targets_list = [model._current_target]

    model.disconnect()

    assert connected.passes == []
    assert current.passes == []
    assert connected.removed == ["FrameDebugger"]
    assert current.removed == ["FrameDebugger"]
    assert model.core.capture.reset is True


def test_refresh_uses_debug_targets_not_viewport_list():
    pipeline = _Pipeline("offscreen")
    target = FramegraphDebugTarget(
        source=object(),
        label="RenderTarget / offscreen",
        get_pipeline=lambda: pipeline,
    )

    model = FramegraphDebuggerModel(_Controller([target]), _Core())
    model.refresh_viewports()

    assert model.viewports == [(target.source, "RenderTarget / offscreen")]
    assert model.targets == [target]
    assert model.get_current_pipeline() is pipeline


def test_format_fbo_info_prints_pixel_format_names():
    pipeline = _Pipeline("debug")
    pipeline.fbos["debug_res"] = {
        "width": 320,
        "height": 180,
        "color_format": 3,
        "has_depth": True,
        "depth_format": 13,
        "samples": 1,
        "color_native_handle": 42,
    }

    model = FramegraphDebuggerModel(None, _Core())
    model._debug_source_res = "debug_res"
    model._current_target = FramegraphDebugTarget(
        source=object(),
        label="Debug",
        get_pipeline=lambda: pipeline,
    )

    text = model.format_fbo_info()

    assert "fmt=rgba8" in text
    assert "depth_fmt=depth32f" in text
    assert "fmt=3" not in text
    assert "depth_fmt=13" not in text


def test_format_fbo_info_uses_target_output_resource_info():
    pipeline = _Pipeline("debug")

    model = FramegraphDebuggerModel(None, _Core())
    model._debug_source_res = "OUTPUT"
    model._current_target = FramegraphDebugTarget(
        source=object(),
        label="RenderTarget",
        get_pipeline=lambda: pipeline,
        get_resource_info=lambda resource: {
            "width": 640,
            "height": 360,
            "color_format_name": "rgba16f",
            "has_depth": True,
            "depth_format_name": "depth32f",
            "samples": 1,
        } if resource == "OUTPUT" else None,
    )

    text = model.format_fbo_info()

    assert "<b>OUTPUT</b>" in text
    assert "Размер: 640×360" in text
    assert "fmt=rgba16f" in text
    assert "depth_fmt=depth32f" in text
