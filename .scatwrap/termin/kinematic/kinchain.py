<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/kinchain.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from .kinematic import *<br>
from termin.geombase import Pose3<br>
from .transform import Transform3<br>
import numpy<br>
import math<br>
<br>
class KinematicChain3:<br>
&#9;&quot;&quot;&quot;A class for kinematic chains in 3D space.&quot;&quot;&quot;<br>
&#9;def __init__(self, distal: Transform3, proximal: Transform3 = None):<br>
&#9;&#9;self.distal = distal<br>
&#9;&#9;self.proximal = proximal<br>
&#9;&#9;self._chain = self.build_chain()<br>
<br>
&#9;&#9;if self.proximal is None:<br>
&#9;&#9;&#9;self.proximal = self._chain[-1]<br>
<br>
&#9;&#9;self._kinematics = [t for t in self._chain if isinstance(t, KinematicTransform3)]<br>
&#9;&#9;self._kinematics[0].update_kinematic_parent_recursively()<br>
<br>
&#9;def __getitem__(self, key):<br>
&#9;&#9;return self._kinematics[key]<br>
<br>
&#9;def kinunits(self) -&gt; [KinematicTransform3]:<br>
&#9;&#9;&quot;&quot;&quot;Return the list of kinematic units in the chain.&quot;&quot;&quot;<br>
&#9;&#9;return self._kinematics<br>
<br>
&#9;def units(self) -&gt; [Transform3]:<br>
&#9;&#9;&quot;&quot;&quot;Return the list of all transform units in the chain.&quot;&quot;&quot;<br>
&#9;&#9;return self._chain<br>
<br>
&#9;def build_chain(self):<br>
&#9;&#9;&quot;&quot;&quot;Build the kinematic chain from the distal to the proximal.&quot;&quot;&quot;<br>
&#9;&#9;current = self.distal<br>
&#9;&#9;chain = []<br>
&#9;&#9;while current != self.proximal:<br>
&#9;&#9;&#9;chain.append(current)<br>
&#9;&#9;&#9;current = current.parent<br>
<br>
&#9;&#9;if self.proximal is not None:<br>
&#9;&#9;&#9;chain.append(self.proximal)<br>
<br>
&#9;&#9;return chain<br>
<br>
&#9;def apply_coordinate_changes(self, delta_coords: [float]):<br>
&#9;&#9;&quot;&quot;&quot;Apply coordinate changes to the kinematic units in the chain.&quot;&quot;&quot;<br>
&#9;&#9;if len(delta_coords) != len(self._kinematics):<br>
&#9;&#9;&#9;raise ValueError(&quot;Length of delta_coords must match number of kinematic units in the chain.&quot;)<br>
<br>
&#9;&#9;for kinunit, delta in zip(self._kinematics, delta_coords):<br>
&#9;&#9;&#9;current_coord = kinunit.get_coord()<br>
&#9;&#9;&#9;kinunit.set_coord(current_coord + delta)<br>
<br>
&#9;def sensitivity_twists(self, topbody:Transform3=None, local_pose:Pose3=Pose3.identity(), basis:Pose3=None) -&gt; [Screw3]:<br>
&#9;&#9;&quot;&quot;&quot;Return the sensitivity twists for all kinematic transforms in the chain.<br>
&#9;&#9;<br>
&#9;&#9;Если basis не задан, то используется локальная система отсчета topbody*local_pose.<br>
&#9;&#9;Базис должен совпадать с системой, в которой формируется управление.<br>
&#9;&#9;&quot;&quot;&quot;<br>
<br>
&#9;&#9;if topbody == None:<br>
&#9;&#9;&#9;topbody = self.distal<br>
<br>
&#9;&#9;top_kinunit = KinematicTransform3.found_first_kinematic_unit_in_parent_tree(topbody, ignore_self=True)<br>
&#9;&#9;if top_kinunit is None:<br>
&#9;&#9;&#9;raise ValueError(&quot;No kinematic unit found in body parent tree&quot;)<br>
<br>
&#9;&#9;senses = []<br>
&#9;&#9;outtrans = topbody.global_pose() * local_pose<br>
<br>
&#9;&#9;top_unit_founded = False<br>
&#9;&#9;for link in self._kinematics:<br>
&#9;&#9;&#9;if link is top_kinunit:<br>
&#9;&#9;&#9;&#9;top_unit_founded = True<br>
<br>
&#9;&#9;&#9;# Получаем собственные чувствительности текущего звена в его собственной системе координат<br>
&#9;&#9;&#9;lsenses = link.senses()<br>
&#9;&#9;&#9;#print(lsenses)<br>
<br>
&#9;&#9;&#9;if top_unit_founded == False:<br>
&#9;&#9;&#9;&#9;for _ in lsenses:<br>
&#9;&#9;&#9;&#9;&#9;senses.append(Screw3())<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;# Получаем трансформацию выхода текущей пары<br>
&#9;&#9;&#9;linktrans = link.output.global_pose()<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;# Получаем трансформацию цели в системе текущего звена<br>
&#9;&#9;&#9;trsf = linktrans.inverse() * outtrans<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;# Получаем радиус-вектор в системе текущего звена<br>
&#9;&#9;&#9;radius = trsf.lin<br>
&#9;&#9;&#9;<br>
&#9;&#9;&#9;for sens in lsenses:<br>
&#9;&#9;&#9;&#9;# Получаем линейную и угловую составляющие чувствительности<br>
&#9;&#9;&#9;&#9;# в системе текущего звена<br>
&#9;&#9;&#9;&#9;scr = sens.kinematic_carry(radius)<br>
<br>
&#9;&#9;&#9;&#9;# Трансформируем их в систему цели и добавляем в список<br>
&#9;&#9;&#9;&#9;senses.append((<br>
&#9;&#9;&#9;&#9;&#9;scr.inverse_transform_by(trsf)<br>
&#9;&#9;&#9;&#9;))<br>
&#9;&#9;&#9;&#9;#senses.append(sens.transform_as_twist_by(trsf))<br>
&#9;&#9;&#9;<br>
&#9;&#9;# Перегоняем в систему basis, если она задана<br>
&#9;&#9;if basis is not None:<br>
&#9;&#9;&#9;btrsf = basis<br>
&#9;&#9;&#9;trsf = btrsf.inverse() * outtrans<br>
&#9;&#9;&#9;senses = [s.transform_by(trsf) for s in senses]<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;# переносим в глобальный фрейм<br>
&#9;&#9;&#9;trsf = outtrans<br>
&#9;&#9;&#9;senses = [s.transform_by(trsf) for s in senses]    <br>
<br>
&#9;&#9;return senses<br>
<br>
&#9;def sensitivity_jacobian(self, body=None, local=Pose3.identity(), basis=None):<br>
&#9;&#9;&quot;&quot;&quot;Вернуть матрицу Якоби выхода по координатам в виде numpy массива 6xN&quot;&quot;&quot;<br>
<br>
&#9;&#9;sens = self.sensitivity_twists(body, local, basis)<br>
&#9;&#9;jacobian = numpy.zeros((6, len(sens)))<br>
<br>
&#9;&#9;for i in range(len(sens)):<br>
&#9;&#9;&#9;wsens = sens[i].ang<br>
&#9;&#9;&#9;vsens = sens[i].lin<br>
<br>
&#9;&#9;&#9;jacobian[0:3, i] = wsens<br>
&#9;&#9;&#9;jacobian[3:6, i] = vsens<br>
<br>
&#9;&#9;return jacobian<br>
<br>
&#9;def translation_sensitivity_jacobian(self, body=None, local=Pose3.identity(), basis=None):<br>
&#9;&#9;&quot;&quot;&quot;Вернуть матрицу Якоби трансляции выхода по координатам в виде numpy массива 3xN&quot;&quot;&quot;<br>
<br>
&#9;&#9;sens = self.sensitivity_twists(body, local, basis)<br>
&#9;&#9;jacobian = numpy.zeros((3, len(sens)))<br>
<br>
&#9;&#9;for i in range(len(sens)):<br>
&#9;&#9;&#9;vsens = sens[i].lin<br>
&#9;&#9;&#9;jacobian[0:3, i] = vsens<br>
<br>
&#9;&#9;return jacobian<br>
<!-- END SCAT CODE -->
</body>
</html>
