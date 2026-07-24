from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tcbase import Key
from termin.editor_native import (
    EditorWindowRegistry,
    NativeUiEventPolicy,
    build_native_editor_shell,
    resolve_native_ui_font,
)
from termin.editor_native.shell import NativeMenuActivationRoute
from termin.editor_core.menu_bar_model import build_editor_menu_inventory
from termin.editor_native.metrics import EDITOR_UI_METRICS
from termin.gui_native import (
    CommandKind,
    DrawCommandType,
    DrawList,
    DrawListRenderer,
    KeyCode,
    PaintContext,
    Rect,
    StyleRole,
)


class _WindowManagerTestWindow:
    def __init__(self, window_id):
        self._window_id = window_id
        self._should_close = False
        self.closed = False

    def window_id(self):
        return self._window_id

    def set_should_close(self, value):
        self._should_close = bool(value)

    def should_close(self):
        return self._should_close

    def close(self):
        self.closed = True


class _WindowManagerTestDocument:
    def __init__(self):
        self.theme = object()


class _WindowManagerTestContent:
    _next_window_id = 1

    def __init__(self, document=None, *, graphics=None, **options):
        self.window = _WindowManagerTestWindow(self._next_window_id)
        type(self)._next_window_id += 1
        self.graphics = graphics
        self.document = document or _WindowManagerTestDocument()
        self.font_path = Path("/tmp/editor.ttf")
        self.render_requested = False
        self.render_count = 0
        self.deferred_count = 0
        self.closed = False
        self.options = options
        self.event_results = []

    def request_render_update(self):
        self.render_requested = True

    def render(self):
        self.render_requested = False
        self.render_count += 1
        return True

    def poll_events(self):
        if self.event_results:
            return self.event_results.pop(0)
        return True, 0

    def close(self):
        self.closed = True
        self.window.close()


class _NativeWindowManagerProbe:
    def __init__(self):
        self._handles = {1}
        self._next_handle = 2
        self.pump_count = 0
        self.destroyed = []
        self.closed = False

    def contains(self, handle):
        return handle in self._handles

    def create_window(self, _title, _width, _height):
        handle = self._next_handle
        self._next_handle += 1
        self._handles.add(handle)
        return handle

    def destroy_window(self, handle):
        self._handles.remove(handle)
        self.destroyed.append(handle)

    def pump_events(self):
        self.pump_count += 1
        return 1

    def close(self):
        self.closed = True
        self._handles.clear()


def test_editor_window_registry_routes_renders_and_closes_secondary_windows():
    graphics = object()
    native_windows = _NativeWindowManagerProbe()
    main_host = _WindowManagerTestContent(graphics=graphics)
    main_host.event_results = [(True, 0), (True, 0), (False, 0)]
    manager = EditorWindowRegistry(native_windows, 1, main_host)
    closed = []
    secondary_content = None

    def create_content(_manager, _handle):
        nonlocal secondary_content
        secondary_content = _WindowManagerTestContent(
            _WindowManagerTestDocument(),
            graphics=graphics,
            enable_text_input=False,
        )
        secondary_content.document.theme = main_host.document.theme
        return secondary_content

    secondary = manager.create_window(
        "Debugger",
        800,
        600,
        on_close=lambda: closed.append("secondary"),
        content_factory=create_content,
    )

    assert secondary.content is secondary_content
    assert secondary.content.graphics is graphics
    assert secondary.content.options["enable_text_input"] is False
    assert secondary.content.document.theme is main_host.document.theme
    secondary.content.event_results = [(True, 1), (False, 0)]
    assert manager.poll_events() == (True, 1)
    assert native_windows.pump_count == 1
    secondary.content.request_render_update()
    assert manager.render_requested() == 1
    assert secondary.content.render_count == 1

    assert manager.poll_events() == (True, 1)
    assert secondary.closed
    assert secondary.content.closed
    assert closed == ["secondary"]
    assert manager.windows == ()
    assert manager.poll_events() == (False, 1)
    manager.close()
    assert main_host.closed
    assert native_windows.closed


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


def test_native_ui_event_policy_intercepts_file_drop_without_owning_event_dispatch():
    from termin.editor_native.ui_host import NativeWidgetContent

    drops = []

    def handle_drop(path, x, y, modifiers):
        drops.append((path, x, y, modifiers))
        return True

    host = NativeWidgetContent.__new__(NativeWidgetContent)
    host.event_policy = NativeUiEventPolicy(file_drop_handler=handle_drop)
    assert host._intercept_event(
        {
            "type": "file_drop",
            "path": "/tmp/scene.glb",
            "x": 20.0,
            "y": 30.0,
            "mods": 1,
        }
    )
    assert drops == [("/tmp/scene.glb", 20.0, 30.0, 1)]


