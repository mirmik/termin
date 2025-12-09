"""
Соглашение о уравнениях такого, что все уравнения собираются в локальной СК тела.
Глобальная поза тела хранится отдельно и используется только для обновления геометрии.

Преобразования следуют конвенции локальная система -> мировая система:
    p_world = P(q) @ p_local
    p_world = R(θ) @ p_local
"""

from typing import List, Dict
import numpy as np
from termin.fem.assembler import Variable, Contribution
from termin.geombase.pose2 import Pose2
from termin.geombase.screw import Screw2
from termin.fem.inertia2d import SpatialInertia2D


class RigidBody2D(Contribution):
    """
    Твёрдое тело в 2D, все расчёты выполняются в локальной СК тела.
    Глобальная поза хранится отдельно и используется только для обновления геометрии.
    """

    def __init__(
        self,
        inertia: SpatialInertia2D,
        gravity: np.ndarray = None,
        assembler=None,
        name="rbody2d",
        angle_normalize: callable = None,
    ):
        self.acceleration_var = Variable(name + "_acc", size=3, tag="acceleration")  # [ax, ay, α]_local
        self.velocity_var = Variable(name + "_vel", size=3, tag="velocity")          # [vx, vy, ω]_local
        self.local_pose_var = Variable(name + "_pos", size=3, tag="position")              # [x, y, θ]_local (для интеграции лок. движения)

        # глобальная поза тела (Pose2)
        self.global_pose = Pose2(lin=np.zeros(2), ang=0.0)

        self.inertia = inertia
        self.angle_normalize = angle_normalize

        # сила тяжести задаётся в мировых координатах
        self.gravity = np.array([0.0, -9.81]) if gravity is None else np.asarray(gravity, float).reshape(2)

        super().__init__([self.acceleration_var, self.velocity_var, self.local_pose_var], assembler=assembler)

    # ---------- геттеры ----------
    def pose(self) -> Pose2:
        return self.global_pose

    def set_pose(self, pose: Pose2):
        self.global_pose = pose

    # ---------- вклад в систему ----------
    def contribute(self, matrices, index_maps):
        """
        Вклад тела в уравнения движения:
            I * a + v×* (I v) = F
        Все в локальной СК.
        """
        self.contribute_to_mass_matrix(matrices, index_maps)

        b = matrices["load"]
        a_idx = index_maps["acceleration"][self.acceleration_var]

        v_local = Screw2.from_vector_vw_order(self.velocity_var.value)
        bias = self.inertia.bias_wrench(v_local)

        # гравитация в локальной СК тела
        g_local = self.global_pose.inverse().rotate_vector(self.gravity)
        grav = self.inertia.gravity_wrench(g_local)

        b[a_idx] += bias.to_vector_vw_order() + grav.to_vector_vw_order()

    def contribute_for_constraints_correction(self, matrices, index_maps):
        self.contribute_to_mass_matrix(matrices, index_maps)

    def contribute_to_mass_matrix(self, matrices, index_maps):
        """
        Массовая матрица в локальной СК (никаких поворотов).
        """
        A = matrices["mass"]
        a_idx = index_maps["acceleration"][self.acceleration_var]
        A[np.ix_(a_idx, a_idx)] += self.inertia.to_matrix_vw_order()

    # ---------- интеграция шага ----------
    def finish_timestep(self, dt):
        """
        После интеграции уравнений ускорений и скоростей обновляем локальные переменные,
        затем обновляем глобальную позу, используя локальное смещение.
        После этого локальная поза обнуляется (тело возвращается в свою СК).
        """
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
        """
        После коррекции позиций сбрасываем локальную позу.
        """
        self.global_pose = self.global_pose @ Pose2(
            lin=self.local_pose_var.value[0:2],
            ang=self.local_pose_var.value[2],
        )
        self.local_pose_var.value[:] = 0.0

class ForceOnBody2D(Contribution):
    """Внешняя сила и момент в локальной СК тела."""
    def __init__(self, body: RigidBody2D, wrench: Screw2,
                 in_local_frame: bool = True, assembler=None):
        self.body = body
        self.acceleration = body.acceleration_var
        self.wrench_local = wrench if in_local_frame else wrench.rotated_by(body.pose().inverse())
        super().__init__([], assembler=assembler)

    def contribute(self, matrices, index_maps):
        b = matrices["load"]
        a_indices = index_maps["acceleration"][self.acceleration]
        b[a_indices] += self.wrench_local.to_vector_vw_order()


