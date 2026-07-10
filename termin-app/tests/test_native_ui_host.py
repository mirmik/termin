from pathlib import Path

import pytest

from tcbase import Key
from termin.editor_native import (
    NativeUiEventRouter,
    build_native_editor_shell,
    resolve_native_ui_font,
)
from termin.editor_native.shell import NativeMenuActivationRoute
from termin.gui_native import (
    Document,
    DrawCommandType,
    DrawList,
    DrawListRenderer,
    EventResult,
    KeyCode,
    PointerEventType,
    PaintContext,
    Rect,
    StyleRole,
    Widget,
)


class EventProbe(Widget):
    def __init__(self) -> None:
        self.pointer_events = []
        self.key_events = []
        self.text_events = []

    def layout(self, rect) -> None:
        self.bounds = rect

    def pointer_event(self, event):
        self.pointer_events.append((event.type, event.button, event.click_count, event.modifiers))
        return EventResult.Handled

    def key_event(self, event):
        self.key_events.append((event.type, event.key, event.modifiers, event.repeat))
        return EventResult.Handled

    def text_event(self, text):
        self.text_events.append(text)
        return EventResult.Handled


def test_native_menu_activation_route_filters_local_command_id_collisions():
    class MenuBarProbe:
        def connect_activated(self, callback):
            self.callback = callback
            return 17

    menu_bar = MenuBarProbe()
    routed = []
    route = NativeMenuActivationRoute(menu_bar, 1)

    assert route.connect_activated(lambda *args: routed.append(args)) == 17
    menu_bar.callback(0, 1, "file-command")
    menu_bar.callback(1, 1, "edit-command")

    assert routed == [(1, 1, "edit-command")]

def test_native_ui_key_codes_match_canonical_platform_values():
    assert KeyCode.Unknown.value == Key.UNKNOWN.value
    assert KeyCode.Escape.value == Key.ESCAPE.value
    assert KeyCode.Backspace.value == Key.BACKSPACE.value
    assert KeyCode.Delete.value == Key.DELETE.value
    assert KeyCode.Left.value == Key.LEFT.value
    assert KeyCode.F12.value == Key.F12.value
    assert KeyCode.S.value == Key.S.value


def test_native_ui_event_router_preserves_click_keys_text_and_file_drop():
    document = Document()
    probe = EventProbe()
    handle = document.adopt_root(probe, "native-editor-event-probe")
    probe.focusable = True
    document.layout_roots(Rect(0.0, 0.0, 320.0, 200.0))
    assert document.set_focus(handle)
    drops = []

    def handle_drop(path, x, y, modifiers):
        drops.append((path, x, y, modifiers))
        return True

    router = NativeUiEventRouter(
        document,
        17,
        file_drop_handler=handle_drop,
    )

    result = router.route(
        {
            "type": "mouse_down",
            "window_id": 17,
            "x": 12.0,
            "y": 14.0,
            "button": 0,
            "click_count": 2,
            "mods": 3,
        }
    )
    assert result.keep_running and result.routed
    assert [event[0] for event in probe.pointer_events] == [
        PointerEventType.Enter,
        PointerEventType.Down,
    ]
    assert probe.pointer_events[-1] == (PointerEventType.Down, 0, 2, 3)

    result = router.route(
        {
            "type": "key_down",
            "window_id": 17,
            "key": Key.S.value,
            "mods": 2,
            "repeat": True,
        }
    )
    assert result.routed
    assert probe.key_events[0][1:] == (KeyCode.S, 2, True)

    assert router.route({"type": "text_input", "window_id": 17, "text": "Привет"}).routed
    assert probe.text_events == ["Привет"]

    assert router.route(
        {
            "type": "file_drop",
            "window_id": 17,
            "path": "/tmp/scene.glb",
            "x": 20.0,
            "y": 30.0,
            "mods": 1,
        }
    ).routed
    assert drops == [("/tmp/scene.glb", 20.0, 30.0, 1)]

    assert not router.route({"type": "mouse_move", "window_id": 18}).routed
    assert router.route({"type": "window_close", "window_id": 18}).keep_running
    assert not router.route({"type": "window_close", "window_id": 17}).keep_running
    assert not router.route({"type": "quit"}).keep_running


