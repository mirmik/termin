from pathlib import Path
from types import SimpleNamespace

import termin.editor_native.framegraph_debugger as framegraph_module
from termin.editor._editor_native import FrameGraphDebuggerView
from termin.editor_native.framegraph_debugger import (
    build_native_framegraph_debugger,
    connect_framegraph_debugger_command,
)
from termin.engine import EngineCore, FrameGraphDebugger
from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy


class _Content:
    def __init__(self, document):
        self.document = document
        self.callbacks = []
        self.render_requests = 0
        self.device = object()

    def add_pre_render_callback(self, callback):
        self.callbacks.append(callback)

    def remove_pre_render_callback(self, callback):
        self.callbacks.remove(callback)

    def request_render_update(self):
        self.render_requests += 1


class _Window:
    def __init__(self, document, on_close):
        self.content = _Content(document)
        self._on_close = on_close
        self.closed = False

    def request_render_update(self):
        self.content.request_render_update()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self._on_close()


class _WindowManager:
    def __init__(self):
        self.main_document = tc_ui_document_create()
        self.main = SimpleNamespace(content=_Content(self.main_document))
        self.windows = []
        self.create_options = []

    def create_window(self, _title, _width, _height, *, document, on_close, **options):
        self.create_options.append(options)
        window = _Window(document, on_close)
        self.windows.append(window)
        return window

    def close(self):
        tc_ui_document_destroy(self.main_document)


class _NativeView:
    def __init__(self, document, model, request_render):
        self.document = document
        self.model = model
        self.request_render = request_render
        self.active = False
        self.closed = False
        self.activate_count = 0
        self.deactivate_count = 0
        self.update_count = 0
        self.resources = []
        self.preview_contexts = []

    def activate(self):
        if self.active:
            return False
        self.active = True
        self.activate_count += 1
        self.request_render()
        return True

    def deactivate(self):
        if self.active:
            self.active = False
            self.deactivate_count += 1

    def update(self):
        self.update_count += 1
        return self.active

    def show_resource(self, resource):
        self.resources.append(resource)
        return resource == "RT_COLOR"

    def render_previews(self, context):
        self.preview_contexts.append(context)
        return True

    def refresh_depth(self, _device):
        return "Depth: 64x32 read OK"

    def close(self):
        self.deactivate()
        self.closed = True


class _MenuBar:
    def __init__(self):
        self.activated = None

    def connect_activated(self, callback):
        self.activated = callback


def test_framegraph_debugger_python_layer_is_window_bootstrap(monkeypatch):
    monkeypatch.setattr(framegraph_module, "FrameGraphDebuggerView", _NativeView)
    manager = _WindowManager()
    scene_renders = []
    model = object()
    debugger = build_native_framegraph_debugger(
        manager,
        model,
        request_render=lambda: scene_renders.append(True),
    )

    assert debugger.model is model
    assert debugger.view.document == debugger.document
    assert debugger.show()
    assert debugger.view.activate_count == 1
    assert manager.create_options[-1]["always_on_top"] is True
    first_window = debugger.window
    assert debugger.view.render_previews in first_window.content.callbacks
    assert debugger.update()
    assert debugger.view.update_count == 1
    assert debugger.show_resource("RT_COLOR")
    assert debugger.refresh_depth() == "Depth: 64x32 read OK"

    first_window.content.callbacks[0]("render-context")
    assert debugger.view.preview_contexts == ["render-context"]
    debugger.dismiss()
    assert first_window.closed
    assert first_window.content.callbacks == []
    assert debugger.view.deactivate_count == 1
    assert not debugger.update()

    assert debugger.show()
    assert debugger.window is manager.windows[-1]
    debugger.close()
    assert debugger.view.closed
    assert debugger.view.deactivate_count == 2
    assert not debugger.document.valid
    assert scene_renders
    manager.close()


def test_framegraph_debugger_command_opens_native_view(monkeypatch):
    monkeypatch.setattr(framegraph_module, "FrameGraphDebuggerView", _NativeView)
    manager = _WindowManager()
    debugger = build_native_framegraph_debugger(
        manager,
        object(),
        request_render=lambda: None,
    )
    menu_bar = _MenuBar()
    command_id = 71
    connect_framegraph_debugger_command(
        menu_bar,
        command_id,
        debugger,
    )

    menu_bar.activated(0, command_id, object())
    assert debugger.window is manager.windows[-1]

    debugger.close()
    manager.close()


def test_framegraph_debugger_python_module_contains_no_widget_projection():
    source = (
        Path(framegraph_module.__file__)
        .read_text(encoding="utf-8")
    )

    assert "FrameGraphDebuggerView" in source
    assert "create_vstack" not in source
    assert "create_canvas" not in source
    assert "connect_changed" not in source
    assert "NativeFramegraphPreviewSurface" not in source


def test_native_framegraph_view_binding_builds_into_tc_document():
    engine = EngineCore()
    document = tc_ui_document_create()
    debugger = FrameGraphDebugger(engine.rendering_manager)
    view = FrameGraphDebuggerView(document, debugger, lambda: None)
    try:
        assert view.root_stable_id == "editor.framegraph-debugger"
        assert document.root_count == 1
        assert view.activate()
        assert view.state_status_text == "Unbound"
        view.close()
        assert document.root_count == 0
    finally:
        view.close()
        tc_ui_document_destroy(document)
        del view
        del debugger
        engine.shutdown()
