"""MenuBar widget."""

from __future__ import annotations

from tcgui.widgets.widget import Widget
from tcgui.widgets.menu import Menu
from tcgui.widgets.events import MouseEvent, KeyEvent
from tcgui.widgets.theme import current_theme as _t


class MenuBar(Widget):
    """Horizontal menu bar with dropdown menus.

    Usage::

        bar = MenuBar()
        file_menu = Menu()
        file_menu.items = [MenuItem("New", shortcut="Ctrl+N"), ...]
        bar.add_menu("File", file_menu)
    """

    def __init__(self):
        super().__init__()

        self._entries: list[tuple[str, Menu]] = []

        # Style
        self.background_color: tuple[float, float, float, float] = _t.bg_surface
        self.text_color: tuple[float, float, float, float] = _t.text_secondary
        self.hover_text_color: tuple[float, float, float, float] = _t.text_primary
        self.active_text_color: tuple[float, float, float, float] = _t.text_primary
        self.hover_color: tuple[float, float, float, float] = _t.hover_subtle
        self.active_color: tuple[float, float, float, float] = _t.hover
        self.font_size: float = _t.font_size
        self.item_padding_x: float = 10.0
        self.item_padding_y: float = 6.0

        # Internal state
        self._hovered_index: int = -1
        self._active_index: int = -1
        self._menu_open: bool = False
        self._item_rects: list[tuple[float, float, float, float]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_menu(self, label: str, menu: Menu) -> None:
        """Add a dropdown menu with the given title."""
        self._entries.append((label, menu))

    def register_shortcuts(self, ui) -> None:
        """Register keyboard shortcuts for all menu items that have both
        ``shortcut`` and ``on_click`` set.  Call once after the UI is created.
        """
        for _label, menu in self._entries:
            for item in menu.items:
                if item.separator or not item.shortcut or not item.on_click:
                    continue
                ui.add_shortcut_from_string(item.shortcut, item.on_click)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else viewport_w
        h = self.font_size + self.item_padding_y * 2
        if self.preferred_height:
            h = self.preferred_height.to_pixels(viewport_h)
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._compute_item_rects()

    def _compute_item_rects(self):
        self._item_rects = []
        cx = self.x
        for label, _ in self._entries:
            tw = len(label) * self.font_size * 0.6 + self.item_padding_x * 2
            self._item_rects.append((cx, self.y, tw, self.height))
            cx += tw

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, renderer: 'UIRenderer'):
        # Bar background
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           self.background_color)

        for i, ((label, _), (rx, ry, rw, rh)) in enumerate(
                zip(self._entries, self._item_rects)):
            # Item background & text color
            if i == self._active_index and self._menu_open:
                renderer.draw_rect(rx, ry, rw, rh, self.active_color)
                tc = self.active_text_color
            elif i == self._hovered_index:
                renderer.draw_rect(rx, ry, rw, rh, self.hover_color)
                tc = self.hover_text_color
            else:
                tc = self.text_color

            renderer.draw_text_centered(
                rx + rw / 2, ry + rh / 2, label, tc, self.font_size,
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
                return i
        return -1

    # ------------------------------------------------------------------
    # Menu open / close
    # ------------------------------------------------------------------

    def _open_menu(self, index: int):
        """Open the dropdown menu for entry at *index*."""
        if self._ui is None or not (0 <= index < len(self._entries)):
            return
        self._close_menu()

        label, menu = self._entries[index]
        rx, ry, rw, rh = self._item_rects[index]

        # Compute menu size and position
        w, h = menu._compute_content_size()
        vw = self._ui._viewport_w
        vh = self._ui._viewport_h

        mx = rx
        my = ry + rh
        if mx + w > vw:
            mx = max(0, vw - w - 2)
        if my + h > vh:
            my = max(0, ry - h)

        menu.x = mx
        menu.y = my
        menu.width = w
        menu.height = h
        menu.layout(mx, my, w, h, vw, vh)
        menu._hovered_index = -1

        # Patch menu keyboard: Left/Right switch menus
        self._patch_menu_keys(menu)

        self._ui.show_overlay(menu, dismiss_on_outside=True,
                              on_dismiss=self._on_menu_dismissed)
        self._active_index = index
        self._menu_open = True

    def _close_menu(self):
        """Close the currently open menu."""
        if self._menu_open and self._ui is not None:
            if 0 <= self._active_index < len(self._entries):
                _, menu = self._entries[self._active_index]
                self._unpatch_menu_keys(menu)
                self._ui.hide_overlay(menu)
        self._active_index = -1
        self._menu_open = False

    def _on_menu_dismissed(self):
        """Called by overlay system when menu is dismissed externally."""
        if 0 <= self._active_index < len(self._entries):
            _, menu = self._entries[self._active_index]
            self._unpatch_menu_keys(menu)
        self._active_index = -1
        self._menu_open = False

    def _switch_menu(self, direction: int):
        """Switch to adjacent menu entry."""
        if not self._entries:
            return
        new_idx = (self._active_index + direction) % len(self._entries)
        self._open_menu(new_idx)

    # ------------------------------------------------------------------
    # Keyboard patching for Left/Right in open menu
    # ------------------------------------------------------------------

    def _patch_menu_keys(self, menu: Menu):
        """Temporarily override menu.on_key_down to intercept Left/Right."""
        bar = self
        original = type(menu).on_key_down

        def _patched(event: KeyEvent) -> bool:
            from tcbase import Key
            if event.key == Key.LEFT:
                bar._switch_menu(-1)
                return True
            if event.key == Key.RIGHT:
                bar._switch_menu(1)
                return True
            return original(menu, event)

        menu.on_key_down = _patched  # type: ignore[assignment]

    def _unpatch_menu_keys(self, menu: Menu):
        """Restore original on_key_down."""
        if 'on_key_down' in menu.__dict__:
            del menu.on_key_down

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def on_mouse_move(self, event: MouseEvent):
        idx = self._index_at(event.x, event.y)
        self._hovered_index = idx

        # If a menu is open and we hover a different title, switch
        if self._menu_open and idx >= 0 and idx != self._active_index:
            self._open_menu(idx)

    def on_mouse_leave(self):
        self._hovered_index = -1

    def on_mouse_down(self, event: MouseEvent) -> bool:
        idx = self._index_at(event.x, event.y)
        if idx < 0:
            return False

        if self._menu_open and idx == self._active_index:
            self._close_menu()
        else:
            self._open_menu(idx)
        return True
