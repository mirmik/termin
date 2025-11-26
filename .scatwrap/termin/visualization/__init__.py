<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Visualization package providing a minimal rendering stack with pluggable backends.<br>
<br>
The module exposes abstractions for window/context management, scene graphs,<br>
camera models and GPU resources such as meshes, shaders, materials and textures.<br>
&quot;&quot;&quot;<br>
<br>
from .window import Window, GLWindow<br>
from .renderer import Renderer<br>
from .scene import Scene<br>
from .entity import Entity, Component, InputComponent, RenderContext<br>
from .camera import (<br>
    CameraComponent,<br>
    PerspectiveCameraComponent,<br>
    OrthographicCameraComponent,<br>
    OrbitCameraController,<br>
)<br>
from .mesh import MeshDrawable<br>
from .material import Material<br>
from .shader import ShaderProgram<br>
from .texture import Texture<br>
from .components import MeshRenderer<br>
from .ui import Canvas, UIElement, UIRectangle<br>
from .world import VisualizationWorld<br>
from .backends.base import GraphicsBackend, WindowBackend, MouseButton, Key, Action<br>
from .backends.opengl import OpenGLGraphicsBackend<br>
from .backends.glfw import GLFWWindowBackend<br>
from .backends.qt import QtWindowBackend, QtGLWindowHandle<br>
<br>
__all__ = [<br>
    &quot;Window&quot;,<br>
    &quot;GLWindow&quot;,<br>
    &quot;Renderer&quot;,<br>
    &quot;Scene&quot;,<br>
    &quot;Entity&quot;,<br>
    &quot;Component&quot;,<br>
    &quot;InputComponent&quot;,<br>
    &quot;RenderContext&quot;,<br>
    &quot;CameraComponent&quot;,<br>
    &quot;PerspectiveCameraComponent&quot;,<br>
    &quot;OrthographicCameraComponent&quot;,<br>
    &quot;OrbitCameraController&quot;,<br>
    &quot;MeshDrawable&quot;,<br>
    &quot;MeshRenderer&quot;,<br>
    &quot;Canvas&quot;,<br>
    &quot;UIElement&quot;,<br>
    &quot;UIRectangle&quot;,<br>
    &quot;Material&quot;,<br>
    &quot;ShaderProgram&quot;,<br>
    &quot;Texture&quot;,<br>
    &quot;VisualizationWorld&quot;,<br>
    &quot;GraphicsBackend&quot;,<br>
    &quot;WindowBackend&quot;,<br>
    &quot;MouseButton&quot;,<br>
    &quot;Key&quot;,<br>
    &quot;Action&quot;,<br>
    &quot;OpenGLGraphicsBackend&quot;,<br>
    &quot;GLFWWindowBackend&quot;,<br>
    &quot;QtWindowBackend&quot;,<br>
    &quot;QtGLWindowHandle&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
