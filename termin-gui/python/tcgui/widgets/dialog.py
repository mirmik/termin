"""Base dialog widget for modal dialogs."""

from __future__ import annotations

from typing import Callable

from tcbase import Key
from tcgui.widgets.widget import Widget
from tcgui.widgets.events import KeyEvent
from tcgui.widgets.theme import current_theme as _t


class Dialog(Widget):
    """Base modal dialog with title bar, content area, and button bar.

    Can be shown as a modal overlay (:meth:`show`) or in a separate
    native window (``show(ui, windowed=True)``).

    Usage::

        dlg = Dialog()
        dlg.title = "New Project"
        dlg.content = my_form_widget
        dlg.buttons = ["OK", "Cancel"]
        dlg.default_button = "OK"
        dlg.on_result = lambda btn: print(btn)
        dlg.show(ui, windowed=True)
    """

    def __init__(self):
        super().__init__()

        # Configuration
        self.title: str = ""
        self.content: Widget | None = None
        self.buttons: list[str] = ["OK"]
        self.default_button: str | None = None
        self.cancel_button: str | None = None
        self.on_result: Callable[[str], None] | None = None
        self.min_width: float = 300

        # Style
        self.background_color: tuple[float, float, float, float] = _t.bg_surface
        self.title_background_color: tuple[float, float, float, float] = (0.18, 0.18, 0.22, 1.0)
        self.title_text_color: tuple[float, float, float, float] = _t.text_primary
        self.title_font_size: float = _t.font_size + 2
        self.border_radius: float = _t.border_radius + 2
        self.padding: float = 16
        self.button_spacing: float = 8
        self.title_height: float = 36
        self.button_bar_height: float = 44

        # Internal
        self._button_widgets: list = []
        self._built: bool = False
        self._windowed: bool = False
        self._window_ui: object | None = None

    # ------------------------------------------------------------------
    # Build internal widgets
    # ------------------------------------------------------------------

    def _build(self):
        """Create button widgets from configuration."""
        from tcgui.widgets.button import Button

        for btn in self._button_widgets:
            self.remove_child(btn)
        self._button_widgets.clear()

        for btn_text in self.buttons:
            btn = Button()
            btn.text = btn_text
            btn.font_size = _t.font_size
            btn.padding = 8
            if btn_text == self.default_button:
                btn.background_color = _t.accent
            btn.on_click = (lambda t: lambda: self._on_button_click(t))(btn_text)
            self._button_widgets.append(btn)

        self._built = True

    def _on_button_click(self, button_name: str):
        if self.on_result:
            self.on_result(button_name)
        self.close()

    # ------------------------------------------------------------------
    # Show / close
    # ------------------------------------------------------------------

    def show(self, ui, windowed: bool = False) -> None:
        """Show this dialog as a modal overlay or in a separate window.

        When *windowed* is True and ``ui.create_window`` is available,
        the dialog opens in its own native window.  Otherwise it falls
        back to the normal centered-overlay behaviour.
        """
        if not self._built:
            self._build()
        self._ensure_children()

        if windowed and ui.create_window is not None:
            vw = ui._viewport_w or 800
            vh = ui._viewport_h or 600
            nat_w, nat_h = self._compute_natural_size(vw, vh)
            # Window doesn't need internal title bar — OS provides one.
            win_h = nat_h - self.title_height + self.padding
            window_ui = ui.create_window(self.title, int(nat_w), int(win_h))
            if window_ui is not None:
                self._windowed = True
                self._window_ui = window_ui
                self._ui = window_ui
                window_ui.root = self
                return

        # Fallback: overlay in the current UI.
        self._ui = ui
        vw = ui._viewport_w
        vh = ui._viewport_h
        w, h = self.compute_size(vw, vh)

        x = (vw - w) / 2
        y = (vh - h) / 2
        self.layout(x, y, w, h, vw, vh)

        ui.show_overlay(self, modal=True, dismiss_on_outside=False,
                        on_dismiss=self._on_overlay_dismissed)

    def close(self) -> None:
        """Close the dialog (overlay or window)."""
        if self._windowed and self._window_ui is not None:
            window_ui = self._window_ui
            self._window_ui = None
            self._windowed = False
            window_ui.root = None  # triggers on_empty → window destroyed
        elif self._ui is not None:
            self._ui.hide_overlay(self)

    def _on_overlay_dismissed(self):
        """Called when ESC closes this overlay."""
        if self.cancel_button and self.on_result:
            self.on_result(self.cancel_button)

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def _compute_natural_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        """Compute size based on content (always includes title bar)."""
        content_w, content_h = 0.0, 0.0
        if self.content is not None:
            content_w, content_h = self.content.compute_size(viewport_w, viewport_h)

        btn_total_w = 0.0
        for btn in self._button_widgets:
            bw, _ = btn.compute_size(viewport_w, viewport_h)
            btn_total_w += bw
        if self._button_widgets:
            btn_total_w += self.button_spacing * (len(self._button_widgets) - 1)

        w = max(self.min_width, content_w + self.padding * 2,
                btn_total_w + self.padding * 2)
        h = self.title_height + content_h + self.padding + self.button_bar_height

        if self.preferred_width:
            w = self.preferred_width.to_pixels(viewport_w)
        if self.preferred_height:
            h = self.preferred_height.to_pixels(viewport_h)

        return (w, h)

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self._windowed:
            return (viewport_w, viewport_h)
        return self._compute_natural_size(viewport_w, viewport_h)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._ensure_children()

        # Content area
        if self.content is not None:
            cx = x + self.padding
            cw = width - self.padding * 2
            if self._windowed:
                cy = y + self.padding
                ch = height - self.padding * 2 - self.button_bar_height
            else:
                cy = y + self.title_height
                _, ch = self.content.compute_size(viewport_w, viewport_h)
            self.content.layout(cx, cy, cw, ch, viewport_w, viewport_h)

        # Buttons: right-aligned at bottom
        btn_y = y + height - self.button_bar_height
        btn_sizes = []
        total_btn_w = 0.0
        for btn in self._button_widgets:
            bw, bh = btn.compute_size(viewport_w, viewport_h)
            btn_sizes.append((bw, bh))
            total_btn_w += bw
        if self._button_widgets:
            total_btn_w += self.button_spacing * (len(self._button_widgets) - 1)

        btn_x = x + width - self.padding - total_btn_w
        for btn, (bw, bh) in zip(self._button_widgets, btn_sizes):
            by = btn_y + (self.button_bar_height - bh) / 2
            btn.layout(btn_x, by, bw, bh, viewport_w, viewport_h)
            btn_x += bw + self.button_spacing

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, renderer: 'UIRenderer'):
        # Background
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           self.background_color,
                           0 if self._windowed else self.border_radius)

        # Title bar (overlay mode only — windowed has OS title bar)
        if not self._windowed:
            renderer.draw_rect(self.x, self.y, self.width, self.title_height,
                               self.title_background_color, self.border_radius)
            if self.title_height < self.height:
                renderer.draw_rect(
                    self.x, self.y + self.title_height - self.border_radius,
                    self.width, self.border_radius,
                    self.title_background_color,
                )
            if self.title:
                renderer.draw_text(
                    self.x + self.padding,
                    self.y + self.title_height / 2 + self.title_font_size * 0.35,
                    self.title, self.title_text_color, self.title_font_size,
                )

        # Content
        if self.content is not None:
            self.content.render(renderer)

        # Buttons
        for btn in self._button_widgets:
            btn.render(renderer)

    def _ensure_children(self):
        if self.content is not None:
            if self.content.parent is not self:
                if self.content.parent is not None:
                    self.content.parent.remove_child(self.content)
                self.add_child(self.content)
        for btn in self._button_widgets:
            if btn.parent is not self:
                if btn.parent is not None:
                    btn.parent.remove_child(btn)
                self.add_child(btn)

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------

    def hit_test(self, px: float, py: float) -> Widget | None:
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None

        # Buttons
        for btn in self._button_widgets:
            hit = btn.hit_test(px, py)
            if hit:
                return hit

        # Content (may have interactive children)
        if self.content is not None:
            hit = self.content.hit_test(px, py)
            if hit:
                return hit

        return self

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def on_key_down(self, event: KeyEvent) -> bool:
        if event.key == Key.ENTER and self.default_button:
            self._on_button_click(self.default_button)
            return True
        if event.key == Key.ESCAPE and self.cancel_button and self._windowed:
            self._on_button_click(self.cancel_button)
            return True
        return False
