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
    &quot;&quot;&quot;Дерево кинематических пар с глобальным построением Якобиана.<br>
<br>
    Класс собирает все `KinematicTransform3` в дереве `Transform3`, фиксирует<br>
    их порядок и предоставляет матрицы чувствительности:<br>
        J = [ ω_1 … ω_n;<br>
              v_1 … v_n ],<br>
    где столбец (ω_i, v_i)^T соответствует очередной обобщённой координате.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, base: Transform3):<br>
        self.base = base<br>
        self._kinematic_units: List[KinematicTransform3] = []<br>
        self._joint_slices: Dict[KinematicTransform3, slice] = {}<br>
        self._dofs = 0<br>
        self.reindex_kinematics()<br>
<br>
    @property<br>
    def dofs(self) -&gt; int:<br>
        &quot;&quot;&quot;Количество обобщённых координат в дереве.&quot;&quot;&quot;<br>
        return self._dofs<br>
<br>
    @property<br>
    def kinematic_units(self) -&gt; List[KinematicTransform3]:<br>
        &quot;&quot;&quot;Возвращает зарегистрированные кинематические пары в порядке индексации.&quot;&quot;&quot;<br>
        return list(self._kinematic_units)<br>
<br>
    def joint_slice(self, joint: KinematicTransform3) -&gt; slice:<br>
        &quot;&quot;&quot;Диапазон столбцов Якобиана, отвечающий данной кинематической паре.&quot;&quot;&quot;<br>
        return self._joint_slices[joint]<br>
<br>
    def reindex_kinematics(self):<br>
        &quot;&quot;&quot;Перестраивает список кинематических пар и их индексы.&quot;&quot;&quot;<br>
        self._kinematic_units.clear()<br>
        self._joint_slices.clear()<br>
        self._dofs = 0<br>
<br>
        for node in self._walk_transforms(self.base):<br>
            if isinstance(node, KinematicTransform3):<br>
                node.update_kinematic_parent()<br>
                dof = len(node.senses())<br>
                start = self._dofs<br>
                self._kinematic_units.append(node)<br>
                self._joint_slices[node] = slice(start, start + dof)<br>
                self._dofs += dof<br>
<br>
    def _walk_transforms(self, node: Transform3) -&gt; Iterable[Transform3]:<br>
        yield node<br>
        for child in node.children:<br>
            yield from self._walk_transforms(child)<br>
<br>
    def sensitivity_twists(<br>
        self,<br>
        body: Transform3,<br>
        local_pose: Pose3 = Pose3.identity(),<br>
        basis: Optional[Pose3] = None,<br>
    ) -&gt; Dict[KinematicTransform3, List[Screw3]]:<br>
        &quot;&quot;&quot;Возвращает чувствительности (твисты) к цели `body * local_pose`.<br>
<br>
        Результат — словарь `{joint: [Screw3, ...]}`. В нём содержатся только те<br>
        пары, которые лежат на пути от `body` к корню дерева. Такой формат не<br>
        требует знания полного числа степеней свободы: нули автоматически<br>
        отсутствуют, а далее `Robot.jacobian` расставляет столбцы по индексам.<br>
        &quot;&quot;&quot;<br>
        out_pose = body.global_pose() * local_pose<br>
        basis_pose = basis.inverse() * out_pose if basis is not None else out_pose<br>
<br>
        current = KinematicTransform3.found_first_kinematic_unit_in_parent_tree(body, ignore_self=True)<br>
        twists: Dict[KinematicTransform3, List[Screw3]] = {}<br>
<br>
        while current is not None:<br>
            link_pose = current.output.global_pose()<br>
            rel = link_pose.inverse() * out_pose<br>
            radius = rel.lin<br>
<br>
            joint_twists: List[Screw3] = []<br>
            for sens in current.senses():<br>
                scr = sens.kinematic_carry(radius)<br>
                scr = scr.inverse_transform_by(rel)<br>
                scr = scr.transform_by(basis_pose)<br>
                joint_twists.append(scr)<br>
<br>
            twists[current] = joint_twists<br>
            current = current.kinematic_parent<br>
<br>
        return twists<br>
<br>
    def jacobian(<br>
        self,<br>
        body: Transform3,<br>
        local_pose: Pose3 = Pose3.identity(),<br>
        basis: Optional[Pose3] = None,<br>
    ) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Строит полный 6×N Якобиан, собирая столбцы из `sensitivity_twists`.<br>
<br>
        Колонка j равна [ω_j^T, v_j^T]^T — угловой и линейной частям твиста<br>
        соответствующей обобщённой координаты θ_j.<br>
        &quot;&quot;&quot;<br>
        jac = np.zeros((6, self._dofs), dtype=float)<br>
        twists = self.sensitivity_twists(body, local_pose, basis)<br>
<br>
        for joint, cols in twists.items():<br>
            sl = self._joint_slices.get(joint)<br>
            if sl is None:<br>
                continue<br>
            for offset, scr in enumerate(cols):<br>
                idx = sl.start + offset<br>
                jac[0:3, idx] = scr.ang<br>
                jac[3:6, idx] = scr.lin<br>
<br>
        return jac<br>
<br>
    def translation_jacobian(<br>
        self,<br>
        body: Transform3,<br>
        local_pose: Pose3 = Pose3.identity(),<br>
        basis: Optional[Pose3] = None,<br>
    ) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Возвращает только трансляционную часть Якобиана (3×N).&quot;&quot;&quot;<br>
        twists = self.sensitivity_twists(body, local_pose, basis)<br>
        jac = np.zeros((3, self._dofs), dtype=float)<br>
<br>
        for joint, cols in twists.items():<br>
            sl = self._joint_slices.get(joint)<br>
            if sl is None:<br>
                continue<br>
            for offset, scr in enumerate(cols):<br>
                idx = sl.start + offset<br>
                jac[:, idx] = scr.lin<br>
<br>
        return jac<br>
<br>
    def integrate_joint_speeds(self, speeds: np.ndarray, dt: float) -&gt; None:<br>
        &quot;&quot;&quot;Применяет численный шаг интегрирования ко всем координатам.<br>
<br>
        Для каждой кинематической пары прибавляет `speed_i * dt` к соответствующей<br>
        координате, используя `set_coord`. Предполагается, что `speeds` задан в<br>
        тех же единицах и порядке, что и столбцы Якобиана.<br>
        &quot;&quot;&quot;<br>
        speeds = np.asarray(speeds, dtype=float)<br>
        if speeds.shape[0] != self._dofs:<br>
            raise ValueError(f&quot;Speeds vector must have length {self._dofs}, got {speeds.shape[0]}&quot;)<br>
<br>
        for joint in self._kinematic_units:<br>
            sl = self._joint_slices[joint]<br>
            span = sl.stop - sl.start<br>
            if span == 0:<br>
                continue<br>
            segment = speeds[sl] * dt<br>
            if span == 1:<br>
                joint.set_coord(joint.get_coord() + segment[0])<br>
            else:<br>
                raise NotImplementedError(&quot;Multi-DOF joints require custom integration.&quot;)<br>
<!-- END SCAT CODE -->
</body>
</html>
