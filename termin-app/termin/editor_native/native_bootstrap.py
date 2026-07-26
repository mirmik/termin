"""Private lifecycle helpers for the native editor bootstrap."""

from __future__ import annotations

from collections.abc import Callable

from termin.editor_native.editor_session import EditorSession
from termin.editor_native.editor_composition import EditorCompositionConfig


def require_offscreen_process_isolation() -> None:
    import sys

    forbidden = (
        "termin.display._platform_native",
        "termin.display.window",
        "termin.gui_native._gui_native_window",
        "termin.gui_native.window",
    )
    loaded = [name for name in forbidden if name in sys.modules]
    if loaded:
        raise RuntimeError(
            "offscreen editor loaded optional window integration: "
            + ", ".join(loaded)
        )


def complete_editor_scene_render(native_viewport, host) -> None:
    """Finish viewport work and schedule presentation of the produced image."""
    native_viewport.after_render()
    host.request_render_update()


def _clear_component_extension_viewport(extension_context) -> None:
    extension_context.on_viewport_tool_state_changed = None
    extension_context.viewport_geometry = None


def bind_editor_viewport_lifecycle(
    workspace_stage,
    scene_manager,
    extension_context,
    native_viewport,
    host,
) -> None:
    """Bind viewport callbacks and register their matching lifecycle cleanup."""
    extension_context.on_viewport_tool_state_changed = native_viewport.sync_gizmo_target
    extension_context.viewport_geometry = native_viewport.geometry
    workspace_stage.add_cleanup(
        "component extension viewport binding",
        lambda: _clear_component_extension_viewport(extension_context),
    )
    workspace_stage.add_cleanup(
        "scene after-render callback",
        lambda: scene_manager.set_on_after_render(None),
    )
    scene_manager.set_on_after_render(
        lambda: complete_editor_scene_render(native_viewport, host)
    )


def close_game_mode_controller(game_mode_controller) -> None:
    if game_mode_controller.model.is_game_mode:
        game_mode_controller.model.toggle_game_mode()
    game_mode_controller.close()


def init_editor_native(
    engine,
    compose_editor: Callable[..., None],
    debug_resource: str | None = None,
    no_scene: bool = False,
    *,
    composition_config: EditorCompositionConfig | None = None,
    failure_injector: Callable[[str], None] | None = None,
) -> EditorSession:
    """Initialize one native document and register it with the C++ engine loop."""

    def compose(session: EditorSession) -> None:
        compose_editor(
            session,
            engine,
            debug_resource=debug_resource,
            no_scene=no_scene,
            composition_config=composition_config,
        )

    return EditorSession.build(
        compose,
        failure_injector=failure_injector,
        shutdown_engine=engine.shutdown,
    )


__all__ = [
    "bind_editor_viewport_lifecycle",
    "close_game_mode_controller",
    "complete_editor_scene_render",
    "init_editor_native",
    "require_offscreen_process_isolation",
]
