# ===== termin/apps/transform_inspector.py =====

from __future__ import annotations

from typing import Optional, Callable

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
    QComboBox,
)
from PyQt5.QtCore import Qt, pyqtSignal

from termin.kinematic.transform import Transform3
from termin.visualization.entity import Entity, Component
from termin.geombase.pose3 import Pose3
from termin.visualization.inspect import InspectField
from termin.visualization.resources import ResourceManager
from termin.apps.undo_stack import UndoCommand
from termin.apps.editor_commands import TransformEditCommand
# scale is now numpy.ndarray


# scale is now numpy.ndarray

class TransformInspector(QWidget):
# Обработчик для отправки команд в общий undo-стек редактора.
# handler(cmd, merge=False) -> None
    def set_undo_command_handler(self, handler):
        """
        Зарегистрировать обработчик команд undo/redo для этого инспектора.

        handler должен быть вызываемым объектом:
            handler(cmd, merge=False) -> None
        """
        self._push_undo_command = handler
    transform_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._transform: Optional[Transform3] = None
        self._updating_from_model = False
        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None

        layout = QFormLayout(self)
        layout.setLabelAlignment(Qt.AlignLeft)
        layout.setFormAlignment(Qt.AlignTop)

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

        pos_row, self._pos = make_vec3_row()
        layout.addRow(QLabel("Position"), pos_row)

        rot_row, self._rot = make_vec3_row()
        layout.addRow(QLabel("Rotation (deg)"), rot_row)

        scale_row, self._scale = make_vec3_row()
        for sb in self._scale:
            sb.setValue(1.0)
        layout.addRow(QLabel("Scale"), scale_row)

        for sb in (*self._pos, *self._rot, *self._scale):
            sb.valueChanged.connect(self._on_value_changed)

        self._set_enabled(False)


    def set_undo_command_handler(
        self, handler: Optional[Callable[[UndoCommand, bool], None]]
    ) -> None:
        """
        Подключает внешний обработчик undo-команд.

        handler(cmd, merge) обычно будет EditorWindow.push_undo_command.
        """
        self._push_undo_command = handler
        
    def set_target(self, obj: Optional[object]):
        if isinstance(obj, Entity):
            transform = obj.transform
        elif isinstance(obj, Transform3):
            transform = obj
        else:
            transform = None

        self._transform = transform
        self._update_from_transform()

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

            px, py, pz = pose.lin
            x, y, z, w = pose.ang
            az, ay, ax = self.quat_to_euler_zyx(np.array([x, y, z, w], dtype=float))
            self._pos[0].setValue(float(px))
            self._pos[1].setValue(float(py))
            self._pos[2].setValue(float(pz))

            self._rot[0].setValue(float(ax))
            self._rot[1].setValue(float(ay))
            self._rot[2].setValue(float(az))

            s = self._transform.entity.scale
            assert s.shape == (3,)
            self._scale[0].setValue(float(s[0]))
            self._scale[1].setValue(float(s[1]))
            self._scale[2].setValue(float(s[2]))
        finally:
            self._updating_from_model = False

    def euler_zyx_to_quat(self, zyx: np.ndarray) -> np.ndarray:
        zquat = np.array(
            [
                0.0,
                0.0,
                np.sin(np.radians(zyx[0]) / 2),
                np.cos(np.radians(zyx[0]) / 2),
            ],
            dtype=float,
        )
        yquat = np.array(
            [
                0.0,
                np.sin(np.radians(zyx[1]) / 2),
                0.0,
                np.cos(np.radians(zyx[1]) / 2),
            ],
            dtype=float,
        )
        xquat = np.array(
            [
                np.sin(np.radians(zyx[2]) / 2),
                0.0,
                0.0,
                np.cos(np.radians(zyx[2]) / 2),
            ],
            dtype=float,
        )
        return self.quat_mult(self.quat_mult(zquat, yquat), xquat)

    def quat_mult(self, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        w1, x1, y1, z1 = q1[3], q1[0], q1[1], q1[2]
        w2, x2, y2, z2 = q2[3], q2[0], q2[1], q2[2]
        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        return np.array([x, y, z, w], dtype=float)

    def quat_to_euler_zyx(self, quat: np.ndarray) -> np.ndarray:
        x, y, z, w = quat[0], quat[1], quat[2], quat[3]

        t0 = +2.0 * (w * z + x * y)
        t1 = +1.0 - 2.0 * (y * y + z * z)
        Z = np.degrees(np.arctan2(t0, t1))

        t2 = +2.0 * (w * y - z * x)
        t2 = +1.0 if t2 > +1.0 else t2
        t2 = -1.0 if t2 < -1.0 else t2
        Y = np.degrees(np.arcsin(t2))

        t3 = +2.0 * (w * x + y * z)
        t4 = +1.0 - 2.0 * (x * x + y * y)
        X = np.degrees(np.arctan2(t3, t4))

        return np.array([Z, Y, X], dtype=float)

    def _on_value_changed(self, _value):
        if self._updating_from_model:
            return
        if self._transform is None:
            return

        # Снимок старого состояния до применения правки из UI
        old_pose: Pose3 = self._transform.global_pose()
        entity = self._transform.entity
        if entity is not None:
            old_scale = np.asarray(entity.scale, dtype=float)
        else:
            # На всякий случай — одиночный Transform3 без сущности.
            old_scale = np.ones(3, dtype=float)

        # Новые значения из спинбоксов
        px = self._pos[0].value()
        py = self._pos[1].value()
        pz = self._pos[2].value()
        new_lin = np.array([px, py, pz], dtype=float)

        ax = self._rot[0].value()
        ay = self._rot[1].value()
        az = self._rot[2].value()
        new_ang = self.euler_zyx_to_quat(np.array([az, ay, ax], dtype=float))

        s_x = self._scale[0].value()
        s_y = self._scale[1].value()
        s_z = self._scale[2].value()
        new_scale = np.array([s_x, s_y, s_z], dtype=float)

        new_pose = Pose3(lin=new_lin, ang=new_ang)

        if self._push_undo_command is not None:
            cmd = TransformEditCommand(
                transform=self._transform,
                old_pose=old_pose,
                old_scale=old_scale,
                new_pose=new_pose,
                new_scale=new_scale,
            )
            # В инспекторе удобно склеивать серию мелких правок
            # (пока пользователь крутит спинбоксы) в одну команду.
            self._push_undo_command(cmd, True)
        else:
            # Режим без undo-стека — старое поведение "напрямую".
            if entity is not None:
                entity.scale = new_scale
            self._transform.relocate(new_pose)

        self.transform_changed.emit()
