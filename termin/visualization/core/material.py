"""Material keeps shader reference and static uniform parameters."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

import numpy as np

from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.texture import Texture
from termin.visualization.platform.backends.base import GraphicsBackend

if TYPE_CHECKING:
    from termin.visualization.render.renderpass import RenderState


def _rgba(vec: Iterable[float]) -> np.ndarray:
    arr = np.asarray(vec, dtype=np.float32)
    if arr.shape != (4,):
        raise ValueError("Color must be an RGBA quadruplet.")
    return arr


class MaterialPhase:
    """
    Фаза материала: шейдер, состояние рендера и статические параметры.
    """

    def __init__(
        self,
        shader_programm: ShaderProgram,
        render_state: Optional["RenderState"] = None,
        phase_mark: str = "main",
        priority: int = 0,
        color: np.ndarray | None = None,
        textures: Dict[str, Texture] | None = None,
        uniforms: Dict[str, Any] | None = None,
    ):
        if render_state is None:
            from termin.visualization.render.renderpass import RenderState

            render_state = RenderState()
        self.shader_programm = shader_programm
        self.render_state = render_state
        self.phase_mark = phase_mark
        self.priority = int(priority)
        self.color = _rgba(color) if color is not None else None
        self.textures = textures if textures is not None else {}
        self.uniforms = uniforms if uniforms is not None else {}
        if self.color is not None and self.uniforms.get("u_color") is None:
            self.uniforms["u_color"] = self.color

    def set_param(self, name: str, value: Any):
        self.uniforms[name] = value

    def update_color(self, rgba):
        rgba_array = _rgba(rgba)
        self.color = rgba_array
        self.uniforms["u_color"] = rgba_array

    def apply(
        self,
        model: np.ndarray,
        view: np.ndarray,
        projection: np.ndarray,
        graphics: GraphicsBackend,
        context_key: int | None = None,
    ):
        self.shader_programm.ensure_ready(graphics)
        self.shader_programm.use()
        self.shader_programm.set_uniform_matrix4("u_model", model)
        self.shader_programm.set_uniform_matrix4("u_view", view)
        self.shader_programm.set_uniform_matrix4("u_projection", projection)

        texture_slots = enumerate(self.textures.items())
        for unit, (uniform_name, texture) in texture_slots:
            texture.bind(graphics, unit, context_key=context_key)
            self.shader_programm.set_uniform_int(uniform_name, unit)

        for name, value in self.uniforms.items():
            self.shader_programm.set_uniform_auto(name, value)

    def serialize(self):
        return {
            "shader": self.shader_programm.source_path,
            "color": None if self.color is None else self.color.tolist(),
            "textures": {k: tex.source_path for k, tex in self.textures.items()},
            "uniforms": self.uniforms,
            "phase_mark": self.phase_mark,
            "priority": self.priority,
        }


class Material:
    """Collection of shader parameters applied before drawing a mesh."""

    def __init__(
        self,
        shader: ShaderProgram = None,
        color: np.ndarray | None = None,
        textures: Dict[str, Texture] | None = None,
        uniforms: Dict[str, Any] | None = None,
        name: str | None = None,
        render_state: Optional["RenderState"] = None,
        phase_mark: str = "main",
        priority: int = 0,
    ):
        shader = shader or getattr(self, "_pre_shader", None) or getattr(self, "shader", None)
        if shader is None:
            shader = ShaderProgram.default_shader()

        base_color = color if color is not None else getattr(self, "_pre_color", None) or getattr(self, "color", None)
        if base_color is None:
            base_color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        else:
            base_color = _rgba(base_color)

        base_textures = textures if textures is not None else getattr(self, "textures", None)
        base_uniforms = uniforms if uniforms is not None else getattr(self, "uniforms", None)
        self.name = name

        phase = MaterialPhase(
            shader_programm=shader,
            render_state=render_state,
            phase_mark=phase_mark,
            priority=priority,
            color=base_color,
            textures=base_textures,
            uniforms=base_uniforms,
        )
        self.phases: List[MaterialPhase] = [phase]

    @property
    def _default_phase(self) -> MaterialPhase:
        return self.phases[0]

    @property
    def shader(self) -> ShaderProgram:
        return self._default_phase.shader_programm if "phases" in self.__dict__ else self.__dict__.get("_pre_shader")  # type: ignore[return-value]

    @shader.setter
    def shader(self, shader: ShaderProgram):
        if "phases" not in self.__dict__:
            self.__dict__["_pre_shader"] = shader
            return
        self._default_phase.shader_programm = shader

    @property
    def color(self) -> Optional[np.ndarray]:
        if "phases" not in self.__dict__:
            return self.__dict__.get("_pre_color")  # type: ignore[return-value]
        return self._default_phase.color

    @color.setter
    def color(self, rgba: Optional[np.ndarray]):
        if "phases" not in self.__dict__:
            self.__dict__["_pre_color"] = rgba
            return
        if rgba is None:
            self._default_phase.color = None
            self._default_phase.uniforms.pop("u_color", None)
        else:
            self._default_phase.color = _rgba(rgba)
            self._default_phase.uniforms["u_color"] = self._default_phase.color

    @property
    def textures(self) -> Dict[str, Texture]:
        if "phases" not in self.__dict__:
            return self.__dict__.get("_pre_textures", {})  # type: ignore[return-value]
        return self._default_phase.textures

    @textures.setter
    def textures(self, value: Dict[str, Texture]):
        if "phases" not in self.__dict__:
            self.__dict__["_pre_textures"] = value
            return
        self._default_phase.textures = value

    @property
    def uniforms(self) -> Dict[str, Any]:
        if "phases" not in self.__dict__:
            return self.__dict__.get("_pre_uniforms", {})  # type: ignore[return-value]
        return self._default_phase.uniforms

    @uniforms.setter
    def uniforms(self, value: Dict[str, Any]):
        if "phases" not in self.__dict__:
            self.__dict__["_pre_uniforms"] = value
            return
        self._default_phase.uniforms = value

    def set_param(self, name: str, value: Any):
        """Удобный метод задания параметров шейдера."""
        self._default_phase.set_param(name, value)

    def update_color(self, rgba):
        self._default_phase.update_color(rgba)

    def apply(self, model: np.ndarray, view: np.ndarray, projection: np.ndarray, graphics: GraphicsBackend, context_key: int | None = None):
        """Bind shader, upload MVP matrices and all statically defined uniforms."""
        self._default_phase.apply(model, view, projection, graphics, context_key=context_key)

    def serialize(self):
        return {
            "shader": self.shader.source_path,
            "color": None if self.color is None else self.color.tolist(),
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
