"""EditorWindowTcgui — main editor window implemented with tcgui."""

from __future__ import annotations

import os
import time
import shutil
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
from tcgui.widgets.message_box import MessageBox

from termin.editor_core.undo_stack import UndoStack, UndoCommand
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
from termin.editor_tcgui.project_build_controller import ProjectBuildController
from termin.editor_tcgui.project_session_controller import ProjectSessionController
from termin.editor_tcgui.scene_file_controller import SceneFileController
from termin.editor_tcgui.editor_window_layout import (
    EditorWindowLayoutCallbacks,
    build_editor_window_layout,
)
from termin.editor_tcgui.viewport_interaction_hub import ViewportInteractionHub
from termin.editor_tcgui.viewport_geometry_controller import (
    ViewportGeometryController,
    is_gltf_project_file_drag,
)
from termin.editor_tcgui.editor_interaction_coordinator import (
    EditorInteractionCoordinator,
)
from termin.editor_tcgui.debug_panel_controller import DebugPanelController
from termin.editor_tcgui.fullscreen_controller import FullscreenController
from termin.editor_tcgui.prefab_toolbar_controller import PrefabToolbarController
from termin.editor_tcgui.game_mode_ui_controller import GameModeUiController
from termin.editor_tcgui.resource_actions_controller import ResourceActionsController
from termin.editor_tcgui.editor_dialog_launcher import EditorDialogLauncher
from termin.editor_tcgui.component_extension_panel_controller import (
    ComponentExtensionPanelController,
)
from termin.editor_tcgui.project_file_action_controller import ProjectFileActionController
from termin.editor_tcgui.scene_tree_controller import SceneTreeControllerTcgui
from termin.editor_tcgui.inspector_controller import InspectorControllerTcgui
from termin.editor_tcgui.project_browser import ProjectBrowserTcgui
from termin.editor_tcgui.default_component_editor_extensions import (
    register_default_component_editor_extensions,
)
from termin.editor_tcgui.editor_camera_ui_controller import EditorCameraUIController

SceneMode = engine_scene.SceneMode


def _resolve_termin_shaderc() -> Path | None:
    configured = os.environ.get("TERMIN_SHADERC")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        log.error(f"[ShaderRuntime] TERMIN_SHADERC points to missing file: {configured}")
        return None

    sdk = os.environ.get("TERMIN_SDK")
    if sdk:
        candidate = Path(sdk) / "bin" / "termin_shaderc"
        if candidate.is_file():
            return candidate

    local_sdk = Path(__file__).resolve().parents[3] / "sdk" / "bin" / "termin_shaderc"
    if local_sdk.is_file():
        return local_sdk

    found = shutil.which("termin_shaderc")
    if found:
        return Path(found)
    return None


def _resolve_slangc() -> Path | None:
    settings_path = EditorSettings.instance().get_slang_compiler()
    if settings_path:
        path = Path(settings_path)
        if path.is_file():
            return path
        log.error(f"[ShaderRuntime] configured Slang compiler is missing: {settings_path}")
        return None

    configured = os.environ.get("TERMIN_SLANGC")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        log.error(f"[ShaderRuntime] TERMIN_SLANGC points to missing file: {configured}")
        return None

    found = shutil.which("slangc")
    if found:
        return Path(found)

    sdk = os.environ.get("TERMIN_SDK")
    if sdk:
        candidate = Path(sdk) / "bin" / "slangc"
        if candidate.is_file():
            return candidate

    return None


