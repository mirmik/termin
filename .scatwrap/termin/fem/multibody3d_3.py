<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody3d_3.py</title>
</head>
<body>
<pre><code>
from typing import List, Dict
import numpy as np

from termin.fem.assembler import Variable, Contribution
from termin.geombase.pose3 import Pose3
from termin.geombase.screw import Screw3
from termin.fem.inertia3d import SpatialInertia3D


&quot;&quot;&quot;
Соглашение такое же, как в 2D-версии:

Все уравнения собираются в локальной СК тела.
Глобальная поза тела хранится отдельно и используется только для обновления геометрии.

Преобразования следуют конвенции локальная система -&gt; мировая система:
    p_world = P(q) @ p_local
&quot;&quot;&quot;

def _skew(r: np.ndarray) -&gt; np.ndarray:
    &quot;&quot;&quot;Матрица векторного произведения:  r×x = skew(r) @ x.&quot;&quot;&quot;
    rx, ry, rz = r
    return np.array([
        [   0.0, -rz,   ry],
        [   rz,  0.0, -rx],
        [  -ry,  rx,  0.0],
    ], dtype=float)

def quat_normalize(q):
    return q / np.linalg.norm(q)

def quat_mul(q1, q2):
    &quot;&quot;&quot;Кватернионное произведение q1*q2 (оба в формате [x,y,z,w]).&quot;&quot;&quot;
    x1,y1,z1,w1 = q1
    x2,y2,z2,w2 = q2
    return np.array([
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 + y1*w2 + z1*x2 - x1*z2,
        w1*z2 + z1*w2 + x1*y2 - y1*x2,
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
    ])

def quat_from_small_angle(dθ):
    &quot;&quot;&quot;Создать кватернион вращения из малого углового вектора dθ.&quot;&quot;&quot;
    θ = np.linalg.norm(dθ)
    if θ &lt; 1e-12:
        # линеаризация
        return quat_normalize(np.array([0.5*dθ[0], 0.5*dθ[1], 0.5*dθ[2], 1.0]))
    axis = dθ / θ
    s = np.sin(0.5 * θ)
    return np.array([axis[0]*s, axis[1]*s, axis[2]*s, np.cos(0.5*θ)])



