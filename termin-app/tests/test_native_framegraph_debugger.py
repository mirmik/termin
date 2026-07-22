from termin.engine import FrameGraphDebuggerMode
from termin.editor_native.framegraph_debugger import (
    NativeFramegraphPreviewSurface,
    build_native_framegraph_debugger,
    connect_framegraph_debugger_command,
)
from termin.editor_native.shell import build_native_editor_shell
from termin.gui_native import (
    Document,
    EventResult,
    Point,
    PointerEvent,
    PointerEventType,
    Rect,
)


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


class _PassItem:
    index = 3
    name = "Color"
    display_name = "Color *"


class _Target:
    def __init__(self):
        self.label = "Editor / Main"
        self.renderable = True


class _Model:
    def __init__(self):
        self.capture = _Capture()
        self.depth_capture = _Capture(is_depth=True)
        self.presenter = _Presenter()
        self.targets = [_Target()]
        self.selected_target_index = None
        self.selected_target_calls = []
        self.mode = FrameGraphDebuggerMode.InsidePass
        self._selected_pass_index = None
        self.selected_symbol = None
        self.selected_resource = ""
        self.channel_mode = 0
        self.paused = False
        self.highlight_hdr = False
        self.disconnect_count = 0
        self.connect_count = 0

    @property
    def selected_pass_index(self):
        return self._selected_pass_index

    @selected_pass_index.setter
    def selected_pass_index(self, index):
        self._selected_pass_index = index
        self.selected_symbol = "opaque" if index is not None else ""

    @property
    def selected_pass(self):
        return "Color" if self.selected_pass_index is not None else ""

    def refresh(self):
        pass

    def passes(self):
        return [_PassItem()]

    def symbols(self):
        return ["opaque"] if self.selected_pass_index is not None else []

    def resources(self):
        return ["RT_COLOR"]

    def select_target_at(self, index):
        self.selected_target_calls.append(index)
        self.selected_target_index = index
        return True

    def set_paused(self, paused):
        self.paused = paused

    def analyze_hdr(self):
        return "HDR: none"

    def finish_frame(self):
        pass

    def cancel_request(self):
        self.disconnect_count += 1

    def connect(self):
        self.connect_count += 1

    def disconnect(self):
        self.disconnect_count += 1

    def format_capture_info(self):
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
        self.fit_mode = True
        self.zoom = 1.0
        self.widget = self
        self.bounds = Rect(0.0, 0.0, 320.0, 240.0)

    def set_texture(self, texture, size):
        self.textures.append((texture, size))

    def clear_texture(self):
        self.textures.append((None, None))

    def fit_in_view(self):
        self.fit_mode = True
        self.zoom = 0.5

    def set_zoom(self, zoom, _anchor):
        self.fit_mode = False
        self.zoom = zoom


class _Root:
    visible = True


class _WindowHost:
    def __init__(self, document, context):
        self.document = document
        self.context = context
        self.callbacks = []
        self.render_requests = 0

    def add_pre_render_callback(self, callback):
        self.callbacks.append(callback)

    def remove_pre_render_callback(self, callback):
        self.callbacks.remove(callback)

    def request_render_update(self):
        self.render_requests += 1


class _ManagedWindow:
    def __init__(self, host, on_close):
        self.host = host
        self.on_close = on_close
        self.closed = False

    def request_render_update(self):
        self.host.request_render_update()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.on_close()


class _WindowManager:
    def __init__(self, context):
        self.main_host = _WindowHost(Document(), context)
        self.main_host.device = object()
        self.windows = []
        self.create_options = []

    def create_window(self, _title, _width, _height, *, document, on_close, **options):
        self.create_options.append(options)
        window = _ManagedWindow(_WindowHost(document, self.main_host.context), on_close)
        self.windows.append(window)
        return window


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
    assert preview.status_text() == "Source: 64x32 | Zoom: Fit (100%) | Pixel: —"

    preview.update_cursor(Point(12.75, 7.25))
    assert preview.status_text() == "Source: 64x32 | Zoom: Fit (100%) | Pixel: 12, 7"
    preview.actual_size()
    assert preview.status_text() == "Source: 64x32 | Zoom: 100% | Pixel: 12, 7"

    capture.width = 128
    assert preview.render(context)
    assert context.destroyed == [context.created[0][2]]
    preview.force_depth = True
    assert preview.render(context)
    assert presenter.draws[-1][-2:] == (5, False)

    preview.close()
    assert context.destroyed[-1] == context.created[-1][2]
    assert root.visible


