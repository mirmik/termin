"""Basic widgets: Label, Button, Checkbox, IconButton, Separator, ImageWidget."""

from __future__ import annotations
import time
from typing import Callable

from termin.visualization.ui.widgets.widget import Widget


class Label(Widget):
    """Text label widget."""

    def __init__(self):
        super().__init__()
        self.text: str = ""
        self.color: tuple[float, float, float, float] = (1, 1, 1, 1)
        self.font_size: float = 14
        self.alignment: str = "left"  # left, center, right

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        # Approximate text size (will be refined when we have font metrics)
        text_width = len(self.text) * self.font_size * 0.6
        text_height = self.font_size * 1.2
        return (text_width, text_height)

    def render(self, renderer: 'UIRenderer'):
        if self.alignment == "center":
            renderer.draw_text_centered(
                self.x + self.width / 2,
                self.y + self.height / 2,
                self.text,
                self.color,
                self.font_size
            )
        elif self.alignment == "right":
            text_width, _ = renderer.measure_text(self.text, self.font_size)
            renderer.draw_text(
                self.x + self.width - text_width,
                self.y + self.font_size,
                self.text,
                self.color,
                self.font_size
            )
        else:  # left
            renderer.draw_text(
                self.x,
                self.y + self.font_size,
                self.text,
                self.color,
                self.font_size
            )


class Button(Widget):
    """Clickable button widget."""

    def __init__(self):
        super().__init__()
        self.text: str = ""
        self.icon: str | None = None

        # Colors
        self.background_color: tuple[float, float, float, float] = (0.3, 0.3, 0.3, 1.0)
        self.hover_color: tuple[float, float, float, float] = (0.4, 0.4, 0.4, 1.0)
        self.pressed_color: tuple[float, float, float, float] = (0.2, 0.2, 0.2, 1.0)
        self.text_color: tuple[float, float, float, float] = (1, 1, 1, 1)
        self.border_radius: float = 3

        # State
        self.hovered: bool = False
        self.pressed: bool = False

        # Callback
        self.on_click: Callable[[], None] | None = None

        # Text settings
        self.font_size: float = 14
        self.padding: float = 10

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        # Size based on text + padding
        text_width = len(self.text) * self.font_size * 0.6
        return (text_width + self.padding * 2, self.font_size + self.padding * 2)

    def render(self, renderer: 'UIRenderer'):
        # Choose color based on state
        if self.pressed:
            color = self.pressed_color
        elif self.hovered:
            color = self.hover_color
        else:
            color = self.background_color

        # Draw background
        renderer.draw_rect(
            self.x, self.y, self.width, self.height,
            color, self.border_radius
        )

        # Draw text centered
        if self.text:
            renderer.draw_text_centered(
                self.x + self.width / 2,
                self.y + self.height / 2,
                self.text,
                self.text_color,
                self.font_size
            )

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False
        self.pressed = False

    def on_mouse_down(self, x: float, y: float) -> bool:
        self.pressed = True
        return True

    def on_mouse_up(self, x: float, y: float):
        if self.pressed and self.contains(x, y):
            if self.on_click:
                self.on_click()
        self.pressed = False


