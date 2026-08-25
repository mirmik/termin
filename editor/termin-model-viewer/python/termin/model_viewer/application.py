"""Window host and command line for ``termin show``."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import partial
import logging
import math
import os
from pathlib import Path
import sys
import time

from termin.model_viewer.model import VisualModel, load_visual_model


_LOG = logging.getLogger("termin.model_viewer")


@dataclass(frozen=True)
class ViewerOptions:
    model: Path
    width: int = 1100
    height: int = 760
    title: str | None = None
    backend: str | None = None
    frame_limit: int = 0


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="termin show",
        description="Show a GLB model in a native window with an orbit camera.",
    )
    parser.add_argument("model", type=Path, help="Path to a .glb or .gltf model")
    parser.add_argument("--width", "-W", type=int, default=1100, help="Window width")
    parser.add_argument("--height", "-H", type=int, default=760, help="Window height")
    parser.add_argument("--title", "-t", help="Override the window title")
    parser.add_argument(
        "--backend",
        choices=("vulkan", "opengl", "d3d11"),
        help="Override the native graphics backend",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=0,
        help="Exit after this many rendered frames (0 keeps the window open)",
    )
    return parser


def parse_options(argv: list[str] | None = None) -> ViewerOptions:
    parser = _argument_parser()
    arguments = parser.parse_args(argv)
    model = arguments.model.expanduser()
    if not model.is_file():
        parser.error(f"model does not exist or is not a file: {model}")
    if model.suffix.lower() not in {".glb", ".gltf"}:
        parser.error(f"expected a .glb or .gltf model: {model}")
    if arguments.width < 320 or arguments.height < 240:
        parser.error("window size must be at least 320x240")
    if arguments.frames < 0:
        parser.error("--frames must be non-negative")
    return ViewerOptions(
        model=model.resolve(),
        width=arguments.width,
        height=arguments.height,
        title=arguments.title,
        backend=arguments.backend,
        frame_limit=arguments.frames,
    )


def _sdk_font_path() -> Path:
    configured = os.environ.get("TERMIN_UI_FONT")
    if configured:
        font = Path(configured)
        if not font.is_file():
            raise FileNotFoundError(f"TERMIN_UI_FONT points to a missing font: {font}")
        return font
    sdk_root = Path(sys.executable).resolve().parent.parent
    font = sdk_root / "share" / "termin" / "fonts" / "DroidSans.ttf"
    if not font.is_file():
        raise FileNotFoundError(f"Termin SDK UI font is missing: {font}")
    return font


class _OrbitInteraction:
    def __init__(self, camera, invalidate) -> None:
        self.camera = camera
        self.invalidate = invalidate
        self.drag_mode: str | None = None
        self.last_x = 0.0
        self.last_y = 0.0
        self.pan_gesture = None
        self.viewport_width = 1.0
        self.viewport_height = 1.0

    def set_viewport(self, width: float, height: float) -> None:
        if width > 0.0 and height > 0.0:
            self.viewport_width = width
            self.viewport_height = height

    def handle(self, event, _ray) -> bool:
        from tcbase import MouseButton
        from termin.geombase import Rect2, Vec2
        from termin.gui_native import PointerEventType

        if event.type == PointerEventType.Wheel:
            self.camera.zoom(math.exp(-float(event.wheel_y) * 0.12))
            self.invalidate()
            return True

        if event.type == PointerEventType.Down:
            self.last_x = float(event.x)
            self.last_y = float(event.y)
            if event.button == MouseButton.LEFT.value:
                self.drag_mode = "orbit"
                return True
            if event.button in (MouseButton.MIDDLE.value, MouseButton.RIGHT.value):
                viewport = Rect2(
                    0.0,
                    0.0,
                    self.viewport_width,
                    self.viewport_height,
                )
                self.pan_gesture = self.camera.begin_pan(
                    Vec2(self.last_x, self.last_y),
                    viewport,
                )
                if self.pan_gesture is not None:
                    self.drag_mode = "pan"
                    return True
                return False

        if event.type == PointerEventType.Move and self.drag_mode == "orbit":
            x = float(event.x)
            y = float(event.y)
            self.camera.orbit(-(x - self.last_x) * 0.008, (y - self.last_y) * 0.008)
            self.last_x = x
            self.last_y = y
            self.invalidate()
            return True

        if event.type == PointerEventType.Move and self.drag_mode == "pan":
            if self.pan_gesture is not None and self.camera.pan(
                self.pan_gesture,
                Vec2(float(event.x), float(event.y)),
            ):
                self.invalidate()
            return True

        if event.type in (PointerEventType.Up, PointerEventType.Cancel):
            if self.drag_mode is not None:
                self.drag_mode = None
                self.pan_gesture = None
                return True
        return False


def _create_view(document, model: VisualModel, request_repaint):
    from tcbase._geom_native import LinearColor
    from termin.geombase import OrbitCamera
    from termin.gui_native import SceneView3DCamera, Size

    view = document.create_scene_view3d(model.scene)
    view.widget.stable_id = "termin.model-viewer.scene"
    view.widget.preferred_size = Size(1100.0, 760.0)
    view.set_clear_color(LinearColor(0.018, 0.024, 0.038, 1.0))

    camera = OrbitCamera()
    camera.fit_bounds(model.bounds.as_aabb())

    def invalidate() -> None:
        view.invalidate_view()
        request_repaint()

    interaction = _OrbitInteraction(camera, invalidate)

    def camera_provider(size):
        if size.width <= 0 or size.height <= 0:
            return None
        interaction.set_viewport(float(size.width), float(size.height))
        aspect = float(size.width) / float(size.height)
        return SceneView3DCamera(
            camera.view_matrix(),
            camera.projection_matrix(aspect),
            camera.eye,
        )

    view.set_camera_provider(camera_provider)
    view.set_fallback_pointer_handler(interaction.handle)
    if not document.add_root(view.widget.handle):
        view.set_fallback_pointer_handler(None)
        view.set_camera_provider(None)
        view.detach_scene()
        raise RuntimeError("failed to add the model view to the UI document")
    return view, camera, interaction


def run_viewer(options: ViewerOptions) -> int:
    """Open and run the native model-viewer window."""

    import tgfx
    from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
    from termin.gui_native.window import GuiWindowAdapter
    from termin.window import WindowManager, WindowedGraphicsSession, quit_sdl

    if options.backend is not None:
        os.environ["TERMIN_BACKEND"] = options.backend
    if not tgfx.configure_default_shader_runtime("termin-model-viewer"):
        raise RuntimeError("failed to configure the Termin graphics shader runtime")

    model = None
    graphics_session = None
    window_manager = None
    window_handle = None
    document = None
    adapter = None
    view = None
    try:
        model = load_visual_model(options.model)
        graphics_session = WindowedGraphicsSession.create_native()
        window_manager = WindowManager(graphics_session)
        window_handle = window_manager.create_window(
            options.title or f"Termin — {options.model.name}",
            options.width,
            options.height,
        )
        document = tc_ui_document_create()
        adapter = GuiWindowAdapter(
            window_manager,
            window_handle,
            document,
            font_path=str(_sdk_font_path()),
            font_size=15,
            enable_text_input=False,
        )
        view, _camera, _interaction = _create_view(
            document,
            model,
            adapter.request_repaint,
        )

        adapter.request_repaint()
        rendered_frames = 0
        while not adapter.should_close:
            window_manager.pump_events()
            adapter.consume_pending_events(window_manager, window_handle, None)
            if adapter.should_close:
                break
            if adapter.repaint_requested:
                if not adapter.render_frame():
                    raise RuntimeError("model viewer failed to render a frame")
                rendered_frames += 1
                if rendered_frames < 2:
                    adapter.request_repaint()
            else:
                time.sleep(0.01)
            if options.frame_limit and rendered_frames >= options.frame_limit:
                break
        _LOG.info("Model viewer rendered %d frame(s)", rendered_frames)
        return 0
    except Exception:
        _LOG.exception("Model viewer failed for '%s'", options.model)
        raise
    finally:
        cleanup_actions = []
        if view is not None:
            cleanup_actions.extend(
                [
                    ("clear model-view pointer handler", partial(view.set_fallback_pointer_handler, None)),
                    ("clear model-view camera provider", partial(view.set_camera_provider, None)),
                    ("detach model-view scene", view.detach_scene),
                ]
            )
        if model is not None:
            cleanup_actions.append(("destroy model visual scene", model.close))
        if adapter is not None:
            cleanup_actions.append(("close GUI window adapter", adapter.close))
        if document is not None:
            cleanup_actions.append(("destroy GUI document", partial(tc_ui_document_destroy, document)))
        if window_manager is not None:
            cleanup_actions.append(("close window manager", window_manager.close))
        if graphics_session is not None:
            cleanup_actions.append(("close windowed graphics session", graphics_session.close))
        cleanup_actions.append(("shut down SDL", quit_sdl))

        first_cleanup_error = None
        for label, cleanup in cleanup_actions:
            try:
                cleanup()
            except Exception as exc:
                _LOG.exception("Failed to %s", label)
                if first_cleanup_error is None:
                    first_cleanup_error = exc
        if first_cleanup_error is not None and sys.exception() is None:
            raise RuntimeError("model viewer cleanup failed") from first_cleanup_error


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        return run_viewer(parse_options(argv))
    except Exception as exc:
        _LOG.error("termin show: %s", exc)
        return 2