class EditorWindowTcgui:
    """Main editor window for the tcgui frontend.

    Does not inherit from any UI framework class — the UI is built in ``build(ui)``.
    Domain logic lives in editor_core where possible.
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
        self.resource_manager.register_component(
            "EditorCameraUIController",
            EditorCameraUIController,
        )
        register_default_component_editor_extensions()

        # Scene manager
        self.scene_manager = scene_manager
        self.scene_manager.set_on_before_scene_close(self._on_before_scene_close)
        # Pump EditorInteractionSystem's pending press / release / hover at the
        # exact moment the render finishes. Without
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
        # Owns DisplayInputRouter instances that route surface events to the
        # per-viewport EditorViewportInputManagers. Populated by
        # _attach_editor_input_router() after the editor display's input
        # managers are created. Without this the surface's input_manager_ptr
        # stays on the default (scene-pipeline) router and Viewport3D never
        # hits the editor picking / hover / gizmo paths.
        self._display_routers: dict[int, object] = {}
        self._current_project_path: str | None = None
        self._project_name: str | None = None
        self._fullscreen = FullscreenController(
            get_panels=self._fullscreen_panels,
            update_fullscreen_action=self._update_fullscreen_action,
        )
        self._editor_state_io: EditorStateIO | None = None
        self._viewport_list = None
        self._left_tabs: TabView | None = None
        self._component_extension_panels = ComponentExtensionPanelController(
            get_editor=lambda: self,
            get_left_tabs=lambda: self._left_tabs,
            get_inspector_controller=lambda: self._inspector_controller,
        )
        self._project_file_actions = ProjectFileActionController(
            load_scene_from_file=self._load_scene_from_file,
            open_prefab=self._open_prefab,
            get_inspector_controller=lambda: self._inspector_controller,
        )
        self._right_scroll: ScrollArea | None = None
        self._bottom_tabs: TabView | None = None
        self._menu_bar_widget: MenuBar | None = None
        self._left_splitter: Splitter | None = None
        self._right_splitter: Splitter | None = None
        self._bottom_splitter: Splitter | None = None
        self._center_tabs: TabView | None = None
        self._prefab_toolbar: HStack | None = None
        self._prefab_toolbar_label: Label | None = None
        self._save_prefab_button = None
        self._exit_prefab_button = None
        self._prefab_toolbar_controller = PrefabToolbarController()
        self._game_mode_ui = GameModeUiController(
            update_play_action=self._update_play_action,
            update_window_title=self._update_window_title,
            request_viewport_update=self._request_viewport_update,
        )
        self._pre_prefab_scene_name: str | None = None
        self.prefab_edit_controller: PrefabEditController | None = None
        # Game mode state + transitions live in GameModeModel. The model is
        # created after editor_attachment/rendering_controller exist (end of build()).
        self._game_mode_model = None
        self._saved_tree_expanded_uuids: list[str] | None = None
        self._spacemouse = None
        self._dialog_launcher = EditorDialogLauncher(
            get_ui=lambda: self._ui,
            get_scene=lambda: self.scene,
            scene_manager=self.scene_manager,
            get_game_scene_name=lambda: self._game_scene_name,
            get_project_path=self._get_project_path,
            get_rendering_controller=lambda: self._rendering_controller,
            get_fbo_surface=lambda: self._fbo_surface,
            get_project_file_watcher=lambda: self._project_file_watcher,
            get_editor_attachment=lambda: self._editor_attachment,
            attach_scene_to_render=self.attach_scene_to_render,
            detach_scene_from_render=self.detach_scene_from_render,
            attach_editor_to_scene=self.attach_editor_to_scene,
            detach_editor_from_scene=self.detach_editor_from_scene,
            request_viewport_update=self._request_viewport_update,
            push_undo_command=self.push_undo_command,
            undo_stack=self.undo_stack,
            undo_stack_changed=self.undo_stack_changed,
            log_to_console=self._log_to_console,
            get_spacemouse=lambda: self._spacemouse,
            set_spacemouse=self._set_spacemouse,
        )

        # Debug panels (Profiler / Modules)
        self._debug_panel: TabView | None = None
        self._debug_splitter: Splitter | None = None
        self._profiler_panel = None
        self._modules_panel = None
        self._debug_panels = DebugPanelController(
            get_ui=lambda: self._ui,
            update_profiler_action=self._update_profiler_action,
            update_modules_action=self._update_modules_action,
        )
        self._surface_edge_debug_tool = None
        self._scene_event_subscription = None
        self._scene_tree_rebuild_pending: bool = False
        self._viewport_interactions = ViewportInteractionHub(
            request_viewport_update=self._request_viewport_update,
            on_tool_activity_changed=self._sync_gizmo_target,
        )
        self._interaction_coordinator = EditorInteractionCoordinator(
            undo_stack=self.undo_stack,
            undo_stack_changed=self.undo_stack_changed,
            get_interaction_system=lambda: self._interaction_system,
            get_scene_tree_controller=lambda: self.scene_tree_controller,
            get_inspector_controller=lambda: self._inspector_controller,
            get_menu_bar_controller=lambda: self._menu_bar_controller,
            get_editor_display=lambda: self._editor_display,
            get_active_viewport_tool_count=lambda: (
                self._viewport_interactions.active_tool_count
            ),
            dispatch_viewport_click=self._viewport_interactions.dispatch_click,
            dispatch_viewport_pointer=self._viewport_interactions.dispatch_pointer,
            dispatch_viewport_key=self._viewport_interactions.dispatch_key,
            request_viewport_update=self._request_viewport_update,
        )
        self._viewport_geometry = ViewportGeometryController(
            get_camera=lambda: self.camera,
            get_viewport_widget=lambda: self._viewport_widget,
            get_interaction_system=lambda: self._interaction_system,
            get_editor_display=lambda: self._editor_display,
            get_scene_tree_controller=lambda: self.scene_tree_controller,
        )

        # Setup ResourceLoader and ProjectFileWatcher
        self._resource_loader = ResourceLoader(
            resource_manager=self.resource_manager,
            get_scene=lambda: self.scene,
            get_project_path=self._get_project_path,
            on_resource_reloaded=self._on_resource_reloaded,
            log_message=self._log_to_console,
        )
        self._resource_loader.scan_builtin_components()
        self._resource_actions = ResourceActionsController(
            get_ui=lambda: self._ui,
            get_project_path=self._get_project_path,
            resource_loader=self._resource_loader,
            get_inspector_controller=lambda: self._inspector_controller,
            request_viewport_update=self._request_viewport_update,
        )

        self._project_file_watcher = ProjectFileWatcher(
            on_resource_reloaded=self._on_resource_reloaded,
        )
        self._register_file_processors()
        self._project_session_controller = ProjectSessionController(
            get_ui=lambda: self._ui,
            set_project_state=self._set_project_state,
            log_to_console=self._log_to_console,
            rescan_file_resources=self._rescan_file_resources,
            set_project_browser_root=self._set_project_browser_root,
            get_init_script_editor=lambda: self,
            resolve_termin_shaderc=_resolve_termin_shaderc,
            resolve_slangc=_resolve_slangc,
        )
        self._scene_file_controller = SceneFileController(
            scene_manager=self.scene_manager,
            get_ui=lambda: self._ui,
            get_editor_scene_name=lambda: self._editor_scene_name,
            set_editor_scene_name=self._set_editor_scene_name,
            get_scene=lambda: self.scene,
            get_project_path=self._get_project_path,
            get_editor_state_io=lambda: self._editor_state_io,
            has_editor_attachment=lambda: self._editor_attachment is not None,
            detach_editor_from_scene=self.detach_editor_from_scene,
            detach_scene_from_render=self.detach_scene_from_render,
            attach_editor_to_scene=self.attach_editor_to_scene,
            attach_scene_to_render=self.attach_scene_to_render,
            get_scene_tree_controller=lambda: self.scene_tree_controller,
            get_inspector_controller=lambda: self._inspector_controller,
            observe_scene_events=self._observe_scene_events,
            on_rendering_changed=self._on_rendering_changed,
            request_viewport_update=self._request_viewport_update,
            update_window_title=self._update_window_title,
            log_to_console=self._log_to_console,
        )
        self._project_build_controller = ProjectBuildController(
            scene_manager=self.scene_manager,
            get_current_project_path=self._get_project_path,
            get_editor_scene_name=lambda: self._editor_scene_name,
            get_ui=lambda: self._ui,
            save_scene=self._save_scene,
            log_to_console=self._log_to_console,
        )

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

        widgets = build_editor_window_layout(
            EditorWindowLayoutCallbacks(
                toggle_game_mode=self._toggle_game_mode,
                toggle_pause=self._toggle_pause,
                save_prefab=self._save_prefab,
                exit_prefab_editing=self._exit_prefab_editing,
                viewport_external_drag=self._on_viewport_external_drag,
                viewport_external_drop=self._on_viewport_external_drop,
            )
        )

        self._menu_bar_widget = widgets.menu_bar
        self._left_tabs = widgets.left_tabs
        self._viewport_list = widgets.viewport_list
        self._left_splitter = widgets.left_splitter
        self._prefab_toolbar = widgets.prefab_toolbar
        self._prefab_toolbar_label = widgets.prefab_toolbar_label
        self._save_prefab_button = widgets.save_prefab_button
        self._exit_prefab_button = widgets.exit_prefab_button
        self._game_mode_ui.set_widgets(
            play_button=widgets.play_button,
            pause_button=widgets.pause_button,
            status_bar=widgets.status_bar,
        )
        self._prefab_toolbar_controller.set_widgets(
            prefab_toolbar=widgets.prefab_toolbar,
            prefab_toolbar_label=widgets.prefab_toolbar_label,
            play_button=widgets.play_button,
        )
        self._center_tabs = widgets.center_tabs
        self._viewport_widget = widgets.viewport_widget
        self._right_scroll = widgets.right_scroll
        self._right_splitter = widgets.right_splitter
        self._debug_panel = widgets.debug_panel
        self._profiler_panel = widgets.profiler_panel
        self._modules_panel = widgets.modules_panel
        self._debug_splitter = widgets.debug_splitter
        self._debug_panels.set_widgets(
            debug_panel=widgets.debug_panel,
            debug_splitter=widgets.debug_splitter,
            profiler_panel=widgets.profiler_panel,
            modules_panel=widgets.modules_panel,
        )
        self._bottom_tabs = widgets.bottom_tabs
        self._bottom_splitter = widgets.bottom_splitter
        self._console_area = widgets.console_area
        self._status_bar = widgets.status_bar

        ui.root = widgets.root

        # Setup FBO surface and Viewport3D
        self._setup_viewport()

        # Dialog service (shared between controllers)
        from termin.editor_tcgui.tcgui_dialog_service import TcguiDialogService
        self._dialog_service = TcguiDialogService()
        self._dialog_service.ui = ui

        # Setup scene tree controller
        self.scene_tree_controller = SceneTreeControllerTcgui(
            tree_widget=widgets.scene_tree,
            scene=self.scene,
            undo_handler=self.push_undo_command,
            dialog_service=self._dialog_service,
            on_object_selected=self._on_tree_object_selected,
            request_viewport_update=self._request_viewport_update,
        )

        # Setup inspector controller
        self._inspector_controller = InspectorControllerTcgui(
            container=widgets.inspector_container,
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
            dir_tree=widgets.project_dir_tree,
            file_list=widgets.project_file_list,
            breadcrumb=widgets.project_breadcrumb,
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
            self._interaction_system.on_viewport_pointer_event = self._dispatch_viewport_pointer
            self._interaction_system.on_key = self._on_editor_key
            # Transform gizmo drag-end -> push an undo command.
            self._interaction_system.on_transform_end = self._on_transform_end

        self._on_rendering_changed()

        # Setup menu bar (after scene tree and inspector are ready)
        self._setup_menu_bar(widgets.menu_bar)
        widgets.menu_bar.register_shortcuts(ui)

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
            on_build_quest_openxr=self._show_quest_openxr_build_dialog,
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
            is_fullscreen=lambda: self._fullscreen.is_fullscreen,
            is_profiler_visible=lambda: self._debug_panels.profiler_visible,
            is_modules_visible=lambda: self._debug_panels.modules_visible,
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
        self._viewport_interactions.set_click_interceptor(callback)

    def add_viewport_click_interceptor(self, callback: Callable) -> None:
        self._viewport_interactions.add_click_interceptor(callback)

    def remove_viewport_click_interceptor(self, callback: Callable) -> None:
        self._viewport_interactions.remove_click_interceptor(callback)

    def add_viewport_pointer_handler(self, callback: Callable[[str, float, float, float, float, int, int, int], bool]) -> None:
        self._viewport_interactions.add_pointer_handler(callback)

    def remove_viewport_pointer_handler(self, callback: Callable[[str, float, float, float, float, int, int, int], bool]) -> None:
        self._viewport_interactions.remove_pointer_handler(callback)

    def add_viewport_key_handler(self, callback: Callable[[object], bool]) -> None:
        self._viewport_interactions.add_key_handler(callback)

    def remove_viewport_key_handler(self, callback: Callable[[object], bool]) -> None:
        self._viewport_interactions.remove_key_handler(callback)

    def add_viewport_overlay_drawer(self, callback: Callable[[], None]) -> None:
        self._viewport_interactions.add_overlay_drawer(callback)

    def remove_viewport_overlay_drawer(self, callback: Callable[[], None]) -> None:
        self._viewport_interactions.remove_overlay_drawer(callback)

    def begin_viewport_tool(self) -> None:
        self._viewport_interactions.begin_tool()

    def end_viewport_tool(self) -> None:
        self._viewport_interactions.end_tool()

    def _sync_gizmo_target(self) -> None:
        self._interaction_coordinator.sync_gizmo_target()

    def _on_inspector_component_selected(self, entity, component_ref) -> None:
        self._component_extension_panels.select_component(entity, component_ref)

    def _clear_component_editor_extension(self) -> None:
        self._component_extension_panels.clear()

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
        return is_gltf_project_file_drag(event)

    def _on_viewport_external_drop(self, event) -> bool:
        return self._viewport_geometry.on_external_drop(event)

    def _world_position_for_viewport_drop(self, x: float, y: float) -> tuple[float, float, float]:
        return self._viewport_geometry.world_position_for_viewport_drop(x, y)

    def _fallback_drop_position(self) -> tuple[float, float, float]:
        return self._viewport_geometry.fallback_drop_position()

    def world_point_on_oxy_plane(self, x: float, y: float) -> tuple[float, float, float] | None:
        return self._viewport_geometry.world_point_on_oxy_plane(x, y)

    def world_ray_from_viewport_point(
        self,
        x: float,
        y: float,
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        return self._viewport_geometry.world_ray_from_viewport_point(x, y)

    def project_world_point_to_viewport(
        self,
        point: tuple[float, float, float],
    ) -> tuple[float, float] | None:
        return self._viewport_geometry.project_world_point_to_viewport(point)

    def world_point_on_plane(
        self,
        x: float,
        y: float,
        plane_origin: tuple[float, float, float],
        plane_normal: tuple[float, float, float],
        label: str = "plane",
    ) -> tuple[float, float, float] | None:
        return self._viewport_geometry.world_point_on_plane(
            x,
            y,
            plane_origin,
            plane_normal,
            label,
        )

    def world_point_on_entity_local_oxy_plane(
        self,
        x: float,
        y: float,
        entity,
    ) -> tuple[float, float, float] | None:
        return self._viewport_geometry.world_point_on_entity_local_oxy_plane(
            x,
            y,
            entity,
        )

    # ------------------------------------------------------------------
    # Undo / Redo
    # ------------------------------------------------------------------

    def push_undo_command(self, cmd: UndoCommand, merge: bool = False) -> None:
        self._interaction_coordinator.push_undo_command(cmd, merge=merge)

    def undo(self) -> None:
        self._interaction_coordinator.undo()

    def redo(self) -> None:
        self._interaction_coordinator.redo()

    def _resync_inspector_from_selection(self) -> None:
        self._interaction_coordinator.resync_inspector_from_selection()

    def _update_undo_redo_actions(self) -> None:
        self._interaction_coordinator.update_undo_redo_actions()

    # ------------------------------------------------------------------
    # Selection / Inspector callbacks
    # ------------------------------------------------------------------

    def _on_entity_selected_from_state(self, entity) -> None:
        """Called by EditorStateIO when restoring selection from file."""
        self._interaction_coordinator.on_entity_selected_from_state(entity)

    def _on_tree_object_selected(self, obj) -> None:
        self._interaction_coordinator.on_tree_object_selected(obj)

    def _on_selection_changed(self, entity) -> None:
        self._interaction_coordinator.on_selection_changed(entity)

    def _on_hover_changed(self, entity) -> None:
        self._interaction_coordinator.on_hover_changed(entity)

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
        return self._interaction_coordinator.on_editor_viewport_click(*args)

    def _dispatch_viewport_pointer(
        self,
        phase: str,
        x: float,
        y: float,
        dx: float,
        dy: float,
        button: int,
        action: int,
        mods: int,
    ) -> bool:
        return self._interaction_coordinator.dispatch_viewport_pointer(
            phase, x, y, dx, dy, button, action, mods
        )

    def _on_editor_key(self, event) -> None:
        self._interaction_coordinator.on_editor_key(event)

    def _on_transform_end(self, old_pose, new_pose) -> None:
        self._interaction_coordinator.on_transform_end(old_pose, new_pose)

    def _update_gizmo_screen_scale(self) -> None:
        self._interaction_coordinator.update_gizmo_screen_scale()

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
        self._scene_file_controller.new_scene()

    def _do_new_scene(self) -> None:
        self._scene_file_controller.do_new_scene()

    def _save_scene(self) -> None:
        self._scene_file_controller.save_scene()

    def _save_scene_as(self) -> None:
        self._scene_file_controller.save_scene_as()

    def _load_scene(self) -> None:
        self._scene_file_controller.load_scene()

    def _close_scene(self) -> None:
        self._scene_file_controller.close_scene()

    def _save_scene_to_file(self, path: str) -> None:
        self._scene_file_controller.save_scene_to_file(path)

    def _load_scene_from_file(self, path: str) -> None:
        self._scene_file_controller.load_scene_from_file(path)

    def _validate_scene_path(self, path: str) -> bool:
        return self._scene_file_controller.validate_scene_path(path)

    def _load_last_scene(self) -> None:
        self._scene_file_controller.load_last_scene()

    # ------------------------------------------------------------------
    # Project restore on startup
    # ------------------------------------------------------------------

    def _restore_project(self) -> None:
        self._project_session_controller.restore_project()

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
        self._project_session_controller.create_project_file(path)

    def _load_project(self, path: str) -> None:
        self._project_session_controller.load_project(path)

    def _configure_shader_runtime_for_project(self, project_root: Path) -> None:
        ProjectSessionController.configure_shader_runtime_for_project(
            project_root,
            resolve_termin_shaderc=_resolve_termin_shaderc,
            resolve_slangc=_resolve_slangc,
        )

    def _load_project_modules(self, project_root: Path) -> None:
        self._project_session_controller.load_project_modules(project_root)

    def _run_project_init_script(self, project_root: Path) -> None:
        self._project_session_controller.run_project_init_script(project_root)

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
        self._project_file_actions.activate_file(path)

    def _on_project_file_selected(self, path: str) -> None:
        self._project_file_actions.select_file(path)

    # ------------------------------------------------------------------
    # Menu action stubs / helpers
    # ------------------------------------------------------------------

    def _noop(self, *args, **kwargs) -> None:
        pass

    def _show_settings(self) -> None:
        self._dialog_launcher.show_settings()

    def _show_project_settings(self) -> None:
        self._dialog_launcher.show_project_settings()

    def _show_scene_properties(self) -> None:
        self._dialog_launcher.show_scene_properties()

    def _show_layers_settings(self) -> None:
        self._dialog_launcher.show_layers_settings()

    def _show_shadow_settings(self) -> None:
        self._dialog_launcher.show_shadow_settings()

    def _show_agent_types(self) -> None:
        self._dialog_launcher.show_agent_types()

    def _show_navmesh_areas(self) -> None:
        self._dialog_launcher.show_navmesh_areas()

    def _show_spacemouse_settings(self) -> None:
        self._dialog_launcher.show_spacemouse_settings()

    def _init_spacemouse(self) -> None:
        self._dialog_launcher.init_spacemouse()

    def _show_resource_manager_viewer(self) -> None:
        self._dialog_launcher.show_resource_manager_viewer()

    def _show_core_registry_viewer(self) -> None:
        self._dialog_launcher.show_core_registry_viewer()

    def _show_inspect_registry_viewer(self) -> None:
        self._dialog_launcher.show_inspect_registry_viewer()

    def _show_navmesh_registry_viewer(self) -> None:
        self._dialog_launcher.show_navmesh_registry_viewer()

    def _show_framegraph_debugger(self) -> None:
        self._dialog_launcher.show_framegraph_debugger()

    def _show_audio_debugger(self) -> None:
        self._dialog_launcher.show_audio_debugger()

    def _show_scene_manager_viewer(self) -> None:
        self._dialog_launcher.show_scene_manager_viewer()

    def _show_pipeline_editor(self) -> None:
        self._dialog_launcher.show_pipeline_editor()

    def _open_pipeline_file_for_edit(self, file_path: str) -> None:
        self._dialog_launcher.open_pipeline_file_for_edit(file_path)

    @property
    def _game_scene_name(self) -> str | None:
        return self._game_mode_model.game_scene_name if self._game_mode_model else None

    def _toggle_game_mode(self) -> None:
        if self._game_mode_model is not None:
            self._game_mode_model.toggle_game_mode()

    def _toggle_pause(self) -> None:
        if self._game_mode_model is None:
            return
        self._game_mode_ui.toggle_pause(self._game_mode_model)

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

        self._game_mode_ui.update_mode(is_playing)
        self._request_viewport_update()

    def _update_game_mode_ui(self, is_playing: bool) -> None:
        self._game_mode_ui.update_mode(is_playing)

    def _update_play_action(self, is_playing: bool) -> None:
        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_play_action(is_playing)

    def _run_standalone(self) -> None:
        self._project_build_controller.run_standalone()

    def _build_project(self) -> None:
        self._project_build_controller.build_project()

    def _build_android(self) -> None:
        self._project_build_controller.build_android()

    def _show_quest_openxr_build_dialog(self) -> None:
        self._project_build_controller.show_quest_openxr_build_dialog()

    def _build_project_to_default_dist(self):
        return self._project_build_controller.build_project_to_default_dist()

    def _run_build(self) -> None:
        self._project_build_controller.run_build()

    def _show_undo_stack_viewer(self) -> None:
        self._dialog_launcher.show_undo_stack_viewer()

    # ------------------------------------------------------------------
    # Debug panels (Profiler / Modules)
    # ------------------------------------------------------------------

    def _toggle_profiler(self) -> None:
        self._debug_panels.toggle_profiler()

    def _toggle_modules(self) -> None:
        self._debug_panels.toggle_modules()

    def _update_debug_panel_visibility(self) -> None:
        self._debug_panels.update_visibility()

    def _update_profiler_action(self) -> None:
        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_profiler_action()

    def _update_modules_action(self) -> None:
        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_modules_action()

    def _toggle_fullscreen(self) -> None:
        self._fullscreen.toggle()

    def _fullscreen_panels(self) -> list[object | None]:
        return [
            self._left_tabs, self._left_splitter,
            self._right_scroll, self._right_splitter,
            self._bottom_tabs, self._bottom_splitter,
            self._menu_bar_widget, self._status_bar,
            self._debug_panel, self._debug_splitter,
        ]

    def _update_fullscreen_action(self) -> None:
        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_fullscreen_action()

    def _load_material_from_file(self) -> None:
        self._resource_actions.load_material_from_file()

    def _load_components_from_file(self) -> None:
        self._resource_actions.load_components_from_file()

    def _deploy_stdlib(self) -> None:
        self._resource_actions.deploy_stdlib()

    def _migrate_spec_to_meta(self) -> None:
        self._resource_actions.migrate_spec_to_meta()

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

    def _set_spacemouse(self, spacemouse) -> None:
        self._spacemouse = spacemouse

    def _set_editor_scene_name(self, scene_name: str | None) -> None:
        self._editor_scene_name = scene_name

    def _set_project_state(self, project_dir: str, project_name: str) -> None:
        self._current_project_path = project_dir
        self._project_name = project_name

    def _set_project_browser_root(self, project_dir: str) -> None:
        if self._project_browser is not None:
            self._project_browser.set_root(project_dir)

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
        self._prefab_toolbar_controller.set_editing(is_editing, prefab_name)
        if is_editing:
            self.attach_editor_to_scene("prefab", restore_state=False)
            self.attach_scene_to_render("prefab")
        else:
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

        self._debug_panels.poll(time.monotonic())
        self._dialog_launcher.update_framegraph_debugger()
        self._process_pending_scene_tree_rebuild()

    def _after_render(self) -> None:
        if self._spacemouse is not None:
            self._spacemouse.poll()
        if self._interaction_system is not None:
            self._interaction_system.after_render()
        has_overlay_drawers = self._viewport_interactions.draw_overlays()
        self._dialog_launcher.update_framegraph_debugger()
        self._process_pending_scene_tree_rebuild()
        if has_overlay_drawers:
            self._request_viewport_update()

    def _on_material_file_selected(self, path: str | None) -> None:
        self._resource_actions.on_material_file_selected(path)

    def _on_components_file_selected(self, path: str | None) -> None:
        self._resource_actions.on_components_file_selected(path)

    def _deploy_stdlib_to(self, path: str | None, stdlib_src: Path) -> None:
        self._resource_actions.deploy_stdlib_to(path, stdlib_src)
