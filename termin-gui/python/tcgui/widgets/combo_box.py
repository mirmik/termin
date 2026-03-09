"""ComboBox widget."""

from __future__ import annotations
from typing import Callable

from tcbase import MouseButton
from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, MouseWheelEvent
from tcgui.widgets.theme import current_theme as _t


class ComboBox(Widget):
    """Dropdown select widget. Click to open a list of options as overlay."""

    def __init__(self):
        super().__init__()
        self.items: list[str] = []
        self.selected_index: int = -1
        self.placeholder: str = "Select..."

        # Style
        self.background_color: tuple[float, float, float, float] = _t.bg_input
        self.border_color: tuple[float, float, float, float] = _t.border
        self.focused_border_color: tuple[float, float, float, float] = _t.border_focus
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.placeholder_color: tuple[float, float, float, float] = _t.text_muted
        self.arrow_color: tuple[float, float, float, float] = _t.text_secondary
        self.font_size: float = max(10.0, _t.font_size - 2.0)
        self.border_radius: float = _t.border_radius
        self.border_width: float = 1.0
        self.padding: float = 5.0

        # Dropdown style
        self.dropdown_background: tuple[float, float, float, float] = (0.18, 0.18, 0.22, 0.98)
        self.dropdown_item_hover: tuple[float, float, float, float] = _t.hover_subtle
        self.dropdown_max_visible: int = 8
        self.dropdown_item_height: float = 24.0

        # State
        self.hovered: bool = False
        self._open: bool = False
        self._dropdown: Widget | None = None

        # Callback
        self.on_changed: Callable[[int, str], None] | None = None

    @property
    def selected_text(self) -> str:
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return ""

    def clear(self) -> None:
        """Remove all items."""
        self.items = []
        self.selected_index = -1

    def add_item(self, text: str) -> None:
        """Append a single item."""
        self.items.append(text)

    @property
    def item_count(self) -> int:
        return len(self.items)

    def item_text(self, index: int) -> str:
        if 0 <= index < len(self.items):
            return self.items[index]
        return ""

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h),
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 200
        h = self.font_size + self.padding * 2 + self.border_width * 2
        return (w, h)

    def render(self, renderer: 'UIRenderer'):
        bw = self.border_width

        # Border
        bc = self.focused_border_color if self._open else self.border_color
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           bc, self.border_radius)

        # Background
        renderer.draw_rect(self.x + bw, self.y + bw,
                           self.width - bw * 2, self.height - bw * 2,
                           self.background_color, max(0, self.border_radius - bw))

        # Text
        text = self.selected_text or self.placeholder
        tc = self.text_color if self.selected_text else self.placeholder_color
        renderer.draw_text(
            self.x + self.padding + bw,
            self.y + self.height / 2 + self.font_size * 0.35,
            text, tc, self.font_size
        )

        # Arrow indicator
        arrow_x = self.x + self.width - self.padding - bw - 8
        arrow_y = self.y + self.height / 2
        arrow = "\u25BC" if not self._open else "\u25B2"
        renderer.draw_text_centered(arrow_x, arrow_y, arrow,
                                    self.arrow_color, self.font_size * 0.7)

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if event.button != MouseButton.LEFT:
            return False
        if self._open:
            self._close_dropdown()
        else:
            self._open_dropdown()
        return True

    def _open_dropdown(self):
        if not self.items or self._ui is None:
            return

        from tcgui.widgets.containers import Panel

        self._open = True
        n_visible = min(len(self.items), self.dropdown_max_visible)
        dd_height = n_visible * self.dropdown_item_height

        # Build dropdown as a Panel containing a custom _DropdownList
        dropdown = _DropdownList(self)
        dropdown.x = self.x
        dropdown.y = self.y + self.height
        dropdown.width = self.width
        dropdown.height = dd_height

        vw, vh = self._ui._viewport_w, self._ui._viewport_h

        # Flip upward if dropdown would go off-screen
        if dropdown.y + dd_height > vh:
            dropdown.y = self.y - dd_height

        dropdown.layout(dropdown.x, dropdown.y, dropdown.width, dropdown.height, vw, vh)
        self._dropdown = dropdown
        self._ui.show_overlay(dropdown, dismiss_on_outside=True,
                              on_dismiss=self._on_dropdown_closed)

    def _close_dropdown(self):
        if self._dropdown is not None and self._ui is not None:
            self._ui.hide_overlay(self._dropdown)
            # on_dismiss callback handles state reset

    def _on_dropdown_closed(self):
        self._open = False
        self._dropdown = None

    def _select_item(self, index: int):
        if 0 <= index < len(self.items):
            old = self.selected_index
            self.selected_index = index
            if old != index and self.on_changed:
                self.on_changed(index, self.items[index])
        self._close_dropdown()


class _DropdownList(Widget):
    """Internal dropdown list widget for ComboBox overlay."""

    def __init__(self, combo: ComboBox):
        super().__init__()
        self._combo = combo
        self._hovered_index: int = -1
        self._scroll_offset: float = 0.0

    def render(self, renderer: 'UIRenderer'):
        c = self._combo
        # Background
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           c.dropdown_background, c.border_radius)

        renderer.begin_clip(self.x, self.y, self.width, self.height)

        item_h = c.dropdown_item_height
        for i, text in enumerate(c.items):
            iy = self.y + i * item_h - self._scroll_offset
            if iy + item_h < self.y or iy > self.y + self.height:
                continue

            # Hover/selected highlight
            if i == self._hovered_index:
                renderer.draw_rect(self.x, iy, self.width, item_h,
                                   c.dropdown_item_hover, 0)
            elif i == c.selected_index:
                renderer.draw_rect(self.x, iy, self.width, item_h,
                                   (c.dropdown_item_hover[0], c.dropdown_item_hover[1],
                                    c.dropdown_item_hover[2], 0.5), 0)

            renderer.draw_text(
                self.x + c.padding,
                iy + item_h / 2 + c.font_size * 0.35,
                text, c.text_color, c.font_size
            )

        renderer.end_clip()

    def _index_at(self, y: float) -> int:
        rel_y = y - self.y + self._scroll_offset
        idx = int(rel_y / self._combo.dropdown_item_height)
        if 0 <= idx < len(self._combo.items):
            return idx
        return -1

    def on_mouse_move(self, event: MouseEvent):
        self._hovered_index = self._index_at(event.y)

    def on_mouse_leave(self):
        self._hovered_index = -1

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if event.button != MouseButton.LEFT:
            return False
        idx = self._index_at(event.y)
        if idx >= 0:
            self._combo._select_item(idx)
        return True

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        c = self._combo
        total = len(c.items) * c.dropdown_item_height
        max_scroll = max(0.0, total - self.height)
        if max_scroll <= 0:
            return False
        self._scroll_offset -= event.dy * 30
        self._scroll_offset = max(0.0, min(self._scroll_offset, max_scroll))
        return True

    def hit_test(self, px: float, py: float):
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None
        return self
