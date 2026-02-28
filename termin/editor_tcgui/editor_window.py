"""EditorWindowTcgui — main editor window implemented with tcgui."""

from __future__ import annotations

import os
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
    ) -> None:
        self._world = world
        self._graphics = graphics
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
        self._current_project_path: str | None = None
        self._project_name: str | None = None

        # Setup ResourceLoader and ProjectFileWatcher
        self._resource_loader = ResourceLoader(
            parent=None,
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
        left_tabs.preferred_width = px(280)

        scene_tab_content = VStack()
        scene_tab_content.spacing = 4

        from tcgui.widgets.tree import TreeWidget
        scene_tree = TreeWidget()
        scene_tree.stretch = True
        scene_tab_content.add_child(scene_tree)
        left_tabs.add_tab("Scene", scene_tab_content)

        rendering_tab_content = VStack()
        rendering_tab_content.add_child(Label())  # placeholder
        left_tabs.add_tab("Rendering", rendering_tab_content)

        main_area.add_child(left_tabs)
        main_area.add_child(Splitter(target=left_tabs, side="right"))

        # --- Center: Viewport3D ---
        self._viewport_widget = Viewport3D()
        self._viewport_widget.stretch = True
        main_area.add_child(self._viewport_widget)

        # --- Right panel: Inspector ---
        right_scroll = ScrollArea()
        right_scroll.preferred_width = px(320)
        inspector_container = VStack()
        inspector_container.spacing = 4
        right_scroll.add_child(inspector_container)
        main_area.add_child(Splitter(target=right_scroll, side="left"))
        main_area.add_child(right_scroll)

        root.add_child(main_area)

        # --- Bottom: TabView [Project | Console] ---
        bottom_tabs = TabView()
        bottom_tabs.preferred_height = px(200)

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

        # Setup editor display and attach to scene
        if self._editor_display is not None:
            from termin.editor.editor_scene_attachment import EditorSceneAttachment
            from termin.editor.editor_pipeline import make_editor_pipeline
            self._editor_attachment = EditorSceneAttachment(
                display=self._editor_display,
                rendering_controller=None,
                make_editor_pipeline=make_editor_pipeline,
            )
            self._editor_attachment.attach(self.scene, restore_state=False)

            self._interaction_system.selection.on_selection_changed = self._on_selection_changed
            self._interaction_system.selection.on_hover_changed = self._on_hover_changed
            self._interaction_system.on_request_update = self._request_viewport_update

        # Setup menu bar (after scene tree and inspector are ready)
        self._setup_menu_bar(menu_bar)
        menu_bar.register_shortcuts(ui)

        # Load settings and last scene
        EditorSettings.instance().init_text_editor_if_empty()
        self._rescan_file_resources()
        self._load_last_scene()

        self._update_window_title()

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
            on_show_undo_stack_viewer=self._noop,
            on_show_framegraph_debugger=self._noop,
            on_show_resource_manager_viewer=self._noop,
            on_show_audio_debugger=self._noop,
            on_show_core_registry_viewer=self._noop,
            on_show_inspect_registry_viewer=self._noop,
            on_show_navmesh_registry_viewer=self._noop,
            on_show_scene_manager_viewer=self._noop,
            on_toggle_profiler=self._noop,
            on_toggle_modules=self._noop,
            on_toggle_fullscreen=self._noop,
            on_show_agent_types=self._noop,
            on_show_spacemouse_settings=self._noop,
            can_undo=lambda: self.undo_stack.can_undo,
            can_redo=lambda: self.undo_stack.can_redo,
            is_fullscreen=lambda: False,
            is_profiler_visible=lambda: False,
            is_modules_visible=lambda: False,
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

    def _on_tree_object_selected(self, obj) -> None:
        if self._inspector_controller is not None:
            self._inspector_controller.resync_from_tree_selection(obj)

        if self._interaction_system is not None:
            from termin.visualization.core.entity import Entity
            if isinstance(obj, Entity):
                self._interaction_system.selection.select(obj)
            else:
                self._interaction_system.selection.clear()

    def _on_selection_changed(self, entities) -> None:
        self._request_viewport_update()
        if self._inspector_controller is not None and entities:
            self._inspector_controller.show_entity_inspector(entities[0])

    def _on_hover_changed(self) -> None:
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
        initial_dir = project_path or str(Path.home())
        from tcgui.widgets.file_dialog_overlay import show_save_file_dialog
        show_save_file_dialog(
            self._ui,
            title="Save Scene As",
            initial_dir=initial_dir,
            filter_string="Scene Files (*.tc_scene);;All Files (*)",
            on_result=lambda path: self._save_scene_to_file(path) if path else None,
        )

    def _load_scene(self) -> None:
        if self._ui is None:
            return
        project_path = self._get_project_path()
        initial_dir = project_path or str(Path.home())
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog
        show_open_file_dialog(
            self._ui,
            title="Load Scene",
            initial_dir=initial_dir,
            filter_string="Scene Files (*.tc_scene);;All Files (*)",
            on_result=lambda path: self._load_scene_from_file(path) if path else None,
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
        scene = self.scene
        if scene is None:
            return
        try:
            from termin.editor.scene_serializer import SceneSerializer
            SceneSerializer.save(scene, path)
            from termin.editor.settings import EditorSettings
            EditorSettings.instance().set("last_scene_file", path)
            self._log_to_console(f"Saved: {path}")
        except Exception as e:
            log.error(f"Failed to save scene: {e}")
            self._log_to_console(f"Error saving: {e}")

    def _load_scene_from_file(self, path: str) -> None:
        if not path:
            return
        try:
            from termin.editor.scene_serializer import SceneSerializer
            scene_name = self._editor_scene_name
            self.scene_manager.create_scene(scene_name)
            self.scene_manager.set_mode(scene_name, SceneMode.STOP)
            scene = self.scene_manager.get_scene(scene_name)
            SceneSerializer.load(scene, path)
            from termin.editor.settings import EditorSettings
            EditorSettings.instance().set("last_scene_file", path)
            self._log_to_console(f"Loaded: {path}")
            if self.scene_tree_controller is not None:
                self.scene_tree_controller.set_scene(scene)
                self.scene_tree_controller.rebuild()
            if self._inspector_controller is not None:
                self._inspector_controller.set_scene(scene)
                self._inspector_controller.clear()
            self._request_viewport_update()
        except Exception as e:
            log.error(f"Failed to load scene: {e}")
            self._log_to_console(f"Error loading: {e}")

    def _load_last_scene(self) -> None:
        from termin.editor.settings import EditorSettings
        last_file = EditorSettings.instance().get("last_scene_file")
        if last_file and Path(last_file).exists():
            self._load_scene_from_file(last_file)

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
        )

    def _open_project(self) -> None:
        if self._ui is None:
            return
        from tcgui.widgets.file_dialog_overlay import show_open_file_dialog
        show_open_file_dialog(
            self._ui,
            title="Open Project",
            filter_string="Project Files (*.terminproj);;All Files (*)",
            on_result=lambda path: self._load_project(path) if path else None,
        )

    def _init_project(self, path: str) -> None:
        self._current_project_path = path
        self._project_name = Path(path).name
        self._log_to_console(f"Project: {path}")
        self._project_file_watcher.set_root(path)
        if self._project_browser is not None:
            self._project_browser.set_root(path)

    def _load_project(self, path: str) -> None:
        project_dir = str(Path(path).parent)
        self._current_project_path = project_dir
        self._project_name = Path(path).stem
        self._log_to_console(f"Project: {path}")
        self._project_file_watcher.set_root(project_dir)
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
        pass  # TODO: settings dialog

    def _show_project_settings(self) -> None:
        pass  # TODO

    def _show_scene_properties(self) -> None:
        pass  # TODO

    def _show_layers_settings(self) -> None:
        pass  # TODO

    def _show_shadow_settings(self) -> None:
        pass  # TODO

    def _show_pipeline_editor(self) -> None:
        pass  # TODO

    def _toggle_game_mode(self) -> None:
        pass  # TODO

    def _run_standalone(self) -> None:
        pass  # TODO

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

    def _rescan_file_resources(self) -> None:
        project_path = self._get_project_path()
        if project_path:
            try:
                self._resource_loader.scan_project(project_path)
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
    # After render (called per-frame)
    # ------------------------------------------------------------------

    def _after_render(self) -> None:
        pass
