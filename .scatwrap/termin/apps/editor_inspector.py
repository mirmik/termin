<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/apps/editor_inspector.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# ===== termin/apps/editor_inspector.py =====<br>
from __future__ import annotations<br>
<br>
from typing import Optional<br>
<br>
import numpy as np<br>
from PyQt5.QtWidgets import (<br>
&#9;QWidget,<br>
&#9;QFormLayout,<br>
&#9;QHBoxLayout,<br>
&#9;QDoubleSpinBox,<br>
&#9;QLabel,<br>
&#9;QVBoxLayout,<br>
&#9;QListWidget,<br>
&#9;QListWidgetItem,<br>
&#9;QCheckBox,<br>
&#9;QLineEdit,<br>
&#9;QMenu,<br>
&#9;QAction,<br>
&#9;QComboBox,<br>
)<br>
from PyQt5.QtCore import Qt, pyqtSignal<br>
<br>
from termin.kinematic.transform import Transform3<br>
from termin.visualization.entity import Entity, Component<br>
from termin.geombase.pose3 import Pose3<br>
from termin.visualization.inspect import InspectField<br>
from termin.visualization.resources import ResourceManager<br>
<br>
from termin.apps.transform_inspector import TransformInspector<br>
<br>
<br>
class ComponentsPanel(QWidget):<br>
&#9;components_changed = pyqtSignal()<br>
<br>
&#9;def __init__(self, parent: Optional[QWidget] = None):<br>
&#9;&#9;super().__init__(parent)<br>
<br>
&#9;&#9;layout = QVBoxLayout(self)<br>
&#9;&#9;layout.setContentsMargins(0, 8, 0, 0)<br>
&#9;&#9;layout.setSpacing(4)<br>
<br>
&#9;&#9;self._title = QLabel(&quot;Components&quot;)<br>
&#9;&#9;layout.addWidget(self._title)<br>
<br>
&#9;&#9;self._list = QListWidget()<br>
&#9;&#9;layout.addWidget(self._list)<br>
<br>
&#9;&#9;self._entity: Optional[Entity] = None<br>
&#9;&#9;self._component_library: list[tuple[str, type[Component]]] = []<br>
<br>
&#9;&#9;self._list.setContextMenuPolicy(Qt.CustomContextMenu)<br>
&#9;&#9;self._list.customContextMenuRequested.connect(self._on_context_menu)<br>
<br>
&#9;def set_entity(self, ent: Optional[Entity]):<br>
&#9;&#9;self._entity = ent<br>
&#9;&#9;self._list.clear()<br>
&#9;&#9;if ent is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;for comp in ent.components:<br>
&#9;&#9;&#9;name = comp.__class__.__name__<br>
&#9;&#9;&#9;item = QListWidgetItem(name)<br>
&#9;&#9;&#9;self._list.addItem(item)<br>
<br>
&#9;def set_component_library(self, library: list[tuple[str, type[Component]]]):<br>
&#9;&#9;self._component_library = list(library)<br>
<br>
&#9;def current_component(self) -&gt; Optional[Component]:<br>
&#9;&#9;if self._entity is None:<br>
&#9;&#9;&#9;return None<br>
&#9;&#9;row = self._list.currentRow()<br>
&#9;&#9;if row &lt; 0 or row &gt;= len(self._entity.components):<br>
&#9;&#9;&#9;return None<br>
&#9;&#9;return self._entity.components[row]<br>
<br>
&#9;def _on_context_menu(self, pos):<br>
&#9;&#9;if self._entity is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;global_pos = self._list.mapToGlobal(pos)<br>
&#9;&#9;menu = QMenu(self)<br>
<br>
&#9;&#9;comp = self.current_component()<br>
&#9;&#9;remove_action = QAction(&quot;Удалить компонент&quot;, self)<br>
&#9;&#9;remove_action.setEnabled(comp is not None)<br>
&#9;&#9;remove_action.triggered.connect(self._remove_current_component)<br>
&#9;&#9;menu.addAction(remove_action)<br>
<br>
&#9;&#9;if self._component_library:<br>
&#9;&#9;&#9;add_menu = menu.addMenu(&quot;Добавить компонент&quot;)<br>
&#9;&#9;&#9;for label, cls in self._component_library:<br>
&#9;&#9;&#9;&#9;act = QAction(label, self)<br>
&#9;&#9;&#9;&#9;act.triggered.connect(<br>
&#9;&#9;&#9;&#9;&#9;lambda _checked=False, c=cls: self._add_component(c)<br>
&#9;&#9;&#9;&#9;)<br>
&#9;&#9;&#9;&#9;add_menu.addAction(act)<br>
<br>
&#9;&#9;menu.exec_(global_pos)<br>
<br>
&#9;def _remove_current_component(self):<br>
&#9;&#9;if self._entity is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;comp = self.current_component()<br>
&#9;&#9;if comp is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;self._entity.remove_component(comp)<br>
&#9;&#9;self.set_entity(self._entity)<br>
&#9;&#9;self.components_changed.emit()<br>
<br>
&#9;def _add_component(self, comp_cls: type[Component]):<br>
&#9;&#9;if self._entity is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;try:<br>
&#9;&#9;&#9;comp = comp_cls()<br>
&#9;&#9;except TypeError as e:<br>
&#9;&#9;&#9;print(f&quot;Не удалось создать компонент {comp_cls}: {e}&quot;)<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;self._entity.add_component(comp)<br>
&#9;&#9;self.set_entity(self._entity)<br>
<br>
&#9;&#9;row = len(self._entity.components) - 1<br>
&#9;&#9;if row &gt;= 0:<br>
&#9;&#9;&#9;self._list.setCurrentRow(row)<br>
<br>
&#9;&#9;self.components_changed.emit()<br>
<br>
<br>
class ComponentInspectorPanel(QWidget):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Рисует форму для одного компонента на основе component.inspect_fields.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;component_changed = pyqtSignal()<br>
<br>
&#9;def __init__(self, resources: ResourceManager, parent: Optional[QWidget] = None):<br>
&#9;&#9;super().__init__(parent)<br>
&#9;&#9;self._component: Optional[Component] = None<br>
&#9;&#9;self._fields: dict[str, InspectField] = {}<br>
&#9;&#9;self._widgets: dict[str, QWidget] = {}<br>
&#9;&#9;self._updating_from_model = False<br>
&#9;&#9;self._resources = resources<br>
<br>
&#9;&#9;layout = QFormLayout(self)<br>
&#9;&#9;layout.setLabelAlignment(Qt.AlignLeft)<br>
&#9;&#9;layout.setFormAlignment(Qt.AlignTop)<br>
&#9;&#9;self._layout = layout<br>
<br>
&#9;def set_component(self, comp: Optional[Component]):<br>
&#9;&#9;for i in reversed(range(self._layout.count())):<br>
&#9;&#9;&#9;item = self._layout.itemAt(i)<br>
&#9;&#9;&#9;w = item.widget()<br>
&#9;&#9;&#9;if w is not None:<br>
&#9;&#9;&#9;&#9;w.setParent(None)<br>
<br>
&#9;&#9;self._widgets.clear()<br>
&#9;&#9;self._component = comp<br>
<br>
&#9;&#9;if comp is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;fields = getattr(comp.__class__, &quot;inspect_fields&quot;, None)<br>
&#9;&#9;if not fields:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;self._fields = fields<br>
<br>
&#9;&#9;self._updating_from_model = True<br>
&#9;&#9;try:<br>
&#9;&#9;&#9;for key, field in fields.items():<br>
&#9;&#9;&#9;&#9;label = field.label or key<br>
&#9;&#9;&#9;&#9;widget = self._create_widget_for_field(field)<br>
&#9;&#9;&#9;&#9;self._widgets[key] = widget<br>
&#9;&#9;&#9;&#9;self._layout.addRow(QLabel(label), widget)<br>
<br>
&#9;&#9;&#9;&#9;value = field.get_value(comp)<br>
&#9;&#9;&#9;&#9;self._set_widget_value(widget, value, field)<br>
&#9;&#9;&#9;&#9;self._connect_widget(widget, key, field)<br>
&#9;&#9;finally:<br>
&#9;&#9;&#9;self._updating_from_model = False<br>
<br>
&#9;def _create_widget_for_field(self, field: InspectField) -&gt; QWidget:<br>
&#9;&#9;kind = field.kind<br>
<br>
&#9;&#9;if kind in (&quot;float&quot;, &quot;int&quot;):<br>
&#9;&#9;&#9;sb = QDoubleSpinBox()<br>
&#9;&#9;&#9;sb.setDecimals(4)<br>
&#9;&#9;&#9;sb.setRange(<br>
&#9;&#9;&#9;&#9;field.min if field.min is not None else -1e9,<br>
&#9;&#9;&#9;&#9;field.max if field.max is not None else 1e9,<br>
&#9;&#9;&#9;)<br>
&#9;&#9;&#9;if field.step is not None:<br>
&#9;&#9;&#9;&#9;sb.setSingleStep(field.step)<br>
&#9;&#9;&#9;return sb<br>
<br>
&#9;&#9;if kind == &quot;bool&quot;:<br>
&#9;&#9;&#9;return QCheckBox()<br>
<br>
&#9;&#9;if kind == &quot;string&quot;:<br>
&#9;&#9;&#9;return QLineEdit()<br>
<br>
&#9;&#9;if kind == &quot;vec3&quot;:<br>
&#9;&#9;&#9;row = QWidget()<br>
&#9;&#9;&#9;hl = QHBoxLayout(row)<br>
&#9;&#9;&#9;hl.setContentsMargins(0, 0, 0, 0)<br>
&#9;&#9;&#9;hl.setSpacing(2)<br>
&#9;&#9;&#9;boxes = []<br>
&#9;&#9;&#9;for _ in range(3):<br>
&#9;&#9;&#9;&#9;sb = QDoubleSpinBox()<br>
&#9;&#9;&#9;&#9;sb.setDecimals(4)<br>
&#9;&#9;&#9;&#9;sb.setRange(<br>
&#9;&#9;&#9;&#9;&#9;field.min if field.min is not None else -1e9,<br>
&#9;&#9;&#9;&#9;&#9;field.max if field.max is not None else 1e9,<br>
&#9;&#9;&#9;&#9;)<br>
&#9;&#9;&#9;&#9;if field.step is not None:<br>
&#9;&#9;&#9;&#9;&#9;sb.setSingleStep(field.step)<br>
&#9;&#9;&#9;&#9;hl.addWidget(sb)<br>
&#9;&#9;&#9;&#9;boxes.append(sb)<br>
&#9;&#9;&#9;row._boxes = boxes  # небольшой хак<br>
&#9;&#9;&#9;return row<br>
<br>
&#9;&#9;if kind == &quot;material&quot;:<br>
&#9;&#9;&#9;combo = QComboBox()<br>
&#9;&#9;&#9;names = self._resources.list_material_names()<br>
&#9;&#9;&#9;for n in names:<br>
&#9;&#9;&#9;&#9;combo.addItem(n)<br>
&#9;&#9;&#9;return combo<br>
<br>
&#9;&#9;if kind == &quot;mesh&quot;:<br>
&#9;&#9;&#9;combo = QComboBox()<br>
&#9;&#9;&#9;names = self._resources.list_mesh_names()<br>
&#9;&#9;&#9;for n in names:<br>
&#9;&#9;&#9;&#9;combo.addItem(n)<br>
&#9;&#9;&#9;return combo<br>
<br>
&#9;&#9;le = QLineEdit()<br>
&#9;&#9;le.setReadOnly(True)<br>
&#9;&#9;return le<br>
<br>
&#9;def _set_widget_value(self, w: QWidget, value, field: InspectField):<br>
&#9;&#9;if isinstance(w, QDoubleSpinBox):<br>
&#9;&#9;&#9;w.setValue(float(value))<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if isinstance(w, QCheckBox):<br>
&#9;&#9;&#9;w.setChecked(bool(value))<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if isinstance(w, QLineEdit) and field.kind != &quot;material&quot;:<br>
&#9;&#9;&#9;w.setText(str(value))<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if hasattr(w, &quot;_boxes&quot;):<br>
&#9;&#9;&#9;arr = np.asarray(value).reshape(-1)<br>
&#9;&#9;&#9;for sb, v in zip(w._boxes, arr):<br>
&#9;&#9;&#9;&#9;sb.setValue(float(v))<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if isinstance(w, QComboBox) and field.kind == &quot;material&quot;:<br>
&#9;&#9;&#9;mat = value<br>
&#9;&#9;&#9;if mat is None:<br>
&#9;&#9;&#9;&#9;w.setCurrentIndex(-1)<br>
&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;&#9;name = self._resources.find_material_name(mat)<br>
&#9;&#9;&#9;# обновим список на всякий случай<br>
&#9;&#9;&#9;existing = [w.itemText(i) for i in range(w.count())]<br>
&#9;&#9;&#9;all_names = self._resources.list_material_names()<br>
&#9;&#9;&#9;if existing != all_names:<br>
&#9;&#9;&#9;&#9;w.clear()<br>
&#9;&#9;&#9;&#9;for n in all_names:<br>
&#9;&#9;&#9;&#9;&#9;w.addItem(n)<br>
<br>
&#9;&#9;&#9;if name is None:<br>
&#9;&#9;&#9;&#9;w.setCurrentIndex(-1)<br>
&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;&#9;idx = w.findText(name)<br>
&#9;&#9;&#9;if idx &gt;= 0:<br>
&#9;&#9;&#9;&#9;w.setCurrentIndex(idx)<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;w.setCurrentIndex(-1)<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if isinstance(w, QComboBox) and field.kind == &quot;mesh&quot;:<br>
&#9;&#9;&#9;mesh = value<br>
&#9;&#9;&#9;if mesh is None:<br>
&#9;&#9;&#9;&#9;w.setCurrentIndex(-1)<br>
&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;&#9;name = self._resources.find_mesh_name(mesh)<br>
&#9;&#9;&#9;existing = [w.itemText(i) for i in range(w.count())]<br>
&#9;&#9;&#9;all_names = self._resources.list_mesh_names()<br>
&#9;&#9;&#9;if existing != all_names:<br>
&#9;&#9;&#9;&#9;w.clear()<br>
&#9;&#9;&#9;&#9;for n in all_names:<br>
&#9;&#9;&#9;&#9;&#9;w.addItem(n)<br>
<br>
&#9;&#9;&#9;if name is None:<br>
&#9;&#9;&#9;&#9;w.setCurrentIndex(-1)<br>
&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;&#9;idx = w.findText(name)<br>
&#9;&#9;&#9;if idx &gt;= 0:<br>
&#9;&#9;&#9;&#9;w.setCurrentIndex(idx)<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;w.setCurrentIndex(-1)<br>
&#9;&#9;&#9;return<br>
<br>
&#9;def _connect_widget(self, w: QWidget, key: str, field: InspectField):<br>
&#9;&#9;def commit():<br>
&#9;&#9;&#9;if self._updating_from_model or self._component is None:<br>
&#9;&#9;&#9;&#9;return<br>
&#9;&#9;&#9;val = self._read_widget_value(w, field)<br>
&#9;&#9;&#9;field.set_value(self._component, val)<br>
&#9;&#9;&#9;self.component_changed.emit()<br>
<br>
&#9;&#9;if isinstance(w, QDoubleSpinBox):<br>
&#9;&#9;&#9;w.valueChanged.connect(lambda _v: commit())<br>
&#9;&#9;elif isinstance(w, QCheckBox):<br>
&#9;&#9;&#9;w.stateChanged.connect(lambda _s: commit())<br>
&#9;&#9;elif isinstance(w, QLineEdit) and field.kind != &quot;material&quot;:<br>
&#9;&#9;&#9;w.editingFinished.connect(commit)<br>
&#9;&#9;elif hasattr(w, &quot;_boxes&quot;):<br>
&#9;&#9;&#9;for sb in w._boxes:<br>
&#9;&#9;&#9;&#9;sb.valueChanged.connect(lambda _v: commit())      <br>
&#9;&#9;elif isinstance(w, QComboBox) and field.kind in (&quot;material&quot;, &quot;mesh&quot;):<br>
&#9;&#9;&#9;w.currentIndexChanged.connect(lambda _i: commit())<br>
<br>
&#9;def _read_widget_value(self, w: QWidget, field: InspectField):<br>
&#9;&#9;if isinstance(w, QDoubleSpinBox):<br>
&#9;&#9;&#9;return float(w.value())<br>
<br>
&#9;&#9;if isinstance(w, QCheckBox):<br>
&#9;&#9;&#9;return bool(w.isChecked())<br>
<br>
&#9;&#9;if isinstance(w, QLineEdit) and field.kind != &quot;material&quot;:<br>
&#9;&#9;&#9;return w.text()<br>
<br>
&#9;&#9;if hasattr(w, &quot;_boxes&quot;):<br>
&#9;&#9;&#9;return np.array([sb.value() for sb in w._boxes], dtype=float)<br>
<br>
&#9;&#9;if isinstance(w, QComboBox) and field.kind == &quot;material&quot;:<br>
&#9;&#9;&#9;name = w.currentText()<br>
&#9;&#9;&#9;if not name:<br>
&#9;&#9;&#9;&#9;return None<br>
&#9;&#9;&#9;return self._resources.get_material(name)<br>
<br>
&#9;&#9;if isinstance(w, QComboBox) and field.kind == &quot;mesh&quot;:<br>
&#9;&#9;&#9;name = w.currentText()<br>
&#9;&#9;&#9;if not name:<br>
&#9;&#9;&#9;&#9;return None<br>
&#9;&#9;&#9;return self._resources.get_mesh(name)<br>
<br>
&#9;&#9;return None<br>
<br>
<br>
class EntityInspector(QWidget):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Общий инспектор для Entity/Transform:<br>
&#9;сверху TransformInspector, ниже список компонентов, ещё ниже – инспектор компонента.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;transform_changed = pyqtSignal()<br>
&#9;component_changed = pyqtSignal()<br>
<br>
&#9;def __init__(self, resources: ResourceManager, parent: Optional[QWidget] = None):<br>
&#9;&#9;super().__init__(parent)<br>
<br>
&#9;&#9;self._resources = resources<br>
<br>
&#9;&#9;layout = QVBoxLayout(self)<br>
&#9;&#9;layout.setContentsMargins(0, 0, 0, 0)<br>
&#9;&#9;layout.setSpacing(4)<br>
<br>
&#9;&#9;self._transform_inspector = TransformInspector(self)<br>
&#9;&#9;layout.addWidget(self._transform_inspector)<br>
<br>
&#9;&#9;self._components_panel = ComponentsPanel(self)<br>
&#9;&#9;layout.addWidget(self._components_panel)<br>
<br>
&#9;&#9;self._component_inspector = ComponentInspectorPanel(resources, self)<br>
&#9;&#9;layout.addWidget(self._component_inspector)<br>
<br>
&#9;&#9;self._entity: Optional[Entity] = None<br>
<br>
&#9;&#9;self._transform_inspector.transform_changed.connect(<br>
&#9;&#9;&#9;self.transform_changed<br>
&#9;&#9;)<br>
&#9;&#9;self._components_panel._list.currentRowChanged.connect(<br>
&#9;&#9;&#9;self._on_component_selected<br>
&#9;&#9;)<br>
&#9;&#9;self._component_inspector.component_changed.connect(<br>
&#9;&#9;&#9;self._on_component_changed<br>
&#9;&#9;)<br>
&#9;&#9;self._components_panel.components_changed.connect(<br>
&#9;&#9;&#9;self._on_components_changed<br>
&#9;&#9;)<br>
<br>
&#9;def _on_components_changed(self):<br>
&#9;&#9;ent = self._entity<br>
&#9;&#9;self._components_panel.set_entity(ent)<br>
<br>
&#9;&#9;if ent is not None:<br>
&#9;&#9;&#9;row = self._components_panel._list.currentRow()<br>
&#9;&#9;&#9;if 0 &lt;= row &lt; len(ent.components):<br>
&#9;&#9;&#9;&#9;self._component_inspector.set_component(ent.components[row])<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;self._component_inspector.set_component(None)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;self._component_inspector.set_component(None)<br>
<br>
&#9;&#9;self.component_changed.emit()<br>
<br>
&#9;def set_component_library(self, library: list[tuple[str, type[Component]]]):<br>
&#9;&#9;self._components_panel.set_component_library(library)<br>
<br>
&#9;def _on_component_changed(self):<br>
&#9;&#9;self.component_changed.emit()<br>
<br>
&#9;def set_target(self, obj: Optional[object]):<br>
&#9;&#9;if isinstance(obj, Entity):<br>
&#9;&#9;&#9;ent = obj<br>
&#9;&#9;&#9;trans = obj.transform<br>
&#9;&#9;elif isinstance(obj, Transform3):<br>
&#9;&#9;&#9;trans = obj<br>
&#9;&#9;&#9;ent = getattr(obj, &quot;entity&quot;, None)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;ent = None<br>
&#9;&#9;&#9;trans = None<br>
<br>
&#9;&#9;self._entity = ent<br>
<br>
&#9;&#9;self._transform_inspector.set_target(trans or ent)<br>
&#9;&#9;self._components_panel.set_entity(ent)<br>
&#9;&#9;self._component_inspector.set_component(None)<br>
<br>
&#9;def _on_component_selected(self, row: int):<br>
&#9;&#9;if self._entity is None or row &lt; 0:<br>
&#9;&#9;&#9;self._component_inspector.set_component(None)<br>
&#9;&#9;&#9;return<br>
&#9;&#9;comp = self._entity.components[row]<br>
&#9;&#9;self._component_inspector.set_component(comp)<br>
<!-- END SCAT CODE -->
</body>
</html>
