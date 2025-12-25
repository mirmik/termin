"""
Entity and Component system.

Re-exports from C++ backend.
Component and InputComponent are available via termin.visualization.core.component.
"""

# Add DLL search path on Windows (for entity_lib.dll)
import os
import sys
if sys.platform == "win32":
    _dll_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(_dll_dir)
    os.environ["PATH"] = _dll_dir + os.pathsep + os.environ.get("PATH", "")

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
