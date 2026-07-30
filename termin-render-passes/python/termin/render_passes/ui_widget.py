"""Thin Python projection of the native UIWidgetPass."""

from termin.render_passes._render_passes_native import UIWidgetPass

UIWidgetPass.__module__ = __name__

__all__ = ["UIWidgetPass"]
