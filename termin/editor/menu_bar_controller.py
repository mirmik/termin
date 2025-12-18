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
        on_load_material: Callable,
        on_load_components: Callable,
        on_deploy_stdlib: Callable,
        on_exit: Callable,
        on_undo: Callable,
        on_redo: Callable,
        on_settings: Callable,
        on_scene_properties: Callable,
        on_layers_settings: Callable,
        on_toggle_game_mode: Callable,
        on_show_undo_stack_viewer: Callable,
        on_show_framegraph_debugger: Callable,
        on_show_resource_manager_viewer: Callable,
        on_toggle_fullscreen: Callable,
        # State getters
        can_undo: Callable[[], bool],
        can_redo: Callable[[], bool],
        is_fullscreen: Callable[[], bool],
    ):
        self._can_undo = can_undo
        self._can_redo = can_redo
        self._is_fullscreen = is_fullscreen

        self._action_undo: QAction | None = None
        self._action_redo: QAction | None = None
        self._action_play: QAction | None = None
        self._action_fullscreen: QAction | None = None

        self._setup_menu_bar(
            menu_bar,
            on_new_project=on_new_project,
            on_open_project=on_open_project,
            on_new_scene=on_new_scene,
            on_save_scene=on_save_scene,
            on_save_scene_as=on_save_scene_as,
            on_load_scene=on_load_scene,
            on_load_material=on_load_material,
            on_load_components=on_load_components,
            on_deploy_stdlib=on_deploy_stdlib,
            on_exit=on_exit,
            on_undo=on_undo,
            on_redo=on_redo,
            on_settings=on_settings,
            on_scene_properties=on_scene_properties,
            on_layers_settings=on_layers_settings,
            on_toggle_game_mode=on_toggle_game_mode,
            on_show_undo_stack_viewer=on_show_undo_stack_viewer,
            on_show_framegraph_debugger=on_show_framegraph_debugger,
            on_show_resource_manager_viewer=on_show_resource_manager_viewer,
            on_toggle_fullscreen=on_toggle_fullscreen,
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
        on_load_material: Callable,
        on_load_components: Callable,
        on_deploy_stdlib: Callable,
        on_exit: Callable,
        on_undo: Callable,
        on_redo: Callable,
        on_settings: Callable,
        on_scene_properties: Callable,
        on_layers_settings: Callable,
        on_toggle_game_mode: Callable,
        on_show_undo_stack_viewer: Callable,
        on_show_framegraph_debugger: Callable,
        on_show_resource_manager_viewer: Callable,
        on_toggle_fullscreen: Callable,
    ) -> None:
        """Create menu bar structure and connect actions."""
        file_menu = menu_bar.addMenu("File")
        edit_menu = menu_bar.addMenu("Edit")
        view_menu = menu_bar.addMenu("View")
        scene_menu = menu_bar.addMenu("Scene")
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

        file_menu.addSeparator()

        load_material_action = file_menu.addAction("Load Material...")
        load_material_action.triggered.connect(on_load_material)

        load_components_action = file_menu.addAction("Load Components...")
        load_components_action.triggered.connect(on_load_components)

        file_menu.addSeparator()

        deploy_stdlib_action = file_menu.addAction("Deploy Standard Library...")
        deploy_stdlib_action.triggered.connect(on_deploy_stdlib)

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

        # Game menu
        self._action_play = game_menu.addAction("Play")
        self._action_play.setShortcut("F5")
        self._action_play.triggered.connect(on_toggle_game_mode)

        # Debug menu
        debug_action = debug_menu.addAction("Undo/Redo Stack...")
        debug_action.triggered.connect(on_show_undo_stack_viewer)

        tex_debug_action = debug_menu.addAction("Framegraph Texture Viewer...")
        tex_debug_action.triggered.connect(on_show_framegraph_debugger)

        resource_debug_action = debug_menu.addAction("Resource Manager...")
        resource_debug_action.triggered.connect(on_show_resource_manager_viewer)

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
