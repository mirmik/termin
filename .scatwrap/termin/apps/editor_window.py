<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/apps/editor_window.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# ===== termin/apps/editor_window.py =====<br>
import os<br>
from PyQt5 import uic<br>
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTreeView, QLabel, QMenu<br>
from PyQt5.QtCore import Qt, QPoint<br>
<br>
from termin.visualization.camera import PerspectiveCameraComponent, OrbitCameraController<br>
from termin.visualization.components.mesh_renderer import MeshRenderer<br>
from termin.visualization.entity import Entity<br>
from termin.kinematic.transform import Transform3<br>
from editor_tree import SceneTreeModel<br>
from editor_inspector import EntityInspector<br>
from termin.visualization.picking import id_to_rgb<br>
from termin.visualization.resources import ResourceManager<br>
from termin.geombase.pose3 import Pose3<br>
from termin.visualization.gizmos.gizmo_axes import GizmoEntity, GizmoMoveController<br>
from termin.visualization.backends.base import Action, MouseButton<br>
<br>
<br>
class EditorWindow(QMainWindow):<br>
    def __init__(self, world, scene):<br>
        super().__init__()<br>
        self.selected_entity_id = 0<br>
        self.hover_entity_id = 0   # &lt;--- добавили<br>
<br>
        ui_path = os.path.join(os.path.dirname(__file__), &quot;editor.ui&quot;)<br>
        uic.loadUi(ui_path, self)<br>
<br>
        self.world = world<br>
        self.scene = scene<br>
<br>
        # будут созданы ниже<br>
        self.camera = None<br>
        self.editor_entities = None<br>
        self.gizmo: GizmoEntity | None = None<br>
<br>
        # --- ресурс-менеджер редактора ---<br>
        self.resource_manager = ResourceManager()<br>
        self._init_resources_from_scene()<br>
<br>
<br>
        # --- UI из .ui ---<br>
        self.sceneTree: QTreeView = self.findChild(QTreeView, &quot;sceneTree&quot;)<br>
<br>
        self.sceneTree.setContextMenuPolicy(Qt.CustomContextMenu)<br>
        self.sceneTree.customContextMenuRequested.connect(self.on_tree_context_menu)<br>
<br>
        self.viewportContainer: QWidget = self.findChild(QWidget, &quot;viewportContainer&quot;)<br>
        self.inspectorContainer: QWidget = self.findChild(QWidget, &quot;inspectorContainer&quot;)<br>
<br>
        from PyQt5.QtWidgets import QSplitter<br>
        self.topSplitter: QSplitter = self.findChild(QSplitter, &quot;topSplitter&quot;)<br>
        self.verticalSplitter: QSplitter = self.findChild(QSplitter, &quot;verticalSplitter&quot;)<br>
<br>
        self._fix_splitters()<br>
<br>
<br>
        # --- инспектор ---<br>
        self.inspector = EntityInspector(self.resource_manager, self.inspectorContainer)<br>
        self._init_inspector_widget()<br>
<br>
        component_library = [<br>
            (&quot;PerspectiveCameraComponent&quot;, PerspectiveCameraComponent),<br>
            (&quot;OrbitCameraController&quot;,      OrbitCameraController),<br>
            (&quot;MeshRenderer&quot;,               MeshRenderer),<br>
        ]<br>
        self.inspector.set_component_library(component_library)<br>
<br>
        # на всякий случай — зарегистрируем компоненты и в ресурс-менеджере<br>
        for label, cls in component_library:<br>
            self.resource_manager.register_component(label, cls)<br>
<br>
        self.inspector.transform_changed.connect(self._on_inspector_transform_changed)<br>
        self.inspector.component_changed.connect(self._on_inspector_component_changed)<br>
<br>
<br>
        # --- создаём редакторские сущности (root, камера, гизмо) ---<br>
        self._ensure_editor_entities_root()<br>
        self._ensure_editor_camera()<br>
        self._ensure_gizmo()<br>
<br>
        # --- дерево сцены ---<br>
        self._tree_model = SceneTreeModel(scene)<br>
        self._setup_tree_model()<br>
<br>
        self.sceneTree.setModel(self._tree_model)<br>
        self.sceneTree.expandAll()<br>
        self.sceneTree.clicked.connect(self.on_tree_click)<br>
