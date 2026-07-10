from tcbase import Key

from termin.editor_core.signal import Signal
from termin.editor_native.framegraph_debugger import (
    NativeFramegraphPreviewSurface,
    build_native_framegraph_debugger,
    connect_framegraph_debugger_command,
)
from termin.editor_native.shell import build_native_editor_shell
from termin.gui_native import Document, Rect


class _Capture:
    def __init__(self, *, ready=False, is_depth=False):
        self.ready = ready
        self.is_depth = is_depth
        self.capture_tex = object() if ready else None
        self.width = 64
        self.height = 32

    def has_capture(self):
        return self.ready


class _Presenter:
    def __init__(self):
        self.draws = []

    def render(self, *args):
        self.draws.append(args)

    def read_depth_normalized(self, _device, _texture):
        return b"pixels", 64, 32


class _Core:
    def __init__(self):
        self.capture = _Capture()
        self.depth_capture = _Capture(is_depth=True)
        self.presenter = _Presenter()


class _PassItem:
    index = 3
    display_name = "Color *"


class _Target:
    def __init__(self):
        self.source = object()
        self.label = "Editor / Main"


class _Model:
    def __init__(self):
        self.core = _Core()
        self.targets = [_Target()]
        self.current_viewport = self.targets[0].source
        self.mode = "inside"
        self.selected_pass_index = None
        self.selected_symbol = None
        self.debug_source_res = ""
        self.channel_mode = 0
        self.debug_paused = False
        self.highlight_hdr = False
        self.disconnect_count = 0
        self.lists_changed = Signal()
        self.selection_changed = Signal()
        self.info_changed = Signal()
        self.capture_updated = Signal()
        self.preview_params_changed = Signal()
        self.hdr_stats_changed = Signal()

    def refresh_viewports(self):
        self.lists_changed.emit(self)

    def get_passes(self):
        return [_PassItem()]

    def get_symbols(self):
        return ["opaque"] if self.selected_pass_index is not None else []

    def get_resources(self):
        return ["RT_COLOR"]

    def set_viewport_by_index(self, _index):
        pass

    def set_mode(self, mode):
        self.mode = mode
        self.selection_changed.emit(self)

    def set_selected_pass_by_index(self, index):
        self.selected_pass_index = index
        self.selected_symbol = "opaque"
        self.lists_changed.emit(self)
        self.selection_changed.emit(self)

    def set_selected_symbol(self, symbol):
        self.selected_symbol = symbol

    def set_source_resource(self, resource):
        self.debug_source_res = resource
        self.selection_changed.emit(self)

    def set_channel_mode(self, mode):
        self.channel_mode = mode
        self.preview_params_changed.emit(self)

    def set_paused(self, paused):
        self.debug_paused = paused

    def set_highlight_hdr(self, enabled):
        self.highlight_hdr = enabled
        self.preview_params_changed.emit(self)

    def analyze_hdr(self):
        self.hdr_stats_changed.emit("HDR: none")

    def refresh_render_stats(self):
        self.info_changed.emit(self)

    def notify_frame_rendered(self):
        self.capture_updated.emit(self)
        self.info_changed.emit(self)

    def disconnect(self):
        self.disconnect_count += 1

    def format_fbo_info(self):
        return "<b>RT_COLOR</b>"

    def format_pipeline_info(self):
        return "<pre>Color: {} -&gt; {RT_COLOR}</pre>"

    def format_pass_json(self):
        return '{"pass": "Color"}'

    def format_render_stats(self):
        return "Scenes: 1"

    def format_timing(self):
        return "CPU: 1ms"


class _Context:
    def __init__(self):
        self.created = []
        self.destroyed = []

    def create_color_attachment(self, width, height):
        target = object()
        self.created.append((width, height, target))
        return target

    def destroy_texture(self, target):
        self.destroyed.append(target)


class _Image:
    def __init__(self):
        self.textures = []

    def set_texture(self, texture, size):
        self.textures.append((texture, size))


class _Root:
    visible = False


def test_native_framegraph_preview_surface_presents_resizes_and_releases():
    context = _Context()
    image = _Image()
    capture = _Capture(ready=True)
    presenter = _Presenter()
    root = _Root()
    preview = NativeFramegraphPreviewSurface(
        context,
        image,
        root,
        capture,
        presenter,
        channel_mode=4,
        highlight_hdr=True,
    )

    assert preview.render(context)
    assert root.visible
    assert len(context.created) == 1
    draw = presenter.draws[-1]
    assert draw[-2:] == (4, True)
    assert image.textures[-1][1].width == 64

    capture.width = 128
    assert preview.render(context)
    assert context.destroyed == [context.created[0][2]]
    preview.force_depth = True
    assert preview.render(context)
    assert presenter.draws[-1][-2:] == (5, False)

    preview.close()
    assert context.destroyed[-1] == context.created[-1][2]
    assert not root.visible


def test_native_framegraph_debugger_f12_projection_reopens_and_closes():
    document = Document()
    shell = build_native_editor_shell(document)
    model = _Model()
    context = _Context()
    callbacks = []
    renders = []
    debugger = build_native_framegraph_debugger(
        document,
        model,
        context=context,
        device=object(),
        viewport=lambda: Rect(0.0, 0.0, 1280.0, 800.0),
        request_render=lambda: renders.append(True),
        add_pre_render_callback=callbacks.append,
        remove_pre_render_callback=callbacks.remove,
    )
    connect_framegraph_debugger_command(
        shell.menu_bar,
        shell.framegraph_debugger_command,
        debugger,
    )

    assert shell.menu_bar.dispatch_shortcut(Key.F12.value, 0)
    assert debugger.dialog.open
    assert model.selected_pass_index == 3
    assert model.selected_symbol == "opaque"
    assert model.debug_source_res == "RT_COLOR"
    assert debugger.pass_indices == [3]
    assert debugger.pass_json.text == '{"pass": "Color"}'
    assert debugger.stats_bar.text == "Scenes: 1"
    assert debugger.inside_panel.visible
    assert not debugger.between_panel.visible
    assert debugger.update()

    debugger.mode_combo.selected_index = 1
    assert model.mode == "between"
    assert debugger.between_panel.visible
    assert debugger.dialog.activate("close")
    assert model.disconnect_count == 1
    assert not debugger.update()

    assert debugger.show()
    assert debugger.dialog.open
    debugger.close()
    assert model.disconnect_count == 2
    assert callbacks == []
    assert not document.is_alive(debugger.dialog.handle)
    assert renders
