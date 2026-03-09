"""TextArea widget with word wrap support."""

from __future__ import annotations
import time
from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, MouseWheelEvent, KeyEvent, TextEvent
from tcgui.widgets.theme import current_theme as _t


class TextArea(Widget):
    """Multi-line text editor with scrollbar and word wrap."""

    def __init__(self):
        super().__init__()
        self.focusable: bool = True

        # Content
        self._lines: list[str] = [""]
        self.placeholder: str = ""
        self.cursor_line: int = 0
        self.cursor_col: int = 0
        self.max_lines: int = 0  # 0 = unlimited
        self.read_only: bool = False
        self.word_wrap: bool = True

        # Visual configuration
        self.font_size: float = _t.font_size
        self.padding: float = 6
        self.border_width: float = 1
        self.border_radius: float = _t.border_radius
        self.line_height: float = 0  # 0 = auto

        # Colors
        self.background_color: tuple[float, float, float, float] = _t.bg_input
        self.focused_background_color: tuple[float, float, float, float] = _t.bg_input_focus
        self.border_color: tuple[float, float, float, float] = _t.border
        self.focused_border_color: tuple[float, float, float, float] = _t.border_focus
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.placeholder_color: tuple[float, float, float, float] = _t.text_muted
        self.cursor_color: tuple[float, float, float, float] = _t.text_primary

        # Scrollbar
        self.show_scrollbar: bool = True
        self.scrollbar_width: float = 8.0
        self.scrollbar_color: tuple[float, float, float, float] = _t.scrollbar
        self.scrollbar_hover_color: tuple[float, float, float, float] = _t.scrollbar_hover

        # State
        self.focused: bool = False
        self.hovered: bool = False
        self._scroll_y: float = 0.0
        self._scroll_x: float = 0.0
        self._cursor_blink_time: float = 0.0
        self._cursor_visible: bool = True
        self._dragging_scrollbar: bool = False
        self._scrollbar_hovered: bool = False
        self._drag_start_y: float = 0.0
        self._drag_start_scroll: float = 0.0
        self._renderer: 'UIRenderer | None' = None

        # Visual line cache for word wrap.
        # Each entry: (logical_line_idx, start_col, end_col)
        self._vlines: list[tuple[int, int, int]] = []
        self._vlines_content_w: float = -1
        self._last_content_w: float = 0

        # Callback
        self.on_changed: Callable[[str], None] | None = None

    # --- Text property ---

    @property
    def text(self) -> str:
        return "\n".join(self._lines)

    @text.setter
    def text(self, value: str):
        self._lines = value.split("\n") if value else [""]
        self.cursor_line = min(self.cursor_line, len(self._lines) - 1)
        self.cursor_col = min(self.cursor_col, len(self._lines[self.cursor_line]))
        self._invalidate_vlines()

    # --- Word wrap ---

    def _invalidate_vlines(self):
        self._vlines_content_w = -1

    def _wrap_line(self, renderer, text: str, max_width: float) -> list[tuple[int, int]]:
        """Split *text* into (start_col, end_col) segments fitting *max_width*."""
        if not text:
            return [(0, 0)]
        if max_width <= 0 or self._measure_text_width(renderer, text) <= max_width:
            return [(0, len(text))]

        segments: list[tuple[int, int]] = []
        start = 0
        while start < len(text):
            if self._measure_text_width(renderer, text[start:]) <= max_width:
                segments.append((start, len(text)))
                break

            # Find the furthest char that still fits.
            fit = start
            for i in range(start + 1, len(text) + 1):
                if self._measure_text_width(renderer, text[start:i]) > max_width:
                    break
                fit = i

            if fit <= start:
                fit = start + 1  # force at least 1 char

            # Prefer breaking at a word boundary.
            break_at = fit
            space_pos = text.rfind(' ', start, fit)
            if space_pos > start:
                break_at = space_pos + 1  # break after space

            segments.append((start, break_at))
            start = break_at

        return segments

    def _ensure_vlines(self, renderer, content_w: float):
        """Recompute visual lines if cache is stale."""
        if self._vlines_content_w == content_w:
            return
        self._vlines = []
        if not self.word_wrap:
            for i, line in enumerate(self._lines):
                self._vlines.append((i, 0, len(line)))
        else:
            for i, line in enumerate(self._lines):
                for sc, ec in self._wrap_line(renderer, line, content_w):
                    self._vlines.append((i, sc, ec))
        self._vlines_content_w = content_w

    def _cursor_visual_row(self) -> int:
        """Return the visual-row index where the cursor sits."""
        for vi, (li, sc, ec) in enumerate(self._vlines):
            if li == self.cursor_line and sc <= self.cursor_col <= ec:
                # At segment boundary → prefer the start of next segment.
                if (self.cursor_col == ec
                        and vi + 1 < len(self._vlines)
                        and self._vlines[vi + 1][0] == li):
                    continue
                return vi
        return max(0, len(self._vlines) - 1)

    def _refresh_vlines_if_possible(self):
        """Eagerly recompute vlines when renderer and dimensions are known."""
        if not self.word_wrap or self._renderer is None or self.width <= 0:
            return
        if self._last_content_w > 0:
            self._ensure_vlines(self._renderer, self._last_content_w)

    # --- Helpers ---

    def _effective_line_height(self) -> float:
        return self.line_height if self.line_height > 0 else self.font_size * 1.4

    def _content_height(self) -> float:
        if self.word_wrap and self._vlines:
            return len(self._vlines) * self._effective_line_height()
        return len(self._lines) * self._effective_line_height()

    def _visible_height(self) -> float:
        bw = self.border_width
        return self.height - self.padding * 2 - bw * 2

    def _max_scroll_y(self) -> float:
        return max(0.0, self._content_height() - self._visible_height())

    def _ensure_cursor_visible(self):
        lh = self._effective_line_height()
        if self.word_wrap and self._vlines and self._vlines_content_w > 0:
            vrow = self._cursor_visual_row()
            cursor_top = vrow * lh
        else:
            cursor_top = self.cursor_line * lh
        cursor_bottom = cursor_top + lh
        visible_h = self._visible_height()
        if cursor_top < self._scroll_y:
            self._scroll_y = cursor_top
        if cursor_bottom > self._scroll_y + visible_h:
            self._scroll_y = cursor_bottom - visible_h
        self._scroll_y = max(0.0, min(self._scroll_y, self._max_scroll_y()))

    def _measure_text_width(self, renderer, text: str) -> float:
        w, _ = renderer.measure_text(text, self.font_size)
        return w

    def _cursor_pos_from_xy(self, renderer, x: float, y: float) -> tuple[int, int]:
        bw = self.border_width
        content_x = self.x + self.padding + bw
        content_y = self.y + self.padding + bw
        lh = self._effective_line_height()

        if self.word_wrap and self._vlines:
            rel_y = y - content_y + self._scroll_y
            vrow = int(rel_y / lh)
            vrow = max(0, min(vrow, len(self._vlines) - 1))
            li, sc, ec = self._vlines[vrow]

            rel_x = x - content_x
            segment_text = self._lines[li][sc:ec]
            col = ec
            x_acc = 0.0
            for i, ch in enumerate(segment_text):
                char_w = self._measure_text_width(renderer, ch)
                if rel_x < x_acc + char_w / 2:
                    col = sc + i
                    break
                x_acc += char_w
            return li, col

        rel_y = y - content_y + self._scroll_y
        line = int(rel_y / lh)
        line = max(0, min(line, len(self._lines) - 1))

        rel_x = x - content_x + self._scroll_x
        line_text = self._lines[line]
        x_acc = 0.0
        col = len(line_text)
        for i, ch in enumerate(line_text):
            char_w = self._measure_text_width(renderer, ch)
            if rel_x < x_acc + char_w / 2:
                col = i
                break
            x_acc += char_w
        return line, col

    # --- Cursor blink ---

    def _update_cursor_blink(self):
        now = time.monotonic()
        if now - self._cursor_blink_time >= 0.5:
            self._cursor_visible = not self._cursor_visible
            self._cursor_blink_time = now

    def _reset_cursor_blink(self):
        self._cursor_visible = True
        self._cursor_blink_time = time.monotonic()

    # --- Size ---

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 300
        h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else 150
        return (w, h)

    # --- Render ---

    def render(self, renderer: 'UIRenderer'):
        self._renderer = renderer
        bw = self.border_width
        lh = self._effective_line_height()

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

        content_x = self.x + self.padding + bw
        content_y = self.y + self.padding + bw
        content_w = self.width - (self.padding + bw) * 2
        content_h = self._visible_height()

        # Determine scrollbar and compute visual lines for word wrap.
        if self.word_wrap:
            self._ensure_vlines(renderer, content_w)
            has_scrollbar = self.show_scrollbar and self._content_height() > content_h
            if has_scrollbar:
                content_w -= self.scrollbar_width
                self._ensure_vlines(renderer, content_w)
                has_scrollbar = self.show_scrollbar and self._content_height() > content_h
        else:
            has_scrollbar = self.show_scrollbar and self._content_height() > content_h
            if has_scrollbar:
                content_w -= self.scrollbar_width

        self._last_content_w = content_w

        renderer.begin_clip(content_x, content_y, content_w, content_h)

        if not self._lines or (len(self._lines) == 1 and not self._lines[0]):
            # Placeholder
            if not self.focused and self.placeholder:
                renderer.draw_text(
                    content_x, content_y + self.font_size,
                    self.placeholder, self.placeholder_color, self.font_size
                )
        elif self.word_wrap and self._vlines:
            # Draw wrapped visual lines.
            first_row = max(0, int(self._scroll_y / lh))
            last_row = min(len(self._vlines), int((self._scroll_y + content_h) / lh) + 1)
            for vi in range(first_row, last_row):
                li, sc, ec = self._vlines[vi]
                row_y = content_y + vi * lh - self._scroll_y + self.font_size
                renderer.draw_text(
                    content_x, row_y,
                    self._lines[li][sc:ec], self.text_color, self.font_size
                )
        else:
            # Draw unwrapped lines.
            first_line = max(0, int(self._scroll_y / lh))
            last_line = min(len(self._lines), int((self._scroll_y + content_h) / lh) + 1)
            for i in range(first_line, last_line):
                line_y = content_y + i * lh - self._scroll_y + self.font_size
                renderer.draw_text(
                    content_x - self._scroll_x, line_y,
                    self._lines[i], self.text_color, self.font_size
                )

        # Cursor
        if self.focused:
            self._update_cursor_blink()
            if self._cursor_visible:
                if self.word_wrap and self._vlines:
                    vrow = self._cursor_visual_row()
                    li, sc, _ec = self._vlines[vrow]
                    cursor_x_px = self._measure_text_width(
                        renderer, self._lines[li][sc:self.cursor_col])
                    cx = content_x + cursor_x_px
                    cy = content_y + vrow * lh - self._scroll_y
                else:
                    cursor_x_px = self._measure_text_width(
                        renderer, self._lines[self.cursor_line][:self.cursor_col])
                    cx = content_x + cursor_x_px - self._scroll_x
                    cy = content_y + self.cursor_line * lh - self._scroll_y
                renderer.draw_rect(cx, cy, 1.5, lh, self.cursor_color)

        renderer.end_clip()

        # Scrollbar
        if has_scrollbar:
            max_sy = self._max_scroll_y()
            viewport_ratio = content_h / self._content_height()
            thumb_h = max(20.0, content_h * viewport_ratio)
            track_h = content_h - thumb_h
            thumb_y = content_y + (track_h * (self._scroll_y / max_sy) if max_sy > 0 else 0)
            sb_x = self.x + self.width - self.scrollbar_width - bw

            color = self.scrollbar_hover_color if (self._scrollbar_hovered or self._dragging_scrollbar) else self.scrollbar_color
            renderer.draw_rect(sb_x, thumb_y, self.scrollbar_width, thumb_h, color, self.scrollbar_width / 2)

    # --- Mouse events ---

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False
        self._scrollbar_hovered = False

    def on_mouse_down(self, event: MouseEvent) -> bool:
        bw = self.border_width
        # Check scrollbar
        if self.show_scrollbar and self._content_height() > self._visible_height():
            sb_x = self.x + self.width - self.scrollbar_width - bw
            if event.x >= sb_x:
                self._dragging_scrollbar = True
                self._drag_start_y = event.y
                self._drag_start_scroll = self._scroll_y
                return True

        # Position cursor
        if self._renderer is not None:
            self.cursor_line, self.cursor_col = self._cursor_pos_from_xy(self._renderer, event.x, event.y)
        self._reset_cursor_blink()
        return True

    def on_mouse_move(self, event: MouseEvent):
        if self._dragging_scrollbar:
            delta_y = event.y - self._drag_start_y
            content_h = self._visible_height()
            viewport_ratio = content_h / self._content_height()
            thumb_h = max(20.0, content_h * viewport_ratio)
            track_h = content_h - thumb_h
            max_sy = self._max_scroll_y()
            if track_h > 0:
                self._scroll_y = self._drag_start_scroll + delta_y * (max_sy / track_h)
                self._scroll_y = max(0.0, min(self._scroll_y, max_sy))
        else:
            # Track scrollbar hover
            bw = self.border_width
            if self.show_scrollbar and self._content_height() > self._visible_height():
                sb_x = self.x + self.width - self.scrollbar_width - bw
                self._scrollbar_hovered = event.x >= sb_x
            else:
                self._scrollbar_hovered = False

    def on_mouse_up(self, event: MouseEvent):
        self._dragging_scrollbar = False

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        max_sy = self._max_scroll_y()
        if max_sy <= 0:
            return False
        self._scroll_y -= event.dy * 30
        self._scroll_y = max(0.0, min(self._scroll_y, max_sy))
        return True

    # --- Focus events ---

    def on_focus(self):
        self.focused = True
        self._reset_cursor_blink()

    def on_blur(self):
        self.focused = False

    # --- Keyboard events ---

    def on_key_down(self, event: KeyEvent) -> bool:
        if self.read_only:
            return False
        from tcbase import Key

        key = event.key
        if key == Key.LEFT:
            if self.cursor_col > 0:
                self.cursor_col -= 1
            elif self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = len(self._lines[self.cursor_line])
            self._reset_cursor_blink()
            self._ensure_cursor_visible()
            return True

        if key == Key.RIGHT:
            if self.cursor_col < len(self._lines[self.cursor_line]):
                self.cursor_col += 1
            elif self.cursor_line < len(self._lines) - 1:
                self.cursor_line += 1
                self.cursor_col = 0
            self._reset_cursor_blink()
            self._ensure_cursor_visible()
            return True

        if key == Key.UP:
            if self.word_wrap and self._vlines:
                vrow = self._cursor_visual_row()
                if vrow > 0:
                    cur_li, cur_sc, _cur_ec = self._vlines[vrow]
                    offset = self.cursor_col - cur_sc
                    prev_li, prev_sc, prev_ec = self._vlines[vrow - 1]
                    self.cursor_line = prev_li
                    self.cursor_col = min(prev_sc + offset, prev_ec)
            elif self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = min(self.cursor_col, len(self._lines[self.cursor_line]))
            self._reset_cursor_blink()
            self._ensure_cursor_visible()
            return True

        if key == Key.DOWN:
            if self.word_wrap and self._vlines:
                vrow = self._cursor_visual_row()
                if vrow < len(self._vlines) - 1:
                    cur_li, cur_sc, _cur_ec = self._vlines[vrow]
                    offset = self.cursor_col - cur_sc
                    next_li, next_sc, next_ec = self._vlines[vrow + 1]
                    self.cursor_line = next_li
                    self.cursor_col = min(next_sc + offset, next_ec)
            elif self.cursor_line < len(self._lines) - 1:
                self.cursor_line += 1
                self.cursor_col = min(self.cursor_col, len(self._lines[self.cursor_line]))
            self._reset_cursor_blink()
            self._ensure_cursor_visible()
            return True

        if key == Key.HOME:
            if self.word_wrap and self._vlines:
                vrow = self._cursor_visual_row()
                _li, sc, _ec = self._vlines[vrow]
                self.cursor_col = sc
            else:
                self.cursor_col = 0
            self._reset_cursor_blink()
            self._ensure_cursor_visible()
            return True

        if key == Key.END:
            if self.word_wrap and self._vlines:
                vrow = self._cursor_visual_row()
                _li, _sc, ec = self._vlines[vrow]
                self.cursor_col = ec
            else:
                self.cursor_col = len(self._lines[self.cursor_line])
            self._reset_cursor_blink()
            self._ensure_cursor_visible()
            return True

        if key == Key.ENTER:
            if self.max_lines > 0 and len(self._lines) >= self.max_lines:
                return True
            line = self._lines[self.cursor_line]
            self._lines[self.cursor_line] = line[:self.cursor_col]
            self._lines.insert(self.cursor_line + 1, line[self.cursor_col:])
            self.cursor_line += 1
            self.cursor_col = 0
            self._invalidate_vlines()
            self._refresh_vlines_if_possible()
            self._fire_on_change()
            self._reset_cursor_blink()
            self._ensure_cursor_visible()
            return True

        if key == Key.BACKSPACE:
            if self.cursor_col > 0:
                line = self._lines[self.cursor_line]
                self._lines[self.cursor_line] = line[:self.cursor_col - 1] + line[self.cursor_col:]
                self.cursor_col -= 1
                self._invalidate_vlines()
                self._refresh_vlines_if_possible()
                self._fire_on_change()
            elif self.cursor_line > 0:
                # Merge with previous line
                prev_len = len(self._lines[self.cursor_line - 1])
                self._lines[self.cursor_line - 1] += self._lines[self.cursor_line]
                del self._lines[self.cursor_line]
                self.cursor_line -= 1
                self.cursor_col = prev_len
                self._invalidate_vlines()
                self._refresh_vlines_if_possible()
                self._fire_on_change()
            self._reset_cursor_blink()
            self._ensure_cursor_visible()
            return True

        if key == Key.DELETE:
            line = self._lines[self.cursor_line]
            if self.cursor_col < len(line):
                self._lines[self.cursor_line] = line[:self.cursor_col] + line[self.cursor_col + 1:]
                self._invalidate_vlines()
                self._refresh_vlines_if_possible()
                self._fire_on_change()
            elif self.cursor_line < len(self._lines) - 1:
                # Merge with next line
                self._lines[self.cursor_line] += self._lines[self.cursor_line + 1]
                del self._lines[self.cursor_line + 1]
                self._invalidate_vlines()
                self._refresh_vlines_if_possible()
                self._fire_on_change()
            self._reset_cursor_blink()
            self._ensure_cursor_visible()
            return True

        return False

    def on_text_input(self, event: TextEvent) -> bool:
        if self.read_only:
            return False
        line = self._lines[self.cursor_line]
        self._lines[self.cursor_line] = line[:self.cursor_col] + event.text + line[self.cursor_col:]
        self.cursor_col += len(event.text)
        self._invalidate_vlines()
        self._refresh_vlines_if_possible()
        self._fire_on_change()
        self._reset_cursor_blink()
        self._ensure_cursor_visible()
        return True

    def _fire_on_change(self):
        if self.on_changed is not None:
            self.on_changed(self.text)
