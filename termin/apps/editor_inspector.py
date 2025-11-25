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
)
from PyQt5.QtCore import Qt, pyqtSignal

from PyQt5.QtCore import Qt
from PyQt5.QtCore import pyqtSignal

from termin.kinematic.transform import Transform3
from termin.visualization.entity import Entity
from termin.geombase.pose3 import Pose3


class ComponentsPanel(QWidget):
    """
    Простая панель компонентов:
    снизу под трансформом показывает список Component'ов у Entity.
    """
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

    def set_entity(self, ent: Optional[Entity]):
        self._entity = ent
        self._list.clear()
        if ent is None:
            return
        for comp in ent.components:
            name = comp.__class__.__name__
            item = QListWidgetItem(name)
            self._list.addItem(item)


class TransformInspector(QWidget):
    """
    Мини-инспектор Transform:
    - position (x, y, z)
    - rotation (x, y, z) в градусах — пока только отображаем / заготовка
    - scale (x, y, z) — опционально, если Transform3 это поддерживает
    """

    transform_changed = pyqtSignal()   # <-- вот он

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

        # rotation (Euler degrees, UX только; математику подставишь свою)
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
            # Здесь всё зависит от того, как ты хранишь ориентацию.
            # Допустим, у Pose3 есть ang – кватернион.
            # Ниже – заглушка: ставим 0,0,0.
            # Ты можешь сюда вставить свои функции "кватернион → эйлеры".
            self._rot[0].setValue(0.0)
            self._rot[1].setValue(0.0)
            self._rot[2].setValue(0.0)

            # --- scale ---
            # Если в Transform3 есть масштаб – подставь сюда:
            # s = getattr(self._transform, "scale", np.array([1.0, 1.0, 1.0]))
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

        # применяем только позицию (минимальный рабочий вариант)
        pose: Pose3 = self._transform.global_pose()

        px = self._pos[0].value()
        py = self._pos[1].value()
        pz = self._pos[2].value()
        new_lin = np.array([px, py, pz], dtype=float)

        # rotation и scale пока не трогаем, чтобы не городить конверсии
        ax = self._rot[0].value()
        ay = self._rot[1].value()
        az = self._rot[2].value()

        #euler zyx to quaternion
        axis = np.array([ax, ay, az])
        angle_deg = np.linalg.norm(axis)
        axis_normalized = axis / angle_deg if angle_deg != 0 else np.array([0.0, 0.0, 1.0])
        angle_rad = np.deg2rad(angle_deg)
        qw = np.cos(angle_rad / 2)
        qx = axis_normalized[0] * np.sin(angle_rad / 2)
        qy = axis_normalized[1] * np.sin(angle_rad / 2)
        qz = axis_normalized[2] * np.sin(angle_rad / 2)
        new_ang = np.array([qw, qx, qy, qz], dtype=float)   

        # scale пока пропускаем         

        pose = Pose3(lin=new_lin, ang=new_ang)
        self._transform.relocate(pose)

        self.transform_changed.emit()

class EntityInspector(QWidget):
    """
    Общий инспектор для Entity/Transform:
    сверху TransformInspector, снизу список компонентов.
    """
    transform_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._transform_inspector = TransformInspector(self)
        layout.addWidget(self._transform_inspector)

        self._components_panel = ComponentsPanel(self)
        layout.addWidget(self._components_panel)

        self._entity: Optional[Entity] = None

        # пробрасываем сигнал наружу
        self._transform_inspector.transform_changed.connect(
            self.transform_changed
        )

    def set_target(self, obj: Optional[object]):
        """
        Принимает Entity, Transform3 или None.
        """
        from termin.kinematic.transform import Transform3
        from termin.visualization.entity import Entity

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

        # внутрь трансформ-инспектора можно передать либо Entity, либо Transform3 –
        # он сам разберётся.
        self._transform_inspector.set_target(trans or ent)
        self._components_panel.set_entity(ent)
