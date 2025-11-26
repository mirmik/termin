<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody2d_2.py</title>
</head>
<body>
<pre><code>
# &quot;&quot;&quot;
# Вторая версия модели многотельной системы в 2D
# &quot;&quot;&quot;


# from typing import List, Dict
# import numpy as np
# from termin.fem.assembler import Variable, Contribution
# from termin.geombase.pose2 import Pose2
# from termin.geombase.screw import Screw2
# from termin.fem.inertia2d import SpatialInertia2D


# class RigidBody2D(Contribution):
#     &quot;&quot;&quot;
#     Твердое тело в плоскости (3 СС: x, y, θ).
#     Поддерживает внецентренную инерцию (смещённый ЦМ).
#     &quot;&quot;&quot;


#     def __init__(self, 
#                 inertia: SpatialInertia2D, 
#                 gravity: np.ndarray = None,
#                 assembler=None, 
#                 name=&quot;rbody2d&quot;,
#                 angle_normalize: callable = None
#             ):
#         self.acceleration_var = Variable(
#             name + &quot;_acc&quot;, size=3, tag=&quot;acceleration&quot;
#         )  # [ax, ay, α] в глобальной СК
#         self.velocity_var = Variable(
#             name + &quot;_vel&quot;, size=3, tag=&quot;velocity&quot;
#         )  # [vx, vy, ω] в глобальной СК
#         self.pose_var = Variable(
#             name + &quot;_pos&quot;, size=3, tag=&quot;position&quot;
#         )  # [x, y, θ] в глобальной СК
#         self.inertia = inertia
#         self.gravity = (
#             np.array([0.0, -9.81]) if gravity is None else np.asarray(gravity, float).reshape(2)
#         )
#         super().__init__(
#             [self.acceleration_var, self.velocity_var, self.pose_var], assembler=assembler
#             )
#         self.angle_normalize = angle_normalize

#     def pose(self):
#         return Pose2(
#             lin=self.pose_var.value[0:2].copy(),
#             ang=float(self.pose_var.value[2].copy())
#         )
        
#     # ---------- ВКЛАД В СИСТЕМУ ----------
#     def contribute(self, matrices, index_maps):
#         self.contribute_to_mass_matrix(matrices, index_maps)
#         # Гравитация в глобальной СК
#         a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]
#         b = matrices[&quot;load&quot;]

#         # 1) Инерционный скоростной bias, она же сила Кориолиса: v×* (I v)
#         v = self.velocity_var.value
#         velscr = Screw2(lin=v[0:2], ang=v[2])
#         velscr_local = velscr.rotated_by(self.pose().inverse())
#         bias_wrench = self.inertia.bias_wrench(velscr_local) 
#         bw_world = bias_wrench.rotated_by(self.pose())
#         b[a_idx] += bw_world.to_vector_vw_order()

#         # 2) Гравитационная сила
#         gravity_local = self.pose().inverse().rotate_vector(self.gravity)
#         gr_wrench_local = self.inertia.gravity_wrench(gravity_local).to_vector_vw_order()
#         gr_wrench_world = Screw2.from_vector_vw_order(gr_wrench_local).rotated_by(self.pose())
#         b[a_idx] += gr_wrench_world.to_vector_vw_order()

#     def contribute_for_constraints_correction(self, matrices, index_maps):
#         self.contribute_to_mass_matrix(matrices, index_maps)
    
#     def contribute_to_mass_matrix(self, matrices, index_maps):
#         A = matrices[&quot;mass&quot;]
#         amap = index_maps[&quot;acceleration&quot;]
#         a_idx = amap[self.acceleration_var]
#         IM = self.inertia.to_matrix_vw_order()
#         A[np.ix_(a_idx, a_idx)] += IM

#     def finish_timestep(self, dt):
#         # semimplicit Euler
#         v = self.velocity_var.value
#         a = self.acceleration_var.value
#         v += a * dt
#         self.velocity_var.value = v
#         self.pose_var.value += v * dt


#         if self.angle_normalize is not None:
#             self.pose_var.value[2] = self.angle_normalize(self.pose_var.value[2])


