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
&#9;&quot;&quot;&quot;<br>
&#9;Минимальная структура данных:<br>
&#9;vertices: (N, 3)<br>
&#9;indices: optional (M,) — индексы для линий; если None, рисуем по порядку<br>
&#9;is_strip: bool — GL_LINE_STRIP или GL_LINES<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;vertices: np.ndarray,<br>
&#9;&#9;&#9;&#9;indices: Optional[np.ndarray] = None,<br>
&#9;&#9;&#9;&#9;is_strip: bool = True):<br>
&#9;&#9;self.vertices = vertices.astype(np.float32)<br>
&#9;&#9;self.indices = indices.astype(np.uint32) if indices is not None else None<br>
&#9;&#9;self.is_strip = is_strip<br>
<br>
<br>
class PolylineDrawable:<br>
&#9;&quot;&quot;&quot;Рисует полилинию из CPU данных.&quot;&quot;&quot;<br>
&#9;<br>
&#9;def __init__(self, polyline: Polyline):<br>
&#9;&#9;self._poly = polyline<br>
&#9;&#9;self._handles: dict[int, PolylineHandle] = {}<br>
<br>
&#9;def upload(self, context: RenderContext):<br>
&#9;&#9;ctx = context.context_key<br>
&#9;&#9;if ctx in self._handles:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;handle = context.graphics.create_polyline(self._poly)<br>
&#9;&#9;self._handles[ctx] = handle<br>
<br>
&#9;def draw(self, context: RenderContext):<br>
&#9;&#9;if context.context_key not in self._handles:<br>
&#9;&#9;&#9;self.upload(context)<br>
&#9;&#9;handle = self._handles[context.context_key]<br>
&#9;&#9;handle.draw()<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;for handle in self._handles.values():<br>
&#9;&#9;&#9;handle.delete()<br>
&#9;&#9;self._handles.clear()<br>
<!-- END SCAT CODE -->
</body>
</html>
