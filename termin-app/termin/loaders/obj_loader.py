"""Compatibility re-export for OBJ loading helpers."""

from termin.mesh.obj_loader import (
    OBJMeshData,
    OBJSceneData,
    load_obj_file,
    parse_obj_text,
)

__all__ = [
    "OBJMeshData",
    "OBJSceneData",
    "load_obj_file",
    "parse_obj_text",
]
