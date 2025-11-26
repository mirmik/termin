<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody3d_2.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from typing import List, Dict<br>
import numpy as np<br>
from termin.fem.assembler import Variable, Contribution<br>
from termin.geombase.pose3 import Pose3<br>
from termin.geombase.screw import Screw3<br>
from termin.fem.inertia3d import SpatialInertia3D<br>
<br>
def skew(v: np.ndarray) -&gt; np.ndarray:<br>
&#9;&quot;&quot;&quot;Возвращает кососимметричную матрицу для вектора v.&quot;&quot;&quot;<br>
&#9;return np.array([[0, -v[2], v[1]],<br>
&#9;&#9;&#9;&#9;&#9;[v[2], 0, -v[0]],<br>
&#9;&#9;&#9;&#9;&#9;[-v[1], v[0], 0]])<br>
<br>
class RigidBody3D(Contribution):<br>
<br>
&#9;def __init__(self, inertia: SpatialInertia3D,<br>
&#9;&#9;&#9;&#9;gravity=np.array([0,0,-9.81]),<br>
&#9;&#9;&#9;&#9;assembler=None, name=&quot;rbody3d&quot;):<br>
&#9;&#9;self.acceleration_var = Variable(name+&quot;_acc&quot;, size=6, tag=&quot;acceleration&quot;)<br>
&#9;&#9;self.velocity_var = Variable(name+&quot;_vel&quot;, size=6, tag=&quot;velocity&quot;)<br>
&#9;&#9;self.pose_var = Variable(name+&quot;_pose&quot;, size=7, tag=&quot;position&quot;)<br>
&#9;&#9;self.gravity = gravity<br>
&#9;&#9;self.spatial_local = inertia   # spatial inertia in body frame<br>
&#9;&#9;super().__init__([self.acceleration_var, self.velocity_var, self.pose_var], assembler=assembler)<br>
<br>
&#9;def pose(self):<br>
&#9;&#9;return Pose3.from_vector_vw_order(self.pose_var.value)<br>
<br>
&#9;def set_pose(self, pose: Pose3):<br>
&#9;&#9;self.pose_var.value = pose.to_vector_vw_order()<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;pose = self.pose()<br>
<br>
&#9;&#9;Iw=self.contribute_mass_matrix(matrices, index_maps)<br>
<br>
&#9;&#9;idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
&#9;&#9;Fg_screw = Iw.gravity_wrench(self.gravity)   # 6×1 vector<br>
&#9;&#9;Fg = Fg_screw.to_vw_array()  # in world frame<br>
&#9;&#9;b = matrices[&quot;load&quot;]<br>
&#9;&#9;for i in range(6):<br>
&#9;&#9;&#9;b[idx[i]] += Fg[i]<br>
<br>
&#9;def contribute_mass_matrix(self, matrices, index_maps):<br>
&#9;&#9;pose = self.pose()<br>
&#9;&#9;I_origin = self.spatial_local.at_body_origin()<br>
&#9;&#9;Iw = I_origin.rotate_by(pose)<br>
<br>
&#9;&#9;A = matrices[&quot;mass&quot;]<br>
&#9;&#9;idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
&#9;&#9;A[np.ix_(idx, idx)] += Iw.to_matrix_vw_order()<br>
&#9;&#9;return Iw<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps):<br>
&#9;&#9;self.contribute_mass_matrix(matrices, index_maps)<br>
&#9;&#9;<br>
&#9;def finish_timestep(self, dt):<br>
&#9;&#9;old_velocity = self.velocity_var.value.copy()<br>
&#9;&#9;self.velocity_var.value += self.acceleration_var.value * dt<br>
&#9;&#9;delta_scr = Screw3(lin=old_velocity[0:3]*dt, ang=old_velocity[3:6]*dt)<br>
&#9;&#9;delta_pose = delta_scr.to_pose()<br>
&#9;&#9;curpose = Pose3.from_vector_vw_order(self.pose_var.value)<br>
&#9;&#9;newpose = curpose * delta_pose<br>
&#9;&#9;self.pose_var.value = newpose.to_vector_vw_order()<br>
<br>
&#9;def matrix_of_transform_from_minimal_coordinates(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Матрица перехода от минимальных координат, где повот выражен в углах в собственной системе координат, к спатиал позе с кватернионом. Матрица 7×6 .&quot;&quot;&quot;<br>
&#9;&#9;<br>
<br>
class ForceOnBody3D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Внешняя сила и момент, приложенные к твердому телу в 3D.<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;body: RigidBody3D,<br>
&#9;&#9;&#9;&#9;force: np.ndarray = np.zeros(3),     # Fx, Fy, Fz<br>
&#9;&#9;&#9;&#9;torque: np.ndarray = np.zeros(3),    # τx, τy, τz<br>
&#9;&#9;&#9;&#9;assembler=None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Args:<br>
&#9;&#9;&#9;force: Внешняя сила (3,)<br>
&#9;&#9;&#9;torque: Внешний момент (3,)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.body = body<br>
&#9;&#9;self.velocity = body.velocity  # PoseVariable<br>
&#9;&#9;self.force = np.asarray(force, float)<br>
&#9;&#9;self.torque = np.asarray(torque, float)<br>
<br>
&#9;&#9;super().__init__([], assembler=assembler)  # переменных нет<br>
<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Добавить вклад в вектор нагрузок b.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;b = matrices[&quot;load&quot;]<br>
&#9;&#9;amap = index_maps[&quot;acceleration&quot;]<br>
<br>
&#9;&#9;# v_idx: три индекса линейной части<br>
&#9;&#9;# w_idx: три индекса угловой части<br>
&#9;&#9;v_idx = amap[self.acceleration][0:3]<br>
&#9;&#9;w_idx = amap[self.acceleration][3:6]<br>
<br>
&#9;&#9;# Линейная сила<br>
&#9;&#9;b[v_idx[0]] += self.force[0]<br>
&#9;&#9;b[v_idx[1]] += self.force[1]<br>
&#9;&#9;b[v_idx[2]] += self.force[2]<br>
<br>
&#9;&#9;# Момент<br>
&#9;&#9;b[w_idx[0]] += self.torque[0]<br>
&#9;&#9;b[w_idx[1]] += self.torque[1]<br>
&#9;&#9;b[w_idx[2]] += self.torque[2]<br>
<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Внешние силы не участвуют в позиционной коррекции.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;pass<br>
<br>
class FixedRotationJoint3D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;3D фиксированная точка (ground spherical joint).<br>
&#9;<br>
&#9;Условие:<br>
&#9;&#9;p + R * r_local = joint_world<br>
&#9;<br>
&#9;Скоростная связь:<br>
&#9;&#9;v + ω × r = 0<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, <br>
&#9;&#9;&#9;&#9;body,                      # RigidBody3D<br>
&#9;&#9;&#9;&#9;joint_point: np.ndarray,   # мировая точка (3,)<br>
&#9;&#9;&#9;&#9;assembler=None):<br>
<br>
&#9;&#9;self.body = body<br>
&#9;&#9;self.joint_point = np.asarray(joint_point, float)<br>
<br>
&#9;&#9;# внутренняя сила — 3 компоненты<br>
&#9;&#9;self.internal_force = Variable(<br>
&#9;&#9;&#9;&quot;F_fixed3d&quot;,<br>
&#9;&#9;&#9;size=3,<br>
&#9;&#9;&#9;tag=&quot;force&quot;<br>
&#9;&#9;)<br>
<br>
&#9;&#9;# вычисляем локальную точку (обратное преобразование)<br>
&#9;&#9;pose = self.body.pose()<br>
&#9;&#9;self.r_local = pose.inverse_transform_point(self.joint_point)<br>
<br>
&#9;&#9;# актуализируем r в мировых<br>
&#9;&#9;self.update_radius()<br>
<br>
&#9;&#9;super().__init__([self.body.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
&#9;# -----------------------------------------------------------<br>
<br>
&#9;def update_radius(self):<br>
&#9;&#9;&quot;&quot;&quot;Обновить мировой радиус r = R * r_local.&quot;&quot;&quot;<br>
&#9;&#9;pose = self.body.pose()<br>
&#9;&#9;self.r = pose.transform_vector(self.r_local)<br>
&#9;&#9;self.radius = self.r<br>
<br>
&#9;# -----------------------------------------------------------<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вклад в матрицу holonomic.<br>
&#9;&#9;Ограничение: e = p + r - j = 0.<br>
&#9;&#9;Якобиан: [ I3 | -skew(r) ].<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.update_radius()<br>
<br>
&#9;&#9;H = matrices[&quot;holonomic&quot;]<br>
<br>
&#9;&#9;amap = index_maps[&quot;acceleration&quot;]<br>
&#9;&#9;cmap = index_maps[&quot;force&quot;]<br>
<br>
&#9;&#9;# индексы скоростей тела<br>
&#9;&#9;v_idx = amap[self.body.acceleration_var]      # 6 индексов<br>
&#9;&#9;# индексы внутренних сил<br>
&#9;&#9;f_idx = cmap[self.internal_force]     # 3 индексов<br>
<br>
&#9;&#9;# --- Заполняем якобиан ---<br>
&#9;&#9;# H[f, v]<br>
&#9;&#9;# линейные скорости: +I<br>
&#9;&#9;H[f_idx[0], v_idx[0]] += 1<br>
&#9;&#9;H[f_idx[1], v_idx[1]] += 1<br>
&#9;&#9;H[f_idx[2], v_idx[2]] += 1<br>
<br>
&#9;&#9;# угловые скорости: -[r]_×<br>
&#9;&#9;S = skew(self.r)<br>
&#9;&#9;# порядок v_idx[3:6] — (wx, wy, wz)<br>
&#9;&#9;H[np.ix_(f_idx, v_idx[3:6])] -= S<br>
<br>
<br>
&#9;# -----------------------------------------------------------<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Для коррекции ограничений делаем то же самое.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.update_radius()<br>
&#9;&#9;self.contribute(matrices, index_maps)<br>
&#9;&#9;<br>
&#9;&#9;poserr = matrices[&quot;position_error&quot;]<br>
&#9;&#9;f_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
<br>
&#9;&#9;# --- Позиционная ошибка ---<br>
&#9;&#9;pose = self.body.pose()<br>
&#9;&#9;p = pose.lin<br>
&#9;&#9;e = p + self.r - self.joint_point<br>
<br>
&#9;&#9;poserr[f_idx[0]] += e[0]<br>
&#9;&#9;poserr[f_idx[1]] += e[1]<br>
&#9;&#9;poserr[f_idx[2]] += e[2]<br>
<br>
<br>
class RevoluteJoint3D(Contribution):<br>
&#9;&quot;&quot;&quot;<br>
&#9;3D револьвентный шарнир в смысле 2D-версии:<br>
&#9;совпадение двух точек на двух телах.<br>
&#9;<br>
&#9;Ограничения: (pA + rA) - (pB + rB) = 0   (3 eq)<br>
&#9;Не ограничивает ориентацию!<br>
&#9;Даёт 3 степени свободы на вращение.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self,<br>
&#9;&#9;&#9;&#9;bodyA,<br>
&#9;&#9;&#9;&#9;bodyB,<br>
&#9;&#9;&#9;&#9;joint_point_world: np.ndarray,<br>
&#9;&#9;&#9;&#9;assembler=None):<br>
<br>
&#9;&#9;self.bodyA = bodyA<br>
&#9;&#9;self.bodyB = bodyB<br>
<br>
&#9;&#9;# Внутренняя реакция — вектор из 3 компонент<br>
&#9;&#9;self.internal_force = Variable(&quot;F_rev3d&quot;, size=3,<br>
&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;&#9;tag=&quot;force&quot;)<br>
<br>
&#9;&#9;# локальные точки крепления<br>
&#9;&#9;poseA = self.bodyA.pose()<br>
&#9;&#9;poseB = self.bodyB.pose()<br>
<br>
&#9;&#9;self.rA_local = poseA.inverse_transform_point(joint_point_world)<br>
&#9;&#9;self.rB_local = poseB.inverse_transform_point(joint_point_world)<br>
<br>
&#9;&#9;# обновляем мировую геометрию<br>
&#9;&#9;self.update_kinematics()<br>
<br>
&#9;&#9;super().__init__([bodyA.velocity, bodyB.velocity, self.internal_force],<br>
&#9;&#9;&#9;&#9;&#9;&#9;assembler=assembler)<br>
<br>
&#9;# --------------------------------------------------------------<br>
<br>
&#9;def update_kinematics(self):<br>
&#9;&#9;poseA = self.bodyA.pose()<br>
&#9;&#9;poseB = self.bodyB.pose()<br>
<br>
&#9;&#9;self.pA = poseA.lin<br>
&#9;&#9;self.pB = poseB.lin<br>
<br>
&#9;&#9;self.rA = poseA.transform_vector(self.rA_local)<br>
&#9;&#9;self.rB = poseB.transform_vector(self.rB_local)<br>
<br>
&#9;# --------------------------------------------------------------<br>
<br>
&#9;def contribute(self, matrices, index_maps):<br>
&#9;&#9;self.update_kinematics()<br>
<br>
&#9;&#9;H = matrices[&quot;holonomic&quot;]<br>
<br>
&#9;&#9;amap = index_maps[&quot;acceleration&quot;]<br>
&#9;&#9;cmap = index_maps[&quot;force&quot;]<br>
<br>
&#9;&#9;vA = amap[self.bodyA.velocity]<br>
&#9;&#9;vB = amap[self.bodyB.velocity]<br>
<br>
&#9;&#9;F = cmap[self.internal_force]  # 3 строки<br>
<br>
&#9;&#9;# Матрицы скосов радиусов<br>
&#9;&#9;SA = skew(self.rA)<br>
&#9;&#9;SB = skew(self.rB)<br>
<br>
&#9;&#9;# dφ/dvA_lin = +I<br>
&#9;&#9;H[np.ix_(F, vA[0:3])] += np.eye(3)<br>
<br>
&#9;&#9;# dφ/dvA_ang = -skew(rA)<br>
&#9;&#9;H[np.ix_(F, vA[3:6])] += -SA<br>
<br>
&#9;&#9;# dφ/dvB_lin = -I<br>
&#9;&#9;H[np.ix_(F, vB[0:3])] += -np.eye(3)<br>
<br>
&#9;&#9;# dφ/dvB_ang = +skew(rB)<br>
&#9;&#9;H[np.ix_(F, vB[3:6])] += SB<br>
<br>
<br>
&#9;# --------------------------------------------------------------<br>
<br>
&#9;def contribute_for_constraints_correction(self, matrices, index_maps):<br>
&#9;&#9;self.update_kinematics()<br>
&#9;&#9;self.contribute(matrices, index_maps)<br>
&#9;&#9;cmap = index_maps[&quot;force&quot;]<br>
&#9;&#9;F = cmap[self.internal_force]  # 3 строки<br>
&#9;&#9;poserr = matrices[&quot;position_error&quot;]<br>
&#9;&#9;# позиционная ошибка: φ = (pA+rA) - (pB+rB)<br>
&#9;&#9;err = (self.pA + self.rA) - (self.pB + self.rB)<br>
<br>
&#9;&#9;poserr[F[0]] += err[0]<br>
&#9;&#9;poserr[F[1]] += err[1]<br>
&#9;&#9;poserr[F[2]] += err[2]<br>
<!-- END SCAT CODE -->
</body>
</html>
