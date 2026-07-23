"""SDL/tgfx2 host boundary for one native ``tc_ui_document``."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Callable

from termin.display import PresentationMode
from tgfx import Tgfx2Context
from termin.gui_native import (
    Document,
    GuiWindowHost,
    Size,
    StyleRole,
)


_logger = logging.getLogger(__name__)

FileDropHandler = Callable[[str, float, float, int], bool]
PreRenderCallback = Callable[[object], None]
ShortcutDispatcher = Callable[[int, int], bool]


@dataclass
class NativeUiEventPolicy:
    file_drop_handler: FileDropHandler | None = None
    shortcut_dispatcher: ShortcutDispatcher | None = None


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


class NativeUiHost:
    """Editor policy adapter around the native application/window host.

    ``GuiWindowHost`` owns the event, frame, render-target and presentation
    lifecycle.  This wrapper keeps only editor-specific callbacks, generated
    preview textures and screenshot routing.
    """

    def __init__(
        self,
        graphics_session: object,
        document: Document | None = None,
        *,
        graphics: Tgfx2Context | None = None,
        title: str = "Termin",
        width: int = 1280,
        height: int = 720,
        presentation_mode: PresentationMode = PresentationMode.VSYNC,
        font_path: str | Path | None = None,
        file_drop_handler: FileDropHandler | None = None,
        enable_text_input: bool = True,
        always_on_top: bool = False,
    ) -> None:
        self._owns_document = document is None
        self.document = document if document is not None else Document()
        resolved_font = resolve_native_ui_font(font_path)
        self.font_path = resolved_font
        self._gui_host = GuiWindowHost(
            graphics_session,
            self.document,
            title=title,
            width=width,
            height=height,
            presentation_mode=presentation_mode,
            font_path=str(resolved_font),
            font_size=15,
            enable_text_input=enable_text_input,
            continuous_rendering=False,
        )
        self.window = self._gui_host.window
        if always_on_top:
            self.window.set_always_on_top(True)
        self.graphics = (
            graphics
            if graphics is not None
            else Tgfx2Context.from_runtime(graphics_session.graphics)
        )
        self.device = self.graphics.device
        self.context = self.graphics.context
        self.event_policy = NativeUiEventPolicy(
            file_drop_handler=file_drop_handler,
        )
        self._closed = False
        self._pre_render_callbacks: list[PreRenderCallback] = []
        self._image_previews: list[_ImagePreview] = []
        self._gui_host.set_event_interceptor(self._intercept_event)
        self._gui_host.set_frame_callbacks(self._before_ui_frame)

    @property
    def color_target(self):
        """Current host-owned render target for screenshot/MCP readback."""

        return self._gui_host.color_target

    def poll_events(self) -> tuple[bool, int]:
        count = self._gui_host.pump_events()
        return not self._gui_host.should_close, count

    def _intercept_event(self, event: dict[str, object]) -> bool:
        event_type = event.get("type")
        if event_type == "key_down":
            dispatcher = self.event_policy.shortcut_dispatcher
            return bool(
                dispatcher is not None
                and not bool(event.get("repeat", False))
                and dispatcher(int(event.get("key", -1)), int(event.get("mods", 0)))
            )
        if event_type == "file_drop":
            handler = self.event_policy.file_drop_handler
            path = event.get("path")
            if handler is None:
                return False
            if not isinstance(path, str) or not path:
                _logger.error("native UI received a file-drop event without a path")
                return False
            return bool(
                handler(
                    path,
                    float(event.get("x", 0.0)),
                    float(event.get("y", 0.0)),
                    int(event.get("mods", 0)),
                )
            )
        return False

    def defer(self, callback: Callable[[], None]) -> None:
        """Schedule a callback for the UI owner thread from any thread."""
        self._gui_host.defer(callback)

    def process_deferred(self) -> int:
        return self._gui_host.run_deferred()

    def render(self) -> bool:
        return self._gui_host.render_frame()

    def _before_ui_frame(self) -> None:
        self._sync_color_picker_surfaces()
        self._sync_image_previews()
        for callback in tuple(self._pre_render_callbacks):
            try:
                callback(self.context)
            except Exception:
                _logger.exception("Native UI pre-render callback failed")
                raise

    def add_pre_render_callback(self, callback: PreRenderCallback) -> None:
        if callback not in self._pre_render_callbacks:
            self._pre_render_callbacks.append(callback)

    def remove_pre_render_callback(self, callback: PreRenderCallback) -> None:
        if callback in self._pre_render_callbacks:
            self._pre_render_callbacks.remove(callback)

    def register_color_picker(self, picker: object) -> None:
        """Arrange for a native ColorPicker's generated surfaces to use GPU textures."""
        self._gui_host.register_color_picker(picker)

    def unregister_color_picker(self, picker: object) -> None:
        self._gui_host.unregister_color_picker(picker)

    def _sync_color_picker_surfaces(self) -> None:
        # ColorPicker GPU surfaces are synchronized by GuiApplicationHost's
        # renderer before document paint.
        return

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
        self._gui_host.request_repaint()

    @property
    def render_requested(self) -> bool:
        return self._gui_host.repaint_requested

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
        self._gui_host.wait_idle()
        color_target = self._gui_host.color_target
        if not color_target:
            raise RuntimeError("native UI has not rendered a frame for screenshot capture")
        from termin.mcp.screenshot import capture_texture_screenshot

        width, height = self._gui_host.framebuffer_size
        return capture_texture_screenshot(
            color_target,
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
        self._gui_host.set_event_interceptor(None)
        self._gui_host.set_frame_callbacks(None, None)
        self._pre_render_callbacks.clear()
        for preview in tuple(self._image_previews):
            self._release_image_preview(preview)
        self._gui_host.close()
        if self._owns_document:
            self.document.close()

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
    _on_close: Callable[[], None] | None = None
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
    """Drive native hosts that share one canonical windowed graphics session."""

    def __init__(
        self,
        main_host: NativeUiHost,
        *,
        graphics_session: object | None = None,
        host_factory: Callable[..., NativeUiHost] | None = None,
    ) -> None:
        self.main_host = main_host
        if graphics_session is None:
            raise ValueError("NativeUiWindowManager requires a graphics runtime")
        self._graphics_session = graphics_session
        self._host_factory = host_factory if host_factory is not None else NativeUiHost
        self._windows: list[NativeUiWindow] = []
        self._closed = False

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
        try:
            host = self._host_factory(
                self._graphics_session,
                document=document,
                graphics=self.main_host.graphics,
                title=title,
                width=width,
                height=height,
                font_path=self.main_host.font_path,
                enable_text_input=False,
                always_on_top=always_on_top,
            )
            # Secondary tools must inherit the complete editor theme, not just
            # the default font size used when their renderer was constructed.
            host.document.theme = self.main_host.document.theme
        except Exception:
            raise

        window = NativeUiWindow(self, host.window, host, on_close)
        self._windows.append(window)
        return window

    def destroy_window(self, window: NativeUiWindow) -> None:
        if window.manager is not self:
            raise ValueError("secondary native UI window belongs to another manager")
        if window._closed:
            return
        window._closed = True
        if window in self._windows:
            self._windows.remove(window)
        try:
            if window._on_close is not None:
                window._on_close()
        except Exception:
            _logger.exception("native secondary-window close callback failed")
        finally:
            window.host.close()

    def poll_events(self) -> tuple[bool, int]:
        if self._closed:
            return False, 0
        keep_running, routed = self.main_host.poll_events()
        if not keep_running:
            return False, routed
        for window in tuple(self._windows):
            if window.closed:
                continue
            secondary_running, secondary_routed = window.host.poll_events()
            routed += secondary_routed
            if not secondary_running:
                self.destroy_window(window)
        return True, routed

    def process_deferred(self) -> int:
        processed = self.main_host.process_deferred()
        for window in tuple(self._windows):
            if not window.closed:
                processed += window.host.process_deferred()
        return processed

    def render_requested(self) -> int:
        rendered = 0
        hosts = (self.main_host,) + tuple(
            window.host for window in self._windows if not window.closed
        )
        for host in hosts:
            if host.render_requested and host.render():
                rendered += 1
        return rendered

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for window in tuple(self._windows):
            self.destroy_window(window)
        self.main_host.close()