# class ForceOnBody2D(Contribution):
#     &quot;&quot;&quot;
#     Внешняя сила и момент, приложенные к твердому телу в 2D.
#     &quot;&quot;&quot;
#     def __init__(self, body: RigidBody2D, wrench: Screw2,
#                  in_local_frame: bool = False, assembler=None):
#         &quot;&quot;&quot;
#         Args:
#             wrench: Screw2 — сила и момент
#             in_local_frame: если True, сила задана в локальной СК тела
#         &quot;&quot;&quot;
#         self.body = body
#         self.acceleration = body.acceleration_var
#         self.wrench = wrench
#         self.in_local_frame = in_local_frame
#         super().__init__([], assembler=assembler)  # Нет переменных для этой нагрузки

#     def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
#         &quot;&quot;&quot;
#         Добавить вклад в вектор нагрузок
#         &quot;&quot;&quot;
#         b = matrices[&quot;load&quot;]
#         index_map = index_maps[&quot;acceleration&quot;]
#         a_indices = index_map[self.acceleration]
#         wrench = self.wrench.rotated_by(self.body.pose()) if self.in_local_frame else self.wrench
#         b[a_indices[0]] += wrench.lin[0]
#         b[a_indices[1]] += wrench.lin[1]
#         b[a_indices[2]] += wrench.ang


#     def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
#         &quot;&quot;&quot;
#         Внешние силы не влияют на коррекцию ограничений на положения
#         &quot;&quot;&quot;
#         pass


# class FixedRotationJoint2D(Contribution):
#     &quot;&quot;&quot;
#     Вращательный шарнир с фиксацией в пространстве (ground revolute joint).
    
#     Фиксирует точку на теле в пространстве, разрешая только вращение вокруг этой точки.
#     Эквивалентно присоединению тела к неподвижному основанию через шарнир.

#     Соглашение о знаках: Лямбда задаёт силу действующую на тело со стороны шарнира.
#     &quot;&quot;&quot;
#     def __init__(self,
#         body: RigidBody2D,
#         coords_of_joint: np.ndarray = None,
#         assembler=None):
#         &quot;&quot;&quot;
#         Args:
#             body: Твердое тело, к которому применяется шарнир
#             coords_of_joint: Вектор координат шарнира [x, y]
#             assembler: Ассемблер для сборки системы
#         &quot;&quot;&quot;
#         self.body = body
#         self.internal_force = Variable(&quot;F_joint&quot;, size=2, tag=&quot;force&quot;)
        
#         body_pose = self.body.pose()

#         self.coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else body_pose.lin.copy()
#         self.radius_in_local = body_pose.inverse_transform_point(self.coords_of_joint)

#         super().__init__([body.acceleration_var, self.internal_force], assembler=assembler)

#     def radius(self):
#         &quot;&quot;&quot;Обновить радиус до тела&quot;&quot;&quot;
#         body_pose = self.body.pose()
#         return body_pose.rotate_vector(self.radius_in_local) # тут достаточно повернуть

#     def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
#         &quot;&quot;&quot;
#         Добавить вклад в матрицы
#         &quot;&quot;&quot;
#         radius = self.radius()
#         omega = self.body.velocity_var.value[2]
        
#         self.contribute_to_holonomic_matrix(matrices, index_maps)

#         h = matrices[&quot;holonomic_rhs&quot;]
#         constraints_map = index_maps[&quot;force&quot;]
#         F_indices = constraints_map[self.internal_force]

#         bias = - (omega**2) * radius
#         h[F_indices[0]] += bias[0]
#         h[F_indices[1]] += bias[1]


#     def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
#         &quot;&quot;&quot;
#         Добавить вклад в матрицы ограничений на положения
#         &quot;&quot;&quot;
#         radius = self.radius()
#         H = matrices[&quot;holonomic&quot;]  # Матрица ограничений
#         index_map = index_maps[&quot;acceleration&quot;]
#         constraint_map = index_maps[&quot;force&quot;]
#         F_indices = constraint_map[self.internal_force]
#         a_indices = index_map[self.body.acceleration_var]

#         # Вклад в матрицу ограничений от связи шарнира
#         H[np.ix_(F_indices, a_indices)] += - np.array([
#             [1.0, 0.0, -radius[1]],
#             [0.0, 1.0,  radius[0]]
#         ])


#     def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
#         &quot;&quot;&quot;
#         Добавить вклад в матрицы для коррекции ограничений на положения
#         &quot;&quot;&quot;
#         radius = self.radius()
#         self.contribute_to_holonomic_matrix(matrices, index_maps)