class Checkbox(Widget):
    """Toggle checkbox widget with visual indicator."""

    def __init__(self):
        super().__init__()
        self.text: str = ""
        self.checked: bool = False

        # Colors
        self.box_color: tuple[float, float, float, float] = (0.3, 0.3, 0.3, 1.0)
        self.check_color: tuple[float, float, float, float] = (0.3, 0.8, 0.4, 1.0)
        self.hover_color: tuple[float, float, float, float] = (0.4, 0.4, 0.4, 1.0)
        self.text_color: tuple[float, float, float, float] = (1, 1, 1, 1)
        self.border_radius: float = 3

        # State
        self.hovered: bool = False
        self.pressed: bool = False

        # Callback
        self.on_change: Callable[[bool], None] | None = None

        # Text settings
        self.font_size: float = 14
        self.box_size: float = 18
        self.spacing: float = 6  # space between box and text

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        # Size based on box + text
        text_width = len(self.text) * self.font_size * 0.6 if self.text else 0
        total_width = self.box_size + (self.spacing + text_width if self.text else 0)
        return (total_width, max(self.box_size, self.font_size))

    def render(self, renderer: 'UIRenderer'):
        # Box background color based on state
        if self.hovered:
            box_bg = self.hover_color
        else:
            box_bg = self.box_color

        # Draw checkbox box
        box_y = self.y + (self.height - self.box_size) / 2
        renderer.draw_rect(
            self.x, box_y, self.box_size, self.box_size,
            box_bg, self.border_radius
        )

        # Draw checkmark if checked
        if self.checked:
            # Inner filled rectangle as checkmark indicator
            inset = 4
            renderer.draw_rect(
                self.x + inset, box_y + inset,
                self.box_size - inset * 2, self.box_size - inset * 2,
                self.check_color, self.border_radius - 1
            )

        # Draw text label
        if self.text:
            text_x = self.x + self.box_size + self.spacing
            renderer.draw_text(
                text_x,
                self.y + self.height / 2 + self.font_size / 3,
                self.text,
                self.text_color,
                self.font_size
            )

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False
        self.pressed = False

    def on_mouse_down(self, x: float, y: float) -> bool:
        self.pressed = True
        return True

    def on_mouse_up(self, x: float, y: float):
        if self.pressed and self.contains(x, y):
            self.checked = not self.checked
            if self.on_change:
                self.on_change(self.checked)
        self.pressed = False


class IconButton(Widget):
    """Compact square button with icon/symbol."""

    def __init__(self):
        super().__init__()
        self.icon: str = ""  # Single character or short text as icon
        self.tooltip: str = ""

        # Colors
        self.background_color: tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.9)
        self.hover_color: tuple[float, float, float, float] = (0.35, 0.35, 0.35, 1.0)
        self.pressed_color: tuple[float, float, float, float] = (0.2, 0.2, 0.2, 1.0)
        self.active_color: tuple[float, float, float, float] = (0.3, 0.6, 0.9, 1.0)
        self.icon_color: tuple[float, float, float, float] = (0.9, 0.9, 0.9, 1.0)
        self.border_radius: float = 4

        # State
        self.hovered: bool = False
        self.pressed: bool = False
        self.active: bool = False  # Toggle state for mode buttons

        # Callback
        self.on_click: Callable[[], None] | None = None

        # Size
        self.size: float = 28
        self.font_size: float = 16

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        return (self.size, self.size)

    def render(self, renderer: 'UIRenderer'):
        # Choose color based on state
        if self.pressed:
            color = self.pressed_color
        elif self.active:
            color = self.active_color
        elif self.hovered:
            color = self.hover_color
        else:
            color = self.background_color

        # Draw background
        renderer.draw_rect(
            self.x, self.y, self.width, self.height,
            color, self.border_radius
        )

        # Draw icon centered
        if self.icon:
            renderer.draw_text_centered(
                self.x + self.width / 2,
                self.y + self.height / 2,
                self.icon,
                self.icon_color,
                self.font_size
            )

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False
        self.pressed = False

    def on_mouse_down(self, x: float, y: float) -> bool:
        self.pressed = True
        return True

    def on_mouse_up(self, x: float, y: float):
        if self.pressed and self.contains(x, y):
            if self.on_click:
                self.on_click()
        self.pressed = False


class Separator(Widget):
    """Visual separator line."""

    def __init__(self):
        super().__init__()
        self.orientation: str = "vertical"  # vertical, horizontal
        self.color: tuple[float, float, float, float] = (0.5, 0.5, 0.5, 1.0)
        self.thickness: float = 1
        self.margin: float = 4  # space around separator

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.orientation == "vertical":
            return (self.thickness + self.margin * 2, 0)  # height from parent
        else:
            return (0, self.thickness + self.margin * 2)  # width from parent

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        # Separator takes full extent in the stacking direction
        if self.orientation == "vertical":
            actual_width = self.thickness + self.margin * 2
            super().layout(x, y, actual_width, height, viewport_w, viewport_h)
        else:
            actual_height = self.thickness + self.margin * 2
            super().layout(x, y, width, actual_height, viewport_w, viewport_h)

    def render(self, renderer: 'UIRenderer'):
        if self.orientation == "vertical":
            lx = self.x + self.margin + self.thickness / 2
            renderer.draw_rect(
                lx - self.thickness / 2,
                self.y + self.margin,
                self.thickness,
                self.height - self.margin * 2,
                self.color
            )
        else:
            ly = self.y + self.margin + self.thickness / 2
            renderer.draw_rect(
                self.x + self.margin,
                ly - self.thickness / 2,
                self.width - self.margin * 2,
                self.thickness,
                self.color
            )