class RigidBody3D(Contribution):
    &quot;&quot;&quot;
    Твёрдое тело в 3D, все расчёты выполняются в локальной СК тела.
    Глобальная поза хранится отдельно и используется только для обновления геометрии.

    Порядок пространственных векторов (vw_order):
        [ v_x, v_y, v_z, ω_x, ω_y, ω_z ]
    &quot;&quot;&quot;

    def __init__(
        self,
        inertia: SpatialInertia3D,
        gravity: np.ndarray = None,
        assembler=None,
        name: str = &quot;rbody3d&quot;,
        angle_normalize: callable = None,
    ):
        # [a_lin(3), α(3)] в локальной СК
        self.acceleration_var = Variable(name + &quot;_acc&quot;, size=6, tag=&quot;acceleration&quot;)
        # [v_lin(3), ω(3)] в локальной СК
        self.velocity_var = Variable(name + &quot;_vel&quot;, size=6, tag=&quot;velocity&quot;)
        # [Δx(3), Δφ(3)] локальная приращённая поза для интеграции
        self.local_pose_var = Variable(name + &quot;_pos&quot;, size=6, tag=&quot;position&quot;)

        # глобальная поза тела
        self.global_pose = Pose3(lin=np.zeros(3), ang=np.array([0.0, 0.0, 0.0, 1.0]))  # единичный кватернион

        self.inertia = inertia
        self.angle_normalize = angle_normalize

        # сила тяжести задаётся в мировых координатах
        # по аналогии с 2D: -g по оси y
        if gravity is None:
            self.gravity = np.array([0.0, -9.81, 0.0], dtype=float)
        else:
            self.gravity = np.asarray(gravity, float).reshape(3)

        super().__init__([self.acceleration_var, self.velocity_var, self.local_pose_var],
                         assembler=assembler)

    # ---------- геттеры ----------
    def pose(self) -&gt; Pose3:
        return self.global_pose

    def set_pose(self, pose: Pose3):
        self.global_pose = pose

    # ---------- вклад в систему ----------
    def contribute(self, matrices, index_maps):
        &quot;&quot;&quot;
        Вклад тела в уравнения движения (в локальной СК):
            I * a + v×* (I v) = F
        &quot;&quot;&quot;
        self.contribute_to_mass_matrix(matrices, index_maps)

        b = matrices[&quot;load&quot;]
        a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]

        v_local = Screw3.from_vector_vw_order(self.velocity_var.value)
        bias = self.inertia.bias_wrench(v_local)

        # гравитация в локальной СК тела
        g_local = self.global_pose.inverse().rotate_vector(self.gravity)
        grav = self.inertia.gravity_wrench(g_local)

        b[a_idx] += bias.to_vector_vw_order() + grav.to_vector_vw_order()

    def contribute_for_constraints_correction(self, matrices, index_maps):
        self.contribute_to_mass_matrix(matrices, index_maps)

    def contribute_to_mass_matrix(self, matrices, index_maps):
        &quot;&quot;&quot;
        Массовая матрица в локальной СК.
        &quot;&quot;&quot;
        A = matrices[&quot;mass&quot;]
        a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]
        A[np.ix_(a_idx, a_idx)] += self.inertia.to_matrix_vw_order()

    # ---------- интеграция шага ----------
    def finish_timestep(self, dt: float):
        v = self.velocity_var.value
        a = self.acceleration_var.value
        v += a * dt
        self.velocity_var.value = v

        # линейное смещение
        v_lin = v[0:3]
        dp_lin = v_lin * dt

        # угловое малое приращение через кватернион
        v_ang = v[3:6]
        dθ = v_ang * dt
        q_delta = quat_from_small_angle(dθ)

        # обновляем глобальную позу
        # pose.lin += R * dp_lin   (делает Pose3 оператор @)
        # pose.ang = pose.ang * q_delta
        delta_pose_local = Pose3(
            lin=dp_lin,
            ang=q_delta,
        )

        self.global_pose = self.global_pose @ delta_pose_local

        # сбрасываем локальную позу
        self.local_pose_var.value[:] = 0.0

        if self.angle_normalize is not None:
            self.global_pose.ang = self.angle_normalize(self.global_pose.ang)
        else:
            self.global_pose.ang = quat_normalize(self.global_pose.ang)

    def finish_correction_step(self):
        dp = self.local_pose_var.value

        # линейная часть
        dp_lin = dp[0:3]

        # угловая часть dp[3:6] — это снова угловой вектор, надо превращать в кватернион
        dθ = dp[3:6]
        q_delta = quat_from_small_angle(dθ)

        delta_pose_local = Pose3(
            lin=dp_lin,
            ang=q_delta,
        )

        self.global_pose = self.global_pose @ delta_pose_local
        self.local_pose_var.value[:] = 0.0
        self.global_pose.ang = quat_normalize(self.global_pose.ang)


class ForceOnBody3D(Contribution):
    &quot;&quot;&quot;Внешний пространственный винт (сила+момент) в локальной СК тела.&quot;&quot;&quot;

    def __init__(self,
                 body: RigidBody3D,
                 wrench: Screw3,
                 in_local_frame: bool = True,
                 assembler=None):
        self.body = body
        self.acceleration = body.acceleration_var
        self.wrench_local = wrench if in_local_frame else wrench.rotated_by(body.pose().inverse())
        super().__init__([], assembler=assembler)

    def contribute(self, matrices, index_maps):
        b = matrices[&quot;load&quot;]
        a_indices = index_maps[&quot;acceleration&quot;][self.acceleration]
        b[a_indices] += self.wrench_local.to_vector_vw_order()


