"""Mesh module - Mesh3, TcMesh."""

import os as _os
_sdk_dir = _os.path.join(_os.sep, "opt", "termin", "lib", "python", "termin", "mesh")
if _os.path.isdir(_sdk_dir) and _sdk_dir not in __path__:
    __path__.append(_sdk_dir)

from tgfx import Mesh3, TcMesh
from termin.mesh.mesh_component import MeshComponent

__all__ = ["Mesh3", "TcMesh", "MeshComponent"]