def test_native_ui_event_policy_consumes_enabled_shortcut_and_ignores_repeats():
    from termin.editor_native.ui_host import NativeWidgetContent

    document = tc_ui_document_create()
    shell = build_native_editor_shell(document)
    shell.edit_menu_model.set_enabled(shell.undo_command, True)
    host = NativeWidgetContent.__new__(NativeWidgetContent)
    host.event_policy = NativeUiEventPolicy(
        shortcut_dispatcher=shell.menu_bar.dispatch_shortcut,
    )
    activated = []
    shell.menu_route("edit").connect_activated(
        lambda _menu, command_id, _command: activated.append(command_id)
    )

    assert host._intercept_event(
        {"type": "key_down", "key": ord("Z"), "mods": 2, "repeat": False}
    )
    assert activated == [shell.undo_command]
    assert not host._intercept_event(
        {"type": "key_down", "key": ord("Z"), "mods": 2, "repeat": True}
    )
    tc_ui_document_destroy(document)


def test_native_editor_continuously_composes_only_in_game_mode():
    from termin.editor_native.event_loop import _game_mode_requires_continuous_render

    class Model:
        is_game_mode = False

    class Controller:
        model = Model()

    controller = Controller()
    assert not _game_mode_requires_continuous_render(None)
    assert not _game_mode_requires_continuous_render(controller)
    controller.model.is_game_mode = True
    assert _game_mode_requires_continuous_render(controller)


def test_completed_scene_render_requests_ui_presentation():
    from termin.editor_native.run_editor import _complete_editor_scene_render

    calls = []

    class Viewport:
        def after_render(self):
            calls.append("viewport")

    class Host:
        def request_render_update(self):
            calls.append("present")

    _complete_editor_scene_render(Viewport(), Host())

    assert calls == ["viewport", "present"]


def test_native_ui_font_resolution_honors_explicit_path(tmp_path: Path):
    font = tmp_path / "editor.ttf"
    font.write_bytes(b"test-font")
    assert resolve_native_ui_font(font) == font
    with pytest.raises(FileNotFoundError, match="missing file"):
        resolve_native_ui_font(tmp_path / "missing.ttf")


