"""
Visualization package providing a minimal rendering stack with pluggable backends.

The module exposes abstractions for window/context management, scene graphs,
camera models and GPU resources such as meshes, shaders, materials and textures.
"""

from termin.visualization.core.scene import Scene
from termin.visualization.core.entity import Entity, Component, InputComponent
from termin.visualization.render.render_context import RenderContext
from termin.visualization.core.input_events import (
    MouseButtonEvent,
    MouseMoveEvent,
    ScrollEvent,
    KeyEvent,
)
from termin.visualization.core.camera import (
    CameraComponent,
    PerspectiveCameraComponent,
    OrthographicCameraComponent,
    OrbitCameraController,
)
from termin.visualization.core.mesh import MeshDrawable
from termin.render_components import MeshRenderer
from termin.visualization.core.material import Material
from tgfx import TcShader
from tgfx.window import WindowBackend
from tcbase import MouseButton, Key, Action
from termin.visualization.render.texture import Texture
from termin.visualization.core.world import VisualizationWorld, Visualization

__all__ = [
    "Renderer",
    "Scene",
    "Entity",
    "Component",
    "InputComponent",
    "RenderContext",
    "MouseButtonEvent",
    "MouseMoveEvent",
    "ScrollEvent",
    "KeyEvent",
    "CameraComponent",
    "PerspectiveCameraComponent",
    "OrthographicCameraComponent",
    "OrbitCameraController",
    "MeshDrawable",
    "MeshRenderer",
    "Material",
    "TcShader",
    "Texture",
    "Visualization",
    "VisualizationWorld",
    "WindowBackend",
    "MouseButton",
    "Key",
    "Action",
]
