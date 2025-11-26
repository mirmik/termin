<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody3d_3.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from typing import List, Dict<br>
import numpy as np<br>
<br>
from termin.fem.assembler import Variable, Contribution<br>
from termin.geombase.pose3 import Pose3<br>
from termin.geombase.screw import Screw3<br>
from termin.fem.inertia3d import SpatialInertia3D<br>
<br>
<br>
&quot;&quot;&quot;<br>
Соглашение такое же, как в 2D-версии:<br>
<br>
Все уравнения собираются в локальной СК тела.<br>
Глобальная поза тела хранится отдельно и используется только для обновления геометрии.<br>
<br>
Преобразования следуют конвенции локальная система -&gt; мировая система:<br>
&#9;p_world = P(q) @ p_local<br>
&quot;&quot;&quot;<br>
<br>
def _skew(r: np.ndarray) -&gt; np.ndarray:<br>
&#9;&quot;&quot;&quot;Матрица векторного произведения:  r×x = skew(r) @ x.&quot;&quot;&quot;<br>
&#9;rx, ry, rz = r<br>
&#9;return np.array([<br>
&#9;&#9;[   0.0, -rz,   ry],<br>
&#9;&#9;[   rz,  0.0, -rx],<br>
&#9;&#9;[  -ry,  rx,  0.0],<br>
&#9;], dtype=float)<br>
<br>
def quat_normalize(q):<br>
&#9;return q / np.linalg.norm(q)<br>
<br>
def quat_mul(q1, q2):<br>
&#9;&quot;&quot;&quot;Кватернионное произведение q1*q2 (оба в формате [x,y,z,w]).&quot;&quot;&quot;<br>
&#9;x1,y1,z1,w1 = q1<br>
&#9;x2,y2,z2,w2 = q2<br>
&#9;return np.array([<br>
&#9;&#9;w1*x2 + x1*w2 + y1*z2 - z1*y2,<br>
&#9;&#9;w1*y2 + y1*w2 + z1*x2 - x1*z2,<br>
&#9;&#9;w1*z2 + z1*w2 + x1*y2 - y1*x2,<br>
&#9;&#9;w1*w2 - x1*x2 - y1*y2 - z1*z2,<br>
&#9;])<br>
<br>
def quat_from_small_angle(dθ):<br>
&#9;&quot;&quot;&quot;Создать кватернион вращения из малого углового вектора dθ.&quot;&quot;&quot;<br>
&#9;θ = np.linalg.norm(dθ)<br>
&#9;if θ &lt; 1e-12:<br>
&#9;&#9;# линеаризация<br>
&#9;&#9;return quat_normalize(np.array([0.5*dθ[0], 0.5*dθ[1], 0.5*dθ[2], 1.0]))<br>
&#9;axis = dθ / θ<br>
&#9;s = np.sin(0.5 * θ)<br>
&#9;return np.array([axis[0]*s, axis[1]*s, axis[2]*s, np.cos(0.5*θ)])<br>
<br>
<br>
<br>
class RigidBody3D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Твёрдое тело в 3D, все расчёты выполняются в локальной СК тела.<br>
&#9;Глобальная поза хранится отдельно и используется только для обновления геометрии.<br>
<br>
&#9;Порядок пространственных векторов (vw_order):<br>
&#9;&#9;[ v_x, v_y, v_z, ω_x, ω_y, ω_z ]<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;inertia: SpatialInertia3D,<br>
&#9;&#9;gravity: np.ndarray = None,<br>
&#9;&#9;assembler=None,<br>
&#9;&#9;name: str = &quot;rbody3d&quot;,<br>
&#9;&#9;angle_normalize: callable = None,<br>
&#9;):<br>
&#9;&#9;# [a_lin(3), α(3)] в локальной СК<br>
&#9;&#9;self.acceleration_var = Variable(name + &quot;_acc&quot;, size=6, tag=&quot;acceleration&quot;)<br>
&#9;&#9;# [v_lin(3), ω(3)] в локальной СК<br>
&#9;&#9;self.velocity_var = Variable(name + &quot;_vel&quot;, size=6, tag=&quot;velocity&quot;)<br>
&#9;&#9;# [Δx(3), Δφ(3)] локальная приращённая поза для интеграции<br>
&#9;&#9;self.local_pose_var = Variable(name + &quot;_pos&quot;, size=6, tag=&quot;position&quot;)<br>
<br>
&#9;&#9;# глобальная поза тела<br>
&#9;&#9;self.global_pose = Pose3(lin=np.zeros(3), ang=np.array([0.0, 0.0, 0.0, 1.0]))  # единичный кватернион<br>
<br>
&#9;&#9;self.inertia = inertia<br>
&#9;&#9;self.angle_normalize = angle_normalize<br>
<br>
&#9;&#9;# сила тяжести задаётся в мировых координатах<br>
&#9;&#9;# по аналогии с 2D: -g по оси y<br>
&#9;&#9;if gravity is None:<br>
&#9;&#9;&#9;self.gravity = np.array([0.0, -9.81, 0.0], dtype=float)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;self.gravity = np.asarray(gravity, float).reshape(3)<br>
<br>
&#9;&#9;super().__init__([self.acceleration_var, self.velocity_var, self.local_pose_var],<br>
&#9;&#9;&#9;&#9;&#9;&#9;assembler=assembler)<br>
<br>
&#9;# ---------- геттеры ----------<br>
&#9;def pose(self) -&gt; Pose3:<br>
&#9;&#9;return self.global_pose<br>
<br>
&#9;def set_pose(self, pose: Pose3):<br>
&#9;&#9;self.global_pose = pose<br>
<br>
&#9;# ---------- вклад в систему ----------<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вклад тела в уравнения движения (в локальной СК):<br>
&#9;&#9;&#9;I * a + v×* (I v) = F<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.contribute_to_mass_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;b = matrices[&quot;load&quot;]<br>
&#9;&#9;a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
<br>
&#9;&#9;v_local = Screw3.from_vector_vw_order(self.velocity_var.value)<br>
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
&#9;&#9;Массовая матрица в локальной СК.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;A = matrices[&quot;mass&quot;]<br>
&#9;&#9;a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
&#9;&#9;A[np.ix_(a_idx, a_idx)] += self.inertia.to_matrix_vw_order()<br>
<br>
&#9;# ---------- интеграция шага ----------<br>
&#9;def finish_timestep(self, dt: float):<br>
&#9;&#9;v = self.velocity_var.value<br>
&#9;&#9;a = self.acceleration_var.value<br>
&#9;&#9;v += a * dt<br>
&#9;&#9;self.velocity_var.value = v<br>
<br>
&#9;&#9;# линейное смещение<br>
&#9;&#9;v_lin = v[0:3]<br>
&#9;&#9;dp_lin = v_lin * dt<br>
<br>
&#9;&#9;# угловое малое приращение через кватернион<br>
&#9;&#9;v_ang = v[3:6]<br>
&#9;&#9;dθ = v_ang * dt<br>
&#9;&#9;q_delta = quat_from_small_angle(dθ)<br>
<br>
&#9;&#9;# обновляем глобальную позу<br>
&#9;&#9;# pose.lin += R * dp_lin   (делает Pose3 оператор @)<br>
&#9;&#9;# pose.ang = pose.ang * q_delta<br>
&#9;&#9;delta_pose_local = Pose3(<br>
&#9;&#9;&#9;lin=dp_lin,<br>
&#9;&#9;&#9;ang=q_delta,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;self.global_pose = self.global_pose @ delta_pose_local<br>
<br>
&#9;&#9;# сбрасываем локальную позу<br>
&#9;&#9;self.local_pose_var.value[:] = 0.0<br>
<br>
&#9;&#9;if self.angle_normalize is not None:<br>
&#9;&#9;&#9;self.global_pose.ang = self.angle_normalize(self.global_pose.ang)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;self.global_pose.ang = quat_normalize(self.global_pose.ang)<br>
<br>
&#9;def finish_correction_step(self):<br>
&#9;&#9;dp = self.local_pose_var.value<br>
<br>
&#9;&#9;# линейная часть<br>
&#9;&#9;dp_lin = dp[0:3]<br>
<br>
&#9;&#9;# угловая часть dp[3:6] — это снова угловой вектор, надо превращать в кватернион<br>
&#9;&#9;dθ = dp[3:6]<br>
&#9;&#9;q_delta = quat_from_small_angle(dθ)<br>
<br>
&#9;&#9;delta_pose_local = Pose3(<br>
&#9;&#9;&#9;lin=dp_lin,<br>
&#9;&#9;&#9;ang=q_delta,<br>
&#9;&#9;)<br>
<br>
&#9;&#9;self.global_pose = self.global_pose @ delta_pose_local<br>
&#9;&#9;self.local_pose_var.value[:] = 0.0<br>
&#9;&#9;self.global_pose.ang = quat_normalize(self.global_pose.ang)<br>
<br>
<br>
class ForceOnBody3D(Contribution):<br>
&#9;&quot;&quot;&quot;Внешний пространственный винт (сила+момент) в локальной СК тела.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;body: RigidBody3D,<br>
&#9;&#9;&#9;&#9;wrench: Screw3,<br>
&#9;&#9;&#9;&#9;in_local_frame: bool = True,<br>
&#9;&#9;&#9;&#9;assembler=None):<br>
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
class FixedRotationJoint3D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Ground-&quot;шарнир&quot;, фиксирующий линейное движение одной точки тела в мировой СК,<br>
&#9;но не ограничивающий ориентацию тела.<br>
<br>
&#9;Как и в 2D-версии:<br>
&#9;- всё формулируется в локальной СК тела;<br>
&#9;- лямбда — линейная сила в локальной СК тела (3 компоненты).<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;body: RigidBody3D,<br>
&#9;&#9;&#9;&#9;coords_of_joint: np.ndarray = None,<br>
&#9;&#9;&#9;&#9;assembler=None):<br>
&#9;&#9;self.body = body<br>
&#9;&#9;self.internal_force = Variable(&quot;F_joint&quot;, size=3, tag=&quot;force&quot;)<br>
<br>
&#9;&#9;pose = self.body.pose()<br>
&#9;&#9;self.coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else pose.lin.copy()<br>
&#9;&#9;# фиксируем локальные координаты точки шарнира на теле<br>
&#9;&#9;self.r_local = pose.inverse_transform_point(self.coords_of_joint)<br>
<br>
&#9;&#9;super().__init__([body.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
&#9;def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;# линейная часть (Якобиан) — в H<br>
&#9;&#9;self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;# правую часть — квадратичные (центростремительные) члены, тоже в локале<br>
&#9;&#9;h = matrices[&quot;holonomic_rhs&quot;]<br>
&#9;&#9;F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&#9;&#9;omega = np.asarray(self.body.velocity_var.value[3:6], dtype=float)<br>
&#9;&#9;# центростремительное ускорение точки: ω × (ω × r)<br>
&#9;&#9;bias = np.cross(omega, np.cross(omega, self.r_local))<br>
&#9;&#9;h[F_idx] += bias<br>
<br>
&#9;def radius(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Радиус-вектор точки шарнира в глобальной СК.&quot;&quot;&quot;<br>
&#9;&#9;pose = self.body.pose()<br>
&#9;&#9;return pose.rotate_vector(self.r_local)<br>
<br>
&#9;def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Ограничение в локале тела:<br>
&#9;&#9;a_lin + α×r_local + (квадр.члены) = 0<br>
<br>
&#9;&#9;В матрицу кладём линейную часть по ускорениям:<br>
&#9;&#9;H * [a_lin(3), α(3)]^T  с блоком  -[ I_3,  -skew(r_local) ]<br>
&#9;&#9;где α×r = -skew(r) α.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;H = matrices[&quot;holonomic&quot;]<br>
&#9;&#9;a_idx = index_maps[&quot;acceleration&quot;][self.body.acceleration_var]<br>
&#9;&#9;F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&#9;&#9;r = self.r_local<br>
&#9;&#9;J = np.hstack([<br>
&#9;&#9;&#9;np.eye(3),<br>
&#9;&#9;&#9;-_skew(r),<br>
&#9;&#9;])  # 3×6<br>
<br>
&#9;&#9;H[np.ix_(F_idx, a_idx)] += -J  # как в 2D: минус перед блоком<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Позиционная ошибка в локале тела:<br>
&#9;&#9;φ_local = R^T (p - c_world) + r_local<br>
&#9;&#9;где p — мировая позиция опорной точки тела, c_world — фиксированная мировая точка шарнира.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;poserr = matrices[&quot;position_error&quot;]<br>
&#9;&#9;F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&#9;&#9;pose = self.body.pose()<br>
&#9;&#9;# предполагается, что Pose3 умеет выдавать матрицу поворота<br>
&#9;&#9;R = pose.rotation_matrix()<br>
&#9;&#9;R_T = R.T<br>
<br>
&#9;&#9;perr = R_T @ (pose.lin - self.coords_of_joint) + self.r_local<br>
&#9;&#9;poserr[F_idx] -= perr<br>
<br>
<br>
class RevoluteJoint3D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Двухтелый &quot;вращательный&quot; шарнир в духе 2D-кода, но в 3D:<br>
&#9;связь формулируется в локальной СК тела A, и<br>
&#9;ограничивает только относительное линейное движение точки шарнира,<br>
&#9;ориентация тел не фиксируется.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;bodyA: RigidBody3D,<br>
&#9;&#9;&#9;&#9;bodyB: RigidBody3D,<br>
&#9;&#9;&#9;&#9;coords_of_joint: np.ndarray = None,<br>
&#9;&#9;&#9;&#9;assembler=None):<br>
<br>
&#9;&#9;cW = coords_of_joint.copy() if coords_of_joint is not None else bodyA.pose().lin.copy()<br>
<br>
&#9;&#9;self.bodyA = bodyA<br>
&#9;&#9;self.bodyB = bodyB<br>
<br>
&#9;&#9;# 3-компонентная лямбда — сила в СК A<br>
&#9;&#9;self.internal_force = Variable(&quot;F_rev&quot;, size=3, tag=&quot;force&quot;)<br>
<br>
&#9;&#9;poseA = self.bodyA.pose()<br>
&#9;&#9;poseB = self.bodyB.pose()<br>
<br>
&#9;&#9;# локальные координаты точки шарнира на каждом теле<br>
&#9;&#9;self.rA_local = poseA.inverse_transform_point(cW)  # в СК A<br>
&#9;&#9;self.rB_local = poseB.inverse_transform_point(cW)  # в СК B<br>
<br>
&#9;&#9;# кэш для rB, выраженного в СК A, и для R_AB<br>
&#9;&#9;self.R_AB = np.eye(3)<br>
&#9;&#9;self.rB_in_A = self.rB_local.copy()<br>
<br>
&#9;&#9;self.update_local_view()<br>
<br>
&#9;&#9;super().__init__([bodyA.acceleration_var, bodyB.acceleration_var, self.internal_force],<br>
&#9;&#9;&#9;&#9;&#9;&#9;assembler=assembler)<br>
<br>
&#9;def update_local_view(self):<br>
&#9;&#9;&quot;&quot;&quot;Обновить R_AB и rB, выраженные в СК A.&quot;&quot;&quot;<br>
&#9;&#9;poseA = self.bodyA.pose()<br>
&#9;&#9;poseB = self.bodyB.pose()<br>
<br>
&#9;&#9;R_A = poseA.rotation_matrix()<br>
&#9;&#9;R_B = poseB.rotation_matrix()<br>
<br>
&#9;&#9;self.R_AB = R_A.T @ R_B<br>
&#9;&#9;self.rB_in_A = self.R_AB @ self.rB_local<br>
<br>
&#9;def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;self.update_local_view()<br>
&#9;&#9;self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;h = matrices[&quot;holonomic_rhs&quot;]<br>
&#9;&#9;F = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
&#9;&#9;omegaA = np.asarray(self.bodyA.velocity_var.value[3:6], dtype=float)<br>
&#9;&#9;omegaB = np.asarray(self.bodyB.velocity_var.value[3:6], dtype=float)<br>
<br>
&#9;&#9;# квадратичные члены (центростремительные), всё в СК A:<br>
&#9;&#9;# bias = (ωA×(ωA×rA))  -  (ωB×(ωB×rB_A))<br>
&#9;&#9;rA = self.rA_local<br>
&#9;&#9;rB_A = self.rB_in_A<br>
<br>
&#9;&#9;biasA = np.cross(omegaA, np.cross(omegaA, rA))<br>
&#9;&#9;biasB = np.cross(omegaB, np.cross(omegaB, rB_A))<br>
&#9;&#9;bias = biasA - biasB<br>
<br>
&#9;&#9;# по принятой конвенции — добавляем -bias<br>
&#9;&#9;h[F] += -bias<br>
<br>
&#9;def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;В СК A:<br>
&#9;&#9;aA_lin + αA×rA  -  R_AB (aB_lin + αB×rB)  + квадр.члены = 0<br>
<br>
&#9;&#9;Линейная часть по ускорениям:<br>
&#9;&#9;H * [aA_lin(3), αA(3), aB_lin(3), αB(3)]^T<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;H = matrices[&quot;holonomic&quot;]<br>
&#9;&#9;aA = index_maps[&quot;acceleration&quot;][self.bodyA.acceleration_var]<br>
&#9;&#9;aB = index_maps[&quot;acceleration&quot;][self.bodyB.acceleration_var]<br>
&#9;&#9;F  = index_maps[&quot;force&quot;][self.internal_force]  # 3 строки<br>
<br>
&#9;&#9;rA = self.rA_local<br>
&#9;&#9;R = self.R_AB<br>
<br>
&#9;&#9;# блок по aA (в СК A): [ I, -skew(rA) ]<br>
&#9;&#9;J_A = np.hstack([<br>
&#9;&#9;&#9;np.eye(3),<br>
&#9;&#9;&#9;-_skew(rA),<br>
&#9;&#9;])  # 3×6<br>
&#9;&#9;H[np.ix_(F, aA)] += J_A<br>
<br>
&#9;&#9;# блок по aB, выраженный в СК A:<br>
&#9;&#9;# - R_AB (aB_lin + αB×rB) =<br>
&#9;&#9;#   [ -R_AB,  R_AB * skew(rB_local) ] * [aB_lin, αB]^T<br>
&#9;&#9;S_rB = _skew(self.rB_local)<br>
&#9;&#9;col_alphaB = R @ S_rB  # 3×3<br>
<br>
&#9;&#9;J_B = np.hstack([<br>
&#9;&#9;&#9;-R,<br>
&#9;&#9;&#9;col_alphaB,<br>
&#9;&#9;])  # 3×6<br>
<br>
&#9;&#9;H[np.ix_(F, aB)] += J_B<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Позиционная ошибка в СК A:<br>
&#9;&#9;φ_A = R_A^T [ (pA + R_A rA) - (pB + R_B rB) ]<br>
&#9;&#9;&#9;= R_A^T (pA - pB) + rA - R_AB rB<br>
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
&#9;&#9;R_A = poseA.rotation_matrix()<br>
&#9;&#9;R_A_T = R_A.T<br>
<br>
&#9;&#9;delta_p_A = R_A_T @ (pA - pB)<br>
&#9;&#9;rA = self.rA_local<br>
&#9;&#9;rB_A = self.rB_in_A<br>
<br>
&#9;&#9;poserr[F] += delta_p_A + rA - rB_A<br>
<!-- END SCAT CODE -->
</body>
</html>
