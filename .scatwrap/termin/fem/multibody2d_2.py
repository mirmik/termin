<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody2d_2.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#&nbsp;&quot;&quot;&quot;<br>
#&nbsp;Вторая&nbsp;версия&nbsp;модели&nbsp;многотельной&nbsp;системы&nbsp;в&nbsp;2D<br>
#&nbsp;&quot;&quot;&quot;<br>
<br>
<br>
#&nbsp;from&nbsp;typing&nbsp;import&nbsp;List,&nbsp;Dict<br>
#&nbsp;import&nbsp;numpy&nbsp;as&nbsp;np<br>
#&nbsp;from&nbsp;termin.fem.assembler&nbsp;import&nbsp;Variable,&nbsp;Contribution<br>
#&nbsp;from&nbsp;termin.geombase.pose2&nbsp;import&nbsp;Pose2<br>
#&nbsp;from&nbsp;termin.geombase.screw&nbsp;import&nbsp;Screw2<br>
#&nbsp;from&nbsp;termin.fem.inertia2d&nbsp;import&nbsp;SpatialInertia2D<br>
<br>
<br>
#&nbsp;class&nbsp;RigidBody2D(Contribution):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Твердое&nbsp;тело&nbsp;в&nbsp;плоскости&nbsp;(3&nbsp;СС:&nbsp;x,&nbsp;y,&nbsp;θ).<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Поддерживает&nbsp;внецентренную&nbsp;инерцию&nbsp;(смещённый&nbsp;ЦМ).<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;inertia:&nbsp;SpatialInertia2D,&nbsp;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity:&nbsp;np.ndarray&nbsp;=&nbsp;None,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None,&nbsp;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name=&quot;rbody2d&quot;,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;angle_normalize:&nbsp;callable&nbsp;=&nbsp;None<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.acceleration_var&nbsp;=&nbsp;Variable(<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name&nbsp;+&nbsp;&quot;_acc&quot;,&nbsp;size=3,&nbsp;tag=&quot;acceleration&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)&nbsp;&nbsp;#&nbsp;[ax,&nbsp;ay,&nbsp;α]&nbsp;в&nbsp;глобальной&nbsp;СК<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.velocity_var&nbsp;=&nbsp;Variable(<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name&nbsp;+&nbsp;&quot;_vel&quot;,&nbsp;size=3,&nbsp;tag=&quot;velocity&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)&nbsp;&nbsp;#&nbsp;[vx,&nbsp;vy,&nbsp;ω]&nbsp;в&nbsp;глобальной&nbsp;СК<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pose_var&nbsp;=&nbsp;Variable(<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name&nbsp;+&nbsp;&quot;_pos&quot;,&nbsp;size=3,&nbsp;tag=&quot;position&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)&nbsp;&nbsp;#&nbsp;[x,&nbsp;y,&nbsp;θ]&nbsp;в&nbsp;глобальной&nbsp;СК<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.inertia&nbsp;=&nbsp;inertia<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.gravity&nbsp;=&nbsp;(<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;np.array([0.0,&nbsp;-9.81])&nbsp;if&nbsp;gravity&nbsp;is&nbsp;None&nbsp;else&nbsp;np.asarray(gravity,&nbsp;float).reshape(2)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[self.acceleration_var,&nbsp;self.velocity_var,&nbsp;self.pose_var],&nbsp;assembler=assembler<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.angle_normalize&nbsp;=&nbsp;angle_normalize<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;pose(self):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Pose2(<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;lin=self.pose_var.value[0:2].copy(),<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ang=float(self.pose_var.value[2].copy())<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;----------&nbsp;ВКЛАД&nbsp;В&nbsp;СИСТЕМУ&nbsp;----------<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_mass_matrix(matrices,&nbsp;index_maps)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Гравитация&nbsp;в&nbsp;глобальной&nbsp;СК<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_idx&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;matrices[&quot;load&quot;]<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;1)&nbsp;Инерционный&nbsp;скоростной&nbsp;bias,&nbsp;она&nbsp;же&nbsp;сила&nbsp;Кориолиса:&nbsp;v×*&nbsp;(I&nbsp;v)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;=&nbsp;self.velocity_var.value<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;velscr&nbsp;=&nbsp;Screw2(lin=v[0:2],&nbsp;ang=v[2])<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;velscr_local&nbsp;=&nbsp;velscr.rotated_by(self.pose().inverse())<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bias_wrench&nbsp;=&nbsp;self.inertia.bias_wrench(velscr_local)&nbsp;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bw_world&nbsp;=&nbsp;bias_wrench.rotated_by(self.pose())<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[a_idx]&nbsp;+=&nbsp;bw_world.to_vector_vw_order()<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;2)&nbsp;Гравитационная&nbsp;сила<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity_local&nbsp;=&nbsp;self.pose().inverse().rotate_vector(self.gravity)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gr_wrench_local&nbsp;=&nbsp;self.inertia.gravity_wrench(gravity_local).to_vector_vw_order()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gr_wrench_world&nbsp;=&nbsp;Screw2.from_vector_vw_order(gr_wrench_local).rotated_by(self.pose())<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[a_idx]&nbsp;+=&nbsp;gr_wrench_world.to_vector_vw_order()<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_mass_matrix(matrices,&nbsp;index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_to_mass_matrix(self,&nbsp;matrices,&nbsp;index_maps):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;matrices[&quot;mass&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;amap&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_idx&nbsp;=&nbsp;amap[self.acceleration_var]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;IM&nbsp;=&nbsp;self.inertia.to_matrix_vw_order()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A[np.ix_(a_idx,&nbsp;a_idx)]&nbsp;+=&nbsp;IM<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;finish_timestep(self,&nbsp;dt):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;semimplicit&nbsp;Euler<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;=&nbsp;self.velocity_var.value<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a&nbsp;=&nbsp;self.acceleration_var.value<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;+=&nbsp;a&nbsp;*&nbsp;dt<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.velocity_var.value&nbsp;=&nbsp;v<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pose_var.value&nbsp;+=&nbsp;v&nbsp;*&nbsp;dt<br>
<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.angle_normalize&nbsp;is&nbsp;not&nbsp;None:<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pose_var.value[2]&nbsp;=&nbsp;self.angle_normalize(self.pose_var.value[2])<br>
<br>
<br>
#&nbsp;class&nbsp;ForceOnBody2D(Contribution):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Внешняя&nbsp;сила&nbsp;и&nbsp;момент,&nbsp;приложенные&nbsp;к&nbsp;твердому&nbsp;телу&nbsp;в&nbsp;2D.<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;body:&nbsp;RigidBody2D,&nbsp;wrench:&nbsp;Screw2,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;in_local_frame:&nbsp;bool&nbsp;=&nbsp;False,&nbsp;assembler=None):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;wrench:&nbsp;Screw2&nbsp;—&nbsp;сила&nbsp;и&nbsp;момент<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;in_local_frame:&nbsp;если&nbsp;True,&nbsp;сила&nbsp;задана&nbsp;в&nbsp;локальной&nbsp;СК&nbsp;тела<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.body&nbsp;=&nbsp;body<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.acceleration&nbsp;=&nbsp;body.acceleration_var<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.wrench&nbsp;=&nbsp;wrench<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.in_local_frame&nbsp;=&nbsp;in_local_frame<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([],&nbsp;assembler=assembler)&nbsp;&nbsp;#&nbsp;Нет&nbsp;переменных&nbsp;для&nbsp;этой&nbsp;нагрузки<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Добавить&nbsp;вклад&nbsp;в&nbsp;вектор&nbsp;нагрузок<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;matrices[&quot;load&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_map&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_indices&nbsp;=&nbsp;index_map[self.acceleration]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;wrench&nbsp;=&nbsp;self.wrench.rotated_by(self.body.pose())&nbsp;if&nbsp;self.in_local_frame&nbsp;else&nbsp;self.wrench<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[a_indices[0]]&nbsp;+=&nbsp;wrench.lin[0]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[a_indices[1]]&nbsp;+=&nbsp;wrench.lin[1]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[a_indices[2]]&nbsp;+=&nbsp;wrench.ang<br>
<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Внешние&nbsp;силы&nbsp;не&nbsp;влияют&nbsp;на&nbsp;коррекцию&nbsp;ограничений&nbsp;на&nbsp;положения<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pass<br>
<br>
<br>
#&nbsp;class&nbsp;FixedRotationJoint2D(Contribution):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Вращательный&nbsp;шарнир&nbsp;с&nbsp;фиксацией&nbsp;в&nbsp;пространстве&nbsp;(ground&nbsp;revolute&nbsp;joint).<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Фиксирует&nbsp;точку&nbsp;на&nbsp;теле&nbsp;в&nbsp;пространстве,&nbsp;разрешая&nbsp;только&nbsp;вращение&nbsp;вокруг&nbsp;этой&nbsp;точки.<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Эквивалентно&nbsp;присоединению&nbsp;тела&nbsp;к&nbsp;неподвижному&nbsp;основанию&nbsp;через&nbsp;шарнир.<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Соглашение&nbsp;о&nbsp;знаках:&nbsp;Лямбда&nbsp;задаёт&nbsp;силу&nbsp;действующую&nbsp;на&nbsp;тело&nbsp;со&nbsp;стороны&nbsp;шарнира.<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body:&nbsp;RigidBody2D,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint:&nbsp;np.ndarray&nbsp;=&nbsp;None,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body:&nbsp;Твердое&nbsp;тело,&nbsp;к&nbsp;которому&nbsp;применяется&nbsp;шарнир<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint:&nbsp;Вектор&nbsp;координат&nbsp;шарнира&nbsp;[x,&nbsp;y]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler:&nbsp;Ассемблер&nbsp;для&nbsp;сборки&nbsp;системы<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.body&nbsp;=&nbsp;body<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.internal_force&nbsp;=&nbsp;Variable(&quot;F_joint&quot;,&nbsp;size=2,&nbsp;tag=&quot;force&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body_pose&nbsp;=&nbsp;self.body.pose()<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.coords_of_joint&nbsp;=&nbsp;coords_of_joint.copy()&nbsp;if&nbsp;coords_of_joint&nbsp;is&nbsp;not&nbsp;None&nbsp;else&nbsp;body_pose.lin.copy()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.radius_in_local&nbsp;=&nbsp;body_pose.inverse_transform_point(self.coords_of_joint)<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([body.acceleration_var,&nbsp;self.internal_force],&nbsp;assembler=assembler)<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;radius(self):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Обновить&nbsp;радиус&nbsp;до&nbsp;тела&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body_pose&nbsp;=&nbsp;self.body.pose()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;body_pose.rotate_vector(self.radius_in_local)&nbsp;#&nbsp;тут&nbsp;достаточно&nbsp;повернуть<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Добавить&nbsp;вклад&nbsp;в&nbsp;матрицы<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;radius&nbsp;=&nbsp;self.radius()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omega&nbsp;=&nbsp;self.body.velocity_var.value[2]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;=&nbsp;matrices[&quot;holonomic_rhs&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;constraints_map&nbsp;=&nbsp;index_maps[&quot;force&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_indices&nbsp;=&nbsp;constraints_map[self.internal_force]<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bias&nbsp;=&nbsp;-&nbsp;(omega**2)&nbsp;*&nbsp;radius<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h[F_indices[0]]&nbsp;+=&nbsp;bias[0]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h[F_indices[1]]&nbsp;+=&nbsp;bias[1]<br>
<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_to_holonomic_matrix(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Добавить&nbsp;вклад&nbsp;в&nbsp;матрицы&nbsp;ограничений&nbsp;на&nbsp;положения<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;radius&nbsp;=&nbsp;self.radius()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;holonomic&quot;]&nbsp;&nbsp;#&nbsp;Матрица&nbsp;ограничений<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;index_map&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;constraint_map&nbsp;=&nbsp;index_maps[&quot;force&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_indices&nbsp;=&nbsp;constraint_map[self.internal_force]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;a_indices&nbsp;=&nbsp;index_map[self.body.acceleration_var]<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Вклад&nbsp;в&nbsp;матрицу&nbsp;ограничений&nbsp;от&nbsp;связи&nbsp;шарнира<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F_indices,&nbsp;a_indices)]&nbsp;+=&nbsp;-&nbsp;np.array([<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[1.0,&nbsp;0.0,&nbsp;-radius[1]],<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[0.0,&nbsp;1.0,&nbsp;&nbsp;radius[0]]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Добавить&nbsp;вклад&nbsp;в&nbsp;матрицы&nbsp;для&nbsp;коррекции&nbsp;ограничений&nbsp;на&nbsp;положения<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;radius&nbsp;=&nbsp;self.radius()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;constraint_map&nbsp;=&nbsp;index_maps[&quot;force&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr&nbsp;=&nbsp;matrices[&quot;position_error&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_indices&nbsp;=&nbsp;constraint_map[self.internal_force]<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[F_indices]&nbsp;+=&nbsp;(self.body.pose().lin&nbsp;+&nbsp;radius)&nbsp;-&nbsp;self.coords_of_joint<br>
<br>
#&nbsp;class&nbsp;RevoluteJoint2D(Contribution):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Двухтелый&nbsp;вращательный&nbsp;шарнир&nbsp;(revolute&nbsp;joint).<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Связывает&nbsp;две&nbsp;точки&nbsp;на&nbsp;двух&nbsp;телах:&nbsp;точка&nbsp;A&nbsp;должна&nbsp;совпадать&nbsp;с&nbsp;точкой&nbsp;B.<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyA:&nbsp;RigidBody2D,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyB:&nbsp;RigidBody2D,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint:&nbsp;np.ndarray&nbsp;=&nbsp;None,<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;coords_of_joint&nbsp;=&nbsp;coords_of_joint.copy()&nbsp;if&nbsp;coords_of_joint&nbsp;is&nbsp;not&nbsp;None&nbsp;else&nbsp;bodyA.pose().lin.copy()<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.bodyA&nbsp;=&nbsp;bodyA<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.bodyB&nbsp;=&nbsp;bodyB<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;переменная&nbsp;внутренней&nbsp;силы&nbsp;(двухкомпонентная)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.internal_force&nbsp;=&nbsp;Variable(&quot;F_rev&quot;,&nbsp;size=2,&nbsp;tag=&quot;force&quot;)<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;вычисляем&nbsp;локальные&nbsp;точки&nbsp;для&nbsp;обоих&nbsp;тел<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseA&nbsp;=&nbsp;self.bodyA.pose()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseB&nbsp;=&nbsp;self.bodyB.pose()<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rA_local&nbsp;=&nbsp;poseA.inverse_transform_point(coords_of_joint)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB_local&nbsp;=&nbsp;poseB.inverse_transform_point(coords_of_joint)<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;актуализируем&nbsp;глобальные&nbsp;вектор-радиусы<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_radii()<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([bodyA.acceleration_var,&nbsp;bodyB.acceleration_var,&nbsp;self.internal_force],&nbsp;assembler=assembler)<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;update_radii(self):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Пересчитать&nbsp;глобальные&nbsp;радиусы&nbsp;до&nbsp;опорных&nbsp;точек&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseA&nbsp;=&nbsp;self.bodyA.pose()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseB&nbsp;=&nbsp;self.bodyB.pose()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rA&nbsp;=&nbsp;poseA.rotate_vector(self.rA_local)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB&nbsp;=&nbsp;poseB.rotate_vector(self.rB_local)<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Добавляет&nbsp;вклад&nbsp;в&nbsp;матрицы&nbsp;для&nbsp;ускорений&quot;&quot;&quot;<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;радиусы&nbsp;актуализируем&nbsp;каждый&nbsp;вызов<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_radii()<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h&nbsp;=&nbsp;matrices[&quot;holonomic_rhs&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;force&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F_indices&nbsp;=&nbsp;cmap[self.internal_force]<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omegaA&nbsp;=&nbsp;self.bodyA.velocity_var.value[2]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;omegaB&nbsp;=&nbsp;self.bodyB.velocity_var.value[2]<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bias&nbsp;=&nbsp;(omegaA**2)&nbsp;*&nbsp;self.rA&nbsp;-&nbsp;(omegaB**2)&nbsp;*&nbsp;self.rB<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h[F_indices[0]]&nbsp;+=&nbsp;-bias[0]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;h[F_indices[1]]&nbsp;+=&nbsp;-bias[1]<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_to_holonomic_matrix(self,&nbsp;matrices,&nbsp;index_maps:&nbsp;Dict[str,&nbsp;Dict[Variable,&nbsp;List[int]]]):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Добавляет&nbsp;вклад&nbsp;в&nbsp;матрицу&nbsp;ограничений&nbsp;на&nbsp;положения&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;holonomic&quot;]<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;amap&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;force&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;aA&nbsp;=&nbsp;amap[self.bodyA.acceleration_var]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;aB&nbsp;=&nbsp;amap[self.bodyB.acceleration_var]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;=&nbsp;cmap[self.internal_force]&nbsp;&nbsp;#&nbsp;2&nbsp;строки&nbsp;ограничений<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Вклад&nbsp;в&nbsp;матрицу&nbsp;ограничений&nbsp;от&nbsp;связи&nbsp;шарнира<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;aA)]&nbsp;+=&nbsp;np.array([<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;1.0,&nbsp;&nbsp;0.0,&nbsp;-self.rA[1]],<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;0.0,&nbsp;&nbsp;1.0,&nbsp;&nbsp;self.rA[0]]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])&nbsp;&nbsp;<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;aB)]&nbsp;+=&nbsp;np.array([<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[-1.0,&nbsp;&nbsp;0.0,&nbsp;&nbsp;self.rB[1]],<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[&nbsp;0.0,&nbsp;-1.0,&nbsp;-self.rB[0]]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;])<br>
<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Для&nbsp;позиционной&nbsp;и&nbsp;скоростной&nbsp;проекции&quot;&quot;&quot;<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_radii()<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_to_holonomic_matrix(matrices,&nbsp;index_maps)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr&nbsp;=&nbsp;matrices[&quot;position_error&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;force&quot;]<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;=&nbsp;cmap[self.internal_force]&nbsp;&nbsp;#&nbsp;2&nbsp;строки&nbsp;ограничений<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;----------&nbsp;позиционная&nbsp;ошибка&nbsp;----------<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;φ&nbsp;=&nbsp;cA&nbsp;-&nbsp;cB&nbsp;=&nbsp;(pA&nbsp;+&nbsp;rA)&nbsp;-&nbsp;(pB&nbsp;+&nbsp;rB)<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pA&nbsp;=&nbsp;self.bodyA.pose().lin<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pB&nbsp;=&nbsp;self.bodyB.pose().lin<br>
<br>
#&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[F]&nbsp;+=&nbsp;(pA&nbsp;+&nbsp;self.rA)&nbsp;-&nbsp;(pB&nbsp;+&nbsp;self.rB)<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