<br>
        # --- viewport ---<br>
        self._init_viewport()<br>
<br>
<br>
    def _ensure_editor_entities_root(self):<br>
        &quot;&quot;&quot;<br>
        Ищем/создаём корневую сущность для редакторских вещей:<br>
        камера, гизмо и т.п.<br>
        &quot;&quot;&quot;<br>
        for ent in self.scene.entities:<br>
            if getattr(ent, &quot;name&quot;, &quot;&quot;) == &quot;EditorEntities&quot;:<br>
                self.editor_entities = ent<br>
                return<br>
<br>
        editor_entities = Entity(name=&quot;EditorEntities&quot;)<br>
        self.scene.add(editor_entities)<br>
        self.editor_entities = editor_entities<br>
<br>
    def _ensure_editor_camera(self):<br>
        &quot;&quot;&quot;<br>
        Создаём редакторскую камеру и вешаем её под EditorEntities (если он есть).<br>
        Никакого поиска по сцене – у редактора всегда своя камера.<br>
        &quot;&quot;&quot;<br>
        camera_entity = Entity(name=&quot;camera&quot;, pose=Pose3.identity())<br>
        camera = PerspectiveCameraComponent()<br>
        camera_entity.add_component(camera)<br>
        camera_entity.add_component(OrbitCameraController())<br>
<br>
        self.editor_entities.transform.link(camera_entity.transform)<br>
        self.scene.add(camera_entity)<br>
        self.camera = camera<br>
<br>
    def _ensure_gizmo(self):<br>
        &quot;&quot;&quot;<br>
        Ищем гизмо в сцене, если нет – создаём.<br>
        &quot;&quot;&quot;<br>
        for ent in self.scene.entities:<br>
            if isinstance(ent, GizmoEntity) or getattr(ent, &quot;name&quot;, &quot;&quot;) == &quot;gizmo&quot;:<br>
                self.gizmo = ent<br>
                return<br>
<br>
        gizmo = GizmoEntity(size=1.5)<br>
        gizmo_controller = GizmoMoveController(gizmo, self.scene)<br>
        gizmo.add_component(gizmo_controller)<br>
<br>
        if self.editor_entities is not None:<br>
            self.editor_entities.transform.add_child(gizmo.transform)<br>
<br>
        self.scene.add(gizmo)<br>
        self.gizmo = gizmo<br>
<br>
<br>
<br>
    # ----------- ресурсы из сцены -----------<br>
<br>
    def _init_resources_from_scene(self):<br>
        &quot;&quot;&quot;<br>
        Складываем в ResourceManager материалы и меши, использованные в сцене.<br>
        И даём им хоть какие-то имена, если их ещё нет.<br>
        &quot;&quot;&quot;<br>
        for ent in self.scene.entities:<br>
            mr = ent.get_component(MeshRenderer)<br>
            if mr is None:<br>
                continue<br>
<br>
            # ------------ МЕШИ ------------<br>
            mesh = getattr(mr, &quot;mesh&quot;, None)<br>
            if mesh is not None:<br>
                existing_mesh_name = self.resource_manager.find_mesh_name(mesh)<br>
                if existing_mesh_name is None:<br>
                    name = getattr(mesh, &quot;name&quot;, None)<br>
                    if not name:<br>
                        base = f&quot;{ent.name}_mesh&quot; if getattr(ent, &quot;name&quot;, None) else &quot;Mesh&quot;<br>
                        name = base<br>
                        i = 1<br>
                        while name in self.resource_manager.meshes:<br>
                            i += 1<br>
                            name = f&quot;{base}_{i}&quot;<br>
                    mesh.name = name<br>
                    self.resource_manager.register_mesh(name, mesh)<br>
<br>
            # ------------ МАТЕРИАЛЫ ------------<br>
            mat = mr.material<br>
            if mat is None:<br>
                continue<br>
<br>
            existing_name = self.resource_manager.find_material_name(mat)<br>
            if existing_name is not None:<br>
                continue<br>
<br>
            name = getattr(mat, &quot;name&quot;, None)<br>
            if not name:<br>
                base = f&quot;{ent.name}_mat&quot; if getattr(ent, &quot;name&quot;, None) else &quot;Material&quot;<br>
                name = base<br>
                i = 1<br>
                while name in self.resource_manager.materials:<br>
                    i += 1<br>
                    name = f&quot;{base}_{i}&quot;<br>
                mat.name = name<br>
