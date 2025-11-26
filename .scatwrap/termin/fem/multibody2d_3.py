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
    p_world = P(q) @ p_local<br>
    p_world = R(θ) @ p_local<br>
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
    &quot;&quot;&quot;<br>
    Твёрдое тело в 2D, все расчёты выполняются в локальной СК тела.<br>
    Глобальная поза хранится отдельно и используется только для обновления геометрии.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        inertia: SpatialInertia2D,<br>
        gravity: np.ndarray = None,<br>
        assembler=None,<br>
        name=&quot;rbody2d&quot;,<br>
        angle_normalize: callable = None,<br>
    ):<br>
        self.acceleration_var = Variable(name + &quot;_acc&quot;, size=3, tag=&quot;acceleration&quot;)  # [ax, ay, α]_local<br>
        self.velocity_var = Variable(name + &quot;_vel&quot;, size=3, tag=&quot;velocity&quot;)          # [vx, vy, ω]_local<br>
        self.local_pose_var = Variable(name + &quot;_pos&quot;, size=3, tag=&quot;position&quot;)              # [x, y, θ]_local (для интеграции лок. движения)<br>
<br>
        # глобальная поза тела (Pose2)<br>
        self.global_pose = Pose2(lin=np.zeros(2), ang=0.0)<br>
<br>
        self.inertia = inertia<br>
        self.angle_normalize = angle_normalize<br>
<br>
        # сила тяжести задаётся в мировых координатах<br>
        self.gravity = np.array([0.0, -9.81]) if gravity is None else np.asarray(gravity, float).reshape(2)<br>
<br>
        super().__init__([self.acceleration_var, self.velocity_var, self.local_pose_var], assembler=assembler)<br>
<br>
    # ---------- геттеры ----------<br>
    def pose(self) -&gt; Pose2:<br>
        return self.global_pose<br>
<br>
    def set_pose(self, pose: Pose2):<br>
        self.global_pose = pose<br>
<br>
    # ---------- вклад в систему ----------<br>
    def contribute(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Вклад тела в уравнения движения:<br>
            I * a + v×* (I v) = F<br>
        Все в локальной СК.<br>
        &quot;&quot;&quot;<br>
        self.contribute_to_mass_matrix(matrices, index_maps)<br>
<br>
        b = matrices[&quot;load&quot;]<br>
        a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
<br>
        v_local = Screw2.from_vector_vw_order(self.velocity_var.value)<br>
        bias = self.inertia.bias_wrench(v_local)<br>
<br>
        # гравитация в локальной СК тела<br>
        g_local = self.global_pose.inverse().rotate_vector(self.gravity)<br>
        grav = self.inertia.gravity_wrench(g_local)<br>
<br>
        b[a_idx] += bias.to_vector_vw_order() + grav.to_vector_vw_order()<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps):<br>
        self.contribute_to_mass_matrix(matrices, index_maps)<br>
