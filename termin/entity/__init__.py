"""
Entity and Component system.

Re-exports from C++ backend.
Component and InputComponent are available via termin.visualization.core.component.
"""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

# Import _geom_native first to register Mat44 type before _entity_native uses it
from termin.geombase import _geom_native  # noqa: F401

# Import _viewport_native to register TcViewport type before _entity_native uses it
from termin.viewport import _viewport_native  # noqa: F401
from termin.viewport import Viewport

from termin.entity._entity_native import (
    Entity,
    Component,
    ComponentRegistry,
    EntityRegistry,
    CXXRotatorComponent,
    TcComponentRef,
    TcSceneRef,
)

# CameraComponent moved to termin.visualization.core.camera (Python implementation)
# Import it from there directly to avoid circular imports

__all__ = [
    "Component",
    "Entity",
    "ComponentRegistry",
    "EntityRegistry",
    "CXXRotatorComponent",
    "TcComponentRef",
    "TcSceneRef",
    "Viewport",
]
