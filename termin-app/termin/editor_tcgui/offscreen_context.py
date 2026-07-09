"""Legacy offscreen GL context placeholder.

The tcgui editor now runs through ``termin.display.SDLBackendWindow`` and
tgfx2-owned offscreen surfaces. The old PySDL2-created hidden GL context is no
longer a supported runtime path.
"""

from __future__ import annotations


class OffscreenContext:
    """Deprecated dedicated offscreen GL context for rendering."""

    CONTEXT_KEY: int = 0

    def __init__(self):
        raise RuntimeError(
            "OffscreenContext is retired. Use SDLBackendWindow + FBOSurface "
            "through termin.display instead of creating a PySDL2 hidden GL context."
        )

    @property
    def gl_context(self):
        """GL context for sharing with display/window surfaces."""
        return None

    @property
    def context_key(self) -> int:
        """Context key for GPU resources."""
        return self.CONTEXT_KEY

    def make_current(self) -> None:
        """Activate the GL context."""
        return None

    def is_valid(self) -> bool:
        """Return whether the context still owns native resources."""
        return False

    def destroy(self) -> None:
        """Release native context resources."""
        return None

    def __enter__(self) -> "OffscreenContext":
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb) -> None:
        self.destroy()
