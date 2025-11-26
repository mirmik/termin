<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/force_link.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
import numpy<br>
from termin.physics.screw_commutator import VariableValueCommutator<br>
from termin.ga201.motor import Motor2<br>
from termin.ga201.screw import Screw2<br>
from termin.physics.pose_object import ReferencedPoseObject, PoseObject<br>
from termin.physics.screw_commutator import ScrewCommutator<br>
from termin.physics.indexed_matrix import IndexedVector<br>
from termin.physics.frame import Frame<br>
<br>
<br>
POSITION_STIFFNESS = 10<br>
VELOCITY_STIFFNESS = 20<br>
<br>
class VariableMultiForce(Frame):<br>
&#9;def __init__(self, position, child, parent, senses=[], stiffness=[POSITION_STIFFNESS, VELOCITY_STIFFNESS], flexible=False):<br>
&#9;&#9;self._flexible = flexible<br>
&#9;&#9;self._position_in_child_frame = child.position().inverse() * position<br>
&#9;&#9;if parent is not None:<br>
&#9;&#9;&#9;self._position_in_parent_frame = parent.position().inverse() * position<br>
&#9;&#9;&#9;self._pose_object = ReferencedPoseObject(<br>
&#9;&#9;&#9;&#9;parent=parent._pose_object, pose=self._position_in_parent_frame)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;self._position_in_parent_frame = position<br>
&#9;&#9;&#9;self._pose_object = PoseObject(<br>
&#9;&#9;&#9;&#9;pose=self._position_in_parent_frame)<br>
<br>
&#9;&#9;super().__init__(pose_object=self._pose_object, screws=senses)<br>
&#9;&#9;<br>
&#9;&#9;self._child = child<br>
&#9;&#9;self._parent = parent<br>
&#9;&#9;self._senses = senses<br>
&#9;&#9;self._stiffness = stiffness<br>
<br>
&#9;def senses(self):<br>
&#9;&#9;return self._senses<br>
<br>
&#9;def diff_position(self):<br>
&#9;&#9;return self.position_error_screw()<br>
<br>
&#9;def position_error_motor(self):<br>
&#9;&#9;position_as_child = self.global_position_by_child()<br>
&#9;&#9;position_as_parent = self.global_position_by_parent()<br>
&#9;&#9;diff = position_as_parent.inverse() * position_as_child<br>
&#9;&#9;return diff<br>
<br>
&#9;def position_error_screw(self):<br>
&#9;&#9;return self.position_error_motor().log()<br>
<br>
&#9;def velocity_error_screw(self):<br>
&#9;&#9;parent_velocity = self.frame_velocity_by_parent()<br>
&#9;&#9;child_velocity = self.frame_velocity_by_child()<br>
&#9;&#9;return child_velocity - parent_velocity<br>
<br>
&#9;def frame_velocity_by_parent(self):<br>
&#9;&#9;if self._parent is None:<br>
&#9;&#9;&#9;return Screw2()<br>
&#9;&#9;<br>
&#9;&#9;vel = self._parent.right_velocity()<br>
&#9;&#9;res = (vel<br>
&#9;&#9;&#9;.inverse_carry(self._position_in_parent_frame)<br>
&#9;&#9;)<br>
&#9;&#9;return vel<br>
<br>
&#9;def frame_velocity_by_child(self):<br>
&#9;&#9;diff = self.position_error_motor()<br>
&#9;&#9;vel = self._child.right_velocity()<br>
&#9;&#9;res = (vel<br>
&#9;&#9;&#9;.inverse_carry(self._position_in_child_frame)<br>
&#9;&#9;&#9;.carry(diff)<br>
&#9;&#9;)<br>
&#9;&#9;return res<br>
<br>
&#9;def global_position_by_parent(self):<br>
&#9;&#9;if self._parent is None:<br>
&#9;&#9;&#9;return self._position_in_parent_frame<br>
&#9;&#9;return self._parent.position() * self._position_in_parent_frame<br>
<br>
&#9;def global_position_by_child(self):<br>
&#9;&#9;return self._child.position() * self._position_in_child_frame<br>
<br>
&#9;def B_matrix_list(self):<br>
&#9;&#9;if self._flexible:<br>
&#9;&#9;&#9;return []<br>
<br>
&#9;&#9;dQdl_child = self.derivative_by_frame(self._child).transpose()<br>
<br>
&#9;&#9;if self._parent is not None:<br>
&#9;&#9;&#9;# Минус из-за того, что в родительском фрейме чувствительность обратна чувствительности в дочернем фрейме<br>
&#9;&#9;&#9;dQdl_parent = -self.derivative_by_frame(self._parent).transpose()<br>
&#9;&#9;&#9;return [dQdl_child, dQdl_parent]<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;return [dQdl_child]<br>
<br>
&#9;def C_matrix_list(self):<br>
&#9;&#9;if not self._flexible:<br>
&#9;&#9;&#9;return []<br>
<br>
&#9;&#9;ret = []<br>
<br>
&#9;&#9;poserror_scr = self.position_error_screw()<br>
&#9;&#9;velerror_scr = self.velocity_error_screw()<br>
&#9;&#9;poserror_mot = self.position_error_motor()<br>
&#9;&#9;force = (<br>
&#9;&#9;&#9;- poserror_scr * self._stiffness[0] <br>
&#9;&#9;&#9;- velerror_scr * self._stiffness[1]<br>
&#9;&#9;)<br>
<br>
&#9;&#9;force_child = (force<br>
&#9;&#9;&#9;.inverse_carry(poserror_mot) <br>
&#9;&#9;&#9;.carry(self._position_in_child_frame)<br>
&#9;&#9;)<br>
&#9;&#9;ret.append(IndexedVector(<br>
&#9;&#9;&#9;force_child.toarray(),<br>
&#9;&#9;&#9;idxs=self._child.screw_commutator().indexes(),<br>
&#9;&#9;&#9;comm=self._child.screw_commutator()))<br>
<br>
&#9;&#9;if self._parent is not None:<br>
&#9;&#9;&#9;force_parent = ((-force)<br>
&#9;&#9;&#9;&#9;.carry(self._position_in_parent_frame)<br>
&#9;&#9;&#9;)<br>
<br>
&#9;&#9;&#9;ret.append(IndexedVector(<br>
&#9;&#9;&#9;&#9;force_parent.toarray(),<br>
&#9;&#9;&#9;&#9;idxs=self._parent.screw_commutator().indexes(),<br>
&#9;&#9;&#9;&#9;comm=self._parent.screw_commutator())<br>
&#9;&#9;&#9;)<br>
&#9;&#9;<br>
&#9;&#9;return ret<br>
<br>
&#9;def D_matrix_list(self):<br>
&#9;&#9;return []<br>
<br>
&#9;&#9;# poserror = self.position_error_screw()<br>
&#9;&#9;# velerror = self.velocity_error_screw()<br>
&#9;&#9;# posdots = numpy.array([poserror.fulldot(s)<br>
&#9;&#9;#                     for s in self._senses]) * self._stiffness[0]<br>
&#9;&#9;# veldots = numpy.array([velerror.fulldot(s)<br>
&#9;&#9;#                     for s in self._senses]) * self._stiffness[1]<br>
&#9;&#9;# correction = - posdots - veldots<br>
&#9;&#9;# print(&quot;correction&quot;, correction)<br>
&#9;&#9;# return [IndexedVector(<br>
&#9;&#9;#         correction,<br>
&#9;&#9;#         idxs=self._screw_commutator.indexes(),<br>
&#9;&#9;#         comm=self._screw_commutator)<br>
&#9;&#9;#         ]<br>
&#9;&#9;<br>
<br>
&#9;def D_matrix_list_velocity(self):<br>
&#9;&#9;if self._flexible:<br>
&#9;&#9;&#9;return []<br>
&#9;&#9;velerror = self.velocity_error_screw()<br>
&#9;&#9;veldots = numpy.array([velerror.fulldot(s)<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;for s in self._senses])<br>
<br>
&#9;&#9;correction = - veldots<br>
&#9;&#9;return [IndexedVector(<br>
&#9;&#9;&#9;&#9;correction,<br>
&#9;&#9;&#9;&#9;idxs=self._screw_commutator.indexes(),<br>
&#9;&#9;&#9;&#9;comm=self._screw_commutator)]<br>
<br>
&#9;def D_matrix_list_position(self):<br>
&#9;&#9;if self._flexible:<br>
&#9;&#9;&#9;return []<br>
&#9;&#9;<br>
&#9;&#9;poserror = self.position_error_screw()<br>
&#9;&#9;posdots = numpy.array([poserror.fulldot(s)<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;for s in self._senses])<br>
<br>
&#9;&#9;correction = - posdots<br>
&#9;&#9;return [IndexedVector(<br>
&#9;&#9;&#9;&#9;correction,<br>
&#9;&#9;&#9;&#9;idxs=self._screw_commutator.indexes(),<br>
&#9;&#9;&#9;&#9;comm=self._screw_commutator)]<br>
<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;from termin.physics.body import Body2<br>
&#9;b1 = Body2()<br>
&#9;b2 = Body2()<br>
<br>
&#9;b1.set_position(Motor2.translation(1, 0))<br>
&#9;b2.set_position(Motor2.translation(2, 0))<br>
<br>
&#9;fl = VariableMultiForce(Motor2.translation(<br>
&#9;&#9;2, 0), b1, b2, senses=[Screw2(m=1), Screw2(v=[1, 0]), Screw2(v=[0, 1])])<br>
<br>
&#9;for s in fl.senses():<br>
&#9;&#9;print(s)<br>
<br>
&#9;B_list = fl.B_matrix_list()<br>
&#9;for B in B_list:<br>
&#9;&#9;print(B)<br>
<!-- END SCAT CODE -->
</body>
</html>
