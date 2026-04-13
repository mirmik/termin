"""
WireframeRenderer - efficient wireframe rendering using instanced unit meshes.

Re-exports C++ implementation from termin._native.render.
"""

from termin._native.render import (
    WireframeRenderer,
    mat4_identity,
    mat4_translate,
    mat4_scale,
    mat4_scale_uniform,
    mat4_from_rotation_matrix,
    rotation_matrix_align_z_to_axis,
)

__all__ = [
    "WireframeRenderer",
    "mat4_identity",
    "mat4_translate",
    "mat4_scale",
    "mat4_scale_uniform",
    "mat4_from_rotation_matrix",
    "rotation_matrix_align_z_to_axis",
]
