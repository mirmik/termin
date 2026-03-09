"""Color picker dialog — HSV-based with optional alpha channel."""

from __future__ import annotations

import colorsys
from typing import Callable

import numpy as np

from tcgui.widgets.widget import Widget
from tcgui.widgets.dialog import Dialog
from tcgui.widgets.events import MouseEvent
from tcgui.widgets.theme import current_theme as _t


def _generate_hue_bar(height: int = 180) -> np.ndarray:
    """(height, 1, 4) uint8 — vertical strip of all hues."""
    bar = np.zeros((height, 1, 4), dtype=np.uint8)
    for y in range(height):
        h = y / height
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        bar[y, 0] = [int(r * 255), int(g * 255), int(b * 255), 255]
    return bar


def _generate_sv_rect(hue: float, width: int = 180, height: int = 180) -> np.ndarray:
    """(height, width, 4) uint8 — SV plane for a given hue."""
    s_row = np.linspace(0, 1, width, dtype=np.float32)
    v_col = np.linspace(1, 0, height, dtype=np.float32)
    s_grid, v_grid = np.meshgrid(s_row, v_col)
    h_grid = np.full_like(s_grid, hue)

    # Vectorized HSV→RGB
    hi = (h_grid * 6.0).astype(np.int32) % 6
    f = (h_grid * 6.0) - np.floor(h_grid * 6.0)
    p = v_grid * (1.0 - s_grid)
    q = v_grid * (1.0 - f * s_grid)
    t = v_grid * (1.0 - (1.0 - f) * s_grid)

    r = np.zeros_like(h_grid)
    g = np.zeros_like(h_grid)
    b = np.zeros_like(h_grid)

    mask0 = hi == 0
    mask1 = hi == 1
    mask2 = hi == 2
    mask3 = hi == 3
    mask4 = hi == 4
    mask5 = hi == 5

    r[mask0] = v_grid[mask0]; g[mask0] = t[mask0];      b[mask0] = p[mask0]
    r[mask1] = q[mask1];      g[mask1] = v_grid[mask1];  b[mask1] = p[mask1]
    r[mask2] = p[mask2];      g[mask2] = v_grid[mask2];  b[mask2] = t[mask2]
    r[mask3] = p[mask3];      g[mask3] = q[mask3];       b[mask3] = v_grid[mask3]
    r[mask4] = t[mask4];      g[mask4] = p[mask4];       b[mask4] = v_grid[mask4]
    r[mask5] = v_grid[mask5]; g[mask5] = p[mask5];       b[mask5] = q[mask5]

    rect = np.zeros((height, width, 4), dtype=np.uint8)
    rect[:, :, 0] = (r * 255).astype(np.uint8)
    rect[:, :, 1] = (g * 255).astype(np.uint8)
    rect[:, :, 2] = (b * 255).astype(np.uint8)
    rect[:, :, 3] = 255
    return rect


