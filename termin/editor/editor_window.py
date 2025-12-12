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
from termin.editor.viewport_controller import ViewportController
from termin.editor.gizmo import GizmoController
from termin.editor.game_mode_controller import GameModeController
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
    ShaderFileProcessor,
    TextureFileProcessor,
    ComponentFileProcessor,
    PipelineFileProcessor,
)

from termin.visualization.core.camera import OrbitCameraController
from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3
from termin.editor.project_browser import ProjectBrowser
from termin.editor.settings import EditorSettings
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
        )

        # контроллеры создадим чуть позже
        self.scene_tree_controller: SceneTreeController | None = None
        self.viewport_controller: ViewportController | None = None
        self.gizmo_controller: GizmoController | None = None
        self.selection_manager: SelectionManager | None = None
        self.game_mode_controller: GameModeController | None = None
        self.project_browser = None
        self._project_name: str | None = None
        self._current_project_file: Path | None = None
        self._play_button: QPushButton | None = None
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
        self._resource_loader.init_resources_from_scene()

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

        # --- гизмо-контроллер ---
        self.gizmo_controller = GizmoController(
            scene=self.scene,
            editor_entities=self._camera_manager.editor_entities,
            undo_handler=self.push_undo_command,
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

        # --- viewport ---
        self.viewport = None
        self.viewport_controller = ViewportController(
            container=self.editorViewportTab,
            world=self.world,
            scene=self.scene,
            camera=self.camera,
            gizmo_controller=self.gizmo_controller,
            on_entity_picked=self._on_entity_picked_from_viewport,
            on_hover_entity=self._on_hover_entity_from_viewport,
            sdl_backend=self._sdl_backend,
        )

        self.viewport = self.viewport_controller.viewport

        gl_widget = self.viewport_controller.gl_widget
        gl_widget.installEventFilter(self)

        # --- ViewportListWidget (in Rendering tab) ---
        self._init_viewport_list_widget()

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

        # --- Инициализация настроек (поиск VS Code и т.п.) ---
        EditorSettings.instance().init_text_editor_if_empty()

        # --- Сканируем ресурсы проекта и включаем отслеживание ---
        self._scan_project_resources()

        # --- Загружаем последнюю открытую сцену ---
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
        if self.viewport_controller is None or self.viewport is None:
            return
        self._dialog_manager.show_framegraph_debugger(
            graphics=self.viewport_controller.graphics,
            viewport_controller=self.viewport_controller,
        )

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

    def _get_project_path(self) -> str | None:
        """Get current project path from project browser."""
        if self.project_browser is None or self.project_browser.root_path is None:
            return None
        return str(self.project_browser.root_path)

    def _get_graphics(self):
        """Get GraphicsBackend from viewport controller."""
        if self.viewport_controller is not None:
            return self.viewport_controller.graphics
        return None

    def _get_window_backend(self):
        """Get WindowBackend from world."""
        if self.world is not None:
            return self.world.window_backend
        return None

    def _get_render_engine(self):
        """Get RenderEngine from viewport controller."""
        if self.viewport_controller is not None:
            return self.viewport_controller._render_engine
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
        self._rendering_controller = RenderingController(
            viewport_list_widget=self._viewport_list_widget,
            inspector_controller=self._inspector_controller,
            center_tab_widget=self._center_tab_widget,
            get_scene=lambda: self.scene,
            get_graphics=self._get_graphics,
            get_window_backend=self._get_window_backend,
            get_render_engine=self._get_render_engine,
            on_request_update=self._request_viewport_update,
        )

        # Add the editor display (main viewport)
        if self.viewport_controller is not None:
            editor_display = self.viewport_controller.display
            if editor_display is not None:
                self._rendering_controller.add_display(editor_display, "Editor")

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

        if path.suffix == ".material":
            # Материал — открываем в инспекторе материалов
            self.show_material_inspector_for_file(str(path))
        elif path.suffix == ".pipeline":
            # Пайплайн — открываем в инспекторе пайплайнов
            self._inspector_controller.show_pipeline_inspector_for_file(str(path))

    def _on_project_file_double_clicked(self, file_path) -> None:
        """Обработчик двойного клика на файл в Project Browser."""
        from pathlib import Path
        path = Path(file_path)

        # Обработка разных типов файлов
        if path.suffix == ".scene":
            # Это файл сцены — загружаем
            self._load_scene_from_file(str(path))

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

        # Сканируем ресурсы нового проекта
        self._scan_project_resources()

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
        Создаёт панель инструментов над viewport с кнопкой Play в центре.
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

        # Вставляем toolbar в editorViewportLayout (первым элементом, перед viewport)
        viewport_layout = self.editorViewportTab.layout()
        viewport_layout.insertWidget(0, toolbar)

    # ----------- связи с контроллерами -----------

    def _request_viewport_update(self) -> None:
        if self.viewport_controller is not None:
            self.viewport_controller.request_update()

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
        Колбэк от ViewportController при выборе сущности кликом в вьюпорте.
        Синхронизируем выделение в дереве и инспекторе.
        """
        if self.selection_manager is not None:
            self.selection_manager.select(ent)

        if self.scene_tree_controller is not None and ent is not None:
            self.scene_tree_controller.select_object(ent)

        self.show_entity_inspector(ent)

    def _on_hover_entity_from_viewport(self, ent: Entity | None) -> None:
        """
        Колбэк от ViewportController при изменении подсвеченной (hover) сущности.
        """
        if self.selection_manager is not None:
            self.selection_manager.hover(ent)

    # ----------- Qt eventFilter -----------

    def eventFilter(self, obj, event):
        """
        Перехватываем нажатие Delete в виджете вьюпорта и удаляем выделенную сущность.
        """
        if (
            self.viewport_controller is not None
            and obj is self.viewport_controller.gl_widget
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Delete
        ):
            ent = self.selection_manager.selected if self.selection_manager else None
            if isinstance(ent, Entity):
                # удаление через команду, дерево и вьюпорт обновятся через undo-стек
                cmd = DeleteEntityCommand(self.scene, ent)
                self.push_undo_command(cmd, merge=False)
            return True

        return super().eventFilter(obj, event)

    def _resync_inspector_from_selection(self):
        """Resync inspector based on current tree selection."""
        self._inspector_controller.resync_from_tree_selection(self.sceneTree, self.scene)

    # ----------- SelectionManager колбэки -----------

    def _get_pick_id_for_entity(self, entity: Entity | None) -> int:
        """Получает pick ID для сущности через viewport_controller."""
        if self.viewport_controller is not None:
            return self.viewport_controller.get_pick_id_for_entity(entity)
        return 0

    def _on_selection_changed_internal(self, entity: Entity | None) -> None:
        """Колбэк от SelectionManager при изменении выделения."""
        # Обновляем viewport
        if self.viewport_controller is not None and self.selection_manager is not None:
            self.viewport_controller.selected_entity_id = self.selection_manager.selected_entity_id

        # Обновляем гизмо
        if self.gizmo_controller is not None:
            self.gizmo_controller.set_target(entity)

        self._request_viewport_update()

    def _on_hover_changed_internal(self, entity: Entity | None) -> None:
        """Колбэк от SelectionManager при изменении hover."""
        if self.viewport_controller is not None and self.selection_manager is not None:
            self.viewport_controller.hover_entity_id = self.selection_manager.hover_entity_id

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

        # Update viewport
        if self.viewport_controller is not None:
            self.viewport_controller.set_scene(new_scene)
            self.viewport_controller.set_camera(self._camera_manager.camera)
            self.viewport_controller.selected_entity_id = 0
            self.viewport_controller.hover_entity_id = 0

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
            if self.viewport_controller is not None:
                self.viewport_controller.set_world_mode("game")

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
            if self.viewport_controller is not None:
                self.viewport_controller.set_world_mode("editor")

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

    def _update_window_title(self) -> None:
        """Обновляет заголовок окна с учётом проекта, сцены и режима."""
        from pathlib import Path

        parts = ["Termin Editor"]

        # Добавляем имя проекта
        if self._project_name is not None:
            parts.append(f"- {self._project_name}")

        # Добавляем имя сцены
        if self.world_persistence is not None:
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

        Handles rendering.
        Note: Game mode updates are handled by GameModeController's QTimer.
        """
        # Always render - SDL window needs continuous updates
        if self.viewport_controller is not None:
            self.viewport_controller.render()
