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
    QWidget,<br>
    QFormLayout,<br>
    QHBoxLayout,<br>
    QDoubleSpinBox,<br>
    QLabel,<br>
    QVBoxLayout,<br>
    QListWidget,<br>
    QListWidgetItem,<br>
    QCheckBox,<br>
    QLineEdit,<br>
    QMenu,<br>
    QAction,<br>
    QComboBox,<br>
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
    components_changed = pyqtSignal()<br>
<br>
    def __init__(self, parent: Optional[QWidget] = None):<br>
        super().__init__(parent)<br>
<br>
        layout = QVBoxLayout(self)<br>
        layout.setContentsMargins(0, 8, 0, 0)<br>
        layout.setSpacing(4)<br>
<br>
        self._title = QLabel(&quot;Components&quot;)<br>
        layout.addWidget(self._title)<br>
<br>
        self._list = QListWidget()<br>
        layout.addWidget(self._list)<br>
<br>
        self._entity: Optional[Entity] = None<br>
        self._component_library: list[tuple[str, type[Component]]] = []<br>
<br>
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)<br>
        self._list.customContextMenuRequested.connect(self._on_context_menu)<br>
<br>
    def set_entity(self, ent: Optional[Entity]):<br>
        self._entity = ent<br>
        self._list.clear()<br>
        if ent is None:<br>
            return<br>
        for comp in ent.components:<br>
            name = comp.__class__.__name__<br>
            item = QListWidgetItem(name)<br>
            self._list.addItem(item)<br>
<br>
    def set_component_library(self, library: list[tuple[str, type[Component]]]):<br>
        self._component_library = list(library)<br>
<br>
    def current_component(self) -&gt; Optional[Component]:<br>
        if self._entity is None:<br>
            return None<br>
        row = self._list.currentRow()<br>
        if row &lt; 0 or row &gt;= len(self._entity.components):<br>
            return None<br>
        return self._entity.components[row]<br>
<br>
    def _on_context_menu(self, pos):<br>
        if self._entity is None:<br>
            return<br>
<br>
        global_pos = self._list.mapToGlobal(pos)<br>
        menu = QMenu(self)<br>
<br>
        comp = self.current_component()<br>
        remove_action = QAction(&quot;Удалить компонент&quot;, self)<br>
        remove_action.setEnabled(comp is not None)<br>
        remove_action.triggered.connect(self._remove_current_component)<br>
        menu.addAction(remove_action)<br>
<br>
        if self._component_library:<br>
            add_menu = menu.addMenu(&quot;Добавить компонент&quot;)<br>
            for label, cls in self._component_library:<br>
                act = QAction(label, self)<br>
                act.triggered.connect(<br>
                    lambda _checked=False, c=cls: self._add_component(c)<br>
                )<br>
                add_menu.addAction(act)<br>
<br>
        menu.exec_(global_pos)<br>
<br>
    def _remove_current_component(self):<br>
        if self._entity is None:<br>
            return<br>
        comp = self.current_component()<br>
        if comp is None:<br>
            return<br>
<br>
        self._entity.remove_component(comp)<br>
        self.set_entity(self._entity)<br>
        self.components_changed.emit()<br>
<br>
    def _add_component(self, comp_cls: type[Component]):<br>
        if self._entity is None:<br>
            return<br>
        try:<br>
            comp = comp_cls()<br>
        except TypeError as e:<br>
            print(f&quot;Не удалось создать компонент {comp_cls}: {e}&quot;)<br>
            return<br>
<br>
        self._entity.add_component(comp)<br>
        self.set_entity(self._entity)<br>
<br>
        row = len(self._entity.components) - 1<br>
        if row &gt;= 0:<br>
            self._list.setCurrentRow(row)<br>
<br>
        self.components_changed.emit()<br>
<br>
<br>
class ComponentInspectorPanel(QWidget):<br>
    &quot;&quot;&quot;<br>
    Рисует форму для одного компонента на основе component.inspect_fields.<br>
    &quot;&quot;&quot;<br>
