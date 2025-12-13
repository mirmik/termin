# ===== termin/editor/editor_window.py =====
import os
from pathlib import Path

from PyQt6 import uic
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTreeView, QListView, QLabel, QMenu, QInputDialog, QMessageBox, QFileDialog, QTabWidget, QPlainTextEdit
from PyQt6.QtWidgets import QStatusBar, QToolBar, QPushButton, QSizePolicy
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QEvent, pyqtSignal

from termin.editor.undo_stack import UndoStack, UndoCommand
from termin.editor.editor_commands import AddEntityCommand, DeleteEntityCommand, RenameEntityCommand
from termin.editor.scene_tree_controller import SceneTreeController
from termin.editor.editor_viewport_features import EditorViewportFeatures
from termin.editor.gizmo import GizmoController
from termin.editor.game_mode_controller import GameModeController
from termin.editor.prefab_edit_controller import PrefabEditController
from termin.editor.world_persistence import WorldPersistence
from termin.editor.selection_manager import SelectionManager
from termin.editor.dialog_manager import DialogManager
from termin.editor.inspector_controller import InspectorController
from termin.editor.menu_bar_controller import MenuBarController
from termin.editor.editor_camera import EditorCameraManager
from termin.editor.resource_loader import ResourceLoader
from termin.editor.viewport_list_widget import ViewportListWidget
from termin.editor.rendering_controller import RenderingController
from termin.editor.external_editor import open_in_text_editor
from termin.editor.scene_file_controller import SceneFileController
from termin.editor.project_file_watcher import ProjectFileWatcher
from termin.editor.file_processors import (
    MaterialFileProcessor,
    MeshFileProcessor,
    ShaderFileProcessor,
    TextureFileProcessor,
    ComponentFileProcessor,
    PipelineFileProcessor,
)
from termin.editor.spacemouse_controller import SpaceMouseController

from termin.visualization.core.camera import OrbitCameraController
from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3
from termin.editor.project_browser import ProjectBrowser
from termin.editor.settings import EditorSettings
from termin.editor.prefab_persistence import PrefabPersistence
from termin.editor.drag_drop import EditorMimeTypes, parse_asset_path_mime_data
from termin.visualization.core.resources import ResourceManager
from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend


