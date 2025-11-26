<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody2d_2.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# &quot;&quot;&quot;<br>
# Вторая версия модели многотельной системы в 2D<br>
# &quot;&quot;&quot;<br>
<br>
<br>
# from typing import List, Dict<br>
# import numpy as np<br>
# from termin.fem.assembler import Variable, Contribution<br>
# from termin.geombase.pose2 import Pose2<br>
# from termin.geombase.screw import Screw2<br>
# from termin.fem.inertia2d import SpatialInertia2D<br>
<br>
<br>
# class RigidBody2D(Contribution):<br>
#     &quot;&quot;&quot;<br>
#     Твердое тело в плоскости (3 СС: x, y, θ).<br>
#     Поддерживает внецентренную инерцию (смещённый ЦМ).<br>
#     &quot;&quot;&quot;<br>
<br>
<br>
#     def __init__(self, <br>
#                 inertia: SpatialInertia2D, <br>
#                 gravity: np.ndarray = None,<br>
#                 assembler=None, <br>
#                 name=&quot;rbody2d&quot;,<br>
#                 angle_normalize: callable = None<br>
#             ):<br>
#         self.acceleration_var = Variable(<br>
#             name + &quot;_acc&quot;, size=3, tag=&quot;acceleration&quot;<br>
#         )  # [ax, ay, α] в глобальной СК<br>
#         self.velocity_var = Variable(<br>
#             name + &quot;_vel&quot;, size=3, tag=&quot;velocity&quot;<br>
#         )  # [vx, vy, ω] в глобальной СК<br>
#         self.pose_var = Variable(<br>
#             name + &quot;_pos&quot;, size=3, tag=&quot;position&quot;<br>
#         )  # [x, y, θ] в глобальной СК<br>
#         self.inertia = inertia<br>
#         self.gravity = (<br>
#             np.array([0.0, -9.81]) if gravity is None else np.asarray(gravity, float).reshape(2)<br>
#         )<br>
#         super().__init__(<br>
#             [self.acceleration_var, self.velocity_var, self.pose_var], assembler=assembler<br>
#             )<br>
#         self.angle_normalize = angle_normalize<br>
<br>
#     def pose(self):<br>
#         return Pose2(<br>
#             lin=self.pose_var.value[0:2].copy(),<br>
#             ang=float(self.pose_var.value[2].copy())<br>
#         )<br>
        <br>
#     # ---------- ВКЛАД В СИСТЕМУ ----------<br>
#     def contribute(self, matrices, index_maps):<br>
#         self.contribute_to_mass_matrix(matrices, index_maps)<br>
#         # Гравитация в глобальной СК<br>
#         a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
#         b = matrices[&quot;load&quot;]<br>
<br>
#         # 1) Инерционный скоростной bias, она же сила Кориолиса: v×* (I v)<br>
#         v = self.velocity_var.value<br>
#         velscr = Screw2(lin=v[0:2], ang=v[2])<br>
#         velscr_local = velscr.rotated_by(self.pose().inverse())<br>
#         bias_wrench = self.inertia.bias_wrench(velscr_local) <br>
#         bw_world = bias_wrench.rotated_by(self.pose())<br>
#         b[a_idx] += bw_world.to_vector_vw_order()<br>
<br>
#         # 2) Гравитационная сила<br>
#         gravity_local = self.pose().inverse().rotate_vector(self.gravity)<br>
#         gr_wrench_local = self.inertia.gravity_wrench(gravity_local).to_vector_vw_order()<br>
#         gr_wrench_world = Screw2.from_vector_vw_order(gr_wrench_local).rotated_by(self.pose())<br>
#         b[a_idx] += gr_wrench_world.to_vector_vw_order()<br>
<br>
#     def contribute_for_constraints_correction(self, matrices, index_maps):<br>
#         self.contribute_to_mass_matrix(matrices, index_maps)<br>
    <br>
