"""Standalone native-window runtime for the procedural CSG CAD app."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import time
from typing import Callable

from termin.base import log
from termin.display.window import WindowManager, WindowedGraphicsSession, quit_sdl
from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
from termin.gui_native.window import GuiWindowAdapter
from termin.graphics import Tgfx2Context

from termin.csg.cad_app import CadApp
from termin.csg.cad_viewer import CsgSceneRenderer


def _sdk_root() -> Path:
    """Return the explicitly selected SDK, or the SDK owning this Python."""

    configured = os.environ.get("TERMIN_SDK")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(sys.executable).resolve().parent.parent


def _resolve_native_ui_font(configured: str | Path | None = None) -> Path:
    """Resolve a font without consulting host-system font installations.

    Standalone SDK tools must remain reproducible on machines whose system font
    selection differs.  An explicit override is accepted for development, but a
    broken override is an error rather than an invitation to silently substitute
    another font.
    """

    explicit = Path(configured).expanduser() if configured is not None else None
    if explicit is None:
        environment = os.environ.get("TERMIN_UI_FONT")
        explicit = Path(environment).expanduser() if environment else None
    if explicit is not None:
        if explicit.is_file():
            return explicit.resolve()
        raise FileNotFoundError(f"TERMIN_UI_FONT points to missing file: {explicit}")

    font = _sdk_root() / "share" / "termin" / "fonts" / "DroidSans.ttf"
    if font.is_file():
        return font
    raise FileNotFoundError(f"native CSG CAD SDK font is missing: {font}")


def _shader_cache_root() -> Path:
    configured = os.environ.get("TERMIN_SDK_SHADER_CACHE_ROOT")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "Termin" / "Cache" / "sdk-shaders"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache) if xdg_cache else Path.home() / ".cache"
    return base / "termin" / "sdk-shaders"


def _configure_shader_runtime() -> bool:
    """Configure the standalone termin.graphics shader resolver from SDK-owned tools."""

    from termin.shader_runtime import (
        resolve_slangc,
        resolve_termin_shaderc,
        slangc_unavailable_message,
    )
    import termin.graphics

    compiler = resolve_termin_shaderc(Path(__file__))
    if compiler is None:
        log.error("[CsgCad] termin_shaderc not found; standalone CAD Slang shaders cannot compile")
        return False
    slangc = resolve_slangc(Path(__file__))
    if slangc is None:
        log.warning(f"[CsgCad] {slangc_unavailable_message('standalone CSG CAD')}")
        return False

    root = _shader_cache_root()
    artifact_root = root / "artifacts"
    cache_root = root / "cache"
    try:
        artifact_root.mkdir(parents=True, exist_ok=True)
        cache_root.mkdir(parents=True, exist_ok=True)
        os.environ["TERMIN_SLANGC"] = str(slangc)
        termin.graphics.configure_shader_runtime(
            artifact_root=str(artifact_root),
            cache_root=str(cache_root),
            shader_compiler=str(compiler),
            dev_compile=True,
        )
    except Exception as exc:
        log.error(f"[CsgCad] failed to configure shader runtime: {exc}")
        return False

    log.info(f"[CsgCad] shader runtime configured: artifact_root='{artifact_root}' cache_root='{cache_root}'")
    return True


def _cleanup(label: str, callback: Callable[[], None]) -> Exception | None:
    try:
        callback()
    except Exception as exc:
        log.error(f"[CsgCad] failed to close {label}: {exc}")
        return exc
    return None


def run_cad_app(title: str = "termin-csg CAD", size: tuple[int, int] = (1200, 760)) -> None:
    """Run the native CSG CAD window until the user closes it."""

    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        raise ValueError("CSG CAD window dimensions must be positive")

    font_path = _resolve_native_ui_font()
    if not _configure_shader_runtime():
        raise RuntimeError("failed to configure the CSG CAD shader runtime")

    graphics_session = None
    window_manager = None
    window_handle = None
    document = None
    adapter = None
    app = None
    scene_renderer = None
    try:
        graphics_session = WindowedGraphicsSession.create_native()
        graphics = Tgfx2Context.from_runtime(graphics_session.graphics)
        window_manager = WindowManager(graphics_session)
        window_handle = window_manager.create_window(title, width, height)
        document = tc_ui_document_create()
        adapter = GuiWindowAdapter(
            window_manager,
            window_handle,
            document,
            font_path=str(font_path),
            font_size=15,
            enable_text_input=True,
        )
        adapter.window.maximize()

        scene_renderer = CsgSceneRenderer(graphics)
        app = CadApp(document, request_render=adapter.request_repaint)
        app.build_ui()
        adapter.set_unhandled_key_handler(app.dispatch_shortcut)

        def render_scene_before_frame() -> None:
            if not app.dirty:
                return
            try:
                app.render_scene(scene_renderer)
            except Exception as exc:
                log.error(f"[CsgCad] scene rendering failed: {exc}")
                raise

        adapter.set_before_frame_callback(render_scene_before_frame)
        adapter.request_repaint()

        while not adapter.should_close:
            window_manager.pump_events()
            adapter.consume_pending_events(window_manager, window_handle, None)
            if adapter.should_close:
                break
            if adapter.repaint_requested:
                adapter.render_frame()
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        log.info("[CsgCad] interrupted; closing standalone CAD")
    finally:
        active_error = sys.exc_info()[1]
        cleanup_error: Exception | None = None

        def close(label: str, callback: Callable[[], None]) -> None:
            nonlocal cleanup_error
            error = _cleanup(label, callback)
            if cleanup_error is None and error is not None:
                cleanup_error = error

        if adapter is not None:
            close(
                "native before-frame callback",
                lambda: adapter.set_before_frame_callback(None),
            )
            close(
                "native shortcut handler",
                lambda: adapter.set_unhandled_key_handler(None),
            )
        if app is not None:
            close("CAD application", app.close)
        if scene_renderer is not None:
            close("CSG scene renderer", scene_renderer.close)
        if adapter is not None:
            close("native GUI adapter", adapter.close)
        if document is not None:
            close("native GUI document", lambda: tc_ui_document_destroy(document))
        if window_manager is not None and window_handle is not None:
            if window_manager.contains(window_handle):
                close("CAD window", lambda: window_manager.destroy_window(window_handle))
        if window_manager is not None:
            close("window manager", window_manager.close)
        if graphics_session is not None:
            close("graphics session", graphics_session.close)
        close("SDL runtime", quit_sdl)

        if active_error is None and cleanup_error is not None:
            raise RuntimeError("CSG CAD runtime teardown failed") from cleanup_error


__all__ = ["run_cad_app"]
