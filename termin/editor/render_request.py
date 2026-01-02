"""
Global render update request.

Allows components to request viewport redraw from anywhere.
The callback is set by EditorWindow on startup.
"""

from typing import Callable

_request_update_callback: Callable[[], None] | None = None


def set_request_update_callback(callback: Callable[[], None] | None) -> None:
    """Set the global render update callback. Called by EditorWindow."""
    global _request_update_callback
    _request_update_callback = callback


def request_render_update() -> None:
    """Request viewport redraw. Can be called from anywhere."""
    if _request_update_callback is not None:
        _request_update_callback()
