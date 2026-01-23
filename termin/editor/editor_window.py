# ===== termin/editor/editor_window.py =====
import os
from pathlib import Path

from termin._native import log

from PyQt6 import uic
from PyQt6.QtWidgets import QMainWindow, QWidget, QTreeView, QListView, QLabel, QMenu, QTabWidget, QPlainTextEdit
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QEvent, pyqtSignal

from termin.editor.undo_stack import UndoStack, UndoCommand
from termin.editor.editor_commands import AddEntityCommand, DeleteEntityCommand, RenameEntityCommand
from termin.editor.scene_tree_controller import SceneTreeController
from termin.editor.editor_viewport_features import EditorViewportFeatures
from termin.editor.gizmo import GizmoManager
from termin.editor.prefab_edit_controller import PrefabEditController
from termin.editor.scene_manager import SceneManager, SceneMode
from termin.editor.selection_manager import SelectionManager
from termin.editor.dialog_manager import DialogManager
from termin.editor.inspector_controller import InspectorController
from termin.editor.menu_bar_controller import MenuBarController
from termin.editor.editor_scene_attachment import EditorSceneAttachment
from termin.editor.resource_loader import ResourceLoader
from termin.editor.viewport_list_widget import ViewportListWidget
from termin.editor.rendering_controller import RenderingController
from termin.visualization.render import RenderingManager
from termin.editor.scene_file_controller import SceneFileController
from termin.editor.project_file_watcher import ProjectFileWatcher
from termin.editor.editor_mode_controller import EditorModeController
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
from termin.editor.spacemouse_controller import SpaceMouseController
from termin.editor.profiler import ProfilerPanel
from termin.editor.modules_panel import ModulesPanel

from termin.visualization.core.camera import OrbitCameraController
from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3
from termin.editor.settings import EditorSettings
from termin.editor.drag_drop import EditorMimeTypes, parse_asset_path_mime_data
from termin.visualization.core.resources import ResourceManager
from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend
from termin.editor.project_controller import EditorProjectController
from termin.editor.editor_ui_builder import EditorUIBuilder


