from termin.editor_core.framegraph_debugger_model import (
    FramegraphDebuggerModel,
    FramegraphDebugTarget,
)


class _Pipeline:
    def __init__(self, name):
        self.name = name
        self.passes = []
        self.removed = []
        self.fbos = {}
        self.pipeline_specs = []

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
    def __init__(self, pass_name="FrameDebugger", symbols=None, type_name="TestPass"):
        self.pass_name = pass_name
        self.type_name = type_name
        self.symbols = list(symbols or [])
        self.debug_internal_point = None
        self.debug_capture = None
        self.cleared = False

    def get_internal_symbols(self):
        return list(self.symbols)

    def get_internal_symbols_with_timing(self):
        return []

    def set_debug_internal_point(self, symbol):
        self.debug_internal_point = symbol

    def set_debug_capture(self, capture):
        self.debug_capture = capture

    def clear_debug_capture(self):
        self.cleared = True

    def serialize(self):
        return {
            "pass_name": self.pass_name,
            "symbols": list(self.symbols),
        }


class _Capture:
    def __init__(self):
        self.reset = False
        self._has_capture = False
        self.width = 0
        self.height = 0
        self.format = 14
        self.is_depth = False

    def reset_capture(self):
        self.reset = True

    def has_capture(self):
        return self._has_capture


class _Core:
    def __init__(self):
        self.capture = _Capture()
        self.depth_capture = _Capture()


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


def test_format_fbo_info_uses_color_capture_info_only():
    core = _Core()
    core.capture._has_capture = True
    core.capture.width = 512
    core.capture.height = 256
    core.capture.format = 7

    model = FramegraphDebuggerModel(None, core)
    model._debug_source_res = "DepthToColorPass_5_output_res"
    model._current_target = FramegraphDebugTarget(
        source=object(),
        label="RenderTarget",
        get_pipeline=lambda: _Pipeline("debug"),
    )

    text = model.format_fbo_info()

    assert "<b>DepthToColorPass_5_output_res</b>" in text
    assert "Тип: color_texture" in text
    assert "Размер: 512×256" in text
    assert "fmt=rgba16f" in text


def test_format_fbo_info_marks_depth_capture():
    core = _Core()
    core.capture._has_capture = True
    core.capture.width = 1024
    core.capture.height = 512
    core.capture.format = 13
    core.capture.is_depth = True

    model = FramegraphDebuggerModel(None, core)
    model._debug_source_res = "RT_COLOR.depth"

    text = model.format_fbo_info()

    assert "<b>RT_COLOR.depth</b>" in text
    assert "Тип: depth_texture" in text
    assert "Размер: 1024×512" in text
    assert "fmt=depth32f" in text


def test_format_fbo_info_reports_missing_capture():
    model = FramegraphDebuggerModel(None, _Core())
    model._debug_source_res = "DepthToColorPass_5_output_res"

    text = model.format_fbo_info()

    assert text == "Ресурс 'DepthToColorPass_5_output_res': capture ещё не получен"


def test_duplicate_pass_selection_uses_pipeline_index():
    first = _Pass("Color", ["first_symbol"])
    second = _Pass("Color", ["second_symbol"])
    pipeline = _Pipeline("debug")
    pipeline.passes = [first, second]

    model = FramegraphDebuggerModel(None, _Core())
    model._current_target = FramegraphDebugTarget(
        source=object(),
        label="RenderTarget",
        get_pipeline=lambda: pipeline,
    )

    passes = model.get_passes()
    assert [(item.index, item.name) for item in passes] == [(0, "Color"), (1, "Color")]

    model.set_selected_pass_by_index(1)

    assert model.selected_pass == "Color"
    assert model.selected_pass_index == 1
    assert model.selected_symbol == "second_symbol"
    assert first.debug_internal_point == ""
    assert second.debug_internal_point == "second_symbol"
    assert second.debug_capture is model.core.capture
    assert '"second_symbol"' in model.format_pass_json()
