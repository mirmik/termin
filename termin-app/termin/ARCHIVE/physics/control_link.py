import numpy
from termin.physics.force_link import VariableMultiForce
from termin.physics.frame import Frame, ReferencedFrame
from termin.physics.pose_object import ReferencedPoseObject
from termin.ga201.screw import Screw2
from termin.physics.pose_object import ReferencedPoseObject, PoseObject
from termin.physics.screw_commutator import ScrewCommutator
from termin.physics.indexed_matrix import IndexedVector

from termin.physics.extlinalg import outkernel_operator
from termin.physics.extlinalg import kernel_operator
import math
import time

start_time = 0

class ControlLink(VariableMultiForce):
    def __init__(self, position, child, parent, senses=[], stiffness=[1, 1]):
        super().__init__(position, child, parent, senses, stiffness)
        self._control = None
        self.curtime = 0
        self.target = numpy.array([0,0])
        self._filter = None

    def set_filter(self, filter):
        self._filter = filter

    def set_control(self, control_vector):
        self._control = control_vector

    def H_matrix_list(self):
        dQdl_child = self.derivative_by_frame(self._child).transpose()
        if self._parent is not None:
            dQdl_parent = -self.derivative_by_frame(self._parent).transpose()
            return [dQdl_child, dQdl_parent]
        else:
            return [dQdl_child]
    
    def Ksi_matrix_list(self, delta, allctrlinks):
        if self._control is None:
            return []

        myposition = allctrlinks.index(self)
        ctr = self._control.reshape((len(self._control), 1))
        #print("C1:", ctr)

        # if self._filter is not None:
        #     mat = []
        #     counter = 0
        #     for link in allctrlinks:
        #         if link is not self:
        #             mat.append(numpy.zeros((1, 1)))
        #         else:
        #             mat.append(ctr)
        #         counter += 1
        #     ctr = numpy.concatenate(mat, axis=0)
        #     ctr = self._filter @ ctr
        #     print(ctr)

        #     ctr = numpy.array([ctr[myposition]])
            
        ctr = ctr.reshape((len(self._control),))
        #print("C2:", ctr)
        #print("C3:", self.screw_commutator().indexes())
        return [
            IndexedVector(ctr, self.screw_commutator().indexes(), self.screw_commutator())
        ]


class ControlTaskFrame(ReferencedFrame):
    def __init__(self, linked_body, position_in_body):
        senses = [
            #Screw2(m=1),
            Screw2(v=[1,0]),
            Screw2(v=[0,1]),
        ]
        super().__init__(linked_body, position_in_body, senses)
        self.curtime = 0
        self._control_screw = Screw2()
        self._control_frames = []
        self._filter = None

    def set_filter(self, filter):
        self._filter = filter

    def add_control_frame(self, frame):
        self._control_frames.append(frame)

    def control_task(self, delta):
        return self._control_screw.vector()

    def set_control_screw(self, screw):
        rotated_to_local = screw.inverse_rotate_by(self.position())
        self._control_screw = rotated_to_local

    def Ksi_matrix_list(self, delta, allctrlinks):
        lst = []
        derivatives = []
        for link in allctrlinks:
            link_dim = len(link.screw_commutator().indexes())
            frame_dim = len(self.screw_commutator().indexes())
            if link not in self._control_frames:
                derivatives.append(numpy.zeros((frame_dim, link_dim)))
                continue                
            derivative = self.derivative_by_frame(link)
            derivatives.append(derivative.matrix)
            
        derivative = numpy.concatenate(derivatives, axis=1)
        pinv_derivative = numpy.linalg.pinv(derivative)
        res = pinv_derivative @ self.control_task(delta)

        if self._filter is not None:
            res = self._filter @ res
        
        counter = 0
        for i in range(len(allctrlinks)):
            link = allctrlinks[i]
            link_dim = len(link.screw_commutator().indexes())
            lst.append(IndexedVector(
                res[counter:counter+link_dim],
                idxs=link.screw_commutator().indexes(), 
                comm=link.screw_commutator())
            )
            counter += link_dim
        
        return lst