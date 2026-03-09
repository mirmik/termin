"""Context menu / popup menu widget."""

from __future__ import annotations

from typing import Callable

from tcbase import MouseButton
from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, KeyEvent
from tcgui.widgets.theme import current_theme as _t


class MenuItem:
    """Single menu item descriptor."""

    __slots__ = ("label", "icon", "shortcut", "enabled", "separator", "on_click")

    def __init__(
        self,
        label: str = "",
        *,
        icon: str | None = None,
        shortcut: str | None = None,
        enabled: bool = True,
        separator: bool = False,
        on_click: Callable[[], None] | None = None,
    ):
        self.label = label
        self.icon = icon
        self.shortcut = shortcut
        self.enabled = enabled
        self.separator = separator
        self.on_click = on_click

    @staticmethod
    def sep() -> MenuItem:
        """Convenience factory for a separator."""
        return MenuItem(separator=True)


class Menu(Widget):
    """Popup / context menu widget.

    Usage::

        menu = Menu()
        menu.items = [
            MenuItem("Cut",   shortcut="Ctrl+X", on_click=do_cut),
            MenuItem("Copy",  shortcut="Ctrl+C", on_click=do_copy),
            MenuItem.sep(),
            MenuItem("Paste", shortcut="Ctrl+V", on_click=do_paste),
        ]
        # Assign as context menu:
        widget.context_menu = menu
        # Or show programmatically:
        menu.show(ui, x, y)
    """

    def __init__(self):
        super().__init__()

        self.items: list[MenuItem] = []

        # Style
        self.background_color: tuple[float, float, float, float] = (0.18, 0.18, 0.22, 0.98)
        self.item_hover_color: tuple[float, float, float, float] = _t.hover_subtle
        self.text_color: tuple[float, float, float, float] = _t.text_primary
        self.text_disabled_color: tuple[float, float, float, float] = _t.text_muted
        self.shortcut_color: tuple[float, float, float, float] = _t.text_muted
        self.icon_color: tuple[float, float, float, float] = _t.text_secondary
        self.separator_color: tuple[float, float, float, float] = (0.35, 0.35, 0.4, 0.7)
        self.border_radius: float = _t.border_radius + 1
        self.font_size: float = _t.font_size
        self.icon_width: float = 22.0
        self.item_height: float = 28.0
        self.separator_height: float = 9.0
        self.padding_x: float = 6.0
        self.padding_y: float = 4.0
        self.shortcut_gap: float = 32.0

        # Internal
        self._hovered_index: int = -1

    def add_item(self, item: MenuItem) -> None:
        """Append a menu item."""
        self.items.append(item)

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def _compute_content_size(self) -> tuple[float, float]:
        """Compute required width and height for current items."""
        max_label_w = 0.0
        max_shortcut_w = 0.0
        has_icons = any(it.icon for it in self.items if not it.separator)

        for it in self.items:
            if it.separator:
                continue
            label_w = len(it.label) * self.font_size * 0.6
            if label_w > max_label_w:
                max_label_w = label_w
            if it.shortcut:
                sc_w = len(it.shortcut) * self.font_size * 0.55
                if sc_w > max_shortcut_w:
                    max_shortcut_w = sc_w

        content_w = self.padding_x * 2 + max_label_w
        if has_icons:
            content_w += self.icon_width
        if max_shortcut_w > 0:
            content_w += self.shortcut_gap + max_shortcut_w

        content_h = self.padding_y * 2
        for it in self.items:
            content_h += self.separator_height if it.separator else self.item_height

        return max(content_w, 80.0), content_h

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        return self._compute_content_size()

    # ------------------------------------------------------------------
    # Show / hide via overlay
    # ------------------------------------------------------------------

    def show(self, ui, x: float, y: float):
        """Show this menu as an overlay at (*x*, *y*)."""
        w, h = self._compute_content_size()
        vw = ui._viewport_w
        vh = ui._viewport_h

        # Clamp to viewport
        if x + w > vw:
            x = max(0, vw - w - 2)
        if y + h > vh:
            y = max(0, vh - h - 2)

        self.x = x
        self.y = y
        self.width = w
        self.height = h
        self.layout(x, y, w, h, vw, vh)

        self._hovered_index = -1
        ui.show_overlay(self, dismiss_on_outside=True, on_dismiss=self._on_dismissed)

    def _on_dismissed(self):
        self._hovered_index = -1

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _item_y(self, index: int) -> float:
        """Return the y-offset (from self.y) for item *index*."""
        y = self.padding_y
        for i, it in enumerate(self.items):
            if i == index:
                return y
            y += self.separator_height if it.separator else self.item_height
        return y

    def _index_at(self, y: float) -> int:
        """Return item index at absolute y, or -1."""
        rel = y - self.y
        acc = self.padding_y
        for i, it in enumerate(self.items):
            h = self.separator_height if it.separator else self.item_height
            if acc <= rel < acc + h:
                if it.separator:
                    return -1
                return i
            acc += h
        return -1

    def _has_icons(self) -> bool:
        return any(it.icon for it in self.items if not it.separator)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, renderer):
        # Background
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           self.background_color, self.border_radius)

        has_icons = self._has_icons()
        text_x_offset = self.padding_x + (self.icon_width if has_icons else 0)

        y = self.y + self.padding_y
        for i, it in enumerate(self.items):
            if it.separator:
                sep_y = y + self.separator_height / 2
                renderer.draw_rect(
                    self.x + self.padding_x, sep_y - 0.5,
                    self.width - self.padding_x * 2, 1,
                    self.separator_color,
                )
                y += self.separator_height
                continue

            # Hover highlight
            if i == self._hovered_index and it.enabled:
                renderer.draw_rect(
                    self.x + 2, y,
                    self.width - 4, self.item_height,
                    self.item_hover_color, self.border_radius - 1,
                )

            tc = self.text_color if it.enabled else self.text_disabled_color

            # Icon
            if has_icons and it.icon:
                renderer.draw_text(
                    self.x + self.padding_x,
                    y + self.item_height / 2 + self.font_size * 0.35,
                    it.icon,
                    self.icon_color if it.enabled else self.text_disabled_color,
                    self.font_size,
                )

            # Label
            renderer.draw_text(
                self.x + text_x_offset,
                y + self.item_height / 2 + self.font_size * 0.35,
                it.label, tc, self.font_size,
            )

            # Shortcut
            if it.shortcut:
                sc_w = len(it.shortcut) * self.font_size * 0.55
                renderer.draw_text(
                    self.x + self.width - self.padding_x - sc_w,
                    y + self.item_height / 2 + self.font_size * 0.35,
                    it.shortcut, self.shortcut_color, self.font_size * 0.9,
                )

            y += self.item_height

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def on_mouse_move(self, event: MouseEvent):
        self._hovered_index = self._index_at(event.y)

    def on_mouse_leave(self):
        self._hovered_index = -1

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if event.button != MouseButton.LEFT:
            return True  # consume but ignore non-left clicks
        # Just capture the press — activation happens on mouse_up,
        # same as ToolBar, so blocking callbacks (e.g. file dialogs)
        # don't corrupt SDL mouse state.
        return True

    def on_mouse_up(self, event: MouseEvent):
        idx = self._index_at(event.y)
        callback = None
        if 0 <= idx < len(self.items):
            it = self.items[idx]
            if it.enabled and it.on_click:
                callback = it.on_click
        # Close menu, then invoke callback (may block).
        if self._ui is not None:
            self._ui.hide_overlay(self)
        if callback is not None:
            callback()

    def hit_test(self, px: float, py: float):
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None
        return self

    # ------------------------------------------------------------------
    # Keyboard (optional — arrow navigation inside menu)
    # ------------------------------------------------------------------

    def on_key_down(self, event: KeyEvent) -> bool:
        from tcbase import Key

        key = event.key
        if key == Key.UP:
            self._move_hover(-1)
            return True
        if key == Key.DOWN:
            self._move_hover(1)
            return True
        if key == Key.ENTER:
            callback = None
            if 0 <= self._hovered_index < len(self.items):
                it = self.items[self._hovered_index]
                if it.enabled and it.on_click:
                    callback = it.on_click
            ui = self._ui
            if ui is not None:
                ui.hide_overlay(self)
            if callback is not None:
                if ui is not None:
                    ui.defer(callback)
                else:
                    callback()
            return True
        return False

    def _move_hover(self, direction: int):
        """Move hover index by *direction* (+1 / -1), skipping separators."""
        n = len(self.items)
        if n == 0:
            return
        start = self._hovered_index
        if start < 0:
            start = -1 if direction > 0 else n
        idx = start
        for _ in range(n):
            idx = (idx + direction) % n
            it = self.items[idx]
            if not it.separator and it.enabled:
                self._hovered_index = idx
                return
