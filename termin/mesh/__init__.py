"""Mesh module - Mesh3, TcMesh, MeshHandle."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

from termin.mesh._mesh_native import Mesh3, TcMesh, MeshHandle

__all__ = ["Mesh3", "TcMesh", "MeshHandle"]
