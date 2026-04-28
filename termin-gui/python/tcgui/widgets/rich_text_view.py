"""Read-only rich text view with a small HTML-subset adapter."""

from __future__ import annotations

from dataclasses import dataclass, replace
from html.parser import HTMLParser
from typing import Iterable

from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.theme import current_theme as _t
from tcgui.widgets.widget import Widget


Color = tuple[float, float, float, float]


@dataclass(frozen=True)
class RichTextStyle:
    color: Color | None = None
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True)
class RichTextSegment:
    text: str
    style: RichTextStyle = RichTextStyle()


RichTextLine = list[RichTextSegment]


def _parse_css_color(value: str) -> Color | None:
    value = value.strip()
    if not value:
        return None
    if value.startswith("#"):
        hex_value = value[1:]
        if len(hex_value) == 3:
            hex_value = "".join(ch * 2 for ch in hex_value)
        if len(hex_value) == 6:
            try:
                r = int(hex_value[0:2], 16) / 255.0
                g = int(hex_value[2:4], 16) / 255.0
                b = int(hex_value[4:6], 16) / 255.0
                return (r, g, b, 1.0)
            except ValueError:
                return None
    return None


def _parse_style_attr(style: str, base: RichTextStyle) -> RichTextStyle:
    result = base
    for part in style.split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "color":
            color = _parse_css_color(value)
            if color is not None:
                result = replace(result, color=color)
        elif key == "font-weight":
            result = replace(result, bold=value.lower() in ("bold", "600", "700", "800", "900"))
        elif key == "font-style":
            result = replace(result, italic=value.lower() == "italic")
    return result


