"""SpinBox widget."""

from __future__ import annotations
import time
from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, KeyEvent, TextEvent
from tcgui.widgets.theme import current_theme as _t


class SpinBox(Widget):
    """Numeric input with increment/decrement buttons."""

    def __init__(self):
        super().__init__()
        self.focusable: bool = True

        # Numeric parameters
        self.value: float = 0.0
        self.min_value: float = -1e9
        self.max_value: float = 1e9
        self.step: float = 1.0
        self.decimals: int = 2

        # Visual configuration
        self.font_size: float = max(10.0, _t.font_size - 2.0)
        self.padding: float = 4
        self.border_width: float = 1
        self.border_radius: float = _t.border_radius
        self.button_width: float = 18

        # Colors
        self.background_color: tuple[float, float, float, float] = _t.bg_input
        self.focused_background_color: tuple[float, float, float, float] = _t.bg_input_focus
        self.border_color: tuple[float, float, float, float] = _t.border
        self.focused_border_color: tuple[float, float, float, float] = _t.border_focus
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.cursor_color: tuple[float, float, float, float] = _t.text_primary
        self.button_color: tuple[float, float, float, float] = _t.bg_surface
        self.button_hover_color: tuple[float, float, float, float] = _t.hover
        self.arrow_color: tuple[float, float, float, float] = _t.text_secondary

        # State
        self.focused: bool = False
        self.hovered: bool = False
        self._editing: bool = False
        self._edit_text: str = ""
        self._cursor_pos: int = 0
        self._hovered_button: str = ""  # "" / "up" / "down"
        self._cursor_blink_time: float = 0.0
        self._cursor_visible: bool = True
        self._renderer: 'UIRenderer | None' = None

        # Callback
        self.on_changed: Callable[[float], None] | None = None

    def _format_value(self) -> str:
        if self.decimals <= 0:
            return str(int(self.value))
        return f"{self.value:.{self.decimals}f}"

    def _clamp(self, val: float) -> float:
        return max(self.min_value, min(self.max_value, val))

    def _set_value(self, val: float):
        val = self._clamp(val)
        if val != self.value:
            self.value = val
            if self.on_changed:
                self.on_changed(self.value)

    def _increment(self):
        self._set_value(self.value + self.step)

    def _decrement(self):
        self._set_value(self.value - self.step)

    def _begin_edit(self):
        self._editing = True
        self._edit_text = self._format_value()
        self._cursor_pos = len(self._edit_text)
        self._reset_cursor_blink()

    def _commit_edit(self):
        if not self._editing:
            return
        self._editing = False
        try:
            val = float(self._edit_text)
        except ValueError:
            return
        self._set_value(val)

    def _cancel_edit(self):
        self._editing = False

    # Cursor blink (same pattern as TextInput)
    def _update_cursor_blink(self):
        now = time.monotonic()
        if now - self._cursor_blink_time >= 0.5:
            self._cursor_visible = not self._cursor_visible
            self._cursor_blink_time = now

    def _reset_cursor_blink(self):
        self._cursor_visible = True
        self._cursor_blink_time = time.monotonic()

    def _measure_text_width(self, renderer, text: str) -> float:
        w, _ = renderer.measure_text(text, self.font_size)
        return w

    # --- Geometry helpers ---

    def _button_rect(self) -> tuple[float, float, float, float]:
        """Return (x, y, w, h) of the button area."""
        bw = self.border_width
        bx = self.x + self.width - self.button_width - bw
        by = self.y + bw
        bh = self.height - bw * 2
        return bx, by, self.button_width, bh

    def _up_button_rect(self) -> tuple[float, float, float, float]:
        bx, by, bw, bh = self._button_rect()
        return bx, by, bw, bh / 2

    def _down_button_rect(self) -> tuple[float, float, float, float]:
        bx, by, bw, bh = self._button_rect()
        return bx, by + bh / 2, bw, bh / 2

    # --- Size ---

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 120
        h = self.font_size + self.padding * 2 + self.border_width * 2
        return (w, h)

    # --- Render ---

    def render(self, renderer: 'UIRenderer'):
        self._renderer = renderer
        bw = self.border_width

        # Border
        border_col = self.focused_border_color if self.focused else self.border_color
        renderer.draw_rect(self.x, self.y, self.width, self.height, border_col, self.border_radius)

        # Background
        bg_color = self.focused_background_color if self.focused else self.background_color
        renderer.draw_rect(
            self.x + bw, self.y + bw,
            self.width - bw * 2, self.height - bw * 2,
            bg_color, max(0, self.border_radius - bw)
        )

        # Button area
        bx, by, btn_w, bh = self._button_rect()

        # Up button
        ux, uy, uw, uh = self._up_button_rect()
        up_col = self.button_hover_color if self._hovered_button == "up" else self.button_color
        renderer.draw_rect(ux, uy, uw, uh, up_col, 0)
        renderer.draw_text_centered(ux + uw / 2, uy + uh / 2, "\u25B2", self.arrow_color, self.font_size * 0.5)

        # Down button
        dx, dy, dw, dh = self._down_button_rect()
        down_col = self.button_hover_color if self._hovered_button == "down" else self.button_color
        renderer.draw_rect(dx, dy, dw, dh, down_col, 0)
        renderer.draw_text_centered(dx + dw / 2, dy + dh / 2, "\u25BC", self.arrow_color, self.font_size * 0.5)

        # Text area
        text_x = self.x + self.padding + bw
        text_area_width = self.width - (self.padding + bw) * 2 - self.button_width
        text_area_height = self.height - bw * 2
        baseline_y = self.y + self.height / 2 + self.font_size * 0.35

        renderer.begin_clip(text_x, self.y + bw, text_area_width, text_area_height)

        display_text = self._edit_text if self._editing else self._format_value()
        renderer.draw_text(text_x, baseline_y, display_text, self.text_color, self.font_size)

        # Cursor
        if self.focused and self._editing:
            self._update_cursor_blink()
            if self._cursor_visible:
                cursor_px = self._measure_text_width(renderer, self._edit_text[:self._cursor_pos])
                cursor_screen_x = text_x + cursor_px
                cursor_y = self.y + (self.height - self.font_size) / 2
                renderer.draw_rect(cursor_screen_x, cursor_y, 1.5, self.font_size, self.cursor_color)

        renderer.end_clip()

    # --- Mouse events ---

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False
        self._hovered_button = ""

    def on_mouse_move(self, event: MouseEvent):
        ux, uy, uw, uh = self._up_button_rect()
        dx, dy, dw, dh = self._down_button_rect()
        if ux <= event.x < ux + uw and uy <= event.y < uy + uh:
            self._hovered_button = "up"
        elif dx <= event.x < dx + dw and dy <= event.y < dy + dh:
            self._hovered_button = "down"
        else:
            self._hovered_button = ""

    def on_mouse_down(self, event: MouseEvent) -> bool:
        # Check buttons
        ux, uy, uw, uh = self._up_button_rect()
        if ux <= event.x < ux + uw and uy <= event.y < uy + uh:
            self._increment()
            if self._editing:
                self._edit_text = self._format_value()
                self._cursor_pos = len(self._edit_text)
            return True

        dx, dy, dw, dh = self._down_button_rect()
        if dx <= event.x < dx + dw and dy <= event.y < dy + dh:
            self._decrement()
            if self._editing:
                self._edit_text = self._format_value()
                self._cursor_pos = len(self._edit_text)
            return True

        # Click on text area — begin editing
        if not self._editing:
            self._begin_edit()
        # Position cursor
        if self._renderer is not None:
            text_start_x = self.x + self.padding + self.border_width
            relative_x = event.x - text_start_x
            x_acc = 0.0
            for i, ch in enumerate(self._edit_text):
                char_w = self._measure_text_width(self._renderer, ch)
                if relative_x < x_acc + char_w / 2:
                    self._cursor_pos = i
                    break
                x_acc += char_w
            else:
                self._cursor_pos = len(self._edit_text)
        self._reset_cursor_blink()
        return True

    # --- Focus events ---

    def on_focus(self):
        self.focused = True
        self._reset_cursor_blink()

    def on_blur(self):
        self.focused = False
        self._commit_edit()

    # --- Keyboard events ---

    def on_key_down(self, event: KeyEvent) -> bool:
        from tcbase import Key

        key = event.key
        if key == Key.UP:
            self._increment()
            if self._editing:
                self._edit_text = self._format_value()
                self._cursor_pos = len(self._edit_text)
            self._reset_cursor_blink()
            return True

        if key == Key.DOWN:
            self._decrement()
            if self._editing:
                self._edit_text = self._format_value()
                self._cursor_pos = len(self._edit_text)
            self._reset_cursor_blink()
            return True

        if not self._editing:
            return False

        if key == Key.LEFT:
            if self._cursor_pos > 0:
                self._cursor_pos -= 1
            self._reset_cursor_blink()
            return True

        if key == Key.RIGHT:
            if self._cursor_pos < len(self._edit_text):
                self._cursor_pos += 1
            self._reset_cursor_blink()
            return True

        if key == Key.HOME:
            self._cursor_pos = 0
            self._reset_cursor_blink()
            return True

        if key == Key.END:
            self._cursor_pos = len(self._edit_text)
            self._reset_cursor_blink()
            return True

        if key == Key.BACKSPACE:
            if self._cursor_pos > 0:
                self._edit_text = self._edit_text[:self._cursor_pos - 1] + self._edit_text[self._cursor_pos:]
                self._cursor_pos -= 1
            self._reset_cursor_blink()
            return True

        if key == Key.DELETE:
            if self._cursor_pos < len(self._edit_text):
                self._edit_text = self._edit_text[:self._cursor_pos] + self._edit_text[self._cursor_pos + 1:]
            self._reset_cursor_blink()
            return True

        if key == Key.ENTER:
            self._commit_edit()
            return True

        if key == Key.ESCAPE:
            self._cancel_edit()
            return True

        return False

    def on_text_input(self, event: TextEvent) -> bool:
        if not self._editing:
            self._begin_edit()
        # Filter: only digits, dot, minus
        filtered = "".join(ch for ch in event.text if ch in "0123456789.-")
        if not filtered:
            return True
        self._edit_text = self._edit_text[:self._cursor_pos] + filtered + self._edit_text[self._cursor_pos:]
        self._cursor_pos += len(filtered)
        self._reset_cursor_blink()
        return True
