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
    def __init__(self, pose_object, screws):<br>
        self._pose_object = pose_object<br>
        self._screw_commutator = ScrewCommutator(<br>
            local_senses=screws, pose_object=self._pose_object)<br>
<br>
    def screw_commutator(self):<br>
        return self._screw_commutator<br>
<br>
    def commutator(self):<br>
        return self._screw_commutator<br>
<br>
    def derivative_by_frame(self, other):<br>
        return self.screw_commutator().derivative(<br>
            other.screw_commutator())<br>
<br>
    # def global_derivative_by_frame(self, other):<br>
    #     return self.screw_commutator().derivative(<br>
    #         other.screw_commutator())<br>
<br>
    def position(self):<br>
        return self._pose_object.position()<br>
<br>
class MultiFrame(Frame):<br>
    def __init__(self):<br>
        self._frames = []<br>
<br>
    def add_frame(self, frame):<br>
        self._frames.append(frame)<br>
<br>
    def derivative_by_frame(self, other):<br>
        list_of_derivatives = []<br>
        for frame in self._frames:<br>
            der = frame.derivative_by_frame(other).matrix<br>
            list_of_derivatives.append(der)<br>
            #print(der)<br>
        return np.concatenate(list_of_derivatives, axis=0)<br>
<br>
    def outkernel_operator_by_frame(self, frame):<br>
        derivative = self.derivative_by_frame(frame)<br>
        return derivative @ np.linalg.pinv(derivative)<br>
<br>
    def kernel_operator_by_frame(self, frame):<br>
        outkernel = self.outkernel_operator_by_frame(frame)<br>
        return np.eye(outkernel.shape[0]) - outkernel<br>
    <br>
    <br>
<br>
class ReferencedFrame(Frame):<br>
    def __init__(self, linked_body, position_in_body, senses):<br>
        self._parent = linked_body<br>
        pose_object = ReferencedPoseObject(<br>
            parent=linked_body._pose_object, pose=position_in_body)<br>
        super().__init__(pose_object=pose_object, screws=senses)<br>
<br>
    def current_position(self):<br>
        return self.position()<br>
<br>
    def right_velocity(self):<br>
        parent_right_velocity = self._parent.right_velocity()<br>
        carried = parent_right_velocity.kinematic_carry(<br>
            self._pose_object.relative_position())<br>
        return carried<br>
<br>
    def right_velocity_global(self):<br>
        right_velocity = self.right_velocity()<br>
        rotated = right_velocity.rotate_by(self.position())<br>
        return rotated<br>
<br>
    def right_acceleration(self):<br>
        parent_right_acceleration = self._parent.right_acceleration()<br>
        carried = parent_right_acceleration.kinematic_carry(<br>
            self._pose_object.relative_position())<br>
        return carried<br>
<br>
    def right_acceleration_global(self):<br>
        right_acceleration = self.right_acceleration()<br>
        rotated = right_acceleration.rotate_by(self.position())<br>
        return rotated<br>
        <br>
<!-- END SCAT CODE -->
</body>
</html>
