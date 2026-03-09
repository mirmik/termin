#!/usr/bin/env python3

import numpy
from termin.physics.screw_commutator import VariableValueCommutator
from termin.ga201.motor import Motor2
from termin.ga201.screw import Screw2
from termin.physics.pose_object import ReferencedPoseObject, PoseObject
from termin.physics.screw_commutator import ScrewCommutator
from termin.physics.indexed_matrix import IndexedVector
from termin.physics.frame import Frame


POSITION_STIFFNESS = 10
VELOCITY_STIFFNESS = 20

class VariableMultiForce(Frame):
    def __init__(self, position, child, parent, senses=[], stiffness=[POSITION_STIFFNESS, VELOCITY_STIFFNESS], flexible=False):
        self._flexible = flexible
        self._position_in_child_frame = child.position().inverse() * position
        if parent is not None:
            self._position_in_parent_frame = parent.position().inverse() * position
            self._pose_object = ReferencedPoseObject(
                parent=parent._pose_object, pose=self._position_in_parent_frame)
        else:
            self._position_in_parent_frame = position
            self._pose_object = PoseObject(
                pose=self._position_in_parent_frame)

        super().__init__(pose_object=self._pose_object, screws=senses)
        
        self._child = child
        self._parent = parent
        self._senses = senses
        self._stiffness = stiffness

    def senses(self):
        return self._senses

    def diff_position(self):
        return self.position_error_screw()

    def position_error_motor(self):
        position_as_child = self.global_position_by_child()
        position_as_parent = self.global_position_by_parent()
        diff = position_as_parent.inverse() * position_as_child
        return diff

    def position_error_screw(self):
        return self.position_error_motor().log()

    def velocity_error_screw(self):
        parent_velocity = self.frame_velocity_by_parent()
        child_velocity = self.frame_velocity_by_child()
        return child_velocity - parent_velocity

    def frame_velocity_by_parent(self):
        if self._parent is None:
            return Screw2()
        
        vel = self._parent.right_velocity()
        res = (vel
            .inverse_carry(self._position_in_parent_frame)
        )
        return vel

    def frame_velocity_by_child(self):
        diff = self.position_error_motor()
        vel = self._child.right_velocity()
        res = (vel
            .inverse_carry(self._position_in_child_frame)
            .carry(diff)
        )
        return res

    def global_position_by_parent(self):
        if self._parent is None:
            return self._position_in_parent_frame
        return self._parent.position() * self._position_in_parent_frame

    def global_position_by_child(self):
        return self._child.position() * self._position_in_child_frame

    def B_matrix_list(self):
        if self._flexible:
            return []

        dQdl_child = self.derivative_by_frame(self._child).transpose()

        if self._parent is not None:
            # Минус из-за того, что в родительском фрейме чувствительность обратна чувствительности в дочернем фрейме
            dQdl_parent = -self.derivative_by_frame(self._parent).transpose()
            return [dQdl_child, dQdl_parent]
        else:
            return [dQdl_child]

    def C_matrix_list(self):
        if not self._flexible:
            return []

        ret = []

        poserror_scr = self.position_error_screw()
        velerror_scr = self.velocity_error_screw()
        poserror_mot = self.position_error_motor()
        force = (
            - poserror_scr * self._stiffness[0] 
            - velerror_scr * self._stiffness[1]
        )

        force_child = (force
            .inverse_carry(poserror_mot) 
            .carry(self._position_in_child_frame)
        )
        ret.append(IndexedVector(
            force_child.toarray(),
            idxs=self._child.screw_commutator().indexes(),
            comm=self._child.screw_commutator()))

        if self._parent is not None:
            force_parent = ((-force)
                .carry(self._position_in_parent_frame)
            )

            ret.append(IndexedVector(
                force_parent.toarray(),
                idxs=self._parent.screw_commutator().indexes(),
                comm=self._parent.screw_commutator())
            )
        
        return ret

    def D_matrix_list(self):
        return []

        # poserror = self.position_error_screw()
        # velerror = self.velocity_error_screw()
        # posdots = numpy.array([poserror.fulldot(s)
        #                     for s in self._senses]) * self._stiffness[0]
        # veldots = numpy.array([velerror.fulldot(s)
        #                     for s in self._senses]) * self._stiffness[1]
        # correction = - posdots - veldots
        # print("correction", correction)
        # return [IndexedVector(
        #         correction,
        #         idxs=self._screw_commutator.indexes(),
        #         comm=self._screw_commutator)
        #         ]
        

    def D_matrix_list_velocity(self):
        if self._flexible:
            return []
        velerror = self.velocity_error_screw()
        veldots = numpy.array([velerror.fulldot(s)
                            for s in self._senses])

        correction = - veldots
        return [IndexedVector(
                correction,
                idxs=self._screw_commutator.indexes(),
                comm=self._screw_commutator)]

    def D_matrix_list_position(self):
        if self._flexible:
            return []
        
        poserror = self.position_error_screw()
        posdots = numpy.array([poserror.fulldot(s)
                            for s in self._senses])

        correction = - posdots
        return [IndexedVector(
                correction,
                idxs=self._screw_commutator.indexes(),
                comm=self._screw_commutator)]



if __name__ == "__main__":
    from termin.physics.body import Body2
    b1 = Body2()
    b2 = Body2()

    b1.set_position(Motor2.translation(1, 0))
    b2.set_position(Motor2.translation(2, 0))

    fl = VariableMultiForce(Motor2.translation(
        2, 0), b1, b2, senses=[Screw2(m=1), Screw2(v=[1, 0]), Screw2(v=[0, 1])])

    for s in fl.senses():
        print(s)

    B_list = fl.B_matrix_list()
    for B in B_list:
        print(B)
