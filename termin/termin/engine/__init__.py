from termin import _dll_setup  # noqa: F401

_dll_setup.extend_package_path(__path__, "engine")

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