def test_native_ui_font_resolution_honors_explicit_path(tmp_path: Path):
    font = tmp_path / "editor.ttf"
    font.write_bytes(b"test-font")
    assert resolve_native_ui_font(font) == font
    with pytest.raises(FileNotFoundError, match="missing file"):
        resolve_native_ui_font(tmp_path / "missing.ttf")


def test_native_editor_shell_has_stable_headless_root_and_chrome():
    document = Document()
    shell = build_native_editor_shell(document)
    renderer = DrawListRenderer()
    assert renderer.set_default_font_path(str(resolve_native_ui_font()), 15)
    renderer.bind_text_measurer(document)

    document.layout_roots(Rect(0.0, 0.0, 1280.0, 720.0))
    draw_list = DrawList()
    document.paint(PaintContext(draw_list))

    assert shell.root.stable_id == "editor.root"
    assert shell.central.stable_id == "editor.central"
    assert shell.main_splitter.widget.stable_id == "editor.main-splitter"
    assert shell.left_splitter.widget.stable_id == "editor.left-splitter"
    assert shell.right_splitter.widget.stable_id == "editor.right-splitter"
    assert shell.navigation_tabs.widget.stable_id == "editor.navigation-tabs"
    assert shell.hierarchy_host.stable_id == "editor.hierarchy-host"
    assert shell.rendering_host.stable_id == "editor.rendering-host"
    assert shell.navigation_tabs.page_count == 2
    assert shell.navigation_tabs.page_title(0) == "Scene"
    assert shell.navigation_tabs.page_title(1) == "Rendering"
    assert shell.navigation_tabs.page_handle(0) == shell.hierarchy_host.handle
    assert shell.navigation_tabs.page_handle(1) == shell.rendering_host.handle
    assert shell.bottom_tabs.widget.stable_id == "editor.bottom-tabs"
    assert shell.bottom_tabs.page_count == 2
    assert shell.bottom_tabs.page_title(0) == "Project"
    assert shell.bottom_tabs.page_title(1) == "Console"
    assert shell.project_host.stable_id == "editor.project-host"
    assert shell.console_host.stable_id == "editor.console-host"
    assert shell.workspace_host.stable_id == "editor.workspace-host"
    assert shell.inspector_host.stable_id == "editor.inspector-host"
    assert shell.menu_bar.entries[0].stable_id == "file"
    assert shell.tool_bar.model.command_count == 1
    assert shell.status_bar.displayed_text == "Ready | Native editor host"
    assert shell.project_host.bounds.y > shell.workspace_host.bounds.y
    assert shell.project_host.bounds.width == pytest.approx(shell.central.bounds.width)
    assert shell.workspace_host.bounds.x > shell.hierarchy_host.bounds.x
    assert shell.inspector_host.bounds.x > shell.workspace_host.bounds.x
    assert shell.tool_bar.widget.bounds.x == pytest.approx(shell.workspace_host.bounds.x)
    assert shell.tool_bar.widget.bounds.width == pytest.approx(shell.workspace_host.bounds.width)
    initial_navigation_width = shell.navigation_tabs.widget.bounds.width
    initial_bottom_height = shell.bottom_tabs.widget.bounds.height
    shell.left_splitter.split_fraction = 0.30
    shell.main_splitter.split_fraction = 0.55
    document.layout_roots(Rect(0.0, 0.0, 1280.0, 720.0))
    assert shell.navigation_tabs.widget.bounds.width > initial_navigation_width
    assert shell.bottom_tabs.widget.bounds.height > initial_bottom_height
    assert shell.tool_bar.widget.bounds.x == pytest.approx(shell.workspace_host.bounds.x)
    assert shell.tool_bar.widget.bounds.width == pytest.approx(shell.workspace_host.bounds.width)
    assert draw_list.command_count > 20
    assert any(command.type == DrawCommandType.Text for command in draw_list.commands)


