<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody2d_3.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Соглашение&nbsp;о&nbsp;уравнениях&nbsp;такого,&nbsp;что&nbsp;все&nbsp;уравнения&nbsp;собираются&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела.<br>
Глобальная&nbsp;поза&nbsp;тела&nbsp;хранится&nbsp;отдельно&nbsp;и&nbsp;используется&nbsp;только&nbsp;для&nbsp;обновления&nbsp;геометрии.<br>
<br>
Преобразования&nbsp;следуют&nbsp;конвенции&nbsp;локальная&nbsp;система&nbsp;-&gt;&nbsp;мировая&nbsp;система:<br>
&nbsp;&nbsp;&nbsp;&nbsp;p_world&nbsp;=&nbsp;P(q)&nbsp;@&nbsp;p_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;p_world&nbsp;=&nbsp;R(θ)&nbsp;@&nbsp;p_local<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;typing&nbsp;import&nbsp;List,&nbsp;Dict<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
from&nbsp;termin.fem.assembler&nbsp;import&nbsp;Variable,&nbsp;Contribution<br>
from&nbsp;termin.geombase.pose2&nbsp;import&nbsp;Pose2<br>
from&nbsp;termin.geombase.screw&nbsp;import&nbsp;Screw2<br>
from&nbsp;termin.fem.inertia2d&nbsp;import&nbsp;SpatialInertia2D<br>
<br>
<br>
class&nbsp;RigidBody2D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Твёрдое&nbsp;тело&nbsp;в&nbsp;2D,&nbsp;все&nbsp;расчёты&nbsp;выполняются&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Глобальная&nbsp;поза&nbsp;хранится&nbsp;отдельно&nbsp;и&nbsp;используется&nbsp;только&nbsp;для&nbsp;обновления&nbsp;геометрии.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia:&nbsp;SpatialInertia2D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity:&nbsp;np.ndarray&nbsp;=&nbsp;None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name=&quot;rbody2d&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;angle_normalize:&nbsp;callable&nbsp;=&nbsp;None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.acceleration_var&nbsp;=&nbsp;Variable(name&nbsp;+&nbsp;&quot;_acc&quot;,&nbsp;size=3,&nbsp;tag=&quot;acceleration&quot;)&nbsp;&nbsp;#&nbsp;[ax,&nbsp;ay,&nbsp;α]_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.velocity_var&nbsp;=&nbsp;Variable(name&nbsp;+&nbsp;&quot;_vel&quot;,&nbsp;size=3,&nbsp;tag=&quot;velocity&quot;)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;[vx,&nbsp;vy,&nbsp;ω]_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.local_pose_var&nbsp;=&nbsp;Variable(name&nbsp;+&nbsp;&quot;_pos&quot;,&nbsp;size=3,&nbsp;tag=&quot;position&quot;)&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;[x,&nbsp;y,&nbsp;θ]_local&nbsp;(для&nbsp;интеграции&nbsp;лок.&nbsp;движения)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;глобальная&nbsp;поза&nbsp;тела&nbsp;(Pose2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose&nbsp;=&nbsp;Pose2(lin=np.zeros(2),&nbsp;ang=0.0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.inertia&nbsp;=&nbsp;inertia<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.angle_normalize&nbsp;=&nbsp;angle_normalize<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;сила&nbsp;тяжести&nbsp;задаётся&nbsp;в&nbsp;мировых&nbsp;координатах<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.gravity&nbsp;=&nbsp;np.array([0.0,&nbsp;-9.81])&nbsp;if&nbsp;gravity&nbsp;is&nbsp;None&nbsp;else&nbsp;np.asarray(gravity,&nbsp;float).reshape(2)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([self.acceleration_var,&nbsp;self.velocity_var,&nbsp;self.local_pose_var],&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;----------&nbsp;геттеры&nbsp;----------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;pose(self)&nbsp;-&gt;&nbsp;Pose2:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.global_pose<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;set_pose(self,&nbsp;pose:&nbsp;Pose2):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose&nbsp;=&nbsp;pose<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;----------&nbsp;вклад&nbsp;в&nbsp;систему&nbsp;----------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Вклад&nbsp;тела&nbsp;в&nbsp;уравнения&nbsp;движения:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;I&nbsp;*&nbsp;a&nbsp;+&nbsp;v×*&nbsp;(I&nbsp;v)&nbsp;=&nbsp;F<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Все&nbsp;в&nbsp;локальной&nbsp;СК.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_mass_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;matrices[&quot;load&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_idx&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_local&nbsp;=&nbsp;Screw2.from_vector_vw_order(self.velocity_var.value)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bias&nbsp;=&nbsp;self.inertia.bias_wrench(v_local)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;гравитация&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;g_local&nbsp;=&nbsp;self.global_pose.inverse().rotate_vector(self.gravity)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;grav&nbsp;=&nbsp;self.inertia.gravity_wrench(g_local)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[a_idx]&nbsp;+=&nbsp;bias.to_vector_vw_order()&nbsp;+&nbsp;grav.to_vector_vw_order()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_mass_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_to_mass_matrix(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Массовая&nbsp;матрица&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;(никаких&nbsp;поворотов).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;matrices[&quot;mass&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_idx&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A[np.ix_(a_idx,&nbsp;a_idx)]&nbsp;+=&nbsp;self.inertia.to_matrix_vw_order()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;----------&nbsp;интеграция&nbsp;шага&nbsp;----------<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;finish_timestep(self,&nbsp;dt):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;После&nbsp;интеграции&nbsp;уравнений&nbsp;ускорений&nbsp;и&nbsp;скоростей&nbsp;обновляем&nbsp;локальные&nbsp;переменные,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;затем&nbsp;обновляем&nbsp;глобальную&nbsp;позу,&nbsp;используя&nbsp;локальное&nbsp;смещение.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;После&nbsp;этого&nbsp;локальная&nbsp;поза&nbsp;обнуляется&nbsp;(тело&nbsp;возвращается&nbsp;в&nbsp;свою&nbsp;СК).<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;=&nbsp;self.velocity_var.value<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a&nbsp;=&nbsp;self.acceleration_var.value<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;+=&nbsp;a&nbsp;*&nbsp;dt<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.velocity_var.value&nbsp;=&nbsp;v<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;локальное&nbsp;приращение&nbsp;позы&nbsp;(интеграция&nbsp;по&nbsp;локальной&nbsp;СК)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;delta_pose_local&nbsp;=&nbsp;Pose2(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lin=v[0:2]&nbsp;*&nbsp;dt,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ang=v[2]&nbsp;*&nbsp;dt,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;обновляем&nbsp;глобальную&nbsp;позу&nbsp;тела<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose&nbsp;=&nbsp;self.global_pose&nbsp;@&nbsp;delta_pose_local<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;сбрасываем&nbsp;локальную&nbsp;позу<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.local_pose_var.value[:]&nbsp;=&nbsp;0.0<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.angle_normalize&nbsp;is&nbsp;not&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose.ang&nbsp;=&nbsp;self.angle_normalize(self.global_pose.ang)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;finish_correction_step(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;После&nbsp;коррекции&nbsp;позиций&nbsp;сбрасываем&nbsp;локальную&nbsp;позу.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.global_pose&nbsp;=&nbsp;self.global_pose&nbsp;@&nbsp;Pose2(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lin=self.local_pose_var.value[0:2],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ang=self.local_pose_var.value[2],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.local_pose_var.value[:]&nbsp;=&nbsp;0.0<br>
<br>
class&nbsp;ForceOnBody2D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Внешняя&nbsp;сила&nbsp;и&nbsp;момент&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;body:&nbsp;RigidBody2D,&nbsp;wrench:&nbsp;Screw2,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;in_local_frame:&nbsp;bool&nbsp;=&nbsp;True,&nbsp;assembler=None):<br>
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
class&nbsp;FixedRotationJoint2D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Ground&nbsp;revolute&nbsp;joint.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Все&nbsp;уравнения&nbsp;формулируются&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Лямбда&nbsp;—&nbsp;сила,&nbsp;действующая&nbsp;на&nbsp;тело,&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body:&nbsp;RigidBody2D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint:&nbsp;np.ndarray&nbsp;=&nbsp;None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.body&nbsp;=&nbsp;body<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.internal_force&nbsp;=&nbsp;Variable(&quot;F_joint&quot;,&nbsp;size=2,&nbsp;tag=&quot;force&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.coords_of_joint&nbsp;=&nbsp;coords_of_joint.copy()&nbsp;if&nbsp;coords_of_joint&nbsp;is&nbsp;not&nbsp;None&nbsp;else&nbsp;pose.lin.copy()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;фиксируем&nbsp;локальные&nbsp;координаты&nbsp;точки&nbsp;шарнира&nbsp;на&nbsp;теле<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.r_local&nbsp;=&nbsp;pose.inverse_transform_point(self.coords_of_joint)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([body.acceleration_var,&nbsp;self.internal_force],&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;линейная&nbsp;часть&nbsp;(Якобиан)&nbsp;—&nbsp;сразу&nbsp;в&nbsp;H<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;правую&nbsp;часть&nbsp;—&nbsp;квадратичные&nbsp;(центростремительные)&nbsp;члены,&nbsp;тоже&nbsp;в&nbsp;локале<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;=&nbsp;matrices[&quot;holonomic_rhs&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_idx&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omega&nbsp;=&nbsp;float(self.body.velocity_var.value[2])<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bias&nbsp;=&nbsp;-&nbsp;(omega&nbsp;**&nbsp;2)&nbsp;*&nbsp;self.r_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h[F_idx]&nbsp;+=&nbsp;bias<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;radius(self)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Радиус&nbsp;шарнира&nbsp;в&nbsp;глобальной&nbsp;СК.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r_world&nbsp;=&nbsp;pose.rotate_vector(self.r_local)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;r_world<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_to_holonomic_matrix(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ограничение&nbsp;в&nbsp;локале&nbsp;тела:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_lin&nbsp;+&nbsp;α×r_local&nbsp;+&nbsp;(квадр.члены)&nbsp;=&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;В&nbsp;матрицу&nbsp;кладём&nbsp;линейную&nbsp;часть&nbsp;по&nbsp;ускорениям:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;*&nbsp;[a_x,&nbsp;a_y,&nbsp;α]^T&nbsp;&nbsp;с&nbsp;блоком&nbsp;&nbsp;-[&nbsp;I,&nbsp;&nbsp;perp(r_local)&nbsp;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;где&nbsp;perp(r)&nbsp;=&nbsp;[-r_y,&nbsp;r_x].<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;holonomic&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_idx&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.body.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_idx&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;r&nbsp;=&nbsp;self.r_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F_idx,&nbsp;a_idx)]&nbsp;+=&nbsp;-np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[1.0,&nbsp;0.0,&nbsp;-r[1]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[0.0,&nbsp;1.0,&nbsp;&nbsp;r[0]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Позиционная&nbsp;ошибка&nbsp;тоже&nbsp;в&nbsp;локале&nbsp;тела:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;φ_local&nbsp;=&nbsp;R^T&nbsp;(p&nbsp;-&nbsp;c_world)&nbsp;+&nbsp;r_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;где&nbsp;p&nbsp;—&nbsp;мировая&nbsp;позиция&nbsp;опорной&nbsp;точки&nbsp;тела,&nbsp;c_world&nbsp;—&nbsp;фиксированная&nbsp;мировая&nbsp;точка&nbsp;шарнира.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Якобиан&nbsp;для&nbsp;коррекции&nbsp;такой&nbsp;же<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr&nbsp;=&nbsp;matrices[&quot;position_error&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_idx&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.body.pose()&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;perr&nbsp;=&nbsp;pose.inverse_rotate_vector(pose.lin&nbsp;-&nbsp;self.coords_of_joint)&nbsp;&nbsp;+&nbsp;self.r_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[F_idx]&nbsp;-=&nbsp;perr<br>
<br>
<br>
class&nbsp;RevoluteJoint2D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Двухтелый&nbsp;вращательный&nbsp;шарнир&nbsp;(revolute&nbsp;joint):<br>
&nbsp;&nbsp;&nbsp;&nbsp;связь&nbsp;формулируется&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела&nbsp;A.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyA:&nbsp;RigidBody2D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyB:&nbsp;RigidBody2D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint:&nbsp;np.ndarray&nbsp;=&nbsp;None,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cW&nbsp;=&nbsp;coords_of_joint.copy()&nbsp;if&nbsp;coords_of_joint&nbsp;is&nbsp;not&nbsp;None&nbsp;else&nbsp;bodyA.pose().lin.copy()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.bodyA&nbsp;=&nbsp;bodyA<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.bodyB&nbsp;=&nbsp;bodyB<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;2-компонентная&nbsp;лямбда&nbsp;силы&nbsp;в&nbsp;СК&nbsp;A<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.internal_force&nbsp;=&nbsp;Variable(&quot;F_rev&quot;,&nbsp;size=2,&nbsp;tag=&quot;force&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseA&nbsp;=&nbsp;self.bodyA.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseB&nbsp;=&nbsp;self.bodyB.pose()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;локальные&nbsp;координаты&nbsp;точки&nbsp;шарнира&nbsp;на&nbsp;каждом&nbsp;теле<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rA_local&nbsp;=&nbsp;poseA.inverse_transform_point(cW)&nbsp;&nbsp;#&nbsp;в&nbsp;СК&nbsp;A<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB_local&nbsp;=&nbsp;poseB.inverse_transform_point(cW)&nbsp;&nbsp;#&nbsp;в&nbsp;СК&nbsp;B<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;кэш&nbsp;для&nbsp;rB,&nbsp;выраженного&nbsp;в&nbsp;СК&nbsp;A,&nbsp;и&nbsp;для&nbsp;R_AB<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#self.R_AB&nbsp;=&nbsp;np.eye(2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.poseAB&nbsp;=&nbsp;Pose2.identity()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB_in_A&nbsp;=&nbsp;self.rB_local.copy()&nbsp;&nbsp;#&nbsp;будет&nbsp;обновляться<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_local_view()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([bodyA.acceleration_var,&nbsp;bodyB.acceleration_var,&nbsp;self.internal_force],&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;@staticmethod<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;_perp_col(r:&nbsp;np.ndarray)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;перпендикуляр&nbsp;к&nbsp;r:&nbsp;α×r&nbsp;=&nbsp;[&nbsp;-α&nbsp;r_y,&nbsp;α&nbsp;r_x&nbsp;]&nbsp;⇒&nbsp;столбец&nbsp;для&nbsp;α&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.array([-r[1],&nbsp;r[0]])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;update_local_view(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Обновить&nbsp;R_AB&nbsp;и&nbsp;rB,&nbsp;выраженные&nbsp;в&nbsp;СК&nbsp;A.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseA&nbsp;=&nbsp;self.bodyA.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseB&nbsp;=&nbsp;self.bodyB.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#cA,&nbsp;sA&nbsp;=&nbsp;np.cos(poseA.ang),&nbsp;np.sin(poseA.ang)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#cB,&nbsp;sB&nbsp;=&nbsp;np.cos(poseB.ang),&nbsp;np.sin(poseB.ang)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#R_A&nbsp;=&nbsp;np.array([[cA,&nbsp;-sA],[sA,&nbsp;cA]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#R_B&nbsp;=&nbsp;np.array([[cB,&nbsp;-sB],[sB,&nbsp;cB]])<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#self.R_AB&nbsp;=&nbsp;R_A.T&nbsp;@&nbsp;R_B<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.poseAB&nbsp;=&nbsp;poseA.inverse()&nbsp;@&nbsp;poseB<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB_in_A&nbsp;=&nbsp;self.poseAB.rotate_vector(self.rB_local)&nbsp;&nbsp;#&nbsp;r_B,&nbsp;выраженный&nbsp;в&nbsp;СК&nbsp;A<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_local_view()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;=&nbsp;matrices[&quot;holonomic_rhs&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omegaA&nbsp;=&nbsp;float(self.bodyA.velocity_var.value[2])<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omegaB&nbsp;=&nbsp;float(self.bodyB.velocity_var.value[2])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;квадратичные&nbsp;члены&nbsp;(центростремительные)&nbsp;в&nbsp;правую&nbsp;часть,&nbsp;всё&nbsp;в&nbsp;СК&nbsp;A:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;bias&nbsp;=&nbsp;(ωA^2)&nbsp;*&nbsp;rA&nbsp;&nbsp;-&nbsp;(ωB^2)&nbsp;*&nbsp;(R_AB&nbsp;rB)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rA&nbsp;=&nbsp;self.rA_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rB_A&nbsp;=&nbsp;self.rB_in_A<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bias&nbsp;=&nbsp;(omegaA**2)&nbsp;*&nbsp;rA&nbsp;-&nbsp;(omegaB**2)&nbsp;*&nbsp;rB_A<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;по&nbsp;принятой&nbsp;конвенции&nbsp;—&nbsp;добавляем&nbsp;-bias<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h[F]&nbsp;+=&nbsp;-bias<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_to_holonomic_matrix(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;В&nbsp;СК&nbsp;A:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;aA_lin&nbsp;+&nbsp;αA×rA&nbsp;&nbsp;-&nbsp;&nbsp;R_AB&nbsp;(aB_lin&nbsp;+&nbsp;αB×rB)&nbsp;&nbsp;+&nbsp;квадр.члены&nbsp;=&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Линейная&nbsp;часть&nbsp;по&nbsp;ускорениям&nbsp;попадает&nbsp;в&nbsp;матрицу&nbsp;H.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;holonomic&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;aA&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.bodyA.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;aB&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.bodyB.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]&nbsp;&nbsp;#&nbsp;2&nbsp;строки<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rA&nbsp;=&nbsp;self.rA_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rB_A&nbsp;=&nbsp;self.rB_in_A<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R&nbsp;=&nbsp;self.poseAB.rotation_matrix()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;блок&nbsp;по&nbsp;aA&nbsp;(в&nbsp;СК&nbsp;A)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;aA)]&nbsp;+=&nbsp;np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;1.0,&nbsp;&nbsp;0.0,&nbsp;-rA[1]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;0.0,&nbsp;&nbsp;1.0,&nbsp;&nbsp;rA[0]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;блок&nbsp;по&nbsp;aB,&nbsp;выраженный&nbsp;в&nbsp;СК&nbsp;A:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;-&nbsp;[&nbsp;R,&nbsp;&nbsp;R&nbsp;*&nbsp;perp(rB)&nbsp;],&nbsp;где&nbsp;perp(r)&nbsp;=&nbsp;[-r_y,&nbsp;r_x]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;col_alphaB&nbsp;=&nbsp;self.poseAB.rotate_vector(self._perp_col(self.rB_local))&nbsp;&nbsp;#&nbsp;=&nbsp;perp(rB_A)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;aB)]&nbsp;+=&nbsp;np.array([<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[-R[0,0],&nbsp;-R[0,1],&nbsp;&nbsp;col_alphaB[0]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[-R[1,0],&nbsp;-R[1,1],&nbsp;&nbsp;col_alphaB[1]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Позиционная&nbsp;ошибка&nbsp;тоже&nbsp;в&nbsp;СК&nbsp;A:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;φ_A&nbsp;=&nbsp;R_A^T&nbsp;*&nbsp;[&nbsp;(pA&nbsp;+&nbsp;R_A&nbsp;rA)&nbsp;-&nbsp;(pB&nbsp;+&nbsp;R_B&nbsp;rB)&nbsp;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;=&nbsp;(R_A^T(pA&nbsp;-&nbsp;pB))&nbsp;+&nbsp;rA&nbsp;-&nbsp;R_AB&nbsp;rB<br>
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
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;R_A_T&nbsp;=&nbsp;poseA.inverse().rotation_matrix()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;delta_p_A&nbsp;=&nbsp;R_A_T&nbsp;@&nbsp;(pA&nbsp;-&nbsp;pB)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rA&nbsp;=&nbsp;self.rA_local<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rB_A&nbsp;=&nbsp;self.rB_in_A<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[F]&nbsp;+=&nbsp;delta_p_A&nbsp;+&nbsp;rA&nbsp;-&nbsp;rB_A<br>
<!-- END SCAT CODE -->
</body>
</html>