<br>
    component_changed = pyqtSignal()<br>
<br>
    def __init__(self, resources: ResourceManager, parent: Optional[QWidget] = None):<br>
        super().__init__(parent)<br>
        self._component: Optional[Component] = None<br>
        self._fields: dict[str, InspectField] = {}<br>
        self._widgets: dict[str, QWidget] = {}<br>
        self._updating_from_model = False<br>
        self._resources = resources<br>
<br>
        layout = QFormLayout(self)<br>
        layout.setLabelAlignment(Qt.AlignLeft)<br>
        layout.setFormAlignment(Qt.AlignTop)<br>
        self._layout = layout<br>
<br>
    def set_component(self, comp: Optional[Component]):<br>
        for i in reversed(range(self._layout.count())):<br>
            item = self._layout.itemAt(i)<br>
            w = item.widget()<br>
            if w is not None:<br>
                w.setParent(None)<br>
<br>
        self._widgets.clear()<br>
        self._component = comp<br>
<br>
        if comp is None:<br>
            return<br>
<br>
        fields = getattr(comp.__class__, &quot;inspect_fields&quot;, None)<br>
        if not fields:<br>
            return<br>
<br>
        self._fields = fields<br>
<br>
        self._updating_from_model = True<br>
        try:<br>
            for key, field in fields.items():<br>
                label = field.label or key<br>
                widget = self._create_widget_for_field(field)<br>
                self._widgets[key] = widget<br>
                self._layout.addRow(QLabel(label), widget)<br>
<br>
                value = field.get_value(comp)<br>
                self._set_widget_value(widget, value, field)<br>
                self._connect_widget(widget, key, field)<br>
        finally:<br>
            self._updating_from_model = False<br>
<br>
    def _create_widget_for_field(self, field: InspectField) -&gt; QWidget:<br>
        kind = field.kind<br>
<br>
        if kind in (&quot;float&quot;, &quot;int&quot;):<br>
            sb = QDoubleSpinBox()<br>
            sb.setDecimals(4)<br>
            sb.setRange(<br>
                field.min if field.min is not None else -1e9,<br>
                field.max if field.max is not None else 1e9,<br>
            )<br>
            if field.step is not None:<br>
                sb.setSingleStep(field.step)<br>
            return sb<br>
<br>
        if kind == &quot;bool&quot;:<br>
            return QCheckBox()<br>
<br>
        if kind == &quot;string&quot;:<br>
            return QLineEdit()<br>
<br>
        if kind == &quot;vec3&quot;:<br>
            row = QWidget()<br>
            hl = QHBoxLayout(row)<br>
            hl.setContentsMargins(0, 0, 0, 0)<br>
            hl.setSpacing(2)<br>
            boxes = []<br>
            for _ in range(3):<br>
                sb = QDoubleSpinBox()<br>
                sb.setDecimals(4)<br>
                sb.setRange(<br>
                    field.min if field.min is not None else -1e9,<br>
                    field.max if field.max is not None else 1e9,<br>
                )<br>
                if field.step is not None:<br>
                    sb.setSingleStep(field.step)<br>
                hl.addWidget(sb)<br>
                boxes.append(sb)<br>
            row._boxes = boxes  # небольшой хак<br>
            return row<br>
<br>
        if kind == &quot;material&quot;:<br>
            combo = QComboBox()<br>
            names = self._resources.list_material_names()<br>
            for n in names:<br>
                combo.addItem(n)<br>
            return combo<br>
<br>
        if kind == &quot;mesh&quot;:<br>
            combo = QComboBox()<br>
            names = self._resources.list_mesh_names()<br>
            for n in names:<br>
                combo.addItem(n)<br>
            return combo<br>
<br>
        le = QLineEdit()<br>
        le.setReadOnly(True)<br>
        return le<br>
