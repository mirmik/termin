"""Compatibility re-export for GLB runtime instantiation."""

from termin.glb.instantiator import (
    GLBInstantiateResult,
    instantiate_glb,
    _glb_mesh_to_tc_mesh,
    _glb_skin_to_tc_skeleton,
    _populate_tc_mesh_from_glb,
    _populate_tc_skeleton_from_glb,
)

__all__ = [
    "GLBInstantiateResult",
    "_glb_mesh_to_tc_mesh",
    "_glb_skin_to_tc_skeleton",
    "_populate_tc_mesh_from_glb",
    "_populate_tc_skeleton_from_glb",
    "instantiate_glb",
]