class _RichHtmlParser(HTMLParser):
    """Parser for the tiny rich-text subset used by editor diagnostics."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[RichTextLine] = [[]]
        self._style_stack: list[RichTextStyle] = [RichTextStyle()]

    @property
    def _style(self) -> RichTextStyle:
        return self._style_stack[-1]

    def _push(self, style: RichTextStyle) -> None:
        self._style_stack.append(style)

    def _pop(self) -> None:
        if len(self._style_stack) > 1:
            self._style_stack.pop()

    def _newline(self) -> None:
        self.lines.append([])

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "br":
            self._newline()
            return
        if tag in ("pre", "p"):
            self._push(self._style)
            return
        if tag in ("b", "strong"):
            self._push(replace(self._style, bold=True))
            return
        if tag in ("i", "em"):
            self._push(replace(self._style, italic=True))
            return
        if tag == "span":
            style = self._style
            for key, value in attrs:
                if key is not None and key.lower() == "style" and value is not None:
                    style = _parse_style_attr(value, style)
            self._push(style)
            return
        self._push(self._style)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("br",):
            return
        self._pop()
        if tag == "p":
            self._newline()

    def handle_data(self, data: str) -> None:
        if not data:
            return
        self.lines[-1].append(RichTextSegment(data, self._style))


class RichTextView(Widget):
    """Read-only scrollable rich text view.

    The native model is structured lines/segments. ``set_html`` is a
    compatibility adapter for a deliberately small subset: ``br``, ``pre``,
    ``b``/``strong``, ``i``/``em`` and ``span style=color/font-weight``.
    """

    def __init__(self) -> None:
        super().__init__()
        self.focusable = False

        self.lines: list[RichTextLine] = [[]]
        self.placeholder: str = ""
        self.word_wrap: bool = True

        self.font_size: float = _t.font_size
        self.padding: float = 6.0
        self.border_width: float = 1.0
        self.border_radius: float = _t.border_radius
        self.line_height: float = 0.0

        self.background_color: Color = _t.bg_input
        self.border_color: Color = _t.border
        self.text_color: Color = _t.text_primary
        self.placeholder_color: Color = _t.text_muted

        self.show_scrollbar: bool = True
        self.scrollbar_width: float = 8.0
        self.scrollbar_color: Color = _t.scrollbar
        self.scrollbar_hover_color: Color = _t.scrollbar_hover

        self._scroll_y: float = 0.0
        self._dragging_scrollbar: bool = False
        self._scrollbar_hovered: bool = False
        self._drag_start_y: float = 0.0
        self._drag_start_scroll: float = 0.0
        self._visual_lines: list[RichTextLine] = []
        self._visual_content_w: float = -1.0

    @property
    def text(self) -> str:
        return "\n".join("".join(seg.text for seg in line) for line in self.lines)

    @text.setter
    def text(self, value: str) -> None:
        self.set_text(value)

    def set_text(self, value: str) -> None:
        self.lines = [[RichTextSegment(part)] for part in value.split("\n")] if value else [[]]
        self._invalidate_layout()

    def set_lines(self, lines: Iterable[Iterable[RichTextSegment]]) -> None:
        self.lines = [list(line) for line in lines]
        if not self.lines:
            self.lines = [[]]
        self._invalidate_layout()

    def set_html(self, html: str) -> None:
        parser = _RichHtmlParser()
        parser.feed(html or "")
        parser.close()
        self.lines = parser.lines if parser.lines else [[]]
        self._invalidate_layout()

    def _invalidate_layout(self) -> None:
        self._visual_content_w = -1.0
        self._scroll_y = min(self._scroll_y, self._max_scroll_y())

    def _effective_line_height(self) -> float:
        return self.line_height if self.line_height > 0 else self.font_size * 1.4

    def _visible_height(self) -> float:
        bw = self.border_width
        return max(0.0, self.height - self.padding * 2 - bw * 2)

    def _content_height(self) -> float:
        return len(self._visual_lines or self.lines) * self._effective_line_height()

    def _max_scroll_y(self) -> float:
        return max(0.0, self._content_height() - self._visible_height())

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 300
        h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else 150
        return (w, h)

    def _segment_width(self, renderer, text: str) -> float:
        if not text:
            return 0.0
        w, _ = renderer.measure_text(text, self.font_size)
        return w

    def _line_width(self, renderer, line: RichTextLine) -> float:
        return sum(self._segment_width(renderer, seg.text) for seg in line)

    def _append_to_visual_line(self, visual: RichTextLine, text: str, style: RichTextStyle) -> None:
        if not text:
            return
        if visual and visual[-1].style == style:
            prev = visual[-1]
            visual[-1] = RichTextSegment(prev.text + text, style)
        else:
            visual.append(RichTextSegment(text, style))

    def _wrap_line(self, renderer, line: RichTextLine, max_width: float) -> list[RichTextLine]:
        if not line:
            return [[]]
        if max_width <= 0 or self._line_width(renderer, line) <= max_width:
            return [line]

        rows: list[RichTextLine] = []
        current: RichTextLine = []
        current_w = 0.0

        for seg in line:
            token = ""
            for ch in seg.text:
                token += ch
                if ch not in (" ", "\t"):
                    continue
                current, current_w = self._append_wrapped_token(
                    renderer, rows, current, current_w, token, seg.style, max_width
                )
                token = ""
            if token:
                current, current_w = self._append_wrapped_token(
                    renderer, rows, current, current_w, token, seg.style, max_width
                )

        rows.append(current)
        return rows

    def _append_wrapped_token(
        self,
        renderer,
        rows: list[RichTextLine],
        current: RichTextLine,
        current_w: float,
        token: str,
        style: RichTextStyle,
        max_width: float,
    ) -> tuple[RichTextLine, float]:
        token_w = self._segment_width(renderer, token)
        if current and current_w + token_w > max_width:
            rows.append(current)
            current = []
            current_w = 0.0
        if token_w <= max_width:
            self._append_to_visual_line(current, token, style)
            return current, current_w + token_w

        for ch in token:
            ch_w = self._segment_width(renderer, ch)
            if current and current_w + ch_w > max_width:
                rows.append(current)
                current = []
                current_w = 0.0
            self._append_to_visual_line(current, ch, style)
            current_w += ch_w
        return current, current_w

    def _ensure_visual_lines(self, renderer, content_w: float) -> None:
        if self._visual_content_w == content_w:
            return
        self._visual_lines = []
        if self.word_wrap:
            for line in self.lines:
                self._visual_lines.extend(self._wrap_line(renderer, line, content_w))
        else:
            self._visual_lines = [list(line) for line in self.lines]
        self._visual_content_w = content_w
        self._scroll_y = max(0.0, min(self._scroll_y, self._max_scroll_y()))

    def _style_color(self, style: RichTextStyle) -> Color:
        return style.color if style.color is not None else self.text_color

    def _draw_segment(self, renderer, x: float, y: float, seg: RichTextSegment) -> None:
        color = self._style_color(seg.style)
        draw_x = x + (self.font_size * 0.12 if seg.style.italic else 0.0)
        renderer.draw_text(draw_x, y, seg.text, color, self.font_size)
        if seg.style.bold:
            renderer.draw_text(draw_x + 0.7, y, seg.text, color, self.font_size)

    def render(self, renderer) -> None:
        bw = self.border_width
        renderer.draw_rect(self.x, self.y, self.width, self.height, self.border_color, self.border_radius)
        renderer.draw_rect(
            self.x + bw,
            self.y + bw,
            self.width - bw * 2,
            self.height - bw * 2,
            self.background_color,
            max(0.0, self.border_radius - bw),
        )

        content_x = self.x + self.padding + bw
        content_y = self.y + self.padding + bw
        content_w = self.width - (self.padding + bw) * 2
        content_h = self._visible_height()

        self._ensure_visual_lines(renderer, content_w)
        has_scrollbar = self.show_scrollbar and self._content_height() > content_h
        if has_scrollbar:
            content_w -= self.scrollbar_width
            self._ensure_visual_lines(renderer, content_w)
            has_scrollbar = self.show_scrollbar and self._content_height() > content_h

        lh = self._effective_line_height()
        renderer.begin_clip(content_x, content_y, content_w, content_h)

        if not self.text and self.placeholder:
            renderer.draw_text(
                content_x,
                content_y + self.font_size,
                self.placeholder,
                self.placeholder_color,
                self.font_size,
            )
        else:
            first_line = max(0, int(self._scroll_y / lh))
            last_line = min(len(self._visual_lines), int((self._scroll_y + content_h) / lh) + 1)
            for i in range(first_line, last_line):
                draw_x = content_x
                baseline_y = content_y + i * lh - self._scroll_y + self.font_size
                for seg in self._visual_lines[i]:
                    self._draw_segment(renderer, draw_x, baseline_y, seg)
                    draw_x += self._segment_width(renderer, seg.text)

        renderer.end_clip()

        if has_scrollbar:
            max_sy = self._max_scroll_y()
            viewport_ratio = content_h / self._content_height()
            thumb_h = max(20.0, content_h * viewport_ratio)
            track_h = content_h - thumb_h
            thumb_y = content_y + (track_h * (self._scroll_y / max_sy) if max_sy > 0 else 0.0)
            sb_x = self.x + self.width - self.scrollbar_width - bw
            color = self.scrollbar_hover_color if (self._scrollbar_hovered or self._dragging_scrollbar) else self.scrollbar_color
            renderer.draw_rect(sb_x, thumb_y, self.scrollbar_width, thumb_h, color, self.scrollbar_width / 2)

    def on_mouse_enter(self) -> None:
        self.hovered = True

    def on_mouse_leave(self) -> None:
        self.hovered = False
        self._scrollbar_hovered = False

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if self.show_scrollbar and self._content_height() > self._visible_height():
            sb_x = self.x + self.width - self.scrollbar_width - self.border_width
            if event.x >= sb_x:
                self._dragging_scrollbar = True
                self._drag_start_y = event.y
                self._drag_start_scroll = self._scroll_y
                return True
        return True

    def on_mouse_move(self, event: MouseEvent) -> None:
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
            return

        if self.show_scrollbar and self._content_height() > self._visible_height():
            sb_x = self.x + self.width - self.scrollbar_width - self.border_width
            self._scrollbar_hovered = event.x >= sb_x
        else:
            self._scrollbar_hovered = False

    def on_mouse_up(self, event: MouseEvent) -> None:
        self._dragging_scrollbar = False

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        max_sy = self._max_scroll_y()
        if max_sy <= 0:
            return False
        self._scroll_y -= event.dy * 30.0
        self._scroll_y = max(0.0, min(self._scroll_y, max_sy))
        return True
