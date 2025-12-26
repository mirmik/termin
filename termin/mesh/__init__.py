"""Mesh module - Mesh3, SkinnedMesh3, MeshHandle."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

from termin.mesh._mesh_native import Mesh3, SkinnedMesh3, MeshHandle

__all__ = ["Mesh3", "SkinnedMesh3", "MeshHandle"]
