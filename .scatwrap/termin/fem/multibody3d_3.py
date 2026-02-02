<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody3d_3.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;typing&nbsp;import&nbsp;List,&nbsp;Dict<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
<br>
from&nbsp;termin.fem.assembler&nbsp;import&nbsp;Variable,&nbsp;Contribution<br>
from&nbsp;termin.geombase&nbsp;import&nbsp;Pose3<br>
from&nbsp;termin.geombase.screw&nbsp;import&nbsp;Screw3<br>
from&nbsp;termin.fem.inertia3d&nbsp;import&nbsp;SpatialInertia3D<br>
<br>
<br>
&quot;&quot;&quot;<br>
Соглашение&nbsp;такое&nbsp;же,&nbsp;как&nbsp;в&nbsp;2D-версии:<br>
<br>
Все&nbsp;уравнения&nbsp;собираются&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела.<br>
Глобальная&nbsp;поза&nbsp;тела&nbsp;хранится&nbsp;отдельно&nbsp;и&nbsp;используется&nbsp;только&nbsp;для&nbsp;обновления&nbsp;геометрии.<br>
<br>
Преобразования&nbsp;следуют&nbsp;конвенции&nbsp;локальная&nbsp;система&nbsp;-&gt;&nbsp;мировая&nbsp;система:<br>
&nbsp;&nbsp;&nbsp;&nbsp;p_world&nbsp;=&nbsp;P(q)&nbsp;@&nbsp;p_local<br>
&quot;&quot;&quot;<br>
<br>
def&nbsp;_skew(r:&nbsp;np.ndarray)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Матрица&nbsp;векторного&nbsp;произведения:&nbsp;&nbsp;r×x&nbsp;=&nbsp;skew(r)&nbsp;@&nbsp;x.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;rx,&nbsp;ry,&nbsp;rz&nbsp;=&nbsp;r<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;&nbsp;&nbsp;0.0,&nbsp;-rz,&nbsp;&nbsp;&nbsp;ry],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;&nbsp;&nbsp;rz,&nbsp;&nbsp;0.0,&nbsp;-rx],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;&nbsp;-ry,&nbsp;&nbsp;rx,&nbsp;&nbsp;0.0],<br>
&nbsp;&nbsp;&nbsp;&nbsp;],&nbsp;dtype=float)<br>
<br>
def&nbsp;quat_normalize(q):<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;q&nbsp;/&nbsp;np.linalg.norm(q)<br>
<br>
def&nbsp;quat_mul(q1,&nbsp;q2):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Кватернионное&nbsp;произведение&nbsp;q1*q2&nbsp;(оба&nbsp;в&nbsp;формате&nbsp;[x,y,z,w]).&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;x1,y1,z1,w1&nbsp;=&nbsp;q1<br>
&nbsp;&nbsp;&nbsp;&nbsp;x2,y2,z2,w2&nbsp;=&nbsp;q2<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;w1*x2&nbsp;+&nbsp;x1*w2&nbsp;+&nbsp;y1*z2&nbsp;-&nbsp;z1*y2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;w1*y2&nbsp;+&nbsp;y1*w2&nbsp;+&nbsp;z1*x2&nbsp;-&nbsp;x1*z2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;w1*z2&nbsp;+&nbsp;z1*w2&nbsp;+&nbsp;x1*y2&nbsp;-&nbsp;y1*x2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;w1*w2&nbsp;-&nbsp;x1*x2&nbsp;-&nbsp;y1*y2&nbsp;-&nbsp;z1*z2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
def&nbsp;quat_from_small_angle(dθ):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Создать&nbsp;кватернион&nbsp;вращения&nbsp;из&nbsp;малого&nbsp;углового&nbsp;вектора&nbsp;dθ.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;θ&nbsp;=&nbsp;np.linalg.norm(dθ)<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;θ&nbsp;&lt;&nbsp;1e-12:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;линеаризация<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;quat_normalize(np.array([0.5*dθ[0],&nbsp;0.5*dθ[1],&nbsp;0.5*dθ[2],&nbsp;1.0]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;axis&nbsp;=&nbsp;dθ&nbsp;/&nbsp;θ<br>
&nbsp;&nbsp;&nbsp;&nbsp;s&nbsp;=&nbsp;np.sin(0.5&nbsp;*&nbsp;θ)<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.array([axis[0]*s,&nbsp;axis[1]*s,&nbsp;axis[2]*s,&nbsp;np.cos(0.5*θ)])<br>
<br>
<br>
<br>
class&nbsp;RigidBody3D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Твёрдое&nbsp;тело&nbsp;в&nbsp;3D,&nbsp;все&nbsp;расчёты&nbsp;выполняются&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Глобальная&nbsp;поза&nbsp;хранится&nbsp;отдельно&nbsp;и&nbsp;используется&nbsp;только&nbsp;для&nbsp;обновления&nbsp;геометрии.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Порядок&nbsp;пространственных&nbsp;векторов&nbsp;(vw_order):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;v_x,&nbsp;v_y,&nbsp;v_z,&nbsp;ω_x,&nbsp;ω_y,&nbsp;ω_z&nbsp;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia:&nbsp;SpatialInertia3D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity:&nbsp;np.ndarray&nbsp;=&nbsp;None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name:&nbsp;str&nbsp;=&nbsp;&quot;rbody3d&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;angle_normalize:&nbsp;callable&nbsp;=&nbsp;None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;[a_lin(3),&nbsp;α(3)]&nbsp;в&nbsp;локальной&nbsp;СК<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.acceleration_var&nbsp;=&nbsp;Variable(name&nbsp;+&nbsp;&quot;_acc&quot;,&nbsp;size=6,&nbsp;tag=&quot;acceleration&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;[v_lin(3),&nbsp;ω(3)]&nbsp;в&nbsp;локальной&nbsp;СК<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.velocity_var&nbsp;=&nbsp;Variable(name&nbsp;+&nbsp;&quot;_vel&quot;,&nbsp;size=6,&nbsp;tag=&quot;velocity&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;[Δx(3),&nbsp;Δφ(3)]&nbsp;локальная&nbsp;приращённая&nbsp;поза&nbsp;для&nbsp;интеграции<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.local_pose_var&nbsp;=&nbsp;Variable(name&nbsp;+&nbsp;&quot;_pos&quot;,&nbsp;size=6,&nbsp;tag=&quot;position&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;глобальная&nbsp;поза&nbsp;тела<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose&nbsp;=&nbsp;Pose3(lin=np.zeros(3),&nbsp;ang=np.array([0.0,&nbsp;0.0,&nbsp;0.0,&nbsp;1.0]))&nbsp;&nbsp;#&nbsp;единичный&nbsp;кватернион<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.inertia&nbsp;=&nbsp;inertia<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.angle_normalize&nbsp;=&nbsp;angle_normalize<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;сила&nbsp;тяжести&nbsp;задаётся&nbsp;в&nbsp;мировых&nbsp;координатах<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;по&nbsp;аналогии&nbsp;с&nbsp;2D:&nbsp;-g&nbsp;по&nbsp;оси&nbsp;y<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;gravity&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.gravity&nbsp;=&nbsp;np.array([0.0,&nbsp;-9.81,&nbsp;0.0],&nbsp;dtype=float)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;else:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.gravity&nbsp;=&nbsp;np.asarray(gravity,&nbsp;float).reshape(3)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([self.acceleration_var,&nbsp;self.velocity_var,&nbsp;self.local_pose_var],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;----------&nbsp;геттеры&nbsp;----------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;pose(self)&nbsp;-&gt;&nbsp;Pose3:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.global_pose<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;set_pose(self,&nbsp;pose:&nbsp;Pose3):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose&nbsp;=&nbsp;pose<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;----------&nbsp;вклад&nbsp;в&nbsp;систему&nbsp;----------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Вклад&nbsp;тела&nbsp;в&nbsp;уравнения&nbsp;движения&nbsp;(в&nbsp;локальной&nbsp;СК):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;I&nbsp;*&nbsp;a&nbsp;+&nbsp;v×*&nbsp;(I&nbsp;v)&nbsp;=&nbsp;F<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_mass_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;matrices[&quot;load&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_idx&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_local&nbsp;=&nbsp;Screw3.from_vector_vw_order(self.velocity_var.value)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bias&nbsp;=&nbsp;self.inertia.bias_wrench(v_local)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;гравитация&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;g_local&nbsp;=&nbsp;self.global_pose.inverse().rotate_vector(self.gravity)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;grav&nbsp;=&nbsp;self.inertia.gravity_wrench(g_local)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[a_idx]&nbsp;+=&nbsp;-&nbsp;bias.to_vector_vw_order()&nbsp;+&nbsp;grav.to_vector_vw_order()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_mass_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_to_mass_matrix(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Массовая&nbsp;матрица&nbsp;в&nbsp;локальной&nbsp;СК.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;matrices[&quot;mass&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_idx&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A[np.ix_(a_idx,&nbsp;a_idx)]&nbsp;+=&nbsp;self.inertia.to_matrix_vw_order()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;----------&nbsp;интеграция&nbsp;шага&nbsp;----------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;finish_timestep(self,&nbsp;dt:&nbsp;float):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;=&nbsp;self.velocity_var.value<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a&nbsp;=&nbsp;self.acceleration_var.value<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;+=&nbsp;a&nbsp;*&nbsp;dt<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.velocity_var.value&nbsp;=&nbsp;v<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;линейное&nbsp;смещение<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_lin&nbsp;=&nbsp;v[0:3]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dp_lin&nbsp;=&nbsp;v_lin&nbsp;*&nbsp;dt<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;угловое&nbsp;малое&nbsp;приращение&nbsp;через&nbsp;кватернион<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_ang&nbsp;=&nbsp;v[3:6]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dθ&nbsp;=&nbsp;v_ang&nbsp;*&nbsp;dt<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_delta&nbsp;=&nbsp;quat_from_small_angle(dθ)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;обновляем&nbsp;глобальную&nbsp;позу<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;pose.lin&nbsp;+=&nbsp;R&nbsp;*&nbsp;dp_lin&nbsp;&nbsp;&nbsp;(делает&nbsp;Pose3&nbsp;оператор&nbsp;@)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;pose.ang&nbsp;=&nbsp;pose.ang&nbsp;*&nbsp;q_delta<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;delta_pose_local&nbsp;=&nbsp;Pose3(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lin=dp_lin,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ang=q_delta,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose&nbsp;=&nbsp;self.global_pose&nbsp;@&nbsp;delta_pose_local<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;сбрасываем&nbsp;локальную&nbsp;позу<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.local_pose_var.value[:]&nbsp;=&nbsp;0.0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.angle_normalize&nbsp;is&nbsp;not&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose.ang&nbsp;=&nbsp;self.angle_normalize(self.global_pose.ang)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;else:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose.ang&nbsp;=&nbsp;quat_normalize(self.global_pose.ang)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;finish_correction_step(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dp&nbsp;=&nbsp;self.local_pose_var.value<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;линейная&nbsp;часть<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dp_lin&nbsp;=&nbsp;dp[0:3]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;угловая&nbsp;часть&nbsp;dp[3:6]&nbsp;—&nbsp;это&nbsp;снова&nbsp;угловой&nbsp;вектор,&nbsp;надо&nbsp;превращать&nbsp;в&nbsp;кватернион<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;dθ&nbsp;=&nbsp;dp[3:6]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_delta&nbsp;=&nbsp;quat_from_small_angle(dθ)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;delta_pose_local&nbsp;=&nbsp;Pose3(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lin=dp_lin,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ang=q_delta,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose&nbsp;=&nbsp;self.global_pose&nbsp;@&nbsp;delta_pose_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.local_pose_var.value[:]&nbsp;=&nbsp;0.0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose.ang&nbsp;=&nbsp;quat_normalize(self.global_pose.ang)<br>
<br>
<br>
class&nbsp;ForceOnBody3D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Внешний&nbsp;пространственный&nbsp;винт&nbsp;(сила+момент)&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела.&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body:&nbsp;RigidBody3D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;wrench:&nbsp;Screw3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;in_local_frame:&nbsp;bool&nbsp;=&nbsp;True,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.body&nbsp;=&nbsp;body<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.acceleration&nbsp;=&nbsp;body.acceleration_var<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.wrench_local&nbsp;=&nbsp;wrench&nbsp;if&nbsp;in_local_frame&nbsp;else&nbsp;wrench.rotated_by(body.pose().inverse())<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([],&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;matrices[&quot;load&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_indices&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.acceleration]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[a_indices]&nbsp;+=&nbsp;self.wrench_local.to_vector_vw_order()<br>
<br>
<br>
class&nbsp;FixedRotationJoint3D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Ground-&quot;шарнир&quot;,&nbsp;фиксирующий&nbsp;линейное&nbsp;движение&nbsp;одной&nbsp;точки&nbsp;тела&nbsp;в&nbsp;мировой&nbsp;СК,<br>
&nbsp;&nbsp;&nbsp;&nbsp;но&nbsp;не&nbsp;ограничивающий&nbsp;ориентацию&nbsp;тела.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Как&nbsp;и&nbsp;в&nbsp;2D-версии:<br>
&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;всё&nbsp;формулируется&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела;<br>
&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;лямбда&nbsp;—&nbsp;линейная&nbsp;сила&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела&nbsp;(3&nbsp;компоненты).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body:&nbsp;RigidBody3D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint:&nbsp;np.ndarray&nbsp;=&nbsp;None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.body&nbsp;=&nbsp;body<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.internal_force&nbsp;=&nbsp;Variable(&quot;F_joint&quot;,&nbsp;size=3,&nbsp;tag=&quot;force&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.coords_of_joint&nbsp;=&nbsp;coords_of_joint.copy()&nbsp;if&nbsp;coords_of_joint&nbsp;is&nbsp;not&nbsp;None&nbsp;else&nbsp;pose.lin.copy()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;фиксируем&nbsp;локальные&nbsp;координаты&nbsp;точки&nbsp;шарнира&nbsp;на&nbsp;теле<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.r_local&nbsp;=&nbsp;np.asarray(pose.inverse_transform_point(self.coords_of_joint))<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([body.acceleration_var,&nbsp;self.internal_force],&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;линейная&nbsp;часть&nbsp;(Якобиан)&nbsp;—&nbsp;в&nbsp;H<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;правую&nbsp;часть&nbsp;—&nbsp;квадратичные&nbsp;(центростремительные)&nbsp;члены,&nbsp;тоже&nbsp;в&nbsp;локале<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;=&nbsp;matrices[&quot;holonomic_rhs&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_idx&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omega&nbsp;=&nbsp;np.asarray(self.body.velocity_var.value[3:6],&nbsp;dtype=float)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;центростремительное&nbsp;ускорение&nbsp;точки:&nbsp;ω&nbsp;×&nbsp;(ω&nbsp;×&nbsp;r)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bias&nbsp;=&nbsp;np.cross(omega,&nbsp;np.cross(omega,&nbsp;self.r_local))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h[F_idx]&nbsp;+=&nbsp;bias<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;radius(self)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Радиус-вектор&nbsp;точки&nbsp;шарнира&nbsp;в&nbsp;глобальной&nbsp;СК.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;pose.rotate_vector(self.r_local)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_to_holonomic_matrix(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ограничение&nbsp;в&nbsp;локале&nbsp;тела:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_lin&nbsp;+&nbsp;α×r_local&nbsp;+&nbsp;(квадр.члены)&nbsp;=&nbsp;0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;В&nbsp;матрицу&nbsp;кладём&nbsp;линейную&nbsp;часть&nbsp;по&nbsp;ускорениям:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;*&nbsp;[a_lin(3),&nbsp;α(3)]^T&nbsp;&nbsp;с&nbsp;блоком&nbsp;&nbsp;-[&nbsp;I_3,&nbsp;&nbsp;-skew(r_local)&nbsp;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;где&nbsp;α×r&nbsp;=&nbsp;-skew(r)&nbsp;α.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;holonomic&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_idx&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.body.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_idx&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;self.r_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;J&nbsp;=&nbsp;np.hstack([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;np.eye(3),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-_skew(r),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])&nbsp;&nbsp;#&nbsp;3×6<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F_idx,&nbsp;a_idx)]&nbsp;+=&nbsp;-J&nbsp;&nbsp;#&nbsp;как&nbsp;в&nbsp;2D:&nbsp;минус&nbsp;перед&nbsp;блоком<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Позиционная&nbsp;ошибка&nbsp;в&nbsp;локале&nbsp;тела:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;φ_local&nbsp;=&nbsp;R^T&nbsp;(p&nbsp;-&nbsp;c_world)&nbsp;+&nbsp;r_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;где&nbsp;p&nbsp;—&nbsp;мировая&nbsp;позиция&nbsp;опорной&nbsp;точки&nbsp;тела,&nbsp;c_world&nbsp;—&nbsp;фиксированная&nbsp;мировая&nbsp;точка&nbsp;шарнира.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr&nbsp;=&nbsp;matrices[&quot;position_error&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_idx&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;предполагается,&nbsp;что&nbsp;Pose3&nbsp;умеет&nbsp;выдавать&nbsp;матрицу&nbsp;поворота<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R&nbsp;=&nbsp;pose.rotation_matrix()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R_T&nbsp;=&nbsp;R.T<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;perr&nbsp;=&nbsp;R_T&nbsp;@&nbsp;(pose.lin&nbsp;-&nbsp;self.coords_of_joint)&nbsp;+&nbsp;self.r_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[F_idx]&nbsp;-=&nbsp;perr<br>
<br>
<br>
class&nbsp;RevoluteJoint3D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Двухтелый&nbsp;&quot;вращательный&quot;&nbsp;шарнир&nbsp;в&nbsp;духе&nbsp;2D-кода,&nbsp;но&nbsp;в&nbsp;3D:<br>
&nbsp;&nbsp;&nbsp;&nbsp;связь&nbsp;формулируется&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела&nbsp;A,&nbsp;и<br>
&nbsp;&nbsp;&nbsp;&nbsp;ограничивает&nbsp;только&nbsp;относительное&nbsp;линейное&nbsp;движение&nbsp;точки&nbsp;шарнира,<br>
&nbsp;&nbsp;&nbsp;&nbsp;ориентация&nbsp;тел&nbsp;не&nbsp;фиксируется.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyA:&nbsp;RigidBody3D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyB:&nbsp;RigidBody3D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint:&nbsp;np.ndarray&nbsp;=&nbsp;None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cW&nbsp;=&nbsp;coords_of_joint.copy()&nbsp;if&nbsp;coords_of_joint&nbsp;is&nbsp;not&nbsp;None&nbsp;else&nbsp;bodyA.pose().lin.copy()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.bodyA&nbsp;=&nbsp;bodyA<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.bodyB&nbsp;=&nbsp;bodyB<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;3-компонентная&nbsp;лямбда&nbsp;—&nbsp;сила&nbsp;в&nbsp;СК&nbsp;A<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.internal_force&nbsp;=&nbsp;Variable(&quot;F_rev&quot;,&nbsp;size=3,&nbsp;tag=&quot;force&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseA&nbsp;=&nbsp;self.bodyA.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseB&nbsp;=&nbsp;self.bodyB.pose()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;локальные&nbsp;координаты&nbsp;точки&nbsp;шарнира&nbsp;на&nbsp;каждом&nbsp;теле<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rA_local&nbsp;=&nbsp;np.asarray(poseA.inverse_transform_point(cW))&nbsp;&nbsp;#&nbsp;в&nbsp;СК&nbsp;A<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB_local&nbsp;=&nbsp;np.asarray(poseB.inverse_transform_point(cW))&nbsp;&nbsp;#&nbsp;в&nbsp;СК&nbsp;B<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;кэш&nbsp;для&nbsp;rB,&nbsp;выраженного&nbsp;в&nbsp;СК&nbsp;A,&nbsp;и&nbsp;для&nbsp;R_AB<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.R_AB&nbsp;=&nbsp;np.eye(3)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB_in_A&nbsp;=&nbsp;self.rB_local.copy()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_local_view()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([bodyA.acceleration_var,&nbsp;bodyB.acceleration_var,&nbsp;self.internal_force],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;update_local_view(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Обновить&nbsp;R_AB&nbsp;и&nbsp;rB,&nbsp;выраженные&nbsp;в&nbsp;СК&nbsp;A.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseA&nbsp;=&nbsp;self.bodyA.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseB&nbsp;=&nbsp;self.bodyB.pose()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R_A&nbsp;=&nbsp;poseA.rotation_matrix()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R_B&nbsp;=&nbsp;poseB.rotation_matrix()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.R_AB&nbsp;=&nbsp;R_A.T&nbsp;@&nbsp;R_B<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB_in_A&nbsp;=&nbsp;self.R_AB&nbsp;@&nbsp;self.rB_local<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_local_view()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;=&nbsp;matrices[&quot;holonomic_rhs&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omegaA&nbsp;=&nbsp;np.asarray(self.bodyA.velocity_var.value[3:6],&nbsp;dtype=float)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omegaB&nbsp;=&nbsp;np.asarray(self.bodyB.velocity_var.value[3:6],&nbsp;dtype=float)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;квадратичные&nbsp;члены&nbsp;(центростремительные),&nbsp;всё&nbsp;в&nbsp;СК&nbsp;A:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;biasA&nbsp;вычисляется&nbsp;в&nbsp;СК&nbsp;A&nbsp;(omegaA&nbsp;и&nbsp;rA_local&nbsp;оба&nbsp;в&nbsp;СК&nbsp;A)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;biasB&nbsp;вычисляется&nbsp;в&nbsp;СК&nbsp;B,&nbsp;затем&nbsp;преобразуется&nbsp;в&nbsp;СК&nbsp;A<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rA&nbsp;=&nbsp;self.rA_local<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;biasA&nbsp;=&nbsp;np.cross(omegaA,&nbsp;np.cross(omegaA,&nbsp;rA))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Центростремительное&nbsp;ускорение&nbsp;B&nbsp;в&nbsp;его&nbsp;локальной&nbsp;СК,&nbsp;затем&nbsp;в&nbsp;СК&nbsp;A<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;biasB_in_B&nbsp;=&nbsp;np.cross(omegaB,&nbsp;np.cross(omegaB,&nbsp;self.rB_local))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;biasB&nbsp;=&nbsp;self.R_AB&nbsp;@&nbsp;biasB_in_B<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bias&nbsp;=&nbsp;biasA&nbsp;-&nbsp;biasB<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;по&nbsp;принятой&nbsp;конвенции&nbsp;—&nbsp;добавляем&nbsp;-bias<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h[F]&nbsp;+=&nbsp;-bias<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_to_holonomic_matrix(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;В&nbsp;СК&nbsp;A:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;aA_lin&nbsp;+&nbsp;αA×rA&nbsp;&nbsp;-&nbsp;&nbsp;R_AB&nbsp;(aB_lin&nbsp;+&nbsp;αB×rB)&nbsp;&nbsp;+&nbsp;квадр.члены&nbsp;=&nbsp;0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Линейная&nbsp;часть&nbsp;по&nbsp;ускорениям:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;*&nbsp;[aA_lin(3),&nbsp;αA(3),&nbsp;aB_lin(3),&nbsp;αB(3)]^T<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;holonomic&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;aA&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.bodyA.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;aB&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.bodyB.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]&nbsp;&nbsp;#&nbsp;3&nbsp;строки<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rA&nbsp;=&nbsp;self.rA_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R&nbsp;=&nbsp;self.R_AB<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;блок&nbsp;по&nbsp;aA&nbsp;(в&nbsp;СК&nbsp;A):&nbsp;[&nbsp;I,&nbsp;-skew(rA)&nbsp;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;J_A&nbsp;=&nbsp;np.hstack([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;np.eye(3),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-_skew(rA),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])&nbsp;&nbsp;#&nbsp;3×6<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;aA)]&nbsp;+=&nbsp;J_A<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;блок&nbsp;по&nbsp;aB,&nbsp;выраженный&nbsp;в&nbsp;СК&nbsp;A:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;-&nbsp;R_AB&nbsp;(aB_lin&nbsp;+&nbsp;αB×rB)&nbsp;=<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;&nbsp;&nbsp;[&nbsp;-R_AB,&nbsp;&nbsp;R_AB&nbsp;*&nbsp;skew(rB_local)&nbsp;]&nbsp;*&nbsp;[aB_lin,&nbsp;αB]^T<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;S_rB&nbsp;=&nbsp;_skew(self.rB_local)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;col_alphaB&nbsp;=&nbsp;R&nbsp;@&nbsp;S_rB&nbsp;&nbsp;#&nbsp;3×3<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;J_B&nbsp;=&nbsp;np.hstack([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-R,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;col_alphaB,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])&nbsp;&nbsp;#&nbsp;3×6<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;aB)]&nbsp;+=&nbsp;J_B<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Позиционная&nbsp;ошибка&nbsp;в&nbsp;СК&nbsp;A:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;φ_A&nbsp;=&nbsp;R_A^T&nbsp;[&nbsp;(pA&nbsp;+&nbsp;R_A&nbsp;rA)&nbsp;-&nbsp;(pB&nbsp;+&nbsp;R_B&nbsp;rB)&nbsp;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;=&nbsp;R_A^T&nbsp;(pA&nbsp;-&nbsp;pB)&nbsp;+&nbsp;rA&nbsp;-&nbsp;R_AB&nbsp;rB<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_local_view()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr&nbsp;=&nbsp;matrices[&quot;position_error&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pA&nbsp;=&nbsp;self.bodyA.pose().lin<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pB&nbsp;=&nbsp;self.bodyB.pose().lin<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseA&nbsp;=&nbsp;self.bodyA.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R_A&nbsp;=&nbsp;poseA.rotation_matrix()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R_A_T&nbsp;=&nbsp;R_A.T<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;delta_p_A&nbsp;=&nbsp;R_A_T&nbsp;@&nbsp;(pA&nbsp;-&nbsp;pB)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rA&nbsp;=&nbsp;self.rA_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rB_A&nbsp;=&nbsp;self.rB_in_A<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[F]&nbsp;+=&nbsp;delta_p_A&nbsp;+&nbsp;rA&nbsp;-&nbsp;rB_A<br>
<!-- END SCAT CODE -->
</body>
</html>
