"""Render context passed to components during rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from termin.visualization.core.camera import Camera
    from termin.visualization.core.scene import Scene
    from termin.visualization.platform.backends.base import GraphicsBackend
    from termin.visualization.render.shader import ShaderProgram


@dataclass
class RenderContext:
    """Data bundle passed to components during rendering."""

    view: np.ndarray
    projection: np.ndarray
    camera: "Camera"
    scene: "Scene"
    context_key: int
    graphics: "GraphicsBackend"
    phase: str = "main"

    # Model матрица — устанавливается пассом перед вызовом Drawable.draw()
    model: np.ndarray | None = None

    # Shadow mapping данные (опционально, заполняется ColorPass)
    shadow_data: "ShadowMapArray | None" = None

    # Currently bound shader program (for skinned mesh uniforms, etc.)
    current_shader: "ShaderProgram | None" = None

    # Extra uniforms to copy when switching to skinned shader variant
    # Keys are uniform names, values are (type, value) tuples
    # Types: "vec3", "float", "int", "mat4"
    extra_uniforms: dict | None = None
