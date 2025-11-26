<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/material.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Material keeps shader reference and static uniform parameters.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from typing import Any, Dict, Iterable<br>
<br>
import numpy as np<br>
<br>
from .shader import ShaderProgram<br>
from .texture import Texture<br>
from .backends.base import GraphicsBackend<br>
<br>
<br>
class Material:<br>
&#9;&quot;&quot;&quot;Collection of shader parameters applied before drawing a mesh.&quot;&quot;&quot;<br>
<br>
&#9;@staticmethod<br>
&#9;def _rgba(vec: Iterable[float]) -&gt; np.ndarray:<br>
&#9;&#9;arr = np.asarray(vec, dtype=np.float32)<br>
&#9;&#9;if arr.shape != (4,):<br>
&#9;&#9;&#9;raise ValueError(&quot;Color must be an RGBA quadruplet.&quot;)<br>
&#9;&#9;return arr<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;shader: ShaderProgram = None,<br>
&#9;&#9;color: np.ndarray | None = None,<br>
&#9;&#9;textures: Dict[str, Texture] | None = None,<br>
&#9;&#9;uniforms: Dict[str, Any] | None = None,<br>
&#9;&#9;name: str | None = None,<br>
&#9;):<br>
&#9;&#9;if shader is None:<br>
&#9;&#9;&#9;shader = ShaderProgram.default_shader()<br>
<br>
&#9;&#9;if color is None:<br>
&#9;&#9;&#9;color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;color = self._rgba(color)<br>
<br>
&#9;&#9;self.shader = shader<br>
&#9;&#9;self.color = color<br>
&#9;&#9;self.textures = textures if textures is not None else {}<br>
&#9;&#9;self.uniforms = uniforms if uniforms is not None else {}<br>
&#9;&#9;self.name = name<br>
<br>
&#9;&#9;if self.uniforms.get(&quot;u_color&quot;) is None:<br>
&#9;&#9;&#9;self.uniforms[&quot;u_color&quot;] = color<br>
<br>
&#9;def set_param(self, name: str, value: Any):<br>
&#9;&#9;&quot;&quot;&quot;Удобный метод задания параметров шейдера.&quot;&quot;&quot;<br>
&#9;&#9;self.uniforms[name] = value<br>
<br>
&#9;def update_color(self, rgba):<br>
&#9;&#9;rgba = self._rgba(rgba)<br>
&#9;&#9;self.color = rgba<br>
&#9;&#9;self.uniforms[&quot;u_color&quot;] = rgba<br>
<br>
<br>
&#9;def apply(self, model: np.ndarray, view: np.ndarray, projection: np.ndarray, graphics: GraphicsBackend, context_key: int | None = None):<br>
&#9;&#9;&quot;&quot;&quot;Bind shader, upload MVP matrices and all statically defined uniforms.&quot;&quot;&quot;<br>
&#9;&#9;self.shader.ensure_ready(graphics)<br>
&#9;&#9;self.shader.use()<br>
&#9;&#9;self.shader.set_uniform_matrix4(&quot;u_model&quot;, model)<br>
&#9;&#9;self.shader.set_uniform_matrix4(&quot;u_view&quot;, view)<br>
&#9;&#9;self.shader.set_uniform_matrix4(&quot;u_projection&quot;, projection)<br>
<br>
&#9;&#9;texture_slots = enumerate(self.textures.items())<br>
&#9;&#9;for unit, (uniform_name, texture) in texture_slots:<br>
&#9;&#9;&#9;texture.bind(graphics, unit, context_key=context_key)<br>
&#9;&#9;&#9;self.shader.set_uniform_int(uniform_name, unit)<br>
<br>
&#9;&#9;for name, value in self.uniforms.items():<br>
&#9;&#9;&#9;self.shader.set_uniform_auto(name, value)<br>
<br>
&#9;def serialize(self):<br>
&#9;&#9;return {<br>
&#9;&#9;&#9;&quot;shader&quot;: self.shader.source_path,<br>
&#9;&#9;&#9;&quot;color&quot;: self.color.tolist(),<br>
&#9;&#9;&#9;&quot;textures&quot;: {k: tex.source_path for k, tex in self.textures.items()},<br>
&#9;&#9;&#9;&quot;uniforms&quot;: self.uniforms,<br>
&#9;&#9;}<br>
<br>
&#9;@classmethod<br>
&#9;def deserialize(cls, data, context):<br>
&#9;&#9;shader = context.load_shader(data[&quot;shader&quot;])<br>
&#9;&#9;mat = cls(shader, data[&quot;color&quot;])<br>
&#9;&#9;for k, p in data[&quot;textures&quot;].items():<br>
&#9;&#9;&#9;mat.textures[k] = context.load_texture(p)<br>
&#9;&#9;mat.uniforms.update(data[&quot;uniforms&quot;])<br>
&#9;&#9;return mat<br>
<!-- END SCAT CODE -->
</body>
</html>