def test_native_framegraph_preview_keeps_layout_slot_while_capture_arrives():
    context = _Context()
    image = _Image()
    capture = _Capture(ready=False)
    preview = NativeFramegraphPreviewSurface(
        context,
        image,
        _Root(),
        capture,
        _Presenter(),
    )

    assert not preview.render(context)
    assert preview.root.visible
    assert image.textures == []

    capture.ready = True
    capture.capture_tex = object()
    assert preview.render(context)
    assert preview.root.visible
    assert len(context.created) == 1
    assert image.textures[-1][0] == context.created[0][2]

    capture.ready = False
    capture.capture_tex = None
    assert not preview.render(context)
    assert image.textures[-1] == (None, None)


def _click(button) -> None:
    bounds = button.widget.bounds
    pointer = PointerEvent()
    pointer.x = bounds.x + bounds.width * 0.5
    pointer.y = bounds.y + bounds.height * 0.5
    pointer.type = PointerEventType.Down
    assert button.widget.dispatch_pointer_event(pointer) == EventResult.Handled
    pointer.type = PointerEventType.Up
    assert button.widget.dispatch_pointer_event(pointer) == EventResult.Handled


def test_native_framegraph_canvases_keep_independent_fit_zoom_and_pixel_status():
    model = _Model()
    context = _Context()
    window_manager = _WindowManager(context)
    debugger = build_native_framegraph_debugger(
        window_manager,
        model,
        request_render=lambda: None,
    )
    debugger.show()
    debugger.document.layout_roots(Rect(0.0, 0.0, 1180.0, 760.0))

    debugger.main_preview.target_size = (64, 32)
    debugger.depth_preview.target_size = (64, 32)
    debugger._refresh_preview_statuses()

    assert debugger.main_preview.canvas.fit_mode
    assert debugger.depth_preview.canvas.fit_mode
    assert "Source: 64x32" in debugger.main_status.text
    _click(debugger.main_actual_button)
    assert not debugger.main_preview.canvas.fit_mode
    assert debugger.main_preview.canvas.zoom == 1.0
    assert debugger.depth_preview.canvas.fit_mode

    target_point = debugger.main_preview.canvas.image_to_widget(Point(12.0, 7.0))
    pointer = PointerEvent()
    pointer.type = PointerEventType.Move
    pointer.x = target_point.x
    pointer.y = target_point.y
    assert (
        debugger.main_preview.canvas.widget.dispatch_pointer_event(pointer)
        == EventResult.Handled
    )
    assert "Zoom: 100%" in debugger.main_status.text
    assert "Pixel:" in debugger.main_status.text
    assert "Pixel: —" not in debugger.main_status.text

    _click(debugger.main_fit_button)
    assert debugger.main_preview.canvas.fit_mode
    debugger.close()


def test_native_framegraph_debugger_f12_projection_reopens_and_closes():
    document = Document()
    shell = build_native_editor_shell(document)
    model = _Model()
    context = _Context()
    window_manager = _WindowManager(context)
    renders = []
    debugger = build_native_framegraph_debugger(
        window_manager,
        model,
        request_render=lambda: renders.append(True),
    )
    assert debugger.document.root_count == 1
    assert debugger.document.root_at(0) == debugger.root.handle
    connect_framegraph_debugger_command(
        shell.menu_bar,
        shell.framegraph_debugger_command,
        debugger,
    )

    assert debugger.show()
    assert model.selected_target_calls == [0]
    assert model.selected_target_index == 0
    assert debugger.target_combo.selected_index == 0
    assert debugger.window is window_manager.windows[-1]
    assert window_manager.create_options[-1]["always_on_top"] is True
    assert debugger.render_previews in debugger.window.host.callbacks
    assert model.selected_pass_index == 3
    assert model.selected_symbol == "opaque"
    assert model.selected_resource == "RT_COLOR"
    assert debugger.pass_indices == [3]
    assert debugger.pass_json.text == '{"pass": "Color"}'
    assert debugger.stats_bar.text == "Scenes: 1"
    assert debugger.inside_panel.visible
    assert not debugger.between_panel.visible
    assert debugger.update()

    # A missing exact target must not be painted as item zero.  Reconnecting
    # the native session will choose a live target explicitly; ordinary UI
    # refresh remains an honest projection of the native selection.
    model.selected_target_index = None
    assert debugger.update()
    assert debugger.target_combo.selected_index == -1
    assert model.select_target_at(0)
    assert debugger.update()
    assert debugger.target_combo.selected_index == 0

    debugger.mode_combo.selected_index = 1
    debugger.update()
    assert model.mode == FrameGraphDebuggerMode.BetweenPasses
    assert debugger.between_panel.visible
    first_window = debugger.window
    debugger.dismiss()
    assert first_window.closed
    assert first_window.host.callbacks == []
    assert model.disconnect_count == 1
    assert not debugger.update()

    assert debugger.show()
    assert debugger.window is window_manager.windows[-1]
    debugger_root = debugger.root.handle
    debugger.close()
    assert model.disconnect_count == 2
    assert window_manager.windows[-1].closed
    assert not debugger.document.is_alive(debugger_root)
    assert renders
