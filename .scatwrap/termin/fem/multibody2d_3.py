<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody2d_3.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;
Соглашение о уравнениях такого, что все уравнения собираются в локальной СК тела.
Глобальная поза тела хранится отдельно и используется только для обновления геометрии.

Преобразования следуют конвенции локальная система -&gt; мировая система:
    p_world = P(q) @ p_local
    p_world = R(θ) @ p_local
&quot;&quot;&quot;

from typing import List, Dict
import numpy as np
from termin.fem.assembler import Variable, Contribution
from termin.geombase.pose2 import Pose2
from termin.geombase.screw import Screw2
from termin.fem.inertia2d import SpatialInertia2D


class RigidBody2D(Contribution):
    &quot;&quot;&quot;
    Твёрдое тело в 2D, все расчёты выполняются в локальной СК тела.
    Глобальная поза хранится отдельно и используется только для обновления геометрии.
    &quot;&quot;&quot;

    def __init__(
        self,
        inertia: SpatialInertia2D,
        gravity: np.ndarray = None,
        assembler=None,
        name=&quot;rbody2d&quot;,
        angle_normalize: callable = None,
    ):
        self.acceleration_var = Variable(name + &quot;_acc&quot;, size=3, tag=&quot;acceleration&quot;)  # [ax, ay, α]_local
        self.velocity_var = Variable(name + &quot;_vel&quot;, size=3, tag=&quot;velocity&quot;)          # [vx, vy, ω]_local
        self.local_pose_var = Variable(name + &quot;_pos&quot;, size=3, tag=&quot;position&quot;)              # [x, y, θ]_local (для интеграции лок. движения)

        # глобальная поза тела (Pose2)
        self.global_pose = Pose2(lin=np.zeros(2), ang=0.0)

        self.inertia = inertia
        self.angle_normalize = angle_normalize

        # сила тяжести задаётся в мировых координатах
        self.gravity = np.array([0.0, -9.81]) if gravity is None else np.asarray(gravity, float).reshape(2)

        super().__init__([self.acceleration_var, self.velocity_var, self.local_pose_var], assembler=assembler)

    # ---------- геттеры ----------
    def pose(self) -&gt; Pose2:
        return self.global_pose

    def set_pose(self, pose: Pose2):
        self.global_pose = pose

    # ---------- вклад в систему ----------
    def contribute(self, matrices, index_maps):
        &quot;&quot;&quot;
        Вклад тела в уравнения движения:
            I * a + v×* (I v) = F
        Все в локальной СК.
        &quot;&quot;&quot;
        self.contribute_to_mass_matrix(matrices, index_maps)

        b = matrices[&quot;load&quot;]
        a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]

        v_local = Screw2.from_vector_vw_order(self.velocity_var.value)
        bias = self.inertia.bias_wrench(v_local)

        # гравитация в локальной СК тела
        g_local = self.global_pose.inverse().rotate_vector(self.gravity)
        grav = self.inertia.gravity_wrench(g_local)

        b[a_idx] += bias.to_vector_vw_order() + grav.to_vector_vw_order()

    def contribute_for_constraints_correction(self, matrices, index_maps):
        self.contribute_to_mass_matrix(matrices, index_maps)

    def contribute_to_mass_matrix(self, matrices, index_maps):
        &quot;&quot;&quot;
        Массовая матрица в локальной СК (никаких поворотов).
        &quot;&quot;&quot;
        A = matrices[&quot;mass&quot;]
        a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]
        A[np.ix_(a_idx, a_idx)] += self.inertia.to_matrix_vw_order()

    # ---------- интеграция шага ----------
    def finish_timestep(self, dt):
        &quot;&quot;&quot;
        После интеграции уравнений ускорений и скоростей обновляем локальные переменные,
        затем обновляем глобальную позу, используя локальное смещение.
        После этого локальная поза обнуляется (тело возвращается в свою СК).
        &quot;&quot;&quot;
        v = self.velocity_var.value
        a = self.acceleration_var.value
        v += a * dt
        self.velocity_var.value = v

        # локальное приращение позы (интеграция по локальной СК)
        delta_pose_local = Pose2(
            lin=v[0:2] * dt,
            ang=v[2] * dt,
        )

        # обновляем глобальную позу тела
        self.global_pose = self.global_pose @ delta_pose_local

        # сбрасываем локальную позу
        self.local_pose_var.value[:] = 0.0

        if self.angle_normalize is not None:
            self.global_pose.ang = self.angle_normalize(self.global_pose.ang)

    def finish_correction_step(self):
        &quot;&quot;&quot;
        После коррекции позиций сбрасываем локальную позу.
        &quot;&quot;&quot;
        self.global_pose = self.global_pose @ Pose2(
            lin=self.local_pose_var.value[0:2],
            ang=self.local_pose_var.value[2],
        )
        self.local_pose_var.value[:] = 0.0

