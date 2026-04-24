#!/usr/bin/env python3

import numpy
import numpy as np
import zencad
import zencad.assemble
import termin.ga201.point as point
import termin.ga201.join as join
import termin.ga201.screw as screw
import termin.ga201.motor as motor

from scipy.spatial import ConvexHull


class VectorsOfJacobian:
    def __init__(self, indexes, sensivities):
        self.indexes = indexes
        self.sensivities = sensivities


def draw_line2_positive(line, step=1, length=0.1):
    min = -100
    max = 100
    for i in numpy.arange(min, max, step):
        x = line.x
        y = line.y
        d = point.Point2(x, y, 0) * length
        a = line.parameter_point(i) + d
        b = line.parameter_point(i)
        zencad.display(zencad.segment(zencad.point3(
            a.x, a.y, 0), zencad.point3(b.x, b.y, 0)))


def draw_line2(line):
    unitized_line = line.unitized()
    a = unitized_line.parameter_point(-100)
    b = unitized_line.parameter_point(100)
    return zencad.display(zencad.segment(zencad.point3(a.x, a.y, 0), zencad.point3(b.x, b.y, 0)))


def draw_point2(point):
    point = point.unitized()
    return zencad.display(zencad.point3(point.x, point.y, 0))


def draw_body2(body):
    cpnts = [(p.x, p.y) for p in [p.unitized() for p in body.vertices()]]
    c = ConvexHull(cpnts)
    zpoints = [zencad.point3(cpnts[i][0], cpnts[i][1]) for i in c.vertices]
    return zencad.display(zencad.polygon(zpoints))


def zencad_sensivity_to_screw2(sensivity):
    a = sensivity[0]
    l = sensivity[1]
    return screw.Screw2(v=numpy.array([l.x, l.y], dtype=numpy.float64), m=a.z)


def zencad_transform_to_motor2(transform):
    l = transform.translation()
    a = transform.rotation_quat()
    return motor.Motor2(l[0], l[1], 0, 1) * motor.Motor2(0, 0, a.z, a.w)


def right_sensivity_screw2_of_kinunit(kinunit, senunit):
    """
        Возвращает правую чувствительность сенсорного фрейма 
        к изменению координаты кинематического фрэйма.

        H=KRS
        K - кинематический юнит
        R - мотор выхода юнита ко входу
        H - сенсорный фрейм
        S - относительный мотор сенсорного фрейма

        ->
        V_H = [H^-1 * KR]V_R
        carried = (senmotor.inverse() * kinmotor).carry(sensivity) 
    """

    sensivity = zencad_sensivity_to_screw2(kinunit.sensivity())
    kinout = kinunit.output
    kinmotor = zencad_transform_to_motor2(kinout.global_location)
    senmotor = zencad_transform_to_motor2(senunit.global_location)
    motor = senmotor.inverse() * kinmotor
    carried = sensivity.kinematic_carry(motor)
    return carried


def indexes_of_kinunits(arr):
    return [id(a) for a in arr]


def right_jacobi_matrix_lin2(kinunits, senunit):
    sensivities = [right_sensivity_screw2_of_kinunit(
        k, senunit) for k in kinunits]
    mat = np.concatenate([k.vector().reshape(2, 1) for k in sensivities], axis=1)
    return mat


def right_jacobi_matrix_lin2_by_indexes(kinunits, senunit):
    indexes = indexes_of_kinunits(kinunits)
    sensivities = [right_sensivity_screw2_of_kinunit(
        k, senunit) for k in kinunits]
    return VectorsOfJacobian(indexes, sensivities)
