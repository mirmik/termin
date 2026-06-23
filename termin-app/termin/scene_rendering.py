"""Scene render extension helpers.

This module is the app-owned transitional home for scene render state and
render mount bindings that are still exported by ``termin._native``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Type, TypeVar

from termin._native import (
    SCENE_EXT_TYPE_COLLISION_WORLD,
    SCENE_EXT_TYPE_RENDER_MOUNT,
    SCENE_EXT_TYPE_RENDER_STATE,
    SceneRenderMount,
    SceneRenderState,
    create_scene,
    create_scene_with_extensions,
    default_scene_extensions,
    deserialize_scene,
    destroy_scene,
    scene_ext_attached_names,
    scene_render_mount,
    scene_render_state,
)
from termin.lighting import ShadowSettings
from termin.scene import TcScene as Scene

if TYPE_CHECKING:
    from termin.input import InputComponent
    from termin.scene import Component
    from termin.scene import TcScene

T = TypeVar("T", bound="Component")


def find_component(scene: "TcScene", component_type: Type[T]) -> T | None:
    """Find first component of given type in scene."""
    components = scene.get_components_of_type(component_type.__name__)
    return components[0] if components else None


def find_components(scene: "TcScene", component_type: Type[T]) -> List[T]:
    """Find all components of given type in scene."""
    return scene.get_components_of_type(component_type.__name__)


def dispatch_input(
    scene: "TcScene",
    event_name: str,
    event,
    filter_fn: Callable[["InputComponent"], bool] | None = None,
) -> None:
    """Dispatch input event to InputComponents."""
    if filter_fn is None:
        scene.dispatch_input(event_name, event)
        return

    from tcbase import log

    def dispatch_to_component(component):
        if not filter_fn(component):
            return True
        handler = getattr(component, event_name, None)
        if handler:
            try:
                handler(event)
            except Exception as exc:
                log.error(
                    f"Error in input handler '{event_name}' of component '{component}': {exc}"
                )
        return True

    scene.foreach_component_of_type("InputComponent", dispatch_to_component)


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
    "scene_ext_attached_names",
    "SceneRenderState",
    "SceneRenderMount",
    "find_component",
    "find_components",
    "dispatch_input",
]