class ForceOnBody2D(Contribution):
    &quot;&quot;&quot;Внешняя сила и момент в локальной СК тела.&quot;&quot;&quot;
    def __init__(self, body: RigidBody2D, wrench: Screw2,
                 in_local_frame: bool = True, assembler=None):
        self.body = body
        self.acceleration = body.acceleration_var
        self.wrench_local = wrench if in_local_frame else wrench.rotated_by(body.pose().inverse())
        super().__init__([], assembler=assembler)

    def contribute(self, matrices, index_maps):
        b = matrices[&quot;load&quot;]
        a_indices = index_maps[&quot;acceleration&quot;][self.acceleration]
        b[a_indices] += self.wrench_local.to_vector_vw_order()


class FixedRotationJoint2D(Contribution):
    &quot;&quot;&quot;
    Ground revolute joint.
    Все уравнения формулируются в локальной СК тела.
    Лямбда — сила, действующая на тело, в локальной СК тела.
    &quot;&quot;&quot;
    def __init__(self,
                 body: RigidBody2D,
                 coords_of_joint: np.ndarray = None,
                 assembler=None):
        self.body = body
        self.internal_force = Variable(&quot;F_joint&quot;, size=2, tag=&quot;force&quot;)

        pose = self.body.pose()
        self.coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else pose.lin.copy()
        # фиксируем локальные координаты точки шарнира на теле
        self.r_local = pose.inverse_transform_point(self.coords_of_joint)
        
        super().__init__([body.acceleration_var, self.internal_force], assembler=assembler)

    def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        # линейная часть (Якобиан) — сразу в H
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        # правую часть — квадратичные (центростремительные) члены, тоже в локале
        h = matrices[&quot;holonomic_rhs&quot;]
        F_idx = index_maps[&quot;force&quot;][self.internal_force]

        omega = float(self.body.velocity_var.value[2])
        bias = - (omega ** 2) * self.r_local
        h[F_idx] += bias

    def radius(self) -&gt; np.ndarray:
        &quot;&quot;&quot;Радиус шарнира в глобальной СК.&quot;&quot;&quot;
        pose = self.body.pose()
        r_world = pose.rotate_vector(self.r_local)
        return r_world

    def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        &quot;&quot;&quot;
        Ограничение в локале тела:
          a_lin + α×r_local + (квадр.члены) = 0
        В матрицу кладём линейную часть по ускорениям:
          H * [a_x, a_y, α]^T  с блоком  -[ I,  perp(r_local) ]
        где perp(r) = [-r_y, r_x].
        &quot;&quot;&quot;
        H = matrices[&quot;holonomic&quot;]
        a_idx = index_maps[&quot;acceleration&quot;][self.body.acceleration_var]
        F_idx = index_maps[&quot;force&quot;][self.internal_force]

        r = self.r_local
        H[np.ix_(F_idx, a_idx)] += -np.array([
            [1.0, 0.0, -r[1]],
            [0.0, 1.0,  r[0]],
        ])

    def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        &quot;&quot;&quot;
        Позиционная ошибка тоже в локале тела:
          φ_local = R^T (p - c_world) + r_local
        где p — мировая позиция опорной точки тела, c_world — фиксированная мировая точка шарнира.
        &quot;&quot;&quot;
        # Якобиан для коррекции такой же
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        poserr = matrices[&quot;position_error&quot;]
        F_idx = index_maps[&quot;force&quot;][self.internal_force]

        pose = self.body.pose()        
        perr = pose.inverse_rotate_vector(pose.lin - self.coords_of_joint)  + self.r_local
        poserr[F_idx] -= perr


