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
<br>
class TransformInspector(QWidget):<br>
&#9;transform_changed = pyqtSignal()<br>
<br>
&#9;def __init__(self, parent: Optional[QWidget] = None):<br>
&#9;&#9;super().__init__(parent)<br>
<br>
&#9;&#9;self._transform: Optional[Transform3] = None<br>
&#9;&#9;self._updating_from_model = False<br>
<br>
&#9;&#9;layout = QFormLayout(self)<br>
&#9;&#9;layout.setLabelAlignment(Qt.AlignLeft)<br>
&#9;&#9;layout.setFormAlignment(Qt.AlignTop)<br>
<br>
&#9;&#9;def make_vec3_row():<br>
&#9;&#9;&#9;row = QHBoxLayout()<br>
&#9;&#9;&#9;sx = QDoubleSpinBox()<br>
&#9;&#9;&#9;sy = QDoubleSpinBox()<br>
&#9;&#9;&#9;sz = QDoubleSpinBox()<br>
&#9;&#9;&#9;for sb in (sx, sy, sz):<br>
&#9;&#9;&#9;&#9;sb.setRange(-1e6, 1e6)<br>
&#9;&#9;&#9;&#9;sb.setDecimals(3)<br>
&#9;&#9;&#9;&#9;sb.setSingleStep(0.1)<br>
&#9;&#9;&#9;&#9;row.addWidget(sb)<br>
&#9;&#9;&#9;return row, (sx, sy, sz)<br>
<br>
&#9;&#9;pos_row, self._pos = make_vec3_row()<br>
&#9;&#9;layout.addRow(QLabel(&quot;Position&quot;), pos_row)<br>
<br>
&#9;&#9;rot_row, self._rot = make_vec3_row()<br>
&#9;&#9;layout.addRow(QLabel(&quot;Rotation (deg)&quot;), rot_row)<br>
<br>
&#9;&#9;scale_row, self._scale = make_vec3_row()<br>
&#9;&#9;for sb in self._scale:<br>
&#9;&#9;&#9;sb.setValue(1.0)<br>
&#9;&#9;layout.addRow(QLabel(&quot;Scale&quot;), scale_row)<br>
<br>
&#9;&#9;for sb in (*self._pos, *self._rot, *self._scale):<br>
&#9;&#9;&#9;sb.valueChanged.connect(self._on_value_changed)<br>
<br>
&#9;&#9;self._set_enabled(False)<br>
<br>
&#9;def set_target(self, obj: Optional[object]):<br>
&#9;&#9;if isinstance(obj, Entity):<br>
&#9;&#9;&#9;transform = obj.transform<br>
&#9;&#9;elif isinstance(obj, Transform3):<br>
&#9;&#9;&#9;transform = obj<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;transform = None<br>
<br>
&#9;&#9;self._transform = transform<br>
&#9;&#9;self._update_from_transform()<br>
<br>
&#9;def _set_enabled(self, flag: bool):<br>
&#9;&#9;for sb in (*self._pos, *self._rot, *self._scale):<br>
&#9;&#9;&#9;sb.setEnabled(flag)<br>
<br>
&#9;def _update_from_transform(self):<br>
&#9;&#9;self._updating_from_model = True<br>
&#9;&#9;try:<br>
&#9;&#9;&#9;if self._transform is None:<br>
&#9;&#9;&#9;&#9;self._set_enabled(False)<br>
&#9;&#9;&#9;&#9;for sb in (*self._pos, *self._rot, *self._scale):<br>
&#9;&#9;&#9;&#9;&#9;sb.setValue(0.0)<br>
&#9;&#9;&#9;&#9;for sb in self._scale:<br>
&#9;&#9;&#9;&#9;&#9;sb.setValue(1.0)<br>
&#9;&#9;&#9;&#9;return<br>
<br>
&#9;&#9;&#9;self._set_enabled(True)<br>
&#9;&#9;&#9;pose: Pose3 = self._transform.global_pose()<br>
<br>
&#9;&#9;&#9;px, py, pz = pose.lin<br>
&#9;&#9;&#9;x, y, z, w = pose.ang<br>
&#9;&#9;&#9;az, ay, ax = self.quat_to_euler_zyx(np.array([x, y, z, w], dtype=float))<br>
&#9;&#9;&#9;self._pos[0].setValue(float(px))<br>
&#9;&#9;&#9;self._pos[1].setValue(float(py))<br>
&#9;&#9;&#9;self._pos[2].setValue(float(pz))<br>
<br>
&#9;&#9;&#9;self._rot[0].setValue(float(ax))<br>
&#9;&#9;&#9;self._rot[1].setValue(float(ay))<br>
&#9;&#9;&#9;self._rot[2].setValue(float(az))<br>
<br>
&#9;&#9;&#9;s = np.array([1.0, 1.0, 1.0], dtype=float)<br>
&#9;&#9;&#9;self._scale[0].setValue(float(s[0]))<br>
&#9;&#9;&#9;self._scale[1].setValue(float(s[1]))<br>
&#9;&#9;&#9;self._scale[2].setValue(float(s[2]))<br>
&#9;&#9;finally:<br>
&#9;&#9;&#9;self._updating_from_model = False<br>
<br>
&#9;def euler_zyx_to_quat(self, zyx: np.ndarray) -&gt; np.ndarray:<br>
&#9;&#9;zquat = np.array(<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;0.0,<br>
&#9;&#9;&#9;&#9;0.0,<br>
&#9;&#9;&#9;&#9;np.sin(np.radians(zyx[0]) / 2),<br>
&#9;&#9;&#9;&#9;np.cos(np.radians(zyx[0]) / 2),<br>
&#9;&#9;&#9;],<br>
&#9;&#9;&#9;dtype=float,<br>
&#9;&#9;)<br>
&#9;&#9;yquat = np.array(<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;0.0,<br>
&#9;&#9;&#9;&#9;np.sin(np.radians(zyx[1]) / 2),<br>
&#9;&#9;&#9;&#9;0.0,<br>
&#9;&#9;&#9;&#9;np.cos(np.radians(zyx[1]) / 2),<br>
&#9;&#9;&#9;],<br>
&#9;&#9;&#9;dtype=float,<br>
&#9;&#9;)<br>
&#9;&#9;xquat = np.array(<br>
&#9;&#9;&#9;[<br>
&#9;&#9;&#9;&#9;np.sin(np.radians(zyx[2]) / 2),<br>
&#9;&#9;&#9;&#9;0.0,<br>
&#9;&#9;&#9;&#9;0.0,<br>
&#9;&#9;&#9;&#9;np.cos(np.radians(zyx[2]) / 2),<br>
&#9;&#9;&#9;],<br>
&#9;&#9;&#9;dtype=float,<br>
&#9;&#9;)<br>
&#9;&#9;return self.quat_mult(self.quat_mult(zquat, yquat), xquat)<br>
<br>
&#9;def quat_mult(self, q1: np.ndarray, q2: np.ndarray) -&gt; np.ndarray:<br>
&#9;&#9;w1, x1, y1, z1 = q1[3], q1[0], q1[1], q1[2]<br>
&#9;&#9;w2, x2, y2, z2 = q2[3], q2[0], q2[1], q2[2]<br>
&#9;&#9;w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2<br>
&#9;&#9;x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2<br>
&#9;&#9;y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2<br>
&#9;&#9;z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2<br>
&#9;&#9;return np.array([x, y, z, w], dtype=float)<br>
<br>
&#9;def quat_to_euler_zyx(self, quat: np.ndarray) -&gt; np.ndarray:<br>
&#9;&#9;x, y, z, w = quat[0], quat[1], quat[2], quat[3]<br>
<br>
&#9;&#9;t0 = +2.0 * (w * z + x * y)<br>
&#9;&#9;t1 = +1.0 - 2.0 * (y * y + z * z)<br>
&#9;&#9;Z = np.degrees(np.arctan2(t0, t1))<br>
<br>
&#9;&#9;t2 = +2.0 * (w * y - z * x)<br>
&#9;&#9;t2 = +1.0 if t2 &gt; +1.0 else t2<br>
&#9;&#9;t2 = -1.0 if t2 &lt; -1.0 else t2<br>
&#9;&#9;Y = np.degrees(np.arcsin(t2))<br>
<br>
&#9;&#9;t3 = +2.0 * (w * x + y * z)<br>
&#9;&#9;t4 = +1.0 - 2.0 * (x * x + y * y)<br>
&#9;&#9;X = np.degrees(np.arctan2(t3, t4))<br>
<br>
&#9;&#9;return np.array([Z, Y, X], dtype=float)<br>
<br>
&#9;def _on_value_changed(self, _value):<br>
&#9;&#9;if self._updating_from_model:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;if self._transform is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;pose: Pose3 = self._transform.global_pose()<br>
<br>
&#9;&#9;px = self._pos[0].value()<br>
&#9;&#9;py = self._pos[1].value()<br>
&#9;&#9;pz = self._pos[2].value()<br>
&#9;&#9;new_lin = np.array([px, py, pz], dtype=float)<br>
<br>
&#9;&#9;ax = self._rot[0].value()<br>
&#9;&#9;ay = self._rot[1].value()<br>
&#9;&#9;az = self._rot[2].value()<br>
&#9;&#9;new_ang = self.euler_zyx_to_quat(np.array([az, ay, ax], dtype=float))<br>
<br>
&#9;&#9;pose = Pose3(lin=new_lin, ang=new_ang)<br>
&#9;&#9;self._transform.relocate(pose)<br>
&#9;&#9;self.transform_changed.emit()<br>
<!-- END SCAT CODE -->
</body>
</html>
