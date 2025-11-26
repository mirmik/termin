<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/robot/robot.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from __future__ import annotations<br>
<br>
from typing import Dict, Iterable, List, Optional<br>
<br>
import numpy as np<br>
<br>
from termin.geombase import Pose3, Screw3<br>
from termin.kinematic.kinematic import KinematicTransform3<br>
from termin.kinematic.transform import Transform3<br>
<br>
<br>
class Robot:<br>
&#9;&quot;&quot;&quot;Дерево кинематических пар с глобальным построением Якобиана.<br>
<br>
&#9;Класс собирает все `KinematicTransform3` в дереве `Transform3`, фиксирует<br>
&#9;их порядок и предоставляет матрицы чувствительности:<br>
&#9;&#9;J = [ ω_1 … ω_n;<br>
&#9;&#9;&#9;v_1 … v_n ],<br>
&#9;где столбец (ω_i, v_i)^T соответствует очередной обобщённой координате.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, base: Transform3):<br>
&#9;&#9;self.base = base<br>
&#9;&#9;self._kinematic_units: List[KinematicTransform3] = []<br>
&#9;&#9;self._joint_slices: Dict[KinematicTransform3, slice] = {}<br>
&#9;&#9;self._dofs = 0<br>
&#9;&#9;self.reindex_kinematics()<br>
<br>
&#9;@property<br>
&#9;def dofs(self) -&gt; int:<br>
&#9;&#9;&quot;&quot;&quot;Количество обобщённых координат в дереве.&quot;&quot;&quot;<br>
&#9;&#9;return self._dofs<br>
<br>
&#9;@property<br>
&#9;def kinematic_units(self) -&gt; List[KinematicTransform3]:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает зарегистрированные кинематические пары в порядке индексации.&quot;&quot;&quot;<br>
&#9;&#9;return list(self._kinematic_units)<br>
<br>
&#9;def joint_slice(self, joint: KinematicTransform3) -&gt; slice:<br>
&#9;&#9;&quot;&quot;&quot;Диапазон столбцов Якобиана, отвечающий данной кинематической паре.&quot;&quot;&quot;<br>
&#9;&#9;return self._joint_slices[joint]<br>
<br>
&#9;def reindex_kinematics(self):<br>
&#9;&#9;&quot;&quot;&quot;Перестраивает список кинематических пар и их индексы.&quot;&quot;&quot;<br>
&#9;&#9;self._kinematic_units.clear()<br>
&#9;&#9;self._joint_slices.clear()<br>
&#9;&#9;self._dofs = 0<br>
<br>
&#9;&#9;for node in self._walk_transforms(self.base):<br>
&#9;&#9;&#9;if isinstance(node, KinematicTransform3):<br>
&#9;&#9;&#9;&#9;node.update_kinematic_parent()<br>
&#9;&#9;&#9;&#9;dof = len(node.senses())<br>
&#9;&#9;&#9;&#9;start = self._dofs<br>
&#9;&#9;&#9;&#9;self._kinematic_units.append(node)<br>
&#9;&#9;&#9;&#9;self._joint_slices[node] = slice(start, start + dof)<br>
&#9;&#9;&#9;&#9;self._dofs += dof<br>
<br>
&#9;def _walk_transforms(self, node: Transform3) -&gt; Iterable[Transform3]:<br>
&#9;&#9;yield node<br>
&#9;&#9;for child in node.children:<br>
&#9;&#9;&#9;yield from self._walk_transforms(child)<br>
<br>
&#9;def sensitivity_twists(<br>
&#9;&#9;self,<br>
&#9;&#9;body: Transform3,<br>
&#9;&#9;local_pose: Pose3 = Pose3.identity(),<br>
&#9;&#9;basis: Optional[Pose3] = None,<br>
&#9;) -&gt; Dict[KinematicTransform3, List[Screw3]]:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает чувствительности (твисты) к цели `body * local_pose`.<br>
<br>
&#9;&#9;Результат — словарь `{joint: [Screw3, ...]}`. В нём содержатся только те<br>
&#9;&#9;пары, которые лежат на пути от `body` к корню дерева. Такой формат не<br>
&#9;&#9;требует знания полного числа степеней свободы: нули автоматически<br>
&#9;&#9;отсутствуют, а далее `Robot.jacobian` расставляет столбцы по индексам.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;out_pose = body.global_pose() * local_pose<br>
&#9;&#9;basis_pose = basis.inverse() * out_pose if basis is not None else out_pose<br>
<br>
&#9;&#9;current = KinematicTransform3.found_first_kinematic_unit_in_parent_tree(body, ignore_self=True)<br>
&#9;&#9;twists: Dict[KinematicTransform3, List[Screw3]] = {}<br>
<br>
&#9;&#9;while current is not None:<br>
&#9;&#9;&#9;link_pose = current.output.global_pose()<br>
&#9;&#9;&#9;rel = link_pose.inverse() * out_pose<br>
&#9;&#9;&#9;radius = rel.lin<br>
<br>
&#9;&#9;&#9;joint_twists: List[Screw3] = []<br>
&#9;&#9;&#9;for sens in current.senses():<br>
&#9;&#9;&#9;&#9;scr = sens.kinematic_carry(radius)<br>
&#9;&#9;&#9;&#9;scr = scr.inverse_transform_by(rel)<br>
&#9;&#9;&#9;&#9;scr = scr.transform_by(basis_pose)<br>
&#9;&#9;&#9;&#9;joint_twists.append(scr)<br>
<br>
&#9;&#9;&#9;twists[current] = joint_twists<br>
&#9;&#9;&#9;current = current.kinematic_parent<br>
<br>
&#9;&#9;return twists<br>
<br>
&#9;def jacobian(<br>
&#9;&#9;self,<br>
&#9;&#9;body: Transform3,<br>
&#9;&#9;local_pose: Pose3 = Pose3.identity(),<br>
&#9;&#9;basis: Optional[Pose3] = None,<br>
&#9;) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Строит полный 6×N Якобиан, собирая столбцы из `sensitivity_twists`.<br>
<br>
&#9;&#9;Колонка j равна [ω_j^T, v_j^T]^T — угловой и линейной частям твиста<br>
&#9;&#9;соответствующей обобщённой координаты θ_j.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;jac = np.zeros((6, self._dofs), dtype=float)<br>
&#9;&#9;twists = self.sensitivity_twists(body, local_pose, basis)<br>
<br>
&#9;&#9;for joint, cols in twists.items():<br>
&#9;&#9;&#9;sl = self._joint_slices.get(joint)<br>
&#9;&#9;&#9;if sl is None:<br>
&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;for offset, scr in enumerate(cols):<br>
&#9;&#9;&#9;&#9;idx = sl.start + offset<br>
&#9;&#9;&#9;&#9;jac[0:3, idx] = scr.ang<br>
&#9;&#9;&#9;&#9;jac[3:6, idx] = scr.lin<br>
<br>
&#9;&#9;return jac<br>
<br>
&#9;def translation_jacobian(<br>
&#9;&#9;self,<br>
&#9;&#9;body: Transform3,<br>
&#9;&#9;local_pose: Pose3 = Pose3.identity(),<br>
&#9;&#9;basis: Optional[Pose3] = None,<br>
&#9;) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Возвращает только трансляционную часть Якобиана (3×N).&quot;&quot;&quot;<br>
&#9;&#9;twists = self.sensitivity_twists(body, local_pose, basis)<br>
&#9;&#9;jac = np.zeros((3, self._dofs), dtype=float)<br>
<br>
&#9;&#9;for joint, cols in twists.items():<br>
&#9;&#9;&#9;sl = self._joint_slices.get(joint)<br>
&#9;&#9;&#9;if sl is None:<br>
&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;for offset, scr in enumerate(cols):<br>
&#9;&#9;&#9;&#9;idx = sl.start + offset<br>
&#9;&#9;&#9;&#9;jac[:, idx] = scr.lin<br>
<br>
&#9;&#9;return jac<br>
<br>
&#9;def integrate_joint_speeds(self, speeds: np.ndarray, dt: float) -&gt; None:<br>
&#9;&#9;&quot;&quot;&quot;Применяет численный шаг интегрирования ко всем координатам.<br>
<br>
&#9;&#9;Для каждой кинематической пары прибавляет `speed_i * dt` к соответствующей<br>
&#9;&#9;координате, используя `set_coord`. Предполагается, что `speeds` задан в<br>
&#9;&#9;тех же единицах и порядке, что и столбцы Якобиана.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;speeds = np.asarray(speeds, dtype=float)<br>
&#9;&#9;if speeds.shape[0] != self._dofs:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Speeds vector must have length {self._dofs}, got {speeds.shape[0]}&quot;)<br>
<br>
&#9;&#9;for joint in self._kinematic_units:<br>
&#9;&#9;&#9;sl = self._joint_slices[joint]<br>
&#9;&#9;&#9;span = sl.stop - sl.start<br>
&#9;&#9;&#9;if span == 0:<br>
&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;segment = speeds[sl] * dt<br>
&#9;&#9;&#9;if span == 1:<br>
&#9;&#9;&#9;&#9;joint.set_coord(joint.get_coord() + segment[0])<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;raise NotImplementedError(&quot;Multi-DOF joints require custom integration.&quot;)<br>
<!-- END SCAT CODE -->
</body>
</html>
