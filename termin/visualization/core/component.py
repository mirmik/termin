"""
Component registration and utilities.

The actual Component class comes from C++ (_entity_native).
This module adds Python-specific functionality via __init_subclass__ hook.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.render_context import RenderContext

from termin.editor.inspect_field import InspectField
from termin.entity import Component as _NativeComponent, ComponentRegistry
from termin._native.inspect import InspectRegistry


def _component_init_subclass(cls, **kwargs):
    """
    Called when a class inherits from Component.
    Registers the class in ComponentRegistry and InspectRegistry.
    """
    # Don't register the base Component itself
    if cls.__name__ == "Component":
        return

    # Collect all inspect_fields from class hierarchy
    all_fields = {}
    for klass in reversed(cls.__mro__):
        if hasattr(klass, 'inspect_fields') and klass.inspect_fields:
            all_fields.update(klass.inspect_fields)

    # Register fields in C++ InspectRegistry
    if all_fields:
        InspectRegistry.instance().register_python_fields(cls.__name__, all_fields)

    # Register in Python ResourceManager
    try:
        from termin.visualization.core.resources import ResourceManager
        manager = ResourceManager.instance()
        manager.register_component(cls.__name__, cls)
    except ImportError:
        pass  # ResourceManager not available yet

    # Register in C++ ComponentRegistry
    ComponentRegistry.instance().register_python(cls.__name__, cls)


# Inject __init_subclass__ into the C++ Component class
_NativeComponent.__init_subclass__ = classmethod(lambda cls, **kw: _component_init_subclass(cls, **kw))

# Wrap __init__ to set _type_name for Python components
_original_init = _NativeComponent.__init__


def _check_overrides_method(cls, method_name: str, base_class) -> bool:
    """Check if cls overrides method_name from base_class."""
    return getattr(cls, method_name) is not getattr(base_class, method_name)


def _wrapped_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    cls = type(self)
    cls_name = cls.__name__
    if cls_name != "Component":
        # Set _type_name to match InspectRegistry registration
        self.set_type_name(cls_name)
        # Set has_update/has_fixed_update based on method overrides
        if _check_overrides_method(cls, "update", _NativeComponent):
            self.has_update = True
        if _check_overrides_method(cls, "fixed_update", _NativeComponent):
            self.has_fixed_update = True

_NativeComponent.__init__ = _wrapped_init


# Re-export Component
Component = _NativeComponent

# Default inspect_fields for Component base class
# Note: "enabled" is registered in C++ Component class via INSPECT_FIELD
Component.inspect_fields = {}


# Import event types for type hints
from termin.visualization.core.input_events import (
    MouseButtonEvent,
    MouseMoveEvent,
    ScrollEvent,
    KeyEvent,
)

from termin.visualization.core.python_component import PythonComponent, InputComponent

__all__ = ["Component", "PythonComponent", "InputComponent", "InspectField"]
