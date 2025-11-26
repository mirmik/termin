<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/polyline.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
from typing import Optional<br>
<br>
import numpy as np<br>
<br>
from .entity import RenderContext<br>
from .backends.base import PolylineHandle<br>
<br>
<br>
class Polyline:<br>
    &quot;&quot;&quot;<br>
    Минимальная структура данных:<br>
    vertices: (N, 3)<br>
    indices: optional (M,) — индексы для линий; если None, рисуем по порядку<br>
    is_strip: bool — GL_LINE_STRIP или GL_LINES<br>
    &quot;&quot;&quot;<br>
    def __init__(self,<br>
                 vertices: np.ndarray,<br>
                 indices: Optional[np.ndarray] = None,<br>
                 is_strip: bool = True):<br>
        self.vertices = vertices.astype(np.float32)<br>
        self.indices = indices.astype(np.uint32) if indices is not None else None<br>
        self.is_strip = is_strip<br>
<br>
<br>
class PolylineDrawable:<br>
    &quot;&quot;&quot;Рисует полилинию из CPU данных.&quot;&quot;&quot;<br>
    <br>
    def __init__(self, polyline: Polyline):<br>
        self._poly = polyline<br>
        self._handles: dict[int, PolylineHandle] = {}<br>
<br>
    def upload(self, context: RenderContext):<br>
        ctx = context.context_key<br>
        if ctx in self._handles:<br>
            return<br>
        handle = context.graphics.create_polyline(self._poly)<br>
        self._handles[ctx] = handle<br>
<br>
    def draw(self, context: RenderContext):<br>
        if context.context_key not in self._handles:<br>
            self.upload(context)<br>
        handle = self._handles[context.context_key]<br>
        handle.draw()<br>
<br>
    def delete(self):<br>
        for handle in self._handles.values():<br>
            handle.delete()<br>
        self._handles.clear()<br>
<!-- END SCAT CODE -->
</body>
</html>
