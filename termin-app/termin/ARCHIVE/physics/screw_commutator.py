#!/usr/bin/env python3
import numpy
from termin.physics.pose_object import PoseObject
from termin.physics.indexed_matrix import IndexedMatrix, IndexedVector
from termin.ga201.motor import Motor2
from termin.ga201.screw import Screw2
import math


class VariableValueCommutator:
    def __init__(self, dim):
        self._dim = dim
        self._sources = [VariableValue(self, i) for i in range(dim)]
        self._values = [0] * dim

    def sources(self):
        return self._sources

    def set_value(self, idx: int, value: float):
        self._values[idx] = value

    def values(self):
        return self._values

    def indexes(self):
        return self._sources

    def dim(self):
        return self._dim


class VariableValue:
    def __init__(self, commutator, index):
        self.commutator = commutator
        self.index = index

    def set_value(self, value):
        self.commutator.set_value(self.index, value)

    def __str__(self):
        return str(id(self))

    def __repr__(self):
        return str(id(self))

    def __lt__(self, oth):
        return id(self) < id(oth)


class ScrewVariableValue(VariableValue):
    def __init__(self, commutator, index):
        super().__init__(commutator, index)
        self._value = Screw2()


class ScrewCommutator(VariableValueCommutator):
    def __init__(self, local_senses, pose_object):
        dim = len(local_senses)
        super().__init__(dim)
        self.pose_object = pose_object
        self._screws = local_senses

    def screws(self):
        return self._screws

    def position(self):
        return self.pose_object.position()

    def derivative_matrix_from(self, other):
        self_screws = self.screws()
        other_screws = other.screws()
        self_pose = self.pose_object.position()
        other_pose = other.pose_object.position()
        diff_pose = self_pose.inverse() * other_pose
        B = numpy.zeros((len(self_screws), len(other_screws)))
        for i, self_screw in enumerate(self_screws):
            for j, other_screw in enumerate(other_screws):
                carried = other_screw.kinematic_carry(
                    diff_pose)
                B[i, j] = self_screw.fulldot(carried)
        return IndexedMatrix(B, self.indexes(), other.indexes(), lcomm=self, rcomm=other)

    def derivative(self, other):
        return self.derivative_matrix_from(other)

if __name__ == "__main__":
    numpy.set_printoptions(precision=3, suppress=True)

    print("1:")
    p1 = PoseObject(Motor2.translation(0, 0))
    p2 = PoseObject(Motor2.translation(1, 0))
    sc1 = ScrewCommutator(local_senses=[Screw2(
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)
    sc2 = ScrewCommutator(local_senses=[Screw2(
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)
    B = sc1.derivative_matrix_from(sc2)
    print(B)

    print("2:")
    p1 = PoseObject(Motor2.translation(2, 0))
    p2 = PoseObject(Motor2.translation(3, 0))
    sc1 = ScrewCommutator(local_senses=[Screw2(
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)
    sc2 = ScrewCommutator(local_senses=[Screw2(
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)
    B = sc1.derivative_matrix_from(sc2)
    print(B)

    print("3:")
    p1 = PoseObject(Motor2.rotation(math.pi/2))
    p2 = PoseObject(Motor2.rotation(math.pi/2) * Motor2.translation(1, 0))
    sc1 = ScrewCommutator(local_senses=[Screw2(
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)
    sc2 = ScrewCommutator(local_senses=[Screw2(
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)
    B = sc1.derivative_matrix_from(sc2)
    print(B)

    print("4:")
    p1 = PoseObject(Motor2.translation(0, 0))
    p2 = PoseObject(Motor2.rotation(math.pi/2) * Motor2.translation(1, 0))
    sc1 = ScrewCommutator(local_senses=[Screw2(
        v=[0, 1]), Screw2(v=[-1, 0]), Screw2(m=1)], pose_object=p1)
    sc2 = ScrewCommutator(local_senses=[Screw2(
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p2)
    B = sc1.derivative_matrix_from(sc2)
    print(B)

    print("5:")
    p1 = PoseObject(Motor2.rotation(math.pi/2) * Motor2.translation(0, 0))
    p2 = PoseObject(Motor2.translation(0, 1))
    sc1 = ScrewCommutator(local_senses=[Screw2(
        v=[1, 0]), Screw2(v=[0, 1]), Screw2(m=1)], pose_object=p1)
    sc2 = ScrewCommutator(local_senses=[Screw2(
        v=[0, 1]), Screw2(v=[-1, 0]), Screw2(m=1)], pose_object=p2)
    B = sc1.derivative_matrix_from(sc2)
    print(B)
