"""
Entity and Component system.

Re-exports from C++ backend and visualization.core.component.
"""

from termin._native.entity import (
    Entity,
    Component as _NativeComponent,
    ComponentRegistry,
    EntityRegistry,
    CXXRotatorComponent,
)

# Full-featured Component with serialization and inspector support
from termin.visualization.core.component import Component, InputComponent

__all__ = [
    "Component",
    "InputComponent",
    "Entity",
    "ComponentRegistry",
    "EntityRegistry",
    "CXXRotatorComponent",
    "_NativeComponent",
]
