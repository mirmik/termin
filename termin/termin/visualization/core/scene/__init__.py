"""Scene module - container for entities and scene configuration."""

from termin.entity._entity_native import (
    TcScene as Scene,
    deserialize_scene,
    create_scene,
    create_scene_with_extensions,
    destroy_scene,
    scene_render_state,
    scene_render_mount,
    default_scene_extensions,
    SCENE_EXT_TYPE_RENDER_MOUNT,
    SCENE_EXT_TYPE_RENDER_STATE,
    SCENE_EXT_TYPE_COLLISION_WORLD,
    SceneRenderState,
    SceneRenderMount,
)
from termin.lighting import ShadowSettings

from ._helpers import find_component, find_components, dispatch_input

__all__ = [
    "Scene",
    "ShadowSettings",
    "deserialize_scene",
    "create_scene",
    "create_scene_with_extensions",
    "destroy_scene",
    "default_scene_extensions",
    "SCENE_EXT_TYPE_RENDER_MOUNT",
    "SCENE_EXT_TYPE_RENDER_STATE",
    "SCENE_EXT_TYPE_COLLISION_WORLD",
    "scene_render_state",
    "scene_render_mount",
    "SceneRenderState",
    "SceneRenderMount",
    "find_component",
    "find_components",
    "dispatch_input",
]
