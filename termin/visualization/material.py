"""Material keeps shader reference and static uniform parameters."""

from __future__ import annotations

from typing import Any, Dict, Iterable

import numpy as np

from .shader import ShaderProgram
from .texture import Texture
from .backends.base import GraphicsBackend


class Material:
    """Collection of shader parameters applied before drawing a mesh."""

    @staticmethod
    def _rgba(vec: Iterable[float]) -> np.ndarray:
        arr = np.asarray(vec, dtype=np.float32)
        if arr.shape != (4,):
            raise ValueError("Color must be an RGBA quadruplet.")
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

        if self.uniforms.get("u_color") is None:
            self.uniforms["u_color"] = color

    def set_param(self, name: str, value: Any):
        """Удобный метод задания параметров шейдера."""
        self.uniforms[name] = value

    def update_color(self, rgba):
        rgba = self._rgba(rgba)
        self.color = rgba
        self.uniforms["u_color"] = rgba


    def apply(self, model: np.ndarray, view: np.ndarray, projection: np.ndarray, graphics: GraphicsBackend, context_key: int | None = None):
        """Bind shader, upload MVP matrices and all statically defined uniforms."""
        self.shader.ensure_ready(graphics)
        self.shader.use()
        self.shader.set_uniform_matrix4("u_model", model)
        self.shader.set_uniform_matrix4("u_view", view)
        self.shader.set_uniform_matrix4("u_projection", projection)

        texture_slots = enumerate(self.textures.items())
        for unit, (uniform_name, texture) in texture_slots:
            texture.bind(graphics, unit, context_key=context_key)
            self.shader.set_uniform_int(uniform_name, unit)

        for name, value in self.uniforms.items():
            self.shader.set_uniform_auto(name, value)

    def serialize(self):
        return {
            "shader": self.shader.source_path,
            "color": self.color.tolist(),
            "textures": {k: tex.source_path for k, tex in self.textures.items()},
            "uniforms": self.uniforms,
        }

    @classmethod
    def deserialize(cls, data, context):
        shader = context.load_shader(data["shader"])
        mat = cls(shader, data["color"])
        for k, p in data["textures"].items():
            mat.textures[k] = context.load_texture(p)
        mat.uniforms.update(data["uniforms"])
        return mat