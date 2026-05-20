from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_engine")

from termin.engine._engine_native import EngineCore, render, scene

RenderingManager = render.RenderingManager
SceneManager = scene.SceneManager
ViewportRenderState = render.ViewportRenderState

__all__ = [
    "EngineCore",
    "RenderingManager",
    "SceneManager",
    "ViewportRenderState",
    "render",
    "scene",
]
