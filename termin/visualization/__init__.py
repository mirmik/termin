"""
Visualization package providing a minimal rendering stack with pluggable backends.

The module exposes abstractions for window/context management, scene graphs,
camera models and GPU resources such as meshes, shaders, materials and textures.
"""

from termin.visualization.platform.window import Window, GLWindow
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
from termin.visualization.render.components import MeshRenderer
from termin.visualization.ui import Canvas, UIElement, UIRectangle
from termin.visualization.core.material import Material
from termin.visualization.render.shader import ShaderProgram
from termin.visualization.render.texture import Texture
from termin.visualization.core.world import VisualizationWorld, Visualization
from termin.visualization.platform.backends.base import GraphicsBackend, WindowBackend, MouseButton, Key, Action
from termin.visualization.platform.backends.qt import QtWindowBackend, QtGLWindowHandle

__all__ = [
    "Window",
    "GLWindow",
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
    "Canvas",
    "UIElement",
    "UIRectangle",
    "Material",
    "ShaderProgram",
    "Texture",
    "Visualization",
    "VisualizationWorld",
    "GraphicsBackend",
    "WindowBackend",
    "MouseButton",
    "Key",
    "Action",
    "QtWindowBackend",
    "QtGLWindowHandle",
]
