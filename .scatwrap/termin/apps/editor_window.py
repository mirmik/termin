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
&#9;def __init__(self, world, scene):<br>
&#9;&#9;super().__init__()<br>
&#9;&#9;self.selected_entity_id = 0<br>
&#9;&#9;self.hover_entity_id = 0   # &lt;--- добавили<br>
<br>
&#9;&#9;ui_path = os.path.join(os.path.dirname(__file__), &quot;editor.ui&quot;)<br>
&#9;&#9;uic.loadUi(ui_path, self)<br>
<br>
&#9;&#9;self.world = world<br>
&#9;&#9;self.scene = scene<br>
<br>
&#9;&#9;# будут созданы ниже<br>
&#9;&#9;self.camera = None<br>
&#9;&#9;self.editor_entities = None<br>
&#9;&#9;self.gizmo: GizmoEntity | None = None<br>
<br>
&#9;&#9;# --- ресурс-менеджер редактора ---<br>
&#9;&#9;self.resource_manager = ResourceManager()<br>
&#9;&#9;self._init_resources_from_scene()<br>
<br>
<br>
&#9;&#9;# --- UI из .ui ---<br>
&#9;&#9;self.sceneTree: QTreeView = self.findChild(QTreeView, &quot;sceneTree&quot;)<br>
<br>
&#9;&#9;self.sceneTree.setContextMenuPolicy(Qt.CustomContextMenu)<br>
&#9;&#9;self.sceneTree.customContextMenuRequested.connect(self.on_tree_context_menu)<br>
<br>
&#9;&#9;self.viewportContainer: QWidget = self.findChild(QWidget, &quot;viewportContainer&quot;)<br>
&#9;&#9;self.inspectorContainer: QWidget = self.findChild(QWidget, &quot;inspectorContainer&quot;)<br>
<br>
&#9;&#9;from PyQt5.QtWidgets import QSplitter<br>
&#9;&#9;self.topSplitter: QSplitter = self.findChild(QSplitter, &quot;topSplitter&quot;)<br>
&#9;&#9;self.verticalSplitter: QSplitter = self.findChild(QSplitter, &quot;verticalSplitter&quot;)<br>
<br>
&#9;&#9;self._fix_splitters()<br>
<br>
<br>
&#9;&#9;# --- инспектор ---<br>
&#9;&#9;self.inspector = EntityInspector(self.resource_manager, self.inspectorContainer)<br>
&#9;&#9;self._init_inspector_widget()<br>
<br>
&#9;&#9;component_library = [<br>
&#9;&#9;&#9;(&quot;PerspectiveCameraComponent&quot;, PerspectiveCameraComponent),<br>
&#9;&#9;&#9;(&quot;OrbitCameraController&quot;,      OrbitCameraController),<br>
&#9;&#9;&#9;(&quot;MeshRenderer&quot;,               MeshRenderer),<br>
&#9;&#9;]<br>
&#9;&#9;self.inspector.set_component_library(component_library)<br>
<br>
&#9;&#9;# на всякий случай — зарегистрируем компоненты и в ресурс-менеджере<br>
&#9;&#9;for label, cls in component_library:<br>
&#9;&#9;&#9;self.resource_manager.register_component(label, cls)<br>
<br>
&#9;&#9;self.inspector.transform_changed.connect(self._on_inspector_transform_changed)<br>
&#9;&#9;self.inspector.component_changed.connect(self._on_inspector_component_changed)<br>
<br>
<br>
&#9;&#9;# --- создаём редакторские сущности (root, камера, гизмо) ---<br>
&#9;&#9;self._ensure_editor_entities_root()<br>
&#9;&#9;self._ensure_editor_camera()<br>
&#9;&#9;self._ensure_gizmo()<br>
<br>
&#9;&#9;# --- дерево сцены ---<br>
&#9;&#9;self._tree_model = SceneTreeModel(scene)<br>
&#9;&#9;self._setup_tree_model()<br>
<br>
&#9;&#9;self.sceneTree.setModel(self._tree_model)<br>
&#9;&#9;self.sceneTree.expandAll()<br>
&#9;&#9;self.sceneTree.clicked.connect(self.on_tree_click)<br>
<br>
&#9;&#9;# --- viewport ---<br>
&#9;&#9;self._init_viewport()<br>
<br>
<br>
&#9;def _ensure_editor_entities_root(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Ищем/создаём корневую сущность для редакторских вещей:<br>
&#9;&#9;камера, гизмо и т.п.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;for ent in self.scene.entities:<br>
&#9;&#9;&#9;if getattr(ent, &quot;name&quot;, &quot;&quot;) == &quot;EditorEntities&quot;:<br>
&#9;&#9;&#9;&#9;self.editor_entities = ent<br>
&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;editor_entities = Entity(name=&quot;EditorEntities&quot;)<br>
&#9;&#9;self.scene.add(editor_entities)<br>
&#9;&#9;self.editor_entities = editor_entities<br>
<br>
&#9;def _ensure_editor_camera(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Создаём редакторскую камеру и вешаем её под EditorEntities (если он есть).<br>
&#9;&#9;Никакого поиска по сцене – у редактора всегда своя камера.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;camera_entity = Entity(name=&quot;camera&quot;, pose=Pose3.identity())<br>
&#9;&#9;camera = PerspectiveCameraComponent()<br>
&#9;&#9;camera_entity.add_component(camera)<br>
&#9;&#9;camera_entity.add_component(OrbitCameraController())<br>
<br>
&#9;&#9;self.editor_entities.transform.link(camera_entity.transform)<br>
&#9;&#9;self.scene.add(camera_entity)<br>
&#9;&#9;self.camera = camera<br>
<br>
&#9;def _ensure_gizmo(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Ищем гизмо в сцене, если нет – создаём.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;for ent in self.scene.entities:<br>
&#9;&#9;&#9;if isinstance(ent, GizmoEntity) or getattr(ent, &quot;name&quot;, &quot;&quot;) == &quot;gizmo&quot;:<br>
&#9;&#9;&#9;&#9;self.gizmo = ent<br>
&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;gizmo = GizmoEntity(size=1.5)<br>
&#9;&#9;gizmo_controller = GizmoMoveController(gizmo, self.scene)<br>
&#9;&#9;gizmo.add_component(gizmo_controller)<br>
<br>
&#9;&#9;if self.editor_entities is not None:<br>
&#9;&#9;&#9;self.editor_entities.transform.add_child(gizmo.transform)<br>
<br>
&#9;&#9;self.scene.add(gizmo)<br>
&#9;&#9;self.gizmo = gizmo<br>
<br>
<br>
<br>
&#9;# ----------- ресурсы из сцены -----------<br>
<br>
&#9;def _init_resources_from_scene(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Складываем в ResourceManager материалы и меши, использованные в сцене.<br>
&#9;&#9;И даём им хоть какие-то имена, если их ещё нет.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;for ent in self.scene.entities:<br>
&#9;&#9;&#9;mr = ent.get_component(MeshRenderer)<br>
&#9;&#9;&#9;if mr is None:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;# ------------ МЕШИ ------------<br>
&#9;&#9;&#9;mesh = getattr(mr, &quot;mesh&quot;, None)<br>
&#9;&#9;&#9;if mesh is not None:<br>
&#9;&#9;&#9;&#9;existing_mesh_name = self.resource_manager.find_mesh_name(mesh)<br>
&#9;&#9;&#9;&#9;if existing_mesh_name is None:<br>
&#9;&#9;&#9;&#9;&#9;name = getattr(mesh, &quot;name&quot;, None)<br>
&#9;&#9;&#9;&#9;&#9;if not name:<br>
&#9;&#9;&#9;&#9;&#9;&#9;base = f&quot;{ent.name}_mesh&quot; if getattr(ent, &quot;name&quot;, None) else &quot;Mesh&quot;<br>
&#9;&#9;&#9;&#9;&#9;&#9;name = base<br>
&#9;&#9;&#9;&#9;&#9;&#9;i = 1<br>
&#9;&#9;&#9;&#9;&#9;&#9;while name in self.resource_manager.meshes:<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;i += 1<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;name = f&quot;{base}_{i}&quot;<br>
&#9;&#9;&#9;&#9;&#9;mesh.name = name<br>
&#9;&#9;&#9;&#9;&#9;self.resource_manager.register_mesh(name, mesh)<br>
<br>
&#9;&#9;&#9;# ------------ МАТЕРИАЛЫ ------------<br>
&#9;&#9;&#9;mat = mr.material<br>
&#9;&#9;&#9;if mat is None:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;existing_name = self.resource_manager.find_material_name(mat)<br>
&#9;&#9;&#9;if existing_name is not None:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;name = getattr(mat, &quot;name&quot;, None)<br>
&#9;&#9;&#9;if not name:<br>
&#9;&#9;&#9;&#9;base = f&quot;{ent.name}_mat&quot; if getattr(ent, &quot;name&quot;, None) else &quot;Material&quot;<br>
&#9;&#9;&#9;&#9;name = base<br>
&#9;&#9;&#9;&#9;i = 1<br>
&#9;&#9;&#9;&#9;while name in self.resource_manager.materials:<br>
&#9;&#9;&#9;&#9;&#9;i += 1<br>
&#9;&#9;&#9;&#9;&#9;name = f&quot;{base}_{i}&quot;<br>
&#9;&#9;&#9;&#9;mat.name = name<br>
<br>
&#9;&#9;&#9;self.resource_manager.register_material(name, mat)<br>
<br>
<br>
&#9;# ----------- реакции инспектора -----------<br>
<br>
&#9;def _on_inspector_transform_changed(self):<br>
&#9;&#9;if self.viewport_window is not None:<br>
&#9;&#9;&#9;self.viewport_window._request_update()<br>
<br>
&#9;def _on_inspector_component_changed(self):<br>
&#9;&#9;if self.viewport_window is not None:<br>
&#9;&#9;&#9;self.viewport_window._request_update()<br>
<br>
&#9;# ----------- контекстное меню дерева -----------<br>
<br>
&#9;def on_tree_context_menu(self, pos: QPoint):<br>
&#9;&#9;index = self.sceneTree.indexAt(pos)<br>
&#9;&#9;node = index.internalPointer() if index.isValid() else None<br>
&#9;&#9;target_obj = node.obj if node is not None else None<br>
<br>
&#9;&#9;menu = QMenu(self)<br>
&#9;&#9;action_add = menu.addAction(&quot;Add entity&quot;)<br>
<br>
&#9;&#9;action_delete = None<br>
&#9;&#9;if isinstance(target_obj, Entity):<br>
&#9;&#9;&#9;action_delete = menu.addAction(&quot;Delete entity&quot;)<br>
<br>
&#9;&#9;global_pos = self.sceneTree.viewport().mapToGlobal(pos)<br>
&#9;&#9;action = menu.exec_(global_pos)<br>
&#9;&#9;if action == action_add:<br>
&#9;&#9;&#9;self._create_entity_from_context(target_obj)<br>
&#9;&#9;elif action == action_delete:<br>
&#9;&#9;&#9;self._delete_entity_from_context(target_obj)<br>
<br>
&#9;def _delete_entity_from_context(self, ent: Entity):<br>
&#9;&#9;if not isinstance(ent, Entity):<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;parent_tf = getattr(ent.transform, &quot;parent&quot;, None)<br>
&#9;&#9;parent_ent = getattr(parent_tf, &quot;entity&quot;, None) if parent_tf is not None else None<br>
&#9;&#9;if not isinstance(parent_ent, Entity):<br>
&#9;&#9;&#9;parent_ent = None<br>
<br>
&#9;&#9;if self.inspector is not None:<br>
&#9;&#9;&#9;self.inspector.set_target(None)<br>
<br>
&#9;&#9;self.on_selection_changed(None)<br>
<br>
&#9;&#9;if hasattr(self.scene, &quot;remove&quot;):<br>
&#9;&#9;&#9;self.scene.remove(ent)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;try:<br>
&#9;&#9;&#9;&#9;self.scene.entities.remove(ent)<br>
&#9;&#9;&#9;&#9;ent.on_removed()<br>
&#9;&#9;&#9;except ValueError:<br>
&#9;&#9;&#9;&#9;pass<br>
<br>
&#9;&#9;self._rebuild_tree_model(select_obj=parent_ent)<br>
<br>
&#9;&#9;if self.viewport_window is not None:<br>
&#9;&#9;&#9;self.viewport_window._request_update()<br>
<br>
&#9;def _setup_tree_model(self):<br>
&#9;&#9;self.sceneTree.setModel(self._tree_model)<br>
&#9;&#9;self.sceneTree.expandAll()<br>
&#9;&#9;self.sceneTree.clicked.connect(self.on_tree_click)<br>
<br>
&#9;&#9;sel_model = self.sceneTree.selectionModel()<br>
&#9;&#9;if sel_model is not None:<br>
&#9;&#9;&#9;sel_model.currentChanged.connect(self.on_tree_current_changed)<br>
<br>
&#9;def _rebuild_tree_model(self, select_obj=None):<br>
&#9;&#9;self._tree_model = SceneTreeModel(self.scene)<br>
&#9;&#9;self._setup_tree_model()<br>
&#9;&#9;if select_obj is not None:<br>
&#9;&#9;&#9;self._select_object_in_tree(select_obj)<br>
<br>
&#9;def on_tree_current_changed(self, current, _previous):<br>
&#9;&#9;if not current.isValid():<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self.on_tree_click(current)<br>
<br>
&#9;def _create_entity_from_context(self, target_obj):<br>
&#9;&#9;parent_transform = None<br>
&#9;&#9;if isinstance(target_obj, Entity):<br>
&#9;&#9;&#9;parent_transform = target_obj.transform<br>
&#9;&#9;elif isinstance(target_obj, Transform3):<br>
&#9;&#9;&#9;parent_transform = target_obj<br>
<br>
&#9;&#9;existing = {e.name for e in self.scene.entities}<br>
&#9;&#9;base = &quot;entity&quot;<br>
&#9;&#9;i = 1<br>
&#9;&#9;while f&quot;{base}{i}&quot; in existing:<br>
&#9;&#9;&#9;i += 1<br>
&#9;&#9;name = f&quot;{base}{i}&quot;<br>
<br>
&#9;&#9;ent = Entity(pose=Pose3.identity(), name=name)<br>
<br>
&#9;&#9;if parent_transform is not None:<br>
&#9;&#9;&#9;ent.transform.set_parent(parent_transform)<br>
<br>
&#9;&#9;self.scene.add(ent)<br>
&#9;&#9;self._rebuild_tree_model(select_obj=ent)<br>
<br>
&#9;&#9;if self.viewport_window is not None:<br>
&#9;&#9;&#9;self.viewport_window._request_update()<br>
<br>
&#9;def _init_inspector_widget(self):<br>
&#9;&#9;parent = self.inspectorContainer<br>
&#9;&#9;layout = parent.layout()<br>
&#9;&#9;if layout is None:<br>
&#9;&#9;&#9;layout = QVBoxLayout(parent)<br>
&#9;&#9;&#9;parent.setLayout(layout)<br>
&#9;&#9;layout.addWidget(self.inspector)<br>
<br>
&#9;def _fix_splitters(self):<br>
&#9;&#9;self.topSplitter.setOpaqueResize(False)<br>
&#9;&#9;self.verticalSplitter.setOpaqueResize(False)<br>
<br>
&#9;&#9;self.topSplitter.setCollapsible(0, False)<br>
&#9;&#9;self.topSplitter.setCollapsible(1, False)<br>
&#9;&#9;self.topSplitter.setCollapsible(2, False)<br>
<br>
&#9;&#9;self.verticalSplitter.setCollapsible(0, False)<br>
&#9;&#9;self.verticalSplitter.setCollapsible(1, False)<br>
<br>
&#9;&#9;self.topSplitter.setSizes([300, 1000, 300])<br>
&#9;&#9;self.verticalSplitter.setSizes([600, 200])<br>
<br>
&#9;# ----------- синхронизация с пиками -----------<br>
<br>
&#9;def mouse_button_event(self, button_type, action, x, y, viewport):<br>
&#9;&#9;from termin.visualization.backends.base import MouseButton<br>
&#9;&#9;if button_type == MouseButton.LEFT and action == Action.RELEASE:<br>
&#9;&#9;&#9;self._pending_pick_release = (x, y, viewport)<br>
&#9;&#9;if button_type == MouseButton.LEFT and action == Action.PRESS:<br>
&#9;&#9;&#9;self._pending_pick_press = (x, y, viewport)<br>
<br>
&#9;def _after_render(self, window):<br>
&#9;&#9;if self._pending_pick_press is not None:<br>
&#9;&#9;&#9;self._process_pending_pick_press(self._pending_pick_press, window)<br>
&#9;&#9;if self._pending_pick_release is not None:<br>
&#9;&#9;&#9;self._process_pending_pick_release(self._pending_pick_release, window)<br>
&#9;&#9;if self._pending_hover is not None:<br>
&#9;&#9;&#9;self._process_pending_hover(self._pending_hover, window)<br>
<br>
&#9;def _process_pending_hover(self, pending_hover, window):<br>
&#9;&#9;x, y, viewport = pending_hover<br>
&#9;&#9;self._pending_hover = None<br>
<br>
&#9;&#9;hovered_ent = window.pick_entity_at(x, y, viewport)<br>
&#9;&#9;self._update_hover_entity(hovered_ent)<br>
<br>
&#9;def _process_pending_pick_release(self, pending_release, window):<br>
&#9;&#9;x, y, viewport = pending_release<br>
&#9;&#9;self._pending_pick_release = None<br>
<br>
&#9;&#9;picked_ent = window.pick_entity_at(x, y, viewport)<br>
<br>
&#9;&#9;# обычный selection (как у тебя было)<br>
&#9;&#9;if picked_ent is not None:<br>
&#9;&#9;&#9;self.on_selection_changed(picked_ent)<br>
&#9;&#9;&#9;self._select_object_in_tree(picked_ent)<br>
&#9;&#9;&#9;self.inspector.set_target(picked_ent)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;self.on_selection_changed(None)<br>
&#9;&#9;&#9;self.inspector.set_target(None)<br>
<br>
&#9;def _is_entity_part_of_gizmo(self, ent: Entity) -&gt; bool:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Проверяет, является ли ent частью гизмо (стрелкой, кольцом и т.п.).<br>
&#9;&#9;Ходит вверх по иерархии transform, пока не найдёт gizmo_axis_* или gizmo_rot_*.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if ent is None or self.gizmo is None:<br>
&#9;&#9;&#9;return False<br>
<br>
&#9;&#9;cur = ent<br>
&#9;&#9;while cur is not None:<br>
&#9;&#9;&#9;name = cur.name<br>
<br>
&#9;&#9;&#9;if name.startswith(&quot;gizmo_axis_&quot;) or name.startswith(&quot;gizmo_rot_&quot;):<br>
&#9;&#9;&#9;&#9;return True<br>
<br>
&#9;&#9;&#9;tf = cur.transform<br>
&#9;&#9;&#9;parent_tf = tf.parent if tf is not None else None<br>
&#9;&#9;&#9;cur = parent_tf.entity if parent_tf is not None else None<br>
<br>
&#9;&#9;return False<br>
<br>
&#9;def _process_pending_pick_press(self, pending_press, window):<br>
&#9;&#9;x, y, viewport = pending_press<br>
&#9;&#9;self._pending_pick_press = None<br>
<br>
&#9;&#9;picked_ent = window.pick_entity_at(x, y, viewport)<br>
<br>
&#9;&#9;gizmo_ctrl = None<br>
&#9;&#9;if self.gizmo is not None:<br>
&#9;&#9;&#9;gizmo_ctrl = self.gizmo.find_component(GizmoMoveController)<br>
<br>
&#9;&#9;# сначала проверяем, не гизмо ли это<br>
&#9;&#9;if picked_ent is not None and gizmo_ctrl is not None:<br>
&#9;&#9;&#9;ent = picked_ent<br>
&#9;&#9;&#9;is_gizmo_part = self._is_entity_part_of_gizmo(ent)<br>
<br>
&#9;&#9;&#9;if is_gizmo_part:<br>
&#9;&#9;&#9;&#9;print(&quot;Clicked on gizmo part&quot;)<br>
&#9;&#9;&#9;&#9;name = picked_ent.name or &quot;&quot;<br>
&#9;&#9;&#9;&#9;print(f&quot;Clicked on gizmo part: {name}&quot;)<br>
<br>
&#9;&#9;&#9;&#9;# перемещение по оси<br>
&#9;&#9;&#9;&#9;if name.endswith(&quot;shaft&quot;) or name.endswith(&quot;head&quot;):<br>
&#9;&#9;&#9;&#9;&#9;axis = name[0]<br>
&#9;&#9;&#9;&#9;&#9;gizmo_ctrl.start_translate_from_pick(axis, viewport, x, y)<br>
&#9;&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;&#9;&#9;# вращение по оси (если уже подключишь кольца)<br>
&#9;&#9;&#9;&#9;if name.endswith(&quot;ring&quot;):<br>
&#9;&#9;&#9;&#9;&#9;print(&quot;Starting rotation from pick&quot;)<br>
&#9;&#9;&#9;&#9;&#9;axis = name[0]<br>
&#9;&#9;&#9;&#9;&#9;gizmo_ctrl.start_rotate_from_pick(axis, viewport, x, y)<br>
&#9;&#9;&#9;&#9;&#9;return<br>
<br>
<br>
&#9;def _extract_gizmo_hit(self, ent: Entity | None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает (&quot;translate&quot; | &quot;rotate&quot;, axis) если кликнули по части гизмо,<br>
&#9;&#9;иначе None.<br>
<br>
&#9;&#9;Ходим вверх по иерархии transform, пока не найдём gizmo_axis_* или gizmo_rot_*.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if ent is None or self.gizmo is None:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;cur = ent<br>
&#9;&#9;while cur is not None:<br>
&#9;&#9;&#9;name = getattr(cur, &quot;name&quot;, &quot;&quot;)<br>
<br>
&#9;&#9;&#9;if name.startswith(&quot;gizmo_axis_&quot;):<br>
&#9;&#9;&#9;&#9;axis = name.removeprefix(&quot;gizmo_axis_&quot;)<br>
&#9;&#9;&#9;&#9;return (&quot;translate&quot;, axis)<br>
<br>
&#9;&#9;&#9;if name.startswith(&quot;gizmo_rot_&quot;):<br>
&#9;&#9;&#9;&#9;axis = name.removeprefix(&quot;gizmo_rot_&quot;)<br>
&#9;&#9;&#9;&#9;return (&quot;rotate&quot;, axis)<br>
<br>
&#9;&#9;&#9;tf = getattr(cur, &quot;transform&quot;, None)<br>
&#9;&#9;&#9;parent_tf = getattr(tf, &quot;parent&quot;, None) if tf is not None else None<br>
&#9;&#9;&#9;cur = getattr(parent_tf, &quot;entity&quot;, None) if parent_tf is not None else None<br>
<br>
&#9;&#9;return None<br>
<br>
&#9;def _update_hover_entity(self, ent: Entity | None):<br>
&#9;&#9;# как и в selection – игнорим невыделяемое (гизмо и т.п.)<br>
&#9;&#9;if ent is not None and ent.selectable is False:<br>
&#9;&#9;&#9;ent = None<br>
<br>
&#9;&#9;if ent is not None:<br>
&#9;&#9;&#9;new_id = self.viewport_window._get_pick_id_for_entity(ent)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;new_id = 0<br>
<br>
&#9;&#9;if new_id == self.hover_entity_id:<br>
&#9;&#9;&#9;return  # ничего не поменялось<br>
<br>
&#9;&#9;self.hover_entity_id = new_id<br>
<br>
&#9;&#9;if self.viewport_window is not None:<br>
&#9;&#9;&#9;self.viewport_window._request_update()<br>
<br>
&#9;def _select_object_in_tree(self, obj):<br>
&#9;&#9;model: SceneTreeModel = self.sceneTree.model()<br>
&#9;&#9;idx = model.index_for_object(obj)<br>
&#9;&#9;if not idx.isValid():<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self.sceneTree.setCurrentIndex(idx)<br>
&#9;&#9;self.sceneTree.scrollTo(idx)<br>
<br>
&#9;def _init_viewport(self):<br>
&#9;&#9;self._pending_pick_press = None<br>
&#9;&#9;self._pending_pick_release = None<br>
&#9;&#9;self._pending_hover = None   # &lt;- новый буфер для hover-пика<br>
&#9;&#9;layout = self.viewportContainer.layout()<br>
<br>
&#9;&#9;self.viewport_window = self.world.create_window(<br>
&#9;&#9;&#9;width=900,<br>
&#9;&#9;&#9;height=800,<br>
&#9;&#9;&#9;title=&quot;viewport&quot;,<br>
&#9;&#9;&#9;parent=self.viewportContainer<br>
&#9;&#9;)<br>
&#9;&#9;# здесь self.camera уже создана в _ensure_editor_camera<br>
&#9;&#9;self.viewport = self.viewport_window.add_viewport(self.scene, self.camera)<br>
&#9;&#9;self.viewport_window.set_world_mode(&quot;editor&quot;)<br>
<br>
&#9;&#9;self.viewport_window.on_mouse_button_event = self.mouse_button_event<br>
&#9;&#9;self.viewport_window.after_render_handler = self._after_render<br>
&#9;&#9;self.viewport_window.on_mouse_move_event   = self.mouse_moved<br>
<br>
&#9;&#9;gl_widget = self.viewport_window.handle.widget<br>
&#9;&#9;gl_widget.setFocusPolicy(Qt.StrongFocus)<br>
&#9;&#9;gl_widget.setMinimumSize(50, 50)<br>
<br>
&#9;&#9;layout.addWidget(gl_widget)<br>
<br>
&#9;&#9;self.viewport.set_render_pipeline(self.make_pipeline())<br>
<br>
<br>
&#9;&#9;def mouse_moved(self, x: float, y: float, viewport):<br>
&#9;&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;&#9;Вызывается Window'ом при каждом движении курсора.<br>
&#9;&#9;&#9;Просто запоминаем, что надо сделать hover-pick после следующего рендера.<br>
&#9;&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;&#9;if viewport is None:<br>
&#9;&#9;&#9;&#9;self._pending_hover = None<br>
&#9;&#9;&#9;&#9;return<br>
&#9;&#9;&#9;self._pending_hover = (x, y, viewport)<br>
<br>
&#9;def on_tree_click(self, index):<br>
&#9;&#9;node = index.internalPointer()<br>
&#9;&#9;obj = node.obj<br>
<br>
&#9;&#9;self.inspector.set_target(obj)<br>
<br>
&#9;&#9;if isinstance(obj, Entity):<br>
&#9;&#9;&#9;ent = obj<br>
&#9;&#9;elif isinstance(obj, Transform3):<br>
&#9;&#9;&#9;ent = next((e for e in self.scene.entities if e.transform is obj), None)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;ent = None<br>
<br>
&#9;&#9;self.on_selection_changed(ent)<br>
<br>
&#9;&#9;if self.viewport_window is not None:<br>
&#9;&#9;&#9;self.viewport_window._request_update()<br>
<br>
&#9;def mouse_moved(self, x: float, y: float, viewport):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вызывается Window'ом при каждом движении курсора.<br>
&#9;&#9;Просто запоминаем, что надо сделать hover-pick после следующего рендера.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;if viewport is None:<br>
&#9;&#9;&#9;self._pending_hover = None<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self._pending_hover = (x, y, viewport)<br>
<br>
&#9;def on_selection_changed(self, selected_ent):<br>
&#9;&#9;if selected_ent is not None and selected_ent.selectable is False:<br>
&#9;&#9;&#9;# Мы пикнули что-то невыделяемое. Скорее всего гизмо.<br>
&#9;&#9;&#9;return<br>
&#9;&#9;<br>
&#9;&#9;self.selected_entity_id = self.viewport_window._get_pick_id_for_entity(selected_ent) if selected_ent is not None else 0<br>
&#9;&#9;self.gizmo.find_component(GizmoMoveController).set_target(selected_ent)<br>
<br>
&#9;def make_pipeline(self) -&gt; list[&quot;FramePass&quot;]:<br>
&#9;&#9;from termin.visualization.framegraph import ColorPass, IdPass, CanvasPass, PresentToScreenPass<br>
&#9;&#9;from termin.visualization.postprocess import PostProcessPass<br>
&#9;&#9;from termin.visualization.posteffects.highlight import HighlightEffect<br>
<br>
&#9;&#9;postprocess = PostProcessPass(<br>
&#9;&#9;&#9;effects=[],<br>
&#9;&#9;&#9;input_res=&quot;color&quot;,<br>
&#9;&#9;&#9;output_res=&quot;color_pp&quot;,<br>
&#9;&#9;&#9;pass_name=&quot;PostFX&quot;,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;passes: list[&quot;FramePass&quot;] = [<br>
&#9;&#9;&#9;ColorPass(input_res=&quot;empty&quot;, output_res=&quot;color&quot;, pass_name=&quot;Color&quot;),<br>
&#9;&#9;&#9;IdPass(input_res=&quot;empty_id&quot;, output_res=&quot;id&quot;, pass_name=&quot;Id&quot;),<br>
&#9;&#9;&#9;postprocess,<br>
&#9;&#9;&#9;CanvasPass(<br>
&#9;&#9;&#9;&#9;src=&quot;color_pp&quot;,<br>
&#9;&#9;&#9;&#9;dst=&quot;color+ui&quot;,<br>
&#9;&#9;&#9;&#9;pass_name=&quot;Canvas&quot;,<br>
&#9;&#9;&#9;),<br>
&#9;&#9;&#9;PresentToScreenPass(<br>
&#9;&#9;&#9;&#9;input_res=&quot;color+ui&quot;,<br>
&#9;&#9;&#9;&#9;pass_name=&quot;Present&quot;,<br>
&#9;&#9;&#9;)<br>
&#9;&#9;]<br>
<br>
&#9;&#9;postprocess.add_effect(HighlightEffect(lambda: self.hover_entity_id, color=(0.3, 0.8, 1.0, 1.0)))<br>
&#9;&#9;postprocess.add_effect(HighlightEffect(lambda: self.selected_entity_id, color=(1.0, 0.9, 0.1, 1.0)))<br>
<br>
&#9;&#9;return passes<br>
<!-- END SCAT CODE -->
</body>
</html>
