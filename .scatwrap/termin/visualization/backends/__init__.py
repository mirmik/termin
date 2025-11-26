<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Backend registry and default implementations.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
from typing import Optional<br>
<br>
<br>
from .base import (<br>
    Action,<br>
    BackendWindow,<br>
    GraphicsBackend,<br>
    Key,<br>
    MeshHandle,<br>
    MouseButton,<br>
    PolylineHandle,<br>
    ShaderHandle,<br>
    TextureHandle,<br>
    WindowBackend,<br>
    FramebufferHandle,<br>
)<br>
from .nop_graphics import NOPGraphicsBackend<br>
from .nop_window import NOPWindowBackend<br>
<br>
from .qt import QtGLWindowHandle<br>
from .opengl import OpenGLGraphicsBackend<br>
from .qt import QtWindowBackend<br>
<br>
_default_graphics_backend: Optional[GraphicsBackend] = None<br>
_default_window_backend: Optional[WindowBackend] = None<br>
<br>
<br>
def set_default_graphics_backend(backend: GraphicsBackend):<br>
    global _default_graphics_backend<br>
    _default_graphics_backend = backend<br>
<br>
<br>
def get_default_graphics_backend() -&gt; Optional[GraphicsBackend]:<br>
    return _default_graphics_backend<br>
<br>
<br>
def set_default_window_backend(backend: WindowBackend):<br>
    global _default_window_backend<br>
    _default_window_backend = backend<br>
<br>
<br>
def get_default_window_backend() -&gt; Optional[WindowBackend]:<br>
    return _default_window_backend<br>
<br>
<br>
__all__ = [<br>
    &quot;Action&quot;,<br>
    &quot;BackendWindow&quot;,<br>
    &quot;GraphicsBackend&quot;,<br>
    &quot;Key&quot;,<br>
    &quot;MeshHandle&quot;,<br>
    &quot;MouseButton&quot;,<br>
    &quot;PolylineHandle&quot;,<br>
    &quot;ShaderHandle&quot;,<br>
    &quot;TextureHandle&quot;,<br>
    &quot;WindowBackend&quot;,<br>
    &quot;FramebufferHandle&quot;,<br>
    &quot;set_default_graphics_backend&quot;,<br>
    &quot;get_default_graphics_backend&quot;,<br>
    &quot;set_default_window_backend&quot;,<br>
    &quot;get_default_window_backend&quot;,<br>
    &quot;NOPGraphicsBackend&quot;,   # &lt;-- экспортируем<br>
    &quot;NOPWindowBackend&quot;,     # &lt;-- экспортируем<br>
    &quot;QtWindowBackend&quot;,<br>
    &quot;QtGLWindowHandle&quot;,<br>
    &quot;OpenGLGraphicsBackend&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
