<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody2d_3.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Соглашение о уравнениях такого, что все уравнения собираются в локальной СК тела.<br>
Глобальная поза тела хранится отдельно и используется только для обновления геометрии.<br>
<br>
Преобразования следуют конвенции локальная система -&gt; мировая система:<br>
&#9;p_world = P(q) @ p_local<br>
&#9;p_world = R(θ) @ p_local<br>
&quot;&quot;&quot;<br>
<br>
from typing import List, Dict<br>
import numpy as np<br>
from termin.fem.assembler import Variable, Contribution<br>
from termin.geombase.pose2 import Pose2<br>
from termin.geombase.screw import Screw2<br>
from termin.fem.inertia2d import SpatialInertia2D<br>
<br>
<br>
class RigidBody2D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Твёрдое тело в 2D, все расчёты выполняются в локальной СК тела.<br>
&#9;Глобальная поза хранится отдельно и используется только для обновления геометрии.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;inertia: SpatialInertia2D,<br>
&#9;&#9;gravity: np.ndarray = None,<br>
&#9;&#9;assembler=None,<br>
&#9;&#9;name=&quot;rbody2d&quot;,<br>
&#9;&#9;angle_normalize: callable = None,<br>
&#9;):<br>
&#9;&#9;self.acceleration_var = Variable(name + &quot;_acc&quot;, size=3, tag=&quot;acceleration&quot;)  # [ax, ay, α]_local<br>
&#9;&#9;self.velocity_var = Variable(name + &quot;_vel&quot;, size=3, tag=&quot;velocity&quot;)          # [vx, vy, ω]_local<br>
&#9;&#9;self.local_pose_var = Variable(name + &quot;_pos&quot;, size=3, tag=&quot;position&quot;)              # [x, y, θ]_local (для интеграции лок. движения)<br>
<br>
&#9;&#9;# глобальная поза тела (Pose2)<br>
&#9;&#9;self.global_pose = Pose2(lin=np.zeros(2), ang=0.0)<br>
<br>
&#9;&#9;self.inertia = inertia<br>
&#9;&#9;self.angle_normalize = angle_normalize<br>
<br>
&#9;&#9;# сила тяжести задаётся в мировых координатах<br>
&#9;&#9;self.gravity = np.array([0.0, -9.81]) if gravity is None else np.asarray(gravity, float).reshape(2)<br>
<br>
&#9;&#9;super().__init__([self.acceleration_var, self.velocity_var, self.local_pose_var], assembler=assembler)<br>
<br>
&#9;# ---------- геттеры ----------<br>
&#9;def pose(self) -&gt; Pose2:<br>
&#9;&#9;return self.global_pose<br>
<br>
&#9;def set_pose(self, pose: Pose2):<br>
&#9;&#9;self.global_pose = pose<br>
<br>
&#9;# ---------- вклад в систему ----------<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вклад тела в уравнения движения:<br>
&#9;&#9;&#9;I * a + v×* (I v) = F<br>
&#9;&#9;Все в локальной СК.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.contribute_to_mass_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;b = matrices[&quot;load&quot;]<br>
&#9;&#9;a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
<br>
&#9;&#9;v_local = Screw2.from_vector_vw_order(self.velocity_var.value)<br>
&#9;&#9;bias = self.inertia.bias_wrench(v_local)<br>
<br>
&#9;&#9;# гравитация в локальной СК тела<br>
&#9;&#9;g_local = self.global_pose.inverse().rotate_vector(self.gravity)<br>
&#9;&#9;grav = self.inertia.gravity_wrench(g_local)<br>
<br>
&#9;&#9;b[a_idx] += bias.to_vector_vw_order() + grav.to_vector_vw_order()<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps):<br>
&#9;&#9;self.contribute_to_mass_matrix(matrices, index_maps)<br>
<br>
&#9;def contribute_to_mass_matrix(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Массовая матрица в локальной СК (никаких поворотов).<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;A = matrices[&quot;mass&quot;]<br>
&#9;&#9;a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
&#9;&#9;A[np.ix_(a_idx, a_idx)] += self.inertia.to_matrix_vw_order()<br>
<br>
&#9;# ---------- интеграция шага ----------<br>
&#9;def finish_timestep(self, dt):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;После интеграции уравнений ускорений и скоростей обновляем локальные переменные,<br>
&#9;&#9;затем обновляем глобальную позу, используя локальное смещение.<br>
&#9;&#9;После этого локальная поза обнуляется (тело возвращается в свою СК).<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;v = self.velocity_var.value<br>
&#9;&#9;a = self.acceleration_var.value<br>
&#9;&#9;v += a * dt<br>
&#9;&#9;self.velocity_var.value = v<br>
<br>
&#9;&#9;# локальное приращение позы (интеграция по локальной СК)<br>
&#9;&#9;delta_pose_local = Pose2(<br>
&#9;&#9;&#9;lin=v[0:2] * dt,<br>
&#9;&#9;&#9;ang=v[2] * dt,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;# обновляем глобальную позу тела<br>
&#9;&#9;self.global_pose = self.global_pose @ delta_pose_local<br>
<br>
&#9;&#9;# сбрасываем локальную позу<br>
&#9;&#9;self.local_pose_var.value[:] = 0.0<br>
<br>
&#9;&#9;if self.angle_normalize is not None:<br>
&#9;&#9;&#9;self.global_pose.ang = self.angle_normalize(self.global_pose.ang)<br>
<br>
&#9;def finish_correction_step(self):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;После коррекции позиций сбрасываем локальную позу.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.global_pose = self.global_pose @ Pose2(<br>
&#9;&#9;&#9;lin=self.local_pose_var.value[0:2],<br>
&#9;&#9;&#9;ang=self.local_pose_var.value[2],<br>
&#9;&#9;)<br>
&#9;&#9;self.local_pose_var.value[:] = 0.0<br>
<br>
class ForceOnBody2D(Contribution):<br>
&#9;&quot;&quot;&quot;Внешняя сила и момент в локальной СК тела.&quot;&quot;&quot;<br>
&#9;def __init__(self, body: RigidBody2D, wrench: Screw2,<br>
&#9;&#9;&#9;&#9;in_local_frame: bool = True, assembler=None):<br>
&#9;&#9;self.body = body<br>
&#9;&#9;self.acceleration = body.acceleration_var<br>
&#9;&#9;self.wrench_local = wrench if in_local_frame else wrench.rotated_by(body.pose().inverse())<br>
&#9;&#9;super().__init__([], assembler=assembler)<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;b = matrices[&quot;load&quot;]<br>
&#9;&#9;a_indices = index_maps[&quot;acceleration&quot;][self.acceleration]<br>
&#9;&#9;b[a_indices] += self.wrench_local.to_vector_vw_order()<br>
<br>
<br>
class FixedRotationJoint2D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Ground revolute joint.<br>
&#9;Все уравнения формулируются в локальной СК тела.<br>
&#9;Лямбда — сила, действующая на тело, в локальной СК тела.<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;body: RigidBody2D,<br>
&#9;&#9;&#9;&#9;coords_of_joint: np.ndarray = None,<br>
&#9;&#9;&#9;&#9;assembler=None):<br>
&#9;&#9;self.body = body<br>
&#9;&#9;self.internal_force = Variable(&quot;F_joint&quot;, size=2, tag=&quot;force&quot;)<br>
<br>
&#9;&#9;pose = self.body.pose()<br>
&#9;&#9;self.coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else pose.lin.copy()<br>
&#9;&#9;# фиксируем локальные координаты точки шарнира на теле<br>
&#9;&#9;self.r_local = pose.inverse_transform_point(self.coords_of_joint)<br>
&#9;&#9;<br>
&#9;&#9;super().__init__([body.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
&#9;def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;# линейная часть (Якобиан) — сразу в H<br>
&#9;&#9;self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;# правую часть — квадратичные (центростремительные) члены, тоже в локале<br>
&#9;&#9;h = matrices[&quot;holonomic_rhs&quot;]<br>
&#9;&#9;F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&#9;&#9;omega = float(self.body.velocity_var.value[2])<br>
&#9;&#9;bias = - (omega ** 2) * self.r_local<br>
&#9;&#9;h[F_idx] += bias<br>
<br>
&#9;def radius(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Радиус шарнира в глобальной СК.&quot;&quot;&quot;<br>
&#9;&#9;pose = self.body.pose()<br>
&#9;&#9;r_world = pose.rotate_vector(self.r_local)<br>
&#9;&#9;return r_world<br>
<br>
&#9;def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Ограничение в локале тела:<br>
&#9;&#9;a_lin + α×r_local + (квадр.члены) = 0<br>
&#9;&#9;В матрицу кладём линейную часть по ускорениям:<br>
&#9;&#9;H * [a_x, a_y, α]^T  с блоком  -[ I,  perp(r_local) ]<br>
&#9;&#9;где perp(r) = [-r_y, r_x].<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;H = matrices[&quot;holonomic&quot;]<br>
&#9;&#9;a_idx = index_maps[&quot;acceleration&quot;][self.body.acceleration_var]<br>
&#9;&#9;F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&#9;&#9;r = self.r_local<br>
&#9;&#9;H[np.ix_(F_idx, a_idx)] += -np.array([<br>
&#9;&#9;&#9;[1.0, 0.0, -r[1]],<br>
&#9;&#9;&#9;[0.0, 1.0,  r[0]],<br>
&#9;&#9;])<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Позиционная ошибка тоже в локале тела:<br>
&#9;&#9;φ_local = R^T (p - c_world) + r_local<br>
&#9;&#9;где p — мировая позиция опорной точки тела, c_world — фиксированная мировая точка шарнира.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;# Якобиан для коррекции такой же<br>
&#9;&#9;self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;poserr = matrices[&quot;position_error&quot;]<br>
&#9;&#9;F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&#9;&#9;pose = self.body.pose()        <br>
&#9;&#9;perr = pose.inverse_rotate_vector(pose.lin - self.coords_of_joint)  + self.r_local<br>
&#9;&#9;poserr[F_idx] -= perr<br>
<br>
<br>
class RevoluteJoint2D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Двухтелый вращательный шарнир (revolute joint):<br>
&#9;связь формулируется в локальной СК тела A.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;bodyA: RigidBody2D,<br>
&#9;&#9;&#9;&#9;bodyB: RigidBody2D,<br>
&#9;&#9;&#9;&#9;coords_of_joint: np.ndarray = None,<br>
&#9;&#9;&#9;&#9;assembler=None):<br>
<br>
&#9;&#9;cW = coords_of_joint.copy() if coords_of_joint is not None else bodyA.pose().lin.copy()<br>
<br>
&#9;&#9;self.bodyA = bodyA<br>
&#9;&#9;self.bodyB = bodyB<br>
<br>
&#9;&#9;# 2-компонентная лямбда силы в СК A<br>
&#9;&#9;self.internal_force = Variable(&quot;F_rev&quot;, size=2, tag=&quot;force&quot;)<br>
<br>
&#9;&#9;poseA = self.bodyA.pose()<br>
&#9;&#9;poseB = self.bodyB.pose()<br>
<br>
&#9;&#9;# локальные координаты точки шарнира на каждом теле<br>
&#9;&#9;self.rA_local = poseA.inverse_transform_point(cW)  # в СК A<br>
&#9;&#9;self.rB_local = poseB.inverse_transform_point(cW)  # в СК B<br>
<br>
&#9;&#9;# кэш для rB, выраженного в СК A, и для R_AB<br>
&#9;&#9;#self.R_AB = np.eye(2)<br>
&#9;&#9;self.poseAB = Pose2.identity()<br>
&#9;&#9;self.rB_in_A = self.rB_local.copy()  # будет обновляться<br>
<br>
&#9;&#9;self.update_local_view()<br>
<br>
&#9;&#9;super().__init__([bodyA.acceleration_var, bodyB.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
&#9;@staticmethod<br>
&#9;def _perp_col(r: np.ndarray) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;перпендикуляр к r: α×r = [ -α r_y, α r_x ] ⇒ столбец для α&quot;&quot;&quot;<br>
&#9;&#9;return np.array([-r[1], r[0]])<br>
<br>
&#9;def update_local_view(self):<br>
&#9;&#9;&quot;&quot;&quot;Обновить R_AB и rB, выраженные в СК A.&quot;&quot;&quot;<br>
&#9;&#9;poseA = self.bodyA.pose()<br>
&#9;&#9;poseB = self.bodyB.pose()<br>
&#9;&#9;#cA, sA = np.cos(poseA.ang), np.sin(poseA.ang)<br>
&#9;&#9;#cB, sB = np.cos(poseB.ang), np.sin(poseB.ang)<br>
&#9;&#9;#R_A = np.array([[cA, -sA],[sA, cA]])<br>
&#9;&#9;#R_B = np.array([[cB, -sB],[sB, cB]])<br>
&#9;&#9;#self.R_AB = R_A.T @ R_B<br>
&#9;&#9;self.poseAB = poseA.inverse() @ poseB<br>
&#9;&#9;self.rB_in_A = self.poseAB.rotate_vector(self.rB_local)  # r_B, выраженный в СК A<br>
<br>
&#9;def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;self.update_local_view()<br>
&#9;&#9;self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;h = matrices[&quot;holonomic_rhs&quot;]<br>
&#9;&#9;F = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&#9;&#9;omegaA = float(self.bodyA.velocity_var.value[2])<br>
&#9;&#9;omegaB = float(self.bodyB.velocity_var.value[2])<br>
<br>
&#9;&#9;# квадратичные члены (центростремительные) в правую часть, всё в СК A:<br>
&#9;&#9;# bias = (ωA^2) * rA  - (ωB^2) * (R_AB rB)<br>
&#9;&#9;rA = self.rA_local<br>
&#9;&#9;rB_A = self.rB_in_A<br>
&#9;&#9;bias = (omegaA**2) * rA - (omegaB**2) * rB_A<br>
<br>
&#9;&#9;# по принятой конвенции — добавляем -bias<br>
&#9;&#9;h[F] += -bias<br>
<br>
&#9;def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;В СК A:<br>
&#9;&#9;aA_lin + αA×rA  -  R_AB (aB_lin + αB×rB)  + квадр.члены = 0<br>
&#9;&#9;Линейная часть по ускорениям попадает в матрицу H.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;H = matrices[&quot;holonomic&quot;]<br>
&#9;&#9;aA = index_maps[&quot;acceleration&quot;][self.bodyA.acceleration_var]<br>
&#9;&#9;aB = index_maps[&quot;acceleration&quot;][self.bodyB.acceleration_var]<br>
&#9;&#9;F  = index_maps[&quot;force&quot;][self.internal_force]  # 2 строки<br>
<br>
&#9;&#9;rA = self.rA_local<br>
&#9;&#9;rB_A = self.rB_in_A<br>
&#9;&#9;R = self.poseAB.rotation_matrix()<br>
<br>
&#9;&#9;# блок по aA (в СК A)<br>
&#9;&#9;H[np.ix_(F, aA)] += np.array([<br>
&#9;&#9;&#9;[ 1.0,  0.0, -rA[1]],<br>
&#9;&#9;&#9;[ 0.0,  1.0,  rA[0]],<br>
&#9;&#9;])<br>
<br>
&#9;&#9;# блок по aB, выраженный в СК A:<br>
&#9;&#9;# - [ R,  R * perp(rB) ], где perp(r) = [-r_y, r_x]<br>
&#9;&#9;col_alphaB = self.poseAB.rotate_vector(self._perp_col(self.rB_local))  # = perp(rB_A)<br>
&#9;&#9;H[np.ix_(F, aB)] += np.array([<br>
&#9;&#9;&#9;[-R[0,0], -R[0,1],  col_alphaB[0]],<br>
&#9;&#9;&#9;[-R[1,0], -R[1,1],  col_alphaB[1]],<br>
&#9;&#9;])<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Позиционная ошибка тоже в СК A:<br>
&#9;&#9;φ_A = R_A^T * [ (pA + R_A rA) - (pB + R_B rB) ]<br>
&#9;&#9;&#9;= (R_A^T(pA - pB)) + rA - R_AB rB<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.update_local_view()<br>
&#9;&#9;self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;poserr = matrices[&quot;position_error&quot;]<br>
&#9;&#9;F = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&#9;&#9;pA = self.bodyA.pose().lin<br>
&#9;&#9;pB = self.bodyB.pose().lin<br>
<br>
&#9;&#9;poseA = self.bodyA.pose()<br>
&#9;&#9;R_A_T = poseA.inverse().rotation_matrix()<br>
<br>
&#9;&#9;delta_p_A = R_A_T @ (pA - pB)<br>
&#9;&#9;rA = self.rA_local<br>
&#9;&#9;rB_A = self.rB_in_A<br>
<br>
&#9;&#9;poserr[F] += delta_p_A + rA - rB_A<br>
<!-- END SCAT CODE -->
</body>
</html>
