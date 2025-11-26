<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/apps/transform_inspector.py</title>
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
<br>
class TransformInspector(QWidget):<br>
    transform_changed = pyqtSignal()<br>
<br>
    def __init__(self, parent: Optional[QWidget] = None):<br>
        super().__init__(parent)<br>
<br>
        self._transform: Optional[Transform3] = None<br>
        self._updating_from_model = False<br>
<br>
        layout = QFormLayout(self)<br>
        layout.setLabelAlignment(Qt.AlignLeft)<br>
        layout.setFormAlignment(Qt.AlignTop)<br>
<br>
        def make_vec3_row():<br>
            row = QHBoxLayout()<br>
            sx = QDoubleSpinBox()<br>
            sy = QDoubleSpinBox()<br>
            sz = QDoubleSpinBox()<br>
            for sb in (sx, sy, sz):<br>
                sb.setRange(-1e6, 1e6)<br>
                sb.setDecimals(3)<br>
                sb.setSingleStep(0.1)<br>
                row.addWidget(sb)<br>
            return row, (sx, sy, sz)<br>
<br>
        pos_row, self._pos = make_vec3_row()<br>
        layout.addRow(QLabel(&quot;Position&quot;), pos_row)<br>
<br>
        rot_row, self._rot = make_vec3_row()<br>
        layout.addRow(QLabel(&quot;Rotation (deg)&quot;), rot_row)<br>
<br>
        scale_row, self._scale = make_vec3_row()<br>
        for sb in self._scale:<br>
            sb.setValue(1.0)<br>
        layout.addRow(QLabel(&quot;Scale&quot;), scale_row)<br>
<br>
        for sb in (*self._pos, *self._rot, *self._scale):<br>
            sb.valueChanged.connect(self._on_value_changed)<br>
<br>
        self._set_enabled(False)<br>
<br>
    def set_target(self, obj: Optional[object]):<br>
        if isinstance(obj, Entity):<br>
            transform = obj.transform<br>
        elif isinstance(obj, Transform3):<br>
            transform = obj<br>
        else:<br>
            transform = None<br>
<br>
        self._transform = transform<br>
        self._update_from_transform()<br>
<br>
    def _set_enabled(self, flag: bool):<br>
        for sb in (*self._pos, *self._rot, *self._scale):<br>
            sb.setEnabled(flag)<br>
<br>
    def _update_from_transform(self):<br>
        self._updating_from_model = True<br>
        try:<br>
            if self._transform is None:<br>
                self._set_enabled(False)<br>
                for sb in (*self._pos, *self._rot, *self._scale):<br>
                    sb.setValue(0.0)<br>
                for sb in self._scale:<br>
                    sb.setValue(1.0)<br>
                return<br>
<br>
            self._set_enabled(True)<br>
            pose: Pose3 = self._transform.global_pose()<br>
<br>
            px, py, pz = pose.lin<br>
            x, y, z, w = pose.ang<br>
            az, ay, ax = self.quat_to_euler_zyx(np.array([x, y, z, w], dtype=float))<br>
            self._pos[0].setValue(float(px))<br>
            self._pos[1].setValue(float(py))<br>
            self._pos[2].setValue(float(pz))<br>
<br>
            self._rot[0].setValue(float(ax))<br>
            self._rot[1].setValue(float(ay))<br>
            self._rot[2].setValue(float(az))<br>
<br>
            s = np.array([1.0, 1.0, 1.0], dtype=float)<br>
            self._scale[0].setValue(float(s[0]))<br>
            self._scale[1].setValue(float(s[1]))<br>
            self._scale[2].setValue(float(s[2]))<br>
        finally:<br>
            self._updating_from_model = False<br>
<br>
    def euler_zyx_to_quat(self, zyx: np.ndarray) -&gt; np.ndarray:<br>
        zquat = np.array(<br>
            [<br>
                0.0,<br>
                0.0,<br>
                np.sin(np.radians(zyx[0]) / 2),<br>
                np.cos(np.radians(zyx[0]) / 2),<br>
            ],<br>
            dtype=float,<br>
        )<br>
        yquat = np.array(<br>
            [<br>
                0.0,<br>
                np.sin(np.radians(zyx[1]) / 2),<br>
                0.0,<br>
                np.cos(np.radians(zyx[1]) / 2),<br>
            ],<br>
            dtype=float,<br>
        )<br>
        xquat = np.array(<br>
            [<br>
                np.sin(np.radians(zyx[2]) / 2),<br>
                0.0,<br>
                0.0,<br>
                np.cos(np.radians(zyx[2]) / 2),<br>
            ],<br>
            dtype=float,<br>
        )<br>
        return self.quat_mult(self.quat_mult(zquat, yquat), xquat)<br>
<br>
    def quat_mult(self, q1: np.ndarray, q2: np.ndarray) -&gt; np.ndarray:<br>
        w1, x1, y1, z1 = q1[3], q1[0], q1[1], q1[2]<br>
        w2, x2, y2, z2 = q2[3], q2[0], q2[1], q2[2]<br>
        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2<br>
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2<br>
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2<br>
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2<br>
        return np.array([x, y, z, w], dtype=float)<br>
<br>
    def quat_to_euler_zyx(self, quat: np.ndarray) -&gt; np.ndarray:<br>
        x, y, z, w = quat[0], quat[1], quat[2], quat[3]<br>
<br>
        t0 = +2.0 * (w * z + x * y)<br>
        t1 = +1.0 - 2.0 * (y * y + z * z)<br>
        Z = np.degrees(np.arctan2(t0, t1))<br>
<br>
        t2 = +2.0 * (w * y - z * x)<br>
        t2 = +1.0 if t2 &gt; +1.0 else t2<br>
        t2 = -1.0 if t2 &lt; -1.0 else t2<br>
        Y = np.degrees(np.arcsin(t2))<br>
<br>
        t3 = +2.0 * (w * x + y * z)<br>
        t4 = +1.0 - 2.0 * (x * x + y * y)<br>
        X = np.degrees(np.arctan2(t3, t4))<br>
<br>
        return np.array([Z, Y, X], dtype=float)<br>
<br>
    def _on_value_changed(self, _value):<br>
        if self._updating_from_model:<br>
            return<br>
        if self._transform is None:<br>
            return<br>
<br>
        pose: Pose3 = self._transform.global_pose()<br>
<br>
        px = self._pos[0].value()<br>
        py = self._pos[1].value()<br>
        pz = self._pos[2].value()<br>
        new_lin = np.array([px, py, pz], dtype=float)<br>
<br>
        ax = self._rot[0].value()<br>
        ay = self._rot[1].value()<br>
        az = self._rot[2].value()<br>
        new_ang = self.euler_zyx_to_quat(np.array([az, ay, ax], dtype=float))<br>
<br>
        pose = Pose3(lin=new_lin, ang=new_ang)<br>
        self._transform.relocate(pose)<br>
        self.transform_changed.emit()<br>
<!-- END SCAT CODE -->
</body>
</html>
