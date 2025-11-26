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
&#9;def __init__(self, indexes, sensivities):<br>
&#9;&#9;self.indexes = indexes<br>
&#9;&#9;self.sensivities = sensivities<br>
<br>
<br>
def draw_line2_positive(line, step=1, length=0.1):<br>
&#9;min = -100<br>
&#9;max = 100<br>
&#9;for i in numpy.arange(min, max, step):<br>
&#9;&#9;x = line.x<br>
&#9;&#9;y = line.y<br>
&#9;&#9;d = point.Point2(x, y, 0) * length<br>
&#9;&#9;a = line.parameter_point(i) + d<br>
&#9;&#9;b = line.parameter_point(i)<br>
&#9;&#9;zencad.display(zencad.segment(zencad.point3(<br>
&#9;&#9;&#9;a.x, a.y, 0), zencad.point3(b.x, b.y, 0)))<br>
<br>
<br>
def draw_line2(line):<br>
&#9;unitized_line = line.unitized()<br>
&#9;a = unitized_line.parameter_point(-100)<br>
&#9;b = unitized_line.parameter_point(100)<br>
&#9;return zencad.display(zencad.segment(zencad.point3(a.x, a.y, 0), zencad.point3(b.x, b.y, 0)))<br>
<br>
<br>
def draw_point2(point):<br>
&#9;point = point.unitized()<br>
&#9;return zencad.display(zencad.point3(point.x, point.y, 0))<br>
<br>
<br>
def draw_body2(body):<br>
&#9;cpnts = [(p.x, p.y) for p in [p.unitized() for p in body.vertices()]]<br>
&#9;c = ConvexHull(cpnts)<br>
&#9;zpoints = [zencad.point3(cpnts[i][0], cpnts[i][1]) for i in c.vertices]<br>
&#9;return zencad.display(zencad.polygon(zpoints))<br>
<br>
<br>
def zencad_sensivity_to_screw2(sensivity):<br>
&#9;a = sensivity[0]<br>
&#9;l = sensivity[1]<br>
&#9;return screw.Screw2(v=numpy.array([l.x, l.y], dtype=numpy.float64), m=a.z)<br>
<br>
<br>
def zencad_transform_to_motor2(transform):<br>
&#9;l = transform.translation()<br>
&#9;a = transform.rotation_quat()<br>
&#9;return motor.Motor2(l[0], l[1], 0, 1) * motor.Motor2(0, 0, a.z, a.w)<br>
<br>
<br>
def right_sensivity_screw2_of_kinunit(kinunit, senunit):<br>
&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает правую чувствительность сенсорного фрейма <br>
&#9;&#9;к изменению координаты кинематического фрэйма.<br>
<br>
&#9;&#9;H=KRS<br>
&#9;&#9;K - кинематический юнит<br>
&#9;&#9;R - мотор выхода юнита ко входу<br>
&#9;&#9;H - сенсорный фрейм<br>
&#9;&#9;S - относительный мотор сенсорного фрейма<br>
<br>
&#9;&#9;-&gt;<br>
&#9;&#9;V_H = [H^-1 * KR]V_R<br>
&#9;&#9;carried = (senmotor.inverse() * kinmotor).carry(sensivity) <br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;sensivity = zencad_sensivity_to_screw2(kinunit.sensivity())<br>
&#9;kinout = kinunit.output<br>
&#9;kinmotor = zencad_transform_to_motor2(kinout.global_location)<br>
&#9;senmotor = zencad_transform_to_motor2(senunit.global_location)<br>
&#9;motor = senmotor.inverse() * kinmotor<br>
&#9;carried = sensivity.kinematic_carry(motor)<br>
&#9;return carried<br>
<br>
<br>
def indexes_of_kinunits(arr):<br>
&#9;return [id(a) for a in arr]<br>
<br>
<br>
def right_jacobi_matrix_lin2(kinunits, senunit):<br>
&#9;sensivities = [right_sensivity_screw2_of_kinunit(<br>
&#9;&#9;k, senunit) for k in kinunits]<br>
&#9;mat = np.concatenate([k.vector().reshape(2, 1) for k in sensivities], axis=1)<br>
&#9;return mat<br>
<br>
<br>
def right_jacobi_matrix_lin2_by_indexes(kinunits, senunit):<br>
&#9;indexes = indexes_of_kinunits(kinunits)<br>
&#9;sensivities = [right_sensivity_screw2_of_kinunit(<br>
&#9;&#9;k, senunit) for k in kinunits]<br>
&#9;return VectorsOfJacobian(indexes, sensivities)<br>
<!-- END SCAT CODE -->
</body>
</html>
