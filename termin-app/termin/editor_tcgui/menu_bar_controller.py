"""Controller for editor menu bar (tcgui version).

Renders a shared ``MenuSpec`` (from ``editor_core``) into tcgui ``MenuItem`` /
``Menu`` widgets.
"""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.menu_bar import MenuBar

from termin.editor_core.menu_bar_model import build_editor_menu_spec
from termin.editor_core.menu_spec import MenuItemSpec, MenuSpec


class MenuBarControllerTcgui:
    """Manages editor menu bar structure and actions for tcgui.

    Builds menus from a shared ``MenuSpec`` and holds references to
    toolkit-specific ``MenuItem`` handles for runtime state updates.
    """

    def __init__(
        self,
        menu_bar: MenuBar,
        # File
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
        # Edit
        on_undo: Callable,
        on_redo: Callable,
        on_settings: Callable,
        on_project_settings: Callable,
        # View
        on_toggle_fullscreen: Callable,
        on_show_spacemouse_settings: Callable,
        # Scene
        on_scene_properties: Callable,
        on_layers_settings: Callable,
        on_shadow_settings: Callable,
        on_pipeline_editor: Callable,
        # Navigation
        on_show_agent_types: Callable,
        # Game
        on_toggle_game_mode: Callable,
        on_run_standalone: Callable,
        # Debug
        on_toggle_profiler: Callable,
        on_toggle_modules: Callable,
        on_show_undo_stack_viewer: Callable,
        on_show_framegraph_debugger: Callable,
        on_show_resource_manager_viewer: Callable,
        on_show_audio_debugger: Callable,
        on_show_core_registry_viewer: Callable,
        on_show_inspect_registry_viewer: Callable,
        on_show_navmesh_registry_viewer: Callable,
        on_show_scene_manager_viewer: Callable,
        # Utils
        on_import_rfmeas: Callable,
        on_export_rfmeas: Callable,
        # State getters
        can_undo: Callable[[], bool],
        can_redo: Callable[[], bool],
        is_fullscreen: Callable[[], bool],
        is_profiler_visible: Callable[[], bool],
        is_modules_visible: Callable[[], bool],
    ):
        # State getters
        self._can_undo = can_undo
        self._can_redo = can_redo
        self._is_fullscreen = is_fullscreen
        self._is_profiler_visible = is_profiler_visible
        self._is_modules_visible = is_modules_visible

        # Toolkit-specific handles for dynamic state
        self._item_undo: MenuItem | None = None
        self._item_redo: MenuItem | None = None
        self._item_play: MenuItem | None = None
        self._item_fullscreen: MenuItem | None = None
        self._item_profiler: MenuItem | None = None
        self._item_modules: MenuItem | None = None

        # Build shared menu spec
        specs = build_editor_menu_spec(
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
            on_toggle_fullscreen=on_toggle_fullscreen,
            is_fullscreen=is_fullscreen,
            on_show_spacemouse_settings=on_show_spacemouse_settings,
            on_scene_properties=on_scene_properties,
            on_layers_settings=on_layers_settings,
            on_shadow_settings=on_shadow_settings,
            on_pipeline_editor=on_pipeline_editor,
            on_show_agent_types=on_show_agent_types,
            on_toggle_game_mode=on_toggle_game_mode,
            on_run_standalone=on_run_standalone,
            on_toggle_profiler=on_toggle_profiler,
            is_profiler_visible=is_profiler_visible,
            on_toggle_modules=on_toggle_modules,
            is_modules_visible=is_modules_visible,
            on_show_undo_stack_viewer=on_show_undo_stack_viewer,
            on_show_framegraph_debugger=on_show_framegraph_debugger,
            on_show_resource_manager_viewer=on_show_resource_manager_viewer,
            on_show_audio_debugger=on_show_audio_debugger,
            on_show_core_registry_viewer=on_show_core_registry_viewer,
            on_show_inspect_registry_viewer=on_show_inspect_registry_viewer,
            on_show_navmesh_registry_viewer=on_show_navmesh_registry_viewer,
            on_show_scene_manager_viewer=on_show_scene_manager_viewer,
            on_import_rfmeas=on_import_rfmeas,
            on_export_rfmeas=on_export_rfmeas,
            # Handle setters — direct assignment, no reflection
            set_undo_handle=self._set_undo_handle,
            set_redo_handle=self._set_redo_handle,
            set_play_handle=self._set_play_handle,
            set_fullscreen_handle=self._set_fullscreen_handle,
            set_profiler_handle=self._set_profiler_handle,
            set_modules_handle=self._set_modules_handle,
        )

        self._render_specs(menu_bar, specs)
        self.update_undo_redo_actions()

    # ------------------------------------------------------------------
    # Handle setters — explicit, no reflection
    # ------------------------------------------------------------------

    def _set_undo_handle(self, h: MenuItem) -> None:
        self._item_undo = h

    def _set_redo_handle(self, h: MenuItem) -> None:
        self._item_redo = h

    def _set_play_handle(self, h: MenuItem) -> None:
        self._item_play = h

    def _set_fullscreen_handle(self, h: MenuItem) -> None:
        self._item_fullscreen = h

    def _set_profiler_handle(self, h: MenuItem) -> None:
        self._item_profiler = h

    def _set_modules_handle(self, h: MenuItem) -> None:
        self._item_modules = h

    def _render_specs(self, menu_bar: MenuBar, specs: list[MenuSpec]) -> None:
        """Render MenuSpec list into tcgui Menu / MenuItem widgets."""
        for spec in specs:
            menu = Menu()
            items = []

            for item in spec.items:
                if item is None:
                    items.append(MenuItem.sep())
                    continue

                mi = MenuItem(
                    item.label,
                    shortcut=item.shortcut,
                    on_click=item.on_click,
                    is_checkable=item.is_checkable,
                    checked=item.state_getter() if item.is_checkable and item.state_getter else False,
                )

                if item.handle_getter:
                    item.handle_getter(mi)

                items.append(mi)

            menu.items = items
            menu_bar.add_menu(spec.name, menu)

    # ------------------------------------------------------------------
    # Public state-update API (called by EditorWindow)
    # ------------------------------------------------------------------

    def update_undo_redo_actions(self) -> None:
        """Update enabled state of Undo/Redo menu items."""
        if self._item_undo is not None:
            self._item_undo.enabled = self._can_undo()
        if self._item_redo is not None:
            self._item_redo.enabled = self._can_redo()

    def update_play_action(self, is_playing: bool) -> None:
        """Update Play/Stop action text based on game mode state."""
        if self._item_play is not None:
            self._item_play.label = "Stop" if is_playing else "Play"

    def update_fullscreen_action(self) -> None:
        """Update fullscreen action checked state."""
        if self._item_fullscreen is not None:
            self._item_fullscreen.checked = self._is_fullscreen()

    def update_profiler_action(self) -> None:
        """Update profiler action checked state."""
        if self._item_profiler is not None:
            self._item_profiler.checked = self._is_profiler_visible()

    def update_modules_action(self) -> None:
        """Update modules action checked state."""
        if self._item_modules is not None:
            self._item_modules.checked = self._is_modules_visible()
