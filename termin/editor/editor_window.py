# ===== termin/editor/editor_window.py =====
import os
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTreeView, QLabel, QMenu, QAction, QInputDialog, QMessageBox
from PyQt5.QtCore import Qt, QPoint, QEvent, pyqtSignal, QTimer, QElapsedTimer
from termin.editor.undo_stack import UndoStack, UndoCommand
from termin.editor.editor_commands import AddEntityCommand, DeleteEntityCommand, RenameEntityCommand
from termin.editor.scene_tree_controller import SceneTreeController
from termin.editor.viewport_controller import ViewportController
from termin.editor.gizmo import GizmoController

from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3
from termin.editor.editor_tree import SceneTreeModel
from termin.editor.editor_inspector import EntityInspector
from termin.visualization.core.picking import id_to_rgb
from termin.visualization.core.resources import ResourceManager
from termin.geombase.pose3 import Pose3
from termin.editor.gizmo import GizmoEntity, GizmoMoveController
from termin.visualization.platform.backends.base import Action, MouseButton


class EditorWindow(QMainWindow):
    undo_stack_changed = pyqtSignal()
    def __init__(self, world, scene):
        super().__init__()
        self.selected_entity_id = 0
        self.hover_entity_id = 0
        self.undo_stack = UndoStack()
        self._action_undo = None
        self._action_redo = None
        self._action_play = None
        self._undo_stack_viewer = None
        self._framegraph_debugger = None

        # Game mode state
        self._game_mode = False
        self._saved_scene_state: dict | None = None

        # Game loop timer (60 FPS)
        self._game_timer = QTimer(self)
        self._game_timer.timeout.connect(self._game_tick)
        self._elapsed_timer = QElapsedTimer()

        self.world = world
        self.scene = scene

        # контроллеры создадим чуть позже
        self.scene_tree_controller: SceneTreeController | None = None
        self.viewport_controller: ViewportController | None = None
        self.gizmo_controller: GizmoController | None = None

        ui_path = os.path.join(os.path.dirname(__file__), "editor.ui")
        uic.loadUi(ui_path, self)

        self._setup_menu_bar()

        # --- ресурс-менеджер редактора ---
        self.resource_manager = ResourceManager.instance()
        self._scan_builtin_components()
        self._init_resources_from_scene()

        # --- UI из .ui ---
        self.sceneTree: QTreeView = self.findChild(QTreeView, "sceneTree")

        self.sceneTree.setContextMenuPolicy(Qt.CustomContextMenu)

        self.viewportContainer: QWidget = self.findChild(QWidget, "viewportContainer")
        self.inspectorContainer: QWidget = self.findChild(QWidget, "inspectorContainer")

        from PyQt5.QtWidgets import QSplitter
        self.topSplitter: QSplitter = self.findChild(QSplitter, "topSplitter")
        self.verticalSplitter: QSplitter = self.findChild(QSplitter, "verticalSplitter")

        self._fix_splitters()

        # --- инспектор ---
        self.inspector = EntityInspector(self.resource_manager, self.inspectorContainer)
        self._init_inspector_widget()
        self.inspector.transform_changed.connect(self._on_inspector_transform_changed)
        self.inspector.component_changed.connect(self._on_inspector_component_changed)
        self.inspector.set_undo_command_handler(self.push_undo_command)

        # --- создаём редакторские сущности (root, камера) ---
        self.editor_entities = None
        self.camera = None
        self._ensure_editor_entities_root()
        self._ensure_editor_camera()

        # --- гизмо-контроллер ---
        self.gizmo_controller = GizmoController(
            scene=self.scene,
            editor_entities=self.editor_entities,
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

        # --- viewport ---
        self.viewport_window = None
        self.viewport = None
        self.viewport_controller = ViewportController(
            container=self.viewportContainer,
            world=self.world,
            scene=self.scene,
            camera=self.camera,
            gizmo_controller=self.gizmo_controller,
            on_entity_picked=self._on_entity_picked_from_viewport,
            on_hover_entity=self._on_hover_entity_from_viewport,
        )

        self.viewport_window = self.viewport_controller.window
        self.viewport = self.viewport_controller.viewport  # viewport из контроллера

        gl_widget = self.viewport_controller.gl_widget
        gl_widget.installEventFilter(self)

        self._selected_entity: Entity | None = None

    # ----------- undo / redo -----------

    def _setup_menu_bar(self) -> None:
        """
        Создаёт верхнее меню редактора и вешает действия Undo/Redo с шорткатами.
        Также добавляет отладочное меню Debug с просмотром undo/redo стека.
        """
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        edit_menu = menu_bar.addMenu("Edit")
        game_menu = menu_bar.addMenu("Game")
        debug_menu = menu_bar.addMenu("Debug")

        new_world_action = file_menu.addAction("New World")
        new_world_action.setShortcut("Ctrl+N")
        new_world_action.triggered.connect(self._new_world)

        file_menu.addSeparator()

        save_world_action = file_menu.addAction("Save World...")
        save_world_action.setShortcut("Ctrl+S")
        save_world_action.triggered.connect(self._save_world)

        load_world_action = file_menu.addAction("Load World...")
        load_world_action.setShortcut("Ctrl+O")
        load_world_action.triggered.connect(self._load_world)

        file_menu.addSeparator()

        load_material_action = file_menu.addAction("Load Material...")
        load_material_action.triggered.connect(self._load_material_from_file)

        load_components_action = file_menu.addAction("Load Components...")
        load_components_action.triggered.connect(self._load_components_from_file)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        self._action_undo = edit_menu.addAction("Undo")
        self._action_undo.setShortcut("Ctrl+Z")
        self._action_undo.triggered.connect(self.undo)

        self._action_redo = edit_menu.addAction("Redo")
        self._action_redo.setShortcut("Ctrl+Shift+Z")
        self._action_redo.triggered.connect(self.redo)

        # Game menu - одна кнопка Play/Stop
        self._action_play = game_menu.addAction("Play")
        self._action_play.setShortcut("F5")
        self._action_play.triggered.connect(self._toggle_game_mode)

        debug_action = debug_menu.addAction("Undo/Redo Stack...")
        tex_debug_action = debug_menu.addAction("Framegraph Texture Viewer...")
        tex_debug_action.triggered.connect(self._show_framegraph_debugger)
        debug_action.triggered.connect(self._show_undo_stack_viewer)

        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self) -> None:
        """
        Обновляет enabled-состояние пунктов меню Undo/Redo.
        """
        if self._action_undo is not None:
            self._action_undo.setEnabled(self.undo_stack.can_undo)
        if self._action_redo is not None:
            self._action_redo.setEnabled(self.undo_stack.can_redo)

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
    def _show_undo_stack_viewer(self) -> None:
        """
        Открывает отдельное окно с содержимым undo/redo стека.
        Окно живёт как независимый top-level, не блокируя основной интерфейс.
        """
        if self._undo_stack_viewer is None:
            from termin.editor.undo_stack_viewer import UndoStackViewer
            self._undo_stack_viewer = UndoStackViewer(
                self.undo_stack,
                self,
                stack_changed_signal=self.undo_stack_changed,
            )

        self._undo_stack_viewer.refresh()
        self._undo_stack_viewer.show()
        self._undo_stack_viewer.raise_()
        self._undo_stack_viewer.activateWindow()

    def _show_framegraph_debugger(self) -> None:
        """
        Открывает отдельное окно с просмотром текстуры из framegraph
        (по умолчанию ресурса 'debug', который заполняет BlitPass).
        """
        if self.viewport_window is None:
            return
        if self.viewport is None:
            return

        if self._framegraph_debugger is None:
            from termin.editor.framegraph_debugger import FramegraphDebugDialog

            graphics = self.viewport_window.graphics

            get_resources = None
            set_source = None
            get_paused = None
            set_paused = None
            get_passes_info = None
            get_pass_internal_symbols = None
            set_pass_internal_symbol = None
            get_debug_blit_pass = None
            get_fbos = lambda: {}

            if self.viewport_controller is not None:
                get_resources = self.viewport_controller.get_available_framegraph_resources
                set_source = self.viewport_controller.set_debug_source_resource
                get_paused = self.viewport_controller.get_debug_paused
                set_paused = self.viewport_controller.set_debug_paused
                get_passes_info = self.viewport_controller.get_passes_info
                get_pass_internal_symbols = self.viewport_controller.get_pass_internal_symbols
                set_pass_internal_symbol = self.viewport_controller.set_pass_internal_symbol
                get_debug_blit_pass = self.viewport_controller.get_debug_blit_pass
                get_fbos = lambda: self.viewport_controller.render_state.fbos

            self._framegraph_debugger = FramegraphDebugDialog(
                graphics=graphics,
                get_fbos=get_fbos,
                resource_name="debug",
                parent=self,
                get_available_resources=get_resources,
                set_source_resource=set_source,
                get_paused=get_paused,
                set_paused=set_paused,
                get_passes_info=get_passes_info,
                get_pass_internal_symbols=get_pass_internal_symbols,
                set_pass_internal_symbol=set_pass_internal_symbol,
                get_debug_blit_pass=get_debug_blit_pass,
            )

            if self.viewport_controller is not None:
                self.viewport_controller.set_framegraph_debugger(self._framegraph_debugger)

        # перед показом синхронизируем состояние и просим перерисовку
        self._framegraph_debugger.debugger_request_update()

        self._framegraph_debugger.show()
        self._framegraph_debugger.raise_()
        self._framegraph_debugger.activateWindow()

    # ----------- вспомогательные сущности редактора -----------

    def _ensure_editor_entities_root(self):
        """
        Ищем/создаём корневую сущность для редакторских вещей:
        камера, гизмо и т.п.
        """
        for ent in self.scene.entities:
            if ent.name == "EditorEntities":
                self.editor_entities = ent
                return

        editor_entities = Entity(name="EditorEntities", serializable=False)
        self.scene.add(editor_entities)
        self.editor_entities = editor_entities

    def _ensure_editor_camera(self):
        """
        Создаём редакторскую камеру и вешаем её под EditorEntities (если он есть).
        Никакого поиска по сцене – у редактора всегда своя камера.
        """
        camera_entity = Entity(name="camera", pose=Pose3.identity(), serializable=False)
        camera = PerspectiveCameraComponent()
        camera_entity.add_component(camera)
        camera_entity.add_component(OrbitCameraController())

        if self.editor_entities is not None:
            self.editor_entities.transform.link(camera_entity.transform)
        self.scene.add(camera_entity)
        self.camera = camera

    def _scan_builtin_components(self):
        """
        Сканирует встроенные модули компонентов и регистрирует их в ResourceManager.
        """
        builtin_modules = [
            "termin.visualization.components",
            # Можно добавить другие модули
        ]
        loaded = self.resource_manager.scan_components(builtin_modules)
        if loaded:
            print(f"Loaded components: {loaded}")

    def _init_resources_from_scene(self):
        """
        Складываем в ResourceManager материалы и меши, использованные в сцене.
        И даём им хоть какие-то имена, если их ещё нет.
        """
        for ent in self.scene.entities:
            mr = ent.get_component(MeshRenderer)
            if mr is None:
                continue

            # ------------ МЕШИ ------------
            mesh = mr.mesh
            if mesh is not None:
                existing_mesh_name = self.resource_manager.find_mesh_name(mesh)
                if existing_mesh_name is None:
                    name = mesh.name if hasattr(mesh, "name") else None
                    if not name:
                        base = f"{ent.name}_mesh" if ent.name else "Mesh"
                        name = base
                        i = 1
                        while name in self.resource_manager.meshes:
                            i += 1
                            name = f"{base}_{i}"
                    mesh.name = name
                    self.resource_manager.register_mesh(name, mesh)

            # ------------ МАТЕРИАЛЫ ------------
            mat = mr.material
            if mat is None:
                continue

            existing_name = self.resource_manager.find_material_name(mat)
            if existing_name is not None:
                continue

            name = mat.name
            if not name:
                base = f"{ent.name}_mat" if ent.name else "Material"
                name = base
                i = 1
                while name in self.resource_manager.materials:
                    i += 1
                    name = f"{base}_{i}"
                mat.name = name

            self.resource_manager.register_material(name, mat)

    # ----------- реакции инспектора -----------

    def _on_inspector_transform_changed(self):
        self._request_viewport_update()

    def _on_inspector_component_changed(self):
        self._request_viewport_update()

    # ----------- инициализация инспектора и сплиттеров -----------

    def _init_inspector_widget(self):
        parent = self.inspectorContainer
        layout = parent.layout()
        if layout is None:
            layout = QVBoxLayout(parent)
            parent.setLayout(layout)
        layout.addWidget(self.inspector)

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

    # ----------- связи с контроллерами -----------

    def _request_viewport_update(self) -> None:
        if self.viewport_controller is not None:
            self.viewport_controller.request_update()

    def _on_tree_object_selected(self, obj: object | None) -> None:
        """
        Колбэк от SceneTreeController при изменении выделения в дереве.
        """
        if self.inspector is not None:
            self.inspector.set_target(obj)

        if isinstance(obj, Entity):
            ent = obj
        elif isinstance(obj, Transform3):
            ent = next((e for e in self.scene.entities if e.transform is obj), None)
        else:
            ent = None

        self.on_selection_changed(ent)
        self._request_viewport_update()

    def _on_entity_picked_from_viewport(self, ent: Entity | None) -> None:
        """
        Колбэк от ViewportController при выборе сущности кликом в вьюпорте.
        Синхронизируем выделение в дереве и инспекторе.
        """
        if ent is not None and not ent.selectable:
            ent = None

        self.on_selection_changed(ent)

        if self.scene_tree_controller is not None and ent is not None:
            self.scene_tree_controller.select_object(ent)

        if self.inspector is not None:
            self.inspector.set_target(ent)

    def _on_hover_entity_from_viewport(self, ent: Entity | None) -> None:
        """
        Колбэк от ViewportController при изменении подсвеченной (hover) сущности.
        """
        self._update_hover_entity(ent)

    # ----------- Qt eventFilter -----------

    def eventFilter(self, obj, event):
        """
        Перехватываем нажатие Delete в виджете вьюпорта и удаляем выделенную сущность.
        """
        if (
            self.viewport_window is not None
            and obj is self.viewport_window.handle.widget
            and event.type() == QEvent.KeyPress
            and event.key() == Qt.Key_Delete
        ):
            ent = self._selected_entity
            if isinstance(ent, Entity):
                # удаление через команду, дерево и вьюпорт обновятся через undo-стек
                cmd = DeleteEntityCommand(self.scene, ent)
                self.push_undo_command(cmd, merge=False)
            return True

        return super().eventFilter(obj, event)

    def _resync_inspector_from_selection(self):
        """
        Обновляет инспектор в соответствии с текущим выделением в дереве.
        """
        index = self.sceneTree.currentIndex()
        if not index.isValid():
            if self.inspector is not None:
                self.inspector.set_target(None)
            return

        node = index.internalPointer()
        obj = node.obj if node is not None else None

        if self.inspector is not None:
            self.inspector.set_target(obj)

    # ----------- hover и выбор -----------

    def _update_hover_entity(self, ent: Entity | None):
        """
        Обновляем идентификатор hover-сущности для подсветки.
        """
        if ent is not None and not ent.selectable:
            ent = None

        if self.viewport_controller is not None:
            new_id = self.viewport_controller.get_pick_id_for_entity(ent)
        else:
            new_id = 0

        if new_id == self.hover_entity_id:
            return

        self.hover_entity_id = new_id
        if self.viewport_controller is not None:
            self.viewport_controller.hover_entity_id = new_id

        self._request_viewport_update()

    def on_selection_changed(self, selected_ent: Entity | None):
        """
        Обновляем текущее выделение, гизмо и id для подсветки.
        """
        if selected_ent is not None and not selected_ent.selectable:
            return

        self._selected_entity = selected_ent

        if self.viewport_controller is not None:
            new_id = self.viewport_controller.get_pick_id_for_entity(selected_ent)
        else:
            new_id = 0

        self.selected_entity_id = new_id
        if self.viewport_controller is not None:
            self.viewport_controller.selected_entity_id = new_id

        if self.gizmo_controller is not None:
            self.gizmo_controller.set_target(selected_ent)

        self._request_viewport_update()

    # ----------- загрузка материалов -----------

    def _load_material_from_file(self) -> None:
        """Открывает диалог выбора .shader файла, парсит его и добавляет в ResourceManager."""
        # QFileDialog зависает на директориях с .json/.js файлами - используем QInputDialog
        file_path, ok = QInputDialog.getText(
            self,
            "Load Material",
            "Enter shader file path:",
        )
        if not ok or not file_path:
            return
        file_path = os.path.expanduser(file_path)

        try:
            from termin.visualization.render.shader_parser import parse_shader_text, ShaderMultyPhaseProgramm
            from termin.visualization.core.material import Material

            with open(file_path, "r", encoding="utf-8") as f:
                shader_text = f.read()

            tree = parse_shader_text(shader_text)
            program = ShaderMultyPhaseProgramm.from_tree(tree)
            material = Material.from_parsed(program, source_path=file_path)

            # Определяем имя материала
            material_name = program.program
            if not material_name:
                # Используем имя файла без расширения
                material_name = os.path.splitext(os.path.basename(file_path))[0]

            # Проверяем уникальность имени
            base_name = material_name
            counter = 1
            while material_name in self.resource_manager.materials:
                counter += 1
                material_name = f"{base_name}_{counter}"

            material.name = material_name
            self.resource_manager.register_material(material_name, material)

            QMessageBox.information(
                self,
                "Material Loaded",
                f"Material '{material_name}' loaded successfully.\n"
                f"Phases: {len(material.phases)}\n"
                f"Phase marks: {', '.join(p.phase_mark for p in material.phases)}",
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Material",
                f"Failed to load material from:\n{file_path}\n\nError: {e}",
            )

    def _load_components_from_file(self) -> None:
        """Загружает компоненты из Python файла или директории."""
        path, ok = QInputDialog.getText(
            self,
            "Load Components",
            "Enter path to .py file or directory with components:",
        )
        if not ok or not path:
            return
        path = os.path.expanduser(path)

        try:
            loaded = self.resource_manager.scan_components([path])

            if loaded:
                QMessageBox.information(
                    self,
                    "Components Loaded",
                    f"Successfully loaded {len(loaded)} component(s):\n\n"
                    + "\n".join(f"• {name}" for name in loaded),
                )
            else:
                QMessageBox.warning(
                    self,
                    "No Components Found",
                    f"No new Component subclasses found in:\n{path}",
                )

        except Exception as e:
            import traceback
            QMessageBox.critical(
                self,
                "Error Loading Components",
                f"Failed to load components from:\n{path}\n\nError: {e}\n\n{traceback.format_exc()}",
            )

    # ----------- сохранение/загрузка мира -----------

    def _reset_world(self) -> None:
        """Полная очистка мира и пересоздание редакторских сущностей."""
        # Удаляем ВСЕ entities (включая редакторские)
        for entity in list(self.scene.entities):
            self.scene.remove(entity)

        # Очищаем ресурсы
        self.resource_manager.materials.clear()
        self.resource_manager.meshes.clear()
        self.resource_manager.textures.clear()

        # Очищаем undo-стек (начинаем с чистого листа)
        self.undo_stack.clear()
        self._update_undo_redo_actions()
        self.undo_stack_changed.emit()

        # Сбрасываем выделение
        self._selected_entity = None
        self.selected_entity_id = 0
        self.hover_entity_id = 0

        # Пересоздаём редакторские сущности
        self.editor_entities = None
        self._ensure_editor_entities_root()
        self._ensure_editor_camera()

        # Пересоздаём гизмо
        if self.gizmo_controller is not None:
            self.gizmo_controller.recreate_gizmo(self.scene, self.editor_entities)

        # Обновляем viewport камеру и сбрасываем выделение
        if self.viewport_controller is not None:
            self.viewport_controller.set_camera(self.camera)
            self.viewport_controller.selected_entity_id = 0
            self.viewport_controller.hover_entity_id = 0

        # Сбрасываем инспектор
        if self.inspector is not None:
            self.inspector.set_target(None)

    def _new_world(self) -> None:
        """Создаёт новый пустой мир - полный перезапуск."""
        reply = QMessageBox.question(
            self,
            "New World",
            "Create a new empty world?\n\nThis will remove all entities and resources.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        self._reset_world()

        # Обновляем UI
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.rebuild()
        self._request_viewport_update()

    def _save_world(self) -> None:
        """Сохраняет текущий мир в JSON файл."""
        # QFileDialog зависает на директориях с .json/.js файлами - используем QInputDialog
        file_path, ok = QInputDialog.getText(
            self,
            "Save World",
            "Enter file path:",
            text="~/world.world.json",
        )
        if not ok or not file_path:
            return
        file_path = os.path.expanduser(file_path)

        # Добавляем расширение если не указано
        if not file_path.endswith(".json"):
            file_path += ".world.json"

        try:
            import json
            import tempfile
            import numpy as np

            # Конвертер numpy типов в Python типы
            def numpy_encoder(obj):
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                if isinstance(obj, np.floating):
                    return float(obj)
                if isinstance(obj, np.integer):
                    return int(obj)
                raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

            data = {
                "version": "1.0",
                "resources": self.resource_manager.serialize(),
                "scenes": [self.scene.serialize()],
            }

            # Сериализуем в строку с конвертером numpy типов
            json_str = json.dumps(data, indent=2, ensure_ascii=False, default=numpy_encoder)

            # Атомарная запись: сначала во временный файл, потом переименование
            dir_path = os.path.dirname(file_path) or "."
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".tmp",
                dir=dir_path,
                delete=False
            ) as f:
                f.write(json_str)
                temp_path = f.name

            # Переименование атомарно на POSIX системах
            os.replace(temp_path, file_path)

            root_count = sum(1 for e in self.scene.entities if e.transform.parent is None)
            QMessageBox.information(
                self,
                "World Saved",
                f"World saved successfully to:\n{file_path}\n\n"
                f"Entities: {root_count}\n"
                f"Materials: {len(self.resource_manager.materials)}\n"
                f"Meshes: {len(self.resource_manager.meshes)}",
            )

        except Exception as e:
            import traceback
            QMessageBox.critical(
                self,
                "Error Saving World",
                f"Failed to save world to:\n{file_path}\n\nError: {e}\n\n{traceback.format_exc()}",
            )

    def _load_world(self) -> None:
        """Загружает мир из JSON файла."""
        # QFileDialog зависает на директориях с .json/.js файлами - используем QInputDialog
        file_path, ok = QInputDialog.getText(
            self,
            "Load World",
            "Enter file path:",
            text="~/world.world.json",
        )
        if not ok or not file_path:
            return
        file_path = os.path.expanduser(file_path)

        try:
            import json
            from termin.visualization.core.resources import ResourceManager

            # Сначала читаем файл, потом парсим
            with open(file_path, "r", encoding="utf-8") as f:
                json_str = f.read()
            data = json.loads(json_str)

            # Спрашиваем пользователя - очистить текущую сцену или добавить?
            reply = QMessageBox.question(
                self,
                "Load World",
                "Clear current scene before loading?\n\n"
                "Yes - Clear scene and load new world\n"
                "No - Add loaded entities to current scene",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes,
            )

            if reply == QMessageBox.Cancel:
                return

            clear_scene = (reply == QMessageBox.Yes)
            if clear_scene:
                # Полная очистка мира и пересоздание редакторских сущностей
                self._reset_world()

            # Восстанавливаем ресурсы
            resources_data = data.get("resources", {})
            if resources_data:
                restored_rm = ResourceManager.deserialize(resources_data)
                self.resource_manager.materials.update(restored_rm.materials)
                self.resource_manager.meshes.update(restored_rm.meshes)
                self.resource_manager.textures.update(restored_rm.textures)

            # Загружаем первую сцену
            loaded_count = 0
            scenes = data.get("scenes", [])
            if scenes:
                loaded_count = self.scene.load_from_data(
                    scenes[0],
                    context=None,
                    update_settings=clear_scene
                )

            if self.scene_tree_controller is not None:
                self.scene_tree_controller.rebuild()
            self._request_viewport_update()

            QMessageBox.information(
                self,
                "World Loaded",
                f"World loaded successfully from:\n{file_path}\n\n"
                f"Entities loaded: {loaded_count}\n"
                f"Materials: {len(self.resource_manager.materials)}\n"
                f"Meshes: {len(self.resource_manager.meshes)}",
            )

        except Exception as e:
            import traceback
            QMessageBox.critical(
                self,
                "Error Loading World",
                f"Failed to load world from:\n{file_path}\n\nError: {e}\n\n{traceback.format_exc()}",
            )

    # ----------- game mode -----------

    def _toggle_game_mode(self) -> None:
        """Переключает режим игры."""
        if self._game_mode:
            self._exit_game_mode()
        else:
            self._enter_game_mode()

    def _enter_game_mode(self) -> None:
        """Входит в игровой режим, сохраняя состояние сцены."""
        if self._game_mode:
            return

        import json
        import numpy as np

        # Конвертер numpy типов
        def numpy_encoder(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        # Сохраняем состояние сцены
        data = {
            "resources": self.resource_manager.serialize(),
            "scene": self.scene.serialize(),
        }
        # Сериализуем в JSON и обратно для глубокого копирования
        json_str = json.dumps(data, default=numpy_encoder)
        self._saved_scene_state = json.loads(json_str)

        # Переключаем режим
        self._game_mode = True
        if self.viewport_window is not None:
            self.viewport_window.set_world_mode("game")

        # Скрываем гизмо
        if self.gizmo_controller is not None:
            self.gizmo_controller.set_visible(False)

        # Сбрасываем выделение
        self.on_selection_changed(None)
        if self.inspector is not None:
            self.inspector.set_target(None)

        # Запускаем игровой цикл
        self._elapsed_timer.start()
        self._game_timer.start(16)  # ~60 FPS

        # Обновляем UI
        self._update_game_mode_ui()
        self._request_viewport_update()

    def _exit_game_mode(self) -> None:
        """Выходит из игрового режима, восстанавливая состояние сцены."""
        if not self._game_mode:
            return

        # Останавливаем игровой цикл
        self._game_timer.stop()

        if self._saved_scene_state is None:
            self._game_mode = False
            self._update_game_mode_ui()
            return

        # Удаляем все serializable entities (игровые объекты)
        for entity in list(self.scene.entities):
            if entity.serializable:
                self.scene.remove(entity)

        # Очищаем и восстанавливаем ресурсы
        self.resource_manager.materials.clear()
        self.resource_manager.meshes.clear()
        self.resource_manager.textures.clear()

        resources_data = self._saved_scene_state.get("resources", {})
        if resources_data:
            restored_rm = ResourceManager.deserialize(resources_data)
            self.resource_manager.materials.update(restored_rm.materials)
            self.resource_manager.meshes.update(restored_rm.meshes)
            self.resource_manager.textures.update(restored_rm.textures)

        # Восстанавливаем сцену
        scene_data = self._saved_scene_state.get("scene", {})
        if scene_data:
            self.scene.load_from_data(scene_data, context=None, update_settings=True)

        # Очищаем сохранённое состояние
        self._saved_scene_state = None

        # Переключаем режим
        self._game_mode = False
        if self.viewport_window is not None:
            self.viewport_window.set_world_mode("editor")

        # Показываем гизмо
        if self.gizmo_controller is not None:
            self.gizmo_controller.set_visible(True)

        # Обновляем UI
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.rebuild()
        self._update_game_mode_ui()
        self._request_viewport_update()

    def _update_game_mode_ui(self) -> None:
        """Обновляет состояние UI элементов в зависимости от режима."""
        if self._action_play is not None:
            if self._game_mode:
                self._action_play.setText("Stop")
                self._action_play.setShortcut("F5")
            else:
                self._action_play.setText("Play")
                self._action_play.setShortcut("F5")

        # Обновляем заголовок окна
        base_title = "Termin Editor"
        if self._game_mode:
            self.setWindowTitle(f"{base_title} [PLAYING]")
        else:
            self.setWindowTitle(base_title)

    def _game_tick(self) -> None:
        """Вызывается таймером в игровом режиме для обновления сцены."""
        if not self._game_mode:
            return

        # Вычисляем dt в секундах
        elapsed_ms = self._elapsed_timer.restart()
        dt = elapsed_ms / 1000.0

        # Обновляем сцену
        self.scene.update(dt)

        # Перерисовываем viewport
        self._request_viewport_update()
