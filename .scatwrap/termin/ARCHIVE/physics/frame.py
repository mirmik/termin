<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/frame.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
from termin.physics.screw_commutator import ScrewCommutator<br>
from termin.ga201.screw import Screw2<br>
from termin.physics.pose_object import ReferencedPoseObject, PoseObject<br>
<br>
class Frame:<br>
&#9;def __init__(self, pose_object, screws):<br>
&#9;&#9;self._pose_object = pose_object<br>
&#9;&#9;self._screw_commutator = ScrewCommutator(<br>
&#9;&#9;&#9;local_senses=screws, pose_object=self._pose_object)<br>
<br>
&#9;def screw_commutator(self):<br>
&#9;&#9;return self._screw_commutator<br>
<br>
&#9;def commutator(self):<br>
&#9;&#9;return self._screw_commutator<br>
<br>
&#9;def derivative_by_frame(self, other):<br>
&#9;&#9;return self.screw_commutator().derivative(<br>
&#9;&#9;&#9;other.screw_commutator())<br>
<br>
&#9;# def global_derivative_by_frame(self, other):<br>
&#9;#     return self.screw_commutator().derivative(<br>
&#9;#         other.screw_commutator())<br>
<br>
&#9;def position(self):<br>
&#9;&#9;return self._pose_object.position()<br>
<br>
class MultiFrame(Frame):<br>
&#9;def __init__(self):<br>
&#9;&#9;self._frames = []<br>
<br>
&#9;def add_frame(self, frame):<br>
&#9;&#9;self._frames.append(frame)<br>
<br>
&#9;def derivative_by_frame(self, other):<br>
&#9;&#9;list_of_derivatives = []<br>
&#9;&#9;for frame in self._frames:<br>
&#9;&#9;&#9;der = frame.derivative_by_frame(other).matrix<br>
&#9;&#9;&#9;list_of_derivatives.append(der)<br>
&#9;&#9;&#9;#print(der)<br>
&#9;&#9;return np.concatenate(list_of_derivatives, axis=0)<br>
<br>
&#9;def outkernel_operator_by_frame(self, frame):<br>
&#9;&#9;derivative = self.derivative_by_frame(frame)<br>
&#9;&#9;return derivative @ np.linalg.pinv(derivative)<br>
<br>
&#9;def kernel_operator_by_frame(self, frame):<br>
&#9;&#9;outkernel = self.outkernel_operator_by_frame(frame)<br>
&#9;&#9;return np.eye(outkernel.shape[0]) - outkernel<br>
&#9;<br>
&#9;<br>
<br>
class ReferencedFrame(Frame):<br>
&#9;def __init__(self, linked_body, position_in_body, senses):<br>
&#9;&#9;self._parent = linked_body<br>
&#9;&#9;pose_object = ReferencedPoseObject(<br>
&#9;&#9;&#9;parent=linked_body._pose_object, pose=position_in_body)<br>
&#9;&#9;super().__init__(pose_object=pose_object, screws=senses)<br>
<br>
&#9;def current_position(self):<br>
&#9;&#9;return self.position()<br>
<br>
&#9;def right_velocity(self):<br>
&#9;&#9;parent_right_velocity = self._parent.right_velocity()<br>
&#9;&#9;carried = parent_right_velocity.kinematic_carry(<br>
&#9;&#9;&#9;self._pose_object.relative_position())<br>
&#9;&#9;return carried<br>
<br>
&#9;def right_velocity_global(self):<br>
&#9;&#9;right_velocity = self.right_velocity()<br>
&#9;&#9;rotated = right_velocity.rotate_by(self.position())<br>
&#9;&#9;return rotated<br>
<br>
&#9;def right_acceleration(self):<br>
&#9;&#9;parent_right_acceleration = self._parent.right_acceleration()<br>
&#9;&#9;carried = parent_right_acceleration.kinematic_carry(<br>
&#9;&#9;&#9;self._pose_object.relative_position())<br>
&#9;&#9;return carried<br>
<br>
&#9;def right_acceleration_global(self):<br>
&#9;&#9;right_acceleration = self.right_acceleration()<br>
&#9;&#9;rotated = right_acceleration.rotate_by(self.position())<br>
&#9;&#9;return rotated<br>
&#9;&#9;<br>
<!-- END SCAT CODE -->
</body>
</html>
