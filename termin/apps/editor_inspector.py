# ===== termin/apps/editor_inspector.py =====
from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt5.QtWidgets import (
    QWidget,
    QFormLayout,
    QHBoxLayout,
    QDoubleSpinBox,
    QLabel,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QLineEdit,
    QMenu,
    QAction,
)

from PyQt5.QtCore import Qt, pyqtSignal

from termin.kinematic.transform import Transform3
from termin.visualization.entity import Entity, Component
from termin.geombase.pose3 import Pose3
from termin.visualization.inspect import InspectField


class TransformInspector(QWidget):
    """
    Мини-инспектор Transform:
    - position (x, y, z)
    - rotation (x, y, z) в градусах — пока только отображаем / заготовка
    - scale (x, y, z) — опционально, если Transform3 это поддерживает
    """

    transform_changed = pyqtSignal()  # сообщаем наверх, что трансформ поменяли

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._transform: Optional[Transform3] = None
        self._updating_from_model = False  # защита от рекурсий

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignLeft)
        layout.setFormAlignment(Qt.AlignTop)

        # --- helpers для тройки спинбоксов ---
        def make_vec3_row():
            row = QHBoxLayout()
            sx = QDoubleSpinBox()
            sy = QDoubleSpinBox()
            sz = QDoubleSpinBox()
            for sb in (sx, sy, sz):
                sb.setRange(-1e6, 1e6)
                sb.setDecimals(3)
                sb.setSingleStep(0.1)
                row.addWidget(sb)
            return row, (sx, sy, sz)

        # position
        pos_row, self._pos = make_vec3_row()
        layout.addRow(QLabel("Position"), pos_row)

        # rotation (Euler degrees – заглушка)
        rot_row, self._rot = make_vec3_row()
        layout.addRow(QLabel("Rotation (deg)"), rot_row)

        # scale (по умолчанию 1,1,1)
        scale_row, self._scale = make_vec3_row()
        for sb in self._scale:
            sb.setValue(1.0)
        layout.addRow(QLabel("Scale"), scale_row)

        # сигналы
        for sb in (*self._pos, *self._rot, *self._scale):
            sb.valueChanged.connect(self._on_value_changed)

        self._set_enabled(False)

    # --------------------------------------------------------
    #   Публичный API
    # --------------------------------------------------------

    def set_target(self, obj: Optional[object]):
        """
        Принимает либо Entity, либо Transform3, либо None.
        """
        if isinstance(obj, Entity):
            transform = obj.transform
        elif isinstance(obj, Transform3):
            transform = obj
        else:
            transform = None

        self._transform = transform
        self._update_from_transform()

    # --------------------------------------------------------
    #   Внутреннее
    # --------------------------------------------------------

    def _set_enabled(self, flag: bool):
        for sb in (*self._pos, *self._rot, *self._scale):
            sb.setEnabled(flag)

    def _update_from_transform(self):
        self._updating_from_model = True
        try:
            if self._transform is None:
                self._set_enabled(False)
                for sb in (*self._pos, *self._rot, *self._scale):
                    sb.setValue(0.0)
                for sb in self._scale:
                    sb.setValue(1.0)
                return

            self._set_enabled(True)

            pose: Pose3 = self._transform.global_pose()

            # --- position ---
            px, py, pz = pose.lin
            self._pos[0].setValue(float(px))
            self._pos[1].setValue(float(py))
            self._pos[2].setValue(float(pz))

            # --- rotation ---
            # Здесь можно потом использовать Pose3.to_euler()
            self._rot[0].setValue(0.0)
            self._rot[1].setValue(0.0)
            self._rot[2].setValue(0.0)

            # --- scale ---
            s = np.array([1.0, 1.0, 1.0], dtype=float)
            self._scale[0].setValue(float(s[0]))
            self._scale[1].setValue(float(s[1]))
            self._scale[2].setValue(float(s[2]))

        finally:
            self._updating_from_model = False

    def _on_value_changed(self, _value):
        if self._updating_from_model:
            return
        if self._transform is None:
            return

        pose: Pose3 = self._transform.global_pose()

        px = self._pos[0].value()
        py = self._pos[1].value()
        pz = self._pos[2].value()
        new_lin = np.array([px, py, pz], dtype=float)

        pose = Pose3(lin=new_lin, ang=pose.ang)
        self._transform.relocate(pose)
        self.transform_changed.emit()


