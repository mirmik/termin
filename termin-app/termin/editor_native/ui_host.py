"""SDL/tgfx2 host boundary for one native ``tc_ui_document``."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import os
from pathlib import Path
import sys
import tempfile
from queue import Empty, SimpleQueue
from typing import Callable

from termin.display import (
    BackendWindowManager,
    SDLBackendWindow,
    SystemCursorShape,
    get_clipboard_text,
    poll_sdl_events,
    set_clipboard_text,
    set_system_cursor,
    start_text_input,
    stop_text_input,
)
from tgfx import Tgfx2Context
from termin.gui_native import (
    Document,
    CursorIntent,
    DrawList,
    DrawListRenderer,
    KeyCode,
    KeyEvent,
    KeyEventType,
    PaintContext,
    PointerEvent,
    PointerEventType,
    Rect,
    Size,
    StyleRole,
)


_logger = logging.getLogger(__name__)

FileDropHandler = Callable[[str, float, float, int], bool]
PreRenderCallback = Callable[[object], None]
ShortcutDispatcher = Callable[[int, int], bool]


@dataclass(frozen=True)
class RouteResult:
    keep_running: bool = True
    routed: bool = False


@dataclass
class _ImagePreview:
    image: object
    pixels: object
    texture: object | None = None


def resolve_native_ui_font(configured: str | Path | None = None) -> Path:
    """Resolve the SDK-owned UI font and reject broken explicit overrides."""

    explicit = Path(configured) if configured is not None else None
    if explicit is None:
        environment = os.environ.get("TERMIN_UI_FONT")
        explicit = Path(environment) if environment else None
    if explicit is not None:
        if explicit.is_file():
            return explicit
        raise FileNotFoundError(f"TERMIN_UI_FONT points to missing file: {explicit}")

    configured_sdk = os.environ.get("TERMIN_SDK")
    sdk_root = (
        Path(configured_sdk).resolve()
        if configured_sdk
        else Path(sys.executable).resolve().parent.parent
    )
    candidates = (
        sdk_root / "share" / "termin" / "fonts" / "DroidSans.ttf",
        Path.cwd() / "termin-thirdparty" / "recastnavigation" / "RecastDemo" / "Bin" / "DroidSans.ttf",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        f"native UI font is absent from the SDK and source checkout; searched: {searched}"
    )


class NativeUiEventRouter:
    """Translate neutral SDL event dictionaries into native document events."""

    def __init__(
        self,
        document: Document,
        window_id: int,
        file_drop_handler: FileDropHandler | None = None,
        shortcut_dispatcher: ShortcutDispatcher | None = None,
    ) -> None:
        self.document = document
        self.window_id = int(window_id)
        self.file_drop_handler = file_drop_handler
        self.shortcut_dispatcher = shortcut_dispatcher

    @staticmethod
    def _key_code(value: int) -> KeyCode:
        try:
            return KeyCode(value)
        except ValueError:
            _logger.debug("native UI ignored unsupported key code %d", value)
            return KeyCode.Unknown

    def route(self, event: dict[str, object]) -> RouteResult:
        event_type = event.get("type")
        if event_type == "quit":
            return RouteResult(keep_running=False)

        event_window_id = int(event.get("window_id", 0))
        if event_type == "window_close":
            return RouteResult(keep_running=event_window_id != self.window_id)
        if event_window_id not in (0, self.window_id):
            return RouteResult()
        if event_type == "window_refresh":
            return RouteResult(routed=True)

        if event_type in ("mouse_move", "mouse_down", "mouse_up", "mouse_wheel", "mouse_leave"):
            pointer = PointerEvent()
            pointer.x = float(event.get("x", 0.0))
            pointer.y = float(event.get("y", 0.0))
            pointer.modifiers = int(event.get("mods", 0))
            pointer.button = int(event.get("button", 0))
            pointer.click_count = max(1, int(event.get("click_count", 1)))
            pointer.wheel_x = float(event.get("dx", 0.0))
            pointer.wheel_y = float(event.get("dy", 0.0))
            pointer.type = {
                "mouse_move": PointerEventType.Move,
                "mouse_down": PointerEventType.Down,
                "mouse_up": PointerEventType.Up,
                "mouse_wheel": PointerEventType.Wheel,
                "mouse_leave": PointerEventType.Leave,
            }[event_type]
            self.document.dispatch_pointer_event(pointer)
            return RouteResult(routed=True)

        if event_type in ("key_down", "key_up"):
            key_value = int(event.get("key", -1))
            modifiers = int(event.get("mods", 0))
            if (
                event_type == "key_down"
                and not bool(event.get("repeat", False))
                and self.shortcut_dispatcher is not None
                and self.shortcut_dispatcher(key_value, modifiers)
            ):
                return RouteResult(routed=True)
            key = KeyEvent()
            key.type = KeyEventType.Down if event_type == "key_down" else KeyEventType.Up
            key.key = self._key_code(key_value)
            key.modifiers = modifiers
            key.repeat = bool(event.get("repeat", False))
            self.document.dispatch_key_event(key)
            return RouteResult(routed=True)

        if event_type == "text_input":
            text = event.get("text", "")
            if not isinstance(text, str):
                _logger.error("native UI text_input event contains non-string text")
                return RouteResult()
            self.document.dispatch_text_event(text)
            return RouteResult(routed=True)

        if event_type == "file_drop":
            path = event.get("path")
            if not isinstance(path, str) or not path:
                _logger.error("native UI file_drop event has an empty path")
                return RouteResult()
            if self.file_drop_handler is None:
                return RouteResult()
            routed = self.file_drop_handler(
                path,
                float(event.get("x", 0.0)),
                float(event.get("y", 0.0)),
                int(event.get("mods", 0)),
            )
            return RouteResult(routed=bool(routed))

        return RouteResult()


class NativeUiHost:
    """Own render/input services for a native document attached to one window."""

    def __init__(
        self,
        window: SDLBackendWindow,
        graphics: Tgfx2Context,
        document: Document | None = None,
        *,
        font_path: str | Path | None = None,
        file_drop_handler: FileDropHandler | None = None,
        manage_text_input: bool = True,
    ) -> None:
        if (
            poll_sdl_events is None
            or get_clipboard_text is None
            or set_clipboard_text is None
            or set_system_cursor is None
            or SystemCursorShape is None
        ):
            raise RuntimeError("termin-display SDL platform bindings are unavailable")
        self.window = window
        self.graphics = graphics
        self.device = graphics.device
        self._owns_document = document is None
        self.document = document if document is not None else Document()
        self.context = graphics.context
        self.draw_list = DrawList()
        self.paint_context = PaintContext(self.draw_list)
        self.renderer = DrawListRenderer()
        resolved_font = resolve_native_ui_font(font_path)
        self.font_path = resolved_font
        if not self.renderer.set_default_font_path(str(resolved_font), 15):
            raise RuntimeError(f"failed to configure native UI font: {resolved_font}")
        self.renderer.bind_text_measurer(self.document)
        self.document.set_clipboard_handlers(get_clipboard_text, set_clipboard_text)
        self.router = NativeUiEventRouter(
            self.document,
            window.window_id(),
            file_drop_handler=file_drop_handler,
        )
        self._color_target = None
        self._target_size = (0, 0)
        self._closed = False
        self._render_requested = True
        self._pre_render_callbacks: list[PreRenderCallback] = []
        self._color_pickers: list[object] = []
        self._image_previews: list[_ImagePreview] = []
        self._deferred: SimpleQueue[Callable[[], None]] = SimpleQueue()
        self._manage_text_input = bool(manage_text_input)
        self.document.set_cursor_changed_handler(self._apply_cursor_intent)
        self._apply_cursor_intent(self.document.cursor_intent)
        if self._manage_text_input:
            start_text_input()

    @staticmethod
    def _apply_cursor_intent(cursor: CursorIntent) -> None:
        shapes = {
            CursorIntent.Default: SystemCursorShape.Default,
            CursorIntent.Text: SystemCursorShape.Text,
            CursorIntent.Hand: SystemCursorShape.Hand,
            CursorIntent.Crosshair: SystemCursorShape.Crosshair,
            CursorIntent.Move: SystemCursorShape.Move,
            CursorIntent.ResizeHorizontal: SystemCursorShape.ResizeHorizontal,
            CursorIntent.ResizeVertical: SystemCursorShape.ResizeVertical,
            CursorIntent.ResizeNwse: SystemCursorShape.ResizeNwse,
            CursorIntent.ResizeNesw: SystemCursorShape.ResizeNesw,
        }
        shape = shapes.get(cursor)
        if shape is None:
            _logger.error("native UI host received unresolved cursor intent %s", cursor)
            shape = SystemCursorShape.Default
        set_system_cursor(shape)

    @property
    def color_target(self):
        """Current host-owned render target for screenshot/MCP readback."""

        return self._color_target

    def poll_events(self) -> tuple[bool, int]:
        routed = 0
        for event in poll_sdl_events():
            result = self.router.route(event)
            routed += int(result.routed)
            if not result.keep_running:
                self.window.set_should_close(True)
                return False, routed
        return not self.window.should_close(), routed

    def defer(self, callback: Callable[[], None]) -> None:
        """Schedule a callback for the UI owner thread from any thread."""
        self._deferred.put(callback)

    def process_deferred(self) -> int:
        processed = 0
        while True:
            try:
                callback = self._deferred.get_nowait()
            except Empty:
                break
            try:
                callback()
            except Exception:
                _logger.exception("Native UI deferred callback failed")
            processed += 1
        if processed:
            self.request_render_update()
        return processed

    def render(self) -> bool:
        width, height = self.window.framebuffer_size()
        if width <= 0 or height <= 0:
            return False
        # Consume the request that led to this frame before composition. Any
        # layout/pre-render callback may request a follow-up frame; do not erase
        # that new request after present.
        self._render_requested = False
        if self._color_target is None or self._target_size != (width, height):
            if self._color_target is not None:
                self.context.destroy_texture(self._color_target)
            self._color_target = self.context.create_color_attachment(width, height)
            self._target_size = (width, height)

        self.document.layout_roots(Rect(0.0, 0.0, float(width), float(height)))
        self.context.begin_frame()
        self._sync_color_picker_surfaces()
        self._sync_image_previews()
        for callback in tuple(self._pre_render_callbacks):
            try:
                callback(self.context)
            except Exception:
                _logger.exception("Native UI pre-render callback failed")
                raise
        self.draw_list.clear()
        self.document.paint(self.paint_context)
        self.context.begin_pass(
            self._color_target,
            clear_color_enabled=True,
            r=0.03,
            g=0.035,
            b=0.045,
            a=1.0,
        )
        self.renderer.render(self.context, self.draw_list, width, height)
        self.context.end_pass()
        self.context.end_frame()
        self.window.present(self._color_target)
        return True

    def add_pre_render_callback(self, callback: PreRenderCallback) -> None:
        if callback not in self._pre_render_callbacks:
            self._pre_render_callbacks.append(callback)

    def remove_pre_render_callback(self, callback: PreRenderCallback) -> None:
        if callback in self._pre_render_callbacks:
            self._pre_render_callbacks.remove(callback)

    def register_color_picker(self, picker: object) -> None:
        """Arrange for a native ColorPicker's generated surfaces to use GPU textures."""

        handle = picker.handle
        if not self.document.is_alive(handle):
            raise RuntimeError("cannot register a stale native ColorPicker")
        if not any(existing.handle == handle for existing in self._color_pickers):
            self._color_pickers.append(picker)

    def unregister_color_picker(self, picker: object) -> None:
        handle = picker.handle
        for index, existing in enumerate(self._color_pickers):
            if existing.handle == handle:
                self.renderer.release_color_picker_surfaces(existing)
                del self._color_pickers[index]
                return

    def _sync_color_picker_surfaces(self) -> None:
        for picker in tuple(self._color_pickers):
            if not self.document.is_alive(picker.handle):
                _logger.error("native ColorPicker was destroyed without host unregistration")
                self._color_pickers.remove(picker)
                continue
            self.renderer.sync_color_picker_surfaces(self.context, picker)

    def register_image_preview(
        self,
        image: object,
        pixels: object,
        *,
        max_dimension: int | None = 128,
    ) -> Callable[[], None]:
        """Upload CPU pixels once and keep the resulting texture owned by this host.

        Preview surfaces are bounded by default because most callers display small
        inspector thumbnails. Full-resolution UI artwork can opt out explicitly.
        """

        import numpy as np

        array = np.asarray(pixels)
        if array.ndim != 3 or array.shape[2] not in (3, 4):
            raise ValueError("native image preview requires an H×W RGB or RGBA array")
        if array.shape[0] <= 0 or array.shape[1] <= 0:
            raise ValueError("native image preview requires non-empty pixels")
        if array.dtype.kind == "f":
            array = np.clip(array * 255.0, 0.0, 255.0)
        array = np.ascontiguousarray(array.astype(np.uint8, copy=False))
        if array.shape[2] == 3:
            alpha = np.full((*array.shape[:2], 1), 255, dtype=np.uint8)
            array = np.concatenate((array, alpha), axis=2)
        if max_dimension is not None and max_dimension <= 0:
            raise ValueError("native image preview max_dimension must be positive or None")
        step = (
            1
            if max_dimension is None
            else max(1, math.ceil(max(array.shape[0], array.shape[1]) / max_dimension))
        )
        if step > 1:
            array = np.ascontiguousarray(array[::step, ::step])
        preview = _ImagePreview(image=image, pixels=array)
        self._image_previews.append(preview)
        self.request_render_update()

        def release() -> None:
            self._release_image_preview(preview)

        return release

    def _sync_image_previews(self) -> None:
        for preview in tuple(self._image_previews):
            if not self.document.is_alive(preview.image.handle):
                _logger.error("native image preview was destroyed without host unregistration")
                self._release_image_preview(preview)
                continue
            if preview.texture is None:
                height, width, _channels = preview.pixels.shape
                preview.texture = self.context.create_texture_rgba8(width, height, preview.pixels)
                preview.image.set_texture(preview.texture, Size(float(width), float(height)))

    def _release_image_preview(self, preview: _ImagePreview) -> None:
        if preview not in self._image_previews:
            return
        self._image_previews.remove(preview)
        if preview.texture is not None:
            self.context.destroy_texture(preview.texture)
            preview.texture = None

    def apply_font_size(self, font_size: float) -> None:
        size = float(font_size)
        if not 8.0 <= size <= 32.0:
            raise ValueError("native UI font size must be in range 8..32")
        theme = self.document.theme
        for role in (
            StyleRole.Generic,
            StyleRole.Panel,
            StyleRole.Label,
            StyleRole.Button,
            StyleRole.TextInput,
            StyleRole.GroupBox,
            StyleRole.Tab,
            StyleRole.Checkbox,
            StyleRole.Progress,
            StyleRole.Slider,
            StyleRole.Separator,
        ):
            role_style = theme.role(role)
            role_style.base.font_size = size
        self.document.theme = theme
        self.request_render_update()

    def request_render_update(self) -> None:
        self._render_requested = True

    @property
    def render_requested(self) -> bool:
        return self._render_requested

    def capture_screenshot(
        self,
        *,
        output_path: str | None = None,
        include_image: bool = False,
    ) -> dict[str, object]:
        """Capture the composed native editor UI from the owner thread."""

        # MCP execution may drain a newly queued screenshot request in the same
        # owner-thread batch as a preceding UI mutation. Compose synchronously
        # here so readback can never observe the previous target contents.
        if not self.render():
            raise RuntimeError("native UI cannot compose a frame for screenshot capture")
        self.device.wait_idle()
        if self._color_target is None:
            raise RuntimeError("native UI has not rendered a frame for screenshot capture")
        from termin.mcp.screenshot import capture_texture_screenshot

        width, height = self._target_size
        return capture_texture_screenshot(
            self._color_target,
            self.device,
            width=width,
            height=height,
            output_path=output_path,
            include_image=include_image,
            default_dir=Path(tempfile.gettempdir()) / "termin-editor-screenshots",
            default_prefix="termin-editor-native",
            log_prefix="NativeEditorScreenshot",
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.document.set_cursor_changed_handler(None)
        self._pre_render_callbacks.clear()
        self._color_pickers.clear()
        for preview in tuple(self._image_previews):
            self._release_image_preview(preview)
        if self._manage_text_input:
            stop_text_input()
        self.renderer.release_gpu()
        if self._color_target is not None:
            self.context.destroy_texture(self._color_target)
            self._color_target = None
        if self._owns_document:
            self.document.close()
        self.window.close()

    def __enter__(self) -> NativeUiHost:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


@dataclass
class NativeUiWindow:
    """A secondary OS window and the native UI host attached to it."""

    manager: "NativeUiWindowManager"
    entry: object
    host: NativeUiHost
    _closed: bool = False

    @property
    def closed(self) -> bool:
        return self._closed

    def request_render_update(self) -> None:
        if not self._closed:
            self.host.request_render_update()

    def close(self) -> None:
        if not self._closed:
            self.manager.destroy_window(self)


class NativeUiWindowManager:
    """Own and drive all native UI windows in one editor process.

    SDL has one process-global event queue, so individual hosts cannot poll it
    independently.  This manager drains the queue once, routes each event by
    window id, and composes every host that requested an update.  Secondary
    windows use the same explicit host graphics runtime through
    :class:`BackendWindowManager`.
    """

    def __init__(
        self,
        main_host: NativeUiHost,
        *,
        graphics_session: object | None = None,
        backend_manager: object | None = None,
        event_source: Callable[[], list[dict[str, object]]] | None = None,
        host_factory: Callable[..., NativeUiHost] | None = None,
    ) -> None:
        if BackendWindowManager is None and backend_manager is None:
            raise RuntimeError("termin-display BackendWindowManager is unavailable")
        self.main_host = main_host
        if backend_manager is None and graphics_session is None:
            raise ValueError("NativeUiWindowManager requires a graphics runtime")
        self._backend = (
            backend_manager
            if backend_manager is not None
            else BackendWindowManager(graphics_session)
        )
        self._event_source = event_source if event_source is not None else poll_sdl_events
        self._host_factory = host_factory if host_factory is not None else NativeUiHost
        self._windows: list[NativeUiWindow] = []
        self._closed = False
        self._main_entry = self._backend.register_main(
            main_host.window,
            host_data=main_host,
            on_destroy=lambda _entry: main_host.close(),
        )

    @property
    def windows(self) -> tuple[NativeUiWindow, ...]:
        return tuple(self._windows)

    def create_window(
        self,
        title: str,
        width: int,
        height: int,
        *,
        document: Document | None = None,
        always_on_top: bool = False,
        on_close: Callable[[], None] | None = None,
    ) -> NativeUiWindow:
        if self._closed:
            raise RuntimeError("native UI window manager is closed")
        entry = self._backend.create_window(
            title,
            width,
            height,
            always_on_top=always_on_top,
        )
        try:
            host = self._host_factory(
                entry.window,
                document=document,
                font_path=self.main_host.font_path,
                manage_text_input=False,
            )
            # Secondary tools must inherit the complete editor theme, not just
            # the default font size used when their renderer was constructed.
            host.document.theme = self.main_host.document.theme
        except Exception:
            self._backend.destroy_window(entry)
            raise

        window = NativeUiWindow(self, entry, host)

        def destroy_secondary(_entry) -> None:
            if window._closed:
                return
            window._closed = True
            if window in self._windows:
                self._windows.remove(window)
            try:
                if on_close is not None:
                    on_close()
            except Exception:
                _logger.exception("native secondary-window close callback failed")
            finally:
                host.close()

        entry.host_data = host
        entry.on_destroy = destroy_secondary
        self._windows.append(window)
        return window

    def destroy_window(self, window: NativeUiWindow) -> None:
        if window.manager is not self:
            raise ValueError("secondary native UI window belongs to another manager")
        if window._closed:
            return
        self._backend.destroy_window(window.entry)

    def poll_events(self) -> tuple[bool, int]:
        if self._closed:
            return False, 0
        routed = 0
        for event in self._event_source():
            event_type = event.get("type")
            if event_type == "quit":
                self.main_host.window.set_should_close(True)
                return False, routed

            window_id = int(event.get("window_id", 0))
            if event_type == "window_close":
                entry = self._backend.get_entry_for_window_id(window_id)
                if entry is None:
                    continue
                if entry.is_main:
                    self.main_host.window.set_should_close(True)
                    return False, routed
                self._backend.destroy_window(entry)
                continue

            entry = (
                self._backend.get_entry_for_window_id(window_id)
                if window_id
                else self._main_entry
            )
            if entry is None:
                continue
            host = entry.host_data
            result = host.router.route(event)
            if not result.keep_running:
                if entry.is_main:
                    self.main_host.window.set_should_close(True)
                    return False, routed
                self._backend.destroy_window(entry)
                continue
            if result.routed:
                routed += 1
                host.request_render_update()
        return not self.main_host.window.should_close(), routed

    def process_deferred(self) -> int:
        processed = self.main_host.process_deferred()
        for window in tuple(self._windows):
            if not window.closed:
                processed += window.host.process_deferred()
        return processed

    def render_requested(self) -> int:
        rendered = 0
        entries = tuple(self._backend.entries)
        for entry in entries:
            host = entry.host_data
            if host.render_requested and host.render():
                rendered += 1
        return rendered

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._backend.destroy_all()
