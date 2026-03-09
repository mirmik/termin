"""ToolBar widget."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.theme import current_theme as _t


class ToolBarItem:
    """Descriptor for a single toolbar item (button or separator)."""

    __slots__ = ("icon", "text", "tooltip", "enabled", "separator", "on_click")

    def __init__(
        self,
        icon: str = "",
        *,
        text: str = "",
        tooltip: str = "",
        enabled: bool = True,
        separator: bool = False,
        on_click: Callable[[], None] | None = None,
    ):
        self.icon = icon
        self.text = text
        self.tooltip = tooltip
        self.enabled = enabled
        self.separator = separator
        self.on_click = on_click

    @staticmethod
    def sep() -> ToolBarItem:
        """Factory for a separator."""
        return ToolBarItem(separator=True)


class ToolBar(Widget):
    """Horizontal toolbar with action buttons and separators.

    Usage::

        tb = ToolBar()
        tb.add_action(icon="\\u2702", tooltip="Cut", on_click=do_cut)
        tb.add_separator()
        tb.add_action(text="Fit", on_click=do_fit)
    """

    def __init__(self):
        super().__init__()

        self.items: list[ToolBarItem] = []

        # Style
        self.background_color: tuple[float, float, float, float] = _t.bg_surface
        self.item_hover_color: tuple[float, float, float, float] = _t.hover_subtle
        self.item_pressed_color: tuple[float, float, float, float] = _t.pressed
        self.icon_color: tuple[float, float, float, float] = _t.text_secondary
        self.icon_hover_color: tuple[float, float, float, float] = _t.text_primary
        self.icon_disabled_color: tuple[float, float, float, float] = _t.text_muted
        self.text_color: tuple[float, float, float, float] = _t.text_secondary
        self.text_hover_color: tuple[float, float, float, float] = _t.text_primary
        self.text_disabled_color: tuple[float, float, float, float] = _t.text_muted
        self.separator_color: tuple[float, float, float, float] = _t.text_muted
        self.border_radius: float = _t.border_radius
        self.font_size: float = _t.font_size
        self.icon_font_size: float = 18.0
        self.item_size: float = 32.0
        self.item_padding: float = 4.0
        self.separator_width: float = 1.0
        self.separator_margin: float = 6.0

        # Internal state
        self._hovered_index: int = -1
        self._pressed_index: int = -1
        self._item_rects: list[tuple[float, float, float, float]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_item(self, item: ToolBarItem) -> None:
        """Append a toolbar item."""
        self.items.append(item)

    def add_action(
        self,
        icon: str = "",
        *,
        text: str = "",
        tooltip: str = "",
        enabled: bool = True,
        on_click: Callable[[], None] | None = None,
    ) -> ToolBarItem:
        """Add an action button and return the item."""
        item = ToolBarItem(
            icon, text=text, tooltip=tooltip, enabled=enabled, on_click=on_click,
        )
        self.items.append(item)
        return item

    def add_separator(self):
        """Add a visual separator."""
        self.items.append(ToolBarItem.sep())

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else viewport_w
        h = self.item_size + self.item_padding * 2
        if self.preferred_height:
            h = self.preferred_height.to_pixels(viewport_h)
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._compute_item_rects()

    def _compute_item_rects(self):
        self._item_rects = []
        cx = self.x + self.item_padding
        iy = self.y + (self.height - self.item_size) / 2

        for item in self.items:
            if item.separator:
                sep_w = self.separator_width + self.separator_margin * 2
                self._item_rects.append((cx, self.y, sep_w, self.height))
                cx += sep_w
            else:
                if item.text and item.icon:
                    text_w = len(item.text) * self.font_size * 0.6
                    iw = self.icon_font_size + 4 + text_w + self.item_padding * 2
                elif item.text:
                    text_w = len(item.text) * self.font_size * 0.6
                    iw = text_w + self.item_padding * 2
                else:
                    iw = self.item_size

                self._item_rects.append((cx, iy, iw, self.item_size))
                cx += iw + self.item_padding

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, renderer: 'UIRenderer'):
        # Bar background
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           self.background_color)

        for i, (item, (rx, ry, rw, rh)) in enumerate(
                zip(self.items, self._item_rects)):
            if item.separator:
                lx = rx + self.separator_margin
                renderer.draw_rect(
                    lx, self.y + self.item_padding * 2,
                    self.separator_width,
                    self.height - self.item_padding * 4,
                    self.separator_color,
                )
                continue

            # Item background
            if i == self._pressed_index and item.enabled:
                renderer.draw_rect(rx, ry, rw, rh,
                                   self.item_pressed_color, self.border_radius)
            elif i == self._hovered_index and item.enabled:
                renderer.draw_rect(rx, ry, rw, rh,
                                   self.item_hover_color, self.border_radius)

            # Colors by state
            if not item.enabled:
                ic = self.icon_disabled_color
                tc = self.text_disabled_color
            elif i == self._hovered_index:
                ic = self.icon_hover_color
                tc = self.text_hover_color
            else:
                ic = self.icon_color
                tc = self.text_color

            # Draw content
            if item.icon and item.text:
                icon_cx = rx + self.item_padding + self.icon_font_size / 2
                renderer.draw_text_centered(
                    icon_cx, ry + rh / 2, item.icon, ic, self.icon_font_size,
                )
                text_x = rx + self.item_padding + self.icon_font_size + 4
                renderer.draw_text(
                    text_x, ry + rh / 2 + self.font_size * 0.35,
                    item.text, tc, self.font_size,
                )
            elif item.icon:
                renderer.draw_text_centered(
                    rx + rw / 2, ry + rh / 2, item.icon, ic, self.icon_font_size,
                )
            elif item.text:
                renderer.draw_text_centered(
                    rx + rw / 2, ry + rh / 2, item.text, tc, self.font_size,
                )

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------

    def hit_test(self, px: float, py: float) -> Widget | None:
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None
        return self

    def _index_at(self, x: float, y: float) -> int:
        for i, (rx, ry, rw, rh) in enumerate(self._item_rects):
            if rx <= x < rx + rw and ry <= y < ry + rh:
                if self.items[i].separator:
                    return -1
                return i
        return -1

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def on_mouse_move(self, event: MouseEvent):
        idx = self._index_at(event.x, event.y)
        if idx != self._hovered_index:
            self._hovered_index = idx
            self.tooltip = self.items[idx].tooltip if idx >= 0 and self.items[idx].tooltip else None

    def on_mouse_leave(self):
        self._hovered_index = -1
        self._pressed_index = -1
        self.tooltip = None

    def on_mouse_down(self, event: MouseEvent) -> bool:
        idx = self._index_at(event.x, event.y)
        if idx >= 0 and self.items[idx].enabled:
            self._pressed_index = idx
            return True
        return False

    def on_mouse_up(self, event: MouseEvent):
        if self._pressed_index >= 0:
            idx = self._pressed_index
            self._pressed_index = -1
            if (self.contains(event.x, event.y)
                    and self._index_at(event.x, event.y) == idx):
                item = self.items[idx]
                if item.enabled and item.on_click:
                    item.on_click()