def test_native_ui_font_is_installed_in_sdk(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    sdk_root = Path(os.environ["TERMIN_SDK"]).resolve()
    installed_font = sdk_root / "share" / "termin" / "fonts" / "DroidSans.ttf"

    assert installed_font.is_file()
    assert resolve_native_ui_font() == installed_font


def test_native_ui_font_resolution_uses_runtime_sdk_root(monkeypatch, tmp_path: Path):
    sdk_root = tmp_path / "runtime-sdk"
    installed_font = sdk_root / "share" / "termin" / "fonts" / "DroidSans.ttf"
    installed_font.parent.mkdir(parents=True)
    installed_font.write_bytes(b"test-font")
    monkeypatch.setenv("TERMIN_SDK", str(sdk_root))
    monkeypatch.chdir(tmp_path)

    assert resolve_native_ui_font() == installed_font


def test_native_editor_shell_has_stable_headless_root_and_chrome():
    document = tc_ui_document_create()
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
    assert shell.bottom_tabs.page_count == 3
    assert shell.bottom_tabs.page_title(0) == "Project"
    assert shell.bottom_tabs.page_title(1) == "Console"
    assert shell.bottom_tabs.page_title(2) == "Python Console"
    assert shell.project_host.stable_id == "editor.project-host"
    assert shell.console_host.stable_id == "editor.console-host"
    assert shell.python_console_host.stable_id == "editor.python-console-host"
    assert shell.profiler_host.stable_id == "editor.profiler-host"
    assert shell.workspace_host.stable_id == "editor.workspace-host"
    assert shell.inspector_host.stable_id == "editor.inspector-host"
    assert shell.menu_bar.entries[0].stable_id == "file"
    assert shell.tool_bar.model.command_count == 2
    assert shell.tool_bar.widget.bounds.height == pytest.approx(EDITOR_UI_METRICS.toolbar)
    assert shell.toolbar_model.command(shell.toolbar_play_command).data.icon == ""
    assert shell.status_bar.displayed_text == "Ready | Native editor host"
    assert shell.project_host.bounds.y > shell.workspace_host.bounds.y
    assert shell.project_host.bounds.width == pytest.approx(shell.central.bounds.width)
    assert shell.workspace_host.bounds.x > shell.hierarchy_host.bounds.x
    assert shell.inspector_host.bounds.x > shell.workspace_host.bounds.x
    play_rect = shell.tool_bar.item_rects[0]
    pause_rect = shell.tool_bar.item_rects[1]
    assert (play_rect.x + pause_rect.x + pause_rect.width) / 2.0 == pytest.approx(
        shell.workspace_host.bounds.x + shell.workspace_host.bounds.width / 2.0
    )
    document.layout_roots(Rect(0.0, 0.0, 2048.0, 1152.0))
    assert shell.navigation_tabs.widget.bounds.width == pytest.approx(225.0, abs=3.0)
    assert shell.inspector_host.bounds.width == pytest.approx(360.0, abs=1.0)
    assert shell.bottom_tabs.widget.bounds.height == pytest.approx(306.0, abs=4.0)
    initial_navigation_width = shell.navigation_tabs.widget.bounds.width
    initial_bottom_height = shell.bottom_tabs.widget.bounds.height
    shell.left_splitter.split_fraction = 0.30
    shell.main_splitter.split_fraction = 0.55
    document.layout_roots(Rect(0.0, 0.0, 2048.0, 1152.0))
    assert shell.navigation_tabs.widget.bounds.width > initial_navigation_width
    assert shell.bottom_tabs.widget.bounds.height > initial_bottom_height
    play_rect = shell.tool_bar.item_rects[0]
    pause_rect = shell.tool_bar.item_rects[1]
    assert (play_rect.x + pause_rect.x + pause_rect.width) / 2.0 == pytest.approx(
        shell.workspace_host.bounds.x + shell.workspace_host.bounds.width / 2.0
    )
    assert draw_list.command_count > 20
    assert any(command.type == DrawCommandType.Text for command in draw_list.commands)
    tc_ui_document_destroy(document)


def test_native_editor_shell_projects_prefab_editing_chrome() -> None:
    document = tc_ui_document_create()
    shell = build_native_editor_shell(document)

    assert not shell.prefab_tool_bar.widget.visible
    assert shell.toolbar_model.command(shell.toolbar_play_command).data.enabled

    shell.set_prefab_editing(True, "Guard")

    assert shell.prefab_tool_bar.widget.visible
    assert (
        shell.prefab_toolbar_model.command(shell.prefab_label_command).data.label
        == "Editing Prefab: Guard"
    )
    assert not shell.toolbar_model.command(shell.toolbar_play_command).data.enabled

    shell.set_prefab_editing(False)

    assert not shell.prefab_tool_bar.widget.visible
    assert shell.toolbar_model.command(shell.toolbar_play_command).data.enabled
    tc_ui_document_destroy(document)


def test_native_shell_projects_the_canonical_menu_inventory():
    document = tc_ui_document_create()
    shell = build_native_editor_shell(document)
    specs = build_editor_menu_inventory()
    assert [entry.label for entry in shell.menu_bar.entries] == [spec.name for spec in specs]
    for entry, spec in zip(shell.menu_bar.entries, specs, strict=True):
        expected = [item.label for item in spec.items if item is not None]
        actual = [
            entry.menu.command(command_id).data.label
            for command_id in range(1, entry.menu.command_count + 1)
            if entry.menu.command(command_id).data.kind != CommandKind.Separator
        ]
        assert actual[: len(expected)] == expected

    assert shell.game_menu_model.command(shell.run_standalone_command).data.shortcut == "F6"
    tc_ui_document_destroy(document)


def test_editor_cli_accepts_native_backend_selection(monkeypatch):
    from termin.editor.run_editor import _parse_editor_args

    monkeypatch.setattr("sys.argv", ["termin_editor", "--ui=native"])
    assert _parse_editor_args() == (None, None, "native")


def test_editor_cli_defaults_to_native_backend(monkeypatch):
    from termin.editor.run_editor import _parse_editor_args

    monkeypatch.setattr("sys.argv", ["termin_editor"])
    assert _parse_editor_args() == (None, None, "native")


def test_editor_cli_accepts_legacy_tcgui_backend_for_migration_comparison(monkeypatch, capsys):
    from termin.editor.run_editor import _parse_editor_args

    monkeypatch.setattr("sys.argv", ["termin_editor", "--ui=tcgui"])
    assert _parse_editor_args() == (None, None, "tcgui")
    assert "migration comparison" in capsys.readouterr().out


def test_native_screenshot_composes_current_document_before_readback(monkeypatch, tmp_path):
    from termin.editor_native.ui_host import NativeWidgetContent

    host = NativeWidgetContent.__new__(NativeWidgetContent)
    calls = []

    class GuiHost:
        color_target = "current-target"
        framebuffer_size = (320, 200)

        def wait_idle(self):
            calls.append("wait-idle")

    host.adapter = GuiHost()
    host.device = object()

    def render():
        calls.append("render")
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
    from termin.editor_native.ui_host import NativeWidgetContent

    calls = []

    class GuiHost:
        repaint_requested = True

        def render_frame(self):
            calls.append("begin-frame")
            host._before_ui_frame()
            calls.append("paint")
            calls.append("present")
            return True

        def request_repaint(self):
            self.repaint_requested = True

    host = NativeWidgetContent.__new__(NativeWidgetContent)
    host.adapter = GuiHost()
    host.context = object()
    host._image_previews = []

    def pre_render(_context):
        calls.append("pre-render")
        host.request_render_update()

    host._pre_render_callbacks = [pre_render]

    assert host.render()
    assert calls.index("begin-frame") < calls.index("pre-render") < calls.index("paint")
    assert calls[-1] == "present"
    assert host.render_requested


def test_native_ui_host_uploads_image_preview_through_render_context():
    from termin.editor_native.ui_host import NativeWidgetContent

    class Handle:
        valid = True

    class Image:
        handle = Handle()

        def __init__(self) -> None:
            self.textures = []

        def set_texture(self, texture, size) -> None:
            self.textures.append((texture, size))

    class _ImagePreviewDocument:
        def is_alive(self, handle) -> bool:
            return handle.valid

    class Context:
        def __init__(self) -> None:
            self.created = []
            self.destroyed = []

        def create_texture_rgba8(self, width, height, pixels):
            self.created.append((width, height, pixels.copy()))
            return "preview-texture"

        def destroy_texture(self, texture) -> None:
            self.destroyed.append(texture)

    host = NativeWidgetContent.__new__(NativeWidgetContent)
    host.document = _ImagePreviewDocument()
    host.context = Context()
    host._image_previews = []
    host.adapter = SimpleNamespace(request_repaint=lambda: None)
    image = Image()

    release = host.register_image_preview(
        image,
        np.array([[[12, 34, 56]]], dtype=np.uint8),
    )
    host._sync_image_previews()

    assert host.context.created[0][:2] == (1, 1)
    assert host.context.created[0][2].tolist() == [[[12, 34, 56, 255]]]
    assert image.textures[0][0] == "preview-texture"
    release()
    assert host.context.destroyed == ["preview-texture"]


def test_native_ui_host_can_upload_full_resolution_ui_artwork():
    import numpy as np

    from termin.editor_native.ui_host import NativeWidgetContent

    class Handle:
        valid = True

    class Image:
        handle = Handle()

        def set_texture(self, texture, size) -> None:
            self.texture = texture
            self.size = size

    class _ImagePreviewDocument:
        def is_alive(self, handle) -> bool:
            return handle.valid

    class Context:
        def __init__(self) -> None:
            self.created = []

        def create_texture_rgba8(self, width, height, pixels):
            self.created.append((width, height))
            return "artwork-texture"

    host = NativeWidgetContent.__new__(NativeWidgetContent)
    host.document = _ImagePreviewDocument()
    host.context = Context()
    host._image_previews = []
    host.adapter = SimpleNamespace(request_repaint=lambda: None)

    host.register_image_preview(
        Image(),
        np.zeros((800, 1200, 4), dtype=np.uint8),
        max_dimension=None,
    )
    host._sync_image_previews()

    assert host.context.created == [(1200, 800)]


def test_native_ui_host_applies_font_size_to_all_theme_roles():
    from termin.editor_native.ui_host import NativeWidgetContent

    host = NativeWidgetContent.__new__(NativeWidgetContent)
    host.document = tc_ui_document_create()
    gui_host = SimpleNamespace(repaint_requested=False)

    def request_repaint():
        gui_host.repaint_requested = True

    gui_host.request_repaint = request_repaint
    host.adapter = gui_host

    host.apply_font_size(18.0)

    for style_role in StyleRole:
        role = host.document.theme.role(style_role)
        assert role.base.font_size == 18.0
    assert host.render_requested
    tc_ui_document_destroy(host.document)
