<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/material.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Material keeps shader reference and static uniform parameters.&quot;&quot;&quot;

from __future__ import annotations

from typing import Any, Dict, Iterable

import numpy as np

from .shader import ShaderProgram
from .texture import Texture
from .backends.base import GraphicsBackend


class Material:
    &quot;&quot;&quot;Collection of shader parameters applied before drawing a mesh.&quot;&quot;&quot;

    @staticmethod
    def _rgba(vec: Iterable[float]) -&gt; np.ndarray:
        arr = np.asarray(vec, dtype=np.float32)
        if arr.shape != (4,):
            raise ValueError(&quot;Color must be an RGBA quadruplet.&quot;)
        return arr

    def __init__(
        self,
        shader: ShaderProgram = None,
        color: np.ndarray | None = None,
        textures: Dict[str, Texture] | None = None,
        uniforms: Dict[str, Any] | None = None,
        name: str | None = None,
    ):
        if shader is None:
            shader = ShaderProgram.default_shader()

        if color is None:
            color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        else:
            color = self._rgba(color)

        self.shader = shader
        self.color = color
        self.textures = textures if textures is not None else {}
        self.uniforms = uniforms if uniforms is not None else {}
        self.name = name

        if self.uniforms.get(&quot;u_color&quot;) is None:
            self.uniforms[&quot;u_color&quot;] = color

    def set_param(self, name: str, value: Any):
        &quot;&quot;&quot;Удобный метод задания параметров шейдера.&quot;&quot;&quot;
        self.uniforms[name] = value

    def update_color(self, rgba):
        rgba = self._rgba(rgba)
        self.color = rgba
        self.uniforms[&quot;u_color&quot;] = rgba


    def apply(self, model: np.ndarray, view: np.ndarray, projection: np.ndarray, graphics: GraphicsBackend, context_key: int | None = None):
        &quot;&quot;&quot;Bind shader, upload MVP matrices and all statically defined uniforms.&quot;&quot;&quot;
        self.shader.ensure_ready(graphics)
        self.shader.use()
        self.shader.set_uniform_matrix4(&quot;u_model&quot;, model)
        self.shader.set_uniform_matrix4(&quot;u_view&quot;, view)
        self.shader.set_uniform_matrix4(&quot;u_projection&quot;, projection)

        texture_slots = enumerate(self.textures.items())
        for unit, (uniform_name, texture) in texture_slots:
            texture.bind(graphics, unit, context_key=context_key)
            self.shader.set_uniform_int(uniform_name, unit)

        for name, value in self.uniforms.items():
            self.shader.set_uniform_auto(name, value)

    def serialize(self):
        return {
            &quot;shader&quot;: self.shader.source_path,
            &quot;color&quot;: self.color.tolist(),
            &quot;textures&quot;: {k: tex.source_path for k, tex in self.textures.items()},
            &quot;uniforms&quot;: self.uniforms,
        }

    @classmethod
    def deserialize(cls, data, context):
        shader = context.load_shader(data[&quot;shader&quot;])
        mat = cls(shader, data[&quot;color&quot;])
        for k, p in data[&quot;textures&quot;].items():
            mat.textures[k] = context.load_texture(p)
        mat.uniforms.update(data[&quot;uniforms&quot;])
        return mat
</code></pre>
</body>
</html>
