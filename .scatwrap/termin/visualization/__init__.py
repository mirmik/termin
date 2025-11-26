<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/__init__.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;
Visualization package providing a minimal rendering stack with pluggable backends.

The module exposes abstractions for window/context management, scene graphs,
camera models and GPU resources such as meshes, shaders, materials and textures.
&quot;&quot;&quot;

from .window import Window, GLWindow
from .renderer import Renderer
from .scene import Scene
from .entity import Entity, Component, InputComponent, RenderContext
from .camera import (
    CameraComponent,
    PerspectiveCameraComponent,
    OrthographicCameraComponent,
    OrbitCameraController,
)
from .mesh import MeshDrawable
from .material import Material
from .shader import ShaderProgram
from .texture import Texture
from .components import MeshRenderer
from .ui import Canvas, UIElement, UIRectangle
from .world import VisualizationWorld
from .backends.base import GraphicsBackend, WindowBackend, MouseButton, Key, Action
from .backends.opengl import OpenGLGraphicsBackend
from .backends.glfw import GLFWWindowBackend
from .backends.qt import QtWindowBackend, QtGLWindowHandle

__all__ = [
    &quot;Window&quot;,
    &quot;GLWindow&quot;,
    &quot;Renderer&quot;,
    &quot;Scene&quot;,
    &quot;Entity&quot;,
    &quot;Component&quot;,
    &quot;InputComponent&quot;,
    &quot;RenderContext&quot;,
    &quot;CameraComponent&quot;,
    &quot;PerspectiveCameraComponent&quot;,
    &quot;OrthographicCameraComponent&quot;,
    &quot;OrbitCameraController&quot;,
    &quot;MeshDrawable&quot;,
    &quot;MeshRenderer&quot;,
    &quot;Canvas&quot;,
    &quot;UIElement&quot;,
    &quot;UIRectangle&quot;,
    &quot;Material&quot;,
    &quot;ShaderProgram&quot;,
    &quot;Texture&quot;,
    &quot;VisualizationWorld&quot;,
    &quot;GraphicsBackend&quot;,
    &quot;WindowBackend&quot;,
    &quot;MouseButton&quot;,
    &quot;Key&quot;,
    &quot;Action&quot;,
    &quot;OpenGLGraphicsBackend&quot;,
    &quot;GLFWWindowBackend&quot;,
    &quot;QtWindowBackend&quot;,
    &quot;QtGLWindowHandle&quot;,
]

</code></pre>
</body>
</html>