<br>
    def _set_widget_value(self, w: QWidget, value, field: InspectField):<br>
        if isinstance(w, QDoubleSpinBox):<br>
            w.setValue(float(value))<br>
            return<br>
<br>
        if isinstance(w, QCheckBox):<br>
            w.setChecked(bool(value))<br>
            return<br>
<br>
        if isinstance(w, QLineEdit) and field.kind != &quot;material&quot;:<br>
            w.setText(str(value))<br>
            return<br>
<br>
        if hasattr(w, &quot;_boxes&quot;):<br>
            arr = np.asarray(value).reshape(-1)<br>
            for sb, v in zip(w._boxes, arr):<br>
                sb.setValue(float(v))<br>
            return<br>
<br>
        if isinstance(w, QComboBox) and field.kind == &quot;material&quot;:<br>
            mat = value<br>
            if mat is None:<br>
                w.setCurrentIndex(-1)<br>
                return<br>
<br>
            name = self._resources.find_material_name(mat)<br>
            # обновим список на всякий случай<br>
            existing = [w.itemText(i) for i in range(w.count())]<br>
            all_names = self._resources.list_material_names()<br>
            if existing != all_names:<br>
                w.clear()<br>
                for n in all_names:<br>
                    w.addItem(n)<br>
<br>
            if name is None:<br>
                w.setCurrentIndex(-1)<br>
                return<br>
<br>
            idx = w.findText(name)<br>
            if idx &gt;= 0:<br>
                w.setCurrentIndex(idx)<br>
            else:<br>
                w.setCurrentIndex(-1)<br>
            return<br>
<br>
        if isinstance(w, QComboBox) and field.kind == &quot;mesh&quot;:<br>
            mesh = value<br>
            if mesh is None:<br>
                w.setCurrentIndex(-1)<br>
                return<br>
<br>
            name = self._resources.find_mesh_name(mesh)<br>
            existing = [w.itemText(i) for i in range(w.count())]<br>
            all_names = self._resources.list_mesh_names()<br>
            if existing != all_names:<br>
                w.clear()<br>
                for n in all_names:<br>
                    w.addItem(n)<br>
<br>
            if name is None:<br>
                w.setCurrentIndex(-1)<br>
                return<br>
<br>
            idx = w.findText(name)<br>
            if idx &gt;= 0:<br>
                w.setCurrentIndex(idx)<br>
            else:<br>
                w.setCurrentIndex(-1)<br>
            return<br>
<br>
    def _connect_widget(self, w: QWidget, key: str, field: InspectField):<br>
        def commit():<br>
            if self._updating_from_model or self._component is None:<br>
                return<br>
            val = self._read_widget_value(w, field)<br>
            field.set_value(self._component, val)<br>
            self.component_changed.emit()<br>
<br>
        if isinstance(w, QDoubleSpinBox):<br>
            w.valueChanged.connect(lambda _v: commit())<br>
        elif isinstance(w, QCheckBox):<br>
            w.stateChanged.connect(lambda _s: commit())<br>
        elif isinstance(w, QLineEdit) and field.kind != &quot;material&quot;:<br>
            w.editingFinished.connect(commit)<br>
        elif hasattr(w, &quot;_boxes&quot;):<br>
            for sb in w._boxes:<br>
                sb.valueChanged.connect(lambda _v: commit())      <br>
        elif isinstance(w, QComboBox) and field.kind in (&quot;material&quot;, &quot;mesh&quot;):<br>
            w.currentIndexChanged.connect(lambda _i: commit())<br>
<br>
    def _read_widget_value(self, w: QWidget, field: InspectField):<br>
        if isinstance(w, QDoubleSpinBox):<br>
            return float(w.value())<br>
<br>
        if isinstance(w, QCheckBox):<br>
            return bool(w.isChecked())<br>
<br>
        if isinstance(w, QLineEdit) and field.kind != &quot;material&quot;:<br>
            return w.text()<br>
