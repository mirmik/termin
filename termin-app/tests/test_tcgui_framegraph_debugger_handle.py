import sys
import types

from termin.editor_tcgui.dialogs.framegraph_debugger import (
    _FramegraphDebuggerHandle,
    CapturePreviewWidget,
)
from termin.editor_core.framegraph_debugger_model import (
    FramegraphDebuggerModel,
    FramegraphPassListItem,
)


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
        self.selected_pass = None
        self.selected_pass_index = None
        self.selected_indices = []
        self.lists_changed = _Signal()
        self.selection_changed = _Signal()
        self.info_changed = _Signal()
        self.capture_updated = _Signal()
        self.preview_params_changed = _Signal()
        self.hdr_stats_changed = _Signal()

    def disconnect(self):
        self.disconnect_count += 1

    def get_passes(self):
        return []

    def set_selected_pass_by_index(self, index):
        self.selected_indices.append(index)
        self.selected_pass_index = index


class _WindowUI:
    def __init__(self):
        self.close_count = 0
        self.close_window = self._close
        self.on_empty = None
        self.on_destroy = None
        self.root = object()

    def _close(self):
        self.close_count += 1


class _Capture:
    def __init__(self, *, is_depth=False):
        self.capture_tex = object()
        self.width = 64
        self.height = 32
        self.is_depth = is_depth


class _Core:
    def __init__(self):
        self.presenter = object()
        self.capture_tex = object()
        self.capture = _Capture()
        self.depth_capture = _Capture(is_depth=True)


class _Renderer:
    def __init__(self):
        self.preview_kwargs = None
        self.texture_kwargs = None

    def draw_rect(self, *_args):
        pass

    def draw_texture_preview(self, *_args, **kwargs):
        self.preview_kwargs = kwargs

    def draw_texture(self, *_args, **kwargs):
        self.texture_kwargs = kwargs


class _ComboBox:
    def __init__(self):
        self.items = []
        self.selected_index = -1

    @property
    def item_count(self):
        return len(self.items)

    def clear(self):
        self.items.clear()
        self.selected_index = -1

    def add_item(self, text):
        self.items.append(text)

    def item_text(self, index):
        return self.items[index]


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


def test_capture_preview_forwards_channel_mode_to_presenter_preview():
    preview = CapturePreviewWidget()
    preview._core = _Core()
    preview._capture = preview._core.capture
    preview.has_content = True
    preview.channel_mode = 4
    preview.highlight_hdr = True
    preview.layout(0, 0, 120, 80, 120, 80)

    renderer = _Renderer()
    preview.render(renderer)

    assert renderer.texture_kwargs is None
    assert renderer.preview_kwargs["presenter"] is preview._core.presenter
    assert renderer.preview_kwargs["channel_mode"] == 4
    assert renderer.preview_kwargs["highlight_hdr"] is True


def test_capture_preview_forces_depth_to_presenter_depth_mode_without_hdr():
    preview = CapturePreviewWidget()
    preview._core = _Core()
    preview._capture = preview._core.depth_capture
    preview.has_content = True
    preview.channel_mode = 4
    preview.highlight_hdr = True
    preview.layout(0, 0, 120, 80, 120, 80)

    renderer = _Renderer()
    preview.render(renderer)

    assert renderer.texture_kwargs is None
    assert renderer.preview_kwargs["presenter"] is preview._core.presenter
    assert renderer.preview_kwargs["channel_mode"] == 5
    assert renderer.preview_kwargs["highlight_hdr"] is False

def test_pass_combo_tracks_stable_pipeline_indices_for_duplicate_names():
    class Model(_Model):
        def __init__(self):
            super().__init__()
            self.selected_pass = "Color"
            self.selected_pass_index = 4

        def get_passes(self):
            return [
                FramegraphPassListItem(2, "Color", True),
                FramegraphPassListItem(4, "Color", True),
            ]

    handle = _FramegraphDebuggerHandle(Model())
    handle._pass_combo = _ComboBox()

    handle._refresh_pass_combo()

    assert handle._pass_combo.items == ["Color *", "Color *"]
    assert handle._pass_combo_indices == [2, 4]
    assert handle._pass_combo.selected_index == 1


def test_pass_combo_event_selects_pass_by_pipeline_index():
    model = _Model()
    handle = _FramegraphDebuggerHandle(model)
    handle._pass_combo_indices = [2, 4]

    handle._select_pass_combo_row(1)

    assert model.selected_indices == [4]


def test_framegraph_render_stats_include_pipeline_cache_counters(monkeypatch):
    class Manager:
        def get_render_stats(self):
            return {
                "attached_scenes": 1,
                "scene_pipelines": 2,
                "unmanaged_viewports": 3,
                "scene_names": ["Scene"],
                "pipeline_names": ["Default"],
                "pipeline_cache_hits": 4,
                "pipeline_cache_misses": 5,
                "pipeline_cache_create_pipeline_count": 6,
                "pipeline_cache_cached_pipelines": 7,
                "pipeline_cache_unique_vertex_layout_signatures": 8,
                "pipeline_cache_vertex_layout_signature_hashes": [0x1234, 0xABCD],
            }

    class RenderingManager:
        @staticmethod
        def instance():
            return Manager()

    engine_module = types.ModuleType("termin.engine")
    engine_module.RenderingManager = RenderingManager
    monkeypatch.setitem(sys.modules, "termin.engine", engine_module)

    model = FramegraphDebuggerModel.__new__(FramegraphDebuggerModel)

    text = model.format_render_stats()

    assert "Scenes: 1" in text
    assert "PipelineCache: hit=4 miss=5 create=6 cached=7 layouts=8" in text
    assert "layout_hashes=1234,abcd" in text