def _generate_alpha_bar(r: int, g: int, b: int, height: int = 180) -> np.ndarray:
    """(height, 1, 4) uint8 — vertical alpha strip for given RGB."""
    bar = np.zeros((height, 1, 4), dtype=np.uint8)
    for y in range(height):
        a = 1.0 - y / height  # top=255, bottom=0
        # Checkerboard background blended with color
        check = 0.3 if ((y // 8) % 2 == 0) else 0.5
        ar = a * r / 255.0 + (1 - a) * check
        ag = a * g / 255.0 + (1 - a) * check
        ab = a * b / 255.0 + (1 - a) * check
        bar[y, 0] = [int(ar * 255), int(ag * 255), int(ab * 255), 255]
    return bar


class _ColorPickerContent(Widget):
    """Content widget for ColorDialog — SV square, H bar, A bar, preview."""

    SV_SIZE = 180
    BAR_WIDTH = 20
    BAR_GAP = 10
    PREVIEW_HEIGHT = 24
    PREVIEW_GAP = 8
    MARKER_RADIUS = 5

    def __init__(self, initial_rgba: tuple[int, int, int, int],
                 show_alpha: bool = True):
        super().__init__()

        self.show_alpha = show_alpha

        # Initial color → HSV + A
        ri, gi, bi, ai = initial_rgba
        h, s, v = colorsys.rgb_to_hsv(ri / 255.0, gi / 255.0, bi / 255.0)
        self._hue: float = h        # 0..1
        self._sat: float = s        # 0..1
        self._val: float = v        # 0..1
        self._alpha: int = ai       # 0..255

        self._old_rgba = initial_rgba

        # Textures (numpy arrays)
        self._hue_bar = _generate_hue_bar(self.SV_SIZE)
        self._sv_rect = _generate_sv_rect(self._hue, self.SV_SIZE, self.SV_SIZE)
        self._alpha_bar: np.ndarray | None = None
        if show_alpha:
            r, g, b, _ = self._current_rgba()
            self._alpha_bar = _generate_alpha_bar(r, g, b, self.SV_SIZE)

        # GPU texture IDs (created on first render)
        self._sv_tex_id = None
        self._hue_tex_id = None
        self._alpha_tex_id = None

        # Interaction state
        self._dragging: str = ""  # "sv", "hue", "alpha", or ""

        # Computed layout areas (set in layout)
        self._sv_x: float = 0
        self._sv_y: float = 0
        self._hue_x: float = 0
        self._hue_y: float = 0
        self._alpha_x: float = 0
        self._alpha_y: float = 0
        self._preview_x: float = 0
        self._preview_y: float = 0

        # Change callback
        self.on_color_changed: Callable[[], None] | None = None

    def _current_rgba(self) -> tuple[int, int, int, int]:
        r, g, b = colorsys.hsv_to_rgb(self._hue, self._sat, self._val)
        return (int(r * 255), int(g * 255), int(b * 255), self._alpha)

    def get_rgba(self) -> tuple[int, int, int, int]:
        return self._current_rgba()

    def _update_sv_texture(self):
        self._sv_rect = _generate_sv_rect(self._hue, self.SV_SIZE, self.SV_SIZE)
        self._sv_tex_id = None  # force re-upload

    def _update_alpha_texture(self):
        if self.show_alpha:
            r, g, b, _ = self._current_rgba()
            self._alpha_bar = _generate_alpha_bar(r, g, b, self.SV_SIZE)
            self._alpha_tex_id = None

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        w = self.SV_SIZE + self.BAR_GAP + self.BAR_WIDTH
        if self.show_alpha:
            w += self.BAR_GAP + self.BAR_WIDTH
        h = self.SV_SIZE + self.PREVIEW_GAP + self.PREVIEW_HEIGHT + self.PREVIEW_GAP + 14
        return (w, h)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        super().layout(x, y, width, height, viewport_w, viewport_h)
        self._sv_x = x
        self._sv_y = y
        self._hue_x = x + self.SV_SIZE + self.BAR_GAP
        self._hue_y = y
        self._alpha_x = self._hue_x + self.BAR_WIDTH + self.BAR_GAP
        self._alpha_y = y
        self._preview_x = x
        self._preview_y = y + self.SV_SIZE + self.PREVIEW_GAP

    def render(self, renderer):
        # Upload textures on first use
        if self._sv_tex_id is None:
            self._sv_tex_id = renderer.upload_texture(self._sv_rect)
        if self._hue_tex_id is None:
            self._hue_tex_id = renderer.upload_texture(self._hue_bar)
        if self.show_alpha and self._alpha_tex_id is None:
            self._alpha_tex_id = renderer.upload_texture(self._alpha_bar)

        # SV area
        renderer.draw_image(self._sv_x, self._sv_y,
                            self.SV_SIZE, self.SV_SIZE, self._sv_tex_id)
        # SV marker (crosshair)
        mx = self._sv_x + self._sat * self.SV_SIZE
        my = self._sv_y + (1 - self._val) * self.SV_SIZE
        r = self.MARKER_RADIUS
        renderer.draw_rect_outline(mx - r, my - r, r * 2, r * 2,
                                   (1, 1, 1, 0.9), thickness=2)
        renderer.draw_rect_outline(mx - r + 1, my - r + 1, r * 2 - 2, r * 2 - 2,
                                   (0, 0, 0, 0.5), thickness=1)

        # Hue bar
        renderer.draw_image(self._hue_x, self._hue_y,
                            self.BAR_WIDTH, self.SV_SIZE, self._hue_tex_id)
        # Hue marker
        hy = self._hue_y + self._hue * self.SV_SIZE
        renderer.draw_rect(self._hue_x - 1, hy - 2,
                           self.BAR_WIDTH + 2, 4, (1, 1, 1, 0.9))
        renderer.draw_rect_outline(self._hue_x - 1, hy - 2,
                                   self.BAR_WIDTH + 2, 4, (0, 0, 0, 0.5))

        # Alpha bar
        if self.show_alpha and self._alpha_tex_id is not None:
            renderer.draw_image(self._alpha_x, self._alpha_y,
                                self.BAR_WIDTH, self.SV_SIZE, self._alpha_tex_id)
            ay = self._alpha_y + (1 - self._alpha / 255.0) * self.SV_SIZE
            renderer.draw_rect(self._alpha_x - 1, ay - 2,
                               self.BAR_WIDTH + 2, 4, (1, 1, 1, 0.9))
            renderer.draw_rect_outline(self._alpha_x - 1, ay - 2,
                                       self.BAR_WIDTH + 2, 4, (0, 0, 0, 0.5))

        # Preview: old | new
        pw = self.SV_SIZE / 2 - 4
        # Old color
        ro, go, bo, ao = self._old_rgba
        old_c = (ro / 255, go / 255, bo / 255, ao / 255)
        renderer.draw_rect(self._preview_x, self._preview_y,
                           pw, self.PREVIEW_HEIGHT, old_c)
        renderer.draw_rect_outline(self._preview_x, self._preview_y,
                                   pw, self.PREVIEW_HEIGHT, (0.5, 0.5, 0.5, 0.8))

        # New color
        rn, gn, bn, an = self._current_rgba()
        new_c = (rn / 255, gn / 255, bn / 255, an / 255)
        new_x = self._preview_x + pw + 8
        renderer.draw_rect(new_x, self._preview_y,
                           pw, self.PREVIEW_HEIGHT, new_c)
        renderer.draw_rect_outline(new_x, self._preview_y,
                                   pw, self.PREVIEW_HEIGHT, (0.5, 0.5, 0.5, 0.8))

        # Hex label
        hex_str = f"#{rn:02X}{gn:02X}{bn:02X}"
        if self.show_alpha:
            hex_str += f"{an:02X}"
        renderer.draw_text(
            self._preview_x,
            self._preview_y + self.PREVIEW_HEIGHT + self.PREVIEW_GAP + 10,
            hex_str, _t.text_secondary, 12,
        )

    # --- Interaction ---

    def _in_sv(self, x: float, y: float) -> bool:
        return (self._sv_x <= x < self._sv_x + self.SV_SIZE and
                self._sv_y <= y < self._sv_y + self.SV_SIZE)

    def _in_hue(self, x: float, y: float) -> bool:
        return (self._hue_x <= x < self._hue_x + self.BAR_WIDTH and
                self._hue_y <= y < self._hue_y + self.SV_SIZE)

    def _in_alpha(self, x: float, y: float) -> bool:
        if not self.show_alpha:
            return False
        return (self._alpha_x <= x < self._alpha_x + self.BAR_WIDTH and
                self._alpha_y <= y < self._alpha_y + self.SV_SIZE)

    def _apply_sv(self, x: float, y: float):
        self._sat = max(0.0, min(1.0, (x - self._sv_x) / self.SV_SIZE))
        self._val = max(0.0, min(1.0, 1.0 - (y - self._sv_y) / self.SV_SIZE))
        self._update_alpha_texture()
        if self.on_color_changed:
            self.on_color_changed()

    def _apply_hue(self, y: float):
        self._hue = max(0.0, min(1.0, (y - self._hue_y) / self.SV_SIZE))
        self._update_sv_texture()
        self._update_alpha_texture()
        if self.on_color_changed:
            self.on_color_changed()

    def _apply_alpha(self, y: float):
        self._alpha = int(max(0, min(255,
            (1.0 - (y - self._alpha_y) / self.SV_SIZE) * 255)))
        if self.on_color_changed:
            self.on_color_changed()

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if self._in_sv(event.x, event.y):
            self._dragging = "sv"
            self._apply_sv(event.x, event.y)
            return True
        elif self._in_hue(event.x, event.y):
            self._dragging = "hue"
            self._apply_hue(event.y)
            return True
        elif self._in_alpha(event.x, event.y):
            self._dragging = "alpha"
            self._apply_alpha(event.y)
            return True
        return False

    def on_mouse_move(self, event: MouseEvent):
        if self._dragging == "sv":
            self._apply_sv(event.x, event.y)
        elif self._dragging == "hue":
            self._apply_hue(event.y)
        elif self._dragging == "alpha":
            self._apply_alpha(event.y)

    def on_mouse_up(self, event: MouseEvent):
        self._dragging = ""

    def hit_test(self, px: float, py: float) -> Widget | None:
        if not self.visible:
            return None
        if self.contains(px, py):
            return self
        return None


class ColorDialog(Dialog):
    """Color picker dialog with HSV selector and optional alpha.

    Usage::

        ColorDialog.pick_color(ui, initial=(255, 0, 0, 255),
                               on_result=lambda rgba: print(rgba))
    """

    def __init__(self):
        super().__init__()
        self.title = "Color Picker"
        self.buttons = ["OK", "Cancel"]
        self.default_button = "OK"
        self.cancel_button = "Cancel"

        self._picker: _ColorPickerContent | None = None
        self._on_color_result: Callable[[tuple[int, int, int, int] | None], None] | None = None

    @staticmethod
    def pick_color(ui, initial: tuple[int, int, int, int] = (255, 255, 255, 255),
                   *, title: str = "Color Picker",
                   show_alpha: bool = True,
                   on_result: Callable[[tuple[int, int, int, int] | None], None] | None = None):
        """Open a color picker dialog.

        Parameters
        ----------
        ui : UI
            The UI instance to attach the dialog to.
        initial : tuple
            Initial color as (R, G, B, A) each 0-255.
        title : str
            Dialog title.
        show_alpha : bool
            Whether to show the alpha channel bar.
        on_result : callable or None
            Called with ``(r, g, b, a)`` on OK, or ``None`` on Cancel.
        """
        dlg = ColorDialog()
        dlg.title = title
        dlg._on_color_result = on_result

        picker = _ColorPickerContent(initial, show_alpha=show_alpha)
        dlg._picker = picker
        dlg.content = picker
        dlg._built = False  # force rebuild with new content

        def handle_result(button_name):
            if button_name == "OK" and dlg._on_color_result:
                dlg._on_color_result(picker.get_rgba())
            elif button_name == "Cancel" and dlg._on_color_result:
                dlg._on_color_result(None)

        dlg.on_result = handle_result
        dlg.show(ui)
        return dlg