<br>
        if hasattr(w, &quot;_boxes&quot;):<br>
            return np.array([sb.value() for sb in w._boxes], dtype=float)<br>
<br>
        if isinstance(w, QComboBox) and field.kind == &quot;material&quot;:<br>
            name = w.currentText()<br>
            if not name:<br>
                return None<br>
            return self._resources.get_material(name)<br>
<br>
        if isinstance(w, QComboBox) and field.kind == &quot;mesh&quot;:<br>
            name = w.currentText()<br>
            if not name:<br>
                return None<br>
            return self._resources.get_mesh(name)<br>
<br>
        return None<br>
<br>
<br>
class EntityInspector(QWidget):<br>
    &quot;&quot;&quot;<br>
    Общий инспектор для Entity/Transform:<br>
    сверху TransformInspector, ниже список компонентов, ещё ниже – инспектор компонента.<br>
    &quot;&quot;&quot;<br>
<br>
    transform_changed = pyqtSignal()<br>
    component_changed = pyqtSignal()<br>
<br>
    def __init__(self, resources: ResourceManager, parent: Optional[QWidget] = None):<br>
        super().__init__(parent)<br>
<br>
        self._resources = resources<br>
<br>
        layout = QVBoxLayout(self)<br>
        layout.setContentsMargins(0, 0, 0, 0)<br>
        layout.setSpacing(4)<br>
<br>
        self._transform_inspector = TransformInspector(self)<br>
        layout.addWidget(self._transform_inspector)<br>
<br>
        self._components_panel = ComponentsPanel(self)<br>
        layout.addWidget(self._components_panel)<br>
<br>
        self._component_inspector = ComponentInspectorPanel(resources, self)<br>
        layout.addWidget(self._component_inspector)<br>
<br>
        self._entity: Optional[Entity] = None<br>
<br>
        self._transform_inspector.transform_changed.connect(<br>
            self.transform_changed<br>
        )<br>
        self._components_panel._list.currentRowChanged.connect(<br>
            self._on_component_selected<br>
        )<br>
        self._component_inspector.component_changed.connect(<br>
            self._on_component_changed<br>
        )<br>
        self._components_panel.components_changed.connect(<br>
            self._on_components_changed<br>
        )<br>
<br>
    def _on_components_changed(self):<br>
        ent = self._entity<br>
        self._components_panel.set_entity(ent)<br>
<br>
        if ent is not None:<br>
            row = self._components_panel._list.currentRow()<br>
            if 0 &lt;= row &lt; len(ent.components):<br>
                self._component_inspector.set_component(ent.components[row])<br>
            else:<br>
                self._component_inspector.set_component(None)<br>
        else:<br>
            self._component_inspector.set_component(None)<br>
<br>
        self.component_changed.emit()<br>
<br>
    def set_component_library(self, library: list[tuple[str, type[Component]]]):<br>
        self._components_panel.set_component_library(library)<br>
<br>
    def _on_component_changed(self):<br>
        self.component_changed.emit()<br>
<br>
    def set_target(self, obj: Optional[object]):<br>
        if isinstance(obj, Entity):<br>
            ent = obj<br>
            trans = obj.transform<br>
        elif isinstance(obj, Transform3):<br>
            trans = obj<br>
            ent = getattr(obj, &quot;entity&quot;, None)<br>
        else:<br>
            ent = None<br>
            trans = None<br>
<br>
        self._entity = ent<br>
<br>
        self._transform_inspector.set_target(trans or ent)<br>
        self._components_panel.set_entity(ent)<br>
        self._component_inspector.set_component(None)<br>
<br>
    def _on_component_selected(self, row: int):<br>
        if self._entity is None or row &lt; 0:<br>
            self._component_inspector.set_component(None)<br>
            return<br>
        comp = self._entity.components[row]<br>
        self._component_inspector.set_component(comp)<br>
<!-- END SCAT CODE -->
</body>
</html>