class FixedRotationJoint3D(Contribution):
    &quot;&quot;&quot;
    Ground-&quot;шарнир&quot;, фиксирующий линейное движение одной точки тела в мировой СК,
    но не ограничивающий ориентацию тела.

    Как и в 2D-версии:
    - всё формулируется в локальной СК тела;
    - лямбда — линейная сила в локальной СК тела (3 компоненты).
    &quot;&quot;&quot;

    def __init__(self,
                 body: RigidBody3D,
                 coords_of_joint: np.ndarray = None,
                 assembler=None):
        self.body = body
        self.internal_force = Variable(&quot;F_joint&quot;, size=3, tag=&quot;force&quot;)

        pose = self.body.pose()
        self.coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else pose.lin.copy()
        # фиксируем локальные координаты точки шарнира на теле
        self.r_local = pose.inverse_transform_point(self.coords_of_joint)

        super().__init__([body.acceleration_var, self.internal_force], assembler=assembler)

    def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        # линейная часть (Якобиан) — в H
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        # правую часть — квадратичные (центростремительные) члены, тоже в локале
        h = matrices[&quot;holonomic_rhs&quot;]
        F_idx = index_maps[&quot;force&quot;][self.internal_force]

        omega = np.asarray(self.body.velocity_var.value[3:6], dtype=float)
        # центростремительное ускорение точки: ω × (ω × r)
        bias = np.cross(omega, np.cross(omega, self.r_local))
        h[F_idx] += bias

    def radius(self) -&gt; np.ndarray:
        &quot;&quot;&quot;Радиус-вектор точки шарнира в глобальной СК.&quot;&quot;&quot;
        pose = self.body.pose()
        return pose.rotate_vector(self.r_local)

    def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        &quot;&quot;&quot;
        Ограничение в локале тела:
          a_lin + α×r_local + (квадр.члены) = 0

        В матрицу кладём линейную часть по ускорениям:
          H * [a_lin(3), α(3)]^T  с блоком  -[ I_3,  -skew(r_local) ]
        где α×r = -skew(r) α.
        &quot;&quot;&quot;
        H = matrices[&quot;holonomic&quot;]
        a_idx = index_maps[&quot;acceleration&quot;][self.body.acceleration_var]
        F_idx = index_maps[&quot;force&quot;][self.internal_force]

        r = self.r_local
        J = np.hstack([
            np.eye(3),
            -_skew(r),
        ])  # 3×6

        H[np.ix_(F_idx, a_idx)] += -J  # как в 2D: минус перед блоком

    def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        &quot;&quot;&quot;
        Позиционная ошибка в локале тела:
          φ_local = R^T (p - c_world) + r_local
        где p — мировая позиция опорной точки тела, c_world — фиксированная мировая точка шарнира.
        &quot;&quot;&quot;
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        poserr = matrices[&quot;position_error&quot;]
        F_idx = index_maps[&quot;force&quot;][self.internal_force]

        pose = self.body.pose()
        # предполагается, что Pose3 умеет выдавать матрицу поворота
        R = pose.rotation_matrix()
        R_T = R.T

        perr = R_T @ (pose.lin - self.coords_of_joint) + self.r_local
        poserr[F_idx] -= perr


