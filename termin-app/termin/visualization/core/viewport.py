"""Viewport - what to render and where."""

from termin.viewport import Viewport

__all__ = ["Viewport", "make_default_pipeline"]


def make_default_pipeline():
    """Create the single native Default render pipeline."""
    from termin.engine import RenderingManager

    return RenderingManager.instance().create_pipeline("Default")
