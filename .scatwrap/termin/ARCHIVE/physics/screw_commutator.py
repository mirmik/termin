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
&#9;def __init__(self, dim):<br>
&#9;&#9;self._dim = dim<br>
&#9;&#9;self._sources = [VariableValue(self, i) for i in range(dim)]<br>
&#9;&#9;self._values = [0] * dim<br>
<br>
&#9;def sources(self):<br>
&#9;&#9;return self._sources<br>
<br>
&#9;def set_value(self, idx: int, value: float):<br>
&#9;&#9;self._values[idx] = value<br>
<br>
&#9;def values(self):<br>
&#9;&#9;return self._values<br>
<br>
&#9;def indexes(self):<br>
&#9;&#9;return self._sources<br>
<br>
&#9;def dim(self):<br>
&#9;&#9;return self._dim<br>
<br>
<br>
class VariableValue:<br>
&#9;def __init__(self, commutator, index):<br>
&#9;&#9;self.commutator = commutator<br>
&#9;&#9;self.index = index<br>
<br>
&#9;def set_value(self, value):<br>
&#9;&#9;self.commutator.set_value(self.index, value)<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return str(id(self))<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return str(id(self))<br>
<br>
&#9;def __lt__(self, oth):<br>
&#9;&#9;return id(self) &lt; id(oth)<br>
<br>
<br>
class ScrewVariableValue(VariableValue):<br>
&#9;def __init__(self, commutator, index):<br>
&#9;&#9;super().__init__(commutator, index)<br>
&#9;&#9;self._value = Screw2()<br>
<br>
<br>
class ScrewCommutator(VariableValueCommutator):<br>
&#9;def __init__(self, local_senses, pose_object):<br>
&#9;&#9;dim = len(local_senses)<br>
&#9;&#9;super().__init__(dim)<br>
&#9;&#9;self.pose_object = pose_object<br>
&#9;&#9;self._screws = local_senses<br>
<br>
&#9;def screws(self):<br>
&#9;&#9;return self._screws<br>
<br>
&#9;def position(self):<br>
&#9;&#9;return self.pose_object.position()<br>
<br>
&#9;def derivative_matrix_from(self, other):<br>
&#9;&#9;self_screws = self.screws()<br>
&#9;&#9;other_screws = other.screws()<br>
&#9;&#9;self_pose = self.pose_object.position()<br>
&#9;&#9;other_pose = other.pose_object.position()<br>
&#9;&#9;diff_pose = self_pose.inverse() * other_pose<br>
&#9;&#9;B = numpy.zeros((len(self_screws), len(other_screws)))<br>
&#9;&#9;for i, self_screw in enumerate(self_screws):<br>
&#9;&#9;&#9;for j, other_screw in enumerate(other_screws):<br>
&#9;&#9;&#9;&#9;carried = other_screw.kinematic_carry(<br>
&#9;&#9;&#9;&#9;&#9;diff_pose)<br>
&#9;&#9;&#9;&#9;B[i, j] = self_screw.fulldot(carried)<br>
&#9;&#9;return IndexedMatrix(B, self.indexes(), other.indexes(), lcomm=self, rcomm=other)<br>
<br>
&#9;def derivative(self, other):<br>
&#9;&#9;return self.derivative_matrix_from(other)<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;numpy.set_printoptions(precision=3, suppress=True)<br>
<br>
&#9;print(&quot;1:&quot;)<br>
&#9;p1 = PoseObject(Motor2.translation(0, 0))<br>
&#9;p2 = PoseObject(Motor2.translation(1, 0))<br>
&#9;sc1 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)<br>
&#9;sc2 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)<br>
&#9;B = sc1.derivative_matrix_from(sc2)<br>
&#9;print(B)<br>
<br>
&#9;print(&quot;2:&quot;)<br>
&#9;p1 = PoseObject(Motor2.translation(2, 0))<br>
&#9;p2 = PoseObject(Motor2.translation(3, 0))<br>
&#9;sc1 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)<br>
&#9;sc2 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)<br>
&#9;B = sc1.derivative_matrix_from(sc2)<br>
&#9;print(B)<br>
<br>
&#9;print(&quot;3:&quot;)<br>
&#9;p1 = PoseObject(Motor2.rotation(math.pi/2))<br>
&#9;p2 = PoseObject(Motor2.rotation(math.pi/2) * Motor2.translation(1, 0))<br>
&#9;sc1 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)<br>
&#9;sc2 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)<br>
&#9;B = sc1.derivative_matrix_from(sc2)<br>
&#9;print(B)<br>
<br>
&#9;print(&quot;4:&quot;)<br>
&#9;p1 = PoseObject(Motor2.translation(0, 0))<br>
&#9;p2 = PoseObject(Motor2.rotation(math.pi/2) * Motor2.translation(1, 0))<br>
&#9;sc1 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[0, 1]), Screw2(v=[-1, 0]), Screw2(m=1)], pose_object=p1)<br>
&#9;sc2 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)<br>
&#9;B = sc1.derivative_matrix_from(sc2)<br>
&#9;print(B)<br>
<br>
&#9;print(&quot;5:&quot;)<br>
&#9;p1 = PoseObject(Motor2.rotation(math.pi/2) * Motor2.translation(0, 0))<br>
&#9;p2 = PoseObject(Motor2.translation(0, 1))<br>
&#9;sc1 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)<br>
&#9;sc2 = ScrewCommutator(local_senses=[Screw2(<br>
&#9;&#9;v=[0, 1]), Screw2(v=[-1, 0]), Screw2(m=1)], pose_object=p2)<br>
&#9;B = sc1.derivative_matrix_from(sc2)<br>
&#9;print(B)<br>
<!-- END SCAT CODE -->
</body>
</html>
