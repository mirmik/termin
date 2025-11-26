<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/texture.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Simple 2D texture wrapper for the graphics backend.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from pathlib import Path<br>
from typing import Optional<br>
<br>
import numpy as np<br>
from PIL import Image<br>
from .backends.base import GraphicsBackend, TextureHandle<br>
<br>
<br>
class Texture:<br>
    &quot;&quot;&quot;Loads an image via Pillow and uploads it as ``GL_TEXTURE_2D``.&quot;&quot;&quot;<br>
<br>
    def __init__(self, path: Optional[str | Path] = None):<br>
        self._handles: dict[int | None, TextureHandle] = {}<br>
        self._image_data: Optional[np.ndarray] = None<br>
        self._size: Optional[tuple[int, int]] = None<br>
        if path is not None:<br>
            self.load(path)<br>
<br>
    def load(self, path: str | Path):<br>
        image = Image.open(path).convert(&quot;RGBA&quot;)<br>
        image = image.transpose(Image.FLIP_TOP_BOTTOM)<br>
        data = np.array(image, dtype=np.uint8)<br>
        width, height = image.size<br>
<br>
        self._image_data = data<br>
        self._size = (width, height)<br>
        self._handles.clear()<br>
<br>
    def _ensure_handle(self, graphics: GraphicsBackend, context_key: int | None) -&gt; TextureHandle:<br>
        handle = self._handles.get(context_key)<br>
        if handle is not None:<br>
            return handle<br>
        if self._image_data is None or self._size is None:<br>
            raise RuntimeError(&quot;Texture has no image data to upload.&quot;)<br>
        handle = graphics.create_texture(self._image_data, self._size, channels=4)<br>
        self._handles[context_key] = handle<br>
        return handle<br>
<br>
    def bind(self, graphics: GraphicsBackend, unit: int = 0, context_key: int | None = None):<br>
        handle = self._ensure_handle(graphics, context_key)<br>
        handle.bind(unit)<br>
<br>
    @classmethod<br>
    def from_file(cls, path: str | Path) -&gt; &quot;Texture&quot;:<br>
        tex = cls()<br>
        tex.load(path)<br>
        return tex<br>
<!-- END SCAT CODE -->
</body>
</html>
