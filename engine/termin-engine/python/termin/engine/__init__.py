from termin_nanobind.runtime import preload_sdk_libs

preload_sdk_libs("termin_engine")

from termin.engine._engine_native import (
    EngineCore,
    EngineLoopClient,
    EngineLoopClientConnection,
    _borrow_engine_core as _borrow_engine_core,
    SCENE_EXT_TYPE_COLLISION_WORLD,
    create_scene,
    create_scene_with_extensions,
    create_scene_with_render,
    default_scene_extensions,
    deserialize_scene,
    deserialize_scene_with_render,
    modules,
    register_default_scene_extensions,
    render,
    scene,
    scene_ext_attached_names,
)

TermModulesIntegration = modules.TermModulesIntegration
RenderingManager = render.RenderingManager
FrameGraphDebugger = render.FrameGraphDebugger
FrameGraphDebuggerMode = render.FrameGraphDebuggerMode
FrameGraphDebuggerPassInfo = render.FrameGraphDebuggerPassInfo
FrameGraphDebuggerState = render.FrameGraphDebuggerState
FrameGraphDebuggerSuspendReason = render.FrameGraphDebuggerSuspendReason
RenderAttachmentContext = render.RenderAttachmentContext
RenderTopology = render.RenderTopology
SceneManager = scene.SceneManager
ViewportRenderState = render.ViewportRenderState

__all__ = [
    "EngineCore",
    "EngineLoopClient",
    "EngineLoopClientConnection",
    "FrameGraphDebugger",
    "FrameGraphDebuggerMode",
    "FrameGraphDebuggerPassInfo",
    "FrameGraphDebuggerState",
    "FrameGraphDebuggerSuspendReason",
    "RenderingManager",
    "RenderAttachmentContext",
    "RenderTopology",
    "SCENE_EXT_TYPE_COLLISION_WORLD",
    "SceneManager",
    "TermModulesIntegration",
    "ViewportRenderState",
    "create_scene",
    "create_scene_with_extensions",
    "create_scene_with_render",
    "default_scene_extensions",
    "deserialize_scene",
    "deserialize_scene_with_render",
    "modules",
    "register_default_scene_extensions",
    "render",
    "scene",
    "scene_ext_attached_names",
]
