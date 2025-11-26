<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/control_link.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy<br>
from termin.physics.force_link import VariableMultiForce<br>
from termin.physics.frame import Frame, ReferencedFrame<br>
from termin.physics.pose_object import ReferencedPoseObject<br>
from termin.ga201.screw import Screw2<br>
from termin.physics.pose_object import ReferencedPoseObject, PoseObject<br>
from termin.physics.screw_commutator import ScrewCommutator<br>
from termin.physics.indexed_matrix import IndexedVector<br>
<br>
from termin.physics.extlinalg import outkernel_operator<br>
from termin.physics.extlinalg import kernel_operator<br>
import math<br>
import time<br>
<br>
start_time = 0<br>
<br>
class ControlLink(VariableMultiForce):<br>
&#9;def __init__(self, position, child, parent, senses=[], stiffness=[1, 1]):<br>
&#9;&#9;super().__init__(position, child, parent, senses, stiffness)<br>
&#9;&#9;self._control = None<br>
&#9;&#9;self.curtime = 0<br>
&#9;&#9;self.target = numpy.array([0,0])<br>
&#9;&#9;self._filter = None<br>
<br>
&#9;def set_filter(self, filter):<br>
&#9;&#9;self._filter = filter<br>
<br>
&#9;def set_control(self, control_vector):<br>
&#9;&#9;self._control = control_vector<br>
<br>
&#9;def H_matrix_list(self):<br>
&#9;&#9;dQdl_child = self.derivative_by_frame(self._child).transpose()<br>
&#9;&#9;if self._parent is not None:<br>
&#9;&#9;&#9;dQdl_parent = -self.derivative_by_frame(self._parent).transpose()<br>
&#9;&#9;&#9;return [dQdl_child, dQdl_parent]<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;return [dQdl_child]<br>
&#9;<br>
&#9;def Ksi_matrix_list(self, delta, allctrlinks):<br>
&#9;&#9;if self._control is None:<br>
&#9;&#9;&#9;return []<br>
<br>
&#9;&#9;myposition = allctrlinks.index(self)<br>
&#9;&#9;ctr = self._control.reshape((len(self._control), 1))<br>
&#9;&#9;#print(&quot;C1:&quot;, ctr)<br>
<br>
&#9;&#9;# if self._filter is not None:<br>
&#9;&#9;#     mat = []<br>
&#9;&#9;#     counter = 0<br>
&#9;&#9;#     for link in allctrlinks:<br>
&#9;&#9;#         if link is not self:<br>
&#9;&#9;#             mat.append(numpy.zeros((1, 1)))<br>
&#9;&#9;#         else:<br>
&#9;&#9;#             mat.append(ctr)<br>
&#9;&#9;#         counter += 1<br>
&#9;&#9;#     ctr = numpy.concatenate(mat, axis=0)<br>
&#9;&#9;#     ctr = self._filter @ ctr<br>
&#9;&#9;#     print(ctr)<br>
<br>
&#9;&#9;#     ctr = numpy.array([ctr[myposition]])<br>
&#9;&#9;&#9;<br>
&#9;&#9;ctr = ctr.reshape((len(self._control),))<br>
&#9;&#9;#print(&quot;C2:&quot;, ctr)<br>
&#9;&#9;#print(&quot;C3:&quot;, self.screw_commutator().indexes())<br>
&#9;&#9;return [<br>
&#9;&#9;&#9;IndexedVector(ctr, self.screw_commutator().indexes(), self.screw_commutator())<br>
&#9;&#9;]<br>
<br>
<br>
class ControlTaskFrame(ReferencedFrame):<br>
&#9;def __init__(self, linked_body, position_in_body):<br>
&#9;&#9;senses = [<br>
&#9;&#9;&#9;#Screw2(m=1),<br>
&#9;&#9;&#9;Screw2(v=[1,0]),<br>
&#9;&#9;&#9;Screw2(v=[0,1]),<br>
&#9;&#9;]<br>
&#9;&#9;super().__init__(linked_body, position_in_body, senses)<br>
&#9;&#9;self.curtime = 0<br>
&#9;&#9;self._control_screw = Screw2()<br>
&#9;&#9;self._control_frames = []<br>
&#9;&#9;self._filter = None<br>
<br>
&#9;def set_filter(self, filter):<br>
&#9;&#9;self._filter = filter<br>
<br>
&#9;def add_control_frame(self, frame):<br>
&#9;&#9;self._control_frames.append(frame)<br>
<br>
&#9;def control_task(self, delta):<br>
&#9;&#9;return self._control_screw.vector()<br>
<br>
&#9;def set_control_screw(self, screw):<br>
&#9;&#9;rotated_to_local = screw.inverse_rotate_by(self.position())<br>
&#9;&#9;self._control_screw = rotated_to_local<br>
<br>
&#9;def Ksi_matrix_list(self, delta, allctrlinks):<br>
&#9;&#9;lst = []<br>
&#9;&#9;derivatives = []<br>
&#9;&#9;for link in allctrlinks:<br>
&#9;&#9;&#9;link_dim = len(link.screw_commutator().indexes())<br>
&#9;&#9;&#9;frame_dim = len(self.screw_commutator().indexes())<br>
&#9;&#9;&#9;if link not in self._control_frames:<br>
&#9;&#9;&#9;&#9;derivatives.append(numpy.zeros((frame_dim, link_dim)))<br>
&#9;&#9;&#9;&#9;continue                <br>
&#9;&#9;&#9;derivative = self.derivative_by_frame(link)<br>
&#9;&#9;&#9;derivatives.append(derivative.matrix)<br>
&#9;&#9;&#9;<br>
&#9;&#9;derivative = numpy.concatenate(derivatives, axis=1)<br>
&#9;&#9;pinv_derivative = numpy.linalg.pinv(derivative)<br>
&#9;&#9;res = pinv_derivative @ self.control_task(delta)<br>
<br>
&#9;&#9;if self._filter is not None:<br>
&#9;&#9;&#9;res = self._filter @ res<br>
&#9;&#9;<br>
&#9;&#9;counter = 0<br>
&#9;&#9;for i in range(len(allctrlinks)):<br>
&#9;&#9;&#9;link = allctrlinks[i]<br>
&#9;&#9;&#9;link_dim = len(link.screw_commutator().indexes())<br>
&#9;&#9;&#9;lst.append(IndexedVector(<br>
&#9;&#9;&#9;&#9;res[counter:counter+link_dim],<br>
&#9;&#9;&#9;&#9;idxs=link.screw_commutator().indexes(), <br>
&#9;&#9;&#9;&#9;comm=link.screw_commutator())<br>
&#9;&#9;&#9;)<br>
&#9;&#9;&#9;counter += link_dim<br>
&#9;&#9;<br>
&#9;&#9;return lst<br>
<!-- END SCAT CODE -->
</body>
</html>
