"""Thin Python projection of the native UIComponent."""

from termin.ui_components._ui_components_native import UIComponent

UIComponent.__module__ = __name__

__all__ = ["UIComponent"]
