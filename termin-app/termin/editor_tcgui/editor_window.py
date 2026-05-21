"""EditorWindowTcgui — main editor window implemented with tcgui."""

from __future__ import annotations

import os
import time
import shutil
from pathlib import Path
from typing import Callable, Optional

from tcbase import log
from tcbase._geom_native import Vec3

from tcgui.widgets.ui import UI
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.splitter import Splitter
from tcgui.widgets.tabs import TabView
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.status_bar import StatusBar
from tcgui.widgets.viewport3d import Viewport3D
from tcgui.widgets.label import Label
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.message_box import MessageBox

from termin.editor_core.undo_stack import UndoStack, UndoCommand
from termin.editor_core.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    RenameEntityCommand,
)
from termin.engine import SceneManager, scene as engine_scene
from termin.editor_core.resource_loader import ResourceLoader
from termin.editor_core.project_file_watcher import ProjectFileWatcher
from termin.editor_core.default_preloaders import register_default_preloaders
from termin.editor_core.prefab_edit_controller import PrefabEditController
from termin.editor_core.settings import EditorSettings
from termin.editor_core.signal import Signal
from termin.assets.resources import ResourceManager
from termin.visualization.platform.backends.fbo_backend import FBOSurface
from termin.visualization.core.scene import default_scene_extensions

from termin.editor_core.editor_state_io import EditorStateIO
from termin.editor_tcgui.menu_bar_controller import MenuBarControllerTcgui
from termin.editor_tcgui.scene_tree_controller import SceneTreeControllerTcgui
from termin.editor_tcgui.inspector_controller import InspectorControllerTcgui
from termin.editor_tcgui.project_browser import ProjectBrowserTcgui
from termin.editor_tcgui.default_component_editor_extensions import (
    register_default_component_editor_extensions,
)
from termin.editor_tcgui.editor_camera_ui_controller import EditorCameraUIController

SceneMode = engine_scene.SceneMode