class EditorWindow(QMainWindow):
    undo_stack_changed = pyqtSignal()

    def __init__(self, world, initial_scene, sdl_backend: SDLEmbeddedWindowBackend):
        super().__init__()
        self.undo_stack = UndoStack()
        self._menu_bar_controller: MenuBarController | None = None
        self._status_bar_label: QLabel | None = None
        self._fps_smooth: float | None = None
        self._fps_alpha: float = 0.1  # экспоненциальное сглаживание: f_new = f_prev*(1-α) + f_curr*α
        self._should_close = False

        self.world = world
        self._sdl_backend = sdl_backend

        # --- ресурс-менеджер редактора ---
        self.resource_manager = ResourceManager.instance()
        self.resource_manager.register_builtin_components()
        self.resource_manager.register_builtin_frame_passes()
        self.resource_manager.register_builtin_post_effects()

        # --- WorldPersistence - ЕДИНСТВЕННЫЙ владелец сцены ---
        # Создаётся ПЕРВЫМ, до всех контроллеров
        self.world_persistence = WorldPersistence(
            scene=initial_scene,
            resource_manager=self.resource_manager,
            on_scene_changed=self._on_scene_changed,
            get_editor_camera_data=self._get_editor_camera_data,
            set_editor_camera_data=self._set_editor_camera_data,
            get_selected_entity_name=self._get_selected_entity_name,
            select_entity_by_name=self._select_entity_by_name,
            get_displays_data=self._get_displays_data,
            set_displays_data=self._set_displays_data,
            rescan_file_resources=self._rescan_file_resources,
        )

        # контроллеры создадим чуть позже
        self.scene_tree_controller: SceneTreeController | None = None
        self.editor_viewport: EditorViewportFeatures | None = None
        self.gizmo_controller: GizmoController | None = None
        self.selection_manager: SelectionManager | None = None
        self.game_mode_controller: GameModeController | None = None
        self.prefab_edit_controller: PrefabEditController | None = None
        self.project_browser = None
        self._project_name: str | None = None
        self._current_project_file: Path | None = None
        self._play_button: QPushButton | None = None
        self._prefab_toolbar: QWidget | None = None
        self._prefab_toolbar_label: QLabel | None = None
        self._prefab_menu: QMenu | None = None
        self._viewport_list_widget: ViewportListWidget | None = None
        self._rendering_controller: RenderingController | None = None

        ui_path = os.path.join(os.path.dirname(__file__), "editor.ui")
        uic.loadUi(ui_path, self)

        self._init_status_bar()

        self._setup_menu_bar()

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
            MaterialFileProcessor(
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
            PipelineFileProcessor(
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

        self._fix_splitters()

        # --- InspectorController ---
        self._inspector_controller = InspectorController(
            container=self.inspectorContainer,
            resource_manager=self.resource_manager,
            push_undo_command=self.push_undo_command,
            on_transform_changed=self._on_inspector_transform_changed,
            on_component_changed=self._on_inspector_component_changed,
            on_material_changed=self._on_material_inspector_changed,
        )

        # Для обратной совместимости
        self.entity_inspector = self._inspector_controller.entity_inspector
        self.material_inspector = self._inspector_controller.material_inspector
        self.inspector = self.entity_inspector

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

        # --- EditorCameraManager ---
        self._camera_manager = EditorCameraManager(self.scene)

        # Для обратной совместимости
        self.editor_entities = self._camera_manager.editor_entities
        self.camera = self._camera_manager.camera

        # --- SpaceMouse support (initialized later after console is ready) ---
        self._spacemouse: SpaceMouseController | None = None

        # --- гизмо-контроллер ---
        self.gizmo_controller = GizmoController(
            scene=self.scene,
            editor_entities=self._camera_manager.editor_entities,
            undo_handler=self.push_undo_command,
        )
        self.gizmo_controller.set_on_transform_dragging(
            self._on_gizmo_transform_dragging
        )

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

        # Create viewport in editor display
        self.viewport = editor_display.create_viewport(
            scene=self.scene,
            camera=self.camera,
        )
        self.camera.add_viewport(self.viewport)

        # Set editor pipeline
        editor_pipeline = None  # Will be set after EditorViewportFeatures creation

        # Install event filter on GL widget
        gl_widget = self._rendering_controller.editor_gl_widget
        if gl_widget is not None:
            gl_widget.installEventFilter(self)
            gl_widget.setAcceptDrops(True)

        # Enable drag-drop on viewport container
        self.editorViewportTab.setAcceptDrops(True)
        self.editorViewportTab.installEventFilter(self)

        # --- EditorViewportFeatures (editor UX layer) ---
        self.editor_viewport = EditorViewportFeatures(
            display=editor_display,
            backend_window=backend_window,
            graphics=self.world.graphics,
            gizmo_controller=self.gizmo_controller,
            on_entity_picked=self._on_entity_picked_from_viewport,
            on_hover_entity=self._on_hover_entity_from_viewport,
            get_fbo_pool=self._rendering_controller.get_editor_fbo_pool,
            request_update=self._request_viewport_update,
        )

        # Register in editor features dict
        self._editor_features[id(editor_display)] = self.editor_viewport

        # Set editor pipeline through RenderingController
        editor_pipeline = self.editor_viewport.make_editor_pipeline()
        self._rendering_controller.set_viewport_pipeline(self.viewport, editor_pipeline)

        # Set editor pipeline getter for ViewportInspector
        self._inspector_controller.viewport_inspector.set_editor_pipeline_getter(
            self.editor_viewport.make_editor_pipeline
        )

        # For backwards compatibility
        self.viewport_controller = self.editor_viewport

        # --- SelectionManager ---
        self.selection_manager = SelectionManager(
            get_pick_id=self._get_pick_id_for_entity,
            on_selection_changed=self._on_selection_changed_internal,
            on_hover_changed=self._on_hover_changed_internal,
        )

        # --- GameModeController - использует WorldPersistence ---
        self.game_mode_controller = GameModeController(
            world_persistence=self.world_persistence,
            on_mode_changed=self._on_game_mode_changed,
            on_request_update=self._request_viewport_update,
            on_tick=self._on_game_tick,
        )

        # --- PrefabEditController - режим изоляции для редактирования префабов ---
        self.prefab_edit_controller = PrefabEditController(
            world_persistence=self.world_persistence,
            resource_manager=self.resource_manager,
            on_mode_changed=self._on_prefab_mode_changed,
            on_request_update=self._request_viewport_update,
            log_message=self._log_to_console,
        )

        # --- SceneFileController ---
        self._scene_file_controller = SceneFileController(
            parent=self,
            get_world_persistence=lambda: self.world_persistence,
            on_after_new=self._on_after_scene_new,
            on_after_save=self._update_window_title,
            on_after_load=self._update_window_title,
            log_message=self._log_to_console,
        )

        # --- Project Browser ---
        self._init_project_browser()

        # --- SpaceMouse support ---
        self._init_spacemouse()

        # --- Инициализация настроек (поиск VS Code и т.п.) ---
        EditorSettings.instance().init_text_editor_if_empty()

        # --- Загружаем последнюю открытую сцену ---
        # Загрузка сцены автоматически триггерит _rescan_file_resources через WorldPersistence
        self._scene_file_controller.load_last_scene()

    @property
    def scene(self):
        """Текущая сцена. Всегда получаем из WorldPersistence."""
        return self.world_persistence.scene

    # ----------- undo / redo -----------

    def _setup_menu_bar(self) -> None:
        """Create editor menu bar via MenuBarController."""
        self._menu_bar_controller = MenuBarController(
            menu_bar=self.menuBar(),
            on_new_project=self._new_project,
            on_open_project=self._open_project,
            on_new_scene=self._new_scene,
            on_save_scene=self._save_scene,
            on_save_scene_as=self._save_scene_as,
            on_load_scene=self._load_scene,
            on_load_material=self._load_material_from_file,
            on_load_components=self._load_components_from_file,
            on_exit=self.close,
            on_undo=self.undo,
            on_redo=self.redo,
            on_settings=self._show_settings_dialog,
            on_scene_properties=self._show_scene_properties,
            on_toggle_game_mode=self._toggle_game_mode,
            on_show_undo_stack_viewer=self._show_undo_stack_viewer,
            on_show_framegraph_debugger=self._show_framegraph_debugger,
            on_show_resource_manager_viewer=self._show_resource_manager_viewer,
            can_undo=lambda: self.undo_stack.can_undo,
            can_redo=lambda: self.undo_stack.can_redo,
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

    def _show_undo_stack_viewer(self) -> None:
        """Opens undo/redo stack viewer window."""
        self._dialog_manager.show_undo_stack_viewer()

    def _show_framegraph_debugger(self) -> None:
        """Opens framegraph texture viewer dialog."""
        debugger = self._dialog_manager.show_framegraph_debugger(
            window_backend=self._sdl_backend,
            graphics=self.world.graphics,
            rendering_controller=self._rendering_controller,
            on_request_update=self._request_viewport_update,
        )
        # Connect debugger to editor viewport for updates in after_render
        if self.editor_viewport is not None:
            self.editor_viewport.set_framegraph_debugger(debugger)

    def _show_resource_manager_viewer(self) -> None:
        """Opens resource manager viewer dialog."""
        self._dialog_manager.show_resource_manager_viewer()

    # ----------- editor camera -----------

    def _get_editor_camera_data(self) -> dict | None:
        """Get editor camera data for serialization."""
        return self._camera_manager.get_camera_data()

    def _set_editor_camera_data(self, data: dict) -> None:
        """Apply saved camera data."""
        self._camera_manager.set_camera_data(data)

    def _get_selected_entity_name(self) -> str | None:
        """
        Возвращает имя выделенной сущности.
        """
        if self.selection_manager is None:
            return None
        selected = self.selection_manager.selected
        if selected is None:
            return None
        return selected.name

    def _select_entity_by_name(self, name: str) -> None:
        """
        Выделяет сущность по имени.
        """
        # Ищем сущность в сцене
        entity = None
        for ent in self.scene.entities:
            if ent.name == name and ent.selectable:
                entity = ent
                break

        if entity is None:
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
        """Get displays/viewports data for serialization."""
        if self._rendering_controller is None:
            return None
        return self._rendering_controller.serialize_displays()

    def _set_displays_data(self, data: list) -> None:
        """Restore displays/viewports from serialized data."""
        if self._rendering_controller is None:
            return
        self._rendering_controller.restore_displays(data, self.scene)

    def _get_project_path(self) -> str | None:
        """Get current project path from project browser."""
        if self.project_browser is None or self.project_browser.root_path is None:
            return None
        return str(self.project_browser.root_path)

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
        """Log message to console output."""
        if self.consoleOutput is not None:
            self.consoleOutput.appendPlainText(message)

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

    def _fix_splitters(self):
        self.topSplitter.setOpaqueResize(False)
        self.verticalSplitter.setOpaqueResize(False)

        self.topSplitter.setCollapsible(0, False)
        self.topSplitter.setCollapsible(1, False)
        self.topSplitter.setCollapsible(2, False)

        self.verticalSplitter.setCollapsible(0, False)
        self.verticalSplitter.setCollapsible(1, False)

        self.topSplitter.setSizes([300, 1000, 300])
        self.verticalSplitter.setSizes([600, 200])

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
            on_request_update=self._request_viewport_update,
            on_display_input_mode_changed=self._on_display_input_mode_changed,
        )

    def _init_spacemouse(self) -> None:
        """Initialize SpaceMouse controller if device available."""
        spacemouse = SpaceMouseController()
        if spacemouse.open():
            self._spacemouse = spacemouse
            self._log_to_console("[SpaceMouse] Device connected")
        else:
            self._spacemouse = None

    def _init_project_browser(self):
        """Инициализация файлового браузера проекта."""
        from pathlib import Path

        # Находим виджеты из .ui
        self.projectDirTree: QTreeView = self.findChild(QTreeView, "projectDirTree")
        self.projectFileList: QListView = self.findChild(QListView, "projectFileList")
        self.bottomTabWidget: QTabWidget = self.findChild(QTabWidget, "bottomTabWidget")
        self.consoleOutput: QPlainTextEdit = self.findChild(QPlainTextEdit, "consoleOutput")

        if self.projectDirTree is None or self.projectFileList is None:
            return

        # Загружаем последний открытый проект (если есть валидный .terminproj)
        settings = EditorSettings.instance()
        project_file = settings.get_last_project_file()

        project_root: Path | None = None
        if project_file is not None:
            project_root = project_file.parent
            self._current_project_file = project_file

        self.project_browser = ProjectBrowser(
            dir_tree=self.projectDirTree,
            file_list=self.projectFileList,
            root_path=project_root,
            on_file_selected=self._on_project_file_selected,
            on_file_double_clicked=self._on_project_file_double_clicked,
        )

        # Обновляем имя проекта и заголовок окна
        if project_root is not None:
            self._project_name = project_root.name
        else:
            self._project_name = None
        self._update_window_title()

    def _on_project_file_selected(self, file_path) -> None:
        """Обработчик выбора файла в Project Browser (одинарный клик)."""
        from pathlib import Path
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".material":
            # Материал — открываем в инспекторе материалов
            self.show_material_inspector_for_file(str(path))
        elif suffix == ".pipeline":
            # Пайплайн — открываем в инспекторе пайплайнов
            self._inspector_controller.show_pipeline_inspector_for_file(str(path))
        elif suffix in (".png", ".jpg", ".jpeg", ".tga", ".bmp"):
            # Текстура — открываем в инспекторе текстур
            self._inspector_controller.show_texture_inspector_for_file(str(path))
        elif suffix in (".stl", ".obj"):
            # Меш — открываем в инспекторе мешей
            self._inspector_controller.show_mesh_inspector_for_file(str(path))

    def _on_project_file_double_clicked(self, file_path) -> None:
        """Обработчик двойного клика на файл в Project Browser."""
        from pathlib import Path
        path = Path(file_path)

        # Обработка разных типов файлов
        if path.suffix == ".scene":
            # Это файл сцены — загружаем
            self._load_scene_from_file(str(path))

        elif path.suffix == ".prefab":
            # Это файл префаба — открываем в режиме изоляции
            self._open_prefab(str(path))

        elif path.suffix in (".material", ".shader", ".py", ".pipeline"):
            # Материалы, шейдеры, скрипты, пайплайны — открываем во внешнем текстовом редакторе
            self._open_in_text_editor(str(path))

        else:
            # Другие файлы — логируем
            if self.consoleOutput is not None:
                self.consoleOutput.appendPlainText(f"Opened: {file_path}")

    def _new_project(self) -> None:
        """Создать новый проект (.terminproj файл)."""
        current_dir = str(Path.cwd())
        if self._current_project_file is not None:
            current_dir = str(self._current_project_file.parent)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Create New Project",
            current_dir,
            "Termin Project (*.terminproj)",
        )

        if not file_path:
            return

        # Добавляем расширение если не указано
        if not file_path.endswith(".terminproj"):
            file_path += ".terminproj"

        project_file = Path(file_path)

        # Создаём пустой файл проекта (пока просто пустой JSON)
        import json
        project_data = {
            "version": 1,
            "name": project_file.stem,
        }
        project_file.write_text(json.dumps(project_data, indent=2), encoding="utf-8")

        self._load_project_file(project_file)

    def _open_project(self) -> None:
        """Открыть существующий проект (.terminproj файл)."""
        current_dir = str(Path.cwd())
        if self._current_project_file is not None:
            current_dir = str(self._current_project_file.parent)

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            current_dir,
            "Termin Project (*.terminproj)",
        )

        if not file_path:
            return

        project_file = Path(file_path)
        if not project_file.exists() or project_file.suffix != ".terminproj":
            return

        self._load_project_file(project_file)

    def _load_project_file(self, project_file: Path) -> None:
        """Загрузить проект из файла .terminproj."""
        project_root = project_file.parent

        self._current_project_file = project_file
        self._project_name = project_root.name

        if self.project_browser is not None:
            self.project_browser.set_root_path(str(project_root))

        self._update_window_title()

        # Сохраняем путь для следующего запуска
        EditorSettings.instance().set_last_project_file(project_file)

        self._log_to_console(f"Opened project: {project_file}")

        # Сбрасываем сцену и пересканируем ресурсы
        self.world_persistence.reset()

    def _show_settings_dialog(self) -> None:
        """Opens editor settings dialog."""
        self._dialog_manager.show_settings_dialog()

    def _open_in_text_editor(self, file_path: str) -> None:
        """Open file in external text editor."""
        open_in_text_editor(file_path, parent=self, log_message=self._log_to_console)

    def _on_resource_reloaded(self, resource_type: str, resource_name: str) -> None:
        """Callback for resource reload."""
        self._log_to_console(f"Reloaded {resource_type}: {resource_name}")
        self._request_viewport_update()

    def _scan_project_resources(self) -> None:
        """Scan project directory for resources using ProjectFileWatcher."""
        project_path = self._get_project_path()
        if project_path is None:
            return

        # Register built-in DefaultShader
        self.resource_manager.register_default_shader()

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
        self.resource_manager.register_builtin_materials()
        self.resource_manager.register_builtin_meshes()

        # If watcher not enabled yet, enable it. Otherwise rescan.
        if not self._project_file_watcher.is_enabled:
            self._project_file_watcher.enable(project_path)
        else:
            self._project_file_watcher.rescan()

    def _init_status_bar(self) -> None:
        """
        Создаёт полосу статуса внизу окна. FPS будем писать сюда в игровом режиме.
        """
        status_bar: QStatusBar = self.statusBar()
        status_bar.setSizeGripEnabled(False)

        label = QLabel("Editor mode")
        status_bar.addPermanentWidget(label, 1)
        self._status_bar_label = label

    def _init_viewport_toolbar(self) -> None:
        """
        Создаёт панель инструментов над centerTabWidget с кнопкой Play в центре.
        """
        toolbar = QWidget()
        toolbar.setFixedHeight(32)
        toolbar.setStyleSheet("background-color: #3c3c3c;")

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Левый спейсер для центрирования кнопки
        layout.addStretch(1)

        # Кнопка Play/Stop
        play_btn = QPushButton("Play")
        play_btn.setFixedSize(60, 24)
        play_btn.setCheckable(True)
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #505050;
                color: #ffffff;
                border: 1px solid #606060;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:checked {
                background-color: #4a90d9;
                border-color: #5aa0e9;
            }
            QPushButton:checked:hover {
                background-color: #5aa0e9;
            }
        """)
        play_btn.clicked.connect(self._toggle_game_mode)
        layout.addWidget(play_btn)
        self._play_button = play_btn

        # Правый спейсер для центрирования кнопки
        layout.addStretch(1)

        # --- Prefab toolbar (скрытый по умолчанию) ---
        prefab_toolbar = QWidget()
        prefab_toolbar.setFixedHeight(28)
        prefab_toolbar.setStyleSheet("background-color: #4a7c59;")  # Зелёный оттенок
        prefab_toolbar.setVisible(False)

        prefab_layout = QHBoxLayout(prefab_toolbar)
        prefab_layout.setContentsMargins(8, 2, 8, 2)
        prefab_layout.setSpacing(8)

        # Иконка и название префаба
        prefab_label = QLabel("Editing Prefab: ")
        prefab_label.setStyleSheet("color: white; font-weight: bold;")
        prefab_layout.addWidget(prefab_label)
        self._prefab_toolbar_label = prefab_label

        prefab_layout.addStretch(1)

        # Кнопка Save
        save_btn = QPushButton("Save")
        save_btn.setFixedSize(70, 22)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #5a9a6a;
                color: white;
                border: 1px solid #6aaa7a;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6aaa7a;
            }
        """)
        save_btn.clicked.connect(self._save_prefab)
        prefab_layout.addWidget(save_btn)

        # Кнопка Exit
        exit_btn = QPushButton("Exit")
        exit_btn.setFixedSize(70, 22)
        exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #6a6a6a;
                color: white;
                border: 1px solid #7a7a7a;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7a7a7a;
            }
        """)
        exit_btn.clicked.connect(self._exit_prefab_editing)
        prefab_layout.addWidget(exit_btn)

        self._prefab_toolbar = prefab_toolbar

        # Создаём контейнер для toolbar + prefab_toolbar + centerTabWidget
        center_container = QWidget()
        container_layout = QVBoxLayout(center_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Добавляем toolbars в контейнер
        container_layout.addWidget(toolbar)
        container_layout.addWidget(prefab_toolbar)

        # Перемещаем centerTabWidget в контейнер
        # Сначала получаем индекс centerTabWidget в topSplitter
        splitter_index = self.topSplitter.indexOf(self._center_tab_widget)

        # Убираем centerTabWidget из splitter (setParent(None))
        self._center_tab_widget.setParent(None)

        # Добавляем centerTabWidget в контейнер
        container_layout.addWidget(self._center_tab_widget)

        # Вставляем контейнер в splitter на место centerTabWidget
        self.topSplitter.insertWidget(splitter_index, center_container)

        # Переустанавливаем размеры сплиттера после перемещения виджетов
        self.topSplitter.setSizes([300, 1000, 300])

    # ----------- связи с контроллерами -----------

    def _request_viewport_update(self) -> None:
        if self._rendering_controller is not None:
            backend = self._rendering_controller.editor_backend_window
            if backend is not None:
                backend.request_update()

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
        from termin.geombase.pose3 import Pose3
        import numpy as np

        # Загружаем prefab
        rm = ResourceManager.instance()
        persistence = PrefabPersistence(rm)

        try:
            entity = persistence.load(Path(prefab_path))
        except Exception as e:
            print(f"Failed to load prefab: {e}")
            return

        # Определяем позицию в мире через unproject
        world_pos = self._unproject_drop_position(drop_pos)
        print(f"[DEBUG] Setting entity position to: {world_pos}")

        # Устанавливаем позицию
        entity.transform.local_pose = Pose3(lin=world_pos)
        print(f"[DEBUG] Entity local_pose after set: {entity.transform.local_pose}")

        # Добавляем entity в сцену через команду (с поддержкой undo)
        cmd = AddEntityCommand(self.scene, entity)
        self.push_undo_command(cmd, merge=False)

        # Обновляем SceneTree и выделяем новый entity
        self.scene_tree_controller.rebuild(select_obj=entity)

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
            print(f"[DEBUG] cam_pos={cam_pos}, forward={cam_forward}, fallback={fallback_pos}")

        if self.editor_viewport is None or self.viewport is None:
            return fallback_pos

        # Координаты drop в пикселях виджета
        x = float(drop_pos.x())
        y = float(drop_pos.y())

        # Читаем глубину из ID buffer
        depth = self.editor_viewport.pick_depth_at(x, y, self.viewport, buffer_name="id")
        print(f"[DEBUG] drop at ({x}, {y}), depth={depth}")
        if depth is None or depth >= 1.0:
            # Нет геометрии под курсором — используем fallback
            print(f"[DEBUG] using fallback_pos={fallback_pos}")
            return fallback_pos

        # Получаем размеры viewport
        viewport_rect = self.viewport.rect  # (x, y, w, h) в нормализованных координатах
        widget = self.editorViewportTab
        w = widget.width()
        h = widget.height()
        print(f"[DEBUG] widget size: {w}x{h}")

        # Нормализованные координаты в пределах viewport (0..1)
        # viewport_rect — нормализованные координаты, но drop_pos — в пикселях виджета
        # Для простоты считаем, что viewport занимает весь виджет
        nx = (x / w) * 2.0 - 1.0
        ny = (y / h) * -2.0 + 1.0  # Y инвертирован

        # Глубина в NDC (OpenGL: 0..1 -> -1..1)
        z_ndc = depth * 2.0 - 1.0
        print(f"[DEBUG] NDC: nx={nx:.3f}, ny={ny:.3f}, z_ndc={z_ndc:.3f}")

        # Точка в clip space
        clip_pos = np.array([nx, ny, z_ndc, 1.0], dtype=np.float32)

        # Матрицы камеры
        if self.camera is None:
            return fallback_pos

        proj = self.camera.get_projection_matrix()
        view = self.camera.get_view_matrix()
        pv = proj @ view

        # Inverse projection-view matrix
        try:
            inv_pv = np.linalg.inv(pv)
        except np.linalg.LinAlgError:
            print("[DEBUG] Failed to invert PV matrix")
            return fallback_pos

        # Unproject
        world_h = inv_pv @ clip_pos
        print(f"[DEBUG] world_h={world_h}")
        if abs(world_h[3]) < 1e-6:
            print("[DEBUG] world_h[3] too small")
            return fallback_pos

        world_pos = world_h[:3] / world_h[3]
        print(f"[DEBUG] unproject result: {world_pos}")
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

        # Обновляем гизмо
        if self.gizmo_controller is not None:
            self.gizmo_controller.set_target(entity)

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

    # ----------- WorldPersistence колбэки -----------

    def _on_scene_changed(self, new_scene) -> None:
        """
        Callback from WorldPersistence when scene changes.
        Called on reset(), load(), restore_state().
        Recreates all editor entities in the new scene.
        """
        # Clear undo stack
        self.undo_stack.clear()
        self._update_undo_redo_actions()
        self.undo_stack_changed.emit()

        # Clear selection
        if self.selection_manager is not None:
            self.selection_manager.clear()

        # Recreate editor entities in new scene
        self._camera_manager.recreate_in_scene(new_scene)
        self.editor_entities = self._camera_manager.editor_entities
        self.camera = self._camera_manager.camera

        # Recreate gizmo in new scene
        if self.gizmo_controller is not None:
            self.gizmo_controller.recreate_gizmo(new_scene, self._camera_manager.editor_entities)
            self.gizmo_controller.set_on_transform_dragging(
                self._on_gizmo_transform_dragging
            )

        # Update all EditorViewportFeatures
        for editor_features in self._editor_features.values():
            editor_features.set_scene(new_scene)
            editor_features.set_camera(self._camera_manager.camera)
            editor_features.selected_entity_id = 0
            editor_features.hover_entity_id = 0

        # Update scene tree
        if self.scene_tree_controller is not None:
            self.scene_tree_controller._scene = new_scene
            self.scene_tree_controller.rebuild()

        # Clear inspector
        if self.inspector is not None:
            self.inspector.set_target(None)

        self._request_viewport_update()

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

    def _on_after_scene_new(self) -> None:
        """Callback after new scene created."""
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.rebuild()
        self._request_viewport_update()

    # ----------- game mode -----------

    def _toggle_game_mode(self) -> None:
        """Переключает режим игры."""
        if self.game_mode_controller is not None:
            self.game_mode_controller.toggle()

    def _on_game_mode_changed(self, is_playing: bool) -> None:
        """Колбэк от GameModeController при изменении режима."""
        if is_playing:
            # Входим в игровой режим
            # Переключаем все EditorViewportFeatures в режим game
            for editor_features in self._editor_features.values():
                editor_features.set_world_mode("game")

            # Скрываем гизмо
            if self.gizmo_controller is not None:
                self.gizmo_controller.set_visible(False)

            # Сбрасываем выделение
            if self.selection_manager is not None:
                self.selection_manager.clear()
            if self.inspector is not None:
                self.inspector.set_target(None)
        else:
            # Выходим из игрового режима
            # Переключаем все EditorViewportFeatures в режим editor
            for editor_features in self._editor_features.values():
                editor_features.set_world_mode("editor")

            # Показываем гизмо
            if self.gizmo_controller is not None:
                self.gizmo_controller.set_visible(True)

            # Обновляем дерево сцены
            if self.scene_tree_controller is not None:
                self.scene_tree_controller.rebuild()

        # Сбрасываем сглаженное значение FPS при входе/выходе
        self._fps_smooth = None
        self._update_game_mode_ui()
        self._request_viewport_update()

    def _on_game_tick(self, dt: float) -> None:
        """
        При вызове игрового тика считаем FPS как 1/dt и сглаживаем экспонентой.
        Формула: f_new = f_prev * (1 - α) + f_curr * α, α берём из _fps_alpha.
        """
        if dt <= 0.0:
            return

        fps_instant = 1.0 / dt
        if self._fps_smooth is None:
            self._fps_smooth = fps_instant
        else:
            alpha = self._fps_alpha
            self._fps_smooth = self._fps_smooth * (1.0 - alpha) + fps_instant * alpha

        self._update_status_bar()

    def _update_game_mode_ui(self) -> None:
        """Update UI elements based on game mode state."""
        is_playing = self.game_mode_controller.is_playing if self.game_mode_controller else False

        if self._menu_bar_controller is not None:
            self._menu_bar_controller.update_play_action(is_playing)

        # Обновляем кнопку Play в toolbar
        if self._play_button is not None:
            self._play_button.setChecked(is_playing)
            self._play_button.setText("Stop" if is_playing else "Play")

        self._update_window_title()
        self._update_status_bar()

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
        if self._project_name is not None:
            parts.append(f"- {self._project_name}")

        # Проверяем режим редактирования префаба
        is_editing_prefab = self.prefab_edit_controller.is_editing if self.prefab_edit_controller else False
        if is_editing_prefab:
            prefab_name = self.prefab_edit_controller.prefab_name
            parts.append(f"[Prefab: {prefab_name}]")
        elif self.world_persistence is not None:
            # Добавляем имя сцены
            scene_path = self.world_persistence.current_scene_path
            if scene_path is not None:
                scene_name = Path(scene_path).stem
                parts.append(f"[{scene_name}]")
            else:
                parts.append("[Untitled]")

        # Добавляем режим игры
        is_playing = self.game_mode_controller.is_playing if self.game_mode_controller else False
        if is_playing:
            parts.append("- PLAYING")

        self.setWindowTitle(" ".join(parts))

    def _update_status_bar(self) -> None:
        """Заполняет текст статус-бара (FPS в игре, режим редактора вне игры)."""
        if self._status_bar_label is None:
            return

        is_playing = self.game_mode_controller.is_playing if self.game_mode_controller else False
        if not is_playing:
            self._status_bar_label.setText("Editor mode")
            return

        if self._fps_smooth is None:
            self._status_bar_label.setText("FPS: --")
            return

        self._status_bar_label.setText(f"FPS: {self._fps_smooth:.1f}")

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
                gizmo_controller=self.gizmo_controller,
                on_entity_picked=self._on_entity_picked_from_viewport,
                on_hover_entity=self._on_hover_entity_from_viewport,
                get_fbo_pool=get_fbo_pool,
                request_update=self._request_viewport_update,
            )

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

    def tick(self, dt: float) -> None:
        """
        Main tick function called from render loop.

        Handles rendering through unified RenderingController.
        Note: Game mode updates are handled by GameModeController's QTimer.
        """
        # In game mode - always render at target FPS
        # In editor mode - render only when needed (on-demand)
        is_playing = self.game_mode_controller.is_playing if self.game_mode_controller else False

        # Poll SpaceMouse input (only in editor mode)
        if not is_playing and self._spacemouse is not None:
            orbit_controller = self._camera_manager.orbit_controller
            self._spacemouse.update(orbit_controller, self._request_viewport_update)

        # Check if any display needs render (unified check)
        needs_render = is_playing
        if not needs_render and self._rendering_controller is not None:
            needs_render = self._rendering_controller.any_display_needs_render()

        # Render all displays through RenderingController (unified render path)
        if needs_render and self._rendering_controller is not None:
            self._rendering_controller.render_all_displays()

            # Editor-specific post-render (picking, hover, etc.) for ALL displays
            for editor_features in self._editor_features.values():
                editor_features.after_render()
