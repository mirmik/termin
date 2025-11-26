<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/__init__.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Backend registry and default implementations.&quot;&quot;&quot;

from __future__ import annotations
from typing import Optional


from .base import (
    Action,
    BackendWindow,
    GraphicsBackend,
    Key,
    MeshHandle,
    MouseButton,
    PolylineHandle,
    ShaderHandle,
    TextureHandle,
    WindowBackend,
    FramebufferHandle,
)
from .nop_graphics import NOPGraphicsBackend
from .nop_window import NOPWindowBackend

from .qt import QtGLWindowHandle
from .opengl import OpenGLGraphicsBackend
from .qt import QtWindowBackend

_default_graphics_backend: Optional[GraphicsBackend] = None
_default_window_backend: Optional[WindowBackend] = None


def set_default_graphics_backend(backend: GraphicsBackend):
    global _default_graphics_backend
    _default_graphics_backend = backend


def get_default_graphics_backend() -&gt; Optional[GraphicsBackend]:
    return _default_graphics_backend


def set_default_window_backend(backend: WindowBackend):
    global _default_window_backend
    _default_window_backend = backend


def get_default_window_backend() -&gt; Optional[WindowBackend]:
    return _default_window_backend


__all__ = [
    &quot;Action&quot;,
    &quot;BackendWindow&quot;,
    &quot;GraphicsBackend&quot;,
    &quot;Key&quot;,
    &quot;MeshHandle&quot;,
    &quot;MouseButton&quot;,
    &quot;PolylineHandle&quot;,
    &quot;ShaderHandle&quot;,
    &quot;TextureHandle&quot;,
    &quot;WindowBackend&quot;,
    &quot;FramebufferHandle&quot;,
    &quot;set_default_graphics_backend&quot;,
    &quot;get_default_graphics_backend&quot;,
    &quot;set_default_window_backend&quot;,
    &quot;get_default_window_backend&quot;,
    &quot;NOPGraphicsBackend&quot;,   # &lt;-- экспортируем
    &quot;NOPWindowBackend&quot;,     # &lt;-- экспортируем
    &quot;QtWindowBackend&quot;,
    &quot;QtGLWindowHandle&quot;,
    &quot;OpenGLGraphicsBackend&quot;,
]

</code></pre>
</body>
</html>
