# ===== termin/apps/editor_window.py =====
import os
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTreeView, QLabel
from PyQt5.QtCore import Qt

from termin.visualization.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.components.mesh_renderer import MeshRenderer
from termin.visualization.entity import Entity
from termin.kinematic.transform import Transform3
from editor_tree import SceneTreeModel
from editor_inspector import TransformInspector, EntityInspector, ComponentsPanel
from termin.visualization.picking import id_to_rgb

from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTreeView, QLabel, QMenu
from PyQt5.QtCore import Qt, QPoint
from termin.geombase.pose3 import Pose3


class EditorWindow(QMainWindow):
    def __init__(self, world, scene, camera):
        super().__init__()
        self.selected_entity_id = None

        ui_path = os.path.join(os.path.dirname(__file__), "editor.ui")
        uic.loadUi(ui_path, self)

        self.world = world
        self.scene = scene
        self.camera = camera

        # --- UI элементы из .ui ---
        self.sceneTree: QTreeView = self.findChild(QTreeView, "sceneTree")

        # контекстное меню
        self.sceneTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sceneTree.customContextMenuRequested.connect(self.on_tree_context_menu)

        self.viewportContainer: QWidget = self.findChild(QWidget, "viewportContainer")
        self.inspectorContainer: QWidget = self.findChild(QWidget, "inspectorContainer")

        from PyQt5.QtWidgets import QSplitter
        self.topSplitter: QSplitter = self.findChild(QSplitter, "topSplitter")
        self.verticalSplitter: QSplitter = self.findChild(QSplitter, "verticalSplitter")

        self._fix_splitters()

        # --- Scene tree ---
        self._tree_model = SceneTreeModel(scene)
        self._setup_tree_model()

        self.sceneTree.setModel(self._tree_model)
        self.sceneTree.expandAll()
        self.sceneTree.clicked.connect(self.on_tree_click)

        # --- Inspector widget ---
        self.inspector = EntityInspector(self.inspectorContainer)
        self._init_inspector_widget()

        component_library = [
            ("PerspectiveCameraComponent", PerspectiveCameraComponent),
            ("OrbitCameraController",      OrbitCameraController),
            ("MeshRenderer",               MeshRenderer),
        ]
        self.inspector.set_component_library(component_library)

        self.inspector.transform_changed.connect(self._on_inspector_transform_changed)
        self.inspector.component_changed.connect(self._on_inspector_component_changed)

        # --- Render viewport ---
        self._init_viewport()

    def _on_inspector_transform_changed(self):
        # трансформ поменялся — нужно перерисовать вьюпорт
        if self.viewport_window is not None:
            self.viewport_window._request_update()

    def _on_inspector_component_changed(self):
        # параметры компонента поменялись — тоже перерисуем
        if self.viewport_window is not None:
            self.viewport_window._request_update()


    def on_tree_context_menu(self, pos: QPoint):
        """
        Контекстное меню по правому клику в дереве.
        """
        index = self.sceneTree.indexAt(pos)
        node = index.internalPointer() if index.isValid() else None
        target_obj = node.obj if node is not None else None

        menu = QMenu(self)
        action_add = menu.addAction("Add entity")

        action_delete = None
        from termin.visualization.entity import Entity
        if isinstance(target_obj, Entity):
            action_delete = menu.addAction("Delete entity")

        global_pos = self.sceneTree.viewport().mapToGlobal(pos)
        action = menu.exec_(global_pos)
        if action == action_add:
            self._create_entity_from_context(target_obj)
        elif action == action_delete:
            self._delete_entity_from_context(target_obj)


    def _delete_entity_from_context(self, ent: Entity):
        """
        Удаляет Entity из сцены и обновляет дерево / инспектор / хайлайт.
        """
        if not isinstance(ent, Entity):
            return

        # запомним родителя, чтобы после удаления выделить его
        parent_tf = getattr(ent.transform, "parent", None)
        parent_ent = getattr(parent_tf, "entity", None) if parent_tf is not None else None
        if not isinstance(parent_ent, Entity):
            parent_ent = None

        # если удаляем то, что сейчас в инспекторе — почистим инспектор
        if self.inspector is not None:
            # инспектор держит Transform3
            t = getattr(self.inspector, "_transform", None)
            if t is ent.transform:
                self.inspector.set_target(None)

        # сброс хайлайта
        self.selected_entity_id = 0

        # убрать из сцены
        # предполагается, что у Scene есть метод remove
        if hasattr(self.scene, "remove"):
            self.scene.remove(ent)
        else:
            # fallback: если вдруг remove нет, можно поправить руками
            try:
                self.scene.entities.remove(ent)
                ent.on_removed()
            except ValueError:
                pass

        # пересобираем дерево, выделяем родителя (если был)
        self._rebuild_tree_model(select_obj=parent_ent)

        # перерисовка вьюпорта
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
        """
        Любая смена текущего элемента дерева (клавиатура, код, мышь)
        → ведём себя так же, как при клике мышью.
        """
        if not current.isValid():
            return
        self.on_tree_click(current)


    def _create_entity_from_context(self, target_obj):
        """
        Создаёт новый Entity.
        Если в контекст щёлкнули по Entity или Transform3 – делаем их родителем,
        иначе вешаем на корень сцены.
        """
        # --- решаем, к какому Transform3 цепляться ---
        parent_transform = None
        if isinstance(target_obj, Entity):
            parent_transform = target_obj.transform
        elif isinstance(target_obj, Transform3):
            parent_transform = target_obj

        # --- придумываем уникальное имя ---
        existing = {e.name for e in self.scene.entities}
        base = "entity"
        i = 1
        while f"{base}{i}" in existing:
            i += 1
        name = f"{base}{i}"

        # --- создаём сущность ---
        ent = Entity(pose=Pose3.identity(), name=name)

        # если есть родительский трансформ – привязываем
        if parent_transform is not None:
            ent.transform.set_parent(parent_transform)

        # добавляем в сцену
        self.scene.add(ent)

        # пересобираем дерево и выделяем нового
        self._rebuild_tree_model(select_obj=ent)

        # сразу обновим инспектор и рендер (через выделение всё само сделается,
        # но на всякий случай дёрнем перерисовку)
        if self.viewport_window is not None:
            self.viewport_window._request_update()


    def _on_inspector_transform_changed(self):
        # тут можно ещё мир/сцену обновить, если нужно
        if self.viewport_window is not None:
            # да, метод «приватный», но мы в том же модуле движка, можно :)
            self.viewport_window._request_update()

    def _init_inspector_widget(self):
        """
        Вкладываем TransformInspector в inspectorContainer (у которого уже есть лейаут из .ui).
        """
        from PyQt5.QtWidgets import QVBoxLayout

        parent = self.inspectorContainer
        layout = parent.layout()
        if layout is None:
            layout = QVBoxLayout(parent)
            parent.setLayout(layout)

        layout.addWidget(self.inspector)

    # ----------------------------------------------------
    def _fix_splitters(self):
        # сглаживание resize
        self.topSplitter.setOpaqueResize(False)
        self.verticalSplitter.setOpaqueResize(False)

        # запрет схлопывания
        self.topSplitter.setCollapsible(0, False)
        self.topSplitter.setCollapsible(1, False)
        self.topSplitter.setCollapsible(2, False)

        self.verticalSplitter.setCollapsible(0, False)
        self.verticalSplitter.setCollapsible(1, False)

        # стартовые размеры
        self.topSplitter.setSizes([300, 1000, 300])
        self.verticalSplitter.setSizes([600, 200])

    # ----------------------------------------------------
    #  СИНХРОНИЗАЦИЯ С ПИККИНГОМ
    # ----------------------------------------------------
    def mouse_button_clicked(self, x, y, viewport):
        # сюда подписан window.on_mouse_button_event
        self._pending_pick = (x, y, viewport)

    def _after_render(self, window):
        if self._pending_pick is None:
            return

        x, y, viewport = self._pending_pick
        self._pending_pick = None

        picked_ent = window.pick_entity_at(x, y, viewport)
        if picked_ent is not None:
            self.selected_entity_id = self.viewport_window._get_pick_id_for_entity(picked_ent)
            # синхронизируем дерево и инспектор
            self._select_object_in_tree(picked_ent)
            self.inspector.set_target(picked_ent)
        else:
            self.selected_entity_id = 0
            self.inspector.set_target(None)

    def _select_object_in_tree(self, obj):
        """
        Выделяет объект (Entity / Transform3) в дереве, если он там есть.
        """
        model: SceneTreeModel = self.sceneTree.model()
        idx = model.index_for_object(obj)
        if not idx.isValid():
            return
        self.sceneTree.setCurrentIndex(idx)
        self.sceneTree.scrollTo(idx)

    # ----------------------------------------------------
    def _init_viewport(self):
        self._pending_pick = None  # (x, y, viewport) или None
        layout = self.viewportContainer.layout()

        self.viewport_window = self.world.create_window(
            width=900,
            height=800,
            title="viewport",
            parent=self.viewportContainer
        )
        self.viewport = self.viewport_window.add_viewport(self.scene, self.camera)
        self.viewport_window.set_world_mode("editor")
        
        self.viewport_window.on_mouse_button_event = self.mouse_button_clicked
        self.viewport_window.after_render_handler = self._after_render

        gl_widget = self.viewport_window.handle.widget
        gl_widget.setFocusPolicy(Qt.StrongFocus)
        gl_widget.setMinimumSize(50, 50)

        layout.addWidget(gl_widget)

        self.viewport.set_render_pipeline(self.make_pipeline())

    # ----------------------------------------------------
    #  КЛИК ПО ДЕРЕВУ → ОБНОВИТЬ ИНСПЕКТОР И ВЫБОР В 3D
    # ----------------------------------------------------
    def on_tree_click(self, index):
        node = index.internalPointer()
        obj = node.obj

        # Инспектор
        self.inspector.set_target(obj)

        # Если выбрали entity / transform – обновим selected_entity_id, чтобы хайлайт совпадал.
        if isinstance(obj, Entity):
            ent = obj
        elif isinstance(obj, Transform3):
            # у Transform3 нет id, привяжемся к его владельцу Entity, если нужно
            # упрощённо: ищем первый entity с таким transform
            ent = next((e for e in self.scene.entities if e.transform is obj), None)
        else:
            ent = None

        if ent is not None:
            self.selected_entity_id = self.viewport_window._get_pick_id_for_entity(ent)
        else:
            self.selected_entity_id = 0

        # чтобы хайлайт обновился сразу
        if self.viewport_window is not None:
            self.viewport_window._request_update()

    # ----------------------------------------------------
    def make_pipeline(self) -> list["FramePass"]:
        """
        Собирает конвейер рендера.
        """
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
