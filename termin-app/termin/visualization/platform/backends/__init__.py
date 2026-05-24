"""Backend registry — SDL embedded window backend only.

Legacy GraphicsBackend/OpenGLGraphicsBackend/FramebufferHandle/… were
removed with the tgfx→tgfx2 migration. Rendering goes through tgfx2
``Tgfx2Context``/``RenderContext2`` now; window backends live here.
"""

from __future__ import annotations

from tcbase import Action, Key, MouseButton
from tgfx.window import BackendWindow, WindowBackend

# SDL backend using C++ implementation (embedded-mode only; used by
# legacy standalone SDL viewport paths).
from termin.visualization.platform.backends.sdl_embedded import (
    SDLEmbeddedWindowBackend,
)

__all__ = [
    "Action",
    "BackendWindow",
    "Key",
    "MouseButton",
    "WindowBackend",
    "SDLEmbeddedWindowBackend",
]