def test_editor_cli_accepts_explicit_native_backend(monkeypatch):
    from termin.editor.run_editor import _parse_editor_args

    monkeypatch.setattr("sys.argv", ["termin_editor", "--ui=native"])
    assert _parse_editor_args() == (None, None, "native")


def test_editor_cli_defaults_to_native_backend(monkeypatch):
    from termin.editor.run_editor import _parse_editor_args

    monkeypatch.setattr("sys.argv", ["termin_editor"])
    assert _parse_editor_args() == (None, None, "native")


def test_editor_cli_keeps_explicit_legacy_tcgui_backend(monkeypatch):
    from termin.editor.run_editor import _parse_editor_args

    monkeypatch.setattr("sys.argv", ["termin_editor", "--ui=tcgui"])
    assert _parse_editor_args() == (None, None, "tcgui")


def test_native_screenshot_composes_current_document_before_readback(monkeypatch, tmp_path):
    from termin.editor_native.ui_host import NativeUiHost

    host = NativeUiHost.__new__(NativeUiHost)
    host._color_target = "previous-target"
    host._target_size = (320, 200)
    calls = []

    class Device:
        def wait_idle(self):
            calls.append("wait-idle")

    host.device = Device()

    def render():
        calls.append("render")
        host._color_target = "current-target"
        return True

    host.render = render

    def capture(source, device, **options):
        calls.append((source, device, options["width"], options["height"]))
        return {"path": options["output_path"]}

    monkeypatch.setattr("termin.mcp.screenshot.capture_texture_screenshot", capture)
    output = tmp_path / "native.png"
    result = host.capture_screenshot(output_path=str(output))

    assert calls == [
        "render",
        "wait-idle",
        ("current-target", host.device, 320, 200),
    ]
    assert result == {"path": str(output)}


def test_native_ui_host_pre_render_runs_before_document_paint():
    from termin.editor_native.ui_host import NativeUiHost

    calls = []

    class Window:
        def framebuffer_size(self):
            return 320, 200

        def present(self, target):
            calls.append(("present", target))

    class Context:
        def create_color_attachment(self, width, height):
            calls.append(("create", width, height))
            return "target"

        def begin_frame(self):
            calls.append("begin-frame")

        def begin_pass(self, target, **_options):
            calls.append(("begin-pass", target))

        def end_pass(self):
            calls.append("end-pass")

        def end_frame(self):
            calls.append("end-frame")

    class Document:
        def layout_roots(self, _rect):
            calls.append("layout")

        def paint(self, _context):
            calls.append("paint")

    class DrawList:
        def clear(self):
            calls.append("clear")

    class Renderer:
        def render(self, _context, _draw_list, width, height):
            calls.append(("render", width, height))

    host = NativeUiHost.__new__(NativeUiHost)
    host.window = Window()
    host.context = Context()
    host.document = Document()
    host.draw_list = DrawList()
    host.paint_context = object()
    host.renderer = Renderer()
    host._color_target = None
    host._target_size = (0, 0)
    host._render_requested = True
    host._pre_render_callbacks = [lambda _context: calls.append("pre-render")]

    assert host.render()
    assert calls.index("begin-frame") < calls.index("pre-render") < calls.index("paint")
    assert calls[-1] == ("present", "target")


def test_native_ui_host_applies_font_size_to_all_theme_roles():
    from termin.editor_native.ui_host import NativeUiHost

    host = NativeUiHost.__new__(NativeUiHost)
    host.document = Document()
    host._render_requested = False

    host.apply_font_size(18.0)

    for style_role in StyleRole:
        role = host.document.theme.role(style_role)
        assert role.base.font_size == 18.0
    assert host.render_requested
