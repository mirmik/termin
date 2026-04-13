"""OpenGL context management.

The main OpenGLGraphicsBackend is now in C++ (_native module).
This file contains context management for GPU resource cleanup.

Framebuffer handles are now created via:
- OpenGLGraphicsBackend.create_framebuffer(width, height) - for offscreen rendering
- OpenGLGraphicsBackend.create_shadow_framebuffer(width, height) - for shadows
- OpenGLGraphicsBackend.create_external_framebuffer(fbo_id, width, height) - for window FBOs
"""

from __future__ import annotations

from typing import Callable

# --- Context Management ---
# Single context - used for making context current before GPU operations

_make_current_fn: Callable[[], None] | None = None


def register_context(make_current: Callable[[], None]) -> None:
    """Register the context's make_current function."""
    global _make_current_fn
    _make_current_fn = make_current


def get_make_current() -> Callable[[], None] | None:
    """Get the make_current function."""
    return _make_current_fn