<br>
            self.resource_manager.register_material(name, mat)<br>
<br>
<br>
    # ----------- реакции инспектора -----------<br>
<br>
    def _on_inspector_transform_changed(self):<br>
        if self.viewport_window is not None:<br>
            self.viewport_window._request_update()<br>
<br>
    def _on_inspector_component_changed(self):<br>
        if self.viewport_window is not None:<br>
            self.viewport_window._request_update()<br>
<br>
    # ----------- контекстное меню дерева -----------<br>
<br>
    def on_tree_context_menu(self, pos: QPoint):<br>
        index = self.sceneTree.indexAt(pos)<br>
        node = index.internalPointer() if index.isValid() else None<br>
        target_obj = node.obj if node is not None else None<br>
<br>
        menu = QMenu(self)<br>
        action_add = menu.addAction(&quot;Add entity&quot;)<br>
<br>
        action_delete = None<br>
        if isinstance(target_obj, Entity):<br>
            action_delete = menu.addAction(&quot;Delete entity&quot;)<br>
<br>
        global_pos = self.sceneTree.viewport().mapToGlobal(pos)<br>
        action = menu.exec_(global_pos)<br>
        if action == action_add:<br>
            self._create_entity_from_context(target_obj)<br>
        elif action == action_delete:<br>
            self._delete_entity_from_context(target_obj)<br>
<br>
    def _delete_entity_from_context(self, ent: Entity):<br>
        if not isinstance(ent, Entity):<br>
            return<br>
<br>
        parent_tf = getattr(ent.transform, &quot;parent&quot;, None)<br>
        parent_ent = getattr(parent_tf, &quot;entity&quot;, None) if parent_tf is not None else None<br>
        if not isinstance(parent_ent, Entity):<br>
            parent_ent = None<br>
<br>
        if self.inspector is not None:<br>
            self.inspector.set_target(None)<br>
<br>
        self.on_selection_changed(None)<br>
<br>
        if hasattr(self.scene, &quot;remove&quot;):<br>
            self.scene.remove(ent)<br>
        else:<br>
            try:<br>
                self.scene.entities.remove(ent)<br>
                ent.on_removed()<br>
            except ValueError:<br>
                pass<br>
<br>
        self._rebuild_tree_model(select_obj=parent_ent)<br>
<br>
        if self.viewport_window is not None:<br>
            self.viewport_window._request_update()<br>
<br>
    def _setup_tree_model(self):<br>
        self.sceneTree.setModel(self._tree_model)<br>
        self.sceneTree.expandAll()<br>
        self.sceneTree.clicked.connect(self.on_tree_click)<br>
<br>
        sel_model = self.sceneTree.selectionModel()<br>
        if sel_model is not None:<br>
            sel_model.currentChanged.connect(self.on_tree_current_changed)<br>
<br>
    def _rebuild_tree_model(self, select_obj=None):<br>
        self._tree_model = SceneTreeModel(self.scene)<br>
        self._setup_tree_model()<br>
        if select_obj is not None:<br>
            self._select_object_in_tree(select_obj)<br>
<br>
    def on_tree_current_changed(self, current, _previous):<br>
        if not current.isValid():<br>
            return<br>
        self.on_tree_click(current)<br>
<br>
    def _create_entity_from_context(self, target_obj):<br>
        parent_transform = None<br>
        if isinstance(target_obj, Entity):<br>
            parent_transform = target_obj.transform<br>
        elif isinstance(target_obj, Transform3):<br>
            parent_transform = target_obj<br>
<br>
        existing = {e.name for e in self.scene.entities}<br>
        base = &quot;entity&quot;<br>
        i = 1<br>
        while f&quot;{base}{i}&quot; in existing:<br>
            i += 1<br>
        name = f&quot;{base}{i}&quot;<br>
<br>
        ent = Entity(pose=Pose3.identity(), name=name)<br>
<br>
        if parent_transform is not None:<br>
            ent.transform.set_parent(parent_transform)<br>
<br>
        self.scene.add(ent)<br>
        self._rebuild_tree_model(select_obj=ent)<br>
