"""ImageWidget widget."""

from __future__ import annotations

from tcgui.widgets.widget import Widget


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
