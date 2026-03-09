
from .kinematic import *
from termin.geombase import Pose3
from .transform import Transform3
import numpy
import math

class KinematicChain3:
    """A class for kinematic chains in 3D space."""
    def __init__(self, distal: Transform3, proximal: Transform3 = None):
        self.distal = distal
        self.proximal = proximal
        self._chain = self.build_chain()

        if self.proximal is None:
            self.proximal = self._chain[-1]

        self._kinematics = [t for t in self._chain if isinstance(t, KinematicTransform3)]
        self._kinematics[0].update_kinematic_parent_recursively()

    def __getitem__(self, key):
        return self._kinematics[key]

    def kinunits(self) -> [KinematicTransform3]:
        """Return the list of kinematic units in the chain."""
        return self._kinematics

    def units(self) -> [Transform3]:
        """Return the list of all transform units in the chain."""
        return self._chain

    def build_chain(self):
        """Build the kinematic chain from the distal to the proximal."""
        current = self.distal
        chain = []
        while current != self.proximal:
            chain.append(current)
            current = current.parent

        if self.proximal is not None:
            chain.append(self.proximal)

        return chain

    def apply_coordinate_changes(self, delta_coords: [float]):
        """Apply coordinate changes to the kinematic units in the chain."""
        if len(delta_coords) != len(self._kinematics):
            raise ValueError("Length of delta_coords must match number of kinematic units in the chain.")

        for kinunit, delta in zip(self._kinematics, delta_coords):
            current_coord = kinunit.get_coord()
            kinunit.set_coord(current_coord + delta)

    def sensitivity_twists(self, topbody:Transform3=None, local_pose:Pose3=Pose3.identity(), basis:Pose3=None) -> [Screw3]:
        """Return the sensitivity twists for all kinematic transforms in the chain.
        
        Если basis не задан, то используется локальная система отсчета topbody*local_pose.
        Базис должен совпадать с системой, в которой формируется управление.
        """

        if topbody == None:
            topbody = self.distal

        top_kinunit = KinematicTransform3.found_first_kinematic_unit_in_parent_tree(topbody, ignore_self=True)
        if top_kinunit is None:
            raise ValueError("No kinematic unit found in body parent tree")

        senses = []
        outtrans = topbody.global_pose() * local_pose

        top_unit_founded = False
        for link in self._kinematics:
            if link is top_kinunit:
                top_unit_founded = True

            # Получаем собственные чувствительности текущего звена в его собственной системе координат
            lsenses = link.senses()
            #print(lsenses)

            if top_unit_founded == False:
                for _ in lsenses:
                    senses.append(Screw3())
                continue
 
            # Получаем трансформацию выхода текущей пары
            linktrans = link.output.global_pose()
            
            # Получаем трансформацию цели в системе текущего звена
            trsf = linktrans.inverse() * outtrans
            
            # Получаем радиус-вектор в системе текущего звена
            radius = trsf.lin
            
            for sens in lsenses:
                # Получаем линейную и угловую составляющие чувствительности
                # в системе текущего звена
                scr = sens.kinematic_carry(radius)

                # Трансформируем их в систему цели и добавляем в список
                senses.append((
                    scr.inverse_transform_by(trsf)
                ))
                #senses.append(sens.transform_as_twist_by(trsf))
            
        # Перегоняем в систему basis, если она задана
        if basis is not None:
            btrsf = basis
            trsf = btrsf.inverse() * outtrans
            senses = [s.transform_by(trsf) for s in senses]
        else:
            # переносим в глобальный фрейм
            trsf = outtrans
            senses = [s.transform_by(trsf) for s in senses]    

        return senses

    def sensitivity_jacobian(self, body=None, local=Pose3.identity(), basis=None):
        """Вернуть матрицу Якоби выхода по координатам в виде numpy массива 6xN"""

        sens = self.sensitivity_twists(body, local, basis)
        jacobian = numpy.zeros((6, len(sens)))

        for i in range(len(sens)):
            wsens = sens[i].ang
            vsens = sens[i].lin

            jacobian[0:3, i] = wsens
            jacobian[3:6, i] = vsens

        return jacobian

    def translation_sensitivity_jacobian(self, body=None, local=Pose3.identity(), basis=None):
        """Вернуть матрицу Якоби трансляции выхода по координатам в виде numpy массива 3xN"""

        sens = self.sensitivity_twists(body, local, basis)
        jacobian = numpy.zeros((3, len(sens)))

        for i in range(len(sens)):
            vsens = sens[i].lin
            jacobian[0:3, i] = vsens

        return jacobian