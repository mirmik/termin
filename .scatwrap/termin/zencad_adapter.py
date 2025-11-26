<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/zencad_adapter.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
import numpy<br>
import numpy as np<br>
import zencad<br>
import zencad.assemble<br>
import termin.ga201.point as point<br>
import termin.ga201.join as join<br>
import termin.ga201.screw as screw<br>
import termin.ga201.motor as motor<br>
<br>
from scipy.spatial import ConvexHull<br>
<br>
<br>
class VectorsOfJacobian:<br>
    def __init__(self, indexes, sensivities):<br>
        self.indexes = indexes<br>
        self.sensivities = sensivities<br>
<br>
<br>
def draw_line2_positive(line, step=1, length=0.1):<br>
    min = -100<br>
    max = 100<br>
    for i in numpy.arange(min, max, step):<br>
        x = line.x<br>
        y = line.y<br>
        d = point.Point2(x, y, 0) * length<br>
        a = line.parameter_point(i) + d<br>
        b = line.parameter_point(i)<br>
        zencad.display(zencad.segment(zencad.point3(<br>
            a.x, a.y, 0), zencad.point3(b.x, b.y, 0)))<br>
<br>
<br>
def draw_line2(line):<br>
    unitized_line = line.unitized()<br>
    a = unitized_line.parameter_point(-100)<br>
    b = unitized_line.parameter_point(100)<br>
    return zencad.display(zencad.segment(zencad.point3(a.x, a.y, 0), zencad.point3(b.x, b.y, 0)))<br>
<br>
<br>
def draw_point2(point):<br>
    point = point.unitized()<br>
    return zencad.display(zencad.point3(point.x, point.y, 0))<br>
<br>
<br>
def draw_body2(body):<br>
    cpnts = [(p.x, p.y) for p in [p.unitized() for p in body.vertices()]]<br>
    c = ConvexHull(cpnts)<br>
    zpoints = [zencad.point3(cpnts[i][0], cpnts[i][1]) for i in c.vertices]<br>
    return zencad.display(zencad.polygon(zpoints))<br>
<br>
<br>
def zencad_sensivity_to_screw2(sensivity):<br>
    a = sensivity[0]<br>
    l = sensivity[1]<br>
    return screw.Screw2(v=numpy.array([l.x, l.y], dtype=numpy.float64), m=a.z)<br>
<br>
<br>
def zencad_transform_to_motor2(transform):<br>
    l = transform.translation()<br>
    a = transform.rotation_quat()<br>
    return motor.Motor2(l[0], l[1], 0, 1) * motor.Motor2(0, 0, a.z, a.w)<br>
<br>
<br>
def right_sensivity_screw2_of_kinunit(kinunit, senunit):<br>
    &quot;&quot;&quot;<br>
        Возвращает правую чувствительность сенсорного фрейма <br>
        к изменению координаты кинематического фрэйма.<br>
<br>
        H=KRS<br>
        K - кинематический юнит<br>
        R - мотор выхода юнита ко входу<br>
        H - сенсорный фрейм<br>
        S - относительный мотор сенсорного фрейма<br>
<br>
        -&gt;<br>
        V_H = [H^-1 * KR]V_R<br>
        carried = (senmotor.inverse() * kinmotor).carry(sensivity) <br>
    &quot;&quot;&quot;<br>
<br>
    sensivity = zencad_sensivity_to_screw2(kinunit.sensivity())<br>
    kinout = kinunit.output<br>
    kinmotor = zencad_transform_to_motor2(kinout.global_location)<br>
    senmotor = zencad_transform_to_motor2(senunit.global_location)<br>
    motor = senmotor.inverse() * kinmotor<br>
    carried = sensivity.kinematic_carry(motor)<br>
    return carried<br>
<br>
<br>
def indexes_of_kinunits(arr):<br>
    return [id(a) for a in arr]<br>
<br>
<br>
def right_jacobi_matrix_lin2(kinunits, senunit):<br>
    sensivities = [right_sensivity_screw2_of_kinunit(<br>
        k, senunit) for k in kinunits]<br>
    mat = np.concatenate([k.vector().reshape(2, 1) for k in sensivities], axis=1)<br>
    return mat<br>
<br>
<br>
def right_jacobi_matrix_lin2_by_indexes(kinunits, senunit):<br>
    indexes = indexes_of_kinunits(kinunits)<br>
    sensivities = [right_sensivity_screw2_of_kinunit(<br>
        k, senunit) for k in kinunits]<br>
    return VectorsOfJacobian(indexes, sensivities)<br>
<!-- END SCAT CODE -->
</body>
</html>
