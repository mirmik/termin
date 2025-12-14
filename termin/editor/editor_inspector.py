# ===== termin/editor/editor_inspector.py =====
from __future__ import annotations

from typing import Optional, Callable
import logging

import numpy as np
from PyQt6.QtWidgets import (
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
    QComboBox,
    QPushButton,
    QSlider,
    QSpinBox,
)
from PyQt6.QtGui import QColor, QAction
from termin.editor.color_dialog import ColorDialog
from PyQt6.QtCore import Qt, pyqtSignal

from termin.kinematic.transform import Transform3
from termin.visualization.core.entity import Entity, Component
from termin.geombase.pose3 import Pose3
from termin.visualization.core.resources import ResourceManager
from termin.editor.inspect_field import InspectField
from termin.editor.inspect_field_panel import _collect_inspect_fields
from termin.editor.undo_stack import UndoCommand

from termin.editor.editor_commands import (
    ComponentFieldEditCommand,
    AddComponentCommand,
    RemoveComponentCommand,
)
from termin.editor.transform_inspector import TransformInspector
from termin.editor.widgets.vec3_list_widget import Vec3ListWidget

logger = logging.getLogger(__name__)


class ComponentsPanel(QWidget):
    components_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        # Заголовок с кнопкой добавления
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("Components")
        header.addWidget(self._title)
        header.addStretch()

        self._add_btn = QPushButton("+")
        self._add_btn.setFixedSize(24, 24)
        self._add_btn.setToolTip("Add Component")
        self._add_btn.clicked.connect(self._show_add_component_menu)
        header.addWidget(self._add_btn)
        layout.addLayout(header)

        self._list = QListWidget()
        layout.addWidget(self._list)

        self._entity: Optional[Entity] = None
        self._component_library: list[tuple[str, type[Component]]] = []

        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None

        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        """
        Регистрирует обработчик undo-команд для операций с компонентами.
        """
        self._push_undo_command = handler

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
        self._component_library = list(library)

    def current_component(self) -> Optional[Component]:
        if self._entity is None:
            return None
        row = self._list.currentRow()
        if row < 0 or row >= len(self._entity.components):
            return None
        return self._entity.components[row]

    def _get_component_library(self) -> list[tuple[str, type[Component]]]:
        """Возвращает список доступных компонентов для добавления."""
        if self._component_library:
            return self._component_library
        manager = ResourceManager.instance()
        return sorted(manager.components.items())

    def _show_add_component_menu(self):
        """Показывает меню добавления компонента."""
        if self._entity is None:
            return

        menu = QMenu(self)
        component_library = self._get_component_library()

        for label, cls in component_library:
            act = QAction(label, self)
            act.triggered.connect(
                lambda _checked=False, c=cls: self._add_component(c)
            )
            menu.addAction(act)

        # Показываем меню под кнопкой
        menu.exec(self._add_btn.mapToGlobal(self._add_btn.rect().bottomLeft()))

    def _on_context_menu(self, pos):
        if self._entity is None:
            return

        global_pos = self._list.mapToGlobal(pos)
        menu = QMenu(self)
        comp = self.current_component()
        remove_action = QAction("Удалить компонент", self)
        remove_action.setEnabled(comp is not None)
        remove_action.triggered.connect(self._remove_current_component)
        menu.addAction(remove_action)

        component_library = self._get_component_library()

        if component_library:
            add_menu = menu.addMenu("Добавить компонент")
            for label, cls in component_library:
                act = QAction(label, self)
                act.triggered.connect(
                    lambda _checked=False, c=cls: self._add_component(c)
                )
                add_menu.addAction(act)

        menu.exec(global_pos)

    def _remove_current_component(self):
        if self._entity is None:
            return
        comp = self.current_component()
        if comp is None:
            return

        if self._push_undo_command is not None:
            cmd = RemoveComponentCommand(self._entity, comp)
            self._push_undo_command(cmd, False)
        else:
            self._entity.remove_component(comp)

        self.set_entity(self._entity)
        self.components_changed.emit()

    def _add_component(self, comp_cls: type[Component]):
        if self._entity is None:
            return
        try:
            comp = comp_cls()
        except TypeError:
            logger.exception("Не удалось создать компонент %s", comp_cls)
            return

        if self._push_undo_command is not None:
            cmd = AddComponentCommand(self._entity, comp)
            self._push_undo_command(cmd, False)
        else:
            self._entity.add_component(comp)

        self.set_entity(self._entity)

        row = len(self._entity.components) - 1
        if row >= 0:
            self._list.setCurrentRow(row)

        self.components_changed.emit()