class RevoluteJoint2D(Contribution):
    &quot;&quot;&quot;
    Двухтелый вращательный шарнир (revolute joint):
    связь формулируется в локальной СК тела A.
    &quot;&quot;&quot;

    def __init__(self,
                 bodyA: RigidBody2D,
                 bodyB: RigidBody2D,
                 coords_of_joint: np.ndarray = None,
                 assembler=None):

        cW = coords_of_joint.copy() if coords_of_joint is not None else bodyA.pose().lin.copy()

        self.bodyA = bodyA
        self.bodyB = bodyB

        # 2-компонентная лямбда силы в СК A
        self.internal_force = Variable(&quot;F_rev&quot;, size=2, tag=&quot;force&quot;)

        poseA = self.bodyA.pose()
        poseB = self.bodyB.pose()

        # локальные координаты точки шарнира на каждом теле
        self.rA_local = poseA.inverse_transform_point(cW)  # в СК A
        self.rB_local = poseB.inverse_transform_point(cW)  # в СК B

        # кэш для rB, выраженного в СК A, и для R_AB
        #self.R_AB = np.eye(2)
        self.poseAB = Pose2.identity()
        self.rB_in_A = self.rB_local.copy()  # будет обновляться

        self.update_local_view()

        super().__init__([bodyA.acceleration_var, bodyB.acceleration_var, self.internal_force], assembler=assembler)

    @staticmethod
    def _perp_col(r: np.ndarray) -&gt; np.ndarray:
        &quot;&quot;&quot;перпендикуляр к r: α×r = [ -α r_y, α r_x ] ⇒ столбец для α&quot;&quot;&quot;
        return np.array([-r[1], r[0]])

    def update_local_view(self):
        &quot;&quot;&quot;Обновить R_AB и rB, выраженные в СК A.&quot;&quot;&quot;
        poseA = self.bodyA.pose()
        poseB = self.bodyB.pose()
        #cA, sA = np.cos(poseA.ang), np.sin(poseA.ang)
        #cB, sB = np.cos(poseB.ang), np.sin(poseB.ang)
        #R_A = np.array([[cA, -sA],[sA, cA]])
        #R_B = np.array([[cB, -sB],[sB, cB]])
        #self.R_AB = R_A.T @ R_B
        self.poseAB = poseA.inverse() @ poseB
        self.rB_in_A = self.poseAB.rotate_vector(self.rB_local)  # r_B, выраженный в СК A

    def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        self.update_local_view()
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        h = matrices[&quot;holonomic_rhs&quot;]
        F = index_maps[&quot;force&quot;][self.internal_force]

        omegaA = float(self.bodyA.velocity_var.value[2])
        omegaB = float(self.bodyB.velocity_var.value[2])

        # квадратичные члены (центростремительные) в правую часть, всё в СК A:
        # bias = (ωA^2) * rA  - (ωB^2) * (R_AB rB)
        rA = self.rA_local
        rB_A = self.rB_in_A
        bias = (omegaA**2) * rA - (omegaB**2) * rB_A

        # по принятой конвенции — добавляем -bias
        h[F] += -bias

    def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        &quot;&quot;&quot;
        В СК A:
          aA_lin + αA×rA  -  R_AB (aB_lin + αB×rB)  + квадр.члены = 0
        Линейная часть по ускорениям попадает в матрицу H.
        &quot;&quot;&quot;
        H = matrices[&quot;holonomic&quot;]
        aA = index_maps[&quot;acceleration&quot;][self.bodyA.acceleration_var]
        aB = index_maps[&quot;acceleration&quot;][self.bodyB.acceleration_var]
        F  = index_maps[&quot;force&quot;][self.internal_force]  # 2 строки

        rA = self.rA_local
        rB_A = self.rB_in_A
        R = self.poseAB.rotation_matrix()

        # блок по aA (в СК A)
        H[np.ix_(F, aA)] += np.array([
            [ 1.0,  0.0, -rA[1]],
            [ 0.0,  1.0,  rA[0]],
        ])

        # блок по aB, выраженный в СК A:
        # - [ R,  R * perp(rB) ], где perp(r) = [-r_y, r_x]
        col_alphaB = self.poseAB.rotate_vector(self._perp_col(self.rB_local))  # = perp(rB_A)
        H[np.ix_(F, aB)] += np.array([
            [-R[0,0], -R[0,1],  col_alphaB[0]],
            [-R[1,0], -R[1,1],  col_alphaB[1]],
        ])

    def contribute_for_constraints_correction(self, matrices, index_maps):
        &quot;&quot;&quot;
        Позиционная ошибка тоже в СК A:
          φ_A = R_A^T * [ (pA + R_A rA) - (pB + R_B rB) ]
              = (R_A^T(pA - pB)) + rA - R_AB rB
        &quot;&quot;&quot;
        self.update_local_view()
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        poserr = matrices[&quot;position_error&quot;]
        F = index_maps[&quot;force&quot;][self.internal_force]

        pA = self.bodyA.pose().lin
        pB = self.bodyB.pose().lin

        poseA = self.bodyA.pose()
        R_A_T = poseA.inverse().rotation_matrix()

        delta_p_A = R_A_T @ (pA - pB)
        rA = self.rA_local
        rB_A = self.rB_in_A

        poserr[F] += delta_p_A + rA - rB_A

</code></pre>
</body>
</html>
