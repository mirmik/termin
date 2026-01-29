"""
Controller for editor menu bar.

Handles menu creation and menu action callbacks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtGui import QAction

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow, QMenuBar


class MenuBarController:
    """
    Manages editor menu bar structure and actions.

    Handles:
    - Menu creation (File, Edit, Scene, Game, Debug)
    - Undo/Redo action state
    - Play/Stop action state
    """

    def __init__(
        self,
        menu_bar: "QMenuBar",
        # Action callbacks
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
        # State getters
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

        self._action_undo: QAction | None = None
        self._action_redo: QAction | None = None
        self._action_play: QAction | None = None
        self._action_fullscreen: QAction | None = None
        self._action_profiler: QAction | None = None
        self._action_modules: QAction | None = None

        self._setup_menu_bar(
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
        )

    def _setup_menu_bar(
        self,
        menu_bar: "QMenuBar",
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
    ) -> None:
        """Create menu bar structure and connect actions."""
        file_menu = menu_bar.addMenu("File")
        edit_menu = menu_bar.addMenu("Edit")
        view_menu = menu_bar.addMenu("View")
        scene_menu = menu_bar.addMenu("Scene")
        navigation_menu = menu_bar.addMenu("Navigation")
        game_menu = menu_bar.addMenu("Game")
        debug_menu = menu_bar.addMenu("Debug")

        # File menu - Project
        new_project_action = file_menu.addAction("New Project...")
        new_project_action.triggered.connect(on_new_project)

        open_project_action = file_menu.addAction("Open Project...")
        open_project_action.triggered.connect(on_open_project)

        file_menu.addSeparator()

        new_scene_action = file_menu.addAction("New Scene")
        new_scene_action.setShortcut("Ctrl+N")
        new_scene_action.triggered.connect(on_new_scene)

        file_menu.addSeparator()

        save_scene_action = file_menu.addAction("Save Scene")
        save_scene_action.setShortcut("Ctrl+S")
        save_scene_action.triggered.connect(on_save_scene)

        save_scene_as_action = file_menu.addAction("Save Scene As...")
        save_scene_as_action.setShortcut("Ctrl+Shift+S")
        save_scene_as_action.triggered.connect(on_save_scene_as)

        load_scene_action = file_menu.addAction("Load Scene...")
        load_scene_action.setShortcut("Ctrl+O")
        load_scene_action.triggered.connect(on_load_scene)

        close_scene_action = file_menu.addAction("Close Scene")
        close_scene_action.setShortcut("Ctrl+W")
        close_scene_action.triggered.connect(on_close_scene)

        file_menu.addSeparator()

        load_material_action = file_menu.addAction("Load Material...")
        load_material_action.triggered.connect(on_load_material)

        load_components_action = file_menu.addAction("Load Components...")
        load_components_action.triggered.connect(on_load_components)

        file_menu.addSeparator()

        deploy_stdlib_action = file_menu.addAction("Deploy Standard Library...")
        deploy_stdlib_action.triggered.connect(on_deploy_stdlib)

        migrate_spec_action = file_menu.addAction("Migrate .spec to .meta")
        migrate_spec_action.triggered.connect(on_migrate_spec_to_meta)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(on_exit)

        # Edit menu
        self._action_undo = edit_menu.addAction("Undo")
        self._action_undo.setShortcut("Ctrl+Z")
        self._action_undo.triggered.connect(on_undo)

        self._action_redo = edit_menu.addAction("Redo")
        self._action_redo.setShortcut("Ctrl+Shift+Z")
        self._action_redo.triggered.connect(on_redo)

        edit_menu.addSeparator()

        settings_action = edit_menu.addAction("Settings...")
        settings_action.triggered.connect(on_settings)

        project_settings_action = edit_menu.addAction("Project Settings...")
        project_settings_action.triggered.connect(on_project_settings)

        # View menu
        self._action_fullscreen = view_menu.addAction("Fullscreen")
        self._action_fullscreen.setShortcut("F11")
        self._action_fullscreen.setCheckable(True)
        self._action_fullscreen.triggered.connect(on_toggle_fullscreen)

        # Scene menu
        scene_properties_action = scene_menu.addAction("Scene Properties...")
        scene_properties_action.triggered.connect(on_scene_properties)

        layers_settings_action = scene_menu.addAction("Layers && Flags...")
        layers_settings_action.triggered.connect(on_layers_settings)

        shadow_settings_action = scene_menu.addAction("Shadow Settings...")
        shadow_settings_action.triggered.connect(on_shadow_settings)

        scene_menu.addSeparator()

        pipeline_editor_action = scene_menu.addAction("Pipeline Editor...")
        pipeline_editor_action.triggered.connect(on_pipeline_editor)

        # Navigation menu
        agent_types_action = navigation_menu.addAction("Agent Types...")
        agent_types_action.triggered.connect(on_show_agent_types)

        # Game menu
        self._action_play = game_menu.addAction("Play")
        self._action_play.setShortcut("F5")
        self._action_play.triggered.connect(on_toggle_game_mode)

        run_standalone_action = game_menu.addAction("Run Standalone...")
        run_standalone_action.setShortcut("F6")
        run_standalone_action.triggered.connect(on_run_standalone)

        # Debug menu
        self._action_profiler = debug_menu.addAction("Profiler")
        self._action_profiler.setShortcut("F7")
        self._action_profiler.setCheckable(True)
        self._action_profiler.triggered.connect(on_toggle_profiler)

        self._action_modules = debug_menu.addAction("Modules")
        self._action_modules.setShortcut("F8")
        self._action_modules.setCheckable(True)
        self._action_modules.triggered.connect(on_toggle_modules)

        debug_menu.addSeparator()

        debug_action = debug_menu.addAction("Undo/Redo Stack...")
        debug_action.triggered.connect(on_show_undo_stack_viewer)

        tex_debug_action = debug_menu.addAction("Framegraph Texture Viewer...")
        tex_debug_action.triggered.connect(on_show_framegraph_debugger)

        resource_debug_action = debug_menu.addAction("Resource Manager...")
        resource_debug_action.triggered.connect(on_show_resource_manager_viewer)

        audio_debug_action = debug_menu.addAction("Audio Debugger...")
        audio_debug_action.triggered.connect(on_show_audio_debugger)

        core_registry_action = debug_menu.addAction("Core Registry...")
        core_registry_action.triggered.connect(on_show_core_registry_viewer)

        inspect_registry_action = debug_menu.addAction("Inspect Registry...")
        inspect_registry_action.triggered.connect(on_show_inspect_registry_viewer)

        navmesh_registry_action = debug_menu.addAction("NavMesh Registry...")
        navmesh_registry_action.triggered.connect(on_show_navmesh_registry_viewer)

        scene_manager_action = debug_menu.addAction("Scene Manager...")
        scene_manager_action.triggered.connect(on_show_scene_manager_viewer)

        self.update_undo_redo_actions()

    def update_undo_redo_actions(self) -> None:
        """Update enabled state of Undo/Redo menu items."""
        if self._action_undo is not None:
            self._action_undo.setEnabled(self._can_undo())
        if self._action_redo is not None:
            self._action_redo.setEnabled(self._can_redo())

    def update_play_action(self, is_playing: bool) -> None:
        """Update Play/Stop action text based on game mode state."""
        if self._action_play is not None:
            if is_playing:
                self._action_play.setText("Stop")
            else:
                self._action_play.setText("Play")

    def update_fullscreen_action(self) -> None:
        """Update fullscreen action checked state."""
        if self._action_fullscreen is not None:
            self._action_fullscreen.setChecked(self._is_fullscreen())

    def update_profiler_action(self) -> None:
        """Update profiler action checked state."""
        if self._action_profiler is not None:
            self._action_profiler.setChecked(self._is_profiler_visible())

    def update_modules_action(self) -> None:
        """Update modules action checked state."""
        if self._action_modules is not None:
            self._action_modules.setChecked(self._is_modules_visible())
