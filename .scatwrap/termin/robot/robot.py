<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/robot/robot.py</title>
</head>
<body>
<pre><code>

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import numpy as np

from termin.geombase import Pose3, Screw3
from termin.kinematic.kinematic import KinematicTransform3
from termin.kinematic.transform import Transform3


class Robot:
    &quot;&quot;&quot;Дерево кинематических пар с глобальным построением Якобиана.

    Класс собирает все `KinematicTransform3` в дереве `Transform3`, фиксирует
    их порядок и предоставляет матрицы чувствительности:
        J = [ ω_1 … ω_n;
              v_1 … v_n ],
    где столбец (ω_i, v_i)^T соответствует очередной обобщённой координате.
    &quot;&quot;&quot;

    def __init__(self, base: Transform3):
        self.base = base
        self._kinematic_units: List[KinematicTransform3] = []
        self._joint_slices: Dict[KinematicTransform3, slice] = {}
        self._dofs = 0
        self.reindex_kinematics()

    @property
    def dofs(self) -&gt; int:
        &quot;&quot;&quot;Количество обобщённых координат в дереве.&quot;&quot;&quot;
        return self._dofs

    @property
    def kinematic_units(self) -&gt; List[KinematicTransform3]:
        &quot;&quot;&quot;Возвращает зарегистрированные кинематические пары в порядке индексации.&quot;&quot;&quot;
        return list(self._kinematic_units)

    def joint_slice(self, joint: KinematicTransform3) -&gt; slice:
        &quot;&quot;&quot;Диапазон столбцов Якобиана, отвечающий данной кинематической паре.&quot;&quot;&quot;
        return self._joint_slices[joint]

    def reindex_kinematics(self):
        &quot;&quot;&quot;Перестраивает список кинематических пар и их индексы.&quot;&quot;&quot;
        self._kinematic_units.clear()
        self._joint_slices.clear()
        self._dofs = 0

        for node in self._walk_transforms(self.base):
            if isinstance(node, KinematicTransform3):
                node.update_kinematic_parent()
                dof = len(node.senses())
                start = self._dofs
                self._kinematic_units.append(node)
                self._joint_slices[node] = slice(start, start + dof)
                self._dofs += dof

    def _walk_transforms(self, node: Transform3) -&gt; Iterable[Transform3]:
        yield node
        for child in node.children:
            yield from self._walk_transforms(child)

    def sensitivity_twists(
        self,
        body: Transform3,
        local_pose: Pose3 = Pose3.identity(),
        basis: Optional[Pose3] = None,
    ) -&gt; Dict[KinematicTransform3, List[Screw3]]:
        &quot;&quot;&quot;Возвращает чувствительности (твисты) к цели `body * local_pose`.

        Результат — словарь `{joint: [Screw3, ...]}`. В нём содержатся только те
        пары, которые лежат на пути от `body` к корню дерева. Такой формат не
        требует знания полного числа степеней свободы: нули автоматически
        отсутствуют, а далее `Robot.jacobian` расставляет столбцы по индексам.
        &quot;&quot;&quot;
        out_pose = body.global_pose() * local_pose
        basis_pose = basis.inverse() * out_pose if basis is not None else out_pose

        current = KinematicTransform3.found_first_kinematic_unit_in_parent_tree(body, ignore_self=True)
        twists: Dict[KinematicTransform3, List[Screw3]] = {}

        while current is not None:
            link_pose = current.output.global_pose()
            rel = link_pose.inverse() * out_pose
            radius = rel.lin

            joint_twists: List[Screw3] = []
            for sens in current.senses():
                scr = sens.kinematic_carry(radius)
                scr = scr.inverse_transform_by(rel)
                scr = scr.transform_by(basis_pose)
                joint_twists.append(scr)

            twists[current] = joint_twists
            current = current.kinematic_parent

        return twists

    def jacobian(
        self,
        body: Transform3,
        local_pose: Pose3 = Pose3.identity(),
        basis: Optional[Pose3] = None,
    ) -&gt; np.ndarray:
        &quot;&quot;&quot;Строит полный 6×N Якобиан, собирая столбцы из `sensitivity_twists`.

        Колонка j равна [ω_j^T, v_j^T]^T — угловой и линейной частям твиста
        соответствующей обобщённой координаты θ_j.
        &quot;&quot;&quot;
        jac = np.zeros((6, self._dofs), dtype=float)
        twists = self.sensitivity_twists(body, local_pose, basis)

        for joint, cols in twists.items():
            sl = self._joint_slices.get(joint)
            if sl is None:
                continue
            for offset, scr in enumerate(cols):
                idx = sl.start + offset
                jac[0:3, idx] = scr.ang
                jac[3:6, idx] = scr.lin

        return jac

    def translation_jacobian(
        self,
        body: Transform3,
        local_pose: Pose3 = Pose3.identity(),
        basis: Optional[Pose3] = None,
    ) -&gt; np.ndarray:
        &quot;&quot;&quot;Возвращает только трансляционную часть Якобиана (3×N).&quot;&quot;&quot;
        twists = self.sensitivity_twists(body, local_pose, basis)
        jac = np.zeros((3, self._dofs), dtype=float)

        for joint, cols in twists.items():
            sl = self._joint_slices.get(joint)
            if sl is None:
                continue
            for offset, scr in enumerate(cols):
                idx = sl.start + offset
                jac[:, idx] = scr.lin

        return jac

    def integrate_joint_speeds(self, speeds: np.ndarray, dt: float) -&gt; None:
        &quot;&quot;&quot;Применяет численный шаг интегрирования ко всем координатам.

        Для каждой кинематической пары прибавляет `speed_i * dt` к соответствующей
        координате, используя `set_coord`. Предполагается, что `speeds` задан в
        тех же единицах и порядке, что и столбцы Якобиана.
        &quot;&quot;&quot;
        speeds = np.asarray(speeds, dtype=float)
        if speeds.shape[0] != self._dofs:
            raise ValueError(f&quot;Speeds vector must have length {self._dofs}, got {speeds.shape[0]}&quot;)

        for joint in self._kinematic_units:
            sl = self._joint_slices[joint]
            span = sl.stop - sl.start
            if span == 0:
                continue
            segment = speeds[sl] * dt
            if span == 1:
                joint.set_coord(joint.get_coord() + segment[0])
            else:
                raise NotImplementedError(&quot;Multi-DOF joints require custom integration.&quot;)

</code></pre>
</body>
</html>