#     def contribute_to_mass_matrix(self, matrices, index_maps):<br>
#         A = matrices[&quot;mass&quot;]<br>
#         amap = index_maps[&quot;acceleration&quot;]<br>
#         a_idx = amap[self.acceleration_var]<br>
#         IM = self.inertia.to_matrix_vw_order()<br>
#         A[np.ix_(a_idx, a_idx)] += IM<br>
<br>
#     def finish_timestep(self, dt):<br>
#         # semimplicit Euler<br>
#         v = self.velocity_var.value<br>
#         a = self.acceleration_var.value<br>
#         v += a * dt<br>
#         self.velocity_var.value = v<br>
#         self.pose_var.value += v * dt<br>
<br>
<br>
#         if self.angle_normalize is not None:<br>
#             self.pose_var.value[2] = self.angle_normalize(self.pose_var.value[2])<br>
<br>
<br>
# class ForceOnBody2D(Contribution):<br>
#     &quot;&quot;&quot;<br>
#     Внешняя сила и момент, приложенные к твердому телу в 2D.<br>
#     &quot;&quot;&quot;<br>
#     def __init__(self, body: RigidBody2D, wrench: Screw2,<br>
#                  in_local_frame: bool = False, assembler=None):<br>
#         &quot;&quot;&quot;<br>
#         Args:<br>
#             wrench: Screw2 — сила и момент<br>
#             in_local_frame: если True, сила задана в локальной СК тела<br>
#         &quot;&quot;&quot;<br>
#         self.body = body<br>
#         self.acceleration = body.acceleration_var<br>
#         self.wrench = wrench<br>
#         self.in_local_frame = in_local_frame<br>
#         super().__init__([], assembler=assembler)  # Нет переменных для этой нагрузки<br>
<br>
#     def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
#         &quot;&quot;&quot;<br>
#         Добавить вклад в вектор нагрузок<br>
#         &quot;&quot;&quot;<br>
#         b = matrices[&quot;load&quot;]<br>
#         index_map = index_maps[&quot;acceleration&quot;]<br>
#         a_indices = index_map[self.acceleration]<br>
#         wrench = self.wrench.rotated_by(self.body.pose()) if self.in_local_frame else self.wrench<br>
#         b[a_indices[0]] += wrench.lin[0]<br>
#         b[a_indices[1]] += wrench.lin[1]<br>
#         b[a_indices[2]] += wrench.ang<br>
<br>
<br>
#     def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
#         &quot;&quot;&quot;<br>
#         Внешние силы не влияют на коррекцию ограничений на положения<br>
#         &quot;&quot;&quot;<br>
#         pass<br>
<br>
<br>
# class FixedRotationJoint2D(Contribution):<br>
#     &quot;&quot;&quot;<br>
#     Вращательный шарнир с фиксацией в пространстве (ground revolute joint).<br>
    <br>
#     Фиксирует точку на теле в пространстве, разрешая только вращение вокруг этой точки.<br>
#     Эквивалентно присоединению тела к неподвижному основанию через шарнир.<br>
<br>
#     Соглашение о знаках: Лямбда задаёт силу действующую на тело со стороны шарнира.<br>
#     &quot;&quot;&quot;<br>
#     def __init__(self,<br>
#         body: RigidBody2D,<br>
#         coords_of_joint: np.ndarray = None,<br>
#         assembler=None):<br>
#         &quot;&quot;&quot;<br>
#         Args:<br>
#             body: Твердое тело, к которому применяется шарнир<br>
#             coords_of_joint: Вектор координат шарнира [x, y]<br>
#             assembler: Ассемблер для сборки системы<br>
#         &quot;&quot;&quot;<br>
#         self.body = body<br>
#         self.internal_force = Variable(&quot;F_joint&quot;, size=2, tag=&quot;force&quot;)<br>
        <br>
#         body_pose = self.body.pose()<br>
<br>
#         self.coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else body_pose.lin.copy()<br>
#         self.radius_in_local = body_pose.inverse_transform_point(self.coords_of_joint)<br>
<br>
#         super().__init__([body.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
#     def radius(self):<br>
#         &quot;&quot;&quot;Обновить радиус до тела&quot;&quot;&quot;<br>
#         body_pose = self.body.pose()<br>
#         return body_pose.rotate_vector(self.radius_in_local) # тут достаточно повернуть<br>
<br>
#     def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
#         &quot;&quot;&quot;<br>
#         Добавить вклад в матрицы<br>
#         &quot;&quot;&quot;<br>
#         radius = self.radius()<br>
#         omega = self.body.velocity_var.value[2]<br>
        <br>
