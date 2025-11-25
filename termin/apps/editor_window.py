# ===== termin/apps/editor_window.py =====
import os
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTreeView, QLabel, QMenu
from PyQt5.QtCore import Qt, QPoint

from termin.visualization.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.components.mesh_renderer import MeshRenderer
from termin.visualization.entity import Entity
from termin.kinematic.transform import Transform3
from editor_tree import SceneTreeModel
from editor_inspector import EntityInspector
from termin.visualization.picking import id_to_rgb
from termin.visualization.resources import ResourceManager
from termin.geombase.pose3 import Pose3
from termin.visualization.gizmos.gizmo_axes import GizmoEntity, GizmoMoveController


class EditorWindow(QMainWindow):
    def __init__(self, world, scene):
        super().__init__()
        self.selected_entity_id = None

        ui_path = os.path.join(os.path.dirname(__file__), "editor.ui")
        uic.loadUi(ui_path, self)

        self.world = world
        self.scene = scene

        # будут созданы ниже
        self.camera = None
        self.editor_entities = None
        self.gizmo: GizmoEntity | None = None

        # --- ресурс-менеджер редактора ---
        self.resource_manager = ResourceManager()
        self._init_resources_from_scene()


        # --- UI из .ui ---
        self.sceneTree: QTreeView = self.findChild(QTreeView, "sceneTree")

        self.sceneTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sceneTree.customContextMenuRequested.connect(self.on_tree_context_menu)

        self.viewportContainer: QWidget = self.findChild(QWidget, "viewportContainer")
        self.inspectorContainer: QWidget = self.findChild(QWidget, "inspectorContainer")

        from PyQt5.QtWidgets import QSplitter
        self.topSplitter: QSplitter = self.findChild(QSplitter, "topSplitter")
        self.verticalSplitter: QSplitter = self.findChild(QSplitter, "verticalSplitter")

        self._fix_splitters()


        # --- инспектор ---
        self.inspector = EntityInspector(self.resource_manager, self.inspectorContainer)
        self._init_inspector_widget()

        component_library = [
            ("PerspectiveCameraComponent", PerspectiveCameraComponent),
            ("OrbitCameraController",      OrbitCameraController),
            ("MeshRenderer",               MeshRenderer),
        ]
        self.inspector.set_component_library(component_library)

        # на всякий случай — зарегистрируем компоненты и в ресурс-менеджере
        for label, cls in component_library:
            self.resource_manager.register_component(label, cls)

        self.inspector.transform_changed.connect(self._on_inspector_transform_changed)
        self.inspector.component_changed.connect(self._on_inspector_component_changed)


        # --- создаём редакторские сущности (root, камера, гизмо) ---
        self._ensure_editor_entities_root()
        self._ensure_editor_camera()
        self._ensure_gizmo()

        # --- дерево сцены ---
        self._tree_model = SceneTreeModel(scene)
        self._setup_tree_model()

        self.sceneTree.setModel(self._tree_model)
        self.sceneTree.expandAll()
        self.sceneTree.clicked.connect(self.on_tree_click)

        # --- viewport ---
        self._init_viewport()


    def _ensure_editor_entities_root(self):
        """
        Ищем/создаём корневую сущность для редакторских вещей:
        камера, гизмо и т.п.
        """
        for ent in self.scene.entities:
            if getattr(ent, "name", "") == "EditorEntities":
                self.editor_entities = ent
                return

        editor_entities = Entity(name="EditorEntities")
        self.scene.add(editor_entities)
        self.editor_entities = editor_entities

    def _ensure_editor_camera(self):
        """
        Создаём редакторскую камеру и вешаем её под EditorEntities (если он есть).
        Никакого поиска по сцене – у редактора всегда своя камера.
        """
        camera_entity = Entity(name="camera", pose=Pose3.identity())
        camera = PerspectiveCameraComponent()
        camera_entity.add_component(camera)
        camera_entity.add_component(OrbitCameraController())

        self.editor_entities.transform.link(camera_entity.transform)
        self.scene.add(camera_entity)
        self.camera = camera

    def _ensure_gizmo(self):
        """
        Ищем гизмо в сцене, если нет – создаём.
        """
        for ent in self.scene.entities:
            if isinstance(ent, GizmoEntity) or getattr(ent, "name", "") == "gizmo":
                self.gizmo = ent
                return

        gizmo = GizmoEntity(size=1.5)
        gizmo_controller = GizmoMoveController(gizmo, self.scene)
        gizmo.add_component(gizmo_controller)

        if self.editor_entities is not None:
            self.editor_entities.transform.add_child(gizmo.transform)

        self.scene.add(gizmo)
        self.gizmo = gizmo



    # ----------- ресурсы из сцены -----------

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
            mesh = getattr(mr, "mesh", None)
            if mesh is not None:
                existing_mesh_name = self.resource_manager.find_mesh_name(mesh)
                if existing_mesh_name is None:
                    name = getattr(mesh, "name", None)
                    if not name:
                        base = f"{ent.name}_mesh" if getattr(ent, "name", None) else "Mesh"
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

            name = getattr(mat, "name", None)
            if not name:
                base = f"{ent.name}_mat" if getattr(ent, "name", None) else "Material"
                name = base
                i = 1
                while name in self.resource_manager.materials:
                    i += 1
                    name = f"{base}_{i}"
                mat.name = name

            self.resource_manager.register_material(name, mat)


    # ----------- реакции инспектора -----------

    def _on_inspector_transform_changed(self):
        if self.viewport_window is not None:
            self.viewport_window._request_update()

    def _on_inspector_component_changed(self):
        if self.viewport_window is not None:
            self.viewport_window._request_update()

    # ----------- контекстное меню дерева -----------

    def on_tree_context_menu(self, pos: QPoint):
        index = self.sceneTree.indexAt(pos)
        node = index.internalPointer() if index.isValid() else None
        target_obj = node.obj if node is not None else None

        menu = QMenu(self)
        action_add = menu.addAction("Add entity")

        action_delete = None
        if isinstance(target_obj, Entity):
            action_delete = menu.addAction("Delete entity")

        global_pos = self.sceneTree.viewport().mapToGlobal(pos)
        action = menu.exec_(global_pos)
        if action == action_add:
            self._create_entity_from_context(target_obj)
        elif action == action_delete:
            self._delete_entity_from_context(target_obj)

    def _delete_entity_from_context(self, ent: Entity):
        if not isinstance(ent, Entity):
            return

        parent_tf = getattr(ent.transform, "parent", None)
        parent_ent = getattr(parent_tf, "entity", None) if parent_tf is not None else None
        if not isinstance(parent_ent, Entity):
            parent_ent = None

        if self.inspector is not None:
            self.inspector.set_target(None)

        self.on_selection_changed(None)

        if hasattr(self.scene, "remove"):
            self.scene.remove(ent)
        else:
            try:
                self.scene.entities.remove(ent)
                ent.on_removed()
            except ValueError:
                pass

        self._rebuild_tree_model(select_obj=parent_ent)

        if self.viewport_window is not None:
            self.viewport_window._request_update()

    def _setup_tree_model(self):
        self.sceneTree.setModel(self._tree_model)
        self.sceneTree.expandAll()
        self.sceneTree.clicked.connect(self.on_tree_click)

        sel_model = self.sceneTree.selectionModel()
        if sel_model is not None:
            sel_model.currentChanged.connect(self.on_tree_current_changed)

    def _rebuild_tree_model(self, select_obj=None):
        self._tree_model = SceneTreeModel(self.scene)
        self._setup_tree_model()
        if select_obj is not None:
            self._select_object_in_tree(select_obj)

    def on_tree_current_changed(self, current, _previous):
        if not current.isValid():
            return
        self.on_tree_click(current)

    def _create_entity_from_context(self, target_obj):
        parent_transform = None
        if isinstance(target_obj, Entity):
            parent_transform = target_obj.transform
        elif isinstance(target_obj, Transform3):
            parent_transform = target_obj

        existing = {e.name for e in self.scene.entities}
        base = "entity"
        i = 1
        while f"{base}{i}" in existing:
            i += 1
        name = f"{base}{i}"

        ent = Entity(pose=Pose3.identity(), name=name)

        if parent_transform is not None:
            ent.transform.set_parent(parent_transform)

        self.scene.add(ent)
        self._rebuild_tree_model(select_obj=ent)

        if self.viewport_window is not None:
            self.viewport_window._request_update()

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

    # ----------- синхронизация с пиками -----------

    def mouse_button_clicked(self, button_type, x, y, viewport):
        from termin.visualization.backends.base import MouseButton
        if button_type == MouseButton.LEFT:
            self._pending_pick = (x, y, viewport)

    def _after_render(self, window):
        if self._pending_pick is None:
            return

        print("PENDING PICK HANDLER")  # --- DEBUG ---
        x, y, viewport = self._pending_pick
        self._pending_pick = None

        picked_ent = window.pick_entity_at(x, y, viewport)
        if picked_ent is not None:
            self.on_selection_changed(picked_ent)
            self._select_object_in_tree(picked_ent)
            self.inspector.set_target(picked_ent)
        else:
            self.on_selection_changed(None)
            self.inspector.set_target(None)

    def _select_object_in_tree(self, obj):
        model: SceneTreeModel = self.sceneTree.model()
        idx = model.index_for_object(obj)
        if not idx.isValid():
            return
        self.sceneTree.setCurrentIndex(idx)
        self.sceneTree.scrollTo(idx)

    def _init_viewport(self):
        self._pending_pick = None
        layout = self.viewportContainer.layout()

        self.viewport_window = self.world.create_window(
            width=900,
            height=800,
            title="viewport",
            parent=self.viewportContainer
        )
        # здесь self.camera уже создана в _ensure_editor_camera
        self.viewport = self.viewport_window.add_viewport(self.scene, self.camera)
        self.viewport_window.set_world_mode("editor")

        self.viewport_window.on_mouse_button_event = self.mouse_button_clicked
        self.viewport_window.after_render_handler = self._after_render

        gl_widget = self.viewport_window.handle.widget
        gl_widget.setFocusPolicy(Qt.StrongFocus)
        gl_widget.setMinimumSize(50, 50)

        layout.addWidget(gl_widget)

        self.viewport.set_render_pipeline(self.make_pipeline())

    def on_tree_click(self, index):
        node = index.internalPointer()
        obj = node.obj

        self.inspector.set_target(obj)

        if isinstance(obj, Entity):
            ent = obj
        elif isinstance(obj, Transform3):
            ent = next((e for e in self.scene.entities if e.transform is obj), None)
        else:
            ent = None

        self.on_selection_changed(ent)

        if self.viewport_window is not None:
            self.viewport_window._request_update()

    def on_selection_changed(self, selected_ent):
        if selected_ent is not None and selected_ent.selectable is False:
            # Мы пикнули что-то невыделяемое. Скорее всего гизмо.
            return
        
        self.selected_entity_id = self.viewport_window._get_pick_id_for_entity(selected_ent) if selected_ent is not None else 0
        self.gizmo.find_component(GizmoMoveController).set_target(selected_ent)

    def make_pipeline(self) -> list["FramePass"]:
        from termin.visualization.framegraph import ColorPass, IdPass, CanvasPass, PresentToScreenPass
        from termin.visualization.postprocess import PostProcessPass
        from termin.visualization.posteffects.highlight import HighlightEffect

        postprocess = PostProcessPass(
            effects=[],
            input_res="color",
            output_res="color_pp",
            pass_name="PostFX",
        )

        passes: list["FramePass"] = [
            ColorPass(input_res="empty", output_res="color", pass_name="Color"),
            IdPass(input_res="empty_id", output_res="id", pass_name="Id"),
            postprocess,
            CanvasPass(
                src="color_pp",
                dst="color+ui",
                pass_name="Canvas",
            ),
            PresentToScreenPass(
                input_res="color+ui",
                pass_name="Present",
            )
        ]

        postprocess.add_effect(HighlightEffect(lambda: self.selected_entity_id))

        return passes