class ImageWidget(Widget):
    """Widget that displays an image from a file."""

    def __init__(self):
        super().__init__()
        self.image_path: str = ""
        self.tint: tuple[float, float, float, float] = (1, 1, 1, 1)
        self._texture = None
        self._image_w: int = 0
        self._image_h: int = 0

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        # Use native image size if loaded
        if self._image_w > 0 and self._image_h > 0:
            w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else float(self._image_w)
            h = self.preferred_height.to_pixels(viewport_h) if self.preferred_height else float(self._image_h)
            return (w, h)
        return (64, 64)

    def _ensure_texture(self, renderer: 'UIRenderer'):
        if self._texture is None and self.image_path:
            from PIL import Image
            img = Image.open(self.image_path)
            self._image_w, self._image_h = img.size
            self._texture = renderer.load_image(self.image_path)

    def render(self, renderer: 'UIRenderer'):
        self._ensure_texture(renderer)
        if self._texture is not None:
            renderer.draw_image(
                self.x, self.y, self.width, self.height,
                self._texture, self.tint
            )


class TextInput(Widget):
    """Single-line text input widget."""

    def __init__(self):
        super().__init__()
        self.focusable: bool = True

        # Text content
        self.text: str = ""
        self.placeholder: str = ""
        self.cursor_pos: int = 0

        # Visual configuration
        self.font_size: float = 14
        self.padding: float = 6
        self.border_width: float = 1
        self.border_radius: float = 3
        self.background_color: tuple[float, float, float, float] = (0.15, 0.15, 0.15, 1.0)
        self.focused_background_color: tuple[float, float, float, float] = (0.18, 0.18, 0.22, 1.0)
        self.border_color: tuple[float, float, float, float] = (0.4, 0.4, 0.4, 1.0)
        self.focused_border_color: tuple[float, float, float, float] = (0.3, 0.5, 0.9, 1.0)
        self.text_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)
        self.placeholder_color: tuple[float, float, float, float] = (0.5, 0.5, 0.5, 1.0)
        self.cursor_color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)

        # State
        self.focused: bool = False
        self.hovered: bool = False
        self._scroll_offset: float = 0.0
        self._cursor_blink_time: float = 0.0
        self._cursor_visible: bool = True
        self._renderer: 'UIRenderer | None' = None

        # Callbacks
        self.on_change: Callable[[str], None] | None = None
        self.on_submit: Callable[[str], None] | None = None

    def compute_size(self, viewport_w: float, viewport_h: float) -> tuple[float, float]:
        if self.preferred_width and self.preferred_height:
            return (
                self.preferred_width.to_pixels(viewport_w),
                self.preferred_height.to_pixels(viewport_h)
            )
        w = self.preferred_width.to_pixels(viewport_w) if self.preferred_width else 200
        h = self.font_size + self.padding * 2 + self.border_width * 2
        return (w, h)

    def render(self, renderer: 'UIRenderer'):
        self._renderer = renderer
        bw = self.border_width

        # Border
        border_col = self.focused_border_color if self.focused else self.border_color
        renderer.draw_rect(
            self.x, self.y, self.width, self.height,
            border_col, self.border_radius
        )

        # Background (inset by border)
        bg_color = self.focused_background_color if self.focused else self.background_color
        renderer.draw_rect(
            self.x + bw, self.y + bw,
            self.width - bw * 2, self.height - bw * 2,
            bg_color, max(0, self.border_radius - bw)
        )

        # Text area bounds
        text_x = self.x + self.padding + bw
        text_area_width = self.width - (self.padding + bw) * 2
        text_area_height = self.height - bw * 2
        baseline_y = self.y + bw + self.padding + self.font_size

        # Clip text and cursor to the inner area
        renderer.begin_clip(text_x, self.y + bw, text_area_width, text_area_height)

        if self.text:
            self._update_scroll(renderer, text_area_width)
            renderer.draw_text(
                text_x - self._scroll_offset, baseline_y,
                self.text, self.text_color, self.font_size
            )
        elif not self.focused and self.placeholder:
            renderer.draw_text(
                text_x, baseline_y,
                self.placeholder, self.placeholder_color, self.font_size
            )

        # Cursor
        if self.focused:
            self._update_cursor_blink()
            if self._cursor_visible:
                cursor_px = self._get_cursor_x(renderer)
                cursor_screen_x = text_x + cursor_px - self._scroll_offset
                cursor_y = self.y + bw + self.padding
                renderer.draw_rect(
                    cursor_screen_x, cursor_y,
                    1.5, self.font_size,
                    self.cursor_color
                )

        renderer.end_clip()

    # --- Text measurement helpers ---

    def _measure_text_width(self, renderer: 'UIRenderer', text: str) -> float:
        w, _ = renderer.measure_text(text, self.font_size)
        return w

    def _get_cursor_x(self, renderer: 'UIRenderer') -> float:
        return self._measure_text_width(renderer, self.text[:self.cursor_pos])

    def _update_scroll(self, renderer: 'UIRenderer', text_area_width: float):
        cursor_x = self._get_cursor_x(renderer)
        if cursor_x - self._scroll_offset > text_area_width:
            self._scroll_offset = cursor_x - text_area_width
        if cursor_x - self._scroll_offset < 0:
            self._scroll_offset = cursor_x
        if self._scroll_offset < 0:
            self._scroll_offset = 0

    # --- Cursor blink ---

    def _update_cursor_blink(self):
        now = time.monotonic()
        if now - self._cursor_blink_time >= 0.5:
            self._cursor_visible = not self._cursor_visible
            self._cursor_blink_time = now

    def _reset_cursor_blink(self):
        self._cursor_visible = True
        self._cursor_blink_time = time.monotonic()

    # --- Cursor positioning from click ---

    def _cursor_pos_from_x(self, renderer: 'UIRenderer', click_x: float) -> int:
        text_start_x = self.x + self.padding + self.border_width
        relative_x = click_x - text_start_x + self._scroll_offset
        x_acc = 0.0
        for i, ch in enumerate(self.text):
            char_w = self._measure_text_width(renderer, ch)
            if relative_x < x_acc + char_w / 2:
                return i
            x_acc += char_w
        return len(self.text)

    # --- Mouse events ---

    def on_mouse_enter(self):
        self.hovered = True

    def on_mouse_leave(self):
        self.hovered = False

    def on_mouse_down(self, x: float, y: float) -> bool:
        if self._renderer is not None:
            self.cursor_pos = self._cursor_pos_from_x(self._renderer, x)
        self._reset_cursor_blink()
        return True

    # --- Focus events ---

    def on_focus(self):
        self.focused = True
        self._reset_cursor_blink()

    def on_blur(self):
        self.focused = False

    # --- Keyboard events ---

    def on_key_down(self, key: int, mods: int) -> bool:
        from termin.visualization.platform.backends.base import Key

        if key == Key.BACKSPACE:
            if self.cursor_pos > 0:
                self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
                self.cursor_pos -= 1
                self._fire_on_change()
            self._reset_cursor_blink()
            return True

        if key == Key.DELETE:
            if self.cursor_pos < len(self.text):
                self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos + 1:]
                self._fire_on_change()
            self._reset_cursor_blink()
            return True

        if key == Key.LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
            self._reset_cursor_blink()
            return True

        if key == Key.RIGHT:
            if self.cursor_pos < len(self.text):
                self.cursor_pos += 1
            self._reset_cursor_blink()
            return True

        if key == Key.HOME:
            self.cursor_pos = 0
            self._reset_cursor_blink()
            return True

        if key == Key.END:
            self.cursor_pos = len(self.text)
            self._reset_cursor_blink()
            return True

        if key == Key.ENTER:
            if self.on_submit is not None:
                self.on_submit(self.text)
            return True

        return False

    def on_text_input(self, text: str) -> bool:
        self.text = self.text[:self.cursor_pos] + text + self.text[self.cursor_pos:]
        self.cursor_pos += len(text)
        self._fire_on_change()
        self._reset_cursor_blink()
        return True

    def _fire_on_change(self):
        if self.on_change is not None:
            self.on_change(self.text)
