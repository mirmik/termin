<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/screw_commutator.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
import numpy<br>
from termin.physics.pose_object import PoseObject<br>
from termin.physics.indexed_matrix import IndexedMatrix, IndexedVector<br>
from termin.ga201.motor import Motor2<br>
from termin.ga201.screw import Screw2<br>
import math<br>
<br>
<br>
class VariableValueCommutator:<br>
    def __init__(self, dim):<br>
        self._dim = dim<br>
        self._sources = [VariableValue(self, i) for i in range(dim)]<br>
        self._values = [0] * dim<br>
<br>
    def sources(self):<br>
        return self._sources<br>
<br>
    def set_value(self, idx: int, value: float):<br>
        self._values[idx] = value<br>
<br>
    def values(self):<br>
        return self._values<br>
<br>
    def indexes(self):<br>
        return self._sources<br>
<br>
    def dim(self):<br>
        return self._dim<br>
<br>
<br>
class VariableValue:<br>
    def __init__(self, commutator, index):<br>
        self.commutator = commutator<br>
        self.index = index<br>
<br>
    def set_value(self, value):<br>
        self.commutator.set_value(self.index, value)<br>
<br>
    def __str__(self):<br>
        return str(id(self))<br>
<br>
    def __repr__(self):<br>
        return str(id(self))<br>
<br>
    def __lt__(self, oth):<br>
        return id(self) &lt; id(oth)<br>
<br>
<br>
class ScrewVariableValue(VariableValue):<br>
    def __init__(self, commutator, index):<br>
        super().__init__(commutator, index)<br>
        self._value = Screw2()<br>
<br>
<br>
class ScrewCommutator(VariableValueCommutator):<br>
    def __init__(self, local_senses, pose_object):<br>
        dim = len(local_senses)<br>
        super().__init__(dim)<br>
        self.pose_object = pose_object<br>
        self._screws = local_senses<br>
<br>
    def screws(self):<br>
        return self._screws<br>
<br>
    def position(self):<br>
        return self.pose_object.position()<br>
<br>
    def derivative_matrix_from(self, other):<br>
        self_screws = self.screws()<br>
        other_screws = other.screws()<br>
        self_pose = self.pose_object.position()<br>
        other_pose = other.pose_object.position()<br>
        diff_pose = self_pose.inverse() * other_pose<br>
        B = numpy.zeros((len(self_screws), len(other_screws)))<br>
        for i, self_screw in enumerate(self_screws):<br>
            for j, other_screw in enumerate(other_screws):<br>
                carried = other_screw.kinematic_carry(<br>
                    diff_pose)<br>
                B[i, j] = self_screw.fulldot(carried)<br>
        return IndexedMatrix(B, self.indexes(), other.indexes(), lcomm=self, rcomm=other)<br>
<br>
    def derivative(self, other):<br>
        return self.derivative_matrix_from(other)<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    numpy.set_printoptions(precision=3, suppress=True)<br>
<br>
    print(&quot;1:&quot;)<br>
    p1 = PoseObject(Motor2.translation(0, 0))<br>
    p2 = PoseObject(Motor2.translation(1, 0))<br>
    sc1 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)<br>
    sc2 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)<br>
    B = sc1.derivative_matrix_from(sc2)<br>
    print(B)<br>
<br>
    print(&quot;2:&quot;)<br>
    p1 = PoseObject(Motor2.translation(2, 0))<br>
    p2 = PoseObject(Motor2.translation(3, 0))<br>
    sc1 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)<br>
    sc2 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)<br>
    B = sc1.derivative_matrix_from(sc2)<br>
    print(B)<br>
<br>
    print(&quot;3:&quot;)<br>
    p1 = PoseObject(Motor2.rotation(math.pi/2))<br>
    p2 = PoseObject(Motor2.rotation(math.pi/2) * Motor2.translation(1, 0))<br>
    sc1 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)<br>
    sc2 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)<br>
    B = sc1.derivative_matrix_from(sc2)<br>
    print(B)<br>
<br>
    print(&quot;4:&quot;)<br>
    p1 = PoseObject(Motor2.translation(0, 0))<br>
    p2 = PoseObject(Motor2.rotation(math.pi/2) * Motor2.translation(1, 0))<br>
    sc1 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[0, 1]), Screw2(v=[-1, 0]), Screw2(m=1)], pose_object=p1)<br>
    sc2 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)<br>
    B = sc1.derivative_matrix_from(sc2)<br>
    print(B)<br>
<br>
    print(&quot;5:&quot;)<br>
    p1 = PoseObject(Motor2.rotation(math.pi/2) * Motor2.translation(0, 0))<br>
    p2 = PoseObject(Motor2.translation(0, 1))<br>
    sc1 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)<br>
    sc2 = ScrewCommutator(local_senses=[Screw2(<br>
        v=[0, 1]), Screw2(v=[-1, 0]), Screw2(m=1)], pose_object=p2)<br>
    B = sc1.derivative_matrix_from(sc2)<br>
    print(B)<br>
<!-- END SCAT CODE -->
</body>
</html>
