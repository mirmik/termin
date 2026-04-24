"""Controller for editor menu bar (tcgui version)."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.menu import Menu, MenuItem


class MenuBarControllerTcgui:
    """Manages editor menu bar structure and actions for tcgui."""

    def __init__(
        self,
        menu_bar: MenuBar,
        on_new_project: Callable,
        on_open_project: Callable,
        on_new_scene: Callable,
        on_save_scene: Callable,
        on_save_scene_as: Callable,
        on_load_scene: Callable,
        on_close_scene: Callable,
        on_load_material: Callable,
        on_load_components: Callable,
        on_deploy_stdlib: Callable,
        on_migrate_spec_to_meta: Callable,
        on_exit: Callable,
        on_undo: Callable,
        on_redo: Callable,
        on_settings: Callable,
        on_project_settings: Callable,
        on_scene_properties: Callable,
        on_layers_settings: Callable,
        on_shadow_settings: Callable,
        on_pipeline_editor: Callable,
        on_toggle_game_mode: Callable,
        on_run_standalone: Callable,
        on_show_undo_stack_viewer: Callable,
        on_show_framegraph_debugger: Callable,
        on_show_resource_manager_viewer: Callable,
        on_show_audio_debugger: Callable,
        on_show_core_registry_viewer: Callable,
        on_show_inspect_registry_viewer: Callable,
        on_show_navmesh_registry_viewer: Callable,
        on_show_scene_manager_viewer: Callable,
        on_toggle_profiler: Callable,
        on_toggle_modules: Callable,
        on_toggle_fullscreen: Callable,
        on_show_agent_types: Callable,
        on_show_spacemouse_settings: Callable,
        can_undo: Callable[[], bool],
        can_redo: Callable[[], bool],
        is_fullscreen: Callable[[], bool],
        is_profiler_visible: Callable[[], bool],
        is_modules_visible: Callable[[], bool],
    ):
        self._can_undo = can_undo
        self._can_redo = can_redo
        self._is_fullscreen = is_fullscreen
        self._is_profiler_visible = is_profiler_visible
        self._is_modules_visible = is_modules_visible

        self._item_undo: MenuItem | None = None
        self._item_redo: MenuItem | None = None
        self._item_play: MenuItem | None = None

        self._setup(
            menu_bar,
            on_new_project=on_new_project,
            on_open_project=on_open_project,
            on_new_scene=on_new_scene,
            on_save_scene=on_save_scene,
            on_save_scene_as=on_save_scene_as,
            on_load_scene=on_load_scene,
            on_close_scene=on_close_scene,
            on_load_material=on_load_material,
            on_load_components=on_load_components,
            on_deploy_stdlib=on_deploy_stdlib,
            on_migrate_spec_to_meta=on_migrate_spec_to_meta,
            on_exit=on_exit,
            on_undo=on_undo,
            on_redo=on_redo,
            on_settings=on_settings,
            on_project_settings=on_project_settings,
            on_scene_properties=on_scene_properties,
            on_layers_settings=on_layers_settings,
            on_shadow_settings=on_shadow_settings,
            on_pipeline_editor=on_pipeline_editor,
            on_toggle_game_mode=on_toggle_game_mode,
            on_run_standalone=on_run_standalone,
            on_show_undo_stack_viewer=on_show_undo_stack_viewer,
            on_show_framegraph_debugger=on_show_framegraph_debugger,
            on_show_resource_manager_viewer=on_show_resource_manager_viewer,
            on_show_audio_debugger=on_show_audio_debugger,
            on_show_core_registry_viewer=on_show_core_registry_viewer,
            on_show_inspect_registry_viewer=on_show_inspect_registry_viewer,
            on_show_navmesh_registry_viewer=on_show_navmesh_registry_viewer,
            on_show_scene_manager_viewer=on_show_scene_manager_viewer,
            on_toggle_profiler=on_toggle_profiler,
            on_toggle_modules=on_toggle_modules,
            on_toggle_fullscreen=on_toggle_fullscreen,
            on_show_agent_types=on_show_agent_types,
            on_show_spacemouse_settings=on_show_spacemouse_settings,
        )

    def _setup(
        self,
        menu_bar: MenuBar,
        on_new_project: Callable,
        on_open_project: Callable,
        on_new_scene: Callable,
        on_save_scene: Callable,
        on_save_scene_as: Callable,
        on_load_scene: Callable,
        on_close_scene: Callable,
        on_load_material: Callable,
        on_load_components: Callable,
        on_deploy_stdlib: Callable,
        on_migrate_spec_to_meta: Callable,
        on_exit: Callable,
        on_undo: Callable,
        on_redo: Callable,
        on_settings: Callable,
        on_project_settings: Callable,
        on_scene_properties: Callable,
        on_layers_settings: Callable,
        on_shadow_settings: Callable,
        on_pipeline_editor: Callable,
        on_toggle_game_mode: Callable,
        on_run_standalone: Callable,
        on_show_undo_stack_viewer: Callable,
        on_show_framegraph_debugger: Callable,
        on_show_resource_manager_viewer: Callable,
        on_show_audio_debugger: Callable,
        on_show_core_registry_viewer: Callable,
        on_show_inspect_registry_viewer: Callable,
        on_show_navmesh_registry_viewer: Callable,
        on_show_scene_manager_viewer: Callable,
        on_toggle_profiler: Callable,
        on_toggle_modules: Callable,
        on_toggle_fullscreen: Callable,
        on_show_agent_types: Callable,
        on_show_spacemouse_settings: Callable,
    ) -> None:
        # File menu
        file_menu = Menu()
        file_menu.items = [
            MenuItem("New Project...", on_click=on_new_project),
            MenuItem("Open Project...", on_click=on_open_project),
            MenuItem.sep(),
            MenuItem("New Scene", shortcut="Ctrl+N", on_click=on_new_scene),
            MenuItem.sep(),
            MenuItem("Save Scene", shortcut="Ctrl+S", on_click=on_save_scene),
            MenuItem("Save Scene As...", shortcut="Ctrl+Shift+S", on_click=on_save_scene_as),
            MenuItem("Load Scene...", shortcut="Ctrl+O", on_click=on_load_scene),
            MenuItem("Close Scene", shortcut="Ctrl+W", on_click=on_close_scene),
            MenuItem.sep(),
            MenuItem("Load Material...", on_click=on_load_material),
            MenuItem("Load Components...", on_click=on_load_components),
            MenuItem.sep(),
            MenuItem("Deploy Standard Library...", on_click=on_deploy_stdlib),
            MenuItem("Migrate .spec to .meta", on_click=on_migrate_spec_to_meta),
            MenuItem.sep(),
            MenuItem("Exit", shortcut="Ctrl+Q", on_click=on_exit),
        ]

        # Edit menu
        self._item_undo = MenuItem("Undo", shortcut="Ctrl+Z", on_click=on_undo, enabled=False)
        self._item_redo = MenuItem("Redo", shortcut="Ctrl+Shift+Z", on_click=on_redo, enabled=False)
        edit_menu = Menu()
        edit_menu.items = [
            self._item_undo,
            self._item_redo,
            MenuItem.sep(),
            MenuItem("Settings...", on_click=on_settings),
            MenuItem("Project Settings...", on_click=on_project_settings),
        ]

        # View menu
        view_menu = Menu()
        view_menu.items = [
            MenuItem("Fullscreen", shortcut="F11", on_click=on_toggle_fullscreen),
            MenuItem.sep(),
            MenuItem("SpaceMouse Settings...", on_click=on_show_spacemouse_settings),
        ]

        # Scene menu
        scene_menu = Menu()
        scene_menu.items = [
            MenuItem("Scene Properties...", on_click=on_scene_properties),
            MenuItem("Layers & Flags...", on_click=on_layers_settings),
            MenuItem("Shadow Settings...", on_click=on_shadow_settings),
            MenuItem.sep(),
            MenuItem("Pipeline Editor...", on_click=on_pipeline_editor),
        ]

        # Navigation menu
        navigation_menu = Menu()
        navigation_menu.items = [
            MenuItem("Agent Types...", on_click=on_show_agent_types),
        ]

        # Game menu
        self._item_play = MenuItem("Play", shortcut="F5", on_click=on_toggle_game_mode)
        game_menu = Menu()
        game_menu.items = [
            self._item_play,
            MenuItem("Run Standalone...", shortcut="F6", on_click=on_run_standalone),
        ]

        # Debug menu
        debug_menu = Menu()
        debug_menu.items = [
            MenuItem("Profiler", shortcut="F7", on_click=on_toggle_profiler),
            MenuItem("Modules", shortcut="F8", on_click=on_toggle_modules),
            MenuItem.sep(),
            MenuItem("Undo/Redo Stack...", on_click=on_show_undo_stack_viewer),
            MenuItem("Framegraph Texture Viewer...", on_click=on_show_framegraph_debugger),
            MenuItem("Resource Manager...", on_click=on_show_resource_manager_viewer),
            MenuItem("Audio Debugger...", on_click=on_show_audio_debugger),
            MenuItem("Core Registry...", on_click=on_show_core_registry_viewer),
            MenuItem("Inspect Registry...", on_click=on_show_inspect_registry_viewer),
            MenuItem("NavMesh Registry...", on_click=on_show_navmesh_registry_viewer),
            MenuItem("Scene Manager...", on_click=on_show_scene_manager_viewer),
        ]

        menu_bar.add_menu("File", file_menu)
        menu_bar.add_menu("Edit", edit_menu)
        menu_bar.add_menu("View", view_menu)
        menu_bar.add_menu("Scene", scene_menu)
        menu_bar.add_menu("Navigation", navigation_menu)
        menu_bar.add_menu("Game", game_menu)
        menu_bar.add_menu("Debug", debug_menu)

        self.update_undo_redo_actions()

    def update_undo_redo_actions(self) -> None:
        if self._item_undo is not None:
            self._item_undo.enabled = self._can_undo()
        if self._item_redo is not None:
            self._item_redo.enabled = self._can_redo()

    def update_play_action(self, is_playing: bool) -> None:
        if self._item_play is not None:
            self._item_play.label = "Stop" if is_playing else "Play"
