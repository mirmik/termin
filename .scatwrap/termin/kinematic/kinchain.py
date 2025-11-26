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
    &quot;&quot;&quot;A class for kinematic chains in 3D space.&quot;&quot;&quot;<br>
    def __init__(self, distal: Transform3, proximal: Transform3 = None):<br>
        self.distal = distal<br>
        self.proximal = proximal<br>
        self._chain = self.build_chain()<br>
<br>
        if self.proximal is None:<br>
            self.proximal = self._chain[-1]<br>
<br>
        self._kinematics = [t for t in self._chain if isinstance(t, KinematicTransform3)]<br>
        self._kinematics[0].update_kinematic_parent_recursively()<br>
<br>
    def __getitem__(self, key):<br>
        return self._kinematics[key]<br>
<br>
    def kinunits(self) -&gt; [KinematicTransform3]:<br>
        &quot;&quot;&quot;Return the list of kinematic units in the chain.&quot;&quot;&quot;<br>
        return self._kinematics<br>
<br>
    def units(self) -&gt; [Transform3]:<br>
        &quot;&quot;&quot;Return the list of all transform units in the chain.&quot;&quot;&quot;<br>
        return self._chain<br>
<br>
    def build_chain(self):<br>
        &quot;&quot;&quot;Build the kinematic chain from the distal to the proximal.&quot;&quot;&quot;<br>
        current = self.distal<br>
        chain = []<br>
        while current != self.proximal:<br>
            chain.append(current)<br>
            current = current.parent<br>
<br>
        if self.proximal is not None:<br>
            chain.append(self.proximal)<br>
<br>
        return chain<br>
<br>
    def apply_coordinate_changes(self, delta_coords: [float]):<br>
        &quot;&quot;&quot;Apply coordinate changes to the kinematic units in the chain.&quot;&quot;&quot;<br>
        if len(delta_coords) != len(self._kinematics):<br>
            raise ValueError(&quot;Length of delta_coords must match number of kinematic units in the chain.&quot;)<br>
<br>
        for kinunit, delta in zip(self._kinematics, delta_coords):<br>
            current_coord = kinunit.get_coord()<br>
            kinunit.set_coord(current_coord + delta)<br>
<br>
    def sensitivity_twists(self, topbody:Transform3=None, local_pose:Pose3=Pose3.identity(), basis:Pose3=None) -&gt; [Screw3]:<br>
        &quot;&quot;&quot;Return the sensitivity twists for all kinematic transforms in the chain.<br>
        <br>
        Если basis не задан, то используется локальная система отсчета topbody*local_pose.<br>
        Базис должен совпадать с системой, в которой формируется управление.<br>
        &quot;&quot;&quot;<br>
<br>
        if topbody == None:<br>
            topbody = self.distal<br>
<br>
        top_kinunit = KinematicTransform3.found_first_kinematic_unit_in_parent_tree(topbody, ignore_self=True)<br>
        if top_kinunit is None:<br>
            raise ValueError(&quot;No kinematic unit found in body parent tree&quot;)<br>
<br>
        senses = []<br>
        outtrans = topbody.global_pose() * local_pose<br>
<br>
        top_unit_founded = False<br>
        for link in self._kinematics:<br>
            if link is top_kinunit:<br>
                top_unit_founded = True<br>
<br>
            # Получаем собственные чувствительности текущего звена в его собственной системе координат<br>
            lsenses = link.senses()<br>
            #print(lsenses)<br>
<br>
            if top_unit_founded == False:<br>
                for _ in lsenses:<br>
                    senses.append(Screw3())<br>
                continue<br>
 <br>
            # Получаем трансформацию выхода текущей пары<br>
            linktrans = link.output.global_pose()<br>
            <br>
            # Получаем трансформацию цели в системе текущего звена<br>
            trsf = linktrans.inverse() * outtrans<br>
            <br>
            # Получаем радиус-вектор в системе текущего звена<br>
            radius = trsf.lin<br>
            <br>
            for sens in lsenses:<br>
                # Получаем линейную и угловую составляющие чувствительности<br>
                # в системе текущего звена<br>
                scr = sens.kinematic_carry(radius)<br>
<br>
                # Трансформируем их в систему цели и добавляем в список<br>
                senses.append((<br>
                    scr.inverse_transform_by(trsf)<br>
                ))<br>
                #senses.append(sens.transform_as_twist_by(trsf))<br>
            <br>
        # Перегоняем в систему basis, если она задана<br>
        if basis is not None:<br>
            btrsf = basis<br>
            trsf = btrsf.inverse() * outtrans<br>
            senses = [s.transform_by(trsf) for s in senses]<br>
        else:<br>
            # переносим в глобальный фрейм<br>
            trsf = outtrans<br>
            senses = [s.transform_by(trsf) for s in senses]    <br>
<br>
        return senses<br>
<br>
    def sensitivity_jacobian(self, body=None, local=Pose3.identity(), basis=None):<br>
        &quot;&quot;&quot;Вернуть матрицу Якоби выхода по координатам в виде numpy массива 6xN&quot;&quot;&quot;<br>
<br>
        sens = self.sensitivity_twists(body, local, basis)<br>
        jacobian = numpy.zeros((6, len(sens)))<br>
<br>
        for i in range(len(sens)):<br>
            wsens = sens[i].ang<br>
            vsens = sens[i].lin<br>
<br>
            jacobian[0:3, i] = wsens<br>
            jacobian[3:6, i] = vsens<br>
<br>
        return jacobian<br>
<br>
    def translation_sensitivity_jacobian(self, body=None, local=Pose3.identity(), basis=None):<br>
        &quot;&quot;&quot;Вернуть матрицу Якоби трансляции выхода по координатам в виде numpy массива 3xN&quot;&quot;&quot;<br>
<br>
        sens = self.sensitivity_twists(body, local, basis)<br>
        jacobian = numpy.zeros((3, len(sens)))<br>
<br>
        for i in range(len(sens)):<br>
            vsens = sens[i].lin<br>
            jacobian[0:3, i] = vsens<br>
<br>
        return jacobian<br>
<!-- END SCAT CODE -->
</body>
</html>
