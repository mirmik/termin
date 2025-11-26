<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/inertia3d.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env&nbsp;python3<br>
<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
from&nbsp;termin.geombase.pose3&nbsp;import&nbsp;Pose3<br>
from&nbsp;termin.geombase.screw&nbsp;import&nbsp;Screw3<br>
<br>
<br>
def&nbsp;skew3(v):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;3D&nbsp;skew&nbsp;matrix:&nbsp;v×x&nbsp;=&nbsp;skew3(v)&nbsp;@&nbsp;x.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;vx,&nbsp;vy,&nbsp;vz&nbsp;=&nbsp;v<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;0,&nbsp;&nbsp;&nbsp;-vz,&nbsp;&nbsp;vy&nbsp;],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;vz,&nbsp;&nbsp;&nbsp;0,&nbsp;&nbsp;-vx&nbsp;],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[-vy,&nbsp;&nbsp;vx,&nbsp;&nbsp;&nbsp;0&nbsp;&nbsp;],<br>
&nbsp;&nbsp;&nbsp;&nbsp;],&nbsp;float)<br>
<br>
<br>
class&nbsp;SpatialInertia3D:<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;mass=0.0,&nbsp;inertia=None,&nbsp;com=np.zeros(3)):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;mass&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp;масса<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia&nbsp;:&nbsp;3×3&nbsp;матрица&nbsp;тензора&nbsp;инерции&nbsp;в&nbsp;центре&nbsp;масс<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;com&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;:&nbsp;3-вектор&nbsp;центра&nbsp;масс&nbsp;(в&nbsp;локальной&nbsp;системе)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.m&nbsp;=&nbsp;float(mass)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;inertia&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.Ic&nbsp;=&nbsp;np.zeros((3,3),&nbsp;float)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;else:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.Ic&nbsp;=&nbsp;np.asarray(inertia,&nbsp;float).reshape(3,3)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.c&nbsp;=&nbsp;np.asarray(com,&nbsp;float).reshape(3)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;mass(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.m<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;inertia_matrix(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.Ic<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@property<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;center_of_mass(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.c<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;transform&nbsp;/&nbsp;rotated<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;transform_by(self,&nbsp;pose:&nbsp;Pose3)&nbsp;-&gt;&nbsp;&quot;SpatialInertia3D&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Преобразование&nbsp;spatial&nbsp;inertia&nbsp;в&nbsp;новую&nbsp;СК.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Как&nbsp;и&nbsp;в&nbsp;2D:&nbsp;COM&nbsp;просто&nbsp;переносится.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Тензор&nbsp;инерции&nbsp;переносится&nbsp;с&nbsp;помощью&nbsp;правила&nbsp;для&nbsp;тензора.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R&nbsp;=&nbsp;pose.rotation_matrix()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cW&nbsp;=&nbsp;pose.transform_point(self.c)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;I_com_new&nbsp;=&nbsp;R&nbsp;*&nbsp;I_com&nbsp;*&nbsp;R^T<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ic_new&nbsp;=&nbsp;R&nbsp;@&nbsp;self.Ic&nbsp;@&nbsp;R.T<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;SpatialInertia3D(self.m,&nbsp;Ic_new,&nbsp;cW)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;rotated(self,&nbsp;ang):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Повернуть&nbsp;spatial&nbsp;inertia&nbsp;в&nbsp;локале.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ang&nbsp;—&nbsp;3-вектор,&nbsp;интерпретируем&nbsp;как&nbsp;ось-угол&nbsp;через&nbsp;экспоненту.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Pose3&nbsp;умеет&nbsp;делать&nbsp;экспоненту<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R&nbsp;=&nbsp;Pose3(lin=np.zeros(3),&nbsp;ang=ang).rotation_matrix()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c_new&nbsp;=&nbsp;R&nbsp;@&nbsp;self.c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ic_new&nbsp;=&nbsp;R&nbsp;@&nbsp;self.Ic&nbsp;@&nbsp;R.T<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;SpatialInertia3D(self.m,&nbsp;Ic_new,&nbsp;c_new)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Spatial&nbsp;inertia&nbsp;matrix&nbsp;(VW&nbsp;order)<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;to_matrix_vw_order(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Возвращает&nbsp;spatial&nbsp;inertia&nbsp;в&nbsp;порядке:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;v,&nbsp;ω&nbsp;]&nbsp;&nbsp;(первые&nbsp;3&nbsp;—&nbsp;линейные,&nbsp;вторые&nbsp;3&nbsp;—&nbsp;угловые).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;self.m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c&nbsp;=&nbsp;self.c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;S&nbsp;=&nbsp;skew3(c)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;upper_left&nbsp;&nbsp;=&nbsp;m&nbsp;*&nbsp;np.eye(3)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;upper_right&nbsp;=&nbsp;-m&nbsp;*&nbsp;S<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lower_left&nbsp;&nbsp;=&nbsp;m&nbsp;*&nbsp;S<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lower_right&nbsp;=&nbsp;self.Ic&nbsp;+&nbsp;m&nbsp;*&nbsp;(S&nbsp;@&nbsp;S.T)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.block([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[upper_left,&nbsp;&nbsp;upper_right],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[lower_left,&nbsp;&nbsp;lower_right]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Gravity&nbsp;wrench<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;gravity_wrench(self,&nbsp;g_local:&nbsp;np.ndarray)&nbsp;-&gt;&nbsp;Screw3:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Возвращает&nbsp;винт&nbsp;(F,&nbsp;τ)&nbsp;в&nbsp;локальной&nbsp;системе.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;g_local&nbsp;—&nbsp;гравитация&nbsp;в&nbsp;ЛОКАЛЕ.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;self.m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c&nbsp;=&nbsp;self.c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;=&nbsp;m&nbsp;*&nbsp;g_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;τ&nbsp;=&nbsp;np.cross(c,&nbsp;F)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Screw3(ang=τ,&nbsp;lin=F)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Bias&nbsp;wrench<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;bias_wrench(self,&nbsp;velocity:&nbsp;Screw3)&nbsp;-&gt;&nbsp;Screw3:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Пространственный&nbsp;bias-винт:&nbsp;v&nbsp;×*&nbsp;(I&nbsp;v).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Полный&nbsp;3D&nbsp;аналог&nbsp;твоего&nbsp;2D-кода.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;self.m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c&nbsp;=&nbsp;self.c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ic&nbsp;=&nbsp;self.Ic<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_lin&nbsp;=&nbsp;velocity.lin<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_ang&nbsp;=&nbsp;velocity.ang<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;S&nbsp;=&nbsp;skew3(c)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;spatial&nbsp;inertia&nbsp;*&nbsp;v:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h_lin&nbsp;=&nbsp;m&nbsp;*&nbsp;(v_lin&nbsp;+&nbsp;np.cross(v_ang,&nbsp;c))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h_ang&nbsp;=&nbsp;Ic&nbsp;@&nbsp;v_ang&nbsp;+&nbsp;m&nbsp;*&nbsp;np.cross(c,&nbsp;v_lin)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;теперь&nbsp;bias&nbsp;=&nbsp;v&nbsp;×*&nbsp;h<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;линейная&nbsp;часть:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b_lin&nbsp;=&nbsp;np.cross(v_ang,&nbsp;h_lin)&nbsp;+&nbsp;np.cross(v_lin,&nbsp;h_ang)*0.0&nbsp;&nbsp;#&nbsp;линейная&nbsp;от&nbsp;линейной&nbsp;не&nbsp;даёт<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;угловая&nbsp;часть:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b_ang&nbsp;=&nbsp;np.cross(v_ang,&nbsp;h_ang)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Screw3(ang=b_ang,&nbsp;lin=b_lin)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Сложение&nbsp;spatial&nbsp;inertia<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__add__(self,&nbsp;other):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;not&nbsp;isinstance(other,&nbsp;SpatialInertia3D):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;NotImplemented<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m1,&nbsp;m2&nbsp;=&nbsp;self.m,&nbsp;other.m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c1,&nbsp;c2&nbsp;=&nbsp;self.c,&nbsp;other.c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;I1,&nbsp;I2&nbsp;=&nbsp;self.Ic,&nbsp;other.Ic<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;m&nbsp;=&nbsp;m1&nbsp;+&nbsp;m2<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;m&nbsp;==&nbsp;0.0:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;SpatialInertia3D(0.0,&nbsp;np.zeros((3,3)),&nbsp;np.zeros(3))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;c&nbsp;=&nbsp;(m1&nbsp;*&nbsp;c1&nbsp;+&nbsp;m2&nbsp;*&nbsp;c2)&nbsp;/&nbsp;m<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;d1&nbsp;=&nbsp;c1&nbsp;-&nbsp;c<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;d2&nbsp;=&nbsp;c2&nbsp;-&nbsp;c<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;S1&nbsp;=&nbsp;skew3(d1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;S2&nbsp;=&nbsp;skew3(d2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ic&nbsp;=&nbsp;I1&nbsp;+&nbsp;m1&nbsp;*&nbsp;(S1&nbsp;@&nbsp;S1.T)&nbsp;+&nbsp;I2&nbsp;+&nbsp;m2&nbsp;*&nbsp;(S2&nbsp;@&nbsp;S2.T)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;SpatialInertia3D(m,&nbsp;Ic,&nbsp;c)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Kinetic&nbsp;energy<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;------------------------------------------------------------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;get_kinetic_energy(self,&nbsp;velocity:&nbsp;np.ndarray,&nbsp;omega:&nbsp;np.ndarray)&nbsp;-&gt;&nbsp;float:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;velocity&nbsp;—&nbsp;линейная&nbsp;скорость<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omega&nbsp;&nbsp;&nbsp;&nbsp;—&nbsp;угловая&nbsp;скорость<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v2&nbsp;=&nbsp;np.dot(velocity,&nbsp;velocity)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;0.5&nbsp;*&nbsp;self.m&nbsp;*&nbsp;v2&nbsp;+&nbsp;0.5&nbsp;*&nbsp;(omega&nbsp;@&nbsp;(self.Ic&nbsp;@&nbsp;omega))<br>
<!-- END SCAT CODE -->
</body>
</html>
