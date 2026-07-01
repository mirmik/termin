"""Canonical editor menu-bar definition.

Returns a list of ``MenuSpec`` describing every menu the editor needs. The
tcgui controller renders this specification into native widgets.

The returned specs contain ``handle_getter`` callbacks for items whose state
changes at runtime (Undo/Redo enabled, Play/Stop label, checkable toggles).
The caller passes a bound setter method that stores the toolkit-specific
handle on the controller so it can be mutated later.
"""

from __future__ import annotations

from typing import Callable

from .menu_spec import MenuItemSpec, MenuSpec


def build_editor_menu_spec(
    # File
    on_new_project: Callable[[], None],
    on_open_project: Callable[[], None],
    on_new_scene: Callable[[], None],
    on_save_scene: Callable[[], None],
    on_save_scene_as: Callable[[], None],
    on_load_scene: Callable[[], None],
    on_close_scene: Callable[[], None],
    on_load_material: Callable[[], None],
    on_load_components: Callable[[], None],
    on_deploy_stdlib: Callable[[], None],
    on_migrate_spec_to_meta: Callable[[], None],
    on_exit: Callable[[], None],
    # Edit
    on_undo: Callable[[], None],
    on_redo: Callable[[], None],
    on_settings: Callable[[], None],
    on_project_settings: Callable[[], None],
    # View
    on_toggle_fullscreen: Callable[[], None],
    is_fullscreen: Callable[[], bool],
    on_show_spacemouse_settings: Callable[[], None],
    # Scene
    on_scene_properties: Callable[[], None],
    on_layers_settings: Callable[[], None],
    on_shadow_settings: Callable[[], None],
    on_pipeline_editor: Callable[[], None],
    # Navigation
    on_show_agent_types: Callable[[], None],
    on_show_navmesh_areas: Callable[[], None],
    # Game
    on_toggle_game_mode: Callable[[], None],
    on_build_project: Callable[[], None],
    on_build_android: Callable[[], None],
    on_build_quest_openxr: Callable[[], None],
    on_run_build: Callable[[], None],
    on_run_standalone: Callable[[], None],
    # Debug
    on_toggle_profiler: Callable[[], None],
    is_profiler_visible: Callable[[], bool],
    on_toggle_modules: Callable[[], None],
    is_modules_visible: Callable[[], bool],
    on_show_undo_stack_viewer: Callable[[], None],
    on_show_framegraph_debugger: Callable[[], None],
    on_show_resource_manager_viewer: Callable[[], None],
    on_show_audio_debugger: Callable[[], None],
    on_show_core_registry_viewer: Callable[[], None],
    on_show_inspect_registry_viewer: Callable[[], None],
    on_show_navmesh_registry_viewer: Callable[[], None],
    on_show_scene_manager_viewer: Callable[[], None],
    on_show_python_console: Callable[[], None],
    # Help
    on_show_about: Callable[[], None],
    # Handle setters (called by the controller with native widget handles)
    set_undo_handle: Callable[[object], None],
    set_redo_handle: Callable[[object], None],
    set_play_handle: Callable[[object], None],
    set_fullscreen_handle: Callable[[object], None],
    set_profiler_handle: Callable[[object], None],
    set_modules_handle: Callable[[object], None],
    on_toggle_surface_edge_debug_tool: Callable[[], None] | None = None,
    is_surface_edge_debug_tool_enabled: Callable[[], bool] | None = None,
    set_surface_edge_debug_tool_handle: Callable[[object], None] | None = None,
    on_toggle_raw_detour_path_debug_tool: Callable[[], None] | None = None,
    is_raw_detour_path_debug_tool_enabled: Callable[[], bool] | None = None,
    set_raw_detour_path_debug_tool_handle: Callable[[object], None] | None = None,
) -> list[MenuSpec]:
    """Build the full menu-bar specification for the editor."""
    navigation_items = [
        MenuItemSpec("Agent Types...", on_show_agent_types),
        MenuItemSpec("NavMesh Areas...", on_show_navmesh_areas),
    ]
    if on_toggle_raw_detour_path_debug_tool is not None:
        navigation_items.extend([
            None,
            MenuItemSpec(
                "Raw Detour Path Debug",
                on_toggle_raw_detour_path_debug_tool,
                is_checkable=True,
                state_getter=is_raw_detour_path_debug_tool_enabled,
                handle_getter=set_raw_detour_path_debug_tool_handle,
            ),
        ])

    debug_items = [
        MenuItemSpec(
            "Profiler", on_toggle_profiler, shortcut="F7",
            is_checkable=True, state_getter=is_profiler_visible,
            handle_getter=set_profiler_handle,
        ),
        MenuItemSpec(
            "Modules", on_toggle_modules, shortcut="F8",
            is_checkable=True, state_getter=is_modules_visible,
            handle_getter=set_modules_handle,
        ),
        None,
        MenuItemSpec("Undo/Redo Stack...", on_show_undo_stack_viewer),
        MenuItemSpec("Framegraph Texture Viewer...", on_show_framegraph_debugger),
        MenuItemSpec("Resource Manager...", on_show_resource_manager_viewer),
        MenuItemSpec("Audio Debugger...", on_show_audio_debugger),
        MenuItemSpec("Core Registry...", on_show_core_registry_viewer),
        MenuItemSpec("Inspect Registry...", on_show_inspect_registry_viewer),
        MenuItemSpec("NavMesh Registry...", on_show_navmesh_registry_viewer),
        MenuItemSpec("Scene Manager...", on_show_scene_manager_viewer),
        None,
        MenuItemSpec("Python Console...", on_show_python_console),
    ]
    if on_toggle_surface_edge_debug_tool is not None:
        debug_items.extend([
            None,
            MenuItemSpec(
                "Surface Edge Debug Tool",
                on_toggle_surface_edge_debug_tool,
                is_checkable=True,
                state_getter=is_surface_edge_debug_tool_enabled,
                handle_getter=set_surface_edge_debug_tool_handle,
            ),
        ])

    return [
        # ── File ───────────────────────────────────────────────────────
        MenuSpec(
            name="File",
            items=[
                MenuItemSpec("New Project...", on_new_project),
                MenuItemSpec("Open Project...", on_open_project),
                None,  # separator
                MenuItemSpec("New Scene", on_new_scene, shortcut="Ctrl+N"),
                None,
                MenuItemSpec("Save Scene", on_save_scene, shortcut="Ctrl+S"),
                MenuItemSpec("Save Scene As...", on_save_scene_as, shortcut="Ctrl+Shift+S"),
                MenuItemSpec("Load Scene...", on_load_scene, shortcut="Ctrl+O"),
                MenuItemSpec("Close Scene", on_close_scene, shortcut="Ctrl+W"),
                None,
                MenuItemSpec("Load Material...", on_load_material),
                MenuItemSpec("Load Components...", on_load_components),
                None,
                MenuItemSpec("Deploy Standard Library...", on_deploy_stdlib),
                MenuItemSpec("Migrate .spec to .meta", on_migrate_spec_to_meta),
                None,
                MenuItemSpec("Exit", on_exit, shortcut="Ctrl+Q"),
            ],
        ),
        # ── Edit ───────────────────────────────────────────────────────
        MenuSpec(
            name="Edit",
            items=[
                MenuItemSpec(
                    "Undo", on_undo, shortcut="Ctrl+Z",
                    handle_getter=set_undo_handle,
                ),
                MenuItemSpec(
                    "Redo", on_redo, shortcut="Ctrl+Shift+Z",
                    handle_getter=set_redo_handle,
                ),
                None,
                MenuItemSpec("Settings...", on_settings),
                MenuItemSpec("Project Settings...", on_project_settings),
            ],
        ),
        # ── View ───────────────────────────────────────────────────────
        MenuSpec(
            name="View",
            items=[
                MenuItemSpec(
                    "Fullscreen", on_toggle_fullscreen, shortcut="F11",
                    is_checkable=True, state_getter=is_fullscreen,
                    handle_getter=set_fullscreen_handle,
                ),
                None,
                MenuItemSpec("SpaceMouse Settings...", on_show_spacemouse_settings),
            ],
        ),
        # ── Scene ──────────────────────────────────────────────────────
        MenuSpec(
            name="Scene",
            items=[
                MenuItemSpec("Scene Properties...", on_scene_properties),
                MenuItemSpec("Layers & Flags...", on_layers_settings),
                MenuItemSpec("Shadow Settings...", on_shadow_settings),
                None,
                MenuItemSpec("Pipeline Editor...", on_pipeline_editor),
            ],
        ),
        # ── Navigation ─────────────────────────────────────────────────
        MenuSpec(
            name="Navigation",
            items=navigation_items,
        ),
        # ── Game ───────────────────────────────────────────────────────
        MenuSpec(
            name="Game",
            items=[
                MenuItemSpec(
                    "Play", on_toggle_game_mode, shortcut="F5",
                    handle_getter=set_play_handle,
                ),
                MenuItemSpec("Build Project...", on_build_project),
                MenuItemSpec("Build Android APK...", on_build_android),
                MenuItemSpec("Quest/OpenXR Build...", on_build_quest_openxr),
                MenuItemSpec("Run Build...", on_run_build),
                MenuItemSpec("Run Standalone...", on_run_standalone, shortcut="F6"),
            ],
        ),
        # ── Debug ──────────────────────────────────────────────────────
        MenuSpec(
            name="Debug",
            items=debug_items,
        ),
        # ── Help ───────────────────────────────────────────────────────
        MenuSpec(
            name="Help",
            items=[
                MenuItemSpec("About Termin...", on_show_about),
            ],
        ),
    ]
