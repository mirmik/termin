"""Selectable windowed and isolated/offscreen editor UI compositions."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from pathlib import Path
import tempfile
from typing import Callable

from termin.graphics import Tgfx2Context
from termin.gui_native import OffscreenGuiComposition, Size, StyleRole


_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EditorCompositionConfig:
    mode: str = "windowed"
    width: int = 1280
    height: int = 720
    backend: str = "vulkan"
    frame_limit: int = 0

    def __post_init__(self) -> None:
        if self.mode not in {"windowed", "offscreen"}:
            raise ValueError(f"unsupported editor composition: {self.mode}")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("editor composition dimensions must be positive")
        if self.frame_limit < 0:
            raise ValueError("editor frame limit must not be negative")


@dataclass(slots=True)
class EditorUiEventPolicy:
    file_drop_handler: Callable[[str, float, float, int], bool] | None = None
    shortcut_dispatcher: Callable[[int, int], bool] | None = None


@dataclass(slots=True)
class _ImagePreview:
    image: object
    pixels: object
    texture: object | None = None


class OffscreenEditorWindow:
    """Window-like editor policy surface backed by no OS window."""

    def __init__(self, composition: OffscreenGuiComposition, backend: str) -> None:
        self._composition = composition
        self.backend = backend
        self.title = "Termin Editor — Offscreen"
        self.fullscreen = False

    def framebuffer_size(self) -> tuple[int, int]:
        return tuple(self._composition.framebuffer_size)

    def set_title(self, title: str) -> None:
        self.title = title

    def set_should_close(self, close: bool) -> None:
        if close:
            self._composition.request_close()

    def should_close(self) -> bool:
        return bool(self._composition.should_close)

    def set_fullscreen(self, fullscreen: bool) -> None:
        self.fullscreen = bool(fullscreen)

    def maximize(self) -> None:
        return


class OffscreenEditorContent:
    """Editor content facade over the window-system-independent composition."""

    def __init__(self, config: EditorCompositionConfig) -> None:
        self.composition = OffscreenGuiComposition(
            width=config.width,
            height=config.height,
            backend=config.backend,
            font_size=15,
            continuous_rendering=False,
            application_graphics_domain=True,
        )
        self.document = self.composition.document
        self.graphics = Tgfx2Context.from_runtime(self.composition.graphics)
        self.device = self.graphics.device
        self.context = self.graphics.context
        self.window = OffscreenEditorWindow(self.composition, config.backend)
        self.event_policy = EditorUiEventPolicy()
        self._pre_render_callbacks: list[Callable[[object], None]] = []
        self._image_previews: list[_ImagePreview] = []
        self._closed = False
        self.composition.set_unhandled_key_handler(self._dispatch_shortcut)

    def _dispatch_shortcut(self, key: int, modifiers: int) -> bool:
        dispatcher = self.event_policy.shortcut_dispatcher
        return bool(dispatcher is not None and dispatcher(key, modifiers))

    def poll_events(self) -> tuple[bool, int]:
        count = int(self.composition.pump_events())
        return not self.composition.should_close, count

    def render(self) -> bool:
        self._sync_image_previews()
        for callback in tuple(self._pre_render_callbacks):
            try:
                callback(self.context)
            except Exception:
                _logger.exception("Offscreen editor pre-render callback failed")
                raise
        return bool(self.composition.render_frame())

    @property
    def render_requested(self) -> bool:
        return bool(self.composition.repaint_requested)

    def request_render_update(self) -> None:
        self.composition.request_repaint()

    def add_pre_render_callback(self, callback: Callable[[object], None]) -> None:
        if callback not in self._pre_render_callbacks:
            self._pre_render_callbacks.append(callback)

    def remove_pre_render_callback(self, callback: Callable[[object], None]) -> None:
        if callback in self._pre_render_callbacks:
            self._pre_render_callbacks.remove(callback)

    def register_color_picker(self, picker: object) -> None:
        self.composition.register_color_picker(picker)

    def unregister_color_picker(self, picker: object) -> None:
        self.composition.unregister_color_picker(picker)

    def set_clipboard_text(self, text: str) -> None:
        if not self.composition.set_clipboard_text(text):
            raise RuntimeError("offscreen editor clipboard rejected text")

    def register_image_preview(
        self,
        image: object,
        pixels: object,
        *,
        max_dimension: int | None = 128,
    ) -> Callable[[], None]:
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
        return lambda: self._release_image_preview(preview)

    def _sync_image_previews(self) -> None:
        for preview in tuple(self._image_previews):
            if not self.document.is_alive(preview.image.handle):
                _logger.error("offscreen image preview destroyed without unregistration")
                self._release_image_preview(preview)
                continue
            if preview.texture is None:
                from termin.graphics import TextureEncoding

                height, width, _channels = preview.pixels.shape
                preview.texture = self.context.create_texture_rgba8(
                    width,
                    height,
                    preview.pixels,
                    TextureEncoding.SRGB,
                )
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
            theme.role(role).base.font_size = size
        self.document.theme = theme
        self.request_render_update()

    def capture_screenshot(
        self,
        *,
        output_path: str | None = None,
        include_image: bool = False,
    ) -> dict[str, object]:
        if not self.render():
            raise RuntimeError("offscreen editor cannot compose a screenshot frame")
        self.composition.wait_idle()
        texture = self.composition.latest_frame_texture
        if not texture:
            raise RuntimeError("offscreen editor has no published frame")
        from termin.graphics.mcp import capture_texture_screenshot

        width, height = self.composition.latest_frame_size
        return capture_texture_screenshot(
            texture,
            self.device,
            width=width,
            height=height,
            output_path=output_path,
            include_image=include_image,
            default_dir=Path(tempfile.gettempdir()) / "termin-editor-screenshots",
            default_prefix="termin-editor-offscreen",
            log_prefix="OffscreenEditorScreenshot",
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._pre_render_callbacks.clear()
        for preview in tuple(self._image_previews):
            self._release_image_preview(preview)
        self.composition.close()


@dataclass(slots=True)
class _HeadlessMainSlot:
    content: OffscreenEditorContent


class OffscreenEditorWindowRegistry:
    """Single-document registry with no termin-window dependency."""

    def __init__(self, content: OffscreenEditorContent) -> None:
        self.main = _HeadlessMainSlot(content)
        self._closed = False

    @property
    def windows(self) -> tuple[object, ...]:
        return ()

    def create_window(self, *_args, **_kwargs):
        raise RuntimeError("secondary OS windows are unavailable in offscreen editor mode")

    def poll_events(self) -> tuple[bool, int]:
        if self._closed:
            return False, 0
        return self.main.content.poll_events()

    def service_platform_events(self) -> int:
        return 0

    def render_requested(self) -> int:
        if self._closed or not self.main.content.render_requested:
            return 0
        return int(self.main.content.render())

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.main.content.close()


@dataclass(slots=True)
class EditorComposition:
    host: object
    window_manager: object
    window: object
    graphics_host: object
    windowed: bool


def create_editor_composition(
    stage,
    config: EditorCompositionConfig,
    *,
    presentation_mode: object,
) -> EditorComposition:
    if config.mode == "offscreen":
        host = stage.own(
            "offscreen editor content",
            OffscreenEditorContent(config),
        )
        window_manager = stage.own(
            "offscreen editor registry",
            OffscreenEditorWindowRegistry(host),
            cleanup=lambda: window_manager.close(),
        )
        return EditorComposition(
            host=host,
            window_manager=window_manager,
            window=host.window,
            graphics_host=host.composition.graphics,
            windowed=False,
        )

    from termin.display.window import WindowManager, WindowedGraphicsSession, quit_sdl
    from termin.editor_native.ui_host import EditorWindowRegistry, NativeWidgetContent

    stage.add_cleanup("SDL runtime", quit_sdl)
    graphics_session = stage.own(
        "windowed graphics session",
        WindowedGraphicsSession.create_native(),
        cleanup=lambda: graphics_session.close(),
    )
    graphics = stage.own(
        "graphics context",
        Tgfx2Context.from_runtime(graphics_session.graphics),
    )
    native_windows = stage.own(
        "framework-neutral window manager",
        WindowManager(graphics_session),
        cleanup=lambda: native_windows.close(),
    )
    main_window_handle = native_windows.create_window(
        "Termin Editor — Native UI",
        config.width,
        config.height,
        presentation_mode,
    )
    host = stage.own(
        "native widget content",
        NativeWidgetContent(
            native_windows,
            main_window_handle,
            graphics=graphics,
        ),
    )
    window_manager = stage.own(
        "editor window registry",
        EditorWindowRegistry(native_windows, main_window_handle, host),
        cleanup=lambda: window_manager.close(),
    )
    return EditorComposition(
        host=host,
        window_manager=window_manager,
        window=host.window,
        graphics_host=graphics_session.graphics,
        windowed=True,
    )


__all__ = [
    "EditorCompositionConfig",
    "OffscreenEditorContent",
    "OffscreenEditorWindowRegistry",
    "create_editor_composition",
]
