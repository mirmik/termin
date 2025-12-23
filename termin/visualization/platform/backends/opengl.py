"""OpenGL context management.

The main OpenGLGraphicsBackend is now in C++ (_native module).
This file contains context management for multi-context GPU resource cleanup.

Framebuffer handles are now created via:
- OpenGLGraphicsBackend.create_framebuffer(width, height) - for offscreen rendering
- OpenGLGraphicsBackend.create_shadow_framebuffer(width, height) - for shadows
- OpenGLGraphicsBackend.create_external_framebuffer(fbo_id, width, height) - for window FBOs
"""

from __future__ import annotations

from typing import Callable, Dict

# --- Context Management ---
# Used for switching contexts when deleting GPU resources in multi-context scenarios

_context_registry: Dict[int, Callable[[], None]] = {}
_current_context_key: int | None = None


def register_context(context_key: int, make_current: Callable[[], None]) -> None:
    """Register a context for resource cleanup."""
    global _current_context_key
    _context_registry[context_key] = make_current
    _current_context_key = context_key


def get_context_make_current(context_key: int) -> Callable[[], None] | None:
    """Get make_current function for a context."""
    original = _context_registry.get(context_key)
    if original is None:
        return None

    def wrapped():
        global _current_context_key
        original()
        _current_context_key = context_key

    return wrapped


def get_current_context_key() -> int | None:
    """Get currently active context key."""
    return _current_context_key
