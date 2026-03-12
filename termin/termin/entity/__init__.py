"""
Entity and Component system.

Re-exports from C++ backend.
Component and InputComponent are available via termin.visualization.core.component.
"""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

import os as _os
_sdk_dir = _os.path.join(_os.sep, "opt", "termin", "lib", "python", "termin", "entity")
if _os.path.isdir(_sdk_dir) and _sdk_dir not in __path__:
    __path__.append(_sdk_dir)

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
    TcComponentRef,
    TcScene,
)
from termin.render_components import (
    CameraComponent,
    PerspectiveCameraComponent,
    OrthographicCameraComponent,
)

# Alias for backwards compatibility
TcSceneRef = TcScene

__all__ = [
    "Component",
    "Entity",
    "ComponentRegistry",
    "EntityRegistry",
    "TcComponentRef",
    "TcScene",
    "TcSceneRef",  # alias
    "Viewport",
    "CameraComponent",
    "PerspectiveCameraComponent",
    "OrthographicCameraComponent",
]