#         constraint_map = index_maps[&quot;force&quot;]
#         poserr = matrices[&quot;position_error&quot;]
#         F_indices = constraint_map[self.internal_force]

#         poserr[F_indices] += (self.body.pose().lin + radius) - self.coords_of_joint

# class RevoluteJoint2D(Contribution):
#     &quot;&quot;&quot;
#     Двухтелый вращательный шарнир (revolute joint).
#     Связывает две точки на двух телах: точка A должна совпадать с точкой B.
#     &quot;&quot;&quot;

#     def __init__(self,
#         bodyA: RigidBody2D,
#         bodyB: RigidBody2D,
#         coords_of_joint: np.ndarray = None,
#         assembler=None):

#         coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else bodyA.pose().lin.copy()

#         self.bodyA = bodyA
#         self.bodyB = bodyB

#         # переменная внутренней силы (двухкомпонентная)
#         self.internal_force = Variable(&quot;F_rev&quot;, size=2, tag=&quot;force&quot;)

#         # вычисляем локальные точки для обоих тел
#         poseA = self.bodyA.pose()
#         poseB = self.bodyB.pose()

#         self.rA_local = poseA.inverse_transform_point(coords_of_joint)
#         self.rB_local = poseB.inverse_transform_point(coords_of_joint)

#         # актуализируем глобальные вектор-радиусы
#         self.update_radii()

#         super().__init__([bodyA.acceleration_var, bodyB.acceleration_var, self.internal_force], assembler=assembler)

#     def update_radii(self):
#         &quot;&quot;&quot;Пересчитать глобальные радиусы до опорных точек&quot;&quot;&quot;
#         poseA = self.bodyA.pose()
#         poseB = self.bodyB.pose()
#         self.rA = poseA.rotate_vector(self.rA_local)
#         self.rB = poseB.rotate_vector(self.rB_local)

#     def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
#         &quot;&quot;&quot;Добавляет вклад в матрицы для ускорений&quot;&quot;&quot;

#         # радиусы актуализируем каждый вызов
#         self.update_radii()

#         self.contribute_to_holonomic_matrix(matrices, index_maps)

#         h = matrices[&quot;holonomic_rhs&quot;]
#         cmap = index_maps[&quot;force&quot;]
#         F_indices = cmap[self.internal_force]

#         omegaA = self.bodyA.velocity_var.value[2]
#         omegaB = self.bodyB.velocity_var.value[2]

#         bias = (omegaA**2) * self.rA - (omegaB**2) * self.rB
#         h[F_indices[0]] += -bias[0]
#         h[F_indices[1]] += -bias[1]

#     def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
#         &quot;&quot;&quot;Добавляет вклад в матрицу ограничений на положения&quot;&quot;&quot;
#         H = matrices[&quot;holonomic&quot;]

#         amap = index_maps[&quot;acceleration&quot;]
#         cmap = index_maps[&quot;force&quot;]
#         aA = amap[self.bodyA.acceleration_var]
#         aB = amap[self.bodyB.acceleration_var]
#         F = cmap[self.internal_force]  # 2 строки ограничений

#         # Вклад в матрицу ограничений от связи шарнира
#         H[np.ix_(F, aA)] += np.array([
#             [ 1.0,  0.0, -self.rA[1]],
#             [ 0.0,  1.0,  self.rA[0]]
#         ])  

#         H[np.ix_(F, aB)] += np.array([
#             [-1.0,  0.0,  self.rB[1]],
#             [ 0.0, -1.0, -self.rB[0]]
#         ])


#     def contribute_for_constraints_correction(self, matrices, index_maps):
#         &quot;&quot;&quot;Для позиционной и скоростной проекции&quot;&quot;&quot;
#         self.update_radii()
#         self.contribute_to_holonomic_matrix(matrices, index_maps)
#         poserr = matrices[&quot;position_error&quot;]
#         cmap = index_maps[&quot;force&quot;]
#         F = cmap[self.internal_force]  # 2 строки ограничений

#         # ---------- позиционная ошибка ----------
#         # φ = cA - cB = (pA + rA) - (pB + rB)
#         pA = self.bodyA.pose().lin
#         pB = self.bodyB.pose().lin

#         poserr[F] += (pA + self.rA) - (pB + self.rB)


</code></pre>
</body>
</html>
