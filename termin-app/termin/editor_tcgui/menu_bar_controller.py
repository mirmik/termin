"""Controller for editor menu bar (tcgui version).

Renders a shared ``MenuSpec`` (from ``editor_core``) into tcgui ``MenuItem`` /
``Menu`` widgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.menu_bar import MenuBar

from termin.editor_core.menu_bar_model import (
    DebugMenuActions,
    EditMenuActions,
    EditorMenuActions,
    EditorMenuHandleSetters,
    EditorMenuSpecConfig,
    EditorMenuStateGetters,
    FileMenuActions,
    GameMenuActions,
    HelpMenuActions,
    NavigationMenuActions,
    SceneMenuActions,
    ViewMenuActions,
    build_editor_menu_spec,
)
from termin.editor_core.menu_spec import MenuSpec


@dataclass(frozen=True, slots=True)
class MenuBarControllerStateGetters:
    can_undo: Callable[[], bool]
    can_redo: Callable[[], bool]
    fullscreen: Callable[[], bool]
    profiler_visible: Callable[[], bool]
    modules_visible: Callable[[], bool]
    camera_frustums_visible: Callable[[], bool]
    surface_edge_debug_tool_enabled: Callable[[], bool]
    raw_detour_path_debug_tool_enabled: Callable[[], bool]


@dataclass(frozen=True, slots=True)
class MenuBarControllerConfig:
    file: FileMenuActions
    edit: EditMenuActions
    view: ViewMenuActions
    scene: SceneMenuActions
    navigation: NavigationMenuActions
    game: GameMenuActions
    debug: DebugMenuActions
    help: HelpMenuActions
    states: MenuBarControllerStateGetters


class MenuBarControllerTcgui:
    """Manages editor menu bar structure and actions for tcgui.

    Builds menus from a shared ``MenuSpec`` and holds references to
    toolkit-specific ``MenuItem`` handles for runtime state updates.
    """

    def __init__(
        self,
        menu_bar: MenuBar,
        config: MenuBarControllerConfig,
    ):
        # State getters
        self._can_undo = config.states.can_undo
        self._can_redo = config.states.can_redo
        self._is_fullscreen = config.states.fullscreen
        self._is_profiler_visible = config.states.profiler_visible
        self._is_modules_visible = config.states.modules_visible
        self._is_camera_frustums_visible = config.states.camera_frustums_visible
        self._is_surface_edge_debug_tool_enabled = config.states.surface_edge_debug_tool_enabled
        self._is_raw_detour_path_debug_tool_enabled = config.states.raw_detour_path_debug_tool_enabled

        # Toolkit-specific handles for dynamic state
        self._item_undo: MenuItem | None = None
        self._item_redo: MenuItem | None = None
        self._item_play: MenuItem | None = None
        self._item_fullscreen: MenuItem | None = None
        self._item_profiler: MenuItem | None = None
        self._item_modules: MenuItem | None = None
        self._item_camera_frustums: MenuItem | None = None
        self._item_surface_edge_debug_tool: MenuItem | None = None
        self._item_raw_detour_path_debug_tool: MenuItem | None = None

        # Build shared menu spec
        specs = build_editor_menu_spec(
            EditorMenuSpecConfig(
                actions=EditorMenuActions(
                    file=config.file,
                    edit=config.edit,
                    view=config.view,
                    scene=config.scene,
                    navigation=config.navigation,
                    game=config.game,
                    debug=config.debug,
                    help=config.help,
                ),
                states=EditorMenuStateGetters(
                    fullscreen=config.states.fullscreen,
                    profiler_visible=config.states.profiler_visible,
                    modules_visible=config.states.modules_visible,
                    camera_frustums_visible=config.states.camera_frustums_visible,
                    surface_edge_debug_tool_enabled=config.states.surface_edge_debug_tool_enabled,
                    raw_detour_path_debug_tool_enabled=config.states.raw_detour_path_debug_tool_enabled,
                ),
                handles=EditorMenuHandleSetters(
                    undo=self._set_undo_handle,
                    redo=self._set_redo_handle,
                    play=self._set_play_handle,
                    fullscreen=self._set_fullscreen_handle,
                    profiler=self._set_profiler_handle,
                    modules=self._set_modules_handle,
                    camera_frustums=self._set_camera_frustums_handle,
                    surface_edge_debug_tool=self._set_surface_edge_debug_tool_handle,
                    raw_detour_path_debug_tool=self._set_raw_detour_path_debug_tool_handle,
                ),
            )
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

    def _set_camera_frustums_handle(self, h: MenuItem) -> None:
        self._item_camera_frustums = h

    def _set_surface_edge_debug_tool_handle(self, h: MenuItem) -> None:
        self._item_surface_edge_debug_tool = h

    def _set_raw_detour_path_debug_tool_handle(self, h: MenuItem) -> None:
        self._item_raw_detour_path_debug_tool = h

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

    def update_camera_frustums_action(self) -> None:
        """Update camera frustums action checked state."""
        if self._item_camera_frustums is not None:
            self._item_camera_frustums.checked = self._is_camera_frustums_visible()

    def update_surface_edge_debug_tool_action(self) -> None:
        """Update surface-edge debug tool action checked state."""
        if self._item_surface_edge_debug_tool is not None:
            self._item_surface_edge_debug_tool.checked = self._is_surface_edge_debug_tool_enabled()

    def update_raw_detour_path_debug_tool_action(self) -> None:
        """Update raw Detour path debug tool action checked state."""
        if self._item_raw_detour_path_debug_tool is not None:
            self._item_raw_detour_path_debug_tool.checked = self._is_raw_detour_path_debug_tool_enabled()
