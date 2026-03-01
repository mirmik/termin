"""EditorWindowTcgui — main editor window implemented with tcgui."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

from tcbase import log

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
from tcgui.widgets.input_dialog import show_input_dialog

from termin.editor.undo_stack import UndoStack, UndoCommand
from termin.editor.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    RenameEntityCommand,
)
from termin.editor.scene_manager import SceneManager, SceneMode
from termin.editor.resource_loader import ResourceLoader
from termin.editor.project_file_watcher import ProjectFileWatcher
from termin.editor.file_processors import (
    MaterialPreLoader,
    MeshFileProcessor,
    ShaderFileProcessor,
    TextureFileProcessor,
    ComponentFileProcessor,
    PipelinePreLoader,
    ScenePipelinePreLoader,
    VoxelGridProcessor,
    NavMeshProcessor,
    GLBPreLoader,
    GlslPreLoader,
    PrefabPreLoader,
    AudioPreLoader,
    UIPreLoader,
)
from termin.editor.settings import EditorSettings
from termin.visualization.core.resources import ResourceManager
from termin.visualization.platform.backends.fbo_backend import FBOSurface

from termin.editor.editor_state_io import EditorStateIO
from termin.editor_tcgui.menu_bar_controller import MenuBarControllerTcgui
from termin.editor_tcgui.scene_tree_controller import SceneTreeControllerTcgui
from termin.editor_tcgui.inspector_controller import InspectorControllerTcgui
from termin.editor_tcgui.project_browser import ProjectBrowserTcgui


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
        graphics=None,
        offscreen_context=None,
    ) -> None:
        self._world = world
        self._graphics = graphics
        self._offscreen_context = offscreen_context
        self._should_close = False
        self._ui: UI | None = None

        self.undo_stack = UndoStack()

        # Resource manager
        self.resource_manager = ResourceManager.instance()
        self.resource_manager.register_builtin_components()
        self.resource_manager.register_builtin_frame_passes()
        self.resource_manager.register_builtin_post_effects()

        # Scene manager
        self.scene_manager = scene_manager
        self.scene_manager.set_on_before_scene_close(self._on_before_scene_close)

        self._editor_data: dict[str, dict] = {}
        self._editor_scene_name = "untitled"

        if initial_scene is not None:
            self.scene_manager.register_scene(self._editor_scene_name, initial_scene.scene_handle())
            self.scene_manager.set_mode(self._editor_scene_name, SceneMode.STOP)
        else:
            self.scene_manager.create_scene(self._editor_scene_name)
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
        self._current_project_path: str | None = None
        self._project_name: str | None = None
        self._is_fullscreen: bool = False
        self._pre_fullscreen_state: dict | None = None
        self._editor_state_io: EditorStateIO | None = None
        self._rendering_tree = None
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
        self._game_scene_name: str | None = None
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
        self._interaction_system.set_graphics(self._graphics)
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

        rendering_tab_content = VStack()
        rendering_tab_content.spacing = 4
        from tcgui.widgets.tree import TreeWidget as RenderTreeWidget
        self._rendering_tree = RenderTreeWidget()
        self._rendering_tree.stretch = True
        rendering_tab_content.add_child(self._rendering_tree)
        left_tabs.add_tab("Rendering", rendering_tab_content)

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
        bottom_tabs.preferred_height = px(200)
        self._bottom_splitter = Splitter(target=bottom_tabs, side="top")
        root.add_child(self._bottom_splitter)

        from tcgui.widgets.hstack import HStack as HStackInner
        from tcgui.widgets.tree import TreeWidget as TreeWidgetInner
        from tcgui.widgets.list_widget import ListWidget
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

        project_file_list = ListWidget()
        project_file_list.stretch = True
        project_file_list.item_height = 28
        project_file_list.empty_text = "Select a directory"

        file_list_scroll = ScrollAreaInner()
        file_list_scroll.stretch = True
        file_list_scroll.add_child(project_file_list)

        project_tab_content.add_child(dir_tree_scroll)
        project_tab_content.add_child(SplitterInner(target=dir_tree_scroll, side="right"))
        project_tab_content.add_child(file_list_scroll)

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

        # Setup scene tree controller
        self.scene_tree_controller = SceneTreeControllerTcgui(
            tree_widget=scene_tree,
            scene=self.scene,
            undo_handler=self.push_undo_command,
            on_object_selected=self._on_tree_object_selected,
            request_viewport_update=self._request_viewport_update,
        )
        self.scene_tree_controller._on_rename_requested = self._rename_entity_dialog

        # Setup inspector controller
        self._inspector_controller = InspectorControllerTcgui(
            container=inspector_container,
            resource_manager=self.resource_manager,
            push_undo_command=self.push_undo_command,
            on_transform_changed=self._on_inspector_transform_changed,
            on_component_changed=self._on_inspector_component_changed,
            graphics=self._graphics,
        )
        self._inspector_controller.set_scene(self.scene)

        # Setup project browser
        self._project_browser = ProjectBrowserTcgui(
            dir_tree=project_dir_tree,
            file_list=project_file_list,
            on_file_activated=self._on_project_file_activated,
        )

        # Setup rendering controller and editor display
        if self._editor_display is not None:
            from termin.editor.editor_pipeline import make_editor_pipeline
            from termin.editor.editor_scene_attachment import EditorSceneAttachment
            from termin.editor_tcgui.rendering_controller import RenderingControllerTcgui
            from termin._native.render import RenderingManager

            # Create rendering controller (registers factories with RenderingManager)
            self._rendering_controller = RenderingControllerTcgui(
                offscreen_context=self._offscreen_context,
                get_scene=lambda: self.scene,
                make_editor_pipeline=make_editor_pipeline,
                on_request_update=self._request_viewport_update,
                on_rendering_changed=self._refresh_rendering_panel,
            )

            self._rendering_controller.set_center_tabs(self._center_tabs)

            # Register editor display and mark it as non-serializable
            RenderingManager.instance().add_display(self._editor_display, "Editor")
            self._rendering_controller.set_editor_display_ptr(self._editor_display.tc_display_ptr)

            # Create editor scene attachment (now with rendering controller)
            self._editor_attachment = EditorSceneAttachment(
                display=self._editor_display,
                rendering_controller=self._rendering_controller,
                make_editor_pipeline=make_editor_pipeline,
            )
            self._editor_attachment.attach(self.scene, restore_state=False)
            self._setup_editor_viewport_input_managers(self._editor_display)

            # EditorStateIO for save/load
            self._editor_state_io = EditorStateIO(
                self._editor_attachment,
                self._interaction_system,
            )
            self._editor_state_io.get_scene = lambda: self.scene
            self._editor_state_io.on_entity_selected = self._on_entity_selected_from_state
            self._editor_state_io.get_displays_data = self._rendering_controller.get_displays_data
            self._editor_state_io.set_displays_data = self._rendering_controller.set_displays_data

            self._interaction_system.selection.on_selection_changed = self._on_selection_changed
            self._interaction_system.selection.on_hover_changed = self._on_hover_changed
            self._interaction_system.on_request_update = self._request_viewport_update

        self._refresh_rendering_panel()

        # Setup menu bar (after scene tree and inspector are ready)
        self._setup_menu_bar(menu_bar)
        menu_bar.register_shortcuts(ui)

        # Load settings and last scene
        EditorSettings.instance().init_text_editor_if_empty()
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

    def _setup_viewport(self) -> None:
        """Create FBO surface, editor display, and connect to Viewport3D."""
        self._fbo_surface = FBOSurface(width=800, height=600)

        try:
            from termin.visualization.core.display import Display
            display = Display(surface=self._fbo_surface, name="Editor")
            display.connect_input()
            self._editor_display = display

            if self._viewport_widget is not None:
                self._viewport_widget.set_surface(self._fbo_surface, display)
                self._viewport_widget.on_before_resize = self._on_before_viewport_resize

            # Setup FBO on_resize to recreate viewport/display connection
            self._fbo_surface.on_resize = self._on_fbo_resized
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
            on_scene_properties=self._show_scene_properties,
            on_layers_settings=self._show_layers_settings,
            on_shadow_settings=self._show_shadow_settings,
            on_pipeline_editor=self._show_pipeline_editor,
            on_toggle_game_mode=self._toggle_game_mode,
            on_run_standalone=self._run_standalone,
            on_show_undo_stack_viewer=self._show_undo_stack_viewer,
            on_show_framegraph_debugger=self._show_framegraph_debugger,
            on_show_resource_manager_viewer=self._show_resource_manager_viewer,
            on_show_audio_debugger=self._show_audio_debugger,
            on_show_core_registry_viewer=self._show_core_registry_viewer,
            on_show_inspect_registry_viewer=self._show_inspect_registry_viewer,
            on_show_navmesh_registry_viewer=self._show_navmesh_registry_viewer,
            on_show_scene_manager_viewer=self._show_scene_manager_viewer,
            on_toggle_profiler=self._toggle_profiler,
            on_toggle_modules=self._toggle_modules,
            on_toggle_fullscreen=self._toggle_fullscreen,
            on_show_agent_types=self._show_agent_types,
            on_show_spacemouse_settings=self._show_spacemouse_settings,
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

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def push_undo_command(self, cmd: UndoCommand, merge: bool = False) -> None:
        self.undo_stack.push(cmd, merge=merge)
        self._request_viewport_update()
        self._update_undo_redo_actions()

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
        self._update_undo_redo_actions()

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
        self._update_undo_redo_actions()

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
        self._request_viewport_update()
        if self._inspector_controller is not None and entity:
            self._inspector_controller.show_entity_inspector(entity)

    def _on_hover_changed(self, entity) -> None:
        self._request_viewport_update()

    def _on_inspector_transform_changed(self) -> None:
        self._request_viewport_update()

    def _on_inspector_component_changed(self) -> None:
        self._request_viewport_update()

    # ------------------------------------------------------------------
    # Viewport update
    # ------------------------------------------------------------------

    def _request_viewport_update(self) -> None:
        self.scene_manager.request_render()

    # ------------------------------------------------------------------
    # Scene file operations
    # ------------------------------------------------------------------

    def _new_scene(self) -> None:
        # TODO: confirm dialog if unsaved changes
        old_scene_name = self._editor_scene_name
        self.scene_manager.create_scene(self._editor_scene_name)
        self.scene_manager.set_mode(self._editor_scene_name, SceneMode.STOP)
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(self.scene)
            self.scene_tree_controller.rebuild()
        self._update_window_title()

    def _save_scene(self) -> None:
        from termin.editor.settings import EditorSettings
        settings = EditorSettings.instance()
        last_file = settings.get("last_scene_file")
        if last_file:
            self._save_scene_to_file(last_file)
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
            self.scene_manager.create_scene(self._editor_scene_name)
            self.scene_manager.set_mode(self._editor_scene_name, SceneMode.STOP)
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(self.scene)
            self.scene_tree_controller.rebuild()
        self._update_window_title()

    def _save_scene_to_file(self, path: str) -> None:
        if not path:
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
        except Exception as e:
            log.error(f"Failed to save scene: {e}")
            self._log_to_console(f"Error saving: {e}")

    def _load_scene_from_file(self, path: str) -> None:
        if not path:
            return
        try:
            scene_name = self._editor_scene_name

            # Close existing scene
            if self.scene_manager.has_scene(scene_name):
                self.scene_manager.close_scene(scene_name)

            self.scene_manager.load_scene(scene_name, path)
            self.scene_manager.set_mode(scene_name, SceneMode.STOP)

            EditorSettings.instance().set_last_scene_path(path)
            from termin.project.settings import ProjectSettingsManager
            ProjectSettingsManager.instance().set_last_scene(path)

            self._log_to_console(f"Loaded: {path}")
            if self.scene_tree_controller is not None:
                self.scene_tree_controller.set_scene(self.scene)
                self.scene_tree_controller.rebuild()
            if self._inspector_controller is not None:
                self._inspector_controller.set_scene(self.scene)
                self._inspector_controller.clear()
            # Extract editor data from file before attach
            editor_data = EditorStateIO.extract_from_file(path)

            if self._editor_attachment is not None:
                self._editor_attachment.attach(self.scene, restore_state=False)
                if self._editor_display is not None:
                    self._setup_editor_viewport_input_managers(self._editor_display)

            # Apply editor state (camera, selection, etc.)
            if self._editor_state_io is not None:
                self._editor_state_io.apply(editor_data)
            self._refresh_rendering_panel()
            self._request_viewport_update()
        except Exception as e:
            log.error(f"Failed to load scene: {e}")
            self._log_to_console(f"Error loading: {e}")

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
        from tcgui.widgets.file_dialog_overlay import show_open_directory_dialog
        show_open_directory_dialog(
            self._ui,
            title="New Project — Select Directory",
            on_result=lambda path: self._init_project(path) if path else None,
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

    def _init_project(self, path: str) -> None:
        self._current_project_path = path
        self._project_name = Path(path).name
        self._log_to_console(f"Project: {path}")
        if self._project_browser is not None:
            self._project_browser.set_root(path)

    def _load_project(self, path: str) -> None:
        project_dir = str(Path(path).parent)
        self._current_project_path = project_dir
        self._project_name = Path(path).stem
        self._log_to_console(f"Project: {project_dir}")

        # Initialize project settings
        from termin.project.settings import ProjectSettingsManager
        ProjectSettingsManager.instance().set_project_path(Path(project_dir))

        EditorSettings.instance().set("last_project_file", path)

        self._rescan_file_resources()
        if self._project_browser is not None:
            self._project_browser.set_root(project_dir)

    def _on_project_file_activated(self, path: str) -> None:
        """Called when a file is double-clicked in the project browser."""
        p = Path(path)
        ext = p.suffix.lower()
        if ext == ".tc_scene":
            self._load_scene_from_file(path)
        elif ext == ".tc_prefab":
            self._open_prefab(path)
        else:
            from termin.editor.external_editor import open_in_text_editor
            try:
                open_in_text_editor(path)
            except Exception as e:
                log.error(f"Failed to open file in text editor: {e}")

    # ------------------------------------------------------------------
    # Rename entity dialog
    # ------------------------------------------------------------------

    def _rename_entity_dialog(self, entity) -> None:
        from termin.visualization.core.entity import Entity
        if self._ui is None or not isinstance(entity, Entity):
            return
        old_name = entity.name or ""
        show_input_dialog(
            self._ui,
            title="Rename Entity",
            message="Name:",
            default=old_name,
            on_result=lambda new_name: self._do_rename_entity(entity, old_name, new_name),
        )

    def _do_rename_entity(self, entity, old_name: str, new_name: str | None) -> None:
        if new_name is None:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return
        from termin.editor.editor_commands import RenameEntityCommand
        cmd = RenameEntityCommand(entity, old_name, new_name)
        self.push_undo_command(cmd, False)
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.update_entity(entity)
        self._request_viewport_update()

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
        show_shadow_settings_dialog(self._ui, self.scene, on_changed=self._request_viewport_update)

    def _show_agent_types(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.agent_types_dialog import show_agent_types_dialog
        show_agent_types_dialog(self._ui)

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
        from termin.editor.spacemouse_controller import SpaceMouseController
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
        show_resource_manager_viewer(self._ui)

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
            self._ui, self._graphics, self._rendering_controller)

    def _show_audio_debugger(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.audio_debugger import show_audio_debugger
        show_audio_debugger(self._ui)

    def _show_scene_manager_viewer(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.scene_manager_viewer import show_scene_manager_viewer

        def _on_scene_edited(scene_name: str):
            self._editor_scene_name = scene_name
            self._sync_attachment_refs()
            if self._interaction_system is not None:
                self._interaction_system.selection.clear()
                self._interaction_system.set_gizmo_target(None)
            if self.scene_tree_controller is not None:
                scene = self.scene_manager.get_scene(scene_name)
                if scene is not None:
                    self.scene_tree_controller.set_scene(scene)
                    self.scene_tree_controller.rebuild()
            self._update_window_title()
            self._request_viewport_update()

        show_scene_manager_viewer(
            self._ui,
            self.scene_manager,
            get_rendering_controller=lambda: self._rendering_controller,
            get_editor_attachment=lambda: self._editor_attachment,
            on_scene_edited=_on_scene_edited,
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

    def _toggle_game_mode(self) -> None:
        if self._game_scene_name is not None:
            self._stop_game_mode()
        else:
            self._start_game_mode()

    def _start_game_mode(self) -> None:
        if self._game_scene_name is not None:
            return
        if self._editor_scene_name is None:
            return

        editor_scene = self.scene_manager.get_scene(self._editor_scene_name)
        if editor_scene is None:
            return

        # Save expanded tree nodes
        if self.scene_tree_controller is not None:
            self._saved_tree_expanded_uuids = (
                self.scene_tree_controller.get_expanded_entity_uuids()
            )

        # Save editor viewport camera to scene
        self._save_editor_viewport_camera_to_scene(editor_scene)

        # Save viewport configs before copying
        if self._rendering_controller is not None:
            self._rendering_controller.sync_viewport_configs_to_scene(editor_scene)

        # Save editor entities state
        if self._editor_attachment is not None:
            self._editor_attachment.save_state()

        # Copy scene for game mode
        self._game_scene_name = f"{self._editor_scene_name}(game)"
        self.scene_manager.copy_scene(
            self._editor_scene_name,
            self._game_scene_name,
        )

        # Detach editor scene from rendering BEFORE attaching game scene
        if self._rendering_controller is not None:
            self._rendering_controller.detach_scene(editor_scene)

        # Attach to game scene
        game_scene = self.scene_manager.get_scene(self._game_scene_name)
        if self._editor_attachment is not None:
            self._editor_attachment.attach(game_scene, transfer_camera_state=True)
            self._setup_editor_viewport_input_managers(self._editor_attachment._display)

        # Set modes
        self.scene_manager.set_mode(self._editor_scene_name, SceneMode.INACTIVE)
        self.scene_manager.set_mode(self._game_scene_name, SceneMode.PLAY)

        self._on_game_mode_changed(True, game_scene)

    def _stop_game_mode(self) -> None:
        if self._game_scene_name is None:
            return

        # Detach from game scene (discard changes)
        if self._editor_attachment is not None:
            self._editor_attachment.detach(save_state=False)

        # Detach game scene from rendering
        game_scene = self.scene_manager.get_scene(self._game_scene_name)
        if game_scene is not None and self._rendering_controller is not None:
            self._rendering_controller.detach_scene(game_scene)

        # Close game scene
        self.scene_manager.close_scene(self._game_scene_name)
        self._game_scene_name = None

        # Return to editor scene
        self.scene_manager.set_mode(self._editor_scene_name, SceneMode.STOP)
        editor_scene = self.scene_manager.get_scene(self._editor_scene_name)

        # Re-attach editor scene
        if self._editor_attachment is not None:
            self._editor_attachment.attach(editor_scene, restore_state=True)
            self._setup_editor_viewport_input_managers(self._editor_attachment._display)

        self._on_game_mode_changed(False, editor_scene)

    def _toggle_pause(self) -> None:
        if self._game_scene_name is None:
            return

        from tcgui.widgets.theme import current_theme as _t
        current_mode = self.scene_manager.get_mode(self._game_scene_name)
        if current_mode == SceneMode.PLAY:
            self.scene_manager.set_mode(self._game_scene_name, SceneMode.STOP)
            if self._pause_button is not None:
                self._pause_button.text = "Resume"
                self._pause_button.background_color = (0.85, 0.63, 0.29, 1.0)
        else:
            self.scene_manager.set_mode(self._game_scene_name, SceneMode.PLAY)
            if self._pause_button is not None:
                self._pause_button.text = "Pause"
                self._pause_button.background_color = _t.bg_surface

        self._request_viewport_update()

    def _on_game_mode_changed(self, is_playing: bool, scene) -> None:
        # Update scene tree
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(scene)
            self.scene_tree_controller.rebuild()
            if self._saved_tree_expanded_uuids:
                self.scene_tree_controller.set_expanded_entity_uuids(
                    self._saved_tree_expanded_uuids
                )
            if not is_playing:
                self._saved_tree_expanded_uuids = None

        # Clear inspector
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

    def _save_editor_viewport_camera_to_scene(self, scene) -> None:
        if self._rendering_controller is None:
            return
        if self._editor_display is None or not self._editor_display.viewports:
            return
        viewport = self._editor_display.viewports[0]
        camera_name = None
        if viewport.camera is not None and viewport.camera.entity is not None:
            camera_name = viewport.camera.entity.name
        scene.set_metadata_value("termin.editor.viewport_camera_name", camera_name)

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

    def _show_undo_stack_viewer(self) -> None:
        if self._ui is None:
            return
        from termin.editor_tcgui.dialogs.undo_stack_viewer import show_undo_stack_viewer
        show_undo_stack_viewer(self._ui, self.undo_stack)

    # ------------------------------------------------------------------
    # Debug panels (Profiler / Modules)
    # ------------------------------------------------------------------

    def _toggle_profiler(self) -> None:
        self._profiler_visible = not self._profiler_visible
        self._update_debug_panel_visibility()

    def _toggle_modules(self) -> None:
        self._modules_visible = not self._modules_visible
        self._update_debug_panel_visibility()

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

    def _load_material_from_file(self) -> None:
        pass  # TODO

    def _load_components_from_file(self) -> None:
        pass  # TODO

    def _deploy_stdlib(self) -> None:
        pass  # TODO

    def _migrate_spec_to_meta(self) -> None:
        pass  # TODO

    def close(self) -> None:
        self._should_close = True

    def _update_window_title(self) -> None:
        pass  # Status bar or window title update

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

    def _refresh_rendering_panel(self) -> None:
        """Rebuild the rendering tree to show all Display > Viewport > Entity hierarchies."""
        if self._rendering_tree is None:
            return
        from tcgui.widgets.tree import TreeNode

        # Clear existing
        for node in list(self._rendering_tree.root_nodes):
            self._rendering_tree.remove_root(node)

        # Get all displays from RenderingManager
        from termin._native.render import RenderingManager
        rm = RenderingManager.instance()
        displays = rm.displays

        for display in displays:
            display_name = display.name if display.name else "Display"
            display_node = self._make_render_tree_node(display_name)
            display_node.data = display

            for vp in display.viewports:
                vp_name = vp.name if vp.name else "Viewport"
                camera_name = "No Camera"
                camera = vp.camera
                if camera is not None:
                    entity = camera.entity
                    if entity is not None:
                        camera_name = entity.name or "Camera"
                vp_node = self._make_render_tree_node(f"{vp_name} ({camera_name})")
                vp_node.data = vp

                # Internal entities hierarchy
                internal = vp.internal_entities
                if internal is not None:
                    self._add_entity_to_render_tree(vp_node, internal)

                display_node.add_node(vp_node)

            self._rendering_tree.add_root(display_node)
            display_node.expanded = True

    def _make_render_tree_node(self, text: str):
        from tcgui.widgets.tree import TreeNode
        lbl = Label()
        lbl.text = text
        node = TreeNode(lbl)
        return node

    def _add_entity_to_render_tree(self, parent_node, entity) -> None:
        name = entity.name or "(unnamed)"
        node = self._make_render_tree_node(name)
        node.data = entity
        parent_node.add_node(node)
        for child_tf in entity.transform.children:
            child_entity = child_tf.entity
            if child_entity is not None:
                self._add_entity_to_render_tree(node, child_entity)

    def _rescan_file_resources(self) -> None:
        project_path = self._get_project_path()
        if project_path:
            try:
                self._project_file_watcher.watch_directory(project_path)
            except Exception as e:
                log.error(f"Resource scan failed: {e}")

    def _register_file_processors(self) -> None:
        for processor_cls in [
            MaterialPreLoader,
            GlslPreLoader,
            ShaderFileProcessor,
            TextureFileProcessor,
            ComponentFileProcessor,
            PipelinePreLoader,
            ScenePipelinePreLoader,
            MeshFileProcessor,
            VoxelGridProcessor,
            NavMeshProcessor,
            GLBPreLoader,
            PrefabPreLoader,
            AudioPreLoader,
            UIPreLoader,
        ]:
            try:
                self._project_file_watcher.register_processor(
                    processor_cls(
                        resource_manager=self.resource_manager,
                        on_resource_reloaded=self._on_resource_reloaded,
                    )
                )
            except Exception as e:
                log.error(f"Failed to register processor {processor_cls.__name__}: {e}")

    # ------------------------------------------------------------------
    # Scene / scene manager callbacks
    # ------------------------------------------------------------------

    def _on_before_scene_close(self, scene_name: str) -> None:
        pass

    def switch_to_scene(self, scene_name: str) -> None:
        self._editor_scene_name = scene_name
        scene = self.scene_manager.get_scene(scene_name)
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(scene)
            self.scene_tree_controller.rebuild()
        if self._inspector_controller is not None:
            self._inspector_controller.set_scene(scene)
            self._inspector_controller.clear()

    def _open_prefab(self, path: str) -> None:
        pass  # TODO

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

    def _after_render(self) -> None:
        pass
