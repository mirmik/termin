"""
Entity and Component system.

Re-exports from C++ backend.
Component and InputComponent are available via termin.visualization.core.component.
"""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

from termin.entity._entity_native import (
    Entity,
    Component,
    ComponentRegistry,
    EntityRegistry,
    EntityHandle,
    CXXRotatorComponent,
)

__all__ = [
    "Component",
    "Entity",
    "EntityHandle",
    "ComponentRegistry",
    "EntityRegistry",
    "CXXRotatorComponent",
]
