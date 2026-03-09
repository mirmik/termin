"""StatusBar widget."""

from __future__ import annotations

import time

from tcgui.widgets.widget import Widget
from tcgui.widgets.theme import current_theme as _t


class StatusBar(Widget):
    """Horizontal status bar, typically anchored at the bottom.

    Usage::

        bar = StatusBar()
        bar.set_text("Ready | My App")
        bar.show_message("File saved", timeout_ms=3000)
    """

    def __init__(self):
        super().__init__()

        # Persistent text
        self._text: str = "Ready"

        # Temporary message state
        self._temp_text: str | None = None
        self._temp_expire: float = 0.0

        # Style
        self.background_color: tuple[float, float, float, float] = _t.bg_surface
        self.text_color: tuple[float, float, float, float] = _t.text_muted
        self.temp_text_color: tuple[float, float, float, float] = _t.text_secondary
        self.font_size: float = _t.font_size_small
        self.padding_x: float = 8.0
        self.padding_y: float = 4.0
        self.separator_color: tuple[float, float, float, float] = (0.35, 0.35, 0.4, 0.5)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def text(self) -> str:
        """The persistent status text."""
        return self._text

    @text.setter
    def text(self, value: str):
        self._text = value

    def set_text(self, text: str):
        """Set the persistent status text."""
        self._text = text

    def show_message(self, text: str, timeout_ms: int = 3000):
        """Show a temporary message that auto-clears after *timeout_ms*."""
        self._temp_text = text
        self._temp_expire = time.monotonic() + timeout_ms / 1000.0

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else viewport_w
        h = self.font_size + self.padding_y * 2
        if self.preferred_height:
            h = self.preferred_height.to_pixels(viewport_h)
        return (w, h)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, renderer: 'UIRenderer'):
        # Expire temporary message
        if self._temp_text is not None and time.monotonic() >= self._temp_expire:
            self._temp_text = None

        # Background
        renderer.draw_rect(self.x, self.y, self.width, self.height,
                           self.background_color)

        # Top separator line
        renderer.draw_rect(self.x, self.y, self.width, 1, self.separator_color)

        # Text
        if self._temp_text is not None:
            display_text = self._temp_text
            color = self.temp_text_color
        else:
            display_text = self._text
            color = self.text_color

        if display_text:
            renderer.draw_text(
                self.x + self.padding_x,
                self.y + self.height / 2 + self.font_size * 0.35,
                display_text, color, self.font_size,
            )

    # ------------------------------------------------------------------
    # Hit test (passive — no interaction)
    # ------------------------------------------------------------------

    def hit_test(self, px: float, py: float) -> Widget | None:
        if not self.visible:
            return None
        if not self.contains(px, py):
            return None
        return self
