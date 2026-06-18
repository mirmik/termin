"""Compatibility re-export for default built-in resources."""

from termin.default_assets.builtin_resources import (
    register_all_builtins,
    register_builtin_materials,
    register_builtin_meshes,
    register_builtin_shaders,
    register_builtin_textures,
    register_default_pipeline,
    register_triangle_pipeline,
)

__all__ = [
    "register_all_builtins",
    "register_builtin_materials",
    "register_builtin_meshes",
    "register_builtin_shaders",
    "register_builtin_textures",
    "register_default_pipeline",
    "register_triangle_pipeline",
]
