# ===== termin/editor/editor_window.py =====
import os
from PyQt6 import uic
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTreeView, QLabel, QMenu, QInputDialog, QMessageBox, QFileDialog
from PyQt6.QtWidgets import QStatusBar
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

from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.render.components.mesh_renderer import MeshRenderer
from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3
from termin.editor.editor_inspector import EntityInspector
from termin.editor.scene_inspector import SceneInspector
from termin.visualization.core.resources import ResourceManager
from termin.geombase.pose3 import Pose3


class EditorWindow(QMainWindow):
    undo_stack_changed = pyqtSignal()

    def __init__(self, world, initial_scene):
        super().__init__()
        self.undo_stack = UndoStack()
        self._action_undo = None
        self._action_redo = None
        self._action_play = None
        self._undo_stack_viewer = None
        self._framegraph_debugger = None
        self._scene_inspector_dialog = None
        self._status_bar_label: QLabel | None = None
        self._fps_smooth: float | None = None
        self._fps_alpha: float = 0.1  # экспоненциальное сглаживание: f_new = f_prev*(1-α) + f_curr*α

        self.world = world

        # --- ресурс-менеджер редактора ---
        self.resource_manager = ResourceManager.instance()

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

        ui_path = os.path.join(os.path.dirname(__file__), "editor.ui")
        uic.loadUi(ui_path, self)

        self._init_status_bar()

        self._setup_menu_bar()

        self._scan_builtin_components()
        self._init_resources_from_scene()

        # --- UI из .ui ---
        self.sceneTree: QTreeView = self.findChild(QTreeView, "sceneTree")

        self.sceneTree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        self.viewportContainer: QWidget = self.findChild(QWidget, "viewportContainer")
        self.inspectorContainer: QWidget = self.findChild(QWidget, "inspectorContainer")

        from PyQt6.QtWidgets import QSplitter
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

    @property
    def scene(self):
        """Текущая сцена. Всегда получаем из WorldPersistence."""
        return self.world_persistence.scene

    # ----------- undo / redo -----------

    def _setup_menu_bar(self) -> None:
        """
        Создаёт верхнее меню редактора и вешает действия Undo/Redo с шорткатами.
        Также добавляет отладочное меню Debug с просмотром undo/redo стека.
        """
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        edit_menu = menu_bar.addMenu("Edit")
        scene_menu = menu_bar.addMenu("Scene")
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

        # Scene menu
        scene_properties_action = scene_menu.addAction("Scene Properties...")
        scene_properties_action.triggered.connect(self._show_scene_properties)

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
    def _show_scene_properties(self) -> None:
        """
        Открывает диалог редактирования свойств сцены (ambient, background и т.п.).
        """
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox

        if self._scene_inspector_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Scene Properties")
            dialog.setMinimumWidth(300)

            layout = QVBoxLayout(dialog)

            inspector = SceneInspector(dialog)
            inspector.set_scene(self.scene)
            inspector.set_undo_command_handler(self.push_undo_command)
            inspector.scene_changed.connect(self._request_viewport_update)

            layout.addWidget(inspector)

            button_box = QDialogButtonBox(QDialogButtonBox.Close)
            button_box.rejected.connect(dialog.close)
            layout.addWidget(button_box)

            dialog._inspector = inspector
            self._scene_inspector_dialog = dialog

        # Обновляем значения при каждом открытии
        self._scene_inspector_dialog._inspector.set_scene(self.scene)

        self._scene_inspector_dialog.show()
        self._scene_inspector_dialog.raise_()
        self._scene_inspector_dialog.activateWindow()

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

    def _get_editor_camera_data(self) -> dict | None:
        """
        Возвращает данные камеры редактора для сериализации.
        """
        if self.camera is None or self.camera.entity is None:
            return None

        orbit_ctrl = self.camera.entity.get_component(OrbitCameraController)
        if orbit_ctrl is None:
            return None

        return {
            "target": list(orbit_ctrl.target),
            "radius": float(orbit_ctrl.radius),
            "azimuth": float(orbit_ctrl.azimuth),
            "elevation": float(orbit_ctrl.elevation),
        }

    def _set_editor_camera_data(self, data: dict) -> None:
        """
        Применяет сохранённые данные к камере редактора.
        """
        if self.camera is None or self.camera.entity is None:
            return

        orbit_ctrl = self.camera.entity.get_component(OrbitCameraController)
        if orbit_ctrl is None:
            return

        import numpy as np

        if "target" in data:
            orbit_ctrl.target = np.array(data["target"], dtype=np.float32)
        if "radius" in data:
            orbit_ctrl.radius = float(data["radius"])
        if "azimuth" in data:
            orbit_ctrl.azimuth = float(data["azimuth"])
        if "elevation" in data:
            orbit_ctrl.elevation = float(data["elevation"])

        # Обновляем позу камеры
        orbit_ctrl._update_pose()

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

    def _init_status_bar(self) -> None:
        """
        Создаёт полосу статуса внизу окна. FPS будем писать сюда в игровом режиме.
        """
        status_bar: QStatusBar = self.statusBar()
        status_bar.setSizeGripEnabled(False)

        label = QLabel("Editor mode")
        status_bar.addPermanentWidget(label, 1)
        self._status_bar_label = label

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

        if self.inspector is not None:
            self.inspector.set_target(ent)

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
            self.viewport_window is not None
            and obj is self.viewport_window.handle.widget
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
        """Открывает диалог выбора .shader файла, парсит его и добавляет в ResourceManager."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Material",
            "",
            "Shader Files (*.shader);;All Files (*)",
        )
        if not file_path:
            return

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
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Components",
            "",
            "Python Files (*.py);;All Files (*)",
        )
        if not path:
            return

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

    # ----------- WorldPersistence колбэки -----------

    def _on_scene_changed(self, new_scene) -> None:
        """
        Колбэк от WorldPersistence при смене сцены.
        Вызывается при reset(), load(), restore_state().
        Пересоздаёт все editor entities в новой сцене.
        """
        # Очищаем undo-стек
        self.undo_stack.clear()
        self._update_undo_redo_actions()
        self.undo_stack_changed.emit()

        # Сбрасываем выделение
        if self.selection_manager is not None:
            self.selection_manager.clear()

        # Пересоздаём редакторские сущности в НОВОЙ сцене
        self.editor_entities = None
        self._ensure_editor_entities_root()
        self._ensure_editor_camera()

        # Пересоздаём гизмо в новой сцене
        if self.gizmo_controller is not None:
            self.gizmo_controller.recreate_gizmo(new_scene, self.editor_entities)

        # Обновляем viewport - теперь он работает с новой сценой
        if self.viewport_controller is not None:
            self.viewport_controller.set_scene(new_scene)
            self.viewport_controller.set_camera(self.camera)
            self.viewport_controller.selected_entity_id = 0
            self.viewport_controller.hover_entity_id = 0

        # Обновляем дерево сцены
        if self.scene_tree_controller is not None:
            self.scene_tree_controller._scene = new_scene
            self.scene_tree_controller.rebuild()

        # Сбрасываем инспектор
        if self.inspector is not None:
            self.inspector.set_target(None)

        self._request_viewport_update()

    # ----------- сохранение/загрузка мира -----------

    def _reset_world(self) -> None:
        """Полная очистка мира и пересоздание редакторских сущностей."""
        if self.world_persistence is not None:
            self.world_persistence.reset()

    def _new_world(self) -> None:
        """Создаёт новый пустой мир - полный перезапуск."""
        reply = QMessageBox.question(
            self,
            "New World",
            "Create a new empty world?\n\nThis will remove all entities and resources.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self._reset_world()

        # Обновляем UI
        if self.scene_tree_controller is not None:
            self.scene_tree_controller.rebuild()
        self._request_viewport_update()

    def _save_world(self) -> None:
        """Сохраняет текущий мир в JSON файл."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save World",
            "world.world.json",
            "World Files (*.world.json);;JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        # Добавляем расширение если не указано
        if not file_path.endswith(".json"):
            file_path += ".world.json"

        try:
            if self.world_persistence is None:
                raise RuntimeError("WorldPersistence not initialized")

            stats = self.world_persistence.save(file_path)
            QMessageBox.information(
                self,
                "World Saved",
                f"World saved successfully to:\n{file_path}\n\n"
                f"Entities: {stats['entities']}\n"
                f"Materials: {stats['materials']}\n"
                f"Meshes: {stats['meshes']}",
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
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load World",
            "",
            "World Files (*.world.json);;JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        try:
            if self.world_persistence is None:
                raise RuntimeError("WorldPersistence not initialized")

            # load() создаёт новую сцену и вызывает on_scene_changed
            stats = self.world_persistence.load(file_path)

            QMessageBox.information(
                self,
                "World Loaded",
                f"World loaded successfully from:\n{file_path}\n\n"
                f"Entities loaded: {stats['loaded_entities']}\n"
                f"Materials: {stats['materials']}\n"
                f"Meshes: {stats['meshes']}",
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
        if self.game_mode_controller is not None:
            self.game_mode_controller.toggle()

    def _on_game_mode_changed(self, is_playing: bool) -> None:
        """Колбэк от GameModeController при изменении режима."""
        if is_playing:
            # Входим в игровой режим
            if self.viewport_window is not None:
                self.viewport_window.set_world_mode("game")

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
            if self.viewport_window is not None:
                self.viewport_window.set_world_mode("editor")

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
        """Обновляет состояние UI элементов в зависимости от режима."""
        is_playing = self.game_mode_controller.is_playing if self.game_mode_controller else False

        if self._action_play is not None:
            if is_playing:
                self._action_play.setText("Stop")
                self._action_play.setShortcut("F5")
            else:
                self._action_play.setText("Play")
                self._action_play.setShortcut("F5")

        # Обновляем заголовок окна
        base_title = "Termin Editor"
        if is_playing:
            self.setWindowTitle(f"{base_title} [PLAYING]")
        else:
            self.setWindowTitle(base_title)

        self._update_status_bar()

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
