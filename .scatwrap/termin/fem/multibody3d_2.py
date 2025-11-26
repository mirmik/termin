<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody3d_2.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from&nbsp;typing&nbsp;import&nbsp;List,&nbsp;Dict<br>
import&nbsp;numpy&nbsp;as&nbsp;np<br>
from&nbsp;termin.fem.assembler&nbsp;import&nbsp;Variable,&nbsp;Contribution<br>
from&nbsp;termin.geombase.pose3&nbsp;import&nbsp;Pose3<br>
from&nbsp;termin.geombase.screw&nbsp;import&nbsp;Screw3<br>
from&nbsp;termin.fem.inertia3d&nbsp;import&nbsp;SpatialInertia3D<br>
<br>
def&nbsp;skew(v:&nbsp;np.ndarray)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Возвращает&nbsp;кососимметричную&nbsp;матрицу&nbsp;для&nbsp;вектора&nbsp;v.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;np.array([[0,&nbsp;-v[2],&nbsp;v[1]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[v[2],&nbsp;0,&nbsp;-v[0]],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[-v[1],&nbsp;v[0],&nbsp;0]])<br>
<br>
class&nbsp;RigidBody3D(Contribution):<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;inertia:&nbsp;SpatialInertia3D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;gravity=np.array([0,0,-9.81]),<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None,&nbsp;name=&quot;rbody3d&quot;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.acceleration_var&nbsp;=&nbsp;Variable(name+&quot;_acc&quot;,&nbsp;size=6,&nbsp;tag=&quot;acceleration&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.velocity_var&nbsp;=&nbsp;Variable(name+&quot;_vel&quot;,&nbsp;size=6,&nbsp;tag=&quot;velocity&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pose_var&nbsp;=&nbsp;Variable(name+&quot;_pose&quot;,&nbsp;size=7,&nbsp;tag=&quot;position&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.gravity&nbsp;=&nbsp;gravity<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.spatial_local&nbsp;=&nbsp;inertia&nbsp;&nbsp;&nbsp;#&nbsp;spatial&nbsp;inertia&nbsp;in&nbsp;body&nbsp;frame<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([self.acceleration_var,&nbsp;self.velocity_var,&nbsp;self.pose_var],&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;pose(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Pose3.from_vector_vw_order(self.pose_var.value)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;set_pose(self,&nbsp;pose:&nbsp;Pose3):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pose_var.value&nbsp;=&nbsp;pose.to_vector_vw_order()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.pose()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Iw=self.contribute_mass_matrix(matrices,&nbsp;index_maps)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;idx&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Fg_screw&nbsp;=&nbsp;Iw.gravity_wrench(self.gravity)&nbsp;&nbsp;&nbsp;#&nbsp;6×1&nbsp;vector<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Fg&nbsp;=&nbsp;Fg_screw.to_vw_array()&nbsp;&nbsp;#&nbsp;in&nbsp;world&nbsp;frame<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;matrices[&quot;load&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;i&nbsp;in&nbsp;range(6):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[idx[i]]&nbsp;+=&nbsp;Fg[i]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_mass_matrix(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;I_origin&nbsp;=&nbsp;self.spatial_local.at_body_origin()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Iw&nbsp;=&nbsp;I_origin.rotate_by(pose)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;matrices[&quot;mass&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;idx&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A[np.ix_(idx,&nbsp;idx)]&nbsp;+=&nbsp;Iw.to_matrix_vw_order()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;Iw<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute_mass_matrix(matrices,&nbsp;index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;finish_timestep(self,&nbsp;dt):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;old_velocity&nbsp;=&nbsp;self.velocity_var.value.copy()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.velocity_var.value&nbsp;+=&nbsp;self.acceleration_var.value&nbsp;*&nbsp;dt<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;delta_scr&nbsp;=&nbsp;Screw3(lin=old_velocity[0:3]*dt,&nbsp;ang=old_velocity[3:6]*dt)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;delta_pose&nbsp;=&nbsp;delta_scr.to_pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;curpose&nbsp;=&nbsp;Pose3.from_vector_vw_order(self.pose_var.value)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;newpose&nbsp;=&nbsp;curpose&nbsp;*&nbsp;delta_pose<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pose_var.value&nbsp;=&nbsp;newpose.to_vector_vw_order()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;matrix_of_transform_from_minimal_coordinates(self)&nbsp;-&gt;&nbsp;np.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Матрица&nbsp;перехода&nbsp;от&nbsp;минимальных&nbsp;координат,&nbsp;где&nbsp;повот&nbsp;выражен&nbsp;в&nbsp;углах&nbsp;в&nbsp;собственной&nbsp;системе&nbsp;координат,&nbsp;к&nbsp;спатиал&nbsp;позе&nbsp;с&nbsp;кватернионом.&nbsp;Матрица&nbsp;7×6&nbsp;.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
<br>
class&nbsp;ForceOnBody3D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Внешняя&nbsp;сила&nbsp;и&nbsp;момент,&nbsp;приложенные&nbsp;к&nbsp;твердому&nbsp;телу&nbsp;в&nbsp;3D.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body:&nbsp;RigidBody3D,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;force:&nbsp;np.ndarray&nbsp;=&nbsp;np.zeros(3),&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Fx,&nbsp;Fy,&nbsp;Fz<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;torque:&nbsp;np.ndarray&nbsp;=&nbsp;np.zeros(3),&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;τx,&nbsp;τy,&nbsp;τz<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;force:&nbsp;Внешняя&nbsp;сила&nbsp;(3,)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;torque:&nbsp;Внешний&nbsp;момент&nbsp;(3,)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.body&nbsp;=&nbsp;body<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.velocity&nbsp;=&nbsp;body.velocity&nbsp;&nbsp;#&nbsp;PoseVariable<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.force&nbsp;=&nbsp;np.asarray(force,&nbsp;float)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.torque&nbsp;=&nbsp;np.asarray(torque,&nbsp;float)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([],&nbsp;assembler=assembler)&nbsp;&nbsp;#&nbsp;переменных&nbsp;нет<br>
<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Добавить&nbsp;вклад&nbsp;в&nbsp;вектор&nbsp;нагрузок&nbsp;b.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;matrices[&quot;load&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;amap&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;v_idx:&nbsp;три&nbsp;индекса&nbsp;линейной&nbsp;части<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;w_idx:&nbsp;три&nbsp;индекса&nbsp;угловой&nbsp;части<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_idx&nbsp;=&nbsp;amap[self.acceleration][0:3]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;w_idx&nbsp;=&nbsp;amap[self.acceleration][3:6]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Линейная&nbsp;сила<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[v_idx[0]]&nbsp;+=&nbsp;self.force[0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[v_idx[1]]&nbsp;+=&nbsp;self.force[1]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[v_idx[2]]&nbsp;+=&nbsp;self.force[2]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Момент<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[w_idx[0]]&nbsp;+=&nbsp;self.torque[0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[w_idx[1]]&nbsp;+=&nbsp;self.torque[1]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b[w_idx[2]]&nbsp;+=&nbsp;self.torque[2]<br>
<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Внешние&nbsp;силы&nbsp;не&nbsp;участвуют&nbsp;в&nbsp;позиционной&nbsp;коррекции.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pass<br>
<br>
class&nbsp;FixedRotationJoint3D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;3D&nbsp;фиксированная&nbsp;точка&nbsp;(ground&nbsp;spherical&nbsp;joint).<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Условие:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;p&nbsp;+&nbsp;R&nbsp;*&nbsp;r_local&nbsp;=&nbsp;joint_world<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Скоростная&nbsp;связь:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v&nbsp;+&nbsp;ω&nbsp;×&nbsp;r&nbsp;=&nbsp;0<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;body,&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;RigidBody3D<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint_point:&nbsp;np.ndarray,&nbsp;&nbsp;&nbsp;#&nbsp;мировая&nbsp;точка&nbsp;(3,)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.body&nbsp;=&nbsp;body<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.joint_point&nbsp;=&nbsp;np.asarray(joint_point,&nbsp;float)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;внутренняя&nbsp;сила&nbsp;—&nbsp;3&nbsp;компоненты<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.internal_force&nbsp;=&nbsp;Variable(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;F_fixed3d&quot;,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;size=3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;tag=&quot;force&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;вычисляем&nbsp;локальную&nbsp;точку&nbsp;(обратное&nbsp;преобразование)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.r_local&nbsp;=&nbsp;pose.inverse_transform_point(self.joint_point)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;актуализируем&nbsp;r&nbsp;в&nbsp;мировых<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_radius()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([self.body.acceleration_var,&nbsp;self.internal_force],&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;-----------------------------------------------------------<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;update_radius(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Обновить&nbsp;мировой&nbsp;радиус&nbsp;r&nbsp;=&nbsp;R&nbsp;*&nbsp;r_local.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.r&nbsp;=&nbsp;pose.transform_vector(self.r_local)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.radius&nbsp;=&nbsp;self.r<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;-----------------------------------------------------------<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Вклад&nbsp;в&nbsp;матрицу&nbsp;holonomic.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Ограничение:&nbsp;e&nbsp;=&nbsp;p&nbsp;+&nbsp;r&nbsp;-&nbsp;j&nbsp;=&nbsp;0.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Якобиан:&nbsp;[&nbsp;I3&nbsp;|&nbsp;-skew(r)&nbsp;].<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_radius()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;holonomic&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;amap&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;force&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;индексы&nbsp;скоростей&nbsp;тела<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;v_idx&nbsp;=&nbsp;amap[self.body.acceleration_var]&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;6&nbsp;индексов<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;индексы&nbsp;внутренних&nbsp;сил<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;f_idx&nbsp;=&nbsp;cmap[self.internal_force]&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;3&nbsp;индексов<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;---&nbsp;Заполняем&nbsp;якобиан&nbsp;---<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;H[f,&nbsp;v]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;линейные&nbsp;скорости:&nbsp;+I<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[f_idx[0],&nbsp;v_idx[0]]&nbsp;+=&nbsp;1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[f_idx[1],&nbsp;v_idx[1]]&nbsp;+=&nbsp;1<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[f_idx[2],&nbsp;v_idx[2]]&nbsp;+=&nbsp;1<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;угловые&nbsp;скорости:&nbsp;-[r]_×<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;S&nbsp;=&nbsp;skew(self.r)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;порядок&nbsp;v_idx[3:6]&nbsp;—&nbsp;(wx,&nbsp;wy,&nbsp;wz)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(f_idx,&nbsp;v_idx[3:6])]&nbsp;-=&nbsp;S<br>
<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;-----------------------------------------------------------<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Для&nbsp;коррекции&nbsp;ограничений&nbsp;делаем&nbsp;то&nbsp;же&nbsp;самое.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_radius()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute(matrices,&nbsp;index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr&nbsp;=&nbsp;matrices[&quot;position_error&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;f_idx&nbsp;=&nbsp;index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;---&nbsp;Позиционная&nbsp;ошибка&nbsp;---<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;pose&nbsp;=&nbsp;self.body.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;p&nbsp;=&nbsp;pose.lin<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;e&nbsp;=&nbsp;p&nbsp;+&nbsp;self.r&nbsp;-&nbsp;self.joint_point<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[f_idx[0]]&nbsp;+=&nbsp;e[0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[f_idx[1]]&nbsp;+=&nbsp;e[1]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[f_idx[2]]&nbsp;+=&nbsp;e[2]<br>
<br>
<br>
class&nbsp;RevoluteJoint3D(Contribution):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;3D&nbsp;револьвентный&nbsp;шарнир&nbsp;в&nbsp;смысле&nbsp;2D-версии:<br>
&nbsp;&nbsp;&nbsp;&nbsp;совпадение&nbsp;двух&nbsp;точек&nbsp;на&nbsp;двух&nbsp;телах.<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Ограничения:&nbsp;(pA&nbsp;+&nbsp;rA)&nbsp;-&nbsp;(pB&nbsp;+&nbsp;rB)&nbsp;=&nbsp;0&nbsp;&nbsp;&nbsp;(3&nbsp;eq)<br>
&nbsp;&nbsp;&nbsp;&nbsp;Не&nbsp;ограничивает&nbsp;ориентацию!<br>
&nbsp;&nbsp;&nbsp;&nbsp;Даёт&nbsp;3&nbsp;степени&nbsp;свободы&nbsp;на&nbsp;вращение.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyA,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bodyB,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;joint_point_world:&nbsp;np.ndarray,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=None):<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.bodyA&nbsp;=&nbsp;bodyA<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.bodyB&nbsp;=&nbsp;bodyB<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Внутренняя&nbsp;реакция&nbsp;—&nbsp;вектор&nbsp;из&nbsp;3&nbsp;компонент<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.internal_force&nbsp;=&nbsp;Variable(&quot;F_rev3d&quot;,&nbsp;size=3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;tag=&quot;force&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;локальные&nbsp;точки&nbsp;крепления<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseA&nbsp;=&nbsp;self.bodyA.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseB&nbsp;=&nbsp;self.bodyB.pose()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rA_local&nbsp;=&nbsp;poseA.inverse_transform_point(joint_point_world)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB_local&nbsp;=&nbsp;poseB.inverse_transform_point(joint_point_world)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;обновляем&nbsp;мировую&nbsp;геометрию<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_kinematics()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__([bodyA.velocity,&nbsp;bodyB.velocity,&nbsp;self.internal_force],<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;assembler=assembler)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;--------------------------------------------------------------<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;update_kinematics(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseA&nbsp;=&nbsp;self.bodyA.pose()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poseB&nbsp;=&nbsp;self.bodyB.pose()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pA&nbsp;=&nbsp;poseA.lin<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.pB&nbsp;=&nbsp;poseB.lin<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rA&nbsp;=&nbsp;poseA.transform_vector(self.rA_local)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.rB&nbsp;=&nbsp;poseB.transform_vector(self.rB_local)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;--------------------------------------------------------------<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_kinematics()<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H&nbsp;=&nbsp;matrices[&quot;holonomic&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;amap&nbsp;=&nbsp;index_maps[&quot;acceleration&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;force&quot;]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vA&nbsp;=&nbsp;amap[self.bodyA.velocity]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;vB&nbsp;=&nbsp;amap[self.bodyB.velocity]<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;=&nbsp;cmap[self.internal_force]&nbsp;&nbsp;#&nbsp;3&nbsp;строки<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Матрицы&nbsp;скосов&nbsp;радиусов<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SA&nbsp;=&nbsp;skew(self.rA)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SB&nbsp;=&nbsp;skew(self.rB)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;dφ/dvA_lin&nbsp;=&nbsp;+I<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;vA[0:3])]&nbsp;+=&nbsp;np.eye(3)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;dφ/dvA_ang&nbsp;=&nbsp;-skew(rA)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;vA[3:6])]&nbsp;+=&nbsp;-SA<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;dφ/dvB_lin&nbsp;=&nbsp;-I<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;vB[0:3])]&nbsp;+=&nbsp;-np.eye(3)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;dφ/dvB_ang&nbsp;=&nbsp;+skew(rB)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;H[np.ix_(F,&nbsp;vB[3:6])]&nbsp;+=&nbsp;SB<br>
<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;--------------------------------------------------------------<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;contribute_for_constraints_correction(self,&nbsp;matrices,&nbsp;index_maps):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.update_kinematics()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.contribute(matrices,&nbsp;index_maps)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;cmap&nbsp;=&nbsp;index_maps[&quot;force&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;F&nbsp;=&nbsp;cmap[self.internal_force]&nbsp;&nbsp;#&nbsp;3&nbsp;строки<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr&nbsp;=&nbsp;matrices[&quot;position_error&quot;]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;позиционная&nbsp;ошибка:&nbsp;φ&nbsp;=&nbsp;(pA+rA)&nbsp;-&nbsp;(pB+rB)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;err&nbsp;=&nbsp;(self.pA&nbsp;+&nbsp;self.rA)&nbsp;-&nbsp;(self.pB&nbsp;+&nbsp;self.rB)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[F[0]]&nbsp;+=&nbsp;err[0]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[F[1]]&nbsp;+=&nbsp;err[1]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;poserr[F[2]]&nbsp;+=&nbsp;err[2]<br>
<!-- END SCAT CODE -->
</body>
</html>
