"""Shader wrapper delegating compilation and uniform uploads to a graphics backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from termin.visualization.platform.backends import get_default_graphics_backend
from termin.visualization.platform.backends.base import GraphicsBackend, ShaderHandle


class ShaderCompilationError(RuntimeError):
    """Raised when GLSL compilation or program linking fails."""


class ShaderProgram:
    """A GLSL shader program (vertex + fragment).

    Uniform setters inside the class assume column-major matrices and they set the
    combined MVP transform ``P * V * M`` in homogeneous coordinates.
    """

    def __init__(
        self,
        vertex_source: str,
        fragment_source: str,
        geometry_source: str | None = None,
        source_path: str | None = None,
    ):
        self.vertex_source = vertex_source
        self.fragment_source = fragment_source
        self.geometry_source = geometry_source
        self.source_path: str | None = source_path
        self._compiled = False
        self._handle: ShaderHandle | None = None
        self._backend: GraphicsBackend | None = None

    def __post_init__(self):
        self._handle = None
        self._backend = None

    @staticmethod
    def default_shader() -> "ShaderProgram":
        """
        Deprecated alias kept for обратная совместимость. Реальная реализация находится
        в termin.visualization.render.materials.default_material.default_shader().
        """
        from termin.visualization.render.materials.default_material import default_shader

        return default_shader()

    def ensure_ready(self, graphics: GraphicsBackend | None = None):
        if self._compiled:
            return
        backend = graphics or self._backend or get_default_graphics_backend()
        if backend is None:
            raise RuntimeError("Graphics backend is not available for shader compilation.")
        self._backend = backend

        # Preprocess #include directives
        from termin.visualization.render.glsl_preprocessor import preprocess_glsl, has_includes

        vs = self.vertex_source
        fs = self.fragment_source
        gs = self.geometry_source

        source_name = self.source_path or "<inline>"

        if has_includes(vs):
            vs = preprocess_glsl(vs, f"{source_name}:vertex")
        if has_includes(fs):
            fs = preprocess_glsl(fs, f"{source_name}:fragment")
        if gs is not None and has_includes(gs):
            gs = preprocess_glsl(gs, f"{source_name}:geometry")

        self._handle = backend.create_shader(vs, fs, gs)
        self._compiled = True

    def _require_handle(self) -> ShaderHandle:
        if self._handle is None:
            raise RuntimeError("ShaderProgram is not compiled. Call ensure_ready() first.")
        return self._handle

    def use(self):
        try:
            self._require_handle().use()
        except RuntimeError as e:
            source_name = self.source_path or "<inline>"
            raise RuntimeError(f"Shader '{source_name}': {e}") from e

    def stop(self):
        if self._handle:
            self._handle.stop()

    def delete(self):
        if self._handle:
            self._handle.delete()
            self._handle = None

    def set_uniform_matrix4(self, name: str, matrix: np.ndarray):
        """Upload a 4x4 matrix (float32) to uniform ``name``."""
        self._require_handle().set_uniform_matrix4(name, matrix)

    def set_uniform_vec2(self, name: str, vector: np.ndarray):
        self._require_handle().set_uniform_vec2(name, vector)

    def set_uniform_vec3(self, name: str, vector: np.ndarray):
        self._require_handle().set_uniform_vec3(name, vector)

    def set_uniform_vec4(self, name: str, vector: np.ndarray):
        self._require_handle().set_uniform_vec4(name, vector)

    def set_uniform_float(self, name: str, value: float):
        self._require_handle().set_uniform_float(name, value)

    def set_uniform_int(self, name: str, value: int):
        self._require_handle().set_uniform_int(name, value)

    def set_uniform_matrix4_array(self, name: str, matrices: np.ndarray, count: int):
        """Upload an array of 4x4 matrices to uniform ``name``."""
        self._require_handle().set_uniform_matrix4_array(name, matrices, count)

    def set_uniform_auto(self, name: str, value: Any):
        """Best-effort setter that infers uniform type based on ``value``."""
        if isinstance(value, (list, tuple, np.ndarray)):
            arr = np.asarray(value)
            if arr.shape == (4, 4):
                self.set_uniform_matrix4(name, arr)
            elif arr.shape == (2,):
                self.set_uniform_vec2(name, arr)
            elif arr.shape == (3,):
                self.set_uniform_vec3(name, arr)
            elif arr.shape == (4,):
                self.set_uniform_vec4(name, arr)
            else:
                raise ValueError(f"Unsupported uniform array shape for {name}: {arr.shape}")
        elif isinstance(value, bool):
            self.set_uniform_int(name, int(value))
        elif isinstance(value, int):
            self.set_uniform_int(name, value)
        else:
            self.set_uniform_float(name, float(value))

    @classmethod
    def from_files(cls, vertex_path: str | Path, fragment_path: str | Path) -> "ShaderProgram":
        vertex_source = Path(vertex_path).read_text(encoding="utf-8")
        fragment_source = Path(fragment_path).read_text(encoding="utf-8")
        return cls(vertex_source=vertex_source, fragment_source=fragment_source)

    # ----------------------------------------------------------------
    # Сериализация
    # ----------------------------------------------------------------

    def direct_serialize(self) -> dict:
        """
        Сериализует шейдер в словарь.

        Если source_path задан, возвращает ссылку на файл.
        Иначе сериализует исходники inline.
        """
        if self.source_path is not None:
            return {
                "type": "path",
                "path": self.source_path,
            }

        result: dict = {
            "type": "inline",
            "vertex": self.vertex_source,
            "fragment": self.fragment_source,
        }
        if self.geometry_source is not None:
            result["geometry"] = self.geometry_source
        return result

    @classmethod
    def direct_deserialize(cls, data: dict) -> "ShaderProgram":
        """Десериализует шейдер из словаря."""
        source_path = data.get("path") if data.get("type") == "path" else None
        return cls(
            vertex_source=data["vertex"],
            fragment_source=data["fragment"],
            geometry_source=data.get("geometry"),
            source_path=source_path,
        )
