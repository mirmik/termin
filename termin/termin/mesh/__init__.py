"""Mesh module - Mesh3, TcMesh."""

from termin import _dll_setup  # noqa: F401

_dll_setup.extend_package_path(__path__, "mesh")

from tgfx import Mesh3, TcMesh
from termin.mesh.mesh_component import MeshComponent

__all__ = ["Mesh3", "TcMesh", "MeshComponent"]