<br>
        if self.viewport_window is not None:<br>
            self.viewport_window._request_update()<br>
<br>
    def _init_inspector_widget(self):<br>
        parent = self.inspectorContainer<br>
        layout = parent.layout()<br>
        if layout is None:<br>
            layout = QVBoxLayout(parent)<br>
            parent.setLayout(layout)<br>
        layout.addWidget(self.inspector)<br>
<br>
    def _fix_splitters(self):<br>
        self.topSplitter.setOpaqueResize(False)<br>
        self.verticalSplitter.setOpaqueResize(False)<br>
<br>
        self.topSplitter.setCollapsible(0, False)<br>
        self.topSplitter.setCollapsible(1, False)<br>
        self.topSplitter.setCollapsible(2, False)<br>
<br>
        self.verticalSplitter.setCollapsible(0, False)<br>
        self.verticalSplitter.setCollapsible(1, False)<br>
<br>
        self.topSplitter.setSizes([300, 1000, 300])<br>
        self.verticalSplitter.setSizes([600, 200])<br>
<br>
    # ----------- синхронизация с пиками -----------<br>
<br>
    def mouse_button_event(self, button_type, action, x, y, viewport):<br>
        from termin.visualization.backends.base import MouseButton<br>
        if button_type == MouseButton.LEFT and action == Action.RELEASE:<br>
            self._pending_pick_release = (x, y, viewport)<br>
        if button_type == MouseButton.LEFT and action == Action.PRESS:<br>
            self._pending_pick_press = (x, y, viewport)<br>
<br>
    def _after_render(self, window):<br>
        if self._pending_pick_press is not None:<br>
            self._process_pending_pick_press(self._pending_pick_press, window)<br>
        if self._pending_pick_release is not None:<br>
            self._process_pending_pick_release(self._pending_pick_release, window)<br>
        if self._pending_hover is not None:<br>
            self._process_pending_hover(self._pending_hover, window)<br>
<br>
    def _process_pending_hover(self, pending_hover, window):<br>
        x, y, viewport = pending_hover<br>
        self._pending_hover = None<br>
<br>
        hovered_ent = window.pick_entity_at(x, y, viewport)<br>
        self._update_hover_entity(hovered_ent)<br>
<br>
    def _process_pending_pick_release(self, pending_release, window):<br>
        x, y, viewport = pending_release<br>
        self._pending_pick_release = None<br>
<br>
        picked_ent = window.pick_entity_at(x, y, viewport)<br>
<br>
        # обычный selection (как у тебя было)<br>
        if picked_ent is not None:<br>
            self.on_selection_changed(picked_ent)<br>
            self._select_object_in_tree(picked_ent)<br>
            self.inspector.set_target(picked_ent)<br>
        else:<br>
            self.on_selection_changed(None)<br>
            self.inspector.set_target(None)<br>
<br>
    def _is_entity_part_of_gizmo(self, ent: Entity) -&gt; bool:<br>
        &quot;&quot;&quot;<br>
        Проверяет, является ли ent частью гизмо (стрелкой, кольцом и т.п.).<br>
        Ходит вверх по иерархии transform, пока не найдёт gizmo_axis_* или gizmo_rot_*.<br>
        &quot;&quot;&quot;<br>
        if ent is None or self.gizmo is None:<br>
            return False<br>
<br>
        cur = ent<br>
        while cur is not None:<br>
            name = cur.name<br>
<br>
            if name.startswith(&quot;gizmo_axis_&quot;) or name.startswith(&quot;gizmo_rot_&quot;):<br>
                return True<br>
<br>
            tf = cur.transform<br>
            parent_tf = tf.parent if tf is not None else None<br>
            cur = parent_tf.entity if parent_tf is not None else None<br>
<br>
        return False<br>
<br>
    def _process_pending_pick_press(self, pending_press, window):<br>
        x, y, viewport = pending_press<br>
        self._pending_pick_press = None<br>
<br>
        picked_ent = window.pick_entity_at(x, y, viewport)<br>
<br>
        gizmo_ctrl = None<br>
        if self.gizmo is not None:<br>
            gizmo_ctrl = self.gizmo.find_component(GizmoMoveController)<br>