#         self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
#         h = matrices[&quot;holonomic_rhs&quot;]<br>
#         constraints_map = index_maps[&quot;force&quot;]<br>
#         F_indices = constraints_map[self.internal_force]<br>
<br>
#         bias = - (omega**2) * radius<br>
#         h[F_indices[0]] += bias[0]<br>
#         h[F_indices[1]] += bias[1]<br>
<br>
<br>
#     def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
#         &quot;&quot;&quot;<br>
#         Добавить вклад в матрицы ограничений на положения<br>
#         &quot;&quot;&quot;<br>
#         radius = self.radius()<br>
#         H = matrices[&quot;holonomic&quot;]  # Матрица ограничений<br>
#         index_map = index_maps[&quot;acceleration&quot;]<br>
#         constraint_map = index_maps[&quot;force&quot;]<br>
#         F_indices = constraint_map[self.internal_force]<br>
#         a_indices = index_map[self.body.acceleration_var]<br>
<br>
#         # Вклад в матрицу ограничений от связи шарнира<br>
#         H[np.ix_(F_indices, a_indices)] += - np.array([<br>
#             [1.0, 0.0, -radius[1]],<br>
#             [0.0, 1.0,  radius[0]]<br>
#         ])<br>
<br>
<br>
#     def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
#         &quot;&quot;&quot;<br>
#         Добавить вклад в матрицы для коррекции ограничений на положения<br>
#         &quot;&quot;&quot;<br>
#         radius = self.radius()<br>
#         self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
#         constraint_map = index_maps[&quot;force&quot;]<br>
#         poserr = matrices[&quot;position_error&quot;]<br>
#         F_indices = constraint_map[self.internal_force]<br>
<br>
#         poserr[F_indices] += (self.body.pose().lin + radius) - self.coords_of_joint<br>
<br>
# class RevoluteJoint2D(Contribution):<br>
#     &quot;&quot;&quot;<br>
#     Двухтелый вращательный шарнир (revolute joint).<br>
#     Связывает две точки на двух телах: точка A должна совпадать с точкой B.<br>
#     &quot;&quot;&quot;<br>
<br>
#     def __init__(self,<br>
#         bodyA: RigidBody2D,<br>
#         bodyB: RigidBody2D,<br>
#         coords_of_joint: np.ndarray = None,<br>
#         assembler=None):<br>
<br>
#         coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else bodyA.pose().lin.copy()<br>
<br>
#         self.bodyA = bodyA<br>
#         self.bodyB = bodyB<br>
<br>
#         # переменная внутренней силы (двухкомпонентная)<br>
#         self.internal_force = Variable(&quot;F_rev&quot;, size=2, tag=&quot;force&quot;)<br>
<br>
#         # вычисляем локальные точки для обоих тел<br>
#         poseA = self.bodyA.pose()<br>
#         poseB = self.bodyB.pose()<br>
<br>
#         self.rA_local = poseA.inverse_transform_point(coords_of_joint)<br>
#         self.rB_local = poseB.inverse_transform_point(coords_of_joint)<br>
<br>
#         # актуализируем глобальные вектор-радиусы<br>
#         self.update_radii()<br>
<br>
#         super().__init__([bodyA.acceleration_var, bodyB.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
#     def update_radii(self):<br>
#         &quot;&quot;&quot;Пересчитать глобальные радиусы до опорных точек&quot;&quot;&quot;<br>
#         poseA = self.bodyA.pose()<br>
#         poseB = self.bodyB.pose()<br>
#         self.rA = poseA.rotate_vector(self.rA_local)<br>
#         self.rB = poseB.rotate_vector(self.rB_local)<br>
<br>
#     def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
#         &quot;&quot;&quot;Добавляет вклад в матрицы для ускорений&quot;&quot;&quot;<br>
<br>
#         # радиусы актуализируем каждый вызов<br>
#         self.update_radii()<br>
<br>
#         self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
#         h = matrices[&quot;holonomic_rhs&quot;]<br>
#         cmap = index_maps[&quot;force&quot;]<br>
#         F_indices = cmap[self.internal_force]<br>
<br>
#         omegaA = self.bodyA.velocity_var.value[2]<br>
#         omegaB = self.bodyB.velocity_var.value[2]<br>
<br>
#         bias = (omegaA**2) * self.rA - (omegaB**2) * self.rB<br>
#         h[F_indices[0]] += -bias[0]<br>
#         h[F_indices[1]] += -bias[1]<br>
<br>
#     def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
#         &quot;&quot;&quot;Добавляет вклад в матрицу ограничений на положения&quot;&quot;&quot;<br>
#         H = matrices[&quot;holonomic&quot;]<br>
<br>
#         amap = index_maps[&quot;acceleration&quot;]<br>
#         cmap = index_maps[&quot;force&quot;]<br>
#         aA = amap[self.bodyA.acceleration_var]<br>
#         aB = amap[self.bodyB.acceleration_var]<br>
#         F = cmap[self.internal_force]  # 2 строки ограничений<br>
<br>
#         # Вклад в матрицу ограничений от связи шарнира<br>
#         H[np.ix_(F, aA)] += np.array([<br>
#             [ 1.0,  0.0, -self.rA[1]],<br>
#             [ 0.0,  1.0,  self.rA[0]]<br>
#         ])  <br>
<br>
#         H[np.ix_(F, aB)] += np.array([<br>
#             [-1.0,  0.0,  self.rB[1]],<br>
#             [ 0.0, -1.0, -self.rB[0]]<br>
#         ])<br>
<br>
<br>
#     def contribute_for_constraints_correction(self, matrices, index_maps):<br>
#         &quot;&quot;&quot;Для позиционной и скоростной проекции&quot;&quot;&quot;<br>
#         self.update_radii()<br>
#         self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
#         poserr = matrices[&quot;position_error&quot;]<br>
#         cmap = index_maps[&quot;force&quot;]<br>
#         F = cmap[self.internal_force]  # 2 строки ограничений<br>
<br>
#         # ---------- позиционная ошибка ----------<br>
#         # φ = cA - cB = (pA + rA) - (pB + rB)<br>
#         pA = self.bodyA.pose().lin<br>
#         pB = self.bodyB.pose().lin<br>
<br>
#         poserr[F] += (pA + self.rA) - (pB + self.rB)<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
