"""Mesh module — Mesh3, TcMesh (via tgfx) + MeshComponent (nanobind)."""

from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("nanobind", "termin_components_mesh")

from tmesh import Mesh3, TcMesh
from termin.mesh.mesh_component import MeshComponent

__all__ = ["Mesh3", "TcMesh", "MeshComponent"]
