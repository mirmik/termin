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
    def __init__(self, position, child, parent, senses=[], stiffness=[POSITION_STIFFNESS, VELOCITY_STIFFNESS], flexible=False):<br>
        self._flexible = flexible<br>
        self._position_in_child_frame = child.position().inverse() * position<br>
        if parent is not None:<br>
            self._position_in_parent_frame = parent.position().inverse() * position<br>
            self._pose_object = ReferencedPoseObject(<br>
                parent=parent._pose_object, pose=self._position_in_parent_frame)<br>
        else:<br>
            self._position_in_parent_frame = position<br>
            self._pose_object = PoseObject(<br>
                pose=self._position_in_parent_frame)<br>
<br>
        super().__init__(pose_object=self._pose_object, screws=senses)<br>
        <br>
        self._child = child<br>
        self._parent = parent<br>
        self._senses = senses<br>
        self._stiffness = stiffness<br>
<br>
    def senses(self):<br>
        return self._senses<br>
<br>
    def diff_position(self):<br>
        return self.position_error_screw()<br>
<br>
    def position_error_motor(self):<br>
        position_as_child = self.global_position_by_child()<br>
        position_as_parent = self.global_position_by_parent()<br>
        diff = position_as_parent.inverse() * position_as_child<br>
        return diff<br>
<br>
    def position_error_screw(self):<br>
        return self.position_error_motor().log()<br>
<br>
    def velocity_error_screw(self):<br>
        parent_velocity = self.frame_velocity_by_parent()<br>
        child_velocity = self.frame_velocity_by_child()<br>
        return child_velocity - parent_velocity<br>
<br>
    def frame_velocity_by_parent(self):<br>
        if self._parent is None:<br>
            return Screw2()<br>
        <br>
        vel = self._parent.right_velocity()<br>
        res = (vel<br>
            .inverse_carry(self._position_in_parent_frame)<br>
        )<br>
        return vel<br>
<br>
    def frame_velocity_by_child(self):<br>
        diff = self.position_error_motor()<br>
        vel = self._child.right_velocity()<br>
        res = (vel<br>
            .inverse_carry(self._position_in_child_frame)<br>
            .carry(diff)<br>
        )<br>
        return res<br>
<br>
    def global_position_by_parent(self):<br>
        if self._parent is None:<br>
            return self._position_in_parent_frame<br>
        return self._parent.position() * self._position_in_parent_frame<br>
<br>
    def global_position_by_child(self):<br>
        return self._child.position() * self._position_in_child_frame<br>
<br>
    def B_matrix_list(self):<br>
        if self._flexible:<br>
            return []<br>
<br>
        dQdl_child = self.derivative_by_frame(self._child).transpose()<br>
<br>
        if self._parent is not None:<br>
            # Минус из-за того, что в родительском фрейме чувствительность обратна чувствительности в дочернем фрейме<br>
            dQdl_parent = -self.derivative_by_frame(self._parent).transpose()<br>
            return [dQdl_child, dQdl_parent]<br>
        else:<br>
            return [dQdl_child]<br>
<br>
    def C_matrix_list(self):<br>
        if not self._flexible:<br>
            return []<br>
<br>
        ret = []<br>
<br>
        poserror_scr = self.position_error_screw()<br>
        velerror_scr = self.velocity_error_screw()<br>
        poserror_mot = self.position_error_motor()<br>
        force = (<br>
            - poserror_scr * self._stiffness[0] <br>
            - velerror_scr * self._stiffness[1]<br>
        )<br>
<br>
        force_child = (force<br>
            .inverse_carry(poserror_mot) <br>
            .carry(self._position_in_child_frame)<br>
        )<br>
        ret.append(IndexedVector(<br>
            force_child.toarray(),<br>
            idxs=self._child.screw_commutator().indexes(),<br>
            comm=self._child.screw_commutator()))<br>
<br>
        if self._parent is not None:<br>
            force_parent = ((-force)<br>
                .carry(self._position_in_parent_frame)<br>
            )<br>
<br>
            ret.append(IndexedVector(<br>
                force_parent.toarray(),<br>
                idxs=self._parent.screw_commutator().indexes(),<br>
                comm=self._parent.screw_commutator())<br>
            )<br>
        <br>
        return ret<br>
<br>
    def D_matrix_list(self):<br>
        return []<br>
<br>
        # poserror = self.position_error_screw()<br>
        # velerror = self.velocity_error_screw()<br>
        # posdots = numpy.array([poserror.fulldot(s)<br>
        #                     for s in self._senses]) * self._stiffness[0]<br>
        # veldots = numpy.array([velerror.fulldot(s)<br>
        #                     for s in self._senses]) * self._stiffness[1]<br>
        # correction = - posdots - veldots<br>
        # print(&quot;correction&quot;, correction)<br>
        # return [IndexedVector(<br>
        #         correction,<br>
        #         idxs=self._screw_commutator.indexes(),<br>
        #         comm=self._screw_commutator)<br>
        #         ]<br>
        <br>
<br>
    def D_matrix_list_velocity(self):<br>
        if self._flexible:<br>
            return []<br>
        velerror = self.velocity_error_screw()<br>
        veldots = numpy.array([velerror.fulldot(s)<br>
                            for s in self._senses])<br>
<br>
        correction = - veldots<br>
        return [IndexedVector(<br>
                correction,<br>
                idxs=self._screw_commutator.indexes(),<br>
                comm=self._screw_commutator)]<br>
<br>
    def D_matrix_list_position(self):<br>
        if self._flexible:<br>
            return []<br>
        <br>
        poserror = self.position_error_screw()<br>
        posdots = numpy.array([poserror.fulldot(s)<br>
                            for s in self._senses])<br>
<br>
        correction = - posdots<br>
        return [IndexedVector(<br>
                correction,<br>
                idxs=self._screw_commutator.indexes(),<br>
                comm=self._screw_commutator)]<br>
<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    from termin.physics.body import Body2<br>
    b1 = Body2()<br>
    b2 = Body2()<br>
<br>
    b1.set_position(Motor2.translation(1, 0))<br>
    b2.set_position(Motor2.translation(2, 0))<br>
<br>
    fl = VariableMultiForce(Motor2.translation(<br>
        2, 0), b1, b2, senses=[Screw2(m=1), Screw2(v=[1, 0]), Screw2(v=[0, 1])])<br>
<br>
    for s in fl.senses():<br>
        print(s)<br>
<br>
    B_list = fl.B_matrix_list()<br>
    for B in B_list:<br>
        print(B)<br>
<!-- END SCAT CODE -->
</body>
</html>
