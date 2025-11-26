<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/inertia2d.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env&nbsp;python3<br>
&quot;&quot;&quot;<br>
Инерционные&nbsp;характеристики&nbsp;для&nbsp;2D&nbsp;многотельной&nbsp;динамики.<br>
&quot;&quot;&quot;<br>
<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
from&nbsp;termin.geombase.pose2&nbsp;import&nbsp;Pose2<br>
from&nbsp;termin.geombase.screw&nbsp;import&nbsp;Screw2,&nbsp;cross2d_scalar<br>
<br>
<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
<br>
def&nbsp;skew2(v):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;2D&nbsp;псевдо-skew:&nbsp;ω&nbsp;×&nbsp;r&nbsp;=&nbsp;[-ω*r_y,&nbsp;ω*r_x].<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Здесь&nbsp;возвращаем&nbsp;2×2&nbsp;матрицу&nbsp;для&nbsp;углового&nbsp;ω.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.array([[0,&nbsp;-v],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[v,&nbsp;&nbsp;0]])<br>
<br>
class&nbsp;SpatialInertia2D:<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;mass&nbsp;=&nbsp;0.0,&nbsp;inertia&nbsp;=&nbsp;0.0,&nbsp;com=np.zeros(2)):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;mass&nbsp;:&nbsp;масса&nbsp;тела<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;J_com&nbsp;:&nbsp;момент&nbsp;инерции&nbsp;вокруг&nbsp;центра&nbsp;масс&nbsp;(скаляр)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;com&nbsp;:&nbsp;2-вектор&nbsp;центра&nbsp;масс&nbsp;в&nbsp;локальной&nbsp;системе<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.m&nbsp;=&nbsp;float(mass)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.Jc&nbsp;=&nbsp;float(inertia)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.c&nbsp;=&nbsp;np.asarray(com,&nbsp;float).reshape(2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;I_com(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.Jc<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;mass(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.m<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;inertia(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.Jc<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;center_of_mass(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.c<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;transform_by(self,&nbsp;pose:&nbsp;Pose2)&nbsp;-&gt;&nbsp;&quot;SpatialInertia2D&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Трансформировать&nbsp;инерцию&nbsp;в&nbsp;новую&nbsp;систему&nbsp;координат.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;В&nbsp;2D&nbsp;момент&nbsp;инерции&nbsp;инвариантен&nbsp;относительно&nbsp;поворота.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Центр&nbsp;масс&nbsp;переводится&nbsp;напрямую.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c_new&nbsp;=&nbsp;pose.transform_point(self.c)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;SpatialInertia2D(self.m,&nbsp;self.I_com,&nbsp;c_new)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Поворот&nbsp;инерции<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;rotated(self,&nbsp;theta):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Повернуть&nbsp;spatial&nbsp;inertia&nbsp;2D&nbsp;на&nbsp;угол&nbsp;theta.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R&nbsp;=&nbsp;np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[np.cos(theta),&nbsp;-np.sin(theta)],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[np.sin(theta),&nbsp;&nbsp;np.cos(theta)],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;поворот&nbsp;центра&nbsp;масс<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c_new&nbsp;=&nbsp;R&nbsp;@&nbsp;self.c<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;J&nbsp;переносится&nbsp;как&nbsp;скаляр&nbsp;(инвариант)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;SpatialInertia2D(self.m,&nbsp;self.Jc,&nbsp;c_new)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Spatial&nbsp;inertia&nbsp;matrix<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;to_matrix_vw_order(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;self.m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cx,&nbsp;cy&nbsp;=&nbsp;self.c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;J&nbsp;=&nbsp;self.Jc<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;upper_left&nbsp;=&nbsp;m&nbsp;*&nbsp;np.eye(2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lower_left&nbsp;=&nbsp;m&nbsp;*&nbsp;np.array([[-cy,&nbsp;cx]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;upper_right&nbsp;=&nbsp;lower_left.T<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lower_right&nbsp;=&nbsp;np.array([[J&nbsp;+&nbsp;m&nbsp;*&nbsp;(cx*cx&nbsp;+&nbsp;cy*cy)]])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.block([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[upper_left,&nbsp;&nbsp;&nbsp;&nbsp;upper_right],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[lower_left,&nbsp;&nbsp;&nbsp;&nbsp;lower_right]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;to_matrix_wv_order(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;self.m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cx,&nbsp;cy&nbsp;=&nbsp;self.c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;J&nbsp;=&nbsp;self.Jc<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;spatial&nbsp;inertia&nbsp;в&nbsp;2D&nbsp;(WV-порядок)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[J&nbsp;+&nbsp;m*(cx*cx&nbsp;+&nbsp;cy*cy),&nbsp;&nbsp;m*cy,&nbsp;&nbsp;&nbsp;-m*cx],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[m*cy,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0&nbsp;&nbsp;&nbsp;&nbsp;],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[-m*cx,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;&nbsp;&nbsp;&nbsp;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;],&nbsp;float)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Gravity&nbsp;wrench<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;gravity_wrench(self,&nbsp;g):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Возвращает&nbsp;3×1&nbsp;винт&nbsp;(Fx,&nbsp;Fy,&nbsp;τz)&nbsp;в&nbsp;локальной&nbsp;системе!<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;g&nbsp;—&nbsp;вектор&nbsp;гравитации&nbsp;в&nbsp;ЛОКАЛЬНОЙ&nbsp;системе.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;self.m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cx,&nbsp;cy&nbsp;=&nbsp;self.c<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;=&nbsp;m&nbsp;*&nbsp;g<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;τ&nbsp;=&nbsp;cx&nbsp;*&nbsp;F[1]&nbsp;-&nbsp;cy&nbsp;*&nbsp;F[0]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Screw2(ang=τ,&nbsp;lin=F)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__add__(self,&nbsp;other):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;not&nbsp;isinstance(other,&nbsp;SpatialInertia2D):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;NotImplemented<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m1,&nbsp;m2&nbsp;=&nbsp;self.m,&nbsp;other.m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c1,&nbsp;c2&nbsp;=&nbsp;self.c,&nbsp;other.c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;J1,&nbsp;J2&nbsp;=&nbsp;self.Jc,&nbsp;other.Jc<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;m1&nbsp;+&nbsp;m2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;m&nbsp;==&nbsp;0.0:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;пустая&nbsp;инерция<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;SpatialInertia2D(0.0,&nbsp;0.0,&nbsp;np.zeros(2))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;общий&nbsp;центр&nbsp;масс<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c&nbsp;=&nbsp;(m1&nbsp;*&nbsp;c1&nbsp;+&nbsp;m2&nbsp;*&nbsp;c2)&nbsp;/&nbsp;m<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;смещения&nbsp;от&nbsp;индивидуальных&nbsp;COM&nbsp;к&nbsp;общему<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;d1&nbsp;=&nbsp;c1&nbsp;-&nbsp;c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;d2&nbsp;=&nbsp;c2&nbsp;-&nbsp;c<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;параллельный&nbsp;перенос&nbsp;для&nbsp;моментов&nbsp;инерции&nbsp;(вокруг&nbsp;общего&nbsp;COM)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;J&nbsp;=&nbsp;J1&nbsp;+&nbsp;m1&nbsp;*&nbsp;(d1&nbsp;@&nbsp;d1)&nbsp;+&nbsp;J2&nbsp;+&nbsp;m2&nbsp;*&nbsp;(d2&nbsp;@&nbsp;d2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;SpatialInertia2D(m,&nbsp;J,&nbsp;c)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;get_kinetic_energy(self,&nbsp;velocity:&nbsp;np.ndarray,&nbsp;omega:&nbsp;float)&nbsp;-&gt;&nbsp;float:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_squared&nbsp;=&nbsp;np.dot(velocity,&nbsp;velocity)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;0.5&nbsp;*&nbsp;self.m&nbsp;*&nbsp;v_squared&nbsp;+&nbsp;0.5&nbsp;*&nbsp;self.I_com&nbsp;*&nbsp;omega**2<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;bias_wrench(self,&nbsp;velocity&nbsp;:&nbsp;Screw2)&nbsp;-&gt;&nbsp;Screw2:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vx,&nbsp;vy,&nbsp;omega&nbsp;=&nbsp;velocity.lin[0],&nbsp;velocity.lin[1],&nbsp;velocity.ang<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;self.m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cx,&nbsp;cy&nbsp;=&nbsp;self.c<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Fx&nbsp;=&nbsp;&nbsp;m&nbsp;*&nbsp;(omega&nbsp;*&nbsp;vy&nbsp;+&nbsp;omega**2&nbsp;*&nbsp;cx)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Fy&nbsp;=&nbsp;-m&nbsp;*&nbsp;(omega&nbsp;*&nbsp;vx)&nbsp;+&nbsp;m&nbsp;*&nbsp;(omega**2&nbsp;*&nbsp;cy)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;τz&nbsp;=&nbsp;0.0&nbsp;&nbsp;#&nbsp;В&nbsp;2D&nbsp;кориолисового&nbsp;момента&nbsp;нет<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Screw2(ang=τz,&nbsp;lin=np.array([Fx,&nbsp;Fy]))<br>
<!-- END SCAT CODE -->
</body>
</html>
