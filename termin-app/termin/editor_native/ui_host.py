"""SDL/tgfx2 host boundary for one native ``tc_ui_document``."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Callable, Protocol

from termin.display import WindowHandle, WindowManager
from tgfx import Tgfx2Context
from termin.gui_native import (
    Document,
    GuiWindowAdapter,
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


class NativeWidgetContent:
    """Application-side native-widget content attached to one managed window.

    The C++ ``GuiWindowAdapter`` remains the actual UI/window integration.
    This object owns only editor features layered beside it: the document,
    shortcut/drop policy, preview textures and screenshot routing.
    """

    def __init__(
        self,
        window_manager: WindowManager,
        window_handle: WindowHandle,
        document: Document | None = None,
        *,
        graphics: Tgfx2Context | None = None,
        font_path: str | Path | None = None,
        file_drop_handler: FileDropHandler | None = None,
        enable_text_input: bool = True,
        always_on_top: bool = False,
    ) -> None:
        self._owns_document = document is None
        self.document = document if document is not None else Document()
        resolved_font = resolve_native_ui_font(font_path)
        self.font_path = resolved_font
        self.window_manager = window_manager
        self.window_handle = window_handle
        self.adapter = GuiWindowAdapter(
            window_manager,
            window_handle,
            self.document,
            font_path=str(resolved_font),
            font_size=15,
            enable_text_input=enable_text_input,
        )
        self.window = self.adapter.window
        if always_on_top:
            self.window.set_always_on_top(True)
        self.graphics = (
            graphics
            if graphics is not None
            else Tgfx2Context.from_runtime(self.adapter.graphics)
        )
        self.device = self.graphics.device
        self.context = self.graphics.context
        self.event_policy = NativeUiEventPolicy(
            file_drop_handler=file_drop_handler,
        )
        self._closed = False
        self._pre_render_callbacks: list[PreRenderCallback] = []
        self._image_previews: list[_ImagePreview] = []
        self.adapter.set_before_frame_callback(self._before_ui_frame)

    @property
    def color_target(self):
        """Current host-owned render target for screenshot/MCP readback."""

        return self.adapter.color_target

    def poll_events(self) -> tuple[bool, int]:
        count = self.adapter.consume_pending_events(
            self.window_manager,
            self.window_handle,
            self._intercept_event,
        )
        return not self.adapter.should_close, count

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
        self.adapter.defer(callback)

    def process_deferred(self) -> int:
        return self.adapter.run_deferred()

    def render(self) -> bool:
        return self.adapter.render_frame()

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
        self.adapter.register_color_picker(picker)

    def unregister_color_picker(self, picker: object) -> None:
        self.adapter.unregister_color_picker(picker)

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
        self.adapter.request_repaint()

    @property
    def render_requested(self) -> bool:
        return self.adapter.repaint_requested

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
        self.adapter.wait_idle()
        color_target = self.adapter.color_target
        if not color_target:
            raise RuntimeError("native UI has not rendered a frame for screenshot capture")
        from termin.mcp.screenshot import capture_texture_screenshot

        width, height = self.adapter.framebuffer_size
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
        self.adapter.set_before_frame_callback(None)
        self._pre_render_callbacks.clear()
        for preview in tuple(self._image_previews):
            self._release_image_preview(preview)
        self.adapter.close()
        if self._owns_document:
            self.document.close()

    def __enter__(self) -> NativeWidgetContent:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


class WindowContent(Protocol):
    """Content contract selected by the application for a managed window."""

    window: object
    render_requested: bool

    def poll_events(self) -> tuple[bool, int]: ...
    def process_deferred(self) -> int: ...
    def render(self) -> bool: ...
    def request_render_update(self) -> None: ...
    def close(self) -> None: ...


@dataclass
class EditorWindowSlot:
    """Application policy for one framework-neutral managed OS window."""

    registry: "EditorWindowRegistry"
    handle: WindowHandle
    content: WindowContent
    _on_close: Callable[[], None] | None = None
    _closed: bool = False

    @property
    def closed(self) -> bool:
        return self._closed

    def request_render_update(self) -> None:
        if not self._closed:
            self.content.request_render_update()

    def close(self) -> None:
        if not self._closed:
            self.registry.destroy_window(self)


class EditorWindowRegistry:
    """Editor-owned mapping from native window handles to selected content."""

    def __init__(
        self,
        window_manager: WindowManager,
        main_handle: WindowHandle,
        main_content: WindowContent,
    ) -> None:
        if not window_manager.contains(main_handle):
            raise ValueError("main window handle is not owned by the window manager")
        self.window_manager = window_manager
        self.main = EditorWindowSlot(self, main_handle, main_content)
        self._windows: list[EditorWindowSlot] = []
        self._closed = False

    @property
    def windows(self) -> tuple[EditorWindowSlot, ...]:
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
        content_factory: Callable[[WindowManager, WindowHandle], WindowContent] | None = None,
    ) -> EditorWindowSlot:
        if self._closed:
            raise RuntimeError("editor window registry is closed")
        handle = self.window_manager.create_window(title, width, height)
        try:
            if content_factory is None:
                main_content = self.main.content
                if not isinstance(main_content, NativeWidgetContent):
                    raise ValueError(
                        "native widget content requires an explicit content_factory"
                    )
                content = NativeWidgetContent(
                    self.window_manager,
                    handle,
                    document=document,
                    graphics=main_content.graphics,
                    font_path=main_content.font_path,
                    enable_text_input=False,
                    always_on_top=always_on_top,
                )
                content.document.theme = main_content.document.theme
            else:
                content = content_factory(self.window_manager, handle)
        except Exception:
            self.window_manager.destroy_window(handle)
            raise

        window = EditorWindowSlot(self, handle, content, on_close)
        self._windows.append(window)
        return window

    def destroy_window(self, window: EditorWindowSlot) -> None:
        if window.registry is not self:
            raise ValueError("editor window belongs to another registry")
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
        content_error: Exception | None = None
        try:
            window.content.close()
        except Exception as error:
            content_error = error
            _logger.exception("editor secondary-window content close failed")
        finally:
            if self.window_manager.contains(window.handle):
                self.window_manager.destroy_window(window.handle)
        if content_error is not None:
            raise content_error

    def poll_events(self) -> tuple[bool, int]:
        if self._closed:
            return False, 0
        routed = self.window_manager.pump_events()
        keep_running, _main_consumed = self.main.content.poll_events()
        if not keep_running:
            return False, routed
        for window in tuple(self._windows):
            if window.closed:
                continue
            secondary_running, _secondary_consumed = window.content.poll_events()
            if not secondary_running:
                self.destroy_window(window)
        return True, routed

    def process_deferred(self) -> int:
        processed = self.main.content.process_deferred()
        for window in tuple(self._windows):
            if not window.closed:
                processed += window.content.process_deferred()
        return processed

    def render_requested(self) -> int:
        rendered = 0
        contents = (self.main.content,) + tuple(
            window.content for window in self._windows if not window.closed
        )
        for content in contents:
            if content.render_requested and content.render():
                rendered += 1
        return rendered

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close_errors: list[Exception] = []
        for window in tuple(self._windows):
            try:
                self.destroy_window(window)
            except Exception as error:
                close_errors.append(error)
        self.main._closed = True
        try:
            self.main.content.close()
        except Exception as error:
            _logger.exception("editor main-window content close failed")
            close_errors.append(error)
        finally:
            try:
                if self.window_manager.contains(self.main.handle):
                    self.window_manager.destroy_window(self.main.handle)
            finally:
                self.window_manager.close()
        if close_errors:
            raise RuntimeError(
                f"editor window registry close failed for {len(close_errors)} content object(s)"
            ) from close_errors[0]