<br>
        # сначала проверяем, не гизмо ли это<br>
        if picked_ent is not None and gizmo_ctrl is not None:<br>
            ent = picked_ent<br>
            is_gizmo_part = self._is_entity_part_of_gizmo(ent)<br>
<br>
            if is_gizmo_part:<br>
                print(&quot;Clicked on gizmo part&quot;)<br>
                name = picked_ent.name or &quot;&quot;<br>
                print(f&quot;Clicked on gizmo part: {name}&quot;)<br>
<br>
                # перемещение по оси<br>
                if name.endswith(&quot;shaft&quot;) or name.endswith(&quot;head&quot;):<br>
                    axis = name[0]<br>
                    gizmo_ctrl.start_translate_from_pick(axis, viewport, x, y)<br>
                    return<br>
<br>
                # вращение по оси (если уже подключишь кольца)<br>
                if name.endswith(&quot;ring&quot;):<br>
                    print(&quot;Starting rotation from pick&quot;)<br>
                    axis = name[0]<br>
                    gizmo_ctrl.start_rotate_from_pick(axis, viewport, x, y)<br>
                    return<br>
<br>
<br>
    def _extract_gizmo_hit(self, ent: Entity | None):<br>
        &quot;&quot;&quot;<br>
        Возвращает (&quot;translate&quot; | &quot;rotate&quot;, axis) если кликнули по части гизмо,<br>
        иначе None.<br>
<br>
        Ходим вверх по иерархии transform, пока не найдём gizmo_axis_* или gizmo_rot_*.<br>
        &quot;&quot;&quot;<br>
        if ent is None or self.gizmo is None:<br>
            return None<br>
<br>
        cur = ent<br>
        while cur is not None:<br>
            name = getattr(cur, &quot;name&quot;, &quot;&quot;)<br>
<br>
            if name.startswith(&quot;gizmo_axis_&quot;):<br>
                axis = name.removeprefix(&quot;gizmo_axis_&quot;)<br>
                return (&quot;translate&quot;, axis)<br>
<br>
            if name.startswith(&quot;gizmo_rot_&quot;):<br>
                axis = name.removeprefix(&quot;gizmo_rot_&quot;)<br>
                return (&quot;rotate&quot;, axis)<br>
<br>
            tf = getattr(cur, &quot;transform&quot;, None)<br>
            parent_tf = getattr(tf, &quot;parent&quot;, None) if tf is not None else None<br>
            cur = getattr(parent_tf, &quot;entity&quot;, None) if parent_tf is not None else None<br>
<br>
        return None<br>
<br>
    def _update_hover_entity(self, ent: Entity | None):<br>
        # как и в selection – игнорим невыделяемое (гизмо и т.п.)<br>
        if ent is not None and ent.selectable is False:<br>
            ent = None<br>
<br>
        if ent is not None:<br>
            new_id = self.viewport_window._get_pick_id_for_entity(ent)<br>
        else:<br>
            new_id = 0<br>
<br>
        if new_id == self.hover_entity_id:<br>
            return  # ничего не поменялось<br>
<br>
        self.hover_entity_id = new_id<br>
<br>
        if self.viewport_window is not None:<br>
            self.viewport_window._request_update()<br>
<br>
    def _select_object_in_tree(self, obj):<br>
        model: SceneTreeModel = self.sceneTree.model()<br>
        idx = model.index_for_object(obj)<br>
        if not idx.isValid():<br>
            return<br>
        self.sceneTree.setCurrentIndex(idx)<br>
        self.sceneTree.scrollTo(idx)<br>
<br>
    def _init_viewport(self):<br>
        self._pending_pick_press = None<br>
        self._pending_pick_release = None<br>
        self._pending_hover = None   # &lt;- новый буфер для hover-пика<br>
        layout = self.viewportContainer.layout()<br>
<br>
        self.viewport_window = self.world.create_window(<br>
            width=900,<br>
            height=800,<br>
            title=&quot;viewport&quot;,<br>
            parent=self.viewportContainer<br>
        )<br>
        # здесь self.camera уже создана в _ensure_editor_camera<br>
        self.viewport = self.viewport_window.add_viewport(self.scene, self.camera)<br>
        self.viewport_window.set_world_mode(&quot;editor&quot;)<br>
