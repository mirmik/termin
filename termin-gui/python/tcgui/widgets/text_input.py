"""TextInput widget."""

from __future__ import annotations
import time
from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, KeyEvent, TextEvent
from tcgui.widgets.theme import current_theme as _t


class TextInput(Widget):
    """Single-line text input widget."""

    def __init__(self):
        super().__init__()
        self.focusable: bool = True

        # Text content
        self.text: str = ""
        self.placeholder: str = ""
        self.cursor_pos: int = 0
        self.read_only: bool = False

        # Visual configuration
        self.font_size: float = max(10.0, _t.font_size - 2.0)
        self.padding: float = 4
        self.border_width: float = 1
        self.border_radius: float = _t.border_radius
        self.background_color: tuple[float, float, float, float] = _t.bg_input
        self.focused_background_color: tuple[float, float, float, float] = _t.bg_input_focus
        self.border_color: tuple[float, float, float, float] = _t.border
        self.focused_border_color: tuple[float, float, float, float] = _t.border_focus
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.placeholder_color: tuple[float, float, float, float] = _t.text_muted
        self.cursor_color: tuple[float, float, float, float] = _t.text_primary

        # State
        self.focused: bool = False
        self.hovered: bool = False
        self._scroll_offset: float = 0.0
        self._cursor_blink_time: float = 0.0
        self._cursor_visible: bool = True
        self._renderer: 'UIRenderer | None' = None

        # Callbacks
        self.on_changed: Callable[[str], None] | None = None
        self.on_submit: Callable[[str], None] | None = None

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 200
        h = self.font_size + self.padding * 2 + self.border_width * 2
        return (w, h)

    def render(self, renderer: 'UIRenderer'):
        self._renderer = renderer
        bw = self.border_width

        # Border
        border_col = self.focused_border_color if self.focused else self.border_color
        renderer.draw_rect(
            self.x, self.y, self.width, self.height,
            border_col, self.border_radius
        )

        # Background (inset by border)
        bg_color = self.focused_background_color if self.focused else self.background_color
        renderer.draw_rect(
            self.x + bw, self.y + bw,
            self.width - bw * 2, self.height - bw * 2,
            bg_color, max(0, self.border_radius - bw)
        )

        # Text area bounds
        text_x = self.x + self.padding + bw
        text_area_width = self.width - (self.padding + bw) * 2
        text_area_height = self.height - bw * 2
        baseline_y = self.y + self.height / 2 + self.font_size * 0.35

        # Clip text and cursor to the inner area
        renderer.begin_clip(text_x, self.y + bw, text_area_width, text_area_height)

        if self.text:
            self._update_scroll(renderer, text_area_width)
            renderer.draw_text(
                text_x - self._scroll_offset, baseline_y,
                self.text, self.text_color, self.font_size
            )
        elif not self.focused and self.placeholder:
            renderer.draw_text(
                text_x, baseline_y,
                self.placeholder, self.placeholder_color, self.font_size
            )

        # Cursor
        if self.focused:
            self._update_cursor_blink()
            if self._cursor_visible:
                cursor_px = self._get_cursor_x(renderer)
                cursor_screen_x = text_x + cursor_px - self._scroll_offset
                cursor_y = self.y + (self.height - self.font_size) / 2
                renderer.draw_rect(
                    cursor_screen_x, cursor_y,
                    1.5, self.font_size,
                    self.cursor_color
                )

        renderer.end_clip()

    # --- Text measurement helpers ---

    def _measure_text_width(self, renderer: 'UIRenderer', text: str) -> float:
        w, _ = renderer.measure_text(text, self.font_size)
        return w

    def _get_cursor_x(self, renderer: 'UIRenderer') -> float:
        return self._measure_text_width(renderer, self.text[:self.cursor_pos])

    def _update_scroll(self, renderer: 'UIRenderer', text_area_width: float):
        cursor_x = self._get_cursor_x(renderer)
        if cursor_x - self._scroll_offset > text_area_width:
            self._scroll_offset = cursor_x - text_area_width
        if cursor_x - self._scroll_offset < 0:
            self._scroll_offset = cursor_x
        if self._scroll_offset < 0:
            self._scroll_offset = 0

    # --- Cursor blink ---

    def _update_cursor_blink(self):
        now = time.monotonic()
        if now - self._cursor_blink_time >= 0.5:
            self._cursor_visible = not self._cursor_visible
            self._cursor_blink_time = now

    def _reset_cursor_blink(self):
        self._cursor_visible = True
        self._cursor_blink_time = time.monotonic()

    # --- Cursor positioning from click ---

    def _cursor_pos_from_x(self, renderer: 'UIRenderer', click_x: float) -> int:
        text_start_x = self.x + self.padding + self.border_width
        relative_x = click_x - text_start_x + self._scroll_offset
        x_acc = 0.0
        for i, ch in enumerate(self.text):
            char_w = self._measure_text_width(renderer, ch)
            if relative_x < x_acc + char_w / 2:
                return i
            x_acc += char_w
        return len(self.text)

    # --- Mouse events ---

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if self._renderer is not None:
            self.cursor_pos = self._cursor_pos_from_x(self._renderer, event.x)
        self._reset_cursor_blink()
        return True

    # --- Focus events ---

    def on_focus(self):
        self.focused = True
        self._reset_cursor_blink()

    def on_blur(self):
        self.focused = False

    # --- Keyboard events ---

    def on_key_down(self, event: KeyEvent) -> bool:
        from tcbase import Key

        key = event.key
        if self.read_only:
            if key in (Key.LEFT, Key.RIGHT, Key.HOME, Key.END):
                if key == Key.LEFT and self.cursor_pos > 0:
                    self.cursor_pos -= 1
                elif key == Key.RIGHT and self.cursor_pos < len(self.text):
                    self.cursor_pos += 1
                elif key == Key.HOME:
                    self.cursor_pos = 0
                elif key == Key.END:
                    self.cursor_pos = len(self.text)
                self._reset_cursor_blink()
                return True
            return False

        if key == Key.BACKSPACE:
            if self.cursor_pos > 0:
                self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
                self.cursor_pos -= 1
                self._fire_on_change()
            self._reset_cursor_blink()
            return True

        if key == Key.DELETE:
            if self.cursor_pos < len(self.text):
                self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos + 1:]
                self._fire_on_change()
            self._reset_cursor_blink()
            return True

        if key == Key.LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
            self._reset_cursor_blink()
            return True

        if key == Key.RIGHT:
            if self.cursor_pos < len(self.text):
                self.cursor_pos += 1
            self._reset_cursor_blink()
            return True

        if key == Key.HOME:
            self.cursor_pos = 0
            self._reset_cursor_blink()
            return True

        if key == Key.END:
            self.cursor_pos = len(self.text)
            self._reset_cursor_blink()
            return True

        if key == Key.ENTER:
            if self.on_submit is not None:
                self.on_submit(self.text)
            return True

        return False

    def on_text_input(self, event: TextEvent) -> bool:
        if self.read_only:
            return False
        self.text = self.text[:self.cursor_pos] + event.text + self.text[self.cursor_pos:]
        self.cursor_pos += len(event.text)
        self._fire_on_change()
        self._reset_cursor_blink()
        return True

    def _fire_on_change(self):
        if self.on_changed is not None:
            self.on_changed(self.text)
