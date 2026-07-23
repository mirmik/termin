"""Standalone SDL runtime shell for the procedural CSG CAD app."""

from __future__ import annotations

from tcbase import Key, MouseButton, log
from tcgui.widgets.ui import UI
from termin.display import WindowedGraphicsSession, quit_sdl, start_text_input, wait_sdl_events_timeout
from tgfx import Tgfx2Context

from termin.csg.cad_app import CadApp
from termin.csg.cad_viewer import CsgSceneRenderer


def _event_key(value: int) -> Key:
    try:
        return Key(int(value))
    except ValueError:
        log.debug(f"[termin-csg] unrecognized native key value={value}")
        return Key.UNKNOWN


def _event_button(value: int) -> MouseButton:
    try:
        return MouseButton(int(value))
    except ValueError:
        log.debug(f"[termin-csg] unrecognized native mouse button value={value}")
        return MouseButton.LEFT


def run_cad_app(title: str = "termin-csg CAD", size: tuple[int, int] = (1200, 760)) -> None:
    graphics_session = WindowedGraphicsSession.create_native()
    window = None
    try:
        window = graphics_session.create_window(title, int(size[0]), int(size[1]))
        window.maximize()
        graphics = Tgfx2Context.from_runtime(graphics_session.graphics)
        ui = UI(graphics=graphics)
        app = CadApp()
        ui.root = app.build_ui(ui)
        scene_renderer = CsgSceneRenderer(graphics)

        start_text_input()
        while not window.should_close():
            for event in wait_sdl_events_timeout(16):
                _dispatch_event(window, ui, event)

            width, height = window.framebuffer_size()
            if width <= 0 or height <= 0:
                continue
            if app.dirty:
                app.render_scene(scene_renderer)
            texture = ui.render_compose(width, height, background_color=(0.10, 0.10, 0.12, 1.0))
            if texture is not None:
                window.present(texture)
    finally:
        if "scene_renderer" in locals():
            scene_renderer.close()
        if window is not None:
            window.close()
        try:
            graphics_session.close()
        finally:
            quit_sdl()


def _dispatch_event(window, ui: UI, event: dict) -> None:
    event_type = event.get("type")
    if event_type == "quit":
        window.set_should_close(True)
    elif event_type == "key_down":
        key = _event_key(int(event.get("key", Key.UNKNOWN.value)))
        mods = int(event.get("mods", 0))
        if ui.key_down(key, mods):
            return
        if key == Key.ESCAPE:
            window.set_should_close(True)
    elif event_type == "text_input":
        ui.text_input(str(event.get("text", "")))
    elif event_type == "window_close":
        window.set_should_close(True)
    elif event_type == "mouse_move":
        ui.mouse_move(
            float(event.get("x", 0.0)),
            float(event.get("y", 0.0)),
            int(event.get("mods", 0)),
        )
    elif event_type == "mouse_down":
        ui.mouse_down(
            float(event.get("x", 0.0)),
            float(event.get("y", 0.0)),
            _event_button(int(event.get("button", MouseButton.LEFT.value))),
            int(event.get("mods", 0)),
        )
    elif event_type == "mouse_up":
        ui.mouse_up(
            float(event.get("x", 0.0)),
            float(event.get("y", 0.0)),
            _event_button(int(event.get("button", MouseButton.LEFT.value))),
            int(event.get("mods", 0)),
        )
    elif event_type == "mouse_wheel":
        ui.mouse_wheel(
            float(event.get("dx", 0.0)),
            float(event.get("dy", 0.0)),
            float(event.get("x", 0.0)),
            float(event.get("y", 0.0)),
            int(event.get("mods", 0)),
        )


__all__ = ["run_cad_app"]
