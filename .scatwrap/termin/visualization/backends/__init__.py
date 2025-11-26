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
&#9;Action,<br>
&#9;BackendWindow,<br>
&#9;GraphicsBackend,<br>
&#9;Key,<br>
&#9;MeshHandle,<br>
&#9;MouseButton,<br>
&#9;PolylineHandle,<br>
&#9;ShaderHandle,<br>
&#9;TextureHandle,<br>
&#9;WindowBackend,<br>
&#9;FramebufferHandle,<br>
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
&#9;global _default_graphics_backend<br>
&#9;_default_graphics_backend = backend<br>
<br>
<br>
def get_default_graphics_backend() -&gt; Optional[GraphicsBackend]:<br>
&#9;return _default_graphics_backend<br>
<br>
<br>
def set_default_window_backend(backend: WindowBackend):<br>
&#9;global _default_window_backend<br>
&#9;_default_window_backend = backend<br>
<br>
<br>
def get_default_window_backend() -&gt; Optional[WindowBackend]:<br>
&#9;return _default_window_backend<br>
<br>
<br>
__all__ = [<br>
&#9;&quot;Action&quot;,<br>
&#9;&quot;BackendWindow&quot;,<br>
&#9;&quot;GraphicsBackend&quot;,<br>
&#9;&quot;Key&quot;,<br>
&#9;&quot;MeshHandle&quot;,<br>
&#9;&quot;MouseButton&quot;,<br>
&#9;&quot;PolylineHandle&quot;,<br>
&#9;&quot;ShaderHandle&quot;,<br>
&#9;&quot;TextureHandle&quot;,<br>
&#9;&quot;WindowBackend&quot;,<br>
&#9;&quot;FramebufferHandle&quot;,<br>
&#9;&quot;set_default_graphics_backend&quot;,<br>
&#9;&quot;get_default_graphics_backend&quot;,<br>
&#9;&quot;set_default_window_backend&quot;,<br>
&#9;&quot;get_default_window_backend&quot;,<br>
&#9;&quot;NOPGraphicsBackend&quot;,   # &lt;-- экспортируем<br>
&#9;&quot;NOPWindowBackend&quot;,     # &lt;-- экспортируем<br>
&#9;&quot;QtWindowBackend&quot;,<br>
&#9;&quot;QtGLWindowHandle&quot;,<br>
&#9;&quot;OpenGLGraphicsBackend&quot;,<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