class ComponentsPanel(QWidget):
    """
    Просто список компонентов entity + контекстное меню (добавить/удалить).
    """
    components_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        self._title = QLabel("Components")
        layout.addWidget(self._title)

        self._list = QListWidget()
        layout.addWidget(self._list)

        self._entity: Optional[Entity] = None
        self._component_library: list[tuple[str, type[Component]]] = []

        # контекстное меню по правому клику
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)

    def set_entity(self, ent: Optional[Entity]):
        self._entity = ent
        self._list.clear()
        if ent is None:
            return
        for comp in ent.components:
            name = comp.__class__.__name__
            item = QListWidgetItem(name)
            self._list.addItem(item)

    def set_component_library(self, library: list[tuple[str, type[Component]]]):
        """
        library: список (label, ComponentClass), которые можно добавить.
        """
        self._component_library = list(library)

    def current_component(self) -> Optional[Component]:
        if self._entity is None:
            return None
        row = self._list.currentRow()
        if row < 0 or row >= len(self._entity.components):
            return None
        return self._entity.components[row]

    # ---------------------------------------------------------
    #   Контекстное меню
    # ---------------------------------------------------------
    def _on_context_menu(self, pos):
        if self._entity is None:
            return

        global_pos = self._list.mapToGlobal(pos)
        menu = QMenu(self)

        # удалить компонент
        comp = self.current_component()
        remove_action = QAction("Удалить компонент", self)
        remove_action.setEnabled(comp is not None)
        remove_action.triggered.connect(self._remove_current_component)
        menu.addAction(remove_action)

        # добавить компонент
        if self._component_library:
            add_menu = menu.addMenu("Добавить компонент")
            for label, cls in self._component_library:
                act = QAction(label, self)
                # нужно аккуратно захватить cls в замыкание
                act.triggered.connect(
                    lambda _checked=False, c=cls: self._add_component(c)
                )
                add_menu.addAction(act)

        menu.exec_(global_pos)

    def _remove_current_component(self):
        if self._entity is None:
            return
        comp = self.current_component()
        if comp is None:
            return

        # удаляем из entity
        self._entity.remove_component(comp)
        # обновляем список
        self.set_entity(self._entity)
        self.components_changed.emit()

    def _add_component(self, comp_cls: type[Component]):
        if self._entity is None:
            return
        try:
            comp = comp_cls()  # предполагаем, что есть конструктор без аргументов
        except TypeError as e:
            print(f"Не удалось создать компонент {comp_cls}: {e}")
            return

        self._entity.add_component(comp)
        self.set_entity(self._entity)

        # выделяем добавленный компонент
        row = len(self._entity.components) - 1
        if row >= 0:
            self._list.setCurrentRow(row)

        self.components_changed.emit()