<br>
        self.viewport_window.on_mouse_button_event = self.mouse_button_event<br>
        self.viewport_window.after_render_handler = self._after_render<br>
        self.viewport_window.on_mouse_move_event   = self.mouse_moved<br>
<br>
        gl_widget = self.viewport_window.handle.widget<br>
        gl_widget.setFocusPolicy(Qt.StrongFocus)<br>
        gl_widget.setMinimumSize(50, 50)<br>
<br>
        layout.addWidget(gl_widget)<br>
<br>
        self.viewport.set_render_pipeline(self.make_pipeline())<br>
<br>
<br>
        def mouse_moved(self, x: float, y: float, viewport):<br>
            &quot;&quot;&quot;<br>
            Вызывается Window'ом при каждом движении курсора.<br>
            Просто запоминаем, что надо сделать hover-pick после следующего рендера.<br>
            &quot;&quot;&quot;<br>
            if viewport is None:<br>
                self._pending_hover = None<br>
                return<br>
            self._pending_hover = (x, y, viewport)<br>
<br>
    def on_tree_click(self, index):<br>
        node = index.internalPointer()<br>
        obj = node.obj<br>
<br>
        self.inspector.set_target(obj)<br>
<br>
        if isinstance(obj, Entity):<br>
            ent = obj<br>
        elif isinstance(obj, Transform3):<br>
            ent = next((e for e in self.scene.entities if e.transform is obj), None)<br>
        else:<br>
            ent = None<br>
<br>
        self.on_selection_changed(ent)<br>
<br>
        if self.viewport_window is not None:<br>
            self.viewport_window._request_update()<br>
<br>
    def mouse_moved(self, x: float, y: float, viewport):<br>
        &quot;&quot;&quot;<br>
        Вызывается Window'ом при каждом движении курсора.<br>
        Просто запоминаем, что надо сделать hover-pick после следующего рендера.<br>
        &quot;&quot;&quot;<br>
        if viewport is None:<br>
            self._pending_hover = None<br>
            return<br>
        self._pending_hover = (x, y, viewport)<br>
<br>
    def on_selection_changed(self, selected_ent):<br>
        if selected_ent is not None and selected_ent.selectable is False:<br>
            # Мы пикнули что-то невыделяемое. Скорее всего гизмо.<br>
            return<br>
        <br>
        self.selected_entity_id = self.viewport_window._get_pick_id_for_entity(selected_ent) if selected_ent is not None else 0<br>
        self.gizmo.find_component(GizmoMoveController).set_target(selected_ent)<br>
<br>
    def make_pipeline(self) -&gt; list[&quot;FramePass&quot;]:<br>
        from termin.visualization.framegraph import ColorPass, IdPass, CanvasPass, PresentToScreenPass<br>
        from termin.visualization.postprocess import PostProcessPass<br>
        from termin.visualization.posteffects.highlight import HighlightEffect<br>
<br>
        postprocess = PostProcessPass(<br>
            effects=[],<br>
            input_res=&quot;color&quot;,<br>
            output_res=&quot;color_pp&quot;,<br>
            pass_name=&quot;PostFX&quot;,<br>
        )<br>
<br>
        passes: list[&quot;FramePass&quot;] = [<br>
            ColorPass(input_res=&quot;empty&quot;, output_res=&quot;color&quot;, pass_name=&quot;Color&quot;),<br>
            IdPass(input_res=&quot;empty_id&quot;, output_res=&quot;id&quot;, pass_name=&quot;Id&quot;),<br>
            postprocess,<br>
            CanvasPass(<br>
                src=&quot;color_pp&quot;,<br>
                dst=&quot;color+ui&quot;,<br>
                pass_name=&quot;Canvas&quot;,<br>
            ),<br>
            PresentToScreenPass(<br>
                input_res=&quot;color+ui&quot;,<br>
                pass_name=&quot;Present&quot;,<br>
            )<br>
        ]<br>
<br>
        postprocess.add_effect(HighlightEffect(lambda: self.hover_entity_id, color=(0.3, 0.8, 1.0, 1.0)))<br>
        postprocess.add_effect(HighlightEffect(lambda: self.selected_entity_id, color=(1.0, 0.9, 0.1, 1.0)))<br>
<br>
        return passes<br>
<!-- END SCAT CODE -->
</body>
</html>
