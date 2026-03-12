"""
SceneManager - manages scene lifecycle and update cycles.

Re-exports C++ SceneManager.
"""

from termin._native.scene import (
    SceneManager,
    SceneMode,
    SCENE_EXT_TYPE_RENDER_MOUNT,
    SCENE_EXT_TYPE_RENDER_STATE,
    SCENE_EXT_TYPE_COLLISION_WORLD,
    default_scene_extensions,
)

__all__ = [
    "SceneManager",
    "SceneMode",
    "SCENE_EXT_TYPE_RENDER_MOUNT",
    "SCENE_EXT_TYPE_RENDER_STATE",
    "SCENE_EXT_TYPE_COLLISION_WORLD",
    "default_scene_extensions",
]