class ComponentInspectorPanel(QWidget):
    """
    Рисует форму для одного компонента на основе component.inspect_fields.
    """

    component_changed = pyqtSignal()

    def __init__(self, parent: Optional[Widget] = None):
        super().__init__(parent)
        self._component: Optional[Component] = None
        self._fields: dict[str, InspectField] = {}
        self._widgets: dict[str, QWidget] = {}
        self._updating_from_model = False

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignLeft)
        layout.setFormAlignment(Qt.AlignTop)
        self._layout = layout

    def set_component(self, comp: Optional[Component]):
        # чистим старые виджеты
        for i in reversed(range(self._layout.count())):
            item = self._layout.itemAt(i)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        self._widgets.clear()
        self._component = comp

        if comp is None:
            return

        fields = getattr(comp.__class__, "inspect_fields", None)
        if not fields:
            return

        self._fields = fields

        self._updating_from_model = True
        try:
            for key, field in fields.items():
                label = field.label or key
                widget = self._create_widget_for_field(field)
                self._widgets[key] = widget
                self._layout.addRow(QLabel(label), widget)

                value = field.get_value(comp)
                self._set_widget_value(widget, value, field)
                self._connect_widget(widget, key, field)
        finally:
            self._updating_from_model = False

    # --- виджеты под разные kind ---

    def _create_widget_for_field(self, field: InspectField) -> QWidget:
        kind = field.kind

        if kind in ("float", "int"):
            sb = QDoubleSpinBox()
            sb.setDecimals(4)
            sb.setRange(
                field.min if field.min is not None else -1e9,
                field.max if field.max is not None else 1e9,
            )
            if field.step is not None:
                sb.setSingleStep(field.step)
            return sb

        if kind == "bool":
            return QCheckBox()

        if kind == "string":
            return QLineEdit()

        if kind == "vec3":
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(2)
            boxes = []
            for _ in range(3):
                sb = QDoubleSpinBox()
                sb.setDecimals(4)
                sb.setRange(
                    field.min if field.min is not None else -1e9,
                    field.max if field.max is not None else 1e9,
                )
                if field.step is not None:
                    sb.setSingleStep(field.step)
                hl.addWidget(sb)
                boxes.append(sb)
            row._boxes = boxes  # небольшой хак
            return row

        # TODO: color / enum
        le = QLineEdit()
        le.setReadOnly(True)
        return le

    def _set_widget_value(self, w: QWidget, value, field: InspectField):
        if isinstance(w, QDoubleSpinBox):
            w.setValue(float(value))
            return

        if isinstance(w, QCheckBox):
            w.setChecked(bool(value))
            return

        if isinstance(w, QLineEdit):
            w.setText(str(value))
            return

        if hasattr(w, "_boxes"):
            arr = np.asarray(value).reshape(-1)
            for sb, v in zip(w._boxes, arr):
                sb.setValue(float(v))
            return

    def _connect_widget(self, w: QWidget, key: str, field: InspectField):
        def commit():
            if self._updating_from_model or self._component is None:
                return
            val = self._read_widget_value(w, field)
            field.set_value(self._component, val)

            self.component_changed.emit()

        if isinstance(w, QDoubleSpinBox):
            w.valueChanged.connect(lambda _v: commit())
        elif isinstance(w, QCheckBox):
            w.stateChanged.connect(lambda _s: commit())
        elif isinstance(w, QLineEdit):
            w.editingFinished.connect(commit)
        elif hasattr(w, "_boxes"):
            for sb in w._boxes:
                sb.valueChanged.connect(lambda _v: commit())

    def _read_widget_value(self, w: QWidget, field: InspectField):
        if isinstance(w, QDoubleSpinBox):
            return float(w.value())

        if isinstance(w, QCheckBox):
            return bool(w.isChecked())

        if isinstance(w, QLineEdit):
            return w.text()

        if hasattr(w, "_boxes"):
            return np.array([sb.value() for sb in w._boxes], dtype=float)

        return None


class EntityInspector(QWidget):
    """
    Общий инспектор для Entity/Transform:
    сверху TransformInspector, ниже список компонентов, ещё ниже – инспектор компонента.
    """

    transform_changed = pyqtSignal()
    component_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._transform_inspector = TransformInspector(self)
        layout.addWidget(self._transform_inspector)

        self._components_panel = ComponentsPanel(self)
        layout.addWidget(self._components_panel)

        self._component_inspector = ComponentInspectorPanel(self)
        layout.addWidget(self._component_inspector)

        self._entity: Optional[Entity] = None


        self._transform_inspector.transform_changed.connect(
            self.transform_changed
        )

        self._components_panel._list.currentRowChanged.connect(
            self._on_component_selected
        )

        self._component_inspector.component_changed.connect(
            self._on_component_changed
        )

        self._components_panel.components_changed.connect(
            self._on_components_changed
        )

    def _on_components_changed(self):
        """
        Список компонентов изменился (добавили/удалили).
        Обновляем список и инспектор, пробрасываем наружу сигнал component_changed.
        """
        ent = self._entity
        self._components_panel.set_entity(ent)

        if ent is not None:
            row = self._components_panel._list.currentRow()
            if 0 <= row < len(ent.components):
                self._component_inspector.set_component(ent.components[row])
            else:
                self._component_inspector.set_component(None)
        else:
            self._component_inspector.set_component(None)

        self.component_changed.emit()
        
    def set_component_library(self, library: list[tuple[str, type[Component]]]):
        """
        Передаём внутрь список типов компонентов, доступных для добавления.
        """
        self._components_panel.set_component_library(library)

    def _on_component_changed(self):
        self.component_changed.emit()


    def set_target(self, obj: Optional[object]):
        """
        Принимает Entity, Transform3 или None.
        """
        if isinstance(obj, Entity):
            ent = obj
            trans = obj.transform
        elif isinstance(obj, Transform3):
            trans = obj
            ent = getattr(obj, "entity", None)
        else:
            ent = None
            trans = None

        self._entity = ent

        self._transform_inspector.set_target(trans or ent)
        self._components_panel.set_entity(ent)
        self._component_inspector.set_component(None)

    def _on_component_selected(self, row: int):
        if self._entity is None or row < 0:
            self._component_inspector.set_component(None)
            return
        comp = self._entity.components[row]
        self._component_inspector.set_component(comp)
