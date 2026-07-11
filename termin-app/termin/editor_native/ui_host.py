"""SDL/tgfx2 host boundary for one native ``tc_ui_document``."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import sys
import tempfile
from typing import Callable

from termin.display import (
    SDLBackendWindow,
    get_clipboard_text,
    poll_sdl_events,
    set_clipboard_text,
    start_text_input,
    stop_text_input,
)
from termin.gui_native import (
    Document,
    DrawList,
    DrawListRenderer,
    KeyCode,
    KeyEvent,
    KeyEventType,
    PaintContext,
    PointerEvent,
    PointerEventType,
    Rect,
    StyleRole,
)


_logger = logging.getLogger(__name__)

FileDropHandler = Callable[[str, float, float, int], bool]
PreRenderCallback = Callable[[object], None]


@dataclass(frozen=True)
class RouteResult:
    keep_running: bool = True
    routed: bool = False


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

    sdk_root = Path(sys.executable).resolve().parent.parent
    candidates = (
        sdk_root / "share" / "termin" / "fonts" / "DroidSans.ttf",
        Path.cwd() / "termin-thirdparty" / "recastnavigation" / "RecastDemo" / "Bin" / "DroidSans.ttf",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("native UI font is absent from the SDK and source checkout")


class NativeUiEventRouter:
    """Translate neutral SDL event dictionaries into native document events."""

    def __init__(
        self,
        document: Document,
        window_id: int,
        file_drop_handler: FileDropHandler | None = None,
    ) -> None:
        self.document = document
        self.window_id = int(window_id)
        self.file_drop_handler = file_drop_handler

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

        if event_type in ("mouse_move", "mouse_down", "mouse_up", "mouse_wheel"):
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
            }[event_type]
            self.document.dispatch_pointer_event(pointer)
            return RouteResult(routed=True)

        if event_type in ("key_down", "key_up"):
            key = KeyEvent()
            key.type = KeyEventType.Down if event_type == "key_down" else KeyEventType.Up
            key.key = self._key_code(int(event.get("key", -1)))
            key.modifiers = int(event.get("mods", 0))
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
        document: Document | None = None,
        *,
        font_path: str | Path | None = None,
        file_drop_handler: FileDropHandler | None = None,
    ) -> None:
        if poll_sdl_events is None or get_clipboard_text is None or set_clipboard_text is None:
            raise RuntimeError("termin-display SDL platform bindings are unavailable")
        self.window = window
        self.device = window.device()
        self.document = document if document is not None else Document()
        self.context = window.context()
        self.draw_list = DrawList()
        self.paint_context = PaintContext(self.draw_list)
        self.renderer = DrawListRenderer()
        resolved_font = resolve_native_ui_font(font_path)
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
        start_text_input()

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
        self._pre_render_callbacks.clear()
        self._color_pickers.clear()
        stop_text_input()
        self.renderer.release_gpu()
        if self._color_target is not None:
            self.context.destroy_texture(self._color_target)
            self._color_target = None
        self.window.close()

    def __enter__(self) -> NativeUiHost:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
