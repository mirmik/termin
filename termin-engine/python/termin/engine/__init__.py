from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_engine")

from termin.engine._engine_native import (
    EngineCore,
    SCENE_EXT_TYPE_COLLISION_WORLD,
    create_scene,
    create_scene_with_extensions,
    create_scene_with_render,
    default_scene_extensions,
    destroy_scene_with_render,
    modules,
    register_default_scene_extensions,
    render,
    scene,
    scene_ext_attached_names,
)

TermModulesIntegration = modules.TermModulesIntegration
RenderingManager = render.RenderingManager
SceneManager = scene.SceneManager
ViewportRenderState = render.ViewportRenderState

__all__ = [
    "EngineCore",
    "RenderingManager",
    "SCENE_EXT_TYPE_COLLISION_WORLD",
    "SceneManager",
    "TermModulesIntegration",
    "ViewportRenderState",
    "create_scene",
    "create_scene_with_extensions",
    "create_scene_with_render",
    "default_scene_extensions",
    "destroy_scene_with_render",
    "modules",
    "register_default_scene_extensions",
    "render",
    "scene",
    "scene_ext_attached_names",
]
