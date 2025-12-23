"""
Entity and Component system with C++ backend.

Both C++ and Python components are supported:
- C++ components use REGISTER_COMPONENT macro
- Python components inherit from Component (auto-registered)
"""

from __future__ import annotations

from termin.entity._entity_native import (
    Entity,
    Component as _NativeComponent,
    ComponentRegistry,
    EntityRegistry,
    CXXRotatorComponent,
)


class Component(_NativeComponent):
    """
    Base class for Python components.

    Subclasses are automatically registered with ComponentRegistry.
    Override type_name(), start(), update(dt), on_destroy() as needed.
    """

    def __init_subclass__(cls, **kwargs):
        """Auto-register subclass with ComponentRegistry."""
        super().__init_subclass__(**kwargs)

        # Skip abstract classes (those with abstract methods)
        if getattr(cls, '__abstractmethods__', None):
            return

        # Register with C++ ComponentRegistry
        ComponentRegistry.instance().register_python(cls.__name__, cls)

    def type_name(self) -> str:
        """Return component type name for serialization."""
        return self.__class__.__name__


__all__ = [
    "Component",
    "Entity",
    "ComponentRegistry",
    "EntityRegistry",
    "CXXRotatorComponent",
]