class RevoluteJoint3D(Contribution):
    &quot;&quot;&quot;
    Двухтелый &quot;вращательный&quot; шарнир в духе 2D-кода, но в 3D:
    связь формулируется в локальной СК тела A, и
    ограничивает только относительное линейное движение точки шарнира,
    ориентация тел не фиксируется.
    &quot;&quot;&quot;

    def __init__(self,
                 bodyA: RigidBody3D,
                 bodyB: RigidBody3D,
                 coords_of_joint: np.ndarray = None,
                 assembler=None):

        cW = coords_of_joint.copy() if coords_of_joint is not None else bodyA.pose().lin.copy()

        self.bodyA = bodyA
        self.bodyB = bodyB

        # 3-компонентная лямбда — сила в СК A
        self.internal_force = Variable(&quot;F_rev&quot;, size=3, tag=&quot;force&quot;)

        poseA = self.bodyA.pose()
        poseB = self.bodyB.pose()

        # локальные координаты точки шарнира на каждом теле
        self.rA_local = poseA.inverse_transform_point(cW)  # в СК A
        self.rB_local = poseB.inverse_transform_point(cW)  # в СК B

        # кэш для rB, выраженного в СК A, и для R_AB
        self.R_AB = np.eye(3)
        self.rB_in_A = self.rB_local.copy()

        self.update_local_view()

        super().__init__([bodyA.acceleration_var, bodyB.acceleration_var, self.internal_force],
                         assembler=assembler)

    def update_local_view(self):
        &quot;&quot;&quot;Обновить R_AB и rB, выраженные в СК A.&quot;&quot;&quot;
        poseA = self.bodyA.pose()
        poseB = self.bodyB.pose()

        R_A = poseA.rotation_matrix()
        R_B = poseB.rotation_matrix()

        self.R_AB = R_A.T @ R_B
        self.rB_in_A = self.R_AB @ self.rB_local

    def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        self.update_local_view()
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        h = matrices[&quot;holonomic_rhs&quot;]
        F = index_maps[&quot;force&quot;][self.internal_force]

        omegaA = np.asarray(self.bodyA.velocity_var.value[3:6], dtype=float)
        omegaB = np.asarray(self.bodyB.velocity_var.value[3:6], dtype=float)

        # квадратичные члены (центростремительные), всё в СК A:
        # bias = (ωA×(ωA×rA))  -  (ωB×(ωB×rB_A))
        rA = self.rA_local
        rB_A = self.rB_in_A

        biasA = np.cross(omegaA, np.cross(omegaA, rA))
        biasB = np.cross(omegaB, np.cross(omegaB, rB_A))
        bias = biasA - biasB

        # по принятой конвенции — добавляем -bias
        h[F] += -bias

    def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        &quot;&quot;&quot;
        В СК A:
          aA_lin + αA×rA  -  R_AB (aB_lin + αB×rB)  + квадр.члены = 0

        Линейная часть по ускорениям:
          H * [aA_lin(3), αA(3), aB_lin(3), αB(3)]^T
        &quot;&quot;&quot;
        H = matrices[&quot;holonomic&quot;]
        aA = index_maps[&quot;acceleration&quot;][self.bodyA.acceleration_var]
        aB = index_maps[&quot;acceleration&quot;][self.bodyB.acceleration_var]
        F  = index_maps[&quot;force&quot;][self.internal_force]  # 3 строки

        rA = self.rA_local
        R = self.R_AB

        # блок по aA (в СК A): [ I, -skew(rA) ]
        J_A = np.hstack([
            np.eye(3),
            -_skew(rA),
        ])  # 3×6
        H[np.ix_(F, aA)] += J_A

        # блок по aB, выраженный в СК A:
        # - R_AB (aB_lin + αB×rB) =
        #   [ -R_AB,  R_AB * skew(rB_local) ] * [aB_lin, αB]^T
        S_rB = _skew(self.rB_local)
        col_alphaB = R @ S_rB  # 3×3

        J_B = np.hstack([
            -R,
            col_alphaB,
        ])  # 3×6

        H[np.ix_(F, aB)] += J_B

    def contribute_for_constraints_correction(self, matrices, index_maps):
        &quot;&quot;&quot;
        Позиционная ошибка в СК A:
          φ_A = R_A^T [ (pA + R_A rA) - (pB + R_B rB) ]
              = R_A^T (pA - pB) + rA - R_AB rB
        &quot;&quot;&quot;
        self.update_local_view()
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        poserr = matrices[&quot;position_error&quot;]
        F = index_maps[&quot;force&quot;][self.internal_force]

        pA = self.bodyA.pose().lin
        pB = self.bodyB.pose().lin

        poseA = self.bodyA.pose()
        R_A = poseA.rotation_matrix()
        R_A_T = R_A.T

        delta_p_A = R_A_T @ (pA - pB)
        rA = self.rA_local
        rB_A = self.rB_in_A

        poserr[F] += delta_p_A + rA - rB_A

</code></pre>
</body>
</html>
