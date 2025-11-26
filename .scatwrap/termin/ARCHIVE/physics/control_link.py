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
    def __init__(self, position, child, parent, senses=[], stiffness=[1, 1]):<br>
        super().__init__(position, child, parent, senses, stiffness)<br>
        self._control = None<br>
        self.curtime = 0<br>
        self.target = numpy.array([0,0])<br>
        self._filter = None<br>
<br>
    def set_filter(self, filter):<br>
        self._filter = filter<br>
<br>
    def set_control(self, control_vector):<br>
        self._control = control_vector<br>
<br>
    def H_matrix_list(self):<br>
        dQdl_child = self.derivative_by_frame(self._child).transpose()<br>
        if self._parent is not None:<br>
            dQdl_parent = -self.derivative_by_frame(self._parent).transpose()<br>
            return [dQdl_child, dQdl_parent]<br>
        else:<br>
            return [dQdl_child]<br>
    <br>
    def Ksi_matrix_list(self, delta, allctrlinks):<br>
        if self._control is None:<br>
            return []<br>
<br>
        myposition = allctrlinks.index(self)<br>
        ctr = self._control.reshape((len(self._control), 1))<br>
        #print(&quot;C1:&quot;, ctr)<br>
<br>
        # if self._filter is not None:<br>
        #     mat = []<br>
        #     counter = 0<br>
        #     for link in allctrlinks:<br>
        #         if link is not self:<br>
        #             mat.append(numpy.zeros((1, 1)))<br>
        #         else:<br>
        #             mat.append(ctr)<br>
        #         counter += 1<br>
        #     ctr = numpy.concatenate(mat, axis=0)<br>
        #     ctr = self._filter @ ctr<br>
        #     print(ctr)<br>
<br>
        #     ctr = numpy.array([ctr[myposition]])<br>
            <br>
        ctr = ctr.reshape((len(self._control),))<br>
        #print(&quot;C2:&quot;, ctr)<br>
        #print(&quot;C3:&quot;, self.screw_commutator().indexes())<br>
        return [<br>
            IndexedVector(ctr, self.screw_commutator().indexes(), self.screw_commutator())<br>
        ]<br>
<br>
<br>
class ControlTaskFrame(ReferencedFrame):<br>
    def __init__(self, linked_body, position_in_body):<br>
        senses = [<br>
            #Screw2(m=1),<br>
            Screw2(v=[1,0]),<br>
            Screw2(v=[0,1]),<br>
        ]<br>
        super().__init__(linked_body, position_in_body, senses)<br>
        self.curtime = 0<br>
        self._control_screw = Screw2()<br>
        self._control_frames = []<br>
        self._filter = None<br>
<br>
    def set_filter(self, filter):<br>
        self._filter = filter<br>
<br>
    def add_control_frame(self, frame):<br>
        self._control_frames.append(frame)<br>
<br>
    def control_task(self, delta):<br>
        return self._control_screw.vector()<br>
<br>
    def set_control_screw(self, screw):<br>
        rotated_to_local = screw.inverse_rotate_by(self.position())<br>
        self._control_screw = rotated_to_local<br>
<br>
    def Ksi_matrix_list(self, delta, allctrlinks):<br>
        lst = []<br>
        derivatives = []<br>
        for link in allctrlinks:<br>
            link_dim = len(link.screw_commutator().indexes())<br>
            frame_dim = len(self.screw_commutator().indexes())<br>
            if link not in self._control_frames:<br>
                derivatives.append(numpy.zeros((frame_dim, link_dim)))<br>
                continue                <br>
            derivative = self.derivative_by_frame(link)<br>
            derivatives.append(derivative.matrix)<br>
            <br>
        derivative = numpy.concatenate(derivatives, axis=1)<br>
        pinv_derivative = numpy.linalg.pinv(derivative)<br>
        res = pinv_derivative @ self.control_task(delta)<br>
<br>
        if self._filter is not None:<br>
            res = self._filter @ res<br>
        <br>
        counter = 0<br>
        for i in range(len(allctrlinks)):<br>
            link = allctrlinks[i]<br>
            link_dim = len(link.screw_commutator().indexes())<br>
            lst.append(IndexedVector(<br>
                res[counter:counter+link_dim],<br>
                idxs=link.screw_commutator().indexes(), <br>
                comm=link.screw_commutator())<br>
            )<br>
            counter += link_dim<br>
        <br>
        return lst<br>
<!-- END SCAT CODE -->
</body>
</html>