class EditorWindowTcgui:
    """Main editor window for the tcgui frontend.

    Does not inherit from any UI framework class — the UI is built in ``build(ui)``.
    Domain logic is identical to the Qt version.
    """

    def __init__(
        self,
        world,
        initial_scene,
        scene_manager: SceneManager,
        offscreen_context=None,
        ctx=None,
        main_window=None,
    ) -> None:
        self._world = world
        self._offscreen_context = offscreen_context
        # Process-global tgfx2 context — the editor's FBOSurface and
        # RenderingControllerTcgui allocate their render targets here.
        # Supplied by run_editor_tcgui; under M4 it will come from
        # BackendWindow (replacing offscreen_context entirely).
        self._ctx = ctx
        self._main_window = main_window
        self._should_close = False
        self._ui: UI | None = None

        self.undo_stack = UndoStack()
        self.undo_stack_changed = Signal()

        # Resource manager
        self.resource_manager = ResourceManager.instance()
        self.resource_manager.register_builtin_components()
        self.resource_manager.register_builtin_frame_passes()
        self.resource_manager.register_builtin_post_effects()
        self.resource_manager.register_component(
            "EditorCameraUIController",
            EditorCameraUIController,
        )
        register_default_component_editor_extensions()

        # Scene manager
        self.scene_manager = scene_manager
        self.scene_manager.set_on_before_scene_close(self._on_before_scene_close)
        # Pump EditorInteractionSystem's pending press / release / hover at the
        # exact moment the render finishes — matches the Qt editor. Without
        # this hook the press/hover events that reach EditorViewportInput-
        # Manager just queue in _pending_* and never get processed, so
        # picking / selection / gizmo hover all silently no-op.
        self.scene_manager.set_on_after_render(self._after_render)

        self._editor_data: dict[str, dict] = {}
        self._editor_scene_name = "untitled"

        if initial_scene is not None:
            self.scene_manager.register_scene(self._editor_scene_name, initial_scene.scene_handle())
            self.scene_manager.set_mode(self._editor_scene_name, SceneMode.STOP)
        else:
            self.scene_manager.create_scene(self._editor_scene_name, default_scene_extensions())
            self.scene_manager.set_mode(self._editor_scene_name, SceneMode.STOP)

        # Controllers (set in build())
        self._menu_bar_controller: MenuBarControllerTcgui | None = None
        self.scene_tree_controller: SceneTreeControllerTcgui | None = None
        self._inspector_controller: InspectorControllerTcgui | None = None
        self._project_browser: ProjectBrowserTcgui | None = None
        self._fbo_surface: FBOSurface | None = None
        self._viewport_widget: Viewport3D | None = None
        self._status_bar: StatusBar | None = None
        self._console_area: TextArea | None = None
        self._editor_display = None
        self._interaction_system = None
        self.gizmo_manager = None
        self._editor_attachment = None
        self._rendering_controller = None
        self._editor_viewport_input_managers: list = []
        self._ar_logged: bool = False
        # Owns DisplayInputRouter instances that route surface events to the
        # per-viewport EditorViewportInputManagers. Populated by
        # _attach_editor_input_router() after the editor display's input
        # managers are created. Without this the surface's input_manager_ptr
        # stays on the default (scene-pipeline) router and Viewport3D never
        # hits the editor picking / hover / gizmo paths.
        self._display_routers: dict[int, object] = {}
        self._current_project_path: str | None = None
        self._project_name: str | None = None
        self._is_fullscreen: bool = False
        self._pre_fullscreen_state: dict | None = None
        self._editor_state_io: EditorStateIO | None = None
        self._viewport_list = None
        self._left_tabs: TabView | None = None
        self._right_scroll: ScrollArea | None = None
        self._bottom_tabs: TabView | None = None
        self._menu_bar_widget: MenuBar | None = None
        self._left_splitter: Splitter | None = None
        self._right_splitter: Splitter | None = None
        self._bottom_splitter: Splitter | None = None
        self._center_tabs: TabView | None = None
        self._play_button = None
        self._pause_button = None
        self._prefab_toolbar: HStack | None = None
        self._prefab_toolbar_label: Label | None = None
        self._save_prefab_button = None
        self._exit_prefab_button = None
        self._pre_prefab_scene_name: str | None = None
        self.prefab_edit_controller: PrefabEditController | None = None
        # Game mode state + transitions live in GameModeModel. The model is
        # created after editor_attachment/rendering_controller exist (end of build()).
        self._game_mode_model = None
        self._saved_tree_expanded_uuids: list[str] | None = None
        self._spacemouse = None

        # Debug panels (Profiler / Modules)
        self._debug_panel: TabView | None = None
        self._debug_splitter: Splitter | None = None
        self._profiler_panel = None
        self._modules_panel = None
        self._profiler_visible: bool = False
        self._modules_visible: bool = False
        self._last_profiler_update: float = 0.0
        self._last_modules_update: float = 0.0
        self._framegraph_debugger = None
        self._surface_edge_debug_tool = None
        self._scene_event_subscription = None
        self._scene_tree_rebuild_pending: bool = False
        self._viewport_click_interceptor: Callable[
            [
                object,
                float, float,
                bool, float, float, float,
                float, float, float, float,
                bool, float, float, float,
                float, float, float,
                int, int, int, int,
            ],
            bool,
        ] | None = None
        self._viewport_click_interceptors: list[Callable] = []
        self._viewport_overlay_drawers: list[Callable[[], None]] = []
        self._active_component_editor_extension = None

        # Setup ResourceLoader and ProjectFileWatcher
        self._resource_loader = ResourceLoader(
            resource_manager=self.resource_manager,
            get_scene=lambda: self.scene,
            get_project_path=self._get_project_path,
            on_resource_reloaded=self._on_resource_reloaded,
            log_message=self._log_to_console,
        )
        self._resource_loader.scan_builtin_components()

        self._project_file_watcher = ProjectFileWatcher(
            on_resource_reloaded=self._on_resource_reloaded,
        )
        self._register_file_processors()

        # Editor interaction system
        from termin._native.editor import EditorInteractionSystem
        self._interaction_system = EditorInteractionSystem()
        EditorInteractionSystem.set_instance(self._interaction_system)
        self.gizmo_manager = self._interaction_system.gizmo_manager

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def build(self, ui: UI) -> None:
        """Create and attach the tcgui widget tree to ui."""
        self._ui = ui

        from tcgui.widgets.units import pct

        root = VStack()
        root.preferred_width = pct(100)
        root.preferred_height = pct(100)
        root.spacing = 0

        # Menu bar
        menu_bar = MenuBar()
        self._menu_bar_widget = menu_bar
        root.add_child(menu_bar)

        # Main area: HStack with Splitter handles
        # Left: TabView [Scene | Rendering]
        # Center: Viewport3D (stretches)
        # Right: ScrollArea > VStack [Inspector]
        from tcgui.widgets.units import px
        main_area = HStack()
        main_area.stretch = True
        main_area.spacing = 0

        # --- Left panel ---
        left_tabs = TabView()
        self._left_tabs = left_tabs
        left_tabs.preferred_width = px(280)

        scene_tab_content = VStack()
        scene_tab_content.spacing = 4

        from tcgui.widgets.tree import TreeWidget
        scene_tree = TreeWidget()
        scene_tree.stretch = True
        scene_tab_content.add_child(scene_tree)
        left_tabs.add_tab("Scene", scene_tab_content)

        from termin.editor_tcgui.viewport_list_widget import ViewportListWidgetTcgui
        self._viewport_list = ViewportListWidgetTcgui()
        self._viewport_list.stretch = True
        left_tabs.add_tab("Rendering", self._viewport_list)

        main_area.add_child(left_tabs)
        self._left_splitter = Splitter(target=left_tabs, side="right")
        main_area.add_child(self._left_splitter)

        # --- Center: toolbar + TabView ---
        from tcgui.widgets.button import Button

        center_area = VStack()
        center_area.stretch = True
        center_area.spacing = 0

        # Toolbar with Play/Stop and Pause buttons
        toolbar = HStack()
        toolbar.preferred_height = px(32)
        toolbar.spacing = 4
        toolbar.alignment = "center"

        spacer_left = Label()
        spacer_left.stretch = True
        spacer_left.mouse_transparent = True
        toolbar.add_child(spacer_left)

        play_btn = Button()
        play_btn.text = "Play"
        play_btn.preferred_width = px(60)
        play_btn.preferred_height = px(24)
        play_btn.on_click = self._toggle_game_mode
        self._play_button = play_btn
        toolbar.add_child(play_btn)

        pause_btn = Button()
        pause_btn.text = "Pause"
        pause_btn.preferred_width = px(60)
        pause_btn.preferred_height = px(24)
        pause_btn.visible = False
        pause_btn.on_click = self._toggle_pause
        self._pause_button = pause_btn
        toolbar.add_child(pause_btn)

        prefab_toolbar = HStack()
        prefab_toolbar.spacing = 4
        prefab_toolbar.visible = False
        self._prefab_toolbar = prefab_toolbar

        prefab_label = Label()
        prefab_label.text = "Editing Prefab"
        prefab_label.mouse_transparent = True
        self._prefab_toolbar_label = prefab_label
        prefab_toolbar.add_child(prefab_label)

        save_prefab_btn = Button()
        save_prefab_btn.text = "Save"
        save_prefab_btn.preferred_width = px(60)
        save_prefab_btn.preferred_height = px(24)
        save_prefab_btn.on_click = self._save_prefab
        self._save_prefab_button = save_prefab_btn
        prefab_toolbar.add_child(save_prefab_btn)

        exit_prefab_btn = Button()
        exit_prefab_btn.text = "Exit"
        exit_prefab_btn.preferred_width = px(60)
        exit_prefab_btn.preferred_height = px(24)
        exit_prefab_btn.on_click = self._exit_prefab_editing
        self._exit_prefab_button = exit_prefab_btn
        prefab_toolbar.add_child(exit_prefab_btn)

        toolbar.add_child(prefab_toolbar)

        spacer_right = Label()
        spacer_right.stretch = True
        spacer_right.mouse_transparent = True
        toolbar.add_child(spacer_right)

        center_area.add_child(toolbar)

        # Center tabs: Editor + dynamic display tabs
        center_tabs = TabView()
        center_tabs.stretch = True
        self._center_tabs = center_tabs

        self._viewport_widget = Viewport3D()
        self._viewport_widget.stretch = True
        self._viewport_widget.on_external_drag = self._on_viewport_external_drag
        self._viewport_widget.on_external_drop = self._on_viewport_external_drop
        center_tabs.add_tab("Editor", self._viewport_widget)

        center_area.add_child(center_tabs)
        main_area.add_child(center_area)

        # --- Right panel: Inspector ---
        right_scroll = ScrollArea()
        self._right_scroll = right_scroll
        right_scroll.preferred_width = px(430)
        inspector_container = VStack()
        inspector_container.spacing = 4
        right_scroll.add_child(inspector_container)
        self._right_splitter = Splitter(target=right_scroll, side="left")
        main_area.add_child(self._right_splitter)
        main_area.add_child(right_scroll)

        # --- Debug panel: Profiler / Modules (right of inspector, hidden) ---
        from termin.editor_tcgui.profiler_panel import ProfilerPanel
        from termin.editor_tcgui.modules_panel import ModulesPanel

        debug_panel = TabView()
        debug_panel.preferred_width = px(350)
        debug_panel.visible = False
        self._debug_panel = debug_panel

        self._profiler_panel = ProfilerPanel()
        debug_panel.add_tab("Profiler", self._profiler_panel)

        self._modules_panel = ModulesPanel()
        debug_panel.add_tab("Modules", self._modules_panel)

        self._debug_splitter = Splitter(target=debug_panel, side="left")
        self._debug_splitter.visible = False
        main_area.add_child(self._debug_splitter)
        main_area.add_child(debug_panel)

        root.add_child(main_area)

        # --- Bottom: TabView [Project | Console] ---
        bottom_tabs = TabView()
        self._bottom_tabs = bottom_tabs
        bottom_tabs.preferred_height = px(380)
        self._bottom_splitter = Splitter(target=bottom_tabs, side="top")
        root.add_child(self._bottom_splitter)

        from tcgui.widgets.hstack import HStack as HStackInner
        from tcgui.widgets.vstack import VStack as VStackInner
        from tcgui.widgets.tree import TreeWidget as TreeWidgetInner
        from tcgui.widgets.file_grid_widget import FileGridWidget
        from tcgui.widgets.units import px as pxu

        project_tab_content = HStackInner()
        project_tab_content.spacing = 0
        project_tab_content.stretch = True

        project_dir_tree = TreeWidgetInner()
        project_dir_tree.preferred_width = pxu(200)
        project_dir_tree.stretch = True

        from tcgui.widgets.splitter import Splitter as SplitterInner
        from tcgui.widgets.scroll_area import ScrollArea as ScrollAreaInner

        dir_tree_scroll = ScrollAreaInner()
        dir_tree_scroll.preferred_width = pxu(200)
        dir_tree_scroll.add_child(project_dir_tree)

        project_file_list = FileGridWidget()
        project_file_list.stretch = True
        project_file_list.empty_text = "Select a directory"

        project_file_column = VStackInner()
        project_file_column.stretch = True
        project_file_column.spacing = 4

        project_breadcrumb = HStackInner()
        project_breadcrumb.preferred_height = pxu(24)
        project_breadcrumb.spacing = 2

        project_file_column.add_child(project_breadcrumb)
        project_file_column.add_child(project_file_list)

        project_tab_content.add_child(dir_tree_scroll)
        project_tab_content.add_child(SplitterInner(target=dir_tree_scroll, side="right"))
        project_tab_content.add_child(project_file_column)

        bottom_tabs.add_tab("Project", project_tab_content)

        self._console_area = TextArea()
        self._console_area.read_only = True
        bottom_tabs.add_tab("Console", self._console_area)
        root.add_child(bottom_tabs)

        # --- Status bar ---
        self._status_bar = StatusBar()
        root.add_child(self._status_bar)

        ui.root = root

        # Setup FBO surface and Viewport3D
        self._setup_viewport()

        # Dialog service (shared between controllers)
        from termin.editor_tcgui.tcgui_dialog_service import TcguiDialogService
        self._dialog_service = TcguiDialogService()
        self._dialog_service.ui = ui

        # Setup scene tree controller
        self.scene_tree_controller = SceneTreeControllerTcgui(
            tree_widget=scene_tree,
            scene=self.scene,
            undo_handler=self.push_undo_command,
            dialog_service=self._dialog_service,
            on_object_selected=self._on_tree_object_selected,
            request_viewport_update=self._request_viewport_update,
        )

        # Setup inspector controller
        self._inspector_controller = InspectorControllerTcgui(
            container=inspector_container,
            resource_manager=self.resource_manager,
            push_undo_command=self.push_undo_command,
            on_transform_changed=self._on_inspector_transform_changed,
            on_component_changed=self._on_inspector_component_changed,
            on_material_changed=self._request_viewport_update,
            on_display_changed=self._request_viewport_update,
            on_viewport_changed=self._request_viewport_update,
            on_pipeline_changed=self._request_viewport_update,
            on_render_target_changed=self._request_viewport_update,
            on_edit_pipeline=self._open_pipeline_file_for_edit,
            dialog_service=self._dialog_service,
        )
        self._inspector_controller.on_component_selected = self._on_inspector_component_selected
        self._inspector_controller.on_component_cleared = self._clear_component_editor_extension
        self._inspector_controller.set_scene(self.scene)
        self._observe_scene_events(self.scene)
        self._inspector_controller.set_render_target_scene_getter(
            lambda: [
                self.scene_manager.get_scene(name)
                for name in self.scene_manager.scene_names()
                if self.scene_manager.get_scene(name) is not None
            ]
        )

        # Setup project browser
        self._project_browser = ProjectBrowserTcgui(
            dir_tree=project_dir_tree,
            file_list=project_file_list,
            breadcrumb=project_breadcrumb,
            dialog_service=self._dialog_service,
            on_file_activated=self._on_project_file_activated,
            on_file_selected=self._on_project_file_selected,
        )

        # Setup rendering controller and editor display
        if self._editor_display is not None:
            from termin.editor_core.editor_pipeline import make_editor_pipeline
            from termin.editor_core.editor_scene_attachment import EditorSceneAttachment
            from termin.editor_tcgui.rendering_controller import RenderingControllerTcgui
            from termin.engine import RenderingManager

            # Create rendering controller (registers factories with RenderingManager)
            self._rendering_controller = RenderingControllerTcgui(
                viewport_list_widget=self._viewport_list,
                offscreen_context=self._offscreen_context,
                ctx=self._ctx,
                get_scene=lambda: self.scene,
                make_editor_pipeline=make_editor_pipeline,
                on_request_update=self._request_viewport_update,
                on_rendering_changed=self._on_rendering_changed,
                on_display_selected=self._on_render_display_selected,
                on_viewport_selected=self._on_render_viewport_selected,
                on_entity_selected=self._on_render_entity_selected,
                on_render_target_selected=self._on_render_target_selected,
            )

            self._rendering_controller.set_center_tabs(self._center_tabs)

            # Register editor display and mark it as non-serializable
            self._rendering_controller.add_editor_display(self._editor_display, "Editor")
            self._rendering_controller.set_editor_display_ptr(self._editor_display.tc_display_ptr)

            # Create editor scene attachment (now with rendering controller)
            self._editor_attachment = EditorSceneAttachment(
                display=self._editor_display,
                rendering_controller=self._rendering_controller,
                make_editor_pipeline=make_editor_pipeline,
            )
            self.attach_editor_to_scene(self._editor_scene_name, restore_state=False)
            self.attach_scene_to_render(self._editor_scene_name)

            # GameModeModel owns Play/Stop/Pause state + transitions.
            from termin.editor_core.game_mode_model import GameModeModel
            self._game_mode_model = GameModeModel(
                scene_manager=self.scene_manager,
                editor_connector=self,
                rendering_controller=self._rendering_controller,
                get_editor_scene_name=lambda: self._editor_scene_name,
                scene_tree_controller=self.scene_tree_controller,
                render_connector=self,
            )
            self._game_mode_model.mode_entered.connect(self._on_game_mode_entered)

            # EditorStateIO for save/load
            self._editor_state_io = EditorStateIO(
                self._editor_attachment,
                self._interaction_system,
            )
            self._editor_state_io.get_scene = lambda: self.scene
            self._editor_state_io.on_entity_selected = self._on_entity_selected_from_state
            self._editor_state_io.get_displays_data = self._rendering_controller.get_displays_data
            self._editor_state_io.set_displays_data = self._rendering_controller.set_displays_data
            if self.scene_tree_controller is not None:
                self._editor_state_io.get_expanded_entity_uuids = (
                    self.scene_tree_controller.get_expanded_entity_uuids
                )
                self._editor_state_io.set_expanded_entity_uuids = (
                    self.scene_tree_controller.set_expanded_entity_uuids
                )

            self._interaction_system.selection.on_selection_changed = self._on_selection_changed
            self._interaction_system.selection.on_hover_changed = self._on_hover_changed
            self._interaction_system.on_request_update = self._request_viewport_update
            self._interaction_system.on_entity_click = self._on_editor_viewport_click
            # Transform gizmo drag-end → push an undo command, same as the
            # Qt editor (editor_window.py::_on_transform_end).
            self._interaction_system.on_transform_end = self._on_transform_end

        self._on_rendering_changed()

        # Setup menu bar (after scene tree and inspector are ready)
        self._setup_menu_bar(menu_bar)
        menu_bar.register_shortcuts(ui)

        # Load settings and last scene
        EditorSettings.instance().init_text_editor_if_empty()
        self.prefab_edit_controller = PrefabEditController(
            scene_manager=self.scene_manager,
            resource_manager=self.resource_manager,
            on_mode_changed=self._on_prefab_mode_changed,
            on_request_update=self._request_viewport_update,
            log_message=self._log_to_console,
            get_editor_scene_name=lambda: self._editor_scene_name,
        )
        self._restore_project()
        # _rescan_file_resources is called inside _load_project, don't call again
        if self._current_project_path is None:
            self._rescan_file_resources()
        self._load_last_scene()

        self._update_window_title()

    def _setup_editor_viewport_input_managers(self, display) -> None:
        """Create EditorViewportInputManager for each viewport on the display."""
        from termin._native.editor import EditorViewportInputManager

        self._editor_viewport_input_managers.clear()

        display_id = display.tc_display_ptr
        for vp in display.viewports:
            vp_idx, vp_gen = vp._viewport_handle()
            editor_im = EditorViewportInputManager(vp_idx, vp_gen, display_id)
            self._editor_viewport_input_managers.append(editor_im)

    def _attach_editor_input_router(self, display) -> None:
        """Wire a DisplayInputRouter onto the editor display's surface.

        This is the critical link for picking / hover / gizmo: the router
        dispatches mouse events to the EditorViewportInputManagers that
        `_setup_editor_viewport_input_managers()` already created, which
        in turn drive the C++ EditorInteractionSystem. Without it the
        surface stays on the default scene-pipeline input_manager and
        Viewport3D never sees editor-aware input.
        """
        from termin.display import DisplayInputRouter

        display_id = display.tc_display_ptr
        router = DisplayInputRouter(display_id)
        self._display_routers[display_id] = router

        surface = display.surface
        if surface is not None:
            surface.set_input_manager(router.tc_input_manager_ptr)

        # Viewport3D cached the old input_manager_ptr during set_surface();
        # refresh it now so the widget dispatches into the new router.
        if self._viewport_widget is not None:
            self._viewport_widget._connect_input(display)

    def _sync_attachment_refs(self) -> None:
        if self._editor_attachment is None:
            self.camera = None
            self.editor_entities = None
            self.viewport = None
            return
        self.camera = self._editor_attachment.camera
        self.editor_entities = self._editor_attachment.editor_entities
        self.viewport = self._editor_attachment.viewport
        if self._editor_attachment._display is not None:
            self._setup_editor_viewport_input_managers(self._editor_attachment._display)
            self._attach_editor_input_router(self._editor_attachment._display)

    def attach_editor_to_scene(
        self,
        scene_name: str,
        restore_state: bool = True,
        transfer_camera_state: bool = False,
        update_editor_scene_name: bool = True,
    ) -> bool:
        scene = self.scene_manager.get_scene(scene_name)
        if scene is None:
            log.error(f"Cannot attach editor to scene '{scene_name}': not found")
            return False
        if self._editor_attachment is None:
            log.error("Cannot attach editor: EditorSceneAttachment not available")
            return False

        if self._editor_attachment.scene is not scene:
            self._editor_attachment.attach(
                scene,
                restore_state=restore_state,
                transfer_camera_state=transfer_camera_state,
            )

        if update_editor_scene_name:
            self._editor_scene_name = scene_name
        self.scene_manager.set_mode(scene_name, SceneMode.STOP)
        self._sync_attachment_refs()

        if self._interaction_system is not None:
            self._interaction_system.selection.clear()
            self._interaction_system.set_gizmo_target(None)

        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(scene)
            self.scene_tree_controller.rebuild()
        self._observe_scene_events(scene)

        if self._inspector_controller is not None:
            self._inspector_controller.set_scene(scene)
            self._inspector_controller.clear()

        self._update_window_title()
        self._request_viewport_update()
        return True

    def detach_editor_from_scene(
        self,
        save_state: bool = True,
        clear_editor_scene_name: bool = True,
    ) -> bool:
        if self._editor_attachment is None:
            log.error("Cannot detach editor: EditorSceneAttachment not available")
            return False
        if self._editor_attachment.scene is None:
            return True

        self._editor_attachment.detach(save_state=save_state)
        self._sync_attachment_refs()
        if clear_editor_scene_name:
            self._editor_scene_name = None

        if self._interaction_system is not None:
            self._interaction_system.selection.clear()
            self._interaction_system.set_gizmo_target(None)

        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(None)
            self.scene_tree_controller.rebuild()
        self._observe_scene_events(None)

        if self._inspector_controller is not None:
            self._inspector_controller.set_scene(None)
            self._inspector_controller.clear()

        self._update_window_title()
        self._request_viewport_update()
        return True

    def sync_scene_render_state(self, scene_name: str) -> bool:
        from termin.editor_core.render_scene_attachment import RenderSceneAttachment
        return RenderSceneAttachment(
            self.scene_manager,
            self._rendering_controller,
            log.error,
        ).sync_scene_render_state(scene_name)

    def attach_scene_to_render(self, scene_name: str) -> bool:
        from termin.editor_core.render_scene_attachment import RenderSceneAttachment
        return RenderSceneAttachment(
            self.scene_manager,
            self._rendering_controller,
            log.error,
        ).attach_scene_to_render(scene_name)

    def detach_scene_from_render(
        self,
        scene_name: str,
        save_state: bool = True,
    ) -> bool:
        from termin.editor_core.render_scene_attachment import RenderSceneAttachment
        return RenderSceneAttachment(
            self.scene_manager,
            self._rendering_controller,
            log.error,
        ).detach_scene_from_render(scene_name, save_state=save_state)

    def _setup_viewport(self) -> None:
        """Create FBO surface, editor display, and connect to Viewport3D."""
        # The old OffscreenContext.make_current() is a no-op under the
        # single-device BackendWindow architecture — the process has one
        # tgfx2 device and on GL its context is always current. Under
        # Vulkan there's nothing to make current anyway. Keep the call
        # only when a legacy offscreen_context was actually passed in,
        # for parity with tests that still supply one.
        if self._offscreen_context is not None:
            self._offscreen_context.make_current()
        self._fbo_surface = FBOSurface(self._ctx.device, 800, 600)

        try:
            from termin.visualization.core.display import Display
            display = Display(surface=self._fbo_surface, name="Editor")
            display.connect_input()
            self._editor_display = display

            if self._viewport_widget is not None:
                self._viewport_widget.on_before_resize = self._on_before_viewport_resize
                self._viewport_widget.set_surface(self._fbo_surface, display)

        except Exception as e:
            log.error(f"EditorWindowTcgui: failed to create editor display: {e}")

    def _on_before_viewport_resize(self, new_w: int, new_h: int) -> None:
        """Called by Viewport3D before FBO is recreated."""
        if self._editor_display is not None:
            self.scene_manager.request_render()

    def _on_fbo_resized(self, w: int, h: int) -> None:
        """Called after FBO is recreated. FBOSurface already notified the C++ surface."""
        self._request_viewport_update()

    def _setup_menu_bar(self, menu_bar: MenuBar) -> None:
        self._menu_bar_controller = MenuBarControllerTcgui(
            menu_bar=menu_bar,
            on_new_project=self._new_project,
            on_open_project=self._open_project,
            on_new_scene=self._new_scene,
            on_save_scene=self._save_scene,
            on_save_scene_as=self._save_scene_as,
            on_load_scene=self._load_scene,
            on_close_scene=self._close_scene,
            on_load_material=self._load_material_from_file,
            on_load_components=self._load_components_from_file,
            on_deploy_stdlib=self._deploy_stdlib,
            on_migrate_spec_to_meta=self._migrate_spec_to_meta,
            on_exit=self.close,
            on_undo=self.undo,
            on_redo=self.redo,
            on_settings=self._show_settings,
            on_project_settings=self._show_project_settings,
            on_toggle_fullscreen=self._toggle_fullscreen,
            on_show_spacemouse_settings=self._show_spacemouse_settings,
            on_scene_properties=self._show_scene_properties,
            on_layers_settings=self._show_layers_settings,
            on_shadow_settings=self._show_shadow_settings,
            on_pipeline_editor=self._show_pipeline_editor,
            on_show_agent_types=self._show_agent_types,
            on_show_navmesh_areas=self._show_navmesh_areas,
            on_toggle_game_mode=self._toggle_game_mode,
            on_build_project=self._build_project,
            on_build_android=self._build_android,
            on_run_build=self._run_build,
            on_run_standalone=self._run_standalone,
            on_toggle_profiler=self._toggle_profiler,
            on_toggle_modules=self._toggle_modules,
            on_show_undo_stack_viewer=self._show_undo_stack_viewer,
            on_show_framegraph_debugger=self._show_framegraph_debugger,
            on_show_resource_manager_viewer=self._show_resource_manager_viewer,
            on_show_audio_debugger=self._show_audio_debugger,
            on_show_core_registry_viewer=self._show_core_registry_viewer,
            on_show_inspect_registry_viewer=self._show_inspect_registry_viewer,
            on_show_navmesh_registry_viewer=self._show_navmesh_registry_viewer,
            on_show_scene_manager_viewer=self._show_scene_manager_viewer,
            on_toggle_surface_edge_debug_tool=self._toggle_surface_edge_debug_tool,
            is_surface_edge_debug_tool_enabled=self._is_surface_edge_debug_tool_enabled,
            can_undo=lambda: self.undo_stack.can_undo,
            can_redo=lambda: self.undo_stack.can_redo,
            is_fullscreen=lambda: self._is_fullscreen,
            is_profiler_visible=lambda: self._profiler_visible,
            is_modules_visible=lambda: self._modules_visible,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def scene(self):
        if self._editor_scene_name:
            return self.scene_manager.get_scene(self._editor_scene_name)
        return None

    def should_close(self) -> bool:
        return self._should_close

    def set_viewport_click_interceptor(
        self,
        callback: Callable[
            [
                object,
                float, float,
                bool, float, float, float,
                float, float, float, float,
                bool, float, float, float,
                float, float, float,
                int, int, int, int,
            ],
            bool,
        ] | None,
    ) -> None:
        self._viewport_click_interceptor = callback

    def add_viewport_click_interceptor(self, callback: Callable) -> None:
        for existing in self._viewport_click_interceptors:
            if existing == callback:
                return
        self._viewport_click_interceptors.append(callback)

    def remove_viewport_click_interceptor(self, callback: Callable) -> None:
        kept = []
        for existing in self._viewport_click_interceptors:
            if existing != callback:
                kept.append(existing)
        self._viewport_click_interceptors = kept

    def add_viewport_overlay_drawer(self, callback: Callable[[], None]) -> None:
        for existing in self._viewport_overlay_drawers:
            if existing == callback:
                return
        self._viewport_overlay_drawers.append(callback)
        self._request_viewport_update()

    def remove_viewport_overlay_drawer(self, callback: Callable[[], None]) -> None:
        kept = []
        for existing in self._viewport_overlay_drawers:
            if existing != callback:
                kept.append(existing)
        self._viewport_overlay_drawers = kept
        self._request_viewport_update()

    def _on_inspector_component_selected(self, entity, component_ref) -> None:
        self._clear_component_editor_extension()
        type_name = component_ref.type_name
        from termin.editor_tcgui.component_editor_extension import (
            create_component_editor_extension,
        )

        extension = create_component_editor_extension(type_name)
        if extension is None:
            return

        try:
            extension.attach(self, entity, component_ref)
            panel = extension.build_panel()
        except Exception as e:
            log.error(
                "[EditorWindowTcgui] component editor extension attach failed "
                f"for '{type_name}': {e}"
            )
            try:
                extension.detach()
            except Exception as detach_error:
                log.error(
                    "[EditorWindowTcgui] component editor extension detach failed "
                    f"after attach error for '{type_name}': {detach_error}"
                )
            return

        self._active_component_editor_extension = extension
        if self._inspector_controller is not None:
            self._inspector_controller.set_component_extension_panel(panel)

    def _clear_component_editor_extension(self) -> None:
        extension = self._active_component_editor_extension
        self._active_component_editor_extension = None
        if self._inspector_controller is not None:
            self._inspector_controller.clear_component_extension_panel()
        if extension is None:
            return
        try:
            extension.detach()
        except Exception as e:
            log.error(f"[EditorWindowTcgui] component editor extension detach failed: {e}")

    def _toggle_surface_edge_debug_tool(self) -> None:
        if self._surface_edge_debug_tool is None:
            from termin.editor_tcgui.surface_edge_debug_tool import SurfaceEdgeDebugTool
            self._surface_edge_debug_tool = SurfaceEdgeDebugTool(self)
        self._surface_edge_debug_tool.toggle()
        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_surface_edge_debug_tool_action()

    def _is_surface_edge_debug_tool_enabled(self) -> bool:
        if self._surface_edge_debug_tool is None:
            return False
        return self._surface_edge_debug_tool.enabled()

    def _on_viewport_external_drag(self, event) -> bool:
        if event.payload.kind != "project_file":
            return False
        data = event.payload.data
        if not isinstance(data, dict):
            return False
        return data.get("extension") == ".glb"

    def _on_viewport_external_drop(self, event) -> bool:
        if not self._on_viewport_external_drag(event):
            return False
        data = event.payload.data
        if not isinstance(data, dict):
            return False
        path = data.get("path")
        if not isinstance(path, str):
            return False
        if self.scene_tree_controller is None:
            log.error("[EditorWindowTcgui] GLB viewport drop failed: scene tree controller is not available")
            return False
        world_pos = self._world_position_for_viewport_drop(event.x, event.y)
        self.scene_tree_controller.operations.drop_glb(path, None, world_position=world_pos)
        return True

    def _world_position_for_viewport_drop(self, x: float, y: float) -> tuple[float, float, float]:
        fallback = self._fallback_drop_position()
        if self._interaction_system is None or self._editor_display is None:
            return fallback
        if not self._editor_display.viewports:
            return fallback
        if self._viewport_widget is None:
            return fallback

        viewport = self._editor_display.viewports[0]
        vp_idx, vp_gen = viewport._viewport_handle()
        local_x = float(x - self._viewport_widget.x)
        local_y = float(y - self._viewport_widget.y)
        try:
            pick = self._interaction_system.pick_surface_at(
                local_x, local_y, vp_idx, vp_gen, self._editor_display.tc_display_ptr,
            )
        except Exception as e:
            log.error(f"[EditorWindowTcgui] GLB viewport drop pick failed: {e}")
            return fallback
        if bool(pick["has_world_point"]):
            point = pick["world_point"]
            return (float(point[0]), float(point[1]), float(point[2]))
        return fallback

    def _fallback_drop_position(self) -> tuple[float, float, float]:
        if self.camera is None or self.camera.entity is None:
            return (0.0, 0.0, 0.0)
        cam_pose = self.camera.entity.transform.global_pose()
        cam_pos = cam_pose.lin
        rot = cam_pose.rotation_matrix()
        forward = rot[:, 1]
        return (
            float(cam_pos[0] + forward[0] * 5.0),
            float(cam_pos[1] + forward[1] * 5.0),
            float(cam_pos[2] + forward[2] * 5.0),
        )

    def world_point_on_oxy_plane(self, x: float, y: float) -> tuple[float, float, float] | None:
        return self.world_point_on_plane(x, y, (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), "OXY plane")

    def world_ray_from_viewport_point(
        self,
        x: float,
        y: float,
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        if self.camera is None or self.camera.entity is None:
            log.error("[EditorWindowTcgui] viewport ray failed: editor camera is not available")
            return None
        if self._viewport_widget is None:
            log.error("[EditorWindowTcgui] viewport ray failed: viewport widget is not available")
            return None

        viewport_rect = (
            0,
            0,
            int(max(1.0, self._viewport_widget.width)),
            int(max(1.0, self._viewport_widget.height)),
        )
        try:
            ray = self.camera.screen_point_to_ray(float(x), float(y), viewport_rect)
            origin = ray.origin
            direction = ray.direction
            return (
                (float(origin[0]), float(origin[1]), float(origin[2])),
                (float(direction[0]), float(direction[1]), float(direction[2])),
            )
        except Exception as e:
            log.error(f"[EditorWindowTcgui] viewport ray failed: {e}")
            return None

    def world_point_on_plane(
        self,
        x: float,
        y: float,
        plane_origin: tuple[float, float, float],
        plane_normal: tuple[float, float, float],
        label: str = "plane",
    ) -> tuple[float, float, float] | None:
        if self.camera is None or self.camera.entity is None:
            log.error(f"[EditorWindowTcgui] {label} pick failed: editor camera is not available")
            return None
        if self._viewport_widget is None:
            log.error(f"[EditorWindowTcgui] {label} pick failed: viewport widget is not available")
            return None

        viewport_rect = (
            0,
            0,
            int(max(1.0, self._viewport_widget.width)),
            int(max(1.0, self._viewport_widget.height)),
        )
        try:
            ray = self.camera.screen_point_to_ray(float(x), float(y), viewport_rect)
            origin = ray.origin
            direction = ray.direction
            denom = (
                float(direction[0]) * plane_normal[0]
                + float(direction[1]) * plane_normal[1]
                + float(direction[2]) * plane_normal[2]
            )
            if abs(denom) < 1e-9:
                log.error(f"[EditorWindowTcgui] {label} pick failed: ray is parallel to plane")
                return None
            t = (
                (plane_origin[0] - float(origin[0])) * plane_normal[0]
                + (plane_origin[1] - float(origin[1])) * plane_normal[1]
                + (plane_origin[2] - float(origin[2])) * plane_normal[2]
            ) / denom
            return (
                float(origin[0] + direction[0] * t),
                float(origin[1] + direction[1] * t),
                float(origin[2] + direction[2] * t),
            )
        except Exception as e:
            log.error(f"[EditorWindowTcgui] {label} pick failed: {e}")
            return None

    def world_point_on_entity_local_oxy_plane(self, x: float, y: float, entity) -> tuple[float, float, float] | None:
        if entity is None or not entity.valid():
            log.error("[EditorWindowTcgui] entity local OXY plane pick failed: entity is not available")
            return None
        pose = entity.transform.global_pose()
        origin = pose.point_to_global(Vec3(0.0, 0.0, 0.0))
        normal = pose.vector_to_global(Vec3(0.0, 0.0, 1.0))
        return self.world_point_on_plane(
            x,
            y,
            (float(origin.x), float(origin.y), float(origin.z)),
            (float(normal.x), float(normal.y), float(normal.z)),
            "entity local OXY plane",
        )

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def push_undo_command(self, cmd: UndoCommand, merge: bool = False) -> None:
        self.undo_stack.push(cmd, merge=merge)
        self._request_viewport_update()
        self._update_undo_redo_actions()
        self.undo_stack_changed.emit()

    def undo(self) -> None:
        cmd = self.undo_stack.undo()
        select_obj = None
        if isinstance(cmd, AddEntityCommand):
            select_obj = cmd.parent_entity
        elif isinstance(cmd, DeleteEntityCommand):
            select_obj = cmd.entity
        elif isinstance(cmd, RenameEntityCommand):
            select_obj = cmd.entity

        if self.scene_tree_controller is not None:
            self.scene_tree_controller.rebuild(select_obj=select_obj)

        self._request_viewport_update()
        self._resync_inspector_from_selection()
        self._update_undo_redo_actions()
        if cmd is not None:
            self.undo_stack_changed.emit()

    def redo(self) -> None:
        cmd = self.undo_stack.redo()
        select_obj = None
        if isinstance(cmd, AddEntityCommand):
            select_obj = cmd.entity
        elif isinstance(cmd, DeleteEntityCommand):
            select_obj = cmd.parent_entity
        elif isinstance(cmd, RenameEntityCommand):
            select_obj = cmd.entity

        if self.scene_tree_controller is not None:
            self.scene_tree_controller.rebuild(select_obj=select_obj)

        self._request_viewport_update()
        self._resync_inspector_from_selection()
        self._update_undo_redo_actions()
        if cmd is not None:
            self.undo_stack_changed.emit()

    def _resync_inspector_from_selection(self) -> None:
        if self._interaction_system is None or self._inspector_controller is None:
            return
        selected = self._interaction_system.selection.selected
        if selected is None or not selected.valid():
            return
        self._inspector_controller.show_entity_inspector(selected)

    def _update_undo_redo_actions(self) -> None:
        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_undo_redo_actions()

    # ------------------------------------------------------------------
    # Selection / Inspector callbacks
    # ------------------------------------------------------------------

    def _on_entity_selected_from_state(self, entity) -> None:
        """Called by EditorStateIO when restoring selection from file."""
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.select_object(entity)
        if self._inspector_controller is not None:
            self._inspector_controller.show_entity_inspector(entity)

    def _on_tree_object_selected(self, obj) -> None:
        if self._inspector_controller is not None:
            self._inspector_controller.resync_from_tree_selection(obj)

        if self._interaction_system is not None:
            from termin.visualization.core.entity import Entity
            if isinstance(obj, Entity):
                self._interaction_system.selection.select(obj)
            else:
                self._interaction_system.selection.clear()

    def _on_selection_changed(self, entity) -> None:
        # The C++ UnifiedGizmoPass pulls its draw target from
        # EditorInteractionSystem::transform_gizmo, which is empty until
        # set_gizmo_target is called. Without this line the gizmo stays
        # invisible even after a successful selection (Qt editor does the
        # same in editor_window.py::_on_selection_changed).
        sys = self._interaction_system
        if sys is not None:
            sys.set_gizmo_target(entity)
            self._update_gizmo_screen_scale()
        self._request_viewport_update()
        if self.scene_tree_controller is not None and entity and entity.valid():
            self.scene_tree_controller.select_object(entity)
        if self._inspector_controller is not None:
            if entity and entity.valid():
                self._inspector_controller.show_entity_inspector(entity)

    def _on_hover_changed(self, entity) -> None:
        self._request_viewport_update()

    def _on_editor_viewport_click(
        self,
        entity,
        x: float,
        y: float,
        has_world_point: bool,
        world_x: float,
        world_y: float,
        world_z: float,
        depth: float,
        view_depth: float,
        reproject_screen_error: float,
        reproject_depth_error: float,
        has_mesh_hit: bool,
        mesh_x: float,
        mesh_y: float,
        mesh_z: float,
        normal_x: float,
        normal_y: float,
        normal_z: float,
        triangle_index: int,
        index0: int,
        index1: int,
        index2: int,
    ) -> bool:
        args = (
            entity, x, y, has_world_point, world_x, world_y, world_z, depth, view_depth,
            reproject_screen_error, reproject_depth_error,
            has_mesh_hit, mesh_x, mesh_y, mesh_z,
            normal_x, normal_y, normal_z,
            triangle_index, index0, index1, index2
        )
        if self._viewport_click_interceptor is not None:
            try:
                if bool(self._viewport_click_interceptor(*args)):
                    return True
            except Exception as e:
                log.error(f"[EditorWindowTcgui] viewport click interceptor failed: {e}")
                return False
        for callback in self._viewport_click_interceptors:
            try:
                if bool(callback(*args)):
                    return True
            except Exception as e:
                log.error(f"[EditorWindowTcgui] viewport click interceptor failed: {e}")
                return False
        return False

    def _on_transform_end(self, old_pose, new_pose) -> None:
        """C++ TransformGizmo drag-end callback — push an undo command."""
        from termin.editor_core.editor_commands import TransformEditCommand
        tg = self._interaction_system.transform_gizmo if self._interaction_system else None
        if tg is None or not tg.target.valid():
            return
        cmd = TransformEditCommand(
            transform=tg.target.transform,
            old_pose=old_pose,
            new_pose=new_pose,
        )
        self.push_undo_command(cmd, False)

    def _update_gizmo_screen_scale(self) -> None:
        """Update gizmo size based on camera distance to target."""
        sys = self._interaction_system
        if sys is None:
            return
        tg = sys.transform_gizmo
        if tg is None or not tg.target.valid():
            return
        display = self._editor_display
        if display is None or not display.viewports:
            return
        viewport = display.viewports[0]
        render_target = viewport.render_target if viewport is not None else None
        camera = render_target.camera if render_target is not None else None
        if camera is None or camera.entity is None:
            return
        import numpy as np
        camera_pos = camera.entity.transform.global_pose().lin
        gizmo_pos = tg.target.transform.global_pose().lin
        distance = np.linalg.norm(np.array(camera_pos) - np.array(gizmo_pos))
        tg.set_screen_scale(max(0.1, distance * 0.1))

    def _on_inspector_transform_changed(self) -> None:
        self._request_viewport_update()

    def _on_inspector_component_changed(self) -> None:
        self._request_viewport_update()

    def _on_render_display_selected(self, display) -> None:
        if self._inspector_controller is None or display is None:
            return
        self._inspector_controller.show_display_inspector(display, display.name or "Display")

    def _on_render_viewport_selected(self, viewport) -> None:
        if self._inspector_controller is None or viewport is None:
            return
        displays = (
            self._rendering_controller.displays
            if self._rendering_controller is not None else None
        )
        current_display = None
        if self._rendering_controller is not None:
            from termin.engine import RenderingManager
            current_display = RenderingManager.instance().get_display_for_viewport(viewport)
            scene = viewport.scene or self.scene
        self._inspector_controller.show_viewport_inspector(
            viewport=viewport,
            displays=displays,
            scene=self.scene,
            current_display=current_display,
        )
        all_scenes = [self.scene_manager.get_scene(name) for name in self.scene_manager.scene_names()]
        self._inspector_controller._viewport_inspector.set_scenes(all_scenes)

    def _on_render_entity_selected(self, entity) -> None:
        if self._inspector_controller is None or entity is None:
            return
        self._inspector_controller.show_entity_inspector(entity)

    def _on_render_target_selected(self, render_target) -> None:
        if self._inspector_controller is None or render_target is None:
            return
        scene = render_target.scene if render_target.scene is not None else self.scene
        self._inspector_controller.show_render_target_inspector(render_target, scene)

    def _on_rendering_changed(self) -> None:
        if self._rendering_controller is not None:
            self._rendering_controller.sync_viewport_list_from_manager()
        elif self._viewport_list is not None:
            self._viewport_list.refresh()

    # ------------------------------------------------------------------
    # Viewport update
    # ------------------------------------------------------------------

    def _request_viewport_update(self) -> None:
        self.scene_manager.request_render()

    def request_viewport_update(self) -> None:
        self._request_viewport_update()

    def _observe_scene_events(self, scene) -> None:
        if self._scene_event_subscription is not None:
            self._scene_event_subscription.unsubscribe()
            self._scene_event_subscription = None

        self._scene_tree_rebuild_pending = False
        if scene is None:
            return

        try:
            self._scene_event_subscription = scene.subscribe_event(
                "tc.scene.structure_changed",
                self._on_scene_structure_changed,
            )
        except Exception as e:
            log.error(f"[EditorWindowTcgui] failed to subscribe to scene events: {e}")

    def _on_scene_structure_changed(self, _event) -> None:
        self._scene_tree_rebuild_pending = True
        self._request_viewport_update()

    def _process_pending_scene_tree_rebuild(self) -> None:
        if not self._scene_tree_rebuild_pending:
            return
        self._scene_tree_rebuild_pending = False
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.rebuild()
        self._request_viewport_update()

    # ------------------------------------------------------------------
    # Scene file operations
    # ------------------------------------------------------------------

    def _new_scene(self) -> None:
        if self._ui is None:
            self._do_new_scene()
            return
        MessageBox.question(
            self._ui,
            "New Scene",
            "Create a new scene?\n\nThis will remove all entities and resources.",
            on_result=lambda result: self._do_new_scene() if result == "Yes" else None,
        )

    def _do_new_scene(self) -> None:
        old_scene_name = self._editor_scene_name
        if old_scene_name and self.scene_manager.has_scene(old_scene_name):
            self.detach_editor_from_scene(save_state=True, clear_editor_scene_name=False)
            self.detach_scene_from_render(old_scene_name, save_state=True)
            self.scene_manager.close_scene(old_scene_name)
        self._editor_scene_name = "untitled"
        self.scene_manager.create_scene(self._editor_scene_name, default_scene_extensions())
        self.scene_manager.set_mode(self._editor_scene_name, SceneMode.STOP)
        if self._editor_attachment is not None:
            self.attach_editor_to_scene(self._editor_scene_name, restore_state=False)
            self.attach_scene_to_render(self._editor_scene_name)
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(self.scene)
            self.scene_tree_controller.rebuild()
        self._observe_scene_events(self.scene)
        self._update_window_title()

    def _save_scene(self) -> None:
        scene_name = self._editor_scene_name
        scene_path = self.scene_manager.get_scene_path(scene_name) if scene_name else None
        if scene_path is not None:
            self._save_scene_to_file(scene_path)
        else:
            self._save_scene_as()

    def _save_scene_as(self) -> None:
        if self._ui is None:
            return
        project_path = self._get_project_path()
        directory = project_path or str(Path.home())
        from tcgui.widgets.file_dialog_overlay import show_save_file_dialog
        show_save_file_dialog(
            self._ui,
            title="Save Scene As",
            directory=directory,
            filter_str="Scene Files (*.tc_scene);;All Files (*)",
            on_result=lambda path: self._save_scene_to_file(path) if path else None,
            windowed=True,
        )

    def _load_scene(self) -> None:
        if self._ui is None:
            return
        project_path = self._get_project_path()
        directory = project_path or str(Path.home())
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog
        show_open_file_dialog(
            self._ui,
            title="Load Scene",
            directory=directory,
            filter_str="Scene Files (*.tc_scene);;All Files (*)",
            on_result=lambda path: self._load_scene_from_file(path) if path else None,
            windowed=True,
        )

    def _close_scene(self) -> None:
        if self._editor_scene_name:
            self.scene_manager.close_scene(self._editor_scene_name)
            self.scene_manager.create_scene(self._editor_scene_name, default_scene_extensions())
            self.scene_manager.set_mode(self._editor_scene_name, SceneMode.STOP)
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(self.scene)
            self.scene_tree_controller.rebuild()
        self._observe_scene_events(self.scene)
        self._update_window_title()

    def _save_scene_to_file(self, path: str) -> None:
        if not path:
            return
        if not self._validate_scene_path(path):
            return
        scene_name = self._editor_scene_name
        if scene_name is None:
            return
        try:
            editor_data = self._editor_state_io.collect() if self._editor_state_io else None
            self.scene_manager.save_scene(scene_name, path, editor_data)
            EditorSettings.instance().set_last_scene_path(path)
            from termin.project.settings import ProjectSettingsManager
            ProjectSettingsManager.instance().set_last_scene(path)
            self._log_to_console(f"Saved: {path}")
            self._update_window_title()
        except Exception as e:
            log.error(f"Failed to save scene: {e}")
            self._log_to_console(f"Error saving: {e}")

    def _load_scene_from_file(self, path: str) -> None:
        if not path:
            return
        if not self._validate_scene_path(path):
            return
        try:
            from termin.editor_core import scene_name_from_file_path
            old_scene_name = self._editor_scene_name
            scene_name = scene_name_from_file_path(path)

            # Close existing scene
            if old_scene_name and self.scene_manager.has_scene(old_scene_name):
                self.scene_manager.close_scene(old_scene_name)

            self._editor_scene_name = scene_name

            self.scene_manager.load_scene(scene_name, path)
            from termin.modules import upgrade_scene_unknown_components
            upgrade_scene_unknown_components(self.scene_manager.get_scene(scene_name))
            self.scene_manager.set_mode(scene_name, SceneMode.STOP)

            EditorSettings.instance().set_last_scene_path(path)
            from termin.project.settings import ProjectSettingsManager
            ProjectSettingsManager.instance().set_last_scene(path)

            self._log_to_console(f"Loaded: {path}")
            if self.scene_tree_controller is not None:
                self.scene_tree_controller.set_scene(self.scene)
                self.scene_tree_controller.rebuild()
            self._observe_scene_events(self.scene)
            if self._inspector_controller is not None:
                self._inspector_controller.set_scene(self.scene)
                self._inspector_controller.clear()
            # Extract editor data from file before attach
            editor_data = EditorStateIO.extract_from_file(path)

            if self._editor_attachment is not None:
                self.attach_editor_to_scene(scene_name, restore_state=False)
                self.attach_scene_to_render(scene_name)

            # Apply editor state (camera, selection, etc.)
            if self._editor_state_io is not None:
                self._editor_state_io.apply(editor_data)
            self._on_rendering_changed()
            self._request_viewport_update()
            self._update_window_title()
        except Exception as e:
            log.error(f"Failed to load scene: {e}")
            self._log_to_console(f"Error loading: {e}")

    def _validate_scene_path(self, path: str) -> bool:
        project_path = self._get_project_path()
        if not project_path:
            return True
        import os
        real_file = os.path.realpath(path)
        real_project = os.path.realpath(project_path)
        if real_file.startswith(real_project + os.sep) or real_file == real_project:
            return True
        if self._ui is not None:
            MessageBox.warning(
                self._ui,
                "Scene Outside Project",
                f"The scene file must be inside the project directory.\n\n"
                f"Scene: {path}\n"
                f"Project: {project_path}",
            )
        log.error(f"Scene path outside project: scene={path} project={project_path}")
        return False

    def _load_last_scene(self) -> None:
        # Per-project last scene has priority
        from termin.project.settings import ProjectSettingsManager
        psm = ProjectSettingsManager.instance()
        project_scene = psm.get_last_scene()
        if project_scene is not None and Path(project_scene).is_file():
            self._load_scene_from_file(project_scene)
            return

        # Fallback to global editor settings
        last_path = EditorSettings.instance().get_last_scene_path()
        if last_path is not None:
            self._load_scene_from_file(str(last_path))

    # ------------------------------------------------------------------
    # Project restore on startup
    # ------------------------------------------------------------------

    def _restore_project(self) -> None:
        """Restore project from launcher or last session."""
        from termin.launcher.recent import read_launch_project

        project_file: str | None = None

        # 1. Check launch_project.json (written by launcher)
        launch_path = read_launch_project()
        if launch_path is not None:
            p = Path(launch_path)
            if p.exists() and p.is_file() and p.suffix == ".terminproj":
                project_file = str(p)

        # 2. Fallback: last project from editor settings
        if project_file is None:
            last = EditorSettings.instance().get("last_project_file")
            if last and Path(last).exists():
                project_file = last

        if project_file is not None:
            self._load_project(project_file)
            EditorSettings.instance().set("last_project_file", project_file)

    # ------------------------------------------------------------------
    # Project operations (stub — file dialogs via tcgui)
    # ------------------------------------------------------------------

    def _new_project(self) -> None:
        if self._ui is None:
            return
        from tcgui.widgets.file_dialog_overlay import show_save_file_dialog
        show_save_file_dialog(
            self._ui,
            title="Create New Project",
            directory=self._current_project_path or str(Path.cwd()),
            filter_str="Termin Project (*.terminproj);;All Files (*)",
            on_result=lambda path: self._create_project_file(path) if path else None,
            windowed=True,
        )

    def _open_project(self) -> None:
        if self._ui is None:
            return
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog
        show_open_file_dialog(
            self._ui,
            title="Open Project",
            filter_str="Project Files (*.terminproj);;All Files (*)",
            on_result=lambda path: self._load_project(path) if path else None,
            windowed=True,
        )

    def _create_project_file(self, path: str) -> None:
        if not path:
            return
        project_file = Path(path)
        if project_file.suffix != ".terminproj":
            project_file = project_file.with_suffix(".terminproj")
        try:
            import json
            project_data = {
                "version": 1,
                "name": project_file.stem,
            }
            project_file.parent.mkdir(parents=True, exist_ok=True)
            project_file.write_text(json.dumps(project_data, indent=2), encoding="utf-8")
        except Exception as e:
            log.error(f"Failed to create project file {project_file}: {e}")
            if self._ui is not None:
                MessageBox.error(self._ui, "Create Project Failed", f"Failed to create project:\n{e}")
            return
        self._load_project(str(project_file))

    def _load_project(self, path: str) -> None:
        project_root = Path(path).parent
        project_dir = str(project_root)
        self._current_project_path = project_dir
        self._project_name = Path(path).stem
        self._log_to_console(f"Project: {project_dir}")

        # Initialize project settings
        from termin.project.settings import ProjectSettingsManager
        ProjectSettingsManager.instance().set_project_path(project_root)

        from termin.navmesh.settings import NavigationSettingsManager
        NavigationSettingsManager.instance().set_project_path(project_root)

        EditorSettings.instance().set("last_project_file", path)

        self._load_project_modules(project_root)
        self._run_project_init_script(project_root)
        self._rescan_file_resources()
        if self._project_browser is not None:
            self._project_browser.set_root(project_dir)

    def _load_project_modules(self, project_root: Path) -> None:
        from termin.modules import get_project_modules_runtime
        from termin_modules import ModuleKind, ModuleState

        runtime = get_project_modules_runtime()
        success = runtime.load_project(project_root)
        if not success and runtime.last_error:
            self._log_to_console(f"Module load error: {runtime.last_error}")

        cpp_loaded = 0
        cpp_failed = 0
        py_loaded = 0
        py_failed = 0

        for record in runtime.records():
            if record.kind == ModuleKind.Cpp:
                if record.state == ModuleState.Loaded:
                    cpp_loaded += 1
                    self._log_to_console(f"Loaded C++ module: {record.id}")
                elif record.state == ModuleState.Failed:
                    cpp_failed += 1
                    self._log_to_console(f"Failed to load C++ module {record.id}: {record.error_message}")
            else:
                if record.state == ModuleState.Loaded:
                    py_loaded += 1
                    self._log_to_console(f"Loaded Python module: {record.id}")
                elif record.state == ModuleState.Failed:
                    py_failed += 1
                    self._log_to_console(f"Failed to load Python module {record.id}: {record.error_message}")

        if cpp_loaded > 0:
            self._log_to_console(f"Loaded {cpp_loaded} C++ module(s)")
        if cpp_failed > 0:
            self._log_to_console(f"Failed to load {cpp_failed} C++ module(s)")
        if py_loaded > 0:
            self._log_to_console(f"Loaded {py_loaded} Python module(s)")
        if py_failed > 0:
            self._log_to_console(f"Failed to load {py_failed} Python module(s)")

    def _run_project_init_script(self, project_root: Path) -> None:
        init_script = project_root / "InitScript.py"
        if not init_script.is_file():
            return

        import runpy
        import sys

        project_path = str(project_root)
        inserted_project_path = False
        if project_path not in sys.path:
            sys.path.insert(0, project_path)
            inserted_project_path = True

        try:
            runpy.run_path(
                str(init_script),
                init_globals={
                    "editor": self,
                    "project_root": project_root,
                },
            )
        except Exception as e:
            log.error(f"Project init script failed: {init_script}: {e}")
            self._log_to_console(f"Project init script failed: {e}")
        finally:
            if inserted_project_path:
                sys.path.remove(project_path)

    @property
    def ui(self) -> UI | None:
        return self._ui

    def add_project_menu(self, name: str, menu) -> None:
        if self._menu_bar_widget is None:
            log.error(f"Cannot add project menu '{name}': menu bar is not initialized")
            return
        self._menu_bar_widget.add_menu(name, menu)

    def add_menu_item(self, menu_name: str, item) -> None:
        if self._menu_bar_widget is None:
            log.error(f"Cannot add menu item to '{menu_name}': menu bar is not initialized")
            return
        for label, menu in self._menu_bar_widget._entries:
            if label == menu_name:
                menu.items.append(item)
                return

        from tcgui.widgets.menu import Menu
        menu = Menu()
        menu.items = [item]
        self._menu_bar_widget.add_menu(menu_name, menu)

    def _on_project_file_activated(self, path: str) -> None:
        """Called when a file is double-clicked in the project browser."""
        p = Path(path)
        ext = p.suffix.lower()
        if ext == ".tc_scene":
            self._load_scene_from_file(path)
        elif ext == ".tc_prefab":
            self._open_prefab(path)
        else:
            from termin.editor_core.external_editor import open_in_text_editor
            try:
                open_in_text_editor(path)
            except Exception as e:
                log.error(f"Failed to open file in text editor: {e}")

    def _on_project_file_selected(self, path: str) -> None:
        if self._inspector_controller is None:
            return

        ext = Path(path).suffix.lower()
        if ext in (".tc_mat", ".material"):
            self._inspector_controller.show_material_inspector_for_file(path)
            return
        if ext in (".pipeline", ".tc_pipeline", ".scene_pipeline"):
            self._inspector_controller.show_pipeline_inspector_for_file(path)
            return
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".hdr", ".exr"):
            self._inspector_controller.show_texture_inspector_for_file(path)
            return
        if ext in (".obj", ".fbx"):
            self._inspector_controller.show_mesh_inspector_for_file(path)
            return
        if ext in (".glb", ".gltf"):
            self._inspector_controller.show_glb_inspector_for_file(path)
            return

    # ------------------------------------------------------------------
    # Menu action stubs / helpers
    # ------------------------------------------------------------------

    def _noop(self, *args, **kwargs) -> None:
        pass

    def _show_settings(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.settings_dialog import show_settings_dialog
        show_settings_dialog(self._ui)

    def _show_project_settings(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.project_settings_dialog import show_project_settings_dialog
        show_project_settings_dialog(self._ui, on_changed=self._request_viewport_update)

    def _show_scene_properties(self) -> None:
        if self._ui is None or self.scene is None:
            return
        from termin.editor_tcgui.dialogs.scene_inspector import show_scene_properties_dialog
        show_scene_properties_dialog(
            self._ui,
            self.scene,
            push_undo_command=self.push_undo_command,
            on_changed=self._request_viewport_update,
        )

    def _show_layers_settings(self) -> None:
        if self._ui is None or self.scene is None:
            return
        from termin.editor_tcgui.dialogs.layers_dialog import show_layers_dialog
        show_layers_dialog(self._ui, self.scene)

    def _show_shadow_settings(self) -> None:
        if self._ui is None or self.scene is None:
            return
        from termin.editor_tcgui.dialogs.shadow_settings_dialog import show_shadow_settings_dialog
        scene = self.scene
        mirror_scenes = []
        game_scene_name = self._game_scene_name
        if game_scene_name is not None:
            game_scene = self.scene_manager.get_scene(game_scene_name)
            if game_scene is not None:
                scene = game_scene
                mirror_scenes.append(self.scene)
        show_shadow_settings_dialog(
            self._ui,
            scene,
            mirror_scenes=mirror_scenes,
            on_changed=self._request_viewport_update,
        )

    def _show_agent_types(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.agent_types_dialog import show_agent_types_dialog
        show_agent_types_dialog(self._ui)

    def _show_navmesh_areas(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.navmesh_areas_dialog import show_navmesh_areas_dialog
        show_navmesh_areas_dialog(self._ui, on_changed=self._request_viewport_update)

    def _show_spacemouse_settings(self) -> None:
        if self._ui is None:
            return
        if self._spacemouse is None:
            self._init_spacemouse()
        if self._spacemouse is None:
            from tcbase import log
            log.warn("SpaceMouse not available")
            return
        from termin.editor_tcgui.dialogs.spacemouse_settings_dialog import show_spacemouse_settings_dialog
        show_spacemouse_settings_dialog(self._ui, self._spacemouse)

    def _init_spacemouse(self) -> None:
        """Initialize SpaceMouse controller if device available."""
        from termin.editor_core.spacemouse_controller import SpaceMouseController
        spacemouse = SpaceMouseController()
        if spacemouse.open(self._editor_attachment, self._request_viewport_update):
            self._spacemouse = spacemouse
            self._log_to_console("[SpaceMouse] Device connected")
        else:
            self._spacemouse = None

    def _show_resource_manager_viewer(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.resource_manager_viewer import show_resource_manager_viewer
        show_resource_manager_viewer(self._ui, project_file_watcher=self._project_file_watcher)

    def _show_core_registry_viewer(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.core_registry_viewer import show_core_registry_viewer
        show_core_registry_viewer(self._ui)

    def _show_inspect_registry_viewer(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.inspect_registry_viewer import show_inspect_registry_viewer
        show_inspect_registry_viewer(self._ui)

    def _show_navmesh_registry_viewer(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.navmesh_registry_viewer import show_navmesh_registry_viewer
        show_navmesh_registry_viewer(self._ui)

    def _show_framegraph_debugger(self) -> None:
        if self._ui is None:
            return
        if self._framegraph_debugger is not None and self._framegraph_debugger.visible:
            return
        from termin.editor_tcgui.dialogs.framegraph_debugger import show_framegraph_debugger
        self._framegraph_debugger = show_framegraph_debugger(
            self._ui, self._rendering_controller, self._fbo_surface,
            on_request_update=self._request_viewport_update)

    def _show_audio_debugger(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.audio_debugger import show_audio_debugger
        show_audio_debugger(self._ui)

    def _show_scene_manager_viewer(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.scene_manager_viewer import show_scene_manager_viewer

        show_scene_manager_viewer(
            self._ui,
            self.scene_manager,
            get_editor_attachment=lambda: self._editor_attachment,
            on_render_attach=lambda name: self.attach_scene_to_render(name),
            on_render_detach=lambda name: self.detach_scene_from_render(name, save_state=True),
            on_editor_attach=lambda name: self.attach_editor_to_scene(
                name,
                restore_state=True,
                transfer_camera_state=False,
            ),
            on_editor_detach=lambda: self.detach_editor_from_scene(save_state=True),
        )

    def _show_pipeline_editor(self) -> None:
        if self._ui is None:
            return
        try:
            from termin.editor_tcgui.pipeline_editor_window import open_pipeline_editor_window
            open_pipeline_editor_window(
                self._ui,
                directory=self._get_project_path() or str(Path.home()),
            )
        except Exception as e:
            log.error(f"[EditorWindowTcgui] Failed to open Pipeline Editor: {e}")
            self._log_to_console(f"Pipeline Editor error: {e}")

    def _open_pipeline_file_for_edit(self, file_path: str) -> None:
        if self._ui is None:
            return
        try:
            from termin.editor_tcgui.pipeline_editor_window import open_pipeline_editor_window
            open_pipeline_editor_window(
                self._ui,
                directory=str(Path(file_path).parent),
                initial_file=file_path,
            )
        except Exception as e:
            log.error(f"[EditorWindowTcgui] Failed to open Pipeline Editor for {file_path}: {e}")
            self._log_to_console(f"Pipeline Editor error: {e}")

    @property
    def _game_scene_name(self) -> str | None:
        return self._game_mode_model.game_scene_name if self._game_mode_model else None

    def _toggle_game_mode(self) -> None:
        if self._game_mode_model is not None:
            self._game_mode_model.toggle_game_mode()

    def _toggle_pause(self) -> None:
        if self._game_mode_model is None:
            return
        self._game_mode_model.toggle_pause()
        from tcgui.widgets.theme import current_theme as _t
        if self._pause_button is not None:
            if self._game_mode_model.is_game_paused:
                self._pause_button.text = "Resume"
                self._pause_button.background_color = (0.85, 0.63, 0.29, 1.0)
            else:
                self._pause_button.text = "Pause"
                self._pause_button.background_color = _t.bg_surface
        self._request_viewport_update()

    def _on_game_mode_entered(self, is_playing: bool, scene, expanded_uuids) -> None:
        """GameModeModel.mode_entered handler — post-attach view setup."""
        # tcgui-specific: rebuild per-viewport input managers + router after
        # attach swapped to new scene.
        if self._editor_attachment is not None:
            self._setup_editor_viewport_input_managers(self._editor_attachment._display)
            self._attach_editor_input_router(self._editor_attachment._display)

        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(scene)
            self.scene_tree_controller.rebuild()
            if expanded_uuids:
                self.scene_tree_controller.set_expanded_entity_uuids(expanded_uuids)
        self._observe_scene_events(scene)

        if self._inspector_controller is not None:
            self._inspector_controller.clear()

        self._update_game_mode_ui(is_playing)
        self._request_viewport_update()

    def _update_game_mode_ui(self, is_playing: bool) -> None:
        from tcgui.widgets.theme import current_theme as _t
        if self._play_button is not None:
            self._play_button.text = "Stop" if is_playing else "Play"
            self._play_button.background_color = _t.accent if is_playing else _t.bg_surface

        if self._pause_button is not None:
            self._pause_button.visible = is_playing
            if not is_playing:
                self._pause_button.background_color = _t.bg_surface
                self._pause_button.text = "Pause"

        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_play_action(is_playing)

        self._update_window_title()

        if self._status_bar is not None:
            if is_playing:
                self._status_bar.text = "Game mode"
            else:
                self._status_bar.text = "Editor mode"

    def _run_standalone(self) -> None:
        if self._current_project_path is None:
            self._log_to_console("No project open — cannot run standalone.")
            return
        self._save_scene()
        import subprocess
        import sys
        cmd = [sys.executable, "-m", "termin.main", "--project", self._current_project_path]
        last_scene = EditorSettings.instance().get("last_scene_file")
        if last_scene:
            cmd.extend(["--scene", last_scene])
        self._log_to_console(f"Launching standalone: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd)
        except Exception as e:
            log.error(f"Failed to launch standalone: {e}")
            self._log_to_console(f"Error: {e}")

    def _build_project(self) -> None:
        self._build_project_to_default_dist()

    def _build_android(self) -> None:
        if self._current_project_path is None:
            self._log_to_console("No project open - cannot build Android APK.")
            return

        self._save_scene()

        scene_name = self._editor_scene_name
        scene_path = self.scene_manager.get_scene_path(scene_name) if scene_name else None
        if scene_path is None:
            self._log_to_console("No saved scene - cannot build Android APK.")
            return

        project_root = Path(self._current_project_path).resolve()
        scene_path_obj = Path(scene_path).resolve()
        try:
            scene_rel_path = scene_path_obj.relative_to(project_root)
        except ValueError:
            self._log_to_console("Android build entry scene must be inside the current project.")
            return

        from termin.project.settings import ProjectSettingsManager
        build_output_dir = ProjectSettingsManager.instance().settings.build_output_dir
        output_dir = project_root / build_output_dir / "android" / project_root.name

        self._log_to_console(f"Android build started: {scene_rel_path}")
        try:
            from termin.project_build import build_android_project

            result = build_android_project(
                project_root=project_root,
                entry_scene=scene_rel_path,
                output_dir=output_dir,
            )
        except Exception as e:
            log.error(f"Android build failed: {e}", exc_info=True)
            self._log_to_console(f"Android build failed: {e}")
            return

        self._log_to_console(f"Android APK: {result.apk_path}")
        self._log_to_console(f"Android applicationId: {result.application_id}")
        self._log_to_console(f"Android launch: {result.application_id}/{result.launch_activity}")
        self._log_to_console(f"Android package: {result.package_result.package_dir}")
        self._log_to_console(f"Android build log: {result.log_path}")
        for diagnostic in result.diagnostics:
            self._log_to_console(f"Android build {diagnostic.level}: {diagnostic.path}: {diagnostic.message}")

    def _build_project_to_default_dist(self):
        if self._current_project_path is None:
            self._log_to_console("No project open - cannot build.")
            return None

        self._save_scene()

        scene_name = self._editor_scene_name
        scene_path = self.scene_manager.get_scene_path(scene_name) if scene_name else None
        if scene_path is None:
            self._log_to_console("No saved scene - cannot build.")
            return None

        project_root = Path(self._current_project_path).resolve()
        scene_path_obj = Path(scene_path).resolve()
        try:
            scene_rel_path = scene_path_obj.relative_to(project_root)
        except ValueError:
            self._log_to_console("Build entry scene must be inside the current project.")
            return None

        from termin.project.settings import ProjectSettingsManager
        build_output_dir = ProjectSettingsManager.instance().settings.build_output_dir
        output_dir = project_root / build_output_dir / project_root.name

        try:
            from termin.project_builder import build_project
            from termin.render_framework import collect_scene_shader_usages

            scene = self.scene_manager.get_scene(scene_name)
            if scene is None:
                self._log_to_console("No loaded scene - cannot collect shader usages.")
                return None
            shader_usages = collect_scene_shader_usages(scene.scene_handle())

            result = build_project(
                project_root=project_root,
                entry_scene=scene_rel_path,
                output_dir=output_dir,
                compile_shaders=True,
                shader_usages=shader_usages,
            )
        except Exception as e:
            log.error(f"Build failed: {e}")
            self._log_to_console(f"Build failed: {e}")
            return None

        resource_count = len(result.manifest.resources)
        diagnostic_count = len(result.manifest.diagnostics)
        self._log_to_console(f"Build complete: {result.build_json_path}")
        self._log_to_console(f"Build manifest: {resource_count} resource(s), {diagnostic_count} diagnostic(s)")
        for diagnostic in result.manifest.diagnostics:
            self._log_to_console(f"Build {diagnostic.level}: {diagnostic.path}: {diagnostic.message}")
        return result

    def _run_build(self) -> None:
        result = self._build_project_to_default_dist()
        if result is None:
            return

        import subprocess
        import sys

        cmd = [
            sys.executable,
            "-m",
            "termin.player",
            "--build",
            str(result.build_json_path),
        ]
        self._log_to_console(f"Launching build: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd, cwd=str(result.output_dir))
        except Exception as e:
            log.error(f"Failed to launch build: {e}")
            self._log_to_console(f"Run build failed: {e}")

    def _show_undo_stack_viewer(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.undo_stack_viewer import show_undo_stack_viewer
        show_undo_stack_viewer(
            self._ui,
            self.undo_stack,
            stack_changed_signal=self.undo_stack_changed,
        )

    # ------------------------------------------------------------------
    # Debug panels (Profiler / Modules)
    # ------------------------------------------------------------------

    def _toggle_profiler(self) -> None:
        self._profiler_visible = not self._profiler_visible
        self._update_debug_panel_visibility()
        self._menu_bar_controller.update_profiler_action()

    def _toggle_modules(self) -> None:
        self._modules_visible = not self._modules_visible
        self._update_debug_panel_visibility()
        self._menu_bar_controller.update_modules_action()

    def _update_debug_panel_visibility(self) -> None:
        visible = self._profiler_visible or self._modules_visible
        if self._debug_panel is not None:
            self._debug_panel.visible = visible
        if self._debug_splitter is not None:
            self._debug_splitter.visible = visible
        # Switch to the relevant tab
        if visible and self._debug_panel is not None:
            if self._profiler_visible and not self._modules_visible:
                self._debug_panel.selected_index = 0
            elif self._modules_visible and not self._profiler_visible:
                self._debug_panel.selected_index = 1
        if self._ui is not None:
            self._ui.request_layout()

    def _toggle_fullscreen(self) -> None:
        panels = [
            self._left_tabs, self._left_splitter,
            self._right_scroll, self._right_splitter,
            self._bottom_tabs, self._bottom_splitter,
            self._menu_bar_widget, self._status_bar,
            self._debug_panel, self._debug_splitter,
        ]
        if self._is_fullscreen:
            # Restore panels
            if self._pre_fullscreen_state is not None:
                for w in panels:
                    if w is not None and id(w) in self._pre_fullscreen_state:
                        w.visible = self._pre_fullscreen_state[id(w)]
            self._is_fullscreen = False
            self._pre_fullscreen_state = None
        else:
            # Save state and hide panels
            self._pre_fullscreen_state = {}
            for w in panels:
                if w is not None:
                    self._pre_fullscreen_state[id(w)] = w.visible
                    w.visible = False
            self._is_fullscreen = True
        self._menu_bar_controller.update_fullscreen_action()

    def _load_material_from_file(self) -> None:
        if self._ui is None:
            return
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog
        show_open_file_dialog(
            self._ui,
            title="Load Material",
            directory=self._get_project_path() or str(Path.home()),
            filter_str="Shader Files (*.shader);;All Files (*)",
            on_result=self._on_material_file_selected,
            windowed=True,
        )

    def _load_components_from_file(self) -> None:
        if self._ui is None:
            return
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog
        show_open_file_dialog(
            self._ui,
            title="Load Components",
            directory=self._get_project_path() or str(Path.home()),
            filter_str="Python Files (*.py);;All Files (*)",
            on_result=self._on_components_file_selected,
            windowed=True,
        )

    def _deploy_stdlib(self) -> None:
        if self._ui is None:
            return
        import termin

        # termin is a namespace package → __file__ is None; use __path__[0]
        stdlib_src = Path(termin.__path__[0]) / "resources" / "stdlib"
        if not stdlib_src.exists():
            MessageBox.error(
                self._ui,
                "Standard Library Not Found",
                f"Path not found:\n{stdlib_src}",
            )
            return

        from tcgui.widgets.file_dialog_overlay import show_open_directory_dialog
        show_open_directory_dialog(
            self._ui,
            title="Select Directory for Standard Library",
            directory=self._get_project_path() or str(Path.home()),
            on_result=lambda path: self._deploy_stdlib_to(path, stdlib_src),
            windowed=True,
        )

    def _migrate_spec_to_meta(self) -> None:
        if self._ui is None:
            return
        project = self._get_project_path()
        if not project:
            MessageBox.warning(
                self._ui,
                "No Project",
                "Open a project first to migrate .spec files.",
            )
            return
        spec_files = list(Path(project).rglob("*.spec"))
        if not spec_files:
            MessageBox.info(
                self._ui,
                "No Files to Migrate",
                "No .spec files found in the current project.",
            )
            return

        migrated = 0
        errors: list[str] = []
        for spec_path in spec_files:
            meta_path = spec_path.with_suffix(".meta")
            try:
                spec_path.rename(meta_path)
                migrated += 1
            except Exception as e:
                errors.append(f"{spec_path.name}: {e}")

        if errors:
            MessageBox.warning(
                self._ui,
                "Migration Completed with Errors",
                f"Migrated {migrated} files.\nErrors: {len(errors)}",
            )
            log.error("Spec->meta migration completed with errors:\n" + "\n".join(errors))
        else:
            MessageBox.info(
                self._ui,
                "Migration Complete",
                f"Successfully migrated {migrated} files.",
            )

    def close(self) -> None:
        self._should_close = True

    def _update_window_title(self) -> None:
        scene_label = "No Scene"
        if self.prefab_edit_controller is not None and self.prefab_edit_controller.is_editing:
            scene_label = f"Prefab: {self.prefab_edit_controller.prefab_name or ''}"
        elif self._editor_scene_name is not None:
            scene_path = self.scene_manager.get_scene_path(self._editor_scene_name)
            if scene_path is not None:
                scene_label = Path(scene_path).stem
            else:
                scene_label = "Untitled"

        project_name = self._project_name or "No Project"
        mode = "Play" if self._game_scene_name is not None else "Edit"
        if self._status_bar is not None:
            self._status_bar.text = f"{project_name} | {scene_label} | {mode}"

        parts = ["Termin Editor"]
        if self._project_name is not None:
            parts.append(f"- {self._project_name}")
        parts.append(f"[{scene_label}]")
        if self._game_scene_name is not None:
            parts.append("- PLAYING")
        if self._main_window is not None:
            self._main_window.set_title(" ".join(parts))

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_to_console(self, message: str) -> None:
        log.info(message)
        if self._console_area is not None:
            self._console_area.text = (self._console_area.text or "") + message + "\n"

    # ------------------------------------------------------------------
    # Resource management
    # ------------------------------------------------------------------

    def _get_project_path(self) -> str | None:
        return self._current_project_path

    def _on_resource_reloaded(self, name: str, kind: str) -> None:
        self._request_viewport_update()

    def _rescan_file_resources(self) -> None:
        project_path = self._get_project_path()
        if project_path:
            try:
                self._project_file_watcher.watch_directory(project_path)
            except Exception as e:
                log.error(f"Resource scan failed: {e}")

    def _register_file_processors(self) -> None:
        try:
            register_default_preloaders(
                self._project_file_watcher,
                self.resource_manager,
                self._on_resource_reloaded,
            )
        except Exception as e:
            log.error(f"Failed to register default file processors: {e}")

    # ------------------------------------------------------------------
    # Scene / scene manager callbacks
    # ------------------------------------------------------------------

    def _on_before_scene_close(self, scene_name: str) -> None:
        self.detach_scene_from_render(scene_name, save_state=False)

    def switch_to_scene(self, scene_name: str) -> None:
        self._editor_scene_name = scene_name
        scene = self.scene_manager.get_scene(scene_name)
        self.attach_scene_to_render(scene_name)
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(scene)
            self.scene_tree_controller.rebuild()
        if self._inspector_controller is not None:
            self._inspector_controller.set_scene(scene)
            self._inspector_controller.clear()
        self.undo_stack.clear()
        self._update_undo_redo_actions()
        self.undo_stack_changed.emit()

    def _open_prefab(self, path: str) -> None:
        if self.prefab_edit_controller is None:
            log.error("[EditorWindowTcgui] prefab edit controller is not initialized")
            return
        if self.prefab_edit_controller.is_editing:
            log.error("[EditorWindowTcgui] already editing a prefab")
            return
        self._pre_prefab_scene_name = self._editor_scene_name
        if not self.prefab_edit_controller.open_prefab(path):
            self._pre_prefab_scene_name = None

    def _save_prefab(self) -> None:
        if self.prefab_edit_controller is None:
            log.error("[EditorWindowTcgui] prefab edit controller is not initialized")
            return
        self.prefab_edit_controller.save()

    def _exit_prefab_editing(self) -> None:
        if self.prefab_edit_controller is None:
            log.error("[EditorWindowTcgui] prefab edit controller is not initialized")
            return
        if not self.prefab_edit_controller.is_editing:
            return
        if self._editor_scene_name == "prefab":
            self.detach_editor_from_scene(save_state=False, clear_editor_scene_name=False)
            self.detach_scene_from_render("prefab", save_state=False)
        self.prefab_edit_controller.exit()

    def _on_prefab_mode_changed(self, is_editing: bool, prefab_name: str | None) -> None:
        if is_editing:
            if self._prefab_toolbar is not None:
                self._prefab_toolbar.visible = True
            if self._prefab_toolbar_label is not None:
                self._prefab_toolbar_label.text = f"Editing Prefab: {prefab_name or ''}"
            if self._play_button is not None:
                self._play_button.enabled = False
            self.attach_editor_to_scene("prefab", restore_state=False)
            self.attach_scene_to_render("prefab")
        else:
            if self._prefab_toolbar is not None:
                self._prefab_toolbar.visible = False
            if self._play_button is not None:
                self._play_button.enabled = True
            previous_scene_name = self._pre_prefab_scene_name
            self._pre_prefab_scene_name = None
            if previous_scene_name and self.scene_manager.has_scene(previous_scene_name):
                self.attach_editor_to_scene(previous_scene_name, restore_state=True)
                self.attach_scene_to_render(previous_scene_name)
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.rebuild()
        self._update_window_title()
        self._request_viewport_update()

    # ------------------------------------------------------------------
    # Per-frame polling
    # ------------------------------------------------------------------

    def poll_file_watcher(self) -> None:
        """Process pending file system changes and update debug panels. Call from main loop."""
        self._project_file_watcher.poll()

        now = time.monotonic()
        if self._profiler_visible and self._profiler_panel is not None:
            if now - self._last_profiler_update > 0.1:
                self._profiler_panel.update_display()
                self._last_profiler_update = now
        if self._modules_visible and self._modules_panel is not None:
            if now - self._last_modules_update > 1.0:
                self._modules_panel.update_display()
                self._last_modules_update = now
        if self._framegraph_debugger is not None and self._framegraph_debugger.visible:
            self._framegraph_debugger.update()
        self._process_pending_scene_tree_rebuild()

    def _after_render(self) -> None:
        if not self._ar_logged:
            log.info(f"[DBG _after_render] first call, interaction_system={self._interaction_system}")
            self._ar_logged = True
        if self._spacemouse is not None:
            self._spacemouse.poll()
        if self._interaction_system is not None:
            self._interaction_system.after_render()
        has_overlay_drawers = False
        for drawer in self._viewport_overlay_drawers:
            has_overlay_drawers = True
            try:
                drawer()
            except Exception as e:
                log.error(f"[EditorWindowTcgui] viewport overlay drawer failed: {e}")
        if self._framegraph_debugger is not None and self._framegraph_debugger.visible:
            self._framegraph_debugger.update()
        self._process_pending_scene_tree_rebuild()
        if has_overlay_drawers:
            self._request_viewport_update()

    def _on_material_file_selected(self, path: str | None) -> None:
        if not path:
            return
        self._resource_loader.load_material_from_path(path)
        if self._inspector_controller is not None:
            self._inspector_controller.show_material_inspector_for_file(path)
        self._request_viewport_update()

    def _on_components_file_selected(self, path: str | None) -> None:
        if not path:
            return
        self._resource_loader.load_components_from_path(path)

    def _deploy_stdlib_to(self, path: str | None, stdlib_src: Path) -> None:
        if not path or self._ui is None:
            return
        target_path = Path(path) / "stdlib"
        try:
            shutil.copytree(stdlib_src, target_path, dirs_exist_ok=True)
            MessageBox.info(
                self._ui,
                "Standard Library Deployed",
                f"Deployed to:\n{target_path}",
            )
            log.info(f"[Editor] Standard library deployed to {target_path}")
        except Exception as e:
            MessageBox.error(
                self._ui,
                "Deployment Failed",
                f"Failed to deploy standard library:\n{e}",
            )
