<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/polyline.py</title>
</head>
<body>
<pre><code>
from __future__ import annotations
from typing import Optional

import numpy as np

from .entity import RenderContext
from .backends.base import PolylineHandle


class Polyline:
    &quot;&quot;&quot;
    Минимальная структура данных:
    vertices: (N, 3)
    indices: optional (M,) — индексы для линий; если None, рисуем по порядку
    is_strip: bool — GL_LINE_STRIP или GL_LINES
    &quot;&quot;&quot;
    def __init__(self,
                 vertices: np.ndarray,
                 indices: Optional[np.ndarray] = None,
                 is_strip: bool = True):
        self.vertices = vertices.astype(np.float32)
        self.indices = indices.astype(np.uint32) if indices is not None else None
        self.is_strip = is_strip


class PolylineDrawable:
    &quot;&quot;&quot;Рисует полилинию из CPU данных.&quot;&quot;&quot;
    
    def __init__(self, polyline: Polyline):
        self._poly = polyline
        self._handles: dict[int, PolylineHandle] = {}

    def upload(self, context: RenderContext):
        ctx = context.context_key
        if ctx in self._handles:
            return
        handle = context.graphics.create_polyline(self._poly)
        self._handles[ctx] = handle

    def draw(self, context: RenderContext):
        if context.context_key not in self._handles:
            self.upload(context)
        handle = self._handles[context.context_key]
        handle.draw()

    def delete(self):
        for handle in self._handles.values():
            handle.delete()
        self._handles.clear()

</code></pre>
</body>
</html>
