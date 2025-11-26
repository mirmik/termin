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
&#9;&quot;&quot;&quot;Loads an image via Pillow and uploads it as ``GL_TEXTURE_2D``.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, path: Optional[str | Path] = None):<br>
&#9;&#9;self._handles: dict[int | None, TextureHandle] = {}<br>
&#9;&#9;self._image_data: Optional[np.ndarray] = None<br>
&#9;&#9;self._size: Optional[tuple[int, int]] = None<br>
&#9;&#9;if path is not None:<br>
&#9;&#9;&#9;self.load(path)<br>
<br>
&#9;def load(self, path: str | Path):<br>
&#9;&#9;image = Image.open(path).convert(&quot;RGBA&quot;)<br>
&#9;&#9;image = image.transpose(Image.FLIP_TOP_BOTTOM)<br>
&#9;&#9;data = np.array(image, dtype=np.uint8)<br>
&#9;&#9;width, height = image.size<br>
<br>
&#9;&#9;self._image_data = data<br>
&#9;&#9;self._size = (width, height)<br>
&#9;&#9;self._handles.clear()<br>
<br>
&#9;def _ensure_handle(self, graphics: GraphicsBackend, context_key: int | None) -&gt; TextureHandle:<br>
&#9;&#9;handle = self._handles.get(context_key)<br>
&#9;&#9;if handle is not None:<br>
&#9;&#9;&#9;return handle<br>
&#9;&#9;if self._image_data is None or self._size is None:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;Texture has no image data to upload.&quot;)<br>
&#9;&#9;handle = graphics.create_texture(self._image_data, self._size, channels=4)<br>
&#9;&#9;self._handles[context_key] = handle<br>
&#9;&#9;return handle<br>
<br>
&#9;def bind(self, graphics: GraphicsBackend, unit: int = 0, context_key: int | None = None):<br>
&#9;&#9;handle = self._ensure_handle(graphics, context_key)<br>
&#9;&#9;handle.bind(unit)<br>
<br>
&#9;@classmethod<br>
&#9;def from_file(cls, path: str | Path) -&gt; &quot;Texture&quot;:<br>
&#9;&#9;tex = cls()<br>
&#9;&#9;tex.load(path)<br>
&#9;&#9;return tex<br>
<!-- END SCAT CODE -->
</body>
</html>