<br>
    def contribute_to_mass_matrix(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Массовая матрица в локальной СК (никаких поворотов).<br>
        &quot;&quot;&quot;<br>
        A = matrices[&quot;mass&quot;]<br>
        a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
        A[np.ix_(a_idx, a_idx)] += self.inertia.to_matrix_vw_order()<br>
<br>
    # ---------- интеграция шага ----------<br>
    def finish_timestep(self, dt):<br>
        &quot;&quot;&quot;<br>
        После интеграции уравнений ускорений и скоростей обновляем локальные переменные,<br>
        затем обновляем глобальную позу, используя локальное смещение.<br>
        После этого локальная поза обнуляется (тело возвращается в свою СК).<br>
        &quot;&quot;&quot;<br>
        v = self.velocity_var.value<br>
        a = self.acceleration_var.value<br>
        v += a * dt<br>
        self.velocity_var.value = v<br>
<br>
        # локальное приращение позы (интеграция по локальной СК)<br>
        delta_pose_local = Pose2(<br>
            lin=v[0:2] * dt,<br>
            ang=v[2] * dt,<br>
        )<br>
<br>
        # обновляем глобальную позу тела<br>
        self.global_pose = self.global_pose @ delta_pose_local<br>
<br>
        # сбрасываем локальную позу<br>
        self.local_pose_var.value[:] = 0.0<br>
<br>
        if self.angle_normalize is not None:<br>
            self.global_pose.ang = self.angle_normalize(self.global_pose.ang)<br>
<br>
    def finish_correction_step(self):<br>
        &quot;&quot;&quot;<br>
        После коррекции позиций сбрасываем локальную позу.<br>
        &quot;&quot;&quot;<br>
        self.global_pose = self.global_pose @ Pose2(<br>
            lin=self.local_pose_var.value[0:2],<br>
            ang=self.local_pose_var.value[2],<br>
        )<br>
        self.local_pose_var.value[:] = 0.0<br>
<br>
class ForceOnBody2D(Contribution):<br>
    &quot;&quot;&quot;Внешняя сила и момент в локальной СК тела.&quot;&quot;&quot;<br>
    def __init__(self, body: RigidBody2D, wrench: Screw2,<br>
                 in_local_frame: bool = True, assembler=None):<br>
        self.body = body<br>
        self.acceleration = body.acceleration_var<br>
        self.wrench_local = wrench if in_local_frame else wrench.rotated_by(body.pose().inverse())<br>
        super().__init__([], assembler=assembler)<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        b = matrices[&quot;load&quot;]<br>
        a_indices = index_maps[&quot;acceleration&quot;][self.acceleration]<br>
        b[a_indices] += self.wrench_local.to_vector_vw_order()<br>
<br>
<br>
class FixedRotationJoint2D(Contribution):<br>
    &quot;&quot;&quot;<br>
    Ground revolute joint.<br>
    Все уравнения формулируются в локальной СК тела.<br>
    Лямбда — сила, действующая на тело, в локальной СК тела.<br>
    &quot;&quot;&quot;<br>
    def __init__(self,<br>
                 body: RigidBody2D,<br>
                 coords_of_joint: np.ndarray = None,<br>
                 assembler=None):<br>
        self.body = body<br>
        self.internal_force = Variable(&quot;F_joint&quot;, size=2, tag=&quot;force&quot;)<br>
<br>
        pose = self.body.pose()<br>
        self.coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else pose.lin.copy()<br>
        # фиксируем локальные координаты точки шарнира на теле<br>
        self.r_local = pose.inverse_transform_point(self.coords_of_joint)<br>
        <br>
        super().__init__([body.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
    def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        # линейная часть (Якобиан) — сразу в H<br>
        self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
        # правую часть — квадратичные (центростремительные) члены, тоже в локале<br>
        h = matrices[&quot;holonomic_rhs&quot;]<br>
        F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
        omega = float(self.body.velocity_var.value[2])<br>
        bias = - (omega ** 2) * self.r_local<br>
        h[F_idx] += bias<br>
<br>
    def radius(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Радиус шарнира в глобальной СК.&quot;&quot;&quot;<br>
        pose = self.body.pose()<br>
        r_world = pose.rotate_vector(self.r_local)<br>
        return r_world<br>
<br>
    def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        &quot;&quot;&quot;<br>
        Ограничение в локале тела:<br>
          a_lin + α×r_local + (квадр.члены) = 0<br>
        В матрицу кладём линейную часть по ускорениям:<br>
          H * [a_x, a_y, α]^T  с блоком  -[ I,  perp(r_local) ]<br>
        где perp(r) = [-r_y, r_x].<br>
        &quot;&quot;&quot;<br>
        H = matrices[&quot;holonomic&quot;]<br>
        a_idx = index_maps[&quot;acceleration&quot;][self.body.acceleration_var]<br>
        F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
        r = self.r_local<br>
        H[np.ix_(F_idx, a_idx)] += -np.array([<br>
            [1.0, 0.0, -r[1]],<br>
            [0.0, 1.0,  r[0]],<br>
        ])<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        &quot;&quot;&quot;<br>
        Позиционная ошибка тоже в локале тела:<br>
          φ_local = R^T (p - c_world) + r_local<br>
        где p — мировая позиция опорной точки тела, c_world — фиксированная мировая точка шарнира.<br>
        &quot;&quot;&quot;<br>
        # Якобиан для коррекции такой же<br>
        self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
        poserr = matrices[&quot;position_error&quot;]<br>
        F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
        pose = self.body.pose()        <br>
        perr = pose.inverse_rotate_vector(pose.lin - self.coords_of_joint)  + self.r_local<br>
        poserr[F_idx] -= perr<br>
<br>
<br>
class RevoluteJoint2D(Contribution):<br>
    &quot;&quot;&quot;<br>
    Двухтелый вращательный шарнир (revolute joint):<br>
    связь формулируется в локальной СК тела A.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self,<br>
                 bodyA: RigidBody2D,<br>
                 bodyB: RigidBody2D,<br>
                 coords_of_joint: np.ndarray = None,<br>
                 assembler=None):<br>
<br>
        cW = coords_of_joint.copy() if coords_of_joint is not None else bodyA.pose().lin.copy()<br>
<br>
        self.bodyA = bodyA<br>
        self.bodyB = bodyB<br>
<br>
        # 2-компонентная лямбда силы в СК A<br>
        self.internal_force = Variable(&quot;F_rev&quot;, size=2, tag=&quot;force&quot;)<br>
<br>
        poseA = self.bodyA.pose()<br>
        poseB = self.bodyB.pose()<br>
<br>
        # локальные координаты точки шарнира на каждом теле<br>
        self.rA_local = poseA.inverse_transform_point(cW)  # в СК A<br>
        self.rB_local = poseB.inverse_transform_point(cW)  # в СК B<br>
<br>
        # кэш для rB, выраженного в СК A, и для R_AB<br>
        #self.R_AB = np.eye(2)<br>
        self.poseAB = Pose2.identity()<br>
        self.rB_in_A = self.rB_local.copy()  # будет обновляться<br>
<br>
        self.update_local_view()<br>
<br>
        super().__init__([bodyA.acceleration_var, bodyB.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
    @staticmethod<br>
    def _perp_col(r: np.ndarray) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;перпендикуляр к r: α×r = [ -α r_y, α r_x ] ⇒ столбец для α&quot;&quot;&quot;<br>
        return np.array([-r[1], r[0]])<br>
<br>
    def update_local_view(self):<br>
        &quot;&quot;&quot;Обновить R_AB и rB, выраженные в СК A.&quot;&quot;&quot;<br>
        poseA = self.bodyA.pose()<br>
        poseB = self.bodyB.pose()<br>
        #cA, sA = np.cos(poseA.ang), np.sin(poseA.ang)<br>
        #cB, sB = np.cos(poseB.ang), np.sin(poseB.ang)<br>
        #R_A = np.array([[cA, -sA],[sA, cA]])<br>
        #R_B = np.array([[cB, -sB],[sB, cB]])<br>
        #self.R_AB = R_A.T @ R_B<br>
        self.poseAB = poseA.inverse() @ poseB<br>
        self.rB_in_A = self.poseAB.rotate_vector(self.rB_local)  # r_B, выраженный в СК A<br>
<br>
    def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        self.update_local_view()<br>
        self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
        h = matrices[&quot;holonomic_rhs&quot;]<br>
        F = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
        omegaA = float(self.bodyA.velocity_var.value[2])<br>
        omegaB = float(self.bodyB.velocity_var.value[2])<br>
<br>
        # квадратичные члены (центростремительные) в правую часть, всё в СК A:<br>
        # bias = (ωA^2) * rA  - (ωB^2) * (R_AB rB)<br>
        rA = self.rA_local<br>
        rB_A = self.rB_in_A<br>
        bias = (omegaA**2) * rA - (omegaB**2) * rB_A<br>
<br>
        # по принятой конвенции — добавляем -bias<br>
        h[F] += -bias<br>
<br>
    def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        &quot;&quot;&quot;<br>
        В СК A:<br>
          aA_lin + αA×rA  -  R_AB (aB_lin + αB×rB)  + квадр.члены = 0<br>
        Линейная часть по ускорениям попадает в матрицу H.<br>
        &quot;&quot;&quot;<br>
        H = matrices[&quot;holonomic&quot;]<br>
        aA = index_maps[&quot;acceleration&quot;][self.bodyA.acceleration_var]<br>
        aB = index_maps[&quot;acceleration&quot;][self.bodyB.acceleration_var]<br>
        F  = index_maps[&quot;force&quot;][self.internal_force]  # 2 строки<br>
<br>
        rA = self.rA_local<br>
        rB_A = self.rB_in_A<br>
        R = self.poseAB.rotation_matrix()<br>
<br>
        # блок по aA (в СК A)<br>
        H[np.ix_(F, aA)] += np.array([<br>
            [ 1.0,  0.0, -rA[1]],<br>
            [ 0.0,  1.0,  rA[0]],<br>
        ])<br>
<br>
        # блок по aB, выраженный в СК A:<br>
        # - [ R,  R * perp(rB) ], где perp(r) = [-r_y, r_x]<br>
        col_alphaB = self.poseAB.rotate_vector(self._perp_col(self.rB_local))  # = perp(rB_A)<br>
        H[np.ix_(F, aB)] += np.array([<br>
            [-R[0,0], -R[0,1],  col_alphaB[0]],<br>
            [-R[1,0], -R[1,1],  col_alphaB[1]],<br>
        ])<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Позиционная ошибка тоже в СК A:<br>
          φ_A = R_A^T * [ (pA + R_A rA) - (pB + R_B rB) ]<br>
              = (R_A^T(pA - pB)) + rA - R_AB rB<br>
        &quot;&quot;&quot;<br>
        self.update_local_view()<br>
        self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
        poserr = matrices[&quot;position_error&quot;]<br>
        F = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
        pA = self.bodyA.pose().lin<br>
        pB = self.bodyB.pose().lin<br>
<br>
        poseA = self.bodyA.pose()<br>
        R_A_T = poseA.inverse().rotation_matrix()<br>
<br>
        delta_p_A = R_A_T @ (pA - pB)<br>
        rA = self.rA_local<br>
        rB_A = self.rB_in_A<br>
<br>
        poserr[F] += delta_p_A + rA - rB_A<br>
<!-- END SCAT CODE -->
</body>
</html>
