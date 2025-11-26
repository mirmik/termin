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
&#9;CameraComponent,<br>
&#9;PerspectiveCameraComponent,<br>
&#9;OrthographicCameraComponent,<br>
&#9;OrbitCameraController,<br>
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
&#9;&quot;Window&quot;,<br>
&#9;&quot;GLWindow&quot;,<br>
&#9;&quot;Renderer&quot;,<br>
&#9;&quot;Scene&quot;,<br>
&#9;&quot;Entity&quot;,<br>
&#9;&quot;Component&quot;,<br>
&#9;&quot;InputComponent&quot;,<br>
&#9;&quot;RenderContext&quot;,<br>
&#9;&quot;CameraComponent&quot;,<br>
&#9;&quot;PerspectiveCameraComponent&quot;,<br>
&#9;&quot;OrthographicCameraComponent&quot;,<br>
&#9;&quot;OrbitCameraController&quot;,<br>
&#9;&quot;MeshDrawable&quot;,<br>
&#9;&quot;MeshRenderer&quot;,<br>
&#9;&quot;Canvas&quot;,<br>
&#9;&quot;UIElement&quot;,<br>
&#9;&quot;UIRectangle&quot;,<br>
&#9;&quot;Material&quot;,<br>
&#9;&quot;ShaderProgram&quot;,<br>
&#9;&quot;Texture&quot;,<br>
&#9;&quot;VisualizationWorld&quot;,<br>
&#9;&quot;GraphicsBackend&quot;,<br>
&#9;&quot;WindowBackend&quot;,<br>
&#9;&quot;MouseButton&quot;,<br>
&#9;&quot;Key&quot;,<br>
&#9;&quot;Action&quot;,<br>
&#9;&quot;OpenGLGraphicsBackend&quot;,<br>
&#9;&quot;GLFWWindowBackend&quot;,<br>
&#9;&quot;QtWindowBackend&quot;,<br>
&#9;&quot;QtGLWindowHandle&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
