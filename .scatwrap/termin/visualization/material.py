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
    &quot;&quot;&quot;Collection of shader parameters applied before drawing a mesh.&quot;&quot;&quot;<br>
<br>
    @staticmethod<br>
    def _rgba(vec: Iterable[float]) -&gt; np.ndarray:<br>
        arr = np.asarray(vec, dtype=np.float32)<br>
        if arr.shape != (4,):<br>
            raise ValueError(&quot;Color must be an RGBA quadruplet.&quot;)<br>
        return arr<br>
<br>
    def __init__(<br>
        self,<br>
        shader: ShaderProgram = None,<br>
        color: np.ndarray | None = None,<br>
        textures: Dict[str, Texture] | None = None,<br>
        uniforms: Dict[str, Any] | None = None,<br>
        name: str | None = None,<br>
    ):<br>
        if shader is None:<br>
            shader = ShaderProgram.default_shader()<br>
<br>
        if color is None:<br>
            color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)<br>
        else:<br>
            color = self._rgba(color)<br>
<br>
        self.shader = shader<br>
        self.color = color<br>
        self.textures = textures if textures is not None else {}<br>
        self.uniforms = uniforms if uniforms is not None else {}<br>
        self.name = name<br>
<br>
        if self.uniforms.get(&quot;u_color&quot;) is None:<br>
            self.uniforms[&quot;u_color&quot;] = color<br>
<br>
    def set_param(self, name: str, value: Any):<br>
        &quot;&quot;&quot;Удобный метод задания параметров шейдера.&quot;&quot;&quot;<br>
        self.uniforms[name] = value<br>
<br>
    def update_color(self, rgba):<br>
        rgba = self._rgba(rgba)<br>
        self.color = rgba<br>
        self.uniforms[&quot;u_color&quot;] = rgba<br>
<br>
<br>
    def apply(self, model: np.ndarray, view: np.ndarray, projection: np.ndarray, graphics: GraphicsBackend, context_key: int | None = None):<br>
        &quot;&quot;&quot;Bind shader, upload MVP matrices and all statically defined uniforms.&quot;&quot;&quot;<br>
        self.shader.ensure_ready(graphics)<br>
        self.shader.use()<br>
        self.shader.set_uniform_matrix4(&quot;u_model&quot;, model)<br>
        self.shader.set_uniform_matrix4(&quot;u_view&quot;, view)<br>
        self.shader.set_uniform_matrix4(&quot;u_projection&quot;, projection)<br>
<br>
        texture_slots = enumerate(self.textures.items())<br>
        for unit, (uniform_name, texture) in texture_slots:<br>
            texture.bind(graphics, unit, context_key=context_key)<br>
            self.shader.set_uniform_int(uniform_name, unit)<br>
<br>
        for name, value in self.uniforms.items():<br>
            self.shader.set_uniform_auto(name, value)<br>
<br>
    def serialize(self):<br>
        return {<br>
            &quot;shader&quot;: self.shader.source_path,<br>
            &quot;color&quot;: self.color.tolist(),<br>
            &quot;textures&quot;: {k: tex.source_path for k, tex in self.textures.items()},<br>
            &quot;uniforms&quot;: self.uniforms,<br>
        }<br>
<br>
    @classmethod<br>
    def deserialize(cls, data, context):<br>
        shader = context.load_shader(data[&quot;shader&quot;])<br>
        mat = cls(shader, data[&quot;color&quot;])<br>
        for k, p in data[&quot;textures&quot;].items():<br>
            mat.textures[k] = context.load_texture(p)<br>
        mat.uniforms.update(data[&quot;uniforms&quot;])<br>
        return mat<br>
<!-- END SCAT CODE -->
</body>
</html>
