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

def _wrapped_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    # Set _type_name to match InspectRegistry registration
    cls_name = type(self).__name__
    if cls_name != "Component":
        self.set_type_name(cls_name)

_NativeComponent.__init__ = _wrapped_init


# Re-export Component
Component = _NativeComponent

# Default inspect_fields for Component base class
# Note: "enabled" is registered in C++ Component class via INSPECT_FIELD
Component.inspect_fields = {}


class InputComponent(Component):
    """Component capable of handling input events."""

    def __init__(self, enabled: bool = True, active_in_editor: bool = False):
        super().__init__()
        self.enabled = enabled
        self.active_in_editor = active_in_editor

    def on_mouse_button(self, event: "MouseButtonEvent"):
        pass

    def on_mouse_move(self, event: "MouseMoveEvent"):
        pass

    def on_scroll(self, event: "ScrollEvent"):
        pass

    def on_key(self, event: "KeyEvent"):
        pass


# Import event types for type hints
from termin.visualization.core.input_events import (
    MouseButtonEvent,
    MouseMoveEvent,
    ScrollEvent,
    KeyEvent,
)

__all__ = ["Component", "InputComponent", "InspectField"]