class FixedRotationJoint2D(Contribution):
    """
    Ground revolute joint.
    Все уравнения формулируются в локальной СК тела.
    Лямбда — сила, действующая на тело, в локальной СК тела.
    """
    def __init__(self,
                 body: RigidBody2D,
                 coords_of_joint: np.ndarray = None,
                 assembler=None):
        self.body = body
        self.internal_force = Variable("F_joint", size=2, tag="force")

        pose = self.body.pose()
        self.coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else pose.lin.copy()
        # фиксируем локальные координаты точки шарнира на теле
        self.r_local = pose.inverse_transform_point(self.coords_of_joint)
        
        super().__init__([body.acceleration_var, self.internal_force], assembler=assembler)

    def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        # линейная часть (Якобиан) — сразу в H
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        # правую часть — квадратичные (центростремительные) члены, тоже в локале
        h = matrices["holonomic_rhs"]
        F_idx = index_maps["force"][self.internal_force]

        omega = float(self.body.velocity_var.value[2])
        bias = - (omega ** 2) * self.r_local
        h[F_idx] += bias

    def radius(self) -> np.ndarray:
        """Радиус шарнира в глобальной СК."""
        pose = self.body.pose()
        r_world = pose.rotate_vector(self.r_local)
        return r_world

    def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        """
        Ограничение в локале тела:
          a_lin + α×r_local + (квадр.члены) = 0
        В матрицу кладём линейную часть по ускорениям:
          H * [a_x, a_y, α]^T  с блоком  -[ I,  perp(r_local) ]
        где perp(r) = [-r_y, r_x].
        """
        H = matrices["holonomic"]
        a_idx = index_maps["acceleration"][self.body.acceleration_var]
        F_idx = index_maps["force"][self.internal_force]

        r = self.r_local
        H[np.ix_(F_idx, a_idx)] += -np.array([
            [1.0, 0.0, -r[1]],
            [0.0, 1.0,  r[0]],
        ])

    def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):
        """
        Позиционная ошибка тоже в локале тела:
          φ_local = R^T (p - c_world) + r_local
        где p — мировая позиция опорной точки тела, c_world — фиксированная мировая точка шарнира.
        """
        # Якобиан для коррекции такой же
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        poserr = matrices["position_error"]
        F_idx = index_maps["force"][self.internal_force]

        pose = self.body.pose()        
        perr = pose.inverse_rotate_vector(pose.lin - self.coords_of_joint)  + self.r_local
        poserr[F_idx] -= perr


class RevoluteJoint2D(Contribution):
    """
    Двухтелый вращательный шарнир (revolute joint):
    связь формулируется в локальной СК тела A.
    """

    def __init__(self,
                 bodyA: RigidBody2D,
                 bodyB: RigidBody2D,
                 coords_of_joint: np.ndarray = None,
                 assembler=None):

        cW = coords_of_joint.copy() if coords_of_joint is not None else bodyA.pose().lin.copy()

        self.bodyA = bodyA
        self.bodyB = bodyB

        # 2-компонентная лямбда силы в СК A
        self.internal_force = Variable("F_rev", size=2, tag="force")

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
    def _perp_col(r: np.ndarray) -> np.ndarray:
        """перпендикуляр к r: α×r = [ -α r_y, α r_x ] ⇒ столбец для α"""
        return np.array([-r[1], r[0]])

    def update_local_view(self):
        """Обновить R_AB и rB, выраженные в СК A."""
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

        h = matrices["holonomic_rhs"]
        F = index_maps["force"][self.internal_force]

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
        """
        В СК A:
          aA_lin + αA×rA  -  R_AB (aB_lin + αB×rB)  + квадр.члены = 0
        Линейная часть по ускорениям попадает в матрицу H.
        """
        H = matrices["holonomic"]
        aA = index_maps["acceleration"][self.bodyA.acceleration_var]
        aB = index_maps["acceleration"][self.bodyB.acceleration_var]
        F  = index_maps["force"][self.internal_force]  # 2 строки

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
        col_alphaB = self.poseAB.rotate_vector(self._perp_col(self.rB_local))  # = R_AB @ perp(rB_local)
        H[np.ix_(F, aB)] += np.array([
            [-R[0,0], -R[0,1], -col_alphaB[0]],
            [-R[1,0], -R[1,1], -col_alphaB[1]],
        ])

    def contribute_for_constraints_correction(self, matrices, index_maps):
        """
        Позиционная ошибка тоже в СК A:
          φ_A = R_A^T * [ (pA + R_A rA) - (pB + R_B rB) ]
              = (R_A^T(pA - pB)) + rA - R_AB rB
        """
        self.update_local_view()
        self.contribute_to_holonomic_matrix(matrices, index_maps)

        poserr = matrices["position_error"]
        F = index_maps["force"][self.internal_force]

        pA = self.bodyA.pose().lin
        pB = self.bodyB.pose().lin

        poseA = self.bodyA.pose()
        R_A_T = poseA.inverse().rotation_matrix()

        delta_p_A = R_A_T @ (pA - pB)
        rA = self.rA_local
        rB_A = self.rB_in_A

        poserr[F] += delta_p_A + rA - rB_A