class EditorWindow(QMainWindow):
    undo_stack_changed = pyqtSignal()

    _instance: "EditorWindow | None" = None

    @classmethod
    def instance(cls) -> "EditorWindow | None":
        return cls._instance

    def __init__(self, world, initial_scene, sdl_backend: SDLEmbeddedWindowBackend):
        super().__init__()
        EditorWindow._instance = self
        self.undo_stack = UndoStack()
        self._menu_bar_controller: MenuBarController | None = None
        self._mode_controller = EditorModeController(self)
        self._should_close = False

        self.world = world
        self._sdl_backend = sdl_backend

        # --- ресурс-менеджер редактора ---
        self.resource_manager = ResourceManager.instance()
        self.resource_manager.register_builtin_components()
        self.resource_manager.register_builtin_frame_passes()
        self.resource_manager.register_builtin_post_effects()

        # --- SceneManager - владеет всеми сценами ---
        # Создаётся ПЕРВЫМ, до всех контроллеров
        self.scene_manager = SceneManager(
            resource_manager=self.resource_manager,
            on_before_scene_close=self._on_before_scene_close,
            get_editor_camera_data=self._get_editor_camera_data,
            set_editor_camera_data=self._set_editor_camera_data,
            get_selected_entity_uuid=self._get_selected_entity_uuid,
            select_entity_by_uuid=self._select_entity_by_uuid,
            get_displays_data=self._get_displays_data,
            set_displays_data=self._set_displays_data,
            get_expanded_entities=self._get_expanded_entities,
            set_expanded_entities=self._set_expanded_entities,
            rescan_file_resources=self._rescan_file_resources,
        )

        # Создаём начальную сцену (или используем переданную)
        self._editor_scene_name = "untitled"
        if initial_scene is not None:
            self.scene_manager._scenes[self._editor_scene_name] = initial_scene
            self.scene_manager._modes[self._editor_scene_name] = SceneMode.STOP
        else:
            self.scene_manager.create_scene(self._editor_scene_name)
            self.scene_manager.set_mode(self._editor_scene_name, SceneMode.STOP)

        # контроллеры создадим чуть позже
        self.scene_tree_controller: SceneTreeController | None = None
        self.editor_viewport: EditorViewportFeatures | None = None
        self.gizmo_manager: GizmoManager | None = None
        self.selection_manager: SelectionManager | None = None
        self.prefab_edit_controller: PrefabEditController | None = None
        self.project_browser = None
        self._project_controller: EditorProjectController | None = None
        self._play_button: QPushButton | None = None
        self._prefab_toolbar: QWidget | None = None
        self._prefab_toolbar_label: QLabel | None = None
        self._prefab_menu: QMenu | None = None
        self._viewport_list_widget: ViewportListWidget | None = None
        self._rendering_controller: RenderingController | None = None
        self._viewport_toolbar: QWidget | None = None
        self._profiler_panel: "ProfilerPanel | None" = None
        self._modules_panel: "ModulesPanel | None" = None

        ui_path = os.path.join(os.path.dirname(__file__), "editor.ui")
        uic.loadUi(ui_path, self)

        self._mode_controller.init_status_bar()

        # --- ResourceLoader ---
        self._resource_loader = ResourceLoader(
            parent=self,
            resource_manager=self.resource_manager,
            get_scene=lambda: self.scene,
            get_project_path=self._get_project_path,
            on_resource_reloaded=self._on_resource_reloaded,
            log_message=self._log_to_console,
        )

        self._resource_loader.scan_builtin_components()

        # --- ProjectFileWatcher ---
        self._project_file_watcher = ProjectFileWatcher(
            on_resource_reloaded=self._on_resource_reloaded,
        )
        self._project_file_watcher.register_processor(
            MaterialPreLoader(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            GlslPreLoader(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            ShaderFileProcessor(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            TextureFileProcessor(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            ComponentFileProcessor(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            PipelinePreLoader(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            ScenePipelinePreLoader(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            MeshFileProcessor(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            VoxelGridProcessor(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            NavMeshProcessor(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            GLBPreLoader(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            PrefabPreLoader(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            AudioPreLoader(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )
        self._project_file_watcher.register_processor(
            UIPreLoader(
                resource_manager=self.resource_manager,
                on_resource_reloaded=self._on_resource_reloaded,
            )
        )

        # --- UI из .ui ---
        self.sceneTree: QTreeView = self.findChild(QTreeView, "sceneTree")
        self.sceneTree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Left tab widget (Scene + Rendering tabs)
        self.leftTabWidget: QTabWidget = self.findChild(QTabWidget, "leftTabWidget")
        self.renderingTab: QWidget = self.findChild(QWidget, "renderingTab")

        # Center tab widget (Editor + additional displays)
        self._center_tab_widget: QTabWidget = self.findChild(QTabWidget, "centerTabWidget")
        self.editorViewportTab: QWidget = self.findChild(QWidget, "editorViewportTab")

        self.inspectorContainer: QWidget = self.findChild(QWidget, "inspectorContainer")

        from PyQt6.QtWidgets import QSplitter
        self.topSplitter: QSplitter = self.findChild(QSplitter, "topSplitter")
        self.verticalSplitter: QSplitter = self.findChild(QSplitter, "verticalSplitter")

        EditorUIBuilder.fix_splitters(self.topSplitter, self.verticalSplitter)

        # --- InspectorController ---
        self._inspector_controller = InspectorController(
            container=self.inspectorContainer,
            resource_manager=self.resource_manager,
            push_undo_command=self.push_undo_command,
            on_transform_changed=self._on_inspector_transform_changed,
            on_component_changed=self._on_inspector_component_changed,
            on_material_changed=self._on_material_inspector_changed,
            window_backend=self._sdl_backend,
            graphics=self.world.graphics,
        )

        # Для обратной совместимости
        self.entity_inspector = self._inspector_controller.entity_inspector
        self.material_inspector = self._inspector_controller.material_inspector
        self.inspector = self.entity_inspector
        self._inspector_controller.set_scene(self.scene)

        # Handle ViewportHintComponent changes
        self.entity_inspector.component_field_changed.connect(
            self._on_component_field_changed
        )

        # --- DialogManager ---
        self._dialog_manager = DialogManager(
            parent=self,
            undo_stack=self.undo_stack,
            undo_stack_changed_signal=self.undo_stack_changed,
            get_scene=lambda: self.scene,
            resource_manager=self.resource_manager,
            push_undo_command=self.push_undo_command,
            request_viewport_update=self._request_viewport_update,
            project_file_watcher=self._project_file_watcher,
        )

        # --- EditorSceneAttachment (created later, after editor display) ---
        self._editor_attachment: EditorSceneAttachment | None = None

        # --- SpaceMouse support (initialized later after console is ready) ---
        self._spacemouse: SpaceMouseController | None = None

        # --- unified gizmo manager ---
        self.gizmo_manager = GizmoManager()

        # --- дерево сцены ---
        self.scene_tree_controller = SceneTreeController(
            tree_view=self.sceneTree,
            scene=self.scene,
            undo_handler=self.push_undo_command,
            on_object_selected=self._on_tree_object_selected,
            request_viewport_update=self._request_viewport_update,
        )

        # --- viewport toolbar ---
        self._init_viewport_toolbar()

        # --- Project controller ---
        self._project_controller = EditorProjectController(
            parent=self,
            settings=EditorSettings.instance(),
            inspector_controller=self._inspector_controller,
            log_message=self._log_to_console,
            update_window_title=self._update_window_title,
            on_project_reset=self.scene_manager.reset,
            on_load_scene=self._load_scene_from_file,
            on_open_prefab=self._open_prefab,
        )

        # --- UI: menu bar and project browser ---
        self._setup_menu_bar()
        self._init_project_browser()

        # --- ViewportListWidget and RenderingController ---
        # Must be created BEFORE EditorViewportFeatures
        self._init_viewport_list_widget()

        # Map display_id -> EditorViewportFeatures for displays in "editor" mode
        self._editor_features: dict[int, EditorViewportFeatures] = {}

        # --- Create editor display through RenderingController ---
        editor_display, backend_window = self._rendering_controller.create_editor_display(
            container=self.editorViewportTab,
            sdl_backend=self._sdl_backend,
            width=800,
            height=600,
        )

        # Install event filter on GL widget
        gl_widget = self._rendering_controller.editor_gl_widget
        if gl_widget is not None:
            gl_widget.installEventFilter(self)
            gl_widget.setAcceptDrops(True)

        # Enable drag-drop on viewport container
        self.editorViewportTab.setAcceptDrops(True)
        self.editorViewportTab.installEventFilter(self)

        # --- EditorViewportFeatures (editor UX layer) ---
        # Created before attachment - viewport will be created by attachment.attach()
        self.editor_viewport = EditorViewportFeatures(
            display=editor_display,
            backend_window=backend_window,
            graphics=self.world.graphics,
            gizmo_manager=self.gizmo_manager,
            on_entity_picked=self._on_entity_picked_from_viewport,
            on_hover_entity=self._on_hover_entity_from_viewport,
            get_fbo_pool=self._rendering_controller.get_editor_fbo_pool,
            request_update=self._request_viewport_update,
        )
        # Set undo handler and transform callback for gizmo operations
        self.editor_viewport.set_gizmo_undo_handler(self.push_undo_command)
        self.editor_viewport.set_on_transform_dragging(self._on_gizmo_transform_dragging)

        # Register in editor features dict
        self._editor_features[id(editor_display)] = self.editor_viewport

        RenderingManager.instance().set_graphics(self.world.graphics)
        self.scene_manager.set_render_callbacks(
            on_after_render=self._after_render,
        )

        # Set editor pipeline maker for RenderingController (and ViewportInspector)
        self._rendering_controller.set_editor_pipeline_maker(
            self.editor_viewport.make_editor_pipeline
        )

        # --- EditorSceneAttachment ---
        # Manages EditorEntities, viewport, and scene connection
        self._editor_attachment = EditorSceneAttachment(
            display=editor_display,
            rendering_controller=self._rendering_controller,
            make_editor_pipeline=self.editor_viewport.make_editor_pipeline,
        )

        # Attach to initial scene (creates EditorEntities and viewport)
        self._editor_attachment.attach(self.scene, restore_state=False)

        # Sync backward-compatible references from attachment
        self._sync_attachment_refs()

        # For backwards compatibility
        self.viewport_controller = self.editor_viewport

        # --- SelectionManager ---
        self.selection_manager = SelectionManager(
            get_pick_id=self._get_pick_id_for_entity,
            on_selection_changed=self._on_selection_changed_internal,
            on_hover_changed=self._on_hover_changed_internal,
        )

        # --- PrefabEditController - режим изоляции для редактирования префабов ---
        self.prefab_edit_controller = PrefabEditController(
            scene_manager=self.scene_manager,
            resource_manager=self.resource_manager,
            on_mode_changed=self._on_prefab_mode_changed,
            on_request_update=self._request_viewport_update,
            log_message=self._log_to_console,
        )

        # --- SceneFileController ---
        self._scene_file_controller = SceneFileController(
            parent=self,
            get_scene_manager=lambda: self.scene_manager,
            switch_to_scene=self.switch_to_scene,
            on_after_save=self._update_window_title,
            get_project_path=self._get_project_path,
            get_editor_scene_name=lambda: self._editor_scene_name,
            set_editor_scene_name=self._set_editor_scene_name,
            log_message=self._log_to_console,
            on_before_close_scene=self._on_before_close_editor_scene,
        )

        # --- SpaceMouse support ---
        self._init_spacemouse()

        # --- Инициализация настроек (поиск VS Code и т.п.) ---
        EditorSettings.instance().init_text_editor_if_empty()

        # --- Инициализируем ресурсы один раз при старте ---
        self.scene_manager.initialize_resources()

        # --- Загружаем последнюю открытую сцену ---
        self._scene_file_controller.load_last_scene()

    @property
    def scene(self):
        """Текущая сцена редактора (или game сцена в game mode)."""
        game_scene_name = self._mode_controller.game_scene_name
        if self.is_game_mode and game_scene_name:
            return self.scene_manager.get_scene(game_scene_name)
        if self._editor_scene_name:
            return self.scene_manager.get_scene(self._editor_scene_name)
        return None

    @property
    def is_game_mode(self) -> bool:
        """True if currently in game mode (including paused)."""
        return self._mode_controller.is_game_mode

    @property
    def is_game_paused(self) -> bool:
        """True if game mode is paused (game scene in STOP mode)."""
        return self._mode_controller.is_game_paused

    def _set_editor_scene_name(self, name: str | None) -> None:
        """Set editor scene name."""
        self._editor_scene_name = name

    # ----------- undo / redo -----------

    def _setup_menu_bar(self) -> None:
        """Create editor menu bar via MenuBarController."""
        if self._project_controller is None:
            return
        self._menu_bar_controller = MenuBarController(
            menu_bar=self.menuBar(),
            on_new_project=self._project_controller.new_project,
            on_open_project=self._project_controller.open_project,
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
            on_settings=self._show_settings_dialog,
            on_scene_properties=self._show_scene_properties,
            on_layers_settings=self._show_layers_dialog,
            on_shadow_settings=self._show_shadow_settings_dialog,
            on_pipeline_editor=self._show_pipeline_editor,
            on_toggle_game_mode=self._mode_controller.toggle_game_mode,
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
            on_toggle_modules=self._toggle_modules_panel,
            on_toggle_fullscreen=self._mode_controller.toggle_fullscreen,
            on_show_agent_types=self._show_agent_types_dialog,
            can_undo=lambda: self.undo_stack.can_undo,
            can_redo=lambda: self.undo_stack.can_redo,
            is_fullscreen=lambda: self._mode_controller.is_fullscreen,
            is_profiler_visible=self._is_profiler_visible,
            is_modules_visible=self._is_modules_panel_visible,
        )

    def _update_undo_redo_actions(self) -> None:
        """Update enabled state of Undo/Redo menu items."""
        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_undo_redo_actions()

    def push_undo_command(self, cmd: UndoCommand, merge: bool = False) -> None:
        """
        Добавить команду в undo-стек редактора.
        merge=True — попытаться слить с предыдущей (для крутилок трансформа).
        """
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

    def _show_scene_properties(self) -> None:
        """Opens scene properties dialog."""
        self._dialog_manager.show_scene_properties()

    def _show_layers_dialog(self) -> None:
        """Opens layers and flags configuration dialog."""
        self._dialog_manager.show_layers_dialog()

    def _show_shadow_settings_dialog(self) -> None:
        """Opens shadow settings dialog."""
        self._dialog_manager.show_shadow_settings_dialog()

    def _show_agent_types_dialog(self) -> None:
        """Opens agent types configuration dialog."""
        self._dialog_manager.show_agent_types_dialog()

    def _show_pipeline_editor(self) -> None:
        """Opens the visual pipeline graph editor."""
        from termin.nodegraph import PipelineGraphEditor

        editor = PipelineGraphEditor(parent=self)
        editor.set_scene(self.scene)
        editor.show()

    def _show_undo_stack_viewer(self) -> None:
        """Opens undo/redo stack viewer window."""
        self._dialog_manager.show_undo_stack_viewer()

    def _show_framegraph_debugger(self) -> None:
        """Opens framegraph texture viewer dialog."""
        self.open_framegraph_debugger()

    def open_framegraph_debugger(self, initial_resource: str | None = None) -> None:
        """Opens framegraph texture viewer dialog.

        Args:
            initial_resource: Resource to show initially (e.g., "shadow_maps", "color").
        """
        debugger = self._dialog_manager.show_framegraph_debugger(
            window_backend=self._sdl_backend,
            graphics=self.world.graphics,
            rendering_controller=self._rendering_controller,
            on_request_update=self._request_viewport_update,
            initial_resource=initial_resource,
        )
        # Connect debugger to editor viewport for updates in after_render
        if self.editor_viewport is not None:
            self.editor_viewport.set_framegraph_debugger(debugger)

    def _refresh_framegraph_debugger(self) -> None:
        """Refresh framegraph debugger if it's open (e.g., after scene change)."""
        debugger = self._dialog_manager.framegraph_debugger
        if debugger is not None and debugger.isVisible():
            # Refresh in place, preserving selection
            debugger.refresh_for_new_scene()

    def _show_resource_manager_viewer(self) -> None:
        """Opens resource manager viewer dialog."""
        self._dialog_manager.show_resource_manager_viewer()

    def _show_audio_debugger(self) -> None:
        """Opens audio debugger dialog."""
        self._dialog_manager.show_audio_debugger()

    def _show_core_registry_viewer(self) -> None:
        """Opens core registry viewer dialog."""
        self._dialog_manager.show_core_registry_viewer()

    def _show_inspect_registry_viewer(self) -> None:
        """Opens inspect registry viewer dialog."""
        self._dialog_manager.show_inspect_registry_viewer()

    def _show_navmesh_registry_viewer(self) -> None:
        """Opens NavMesh registry viewer dialog."""
        self._dialog_manager.show_navmesh_registry_viewer()

    def _show_scene_manager_viewer(self) -> None:
        """Opens scene manager viewer window."""
        from termin.editor.scene_manager_viewer import SceneManagerViewer
        viewer = SceneManagerViewer(self.scene_manager, parent=self)
        viewer.show()

    def _toggle_profiler(self, checked: bool) -> None:
        """Toggle profiler panel visibility."""
        if checked:
            if self._profiler_panel is None:
                self._profiler_panel = ProfilerPanel(self)
                self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._profiler_panel)
                # Connect visibility changed to update menu checkbox
                self._profiler_panel.visibilityChanged.connect(self._on_profiler_visibility_changed)
            self._profiler_panel.show()
        else:
            if self._profiler_panel is not None:
                self._profiler_panel.hide()

    def _is_profiler_visible(self) -> bool:
        """Returns True if profiler panel is visible."""
        if self._profiler_panel is None:
            return False
        return self._profiler_panel.isVisible()

    def _on_profiler_visibility_changed(self, visible: bool) -> None:
        """Called when profiler panel visibility changes (e.g., closed via X button)."""
        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_profiler_action()

    def _toggle_modules_panel(self, checked: bool) -> None:
        """Toggle modules panel visibility."""
        if checked:
            if self._modules_panel is None:
                self._modules_panel = ModulesPanel(self)
                self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._modules_panel)
                self._modules_panel.visibilityChanged.connect(self._on_modules_panel_visibility_changed)
            self._modules_panel.show()
        else:
            if self._modules_panel is not None:
                self._modules_panel.hide()

    def _is_modules_panel_visible(self) -> bool:
        """Returns True if modules panel is visible."""
        if self._modules_panel is None:
            return False
        return self._modules_panel.isVisible()

    def _on_modules_panel_visibility_changed(self, visible: bool) -> None:
        """Called when modules panel visibility changes."""
        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_modules_action()

    # ----------- editor camera -----------

    def _sync_attachment_refs(self) -> None:
        """
        Sync backward-compatible references from EditorSceneAttachment.

        Updates self.camera, self.editor_entities, self.viewport from attachment.
        Call this after any attachment.attach() call.
        """
        if self._editor_attachment is None:
            self.camera = None
            self.editor_entities = None
            self.viewport = None
        else:
            self.camera = self._editor_attachment.camera
            self.editor_entities = self._editor_attachment.editor_entities
            self.viewport = self._editor_attachment.viewport

    def _get_editor_camera_data(self) -> dict | None:
        """Get editor camera data for serialization."""
        if self._editor_attachment is None:
            return None
        return self._editor_attachment.get_camera_data()

    def _set_editor_camera_data(self, data: dict) -> None:
        """Apply saved camera data."""
        if self._editor_attachment is not None:
            self._editor_attachment.set_camera_data(data)

    def _get_selected_entity_uuid(self) -> str | None:
        """
        Возвращает UUID выделенной сущности.
        """
        if self.selection_manager is None:
            return None
        selected = self.selection_manager.selected
        if selected is None:
            return None
        return selected.uuid

    def _select_entity_by_uuid(self, uuid: str) -> None:
        """
        Выделяет сущность по UUID.
        """
        if self.scene is None:
            return

        # Ищем сущность по UUID
        entity = self.scene.get_entity(uuid)
        if entity is None or not entity.selectable:
            return

        # Выделяем через SelectionManager
        if self.selection_manager is not None:
            self.selection_manager.select(entity)

        # Обновляем дерево сцены
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.select_object(entity)

        # Обновляем инспектор
        if self.inspector is not None:
            self.inspector.set_target(entity)

    def _get_displays_data(self) -> list | None:
        """Get displays/viewports data for serialization.

        Syncs viewport_configs to scene before saving.
        Returns None for new format (viewport_configs in scene).
        Returns legacy data for old format (backward compatibility).
        """
        if self._rendering_controller is None:
            return None

        # Always sync current state to scene.viewport_configs
        if self.scene is not None:
            self._rendering_controller.sync_viewport_configs_to_scene(self.scene)

        # New format: viewport_configs is serialized with scene, return None
        # (This triggers new format on next load)
        return None

    def _set_displays_data(self, data: list | None) -> None:
        """Restore displays/viewports after scene load.

        Attaches scene viewports from scene.viewport_configs.
        Always refreshes viewport list at the end.
        """
        if self._rendering_controller is None:
            return

        # Attach scene viewports from viewport_configs
        if self.scene is not None and self.scene.viewport_configs:
            self._rendering_controller.attach_scene(self.scene)

        # Always refresh viewport list to show editor display
        self._rendering_controller._viewport_list.refresh()

    def _get_expanded_entities(self) -> list[str] | None:
        """Get expanded entity UUIDs for serialization."""
        if self.scene_tree_controller is None:
            return None
        return self.scene_tree_controller.get_expanded_entity_uuids()

    def _set_expanded_entities(self, uuids: list[str]) -> None:
        """Restore expanded entities from saved UUIDs."""
        if self.scene_tree_controller is None:
            return
        # Update scene reference (may have changed during load)
        self.scene_tree_controller.set_scene(self.scene)
        # Rebuild tree - entities were added after initial rebuild
        self.scene_tree_controller.rebuild()
        self.scene_tree_controller.set_expanded_entity_uuids(uuids)

    def _get_project_path(self) -> str | None:
        """Get current project path from project browser."""
        if self._project_controller is None:
            return None
        return self._project_controller.get_project_path()

    def _get_graphics(self):
        """Get GraphicsBackend from world."""
        if self.world is not None:
            return self.world.graphics
        return None

    def _get_window_backend(self):
        """Get WindowBackend from world."""
        if self.world is not None:
            return self.world.window_backend
        return None

    def _get_render_engine(self):
        """Get RenderEngine from RenderingController."""
        if self._rendering_controller is not None:
            return self._rendering_controller._render_engine
        return None

    def _log_to_console(self, message: str) -> None:
        """Log message to console output (native logs already print to stderr)."""
        if self.consoleOutput is not None:
            self.consoleOutput.appendPlainText(message)

    def _setup_native_log_callback(self) -> None:
        """Setup callback for native (C/C++) log messages."""
        from termin._native import log as native_log

        level_names = {
            native_log.DEBUG: "DEBUG",
            native_log.INFO: "INFO",
            native_log.WARN: "WARN",
            native_log.ERROR: "ERROR",
        }

        def on_native_log(level: int, message: str) -> None:
            level_name = level_names.get(level, "?")
            self._log_to_console(f"[{level_name}] {message}")

        native_log.set_callback(on_native_log)

    # ----------- реакции инспектора -----------

    def _on_inspector_transform_changed(self):
        self._request_viewport_update()

    def _on_inspector_component_changed(self):
        self._request_viewport_update()

    def _on_gizmo_transform_dragging(self):
        """Обновляет инспектор при перетаскивании объекта гизмо."""
        if self.entity_inspector is not None:
            self.entity_inspector.refresh_transform()

    def _on_material_inspector_changed(self):
        """Обработчик изменения материала в инспекторе."""
        self._request_viewport_update()

    def _on_component_field_changed(self, component, field_key: str, new_value):
        """Handle component field changes, particularly ViewportHintComponent."""
        from termin.visualization.core.viewport_hint import ViewportHintComponent

        if not isinstance(component, ViewportHintComponent):
            return

        if field_key != "pipeline_name":
            return

        # Get camera from component's entity
        entity = component.entity
        if entity is None:
            return

        from termin.visualization.core.camera import CameraComponent
        camera = entity.get_component(CameraComponent)
        if camera is None:
            return

        # Create pipeline based on name
        pipeline = self._create_pipeline_by_name(new_value)

        # Update all viewports using this camera
        for viewport in camera.viewports:
            self._rendering_controller.set_viewport_pipeline(viewport, pipeline)

        self._request_viewport_update()

    def _create_pipeline_by_name(self, pipeline_name: str):
        """Create pipeline by name."""
        from termin.assets.resources import ResourceManager

        if pipeline_name == "(Editor)":
            if self.editor_viewport is not None:
                return self.editor_viewport.make_editor_pipeline()
            pipeline_name = "Default"

        if not pipeline_name:
            pipeline_name = "Default"

        # Lookup pipeline from ResourceManager
        rm = ResourceManager.instance()
        pipeline = rm.get_pipeline(pipeline_name)
        if pipeline is not None:
            return pipeline

        # Fallback to Default
        return rm.get_pipeline("Default")

    def show_entity_inspector(self, entity: Entity | None = None):
        """Show EntityInspector and set target."""
        self._inspector_controller.show_entity_inspector(entity)

    def show_material_inspector(self, material_name: str | None = None):
        """Show MaterialInspector and load material by name."""
        self._inspector_controller.show_material_inspector(material_name)

    def show_material_inspector_for_file(self, file_path: str):
        """Show MaterialInspector and load material from file."""
        self._inspector_controller.show_material_inspector_for_file(file_path)

    # ----------- инициализация сплиттеров -----------

    def _init_viewport_list_widget(self) -> None:
        """Initialize ViewportListWidget and RenderingController."""
        if self.renderingTab is None:
            return

        # Create ViewportListWidget
        self._viewport_list_widget = ViewportListWidget()

        # Add to rendering tab layout
        rendering_layout = self.renderingTab.layout()
        if rendering_layout is not None:
            rendering_layout.addWidget(self._viewport_list_widget)

        # Create RenderingController
        # Editor display will be created later via create_editor_display()
        self._rendering_controller = RenderingController(
            viewport_list_widget=self._viewport_list_widget,
            inspector_controller=self._inspector_controller,
            center_tab_widget=self._center_tab_widget,
            get_scene=lambda: self.scene,
            get_graphics=self._get_graphics,
            get_window_backend=self._get_window_backend,
            get_sdl_backend=lambda: self._sdl_backend,
            on_entity_selected=self.show_entity_inspector,
            on_request_update=self._request_viewport_update,
            on_display_input_mode_changed=self._on_display_input_mode_changed,
        )

        # Register global render update callback
        from termin.editor.render_request import set_request_update_callback
        set_request_update_callback(self._request_viewport_update)

    def _init_spacemouse(self) -> None:
        """Initialize SpaceMouse controller if device available."""
        spacemouse = SpaceMouseController()
        if spacemouse.open():
            self._spacemouse = spacemouse
            self._log_to_console("[SpaceMouse] Device connected")
        else:
            self._spacemouse = None

    def _init_project_browser(self) -> None:
        """Инициализация файлового браузера проекта."""
        # Находим виджеты из .ui
        self.projectDirTree: QTreeView = self.findChild(QTreeView, "projectDirTree")
        self.projectFileList: QListView = self.findChild(QListView, "projectFileList")
        self.bottomTabWidget: QTabWidget = self.findChild(QTabWidget, "bottomTabWidget")
        self.consoleOutput: QPlainTextEdit = self.findChild(QPlainTextEdit, "consoleOutput")

        # Connect native logging to console
        self._setup_native_log_callback()

        if self._project_controller is None:
            return

        self.project_browser = self._project_controller.init_project_browser(
            project_dir_tree=self.projectDirTree,
            project_file_list=self.projectFileList,
        )


    def _show_settings_dialog(self) -> None:
        """Opens editor settings dialog."""
        self._dialog_manager.show_settings_dialog()

    def _on_resource_reloaded(self, resource_type: str, resource_name: str) -> None:
        """Callback for resource reload."""
        self._request_viewport_update()

    def _scan_project_resources(self) -> None:
        """Scan project directory for resources using ProjectFileWatcher."""
        project_path = self._get_project_path()
        if project_path is None:
            return

        # Register built-in shaders
        self.resource_manager.register_default_shader()
        self.resource_manager.register_pbr_shader()

        # Enable file watching and scan project
        self._project_file_watcher.enable(project_path)

        stats = self._project_file_watcher.get_stats()
        total = sum(stats.values())
        if total > 0:
            self._log_to_console(
                f"Scanned project: {stats.get('material', 0)} materials, "
                f"{stats.get('shader', 0)} shaders, {stats.get('texture', 0)} textures"
            )

    def _rescan_file_resources(self) -> None:
        """Rescan file resources. Called by WorldPersistence on scene load/reset."""
        project_path = self._get_project_path()
        if project_path is None:
            return

        # Register built-in resources
        self.resource_manager.register_default_shader()
        self.resource_manager.register_pbr_shader()
        self.resource_manager.register_builtin_materials()
        self.resource_manager.register_builtin_meshes()

        # If watcher not enabled yet, enable it. Otherwise rescan.
        if not self._project_file_watcher.is_enabled:
            self._project_file_watcher.enable(project_path)
        else:
            self._project_file_watcher.rescan()

    def _init_viewport_toolbar(self) -> None:
        handles = EditorUIBuilder.build_viewport_toolbar(
            center_tab_widget=self._center_tab_widget,
            top_splitter=self.topSplitter,
            on_toggle_game_mode=self._mode_controller.toggle_game_mode,
            on_toggle_pause=self._mode_controller.toggle_pause,
            on_save_prefab=self._save_prefab,
            on_exit_prefab=self._exit_prefab_editing,
        )
        self._viewport_toolbar = handles.viewport_toolbar
        self._play_button = handles.play_button
        self._pause_button = handles.pause_button
        self._prefab_toolbar = handles.prefab_toolbar
        self._prefab_toolbar_label = handles.prefab_toolbar_label

    # ----------- связи с контроллерами -----------

    def _request_viewport_update(self) -> None:
        self.scene_manager.request_render()
        if self._rendering_controller is not None:
            backend = self._rendering_controller.editor_backend_window
            if backend is not None:
                backend.request_update()

    def _after_render(self) -> None:
        for editor_features in self._editor_features.values():
            editor_features.after_render()

    def _on_before_scene_close(self, scene) -> None:
        """Called before a scene is destroyed. Removes viewports referencing this scene."""
        if self._rendering_controller is not None:
            self._rendering_controller.remove_viewports_for_scene(scene)

    def _on_before_close_editor_scene(self, scene_name: str) -> None:
        """Called before editor scene is closed. Unbinds UI and sets INACTIVE."""
        # Unbind scene tree first (prevents access to destroyed entities)
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(None)

        # Remove viewports for this scene
        scene = self.scene_manager.get_scene(scene_name)
        if scene is not None and self._rendering_controller is not None:
            self._rendering_controller.remove_viewports_for_scene(scene)

        # Set INACTIVE mode
        if self.scene_manager.has_scene(scene_name):
            self.scene_manager.set_mode(scene_name, SceneMode.INACTIVE)

    def _on_tree_object_selected(self, obj: object | None) -> None:
        """
        Колбэк от SceneTreeController при изменении выделения в дереве.
        """
        if isinstance(obj, Entity):
            self.show_entity_inspector(obj)
            ent = obj
        elif isinstance(obj, Transform3):
            ent = next((e for e in self.scene.entities if e.transform is obj), None)
            self.show_entity_inspector(ent)
        else:
            ent = None
            self.show_entity_inspector(None)

        if self.selection_manager is not None:
            self.selection_manager.select(ent)
        self._request_viewport_update()

    def _on_entity_picked_from_viewport(self, ent: Entity | None) -> None:
        """
        Колбэк от EditorViewportFeatures при выборе сущности кликом в вьюпорте.
        Синхронизируем выделение в дереве и инспекторе.
        """
        if self.selection_manager is not None:
            self.selection_manager.select(ent)

        if self.scene_tree_controller is not None and ent is not None:
            self.scene_tree_controller.select_object(ent)

        self.show_entity_inspector(ent)

    def _on_hover_entity_from_viewport(self, ent: Entity | None) -> None:
        """
        Колбэк от EditorViewportFeatures при изменении подсвеченной (hover) сущности.
        """
        if self.selection_manager is not None:
            self.selection_manager.hover(ent)

    # ----------- Qt eventFilter -----------

    def eventFilter(self, obj, event):
        """
        Перехватываем:
        - Delete в виджете вьюпорта для удаления выделенной сущности
        - Drag-drop prefab на viewport
        """
        editor_gl_widget = None
        if self._rendering_controller is not None:
            editor_gl_widget = self._rendering_controller.editor_gl_widget

        # Delete key in viewport
        if (
            editor_gl_widget is not None
            and obj is editor_gl_widget
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Delete
        ):
            ent = self.selection_manager.selected if self.selection_manager else None
            if isinstance(ent, Entity):
                # удаление через команду, дерево и вьюпорт обновятся через undo-стек
                cmd = DeleteEntityCommand(self.scene, ent)
                self.push_undo_command(cmd, merge=False)
            return True

        # Drag-drop on viewport container (or GL widget inside it)
        gl_widget = self._rendering_controller.editor_gl_widget
        is_viewport_target = (obj is self.editorViewportTab) or (gl_widget is not None and obj is gl_widget)

        if is_viewport_target:
            if event.type() == QEvent.Type.DragEnter:
                mime = event.mimeData()
                if mime.hasFormat(EditorMimeTypes.ASSET_PATH):
                    path = parse_asset_path_mime_data(mime)
                    if path and path.lower().endswith(".prefab"):
                        event.acceptProposedAction()
                        return True
            elif event.type() == QEvent.Type.DragMove:
                event.acceptProposedAction()
                return True
            elif event.type() == QEvent.Type.Drop:
                mime = event.mimeData()
                path = parse_asset_path_mime_data(mime)
                if path and path.lower().endswith(".prefab"):
                    drop_pos = event.position().toPoint()
                    self._on_prefab_dropped_to_viewport(path, drop_pos)
                    event.acceptProposedAction()
                    return True

        return super().eventFilter(obj, event)

    def _on_prefab_dropped_to_viewport(self, prefab_path: str, drop_pos) -> None:
        """
        Обработчик drop prefab на viewport.

        Args:
            prefab_path: Путь к .prefab файлу
            drop_pos: Позиция drop в координатах виджета
        """
        from termin.geombase import Pose3

        # Определяем позицию в мире через unproject
        world_pos = self._unproject_drop_position(drop_pos)

        # Используем PrefabAsset.instantiate() для правильного создания маркера
        rm = ResourceManager.instance()
        prefab_name = Path(prefab_path).stem
        position = (float(world_pos[0]), float(world_pos[1]), float(world_pos[2]))

        entity = rm.instantiate_prefab(prefab_name, position=position)
        if entity is None:
            print(f"Failed to instantiate prefab: {prefab_name}")
            return

        # Добавляем entity в сцену через команду (с поддержкой undo)
        cmd = AddEntityCommand(self.scene, entity)
        self.push_undo_command(cmd, merge=False)

        # Обновляем SceneTree и выделяем новый entity
        self.scene_tree_controller.add_entity_hierarchy(entity)

        # Выделяем entity
        if self.selection_manager is not None:
            self.selection_manager.select(entity)

    def _unproject_drop_position(self, drop_pos) -> "np.ndarray":
        """
        Преобразует позицию drop в мировые координаты через depth buffer.

        Args:
            drop_pos: QPoint с координатами в виджете

        Returns:
            np.ndarray с мировыми координатами (x, y, z)
        """
        import numpy as np

        # Fallback: позиция перед камерой
        fallback_pos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        if self.camera is not None and self.camera.entity is not None:
            cam_pose = self.camera.entity.transform.global_pose()
            cam_pos = cam_pose.lin
            # Forward = +Y в нашей системе координат
            rot = cam_pose.rotation_matrix()
            cam_forward = rot[:, 1]  # Y колонка = forward
            fallback_pos = cam_pos + cam_forward * 5.0

        if self.editor_viewport is None or self.viewport is None:
            return fallback_pos

        # Координаты drop в пикселях виджета
        x = float(drop_pos.x())
        y = float(drop_pos.y())

        # Читаем глубину из ID buffer
        depth = self.editor_viewport.pick_depth_at(x, y, self.viewport, buffer_name="id")
        if depth is None or depth >= 1.0:
            # Нет геометрии под курсором — используем fallback
            return fallback_pos

        # Получаем размеры viewport
        widget = self.editorViewportTab
        w = widget.width()
        h = widget.height()

        # Нормализованные координаты в пределах viewport
        nx = (x / w) * 2.0 - 1.0
        ny = (y / h) * -2.0 + 1.0  # Y инвертирован

        # Глубина в NDC (OpenGL: 0..1 -> -1..1)
        z_ndc = depth * 2.0 - 1.0

        # Точка в clip space
        clip_pos = np.array([nx, ny, z_ndc, 1.0], dtype=np.float32)

        # Матрицы камеры
        if self.camera is None:
            return fallback_pos

        proj = self.camera.get_projection_matrix().to_numpy()
        view = self.camera.get_view_matrix().to_numpy()
        pv = proj @ view

        # Inverse projection-view matrix
        try:
            inv_pv = np.linalg.inv(pv)
        except np.linalg.LinAlgError:
            return fallback_pos

        # Unproject
        world_h = inv_pv @ clip_pos
        if abs(world_h[3]) < 1e-6:
            return fallback_pos

        world_pos = world_h[:3] / world_h[3]
        return world_pos.astype(np.float32)

    def _resync_inspector_from_selection(self):
        """Resync inspector based on current tree selection."""
        self._inspector_controller.resync_from_tree_selection(self.sceneTree, self.scene)

    # ----------- SelectionManager колбэки -----------

    def _get_pick_id_for_entity(self, entity: Entity | None) -> int:
        """Получает pick ID для сущности через editor_viewport."""
        if self.editor_viewport is not None:
            return self.editor_viewport.get_pick_id_for_entity(entity)
        return 0

    def _on_selection_changed_internal(self, entity: Entity | None) -> None:
        """Колбэк от SelectionManager при изменении выделения."""
        # Обновляем все EditorViewportFeatures
        if self.selection_manager is not None:
            selected_id = self.selection_manager.selected_entity_id
            for editor_features in self._editor_features.values():
                editor_features.selected_entity_id = selected_id

        # Обновляем гизмо target через EditorViewportFeatures
        if self.editor_viewport is not None:
            self.editor_viewport.set_gizmo_target(entity)
            self.editor_viewport.update_gizmo_screen_scale(self.editor_viewport.viewport)

        self._request_viewport_update()

    def _on_hover_changed_internal(self, entity: Entity | None) -> None:
        """Колбэк от SelectionManager при изменении hover."""
        # Обновляем все EditorViewportFeatures
        if self.selection_manager is not None:
            hover_id = self.selection_manager.hover_entity_id
            for editor_features in self._editor_features.values():
                editor_features.hover_entity_id = hover_id

        self._request_viewport_update()

    # ----------- загрузка материалов -----------

    def _load_material_from_file(self) -> None:
        """Load material from .shader file."""
        self._resource_loader.load_material_from_file()

    def _load_components_from_file(self) -> None:
        """Load components from Python file."""
        self._resource_loader.load_components_from_file()

    def keyPressEvent(self, event) -> None:
        """Handle key press events."""
        from PyQt6.QtCore import Qt

        # F11 to toggle fullscreen (backup if menu shortcut doesn't work)
        if event.key() == Qt.Key.Key_F11:
            self._mode_controller.toggle_fullscreen()
            return

        # Escape to exit fullscreen
        if event.key() == Qt.Key.Key_Escape and self._mode_controller.is_fullscreen:
            self._mode_controller.exit_fullscreen()
            return

        super().keyPressEvent(event)

    def _deploy_stdlib(self) -> None:
        """Deploy standard library to user's project directory."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import shutil
        from pathlib import Path

        # Get stdlib source directory
        import termin
        stdlib_src = Path(termin.__file__).parent / "resources" / "stdlib"

        if not stdlib_src.exists():
            QMessageBox.warning(
                self,
                "Standard Library Not Found",
                f"Standard library not found at:\n{stdlib_src}\n\n"
                "Please ensure termin package is properly installed.",
            )
            return

        # Get current project path
        current_project = ""
        if self._project_controller is not None:
            project_root = self._project_controller.get_project_root_path()
            if project_root is not None:
                current_project = str(project_root)

        # Ask user where to deploy
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Directory for Standard Library",
            current_project,
        )

        if not target_dir:
            return

        target_path = Path(target_dir) / "stdlib"

        # Confirm if exists
        if target_path.exists():
            reply = QMessageBox.question(
                self,
                "Directory Exists",
                f"Directory '{target_path}' already exists.\n\n"
                "Overwrite existing files?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Copy files
        try:
            shutil.copytree(stdlib_src, target_path, dirs_exist_ok=True)
            QMessageBox.information(
                self,
                "Standard Library Deployed",
                f"Standard library deployed to:\n{target_path}\n\n"
                "GLSL files can now be used with #include directive.",
            )
            log.info(f"[Editor] Standard library deployed to {target_path}")
        except Exception as e:
            QMessageBox.critical(
                self,
                "Deployment Failed",
                f"Failed to deploy standard library:\n{e}",
            )

    def _migrate_spec_to_meta(self) -> None:
        """Rename all .spec files to .meta in the current project."""
        from PyQt6.QtWidgets import QMessageBox

        # Get project path
        project_path = None
        if self._project_controller is not None:
            project_path = self._project_controller.get_project_root_path()

        if not project_path:
            QMessageBox.warning(
                self,
                "No Project",
                "No project is currently open.\n\n"
                "Open a project first to migrate .spec files.",
            )
            return

        # Find all .spec files
        spec_files = list(project_path.rglob("*.spec"))

        if not spec_files:
            QMessageBox.information(
                self,
                "No Files to Migrate",
                "No .spec files found in the project.",
            )
            return

        # Migrate
        migrated = 0
        errors = []

        for spec_path in spec_files:
            meta_path = spec_path.with_suffix(".meta")
            try:
                spec_path.rename(meta_path)
                migrated += 1
            except Exception as e:
                errors.append(f"{spec_path.name}: {e}")

        # Report
        if errors:
            QMessageBox.warning(
                self,
                "Migration Completed with Errors",
                f"Migrated {migrated} files.\n\n"
                f"Errors ({len(errors)}):\n" + "\n".join(errors[:10]),
            )
        else:
            QMessageBox.information(
                self,
                "Migration Complete",
                f"Successfully migrated {migrated} .spec files to .meta.",
            )
            log.info(f"[Editor] Migrated {migrated} .spec files to .meta")

    # ----------- Scene switching -----------

    def switch_to_scene(self, name: str) -> None:
        """
        Switch editor to a different scene.

        Activates the scene in SceneManager and sets up all editor UI.
        Uses EditorSceneAttachment for clean attach/detach.
        """
        print(f"[EditorWindow] Switching to scene: {name}")

        new_scene = self.scene_manager.get_scene(name)
        if new_scene is None:
            from termin._native import log
            log.error(f"Cannot switch to scene '{name}': not found")
            return

        # Update editor scene name and mode
        self._editor_scene_name = name
        self.scene_manager.set_mode(name, SceneMode.STOP)

        # Attach to new scene (transfers camera state from previous scene)
        self._editor_attachment.attach(new_scene, transfer_camera_state=True)

        # Update backward-compatible references
        self._sync_attachment_refs()

        # Clear undo stack
        self.undo_stack.clear()
        self._update_undo_redo_actions()
        self.undo_stack_changed.emit()

        # Clear selection (viewport must exist before this, as callbacks access it)
        if self.selection_manager is not None:
            self.selection_manager.clear()

        # Clear gizmo target for new scene
        if self.editor_viewport is not None:
            self.editor_viewport.set_gizmo_target(None)

        # Update all EditorViewportFeatures
        for editor_features in self._editor_features.values():
            editor_features.set_scene(new_scene)
            editor_features.set_camera(self._editor_attachment.camera)
            editor_features.selected_entity_id = 0
            editor_features.hover_entity_id = 0

        # Update scene tree
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.set_scene(new_scene)
            self.scene_tree_controller.rebuild()

        # Clear inspector and update scene for layer/flag names
        if self._inspector_controller is not None:
            self._inspector_controller.set_scene(new_scene)
        if self.inspector is not None:
            self.inspector.set_target(None)

        # Apply stored editor data (camera position, selection, displays, etc.) from loaded scene
        # Must be after all viewport/scene setup is complete
        stored_data = self.scene_manager.get_stored_editor_data(name)
        self.scene_manager.apply_editor_data(stored_data)
        self.scene_manager.clear_stored_editor_data(name)

        self._request_viewport_update()
        self._update_window_title()

    # ----------- сохранение/загрузка сцены -----------

    def _new_scene(self) -> None:
        """Create new empty scene."""
        self._scene_file_controller.new_scene()

    def _save_scene(self) -> None:
        """Save scene to current file or prompt for new file."""
        self._scene_file_controller.save_scene()

    def _save_scene_as(self) -> None:
        """Save scene to new file."""
        self._scene_file_controller.save_scene_as()

    def _load_scene(self) -> None:
        """Load scene from file."""
        self._scene_file_controller.load_scene()

    def _load_scene_from_file(self, file_path: str) -> None:
        """Load scene from specified file."""
        self._scene_file_controller.load_scene_from_file(file_path)

    def _close_scene(self) -> None:
        """Close current scene (enter no-scene mode)."""
        if self._editor_scene_name and self.scene_manager.has_scene(self._editor_scene_name):
            # Detach from scene before closing
            self._editor_attachment.detach(save_state=False)
            self._sync_attachment_refs()

            self.scene_manager.close_scene(self._editor_scene_name)
            self._editor_scene_name = None

            # Clear viewports
            for editor_features in self._editor_features.values():
                editor_features.set_scene(None)
                editor_features.selected_entity_id = 0
                editor_features.hover_entity_id = 0

            # Clear scene tree
            if self.scene_tree_controller is not None:
                self.scene_tree_controller._scene = None
                self.scene_tree_controller.rebuild()

            self._request_viewport_update()

    def _run_standalone(self) -> None:
        """Run project in standalone player window."""
        import subprocess
        import sys
        from pathlib import Path

        project_path = self._get_project_path()
        if project_path is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Project", "Please open a project first.")
            return

        scene_path = self.scene_manager.get_scene_path(self._editor_scene_name)
        if scene_path is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No Scene", "Please save the scene first.")
            return

        # Save scene before running
        self._save_scene()

        # Run player in separate process
        project_root = Path(project_path)
        scene_path_obj = Path(scene_path)
        # Get relative path from project root
        try:
            scene_name = str(scene_path_obj.relative_to(project_root))
        except ValueError:
            # Scene is outside project, use absolute path
            scene_name = str(scene_path_obj)
        cmd = [
            sys.executable,
            "-m", "termin.player",
            str(project_root),
            "--scene", scene_name,
        ]

        subprocess.Popen(cmd, cwd=str(project_root))

    # ----------- prefab edit mode -----------

    def _open_prefab(self, prefab_path: str) -> None:
        """Открывает префаб для редактирования в режиме изоляции."""
        if self.prefab_edit_controller is not None:
            self.prefab_edit_controller.open_prefab(prefab_path)

    def _save_prefab(self) -> None:
        """Сохраняет префаб (без выхода из режима редактирования)."""
        if self.prefab_edit_controller is not None:
            self.prefab_edit_controller.save()

    def _exit_prefab_editing(self) -> None:
        """Выходит из режима редактирования префаба (без сохранения)."""
        if self.prefab_edit_controller is not None:
            self.prefab_edit_controller.exit()

    def _on_prefab_mode_changed(self, is_editing: bool, prefab_name: str | None) -> None:
        """Колбэк от PrefabEditController при изменении режима."""
        if is_editing:
            # Входим в режим редактирования префаба
            # Показываем prefab toolbar
            if self._prefab_toolbar is not None:
                self._prefab_toolbar.setVisible(True)
            if self._prefab_toolbar_label is not None and prefab_name:
                self._prefab_toolbar_label.setText(f"Editing Prefab: {prefab_name}")

            # Скрываем кнопку Play (нельзя запускать игру при редактировании префаба)
            if self._play_button is not None:
                self._play_button.setEnabled(False)

            # Показываем меню Prefab
            self._show_prefab_menu()
        else:
            # Выходим из режима редактирования префаба
            # Скрываем prefab toolbar
            if self._prefab_toolbar is not None:
                self._prefab_toolbar.setVisible(False)

            # Включаем кнопку Play
            if self._play_button is not None:
                self._play_button.setEnabled(True)

            # Скрываем меню Prefab
            self._hide_prefab_menu()

        # Обновляем дерево сцены
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.rebuild()

        self._update_window_title()
        self._request_viewport_update()

    def _show_prefab_menu(self) -> None:
        """Показывает меню Prefab в menuBar."""
        if self._prefab_menu is not None:
            return  # Уже показано

        menu_bar = self.menuBar()
        self._prefab_menu = menu_bar.addMenu("Prefab")

        save_action = self._prefab_menu.addAction("Save Prefab")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_prefab)

        self._prefab_menu.addSeparator()

        exit_action = self._prefab_menu.addAction("Exit Prefab Editing")
        exit_action.triggered.connect(self._exit_prefab_editing)

    def _hide_prefab_menu(self) -> None:
        """Скрывает меню Prefab из menuBar."""
        if self._prefab_menu is None:
            return

        menu_bar = self.menuBar()
        menu_bar.removeAction(self._prefab_menu.menuAction())
        self._prefab_menu = None

    def _update_window_title(self) -> None:
        """Обновляет заголовок окна с учётом проекта, сцены и режима."""
        from pathlib import Path

        parts = ["Termin Editor"]

        # Добавляем имя проекта
        if self._project_controller is not None:
            project_name = self._project_controller.project_name
            if project_name is not None:
                parts.append(f"- {project_name}")

        # Проверяем режим редактирования префаба
        is_editing_prefab = self.prefab_edit_controller.is_editing if self.prefab_edit_controller else False
        if is_editing_prefab:
            prefab_name = self.prefab_edit_controller.prefab_name
            parts.append(f"[Prefab: {prefab_name}]")
        elif self.scene_manager is not None:
            # Добавляем имя сцены
            scene_path = self.scene_manager.get_scene_path(self._editor_scene_name)
            if scene_path is not None:
                scene_name = Path(scene_path).stem
                parts.append(f"[{scene_name}]")
            else:
                parts.append("[Untitled]")

        # Добавляем режим игры
        is_playing = self.is_game_mode
        if is_playing:
            parts.append("- PLAYING")

        self.setWindowTitle(" ".join(parts))

    # ----------- display input mode -----------

    def _on_display_input_mode_changed(self, display, mode: str) -> None:
        """
        Handle display input mode change from RenderingController.

        When a display switches to "editor" mode, creates EditorViewportFeatures
        for that display. When switching away, destroys it.

        Multiple displays can be in "editor" mode simultaneously.

        Args:
            display: Display that changed mode.
            mode: New input mode ("none", "simple", "editor").
        """
        if self._rendering_controller is None:
            return

        display_id = id(display)

        if mode == "editor":
            # Create EditorViewportFeatures for this display (if not exists)
            if display_id in self._editor_features:
                # Already has editor features
                return

            backend_window = self._rendering_controller.get_display_backend_window(display)
            if backend_window is None:
                return

            def get_fbo_pool(d=display):
                return self._rendering_controller.get_display_fbo_pool(d)

            # Create new EditorViewportFeatures
            editor_features = EditorViewportFeatures(
                display=display,
                backend_window=backend_window,
                graphics=self.world.graphics,
                gizmo_manager=self.gizmo_manager,
                on_entity_picked=self._on_entity_picked_from_viewport,
                on_hover_entity=self._on_hover_entity_from_viewport,
                get_fbo_pool=get_fbo_pool,
                request_update=self._request_viewport_update,
            )
            editor_features.set_gizmo_undo_handler(self.push_undo_command)
            editor_features.set_on_transform_dragging(self._on_gizmo_transform_dragging)

            # Sync current selection state
            if self.selection_manager is not None:
                editor_features.selected_entity_id = self.selection_manager.selected_entity_id
                editor_features.hover_entity_id = self.selection_manager.hover_entity_id

            # Register
            self._editor_features[display_id] = editor_features

            # Set editor pipeline for the viewport (if it has viewports)
            if display.viewports:
                editor_pipeline = editor_features.make_editor_pipeline()
                self._rendering_controller.set_viewport_pipeline(
                    display.viewports[0],
                    editor_pipeline,
                )
        else:
            # Destroy EditorViewportFeatures for this display (if exists)
            if display_id in self._editor_features:
                editor_features = self._editor_features.pop(display_id)
                # Clean up callbacks
                editor_features.detach_from_display()

        self._request_viewport_update()

    # ----------- SDL render loop support -----------

    def should_close(self) -> bool:
        """Check if window should close."""
        return self._should_close

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        self._should_close = True
        super().closeEvent(event)
