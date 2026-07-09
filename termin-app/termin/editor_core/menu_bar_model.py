"""Canonical editor menu-bar definition.

Returns a list of ``MenuSpec`` describing every menu the editor needs. The
tcgui controller renders this specification into native widgets.

The returned specs contain ``handle_getter`` callbacks for items whose state
changes at runtime (Undo/Redo enabled, Play/Stop label, checkable toggles).
The caller passes a bound setter method that stores the toolkit-specific
handle on the controller so it can be mutated later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .menu_spec import MenuItemSpec, MenuSpec

VoidCallback = Callable[[], None]
BoolGetter = Callable[[], bool]
HandleSetter = Callable[[object], None]


@dataclass(frozen=True, slots=True)
class FileMenuActions:
    new_project: VoidCallback
    open_project: VoidCallback
    new_scene: VoidCallback
    save_scene: VoidCallback
    save_scene_as: VoidCallback
    load_scene: VoidCallback
    close_scene: VoidCallback
    load_material: VoidCallback
    load_components: VoidCallback
    deploy_stdlib: VoidCallback
    exit: VoidCallback


@dataclass(frozen=True, slots=True)
class EditMenuActions:
    undo: VoidCallback
    redo: VoidCallback
    settings: VoidCallback
    project_settings: VoidCallback


@dataclass(frozen=True, slots=True)
class ViewMenuActions:
    toggle_fullscreen: VoidCallback
    show_spacemouse_settings: VoidCallback


@dataclass(frozen=True, slots=True)
class SceneMenuActions:
    scene_properties: VoidCallback
    layers_settings: VoidCallback
    shadow_settings: VoidCallback
    pipeline_editor: VoidCallback


@dataclass(frozen=True, slots=True)
class NavigationMenuActions:
    show_agent_types: VoidCallback
    show_navmesh_areas: VoidCallback
    toggle_raw_detour_path_debug_tool: VoidCallback | None = None


@dataclass(frozen=True, slots=True)
class GameMenuActions:
    toggle_game_mode: VoidCallback
    build_project: VoidCallback
    build_android: VoidCallback
    build_quest_openxr: VoidCallback
    run_build: VoidCallback
    run_standalone: VoidCallback


@dataclass(frozen=True, slots=True)
class DebugMenuActions:
    toggle_profiler: VoidCallback
    toggle_modules: VoidCallback
    toggle_camera_frustums: VoidCallback
    show_undo_stack_viewer: VoidCallback
    show_framegraph_debugger: VoidCallback
    show_resource_manager_viewer: VoidCallback
    show_audio_debugger: VoidCallback
    show_core_registry_viewer: VoidCallback
    show_inspect_registry_viewer: VoidCallback
    show_navmesh_registry_viewer: VoidCallback
    show_scene_manager_viewer: VoidCallback
    show_python_console: VoidCallback
    toggle_surface_edge_debug_tool: VoidCallback | None = None


@dataclass(frozen=True, slots=True)
class HelpMenuActions:
    show_about: VoidCallback


@dataclass(frozen=True, slots=True)
class EditorMenuActions:
    file: FileMenuActions
    edit: EditMenuActions
    view: ViewMenuActions
    scene: SceneMenuActions
    navigation: NavigationMenuActions
    game: GameMenuActions
    debug: DebugMenuActions
    help: HelpMenuActions


@dataclass(frozen=True, slots=True)
class EditorMenuStateGetters:
    fullscreen: BoolGetter
    profiler_visible: BoolGetter
    modules_visible: BoolGetter
    camera_frustums_visible: BoolGetter
    surface_edge_debug_tool_enabled: BoolGetter | None = None
    raw_detour_path_debug_tool_enabled: BoolGetter | None = None


@dataclass(frozen=True, slots=True)
class EditorMenuHandleSetters:
    undo: HandleSetter
    redo: HandleSetter
    play: HandleSetter
    fullscreen: HandleSetter
    profiler: HandleSetter
    modules: HandleSetter
    camera_frustums: HandleSetter
    surface_edge_debug_tool: HandleSetter | None = None
    raw_detour_path_debug_tool: HandleSetter | None = None


@dataclass(frozen=True, slots=True)
class EditorMenuSpecConfig:
    actions: EditorMenuActions
    states: EditorMenuStateGetters
    handles: EditorMenuHandleSetters


def build_editor_menu_spec(config: EditorMenuSpecConfig) -> list[MenuSpec]:
    """Build the full menu-bar specification for the editor."""
    actions = config.actions
    states = config.states
    handles = config.handles

    navigation_items = [
        MenuItemSpec("Agent Types...", actions.navigation.show_agent_types),
        MenuItemSpec("NavMesh Areas...", actions.navigation.show_navmesh_areas),
    ]
    if actions.navigation.toggle_raw_detour_path_debug_tool is not None:
        navigation_items.extend([
            None,
            MenuItemSpec(
                "Raw Detour Path Debug",
                actions.navigation.toggle_raw_detour_path_debug_tool,
                is_checkable=True,
                state_getter=states.raw_detour_path_debug_tool_enabled,
                handle_getter=handles.raw_detour_path_debug_tool,
            ),
        ])

    debug_items = [
        MenuItemSpec(
            "Profiler", actions.debug.toggle_profiler, shortcut="F7",
            is_checkable=True, state_getter=states.profiler_visible,
            handle_getter=handles.profiler,
        ),
        MenuItemSpec(
            "Modules", actions.debug.toggle_modules, shortcut="F8",
            is_checkable=True, state_getter=states.modules_visible,
            handle_getter=handles.modules,
        ),
        MenuItemSpec(
            "Camera Frustums", actions.debug.toggle_camera_frustums,
            is_checkable=True, state_getter=states.camera_frustums_visible,
            handle_getter=handles.camera_frustums,
        ),
        None,
        MenuItemSpec("Undo/Redo Stack...", actions.debug.show_undo_stack_viewer),
        MenuItemSpec("Framegraph Texture Viewer...", actions.debug.show_framegraph_debugger),
        MenuItemSpec("Resource Manager...", actions.debug.show_resource_manager_viewer),
        MenuItemSpec("Audio Debugger...", actions.debug.show_audio_debugger),
        MenuItemSpec("Core Registry...", actions.debug.show_core_registry_viewer),
        MenuItemSpec("Inspect Registry...", actions.debug.show_inspect_registry_viewer),
        MenuItemSpec("NavMesh Registry...", actions.debug.show_navmesh_registry_viewer),
        MenuItemSpec("Scene Manager...", actions.debug.show_scene_manager_viewer),
        None,
        MenuItemSpec("Python Console...", actions.debug.show_python_console),
    ]
    if actions.debug.toggle_surface_edge_debug_tool is not None:
        debug_items.extend([
            None,
            MenuItemSpec(
                "Surface Edge Debug Tool",
                actions.debug.toggle_surface_edge_debug_tool,
                is_checkable=True,
                state_getter=states.surface_edge_debug_tool_enabled,
                handle_getter=handles.surface_edge_debug_tool,
            ),
        ])

    return [
        # ── File ───────────────────────────────────────────────────────
        MenuSpec(
            name="File",
            items=[
                MenuItemSpec("New Project...", actions.file.new_project),
                MenuItemSpec("Open Project...", actions.file.open_project),
                None,  # separator
                MenuItemSpec("New Scene", actions.file.new_scene, shortcut="Ctrl+N"),
                None,
                MenuItemSpec("Save Scene", actions.file.save_scene, shortcut="Ctrl+S"),
                MenuItemSpec("Save Scene As...", actions.file.save_scene_as, shortcut="Ctrl+Shift+S"),
                MenuItemSpec("Load Scene...", actions.file.load_scene, shortcut="Ctrl+O"),
                MenuItemSpec("Close Scene", actions.file.close_scene, shortcut="Ctrl+W"),
                None,
                MenuItemSpec("Load Material...", actions.file.load_material),
                MenuItemSpec("Load Components...", actions.file.load_components),
                None,
                MenuItemSpec("Deploy Standard Library...", actions.file.deploy_stdlib),
                None,
                MenuItemSpec("Exit", actions.file.exit, shortcut="Ctrl+Q"),
            ],
        ),
        # ── Edit ───────────────────────────────────────────────────────
        MenuSpec(
            name="Edit",
            items=[
                MenuItemSpec(
                    "Undo", actions.edit.undo, shortcut="Ctrl+Z",
                    handle_getter=handles.undo,
                ),
                MenuItemSpec(
                    "Redo", actions.edit.redo, shortcut="Ctrl+Shift+Z",
                    handle_getter=handles.redo,
                ),
                None,
                MenuItemSpec("Settings...", actions.edit.settings),
                MenuItemSpec("Project Settings...", actions.edit.project_settings),
            ],
        ),
        # ── View ───────────────────────────────────────────────────────
        MenuSpec(
            name="View",
            items=[
                MenuItemSpec(
                    "Fullscreen", actions.view.toggle_fullscreen, shortcut="F11",
                    is_checkable=True, state_getter=states.fullscreen,
                    handle_getter=handles.fullscreen,
                ),
                None,
                MenuItemSpec("SpaceMouse Settings...", actions.view.show_spacemouse_settings),
            ],
        ),
        # ── Scene ──────────────────────────────────────────────────────
        MenuSpec(
            name="Scene",
            items=[
                MenuItemSpec("Scene Properties...", actions.scene.scene_properties),
                MenuItemSpec("Layers & Flags...", actions.scene.layers_settings),
                MenuItemSpec("Shadow Settings...", actions.scene.shadow_settings),
                None,
                MenuItemSpec("Pipeline Editor...", actions.scene.pipeline_editor),
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
                    "Play", actions.game.toggle_game_mode, shortcut="F5",
                    handle_getter=handles.play,
                ),
                MenuItemSpec("Build Project...", actions.game.build_project),
                MenuItemSpec("Build Android APK...", actions.game.build_android),
                MenuItemSpec("Quest/OpenXR Build...", actions.game.build_quest_openxr),
                MenuItemSpec("Run Build...", actions.game.run_build),
                MenuItemSpec("Run Standalone...", actions.game.run_standalone, shortcut="F6"),
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
                MenuItemSpec("About Termin...", actions.help.show_about),
            ],
        ),
    ]