def _to_qcolor(value) -> QColor:
    """
    Конвертирует значение цвета в QColor.
    Поддерживает:
    - QColor
    - tuple/list (r, g, b) или (r, g, b, a) в диапазоне 0..1
    - numpy array
    """
    if isinstance(value, QColor):
        return value
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        r = float(value[0])
        g = float(value[1])
        b = float(value[2])
        a = float(value[3]) if len(value) > 3 else 1.0
        # Предполагаем диапазон 0..1
        return QColor.fromRgbF(
            max(0.0, min(1.0, r)),
            max(0.0, min(1.0, g)),
            max(0.0, min(1.0, b)),
            max(0.0, min(1.0, a)),
        )
    try:
        arr = np.asarray(value).reshape(-1)
        if arr.size >= 3:
            r = float(arr[0])
            g = float(arr[1])
            b = float(arr[2])
            a = float(arr[3]) if arr.size > 3 else 1.0
            return QColor.fromRgbF(
                max(0.0, min(1.0, r)),
                max(0.0, min(1.0, g)),
                max(0.0, min(1.0, b)),
                max(0.0, min(1.0, a)),
            )
    except Exception:
        pass
    return QColor(255, 255, 255)
class ComponentInspectorPanel(QWidget):
    """
    Рисует форму для одного компонента на основе component.inspect_fields.
    """

    component_changed = pyqtSignal()

    def __init__(self, resources: ResourceManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._component: Optional[Component] = None
        self._fields: dict[str, InspectField] = {}
        self._widgets: dict[str, QWidget] = {}
        self._updating_from_model = False
        self._resources = resources
        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout = layout

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        """
        Регистрирует обработчик undo-команд для правок полей компонента.
        """
        self._push_undo_command = handler

    def set_component(self, comp: Optional[Component]):
        for i in reversed(range(self._layout.count())):
            item = self._layout.itemAt(i)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        self._widgets.clear()
        self._component = comp

        if comp is None:
            return

        fields = _collect_inspect_fields(comp.__class__)
        if not fields:
            return

        self._fields = fields

        self._updating_from_model = True
        try:
            for key, field in fields.items():
                label = field.label or key
                widget = self._create_widget_for_field(field)
                self._widgets[key] = widget

                # Buttons span the full row, no separate label
                if field.kind == "button":
                    self._layout.addRow(widget)
                else:
                    self._layout.addRow(QLabel(label), widget)
                    value = field.get_value(comp)
                    self._set_widget_value(widget, value, field)

                self._connect_widget(widget, key, field)
        finally:
            self._updating_from_model = False

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
            le = QLineEdit()
            # Read-only если есть getter, но нет setter и нет path
            if field.getter is not None and field.setter is None and field.path is None:
                le.setReadOnly(True)
            return le

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

        if kind == "slider":
            # Слайдер + спинбокс в одном ряду
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(4)

            min_val = int(field.min) if field.min is not None else 0
            max_val = int(field.max) if field.max is not None else 100

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setTickPosition(QSlider.TickPosition.NoTicks)

            spinbox = QSpinBox()
            spinbox.setRange(min_val, max_val)
            spinbox.setFixedWidth(50)

            # Синхронизация слайдера и спинбокса
            slider.valueChanged.connect(spinbox.setValue)
            spinbox.valueChanged.connect(slider.setValue)

            hl.addWidget(slider, stretch=1)
            hl.addWidget(spinbox)

            row._slider = slider
            row._spinbox = spinbox
            return row

        if kind == "material":
            combo = QComboBox()
            names = self._resources.list_material_names()
            for n in names:
                combo.addItem(n)
            return combo

        if kind == "mesh":
            combo = QComboBox()
            names = self._resources.list_mesh_names()
            for n in names:
                combo.addItem(n)
            return combo

        if kind == "voxel_grid":
            combo = QComboBox()
            names = self._resources.list_voxel_grid_names()
            for n in names:
                combo.addItem(n)
            return combo

        if kind == "navmesh":
            combo = QComboBox()
            names = self._resources.list_navmesh_names()
            for n in names:
                combo.addItem(n)
            return combo

        if kind == "enum":
            combo = QComboBox()
            if field.choices:
                for value, label in field.choices:
                    combo.addItem(label, userData=value)
            return combo

        if kind == "color":
            btn = QPushButton()
            btn.setAutoFillBackground(True)
            btn._current_color = None  # tuple (r, g, b, a) в диапазоне 0..1

            def set_btn_color(color: QColor):
                # Сохраняем цвет в диапазоне 0..1 с альфой
                btn._current_color = (
                    color.redF(),
                    color.greenF(),
                    color.blueF(),
                    color.alphaF(),
                )
                pal = btn.palette()
                pal.setColor(btn.backgroundRole(), color)
                btn.setPalette(pal)
                # Отображаем значения RGBA в диапазоне 0..1
                btn.setText(
                    f"{color.redF():.2f}, {color.greenF():.2f}, "
                    f"{color.blueF():.2f}, {color.alphaF():.2f}"
                )

            btn._set_color = set_btn_color
            return btn

        if kind == "button":
            btn = QPushButton(field.label or "Action")
            btn._action = field.action
            btn._field = field
            return btn

        if kind == "vec3_list":
            return Vec3ListWidget()

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

        if isinstance(w, QLineEdit) and field.kind != "material":
            w.setText(str(value))
            return

        if hasattr(w, "_boxes"):
            arr = np.asarray(value).reshape(-1)
            for sb, v in zip(w._boxes, arr):
                sb.setValue(float(v))
            return

        if hasattr(w, "_slider") and field.kind == "slider":
            int_val = int(value) if value is not None else 0
            w._slider.setValue(int_val)
            return

        if isinstance(w, QComboBox) and field.kind == "material":
            mat = value
            if mat is None:
                w.setCurrentIndex(-1)
                return

            name = self._resources.find_material_name(mat)
            # обновим список на всякий случай
            existing = [w.itemText(i) for i in range(w.count())]
            all_names = self._resources.list_material_names()
            if existing != all_names:
                w.clear()
                for n in all_names:
                    w.addItem(n)

            if name is None:
                w.setCurrentIndex(-1)
                return

            idx = w.findText(name)
            if idx >= 0:
                w.setCurrentIndex(idx)
            else:
                w.setCurrentIndex(-1)
            return

        if isinstance(w, QComboBox) and field.kind == "mesh":
            mesh = value
            if mesh is None:
                w.setCurrentIndex(-1)
                return

            name = self._resources.find_mesh_name(mesh)
            existing = [w.itemText(i) for i in range(w.count())]
            all_names = self._resources.list_mesh_names()
            if existing != all_names:
                w.clear()
                for n in all_names:
                    w.addItem(n)

            if name is None:
                w.setCurrentIndex(-1)
                return

            idx = w.findText(name)
            if idx >= 0:
                w.setCurrentIndex(idx)
            else:
                w.setCurrentIndex(-1)
            return

        if isinstance(w, QComboBox) and field.kind == "voxel_grid":
            grid = value
            if grid is None:
                w.setCurrentIndex(-1)
                return

            name = self._resources.find_voxel_grid_name(grid)
            existing = [w.itemText(i) for i in range(w.count())]
            all_names = self._resources.list_voxel_grid_names()
            if existing != all_names:
                w.clear()
                for n in all_names:
                    w.addItem(n)

            if name is None:
                w.setCurrentIndex(-1)
                return

            idx = w.findText(name)
            if idx >= 0:
                w.setCurrentIndex(idx)
            else:
                w.setCurrentIndex(-1)
            return

        if isinstance(w, QComboBox) and field.kind == "navmesh":
            # value — это имя navmesh (строка)
            name = value if isinstance(value, str) else None
            existing = [w.itemText(i) for i in range(w.count())]
            all_names = self._resources.list_navmesh_names()
            if existing != all_names:
                w.clear()
                for n in all_names:
                    w.addItem(n)

            if name is None or name == "":
                w.setCurrentIndex(-1)
                return

            idx = w.findText(name)
            if idx >= 0:
                w.setCurrentIndex(idx)
            else:
                w.setCurrentIndex(-1)
            return

        if isinstance(w, QComboBox) and field.kind == "enum":
            if field.choices:
                for i in range(w.count()):
                    if w.itemData(i) == value:
                        w.setCurrentIndex(i)
                        break
                else:
                    w.setCurrentIndex(-1)
            else:
                idx = w.findText(str(value))
                w.setCurrentIndex(idx if idx >= 0 else -1)
            return

        if isinstance(w, QPushButton) and field.kind == "color":
            qcol = _to_qcolor(value)
            if hasattr(w, "_set_color"):
                w._set_color(qcol)
            return

        if isinstance(w, Vec3ListWidget) and field.kind == "vec3_list":
            points = list(value) if value else []
            w.set_value(points)
            return

    def _connect_widget(self, w: QWidget, key: str, field: InspectField):
        def commit(merge: bool):
            if self._updating_from_model or self._component is None:
                return

            old_value = field.get_value(self._component)
            new_value = self._read_widget_value(w, field)

            if self._push_undo_command is not None:
                cmd = ComponentFieldEditCommand(
                    component=self._component,
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                )
                self._push_undo_command(cmd, merge)
            else:
                field.set_value(self._component, new_value)

            self.component_changed.emit()

        if isinstance(w, QDoubleSpinBox):
            w.valueChanged.connect(lambda _v: commit(True))
        elif isinstance(w, QCheckBox):
            w.stateChanged.connect(lambda _s: commit(False))
        elif isinstance(w, QLineEdit) and field.kind != "material":
            # Не подключаем commit для read-only полей
            if not (field.getter is not None and field.setter is None and field.path is None):
                w.textEdited.connect(lambda _t: commit(True))
                w.editingFinished.connect(lambda: commit(False))
        elif hasattr(w, "_boxes"):
            for sb in w._boxes:
                sb.valueChanged.connect(lambda _v: commit(True))
        elif hasattr(w, "_slider") and field.kind == "slider":
            w._slider.valueChanged.connect(lambda _v: commit(True))
        elif isinstance(w, QComboBox) and field.kind in ("material", "mesh", "voxel_grid", "navmesh", "enum"):
            w.currentIndexChanged.connect(lambda _i: commit(False))
        elif isinstance(w, QPushButton) and field.kind == "color":
            def on_click():
                if self._component is None:
                    return
                # Получаем текущий цвет в диапазоне 0..1 (RGBA)
                current_value = field.get_value(self._component)
                if current_value is None:
                    initial = (1.0, 1.0, 1.0, 1.0)
                elif isinstance(current_value, (list, tuple)) and len(current_value) >= 3:
                    r = float(current_value[0])
                    g = float(current_value[1])
                    b = float(current_value[2])
                    a = float(current_value[3]) if len(current_value) > 3 else 1.0
                    initial = (r, g, b, a)
                else:
                    initial = (1.0, 1.0, 1.0, 1.0)

                result = ColorDialog.get_color(initial, self)
                if result is None:
                    return
                # result теперь (r, g, b, a)
                new_color = QColor.fromRgbF(result[0], result[1], result[2], result[3])
                if hasattr(w, "_set_color"):
                    w._set_color(new_color)
                commit(False)

            w.clicked.connect(on_click)
        elif isinstance(w, QPushButton) and field.kind == "button":
            def on_button_click():
                if self._component is None:
                    return
                action = getattr(w, "_action", None)
                if action is not None:
                    action(self._component)

            w.clicked.connect(on_button_click)
        elif isinstance(w, Vec3ListWidget) and field.kind == "vec3_list":
            w.value_changed.connect(lambda: commit(False))

    def _read_widget_value(self, w: QWidget, field: InspectField):
        if isinstance(w, QDoubleSpinBox):
            return float(w.value())

        if isinstance(w, QCheckBox):
            return bool(w.isChecked())

        if isinstance(w, QLineEdit) and field.kind != "material":
            return w.text()

        if hasattr(w, "_boxes"):
            return np.array([sb.value() for sb in w._boxes], dtype=float)

        if hasattr(w, "_slider") and field.kind == "slider":
            return float(w._slider.value())

        if isinstance(w, QComboBox) and field.kind == "material":
            name = w.currentText()
            if not name:
                return None
            return self._resources.get_material(name)

        if isinstance(w, QComboBox) and field.kind == "mesh":
            name = w.currentText()
            if not name:
                return None
            return self._resources.get_mesh(name)

        if isinstance(w, QComboBox) and field.kind == "voxel_grid":
            name = w.currentText()
            if not name:
                return None
            return self._resources.get_voxel_grid(name)

        if isinstance(w, QComboBox) and field.kind == "navmesh":
            name = w.currentText()
            if not name:
                return None
            return self._resources.get_navmesh(name)

        if isinstance(w, QComboBox) and field.kind == "enum":
            if field.choices:
                return w.currentData()
            text = w.currentText()
            return text if text else None

        if isinstance(w, QPushButton) and field.kind == "color":
            # _current_color теперь хранит tuple (r, g, b) в диапазоне 0..1
            color_tuple = getattr(w, "_current_color", None)
            if color_tuple is None:
                return None
            return color_tuple

        if isinstance(w, Vec3ListWidget) and field.kind == "vec3_list":
            return w.get_value()

        return None


class EntityInspector(QWidget):
    """
    Общий инспектор для Entity/Transform:
    сверху TransformInspector, ниже список компонентов, ещё ниже – инспектор компонента.
    """

    transform_changed = pyqtSignal()
    component_changed = pyqtSignal()

    def __init__(self, resources: ResourceManager, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._resources = resources

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._transform_inspector = TransformInspector(self)
        layout.addWidget(self._transform_inspector)

        self._components_panel = ComponentsPanel(self)
        layout.addWidget(self._components_panel)

        self._component_inspector = ComponentInspectorPanel(resources, self)
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
        self._undo_command_handler: Optional[Callable[[UndoCommand, bool], None]] = None

    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        """
        Задаёт функцию, через которую инспектор будет отправлять undo-команды.
        Сейчас она используется TransformInspector и панелями компонентов.
        """
        self._undo_command_handler = handler
        self._transform_inspector.set_undo_command_handler(handler)
        self._components_panel.set_undo_command_handler(handler)
        self._component_inspector.set_undo_command_handler(handler)
    def _on_components_changed(self):
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
        self._components_panel.set_component_library(library)

    def _on_component_changed(self):
        self.component_changed.emit()

    def set_target(self, obj: Optional[object]):
        if isinstance(obj, Entity):
            ent = obj
            trans = obj.transform
        elif isinstance(obj, Transform3):
            trans = obj
            ent = obj.entity
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

    def refresh_transform(self) -> None:
        """
        Обновляет значения в TransformInspector из текущего трансформа.

        Вызывается при изменении трансформа извне (например, при drag гизмо).
        """
        self._transform_inspector._update_from_transform()
