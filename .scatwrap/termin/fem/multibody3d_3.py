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
    p_world = P(q) @ p_local<br>
&quot;&quot;&quot;<br>
<br>
def _skew(r: np.ndarray) -&gt; np.ndarray:<br>
    &quot;&quot;&quot;Матрица векторного произведения:  r×x = skew(r) @ x.&quot;&quot;&quot;<br>
    rx, ry, rz = r<br>
    return np.array([<br>
        [   0.0, -rz,   ry],<br>
        [   rz,  0.0, -rx],<br>
        [  -ry,  rx,  0.0],<br>
    ], dtype=float)<br>
<br>
def quat_normalize(q):<br>
    return q / np.linalg.norm(q)<br>
<br>
def quat_mul(q1, q2):<br>
    &quot;&quot;&quot;Кватернионное произведение q1*q2 (оба в формате [x,y,z,w]).&quot;&quot;&quot;<br>
    x1,y1,z1,w1 = q1<br>
    x2,y2,z2,w2 = q2<br>
    return np.array([<br>
        w1*x2 + x1*w2 + y1*z2 - z1*y2,<br>
        w1*y2 + y1*w2 + z1*x2 - x1*z2,<br>
        w1*z2 + z1*w2 + x1*y2 - y1*x2,<br>
        w1*w2 - x1*x2 - y1*y2 - z1*z2,<br>
    ])<br>
<br>
def quat_from_small_angle(dθ):<br>
    &quot;&quot;&quot;Создать кватернион вращения из малого углового вектора dθ.&quot;&quot;&quot;<br>
    θ = np.linalg.norm(dθ)<br>
    if θ &lt; 1e-12:<br>
        # линеаризация<br>
        return quat_normalize(np.array([0.5*dθ[0], 0.5*dθ[1], 0.5*dθ[2], 1.0]))<br>
    axis = dθ / θ<br>
    s = np.sin(0.5 * θ)<br>
    return np.array([axis[0]*s, axis[1]*s, axis[2]*s, np.cos(0.5*θ)])<br>
<br>
<br>
<br>
class RigidBody3D(Contribution):<br>
    &quot;&quot;&quot;<br>
    Твёрдое тело в 3D, все расчёты выполняются в локальной СК тела.<br>
    Глобальная поза хранится отдельно и используется только для обновления геометрии.<br>
<br>
    Порядок пространственных векторов (vw_order):<br>
        [ v_x, v_y, v_z, ω_x, ω_y, ω_z ]<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(<br>
        self,<br>
        inertia: SpatialInertia3D,<br>
        gravity: np.ndarray = None,<br>
        assembler=None,<br>
        name: str = &quot;rbody3d&quot;,<br>
        angle_normalize: callable = None,<br>
    ):<br>
        # [a_lin(3), α(3)] в локальной СК<br>
        self.acceleration_var = Variable(name + &quot;_acc&quot;, size=6, tag=&quot;acceleration&quot;)<br>
        # [v_lin(3), ω(3)] в локальной СК<br>
        self.velocity_var = Variable(name + &quot;_vel&quot;, size=6, tag=&quot;velocity&quot;)<br>
        # [Δx(3), Δφ(3)] локальная приращённая поза для интеграции<br>
        self.local_pose_var = Variable(name + &quot;_pos&quot;, size=6, tag=&quot;position&quot;)<br>
<br>
        # глобальная поза тела<br>
        self.global_pose = Pose3(lin=np.zeros(3), ang=np.array([0.0, 0.0, 0.0, 1.0]))  # единичный кватернион<br>
<br>
        self.inertia = inertia<br>
        self.angle_normalize = angle_normalize<br>
<br>
        # сила тяжести задаётся в мировых координатах<br>
        # по аналогии с 2D: -g по оси y<br>
        if gravity is None:<br>
            self.gravity = np.array([0.0, -9.81, 0.0], dtype=float)<br>
        else:<br>
            self.gravity = np.asarray(gravity, float).reshape(3)<br>
<br>
        super().__init__([self.acceleration_var, self.velocity_var, self.local_pose_var],<br>
                         assembler=assembler)<br>
<br>
    # ---------- геттеры ----------<br>
    def pose(self) -&gt; Pose3:<br>
        return self.global_pose<br>
<br>
    def set_pose(self, pose: Pose3):<br>
        self.global_pose = pose<br>
<br>
    # ---------- вклад в систему ----------<br>
    def contribute(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Вклад тела в уравнения движения (в локальной СК):<br>
            I * a + v×* (I v) = F<br>
        &quot;&quot;&quot;<br>
        self.contribute_to_mass_matrix(matrices, index_maps)<br>
<br>
        b = matrices[&quot;load&quot;]<br>
        a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
<br>
        v_local = Screw3.from_vector_vw_order(self.velocity_var.value)<br>
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
        Массовая матрица в локальной СК.<br>
        &quot;&quot;&quot;<br>
        A = matrices[&quot;mass&quot;]<br>
        a_idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
        A[np.ix_(a_idx, a_idx)] += self.inertia.to_matrix_vw_order()<br>
<br>
    # ---------- интеграция шага ----------<br>
    def finish_timestep(self, dt: float):<br>
        v = self.velocity_var.value<br>
        a = self.acceleration_var.value<br>
        v += a * dt<br>
        self.velocity_var.value = v<br>
<br>
        # линейное смещение<br>
        v_lin = v[0:3]<br>
        dp_lin = v_lin * dt<br>
<br>
        # угловое малое приращение через кватернион<br>
        v_ang = v[3:6]<br>
        dθ = v_ang * dt<br>
        q_delta = quat_from_small_angle(dθ)<br>
<br>
        # обновляем глобальную позу<br>
        # pose.lin += R * dp_lin   (делает Pose3 оператор @)<br>
        # pose.ang = pose.ang * q_delta<br>
        delta_pose_local = Pose3(<br>
            lin=dp_lin,<br>
            ang=q_delta,<br>
        )<br>
<br>
        self.global_pose = self.global_pose @ delta_pose_local<br>
<br>
        # сбрасываем локальную позу<br>
        self.local_pose_var.value[:] = 0.0<br>
<br>
        if self.angle_normalize is not None:<br>
            self.global_pose.ang = self.angle_normalize(self.global_pose.ang)<br>
        else:<br>
            self.global_pose.ang = quat_normalize(self.global_pose.ang)<br>
<br>
    def finish_correction_step(self):<br>
        dp = self.local_pose_var.value<br>
<br>
        # линейная часть<br>
        dp_lin = dp[0:3]<br>
<br>
        # угловая часть dp[3:6] — это снова угловой вектор, надо превращать в кватернион<br>
        dθ = dp[3:6]<br>
        q_delta = quat_from_small_angle(dθ)<br>
<br>
        delta_pose_local = Pose3(<br>
            lin=dp_lin,<br>
            ang=q_delta,<br>
        )<br>
<br>
        self.global_pose = self.global_pose @ delta_pose_local<br>
        self.local_pose_var.value[:] = 0.0<br>
        self.global_pose.ang = quat_normalize(self.global_pose.ang)<br>
<br>
<br>
class ForceOnBody3D(Contribution):<br>
    &quot;&quot;&quot;Внешний пространственный винт (сила+момент) в локальной СК тела.&quot;&quot;&quot;<br>
<br>
    def __init__(self,<br>
                 body: RigidBody3D,<br>
                 wrench: Screw3,<br>
                 in_local_frame: bool = True,<br>
                 assembler=None):<br>
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
class FixedRotationJoint3D(Contribution):<br>
    &quot;&quot;&quot;<br>
    Ground-&quot;шарнир&quot;, фиксирующий линейное движение одной точки тела в мировой СК,<br>
    но не ограничивающий ориентацию тела.<br>
<br>
    Как и в 2D-версии:<br>
    - всё формулируется в локальной СК тела;<br>
    - лямбда — линейная сила в локальной СК тела (3 компоненты).<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self,<br>
                 body: RigidBody3D,<br>
                 coords_of_joint: np.ndarray = None,<br>
                 assembler=None):<br>
        self.body = body<br>
        self.internal_force = Variable(&quot;F_joint&quot;, size=3, tag=&quot;force&quot;)<br>
<br>
        pose = self.body.pose()<br>
        self.coords_of_joint = coords_of_joint.copy() if coords_of_joint is not None else pose.lin.copy()<br>
        # фиксируем локальные координаты точки шарнира на теле<br>
        self.r_local = pose.inverse_transform_point(self.coords_of_joint)<br>
<br>
        super().__init__([body.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
    def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        # линейная часть (Якобиан) — в H<br>
        self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
        # правую часть — квадратичные (центростремительные) члены, тоже в локале<br>
        h = matrices[&quot;holonomic_rhs&quot;]<br>
        F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
        omega = np.asarray(self.body.velocity_var.value[3:6], dtype=float)<br>
        # центростремительное ускорение точки: ω × (ω × r)<br>
        bias = np.cross(omega, np.cross(omega, self.r_local))<br>
        h[F_idx] += bias<br>
<br>
    def radius(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Радиус-вектор точки шарнира в глобальной СК.&quot;&quot;&quot;<br>
        pose = self.body.pose()<br>
        return pose.rotate_vector(self.r_local)<br>
<br>
    def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        &quot;&quot;&quot;<br>
        Ограничение в локале тела:<br>
          a_lin + α×r_local + (квадр.члены) = 0<br>
<br>
        В матрицу кладём линейную часть по ускорениям:<br>
          H * [a_lin(3), α(3)]^T  с блоком  -[ I_3,  -skew(r_local) ]<br>
        где α×r = -skew(r) α.<br>
        &quot;&quot;&quot;<br>
        H = matrices[&quot;holonomic&quot;]<br>
        a_idx = index_maps[&quot;acceleration&quot;][self.body.acceleration_var]<br>
        F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
        r = self.r_local<br>
        J = np.hstack([<br>
            np.eye(3),<br>
            -_skew(r),<br>
        ])  # 3×6<br>
<br>
        H[np.ix_(F_idx, a_idx)] += -J  # как в 2D: минус перед блоком<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        &quot;&quot;&quot;<br>
        Позиционная ошибка в локале тела:<br>
          φ_local = R^T (p - c_world) + r_local<br>
        где p — мировая позиция опорной точки тела, c_world — фиксированная мировая точка шарнира.<br>
        &quot;&quot;&quot;<br>
        self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
        poserr = matrices[&quot;position_error&quot;]<br>
        F_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
        pose = self.body.pose()<br>
        # предполагается, что Pose3 умеет выдавать матрицу поворота<br>
        R = pose.rotation_matrix()<br>
        R_T = R.T<br>
<br>
        perr = R_T @ (pose.lin - self.coords_of_joint) + self.r_local<br>
        poserr[F_idx] -= perr<br>
<br>
<br>
class RevoluteJoint3D(Contribution):<br>
    &quot;&quot;&quot;<br>
    Двухтелый &quot;вращательный&quot; шарнир в духе 2D-кода, но в 3D:<br>
    связь формулируется в локальной СК тела A, и<br>
    ограничивает только относительное линейное движение точки шарнира,<br>
    ориентация тел не фиксируется.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self,<br>
                 bodyA: RigidBody3D,<br>
                 bodyB: RigidBody3D,<br>
                 coords_of_joint: np.ndarray = None,<br>
                 assembler=None):<br>
<br>
        cW = coords_of_joint.copy() if coords_of_joint is not None else bodyA.pose().lin.copy()<br>
<br>
        self.bodyA = bodyA<br>
        self.bodyB = bodyB<br>
<br>
        # 3-компонентная лямбда — сила в СК A<br>
        self.internal_force = Variable(&quot;F_rev&quot;, size=3, tag=&quot;force&quot;)<br>
<br>
        poseA = self.bodyA.pose()<br>
        poseB = self.bodyB.pose()<br>
<br>
        # локальные координаты точки шарнира на каждом теле<br>
        self.rA_local = poseA.inverse_transform_point(cW)  # в СК A<br>
        self.rB_local = poseB.inverse_transform_point(cW)  # в СК B<br>
<br>
        # кэш для rB, выраженного в СК A, и для R_AB<br>
        self.R_AB = np.eye(3)<br>
        self.rB_in_A = self.rB_local.copy()<br>
<br>
        self.update_local_view()<br>
<br>
        super().__init__([bodyA.acceleration_var, bodyB.acceleration_var, self.internal_force],<br>
                         assembler=assembler)<br>
<br>
    def update_local_view(self):<br>
        &quot;&quot;&quot;Обновить R_AB и rB, выраженные в СК A.&quot;&quot;&quot;<br>
        poseA = self.bodyA.pose()<br>
        poseB = self.bodyB.pose()<br>
<br>
        R_A = poseA.rotation_matrix()<br>
        R_B = poseB.rotation_matrix()<br>
<br>
        self.R_AB = R_A.T @ R_B<br>
        self.rB_in_A = self.R_AB @ self.rB_local<br>
<br>
    def contribute(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        self.update_local_view()<br>
        self.contribute_to_holonomic_matrix(matrices, index_maps)<br>
<br>
        h = matrices[&quot;holonomic_rhs&quot;]<br>
        F = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
        omegaA = np.asarray(self.bodyA.velocity_var.value[3:6], dtype=float)<br>
        omegaB = np.asarray(self.bodyB.velocity_var.value[3:6], dtype=float)<br>
<br>
        # квадратичные члены (центростремительные), всё в СК A:<br>
        # bias = (ωA×(ωA×rA))  -  (ωB×(ωB×rB_A))<br>
        rA = self.rA_local<br>
        rB_A = self.rB_in_A<br>
<br>
        biasA = np.cross(omegaA, np.cross(omegaA, rA))<br>
        biasB = np.cross(omegaB, np.cross(omegaB, rB_A))<br>
        bias = biasA - biasB<br>
<br>
        # по принятой конвенции — добавляем -bias<br>
        h[F] += -bias<br>
<br>
    def contribute_to_holonomic_matrix(self, matrices, index_maps: Dict[str, Dict[Variable, List[int]]]):<br>
        &quot;&quot;&quot;<br>
        В СК A:<br>
          aA_lin + αA×rA  -  R_AB (aB_lin + αB×rB)  + квадр.члены = 0<br>
<br>
        Линейная часть по ускорениям:<br>
          H * [aA_lin(3), αA(3), aB_lin(3), αB(3)]^T<br>
        &quot;&quot;&quot;<br>
        H = matrices[&quot;holonomic&quot;]<br>
        aA = index_maps[&quot;acceleration&quot;][self.bodyA.acceleration_var]<br>
        aB = index_maps[&quot;acceleration&quot;][self.bodyB.acceleration_var]<br>
        F  = index_maps[&quot;force&quot;][self.internal_force]  # 3 строки<br>
<br>
        rA = self.rA_local<br>
        R = self.R_AB<br>
<br>
        # блок по aA (в СК A): [ I, -skew(rA) ]<br>
        J_A = np.hstack([<br>
            np.eye(3),<br>
            -_skew(rA),<br>
        ])  # 3×6<br>
        H[np.ix_(F, aA)] += J_A<br>
<br>
        # блок по aB, выраженный в СК A:<br>
        # - R_AB (aB_lin + αB×rB) =<br>
        #   [ -R_AB,  R_AB * skew(rB_local) ] * [aB_lin, αB]^T<br>
        S_rB = _skew(self.rB_local)<br>
        col_alphaB = R @ S_rB  # 3×3<br>
<br>
        J_B = np.hstack([<br>
            -R,<br>
            col_alphaB,<br>
        ])  # 3×6<br>
<br>
        H[np.ix_(F, aB)] += J_B<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Позиционная ошибка в СК A:<br>
          φ_A = R_A^T [ (pA + R_A rA) - (pB + R_B rB) ]<br>
              = R_A^T (pA - pB) + rA - R_AB rB<br>
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
        R_A = poseA.rotation_matrix()<br>
        R_A_T = R_A.T<br>
<br>
        delta_p_A = R_A_T @ (pA - pB)<br>
        rA = self.rA_local<br>
        rB_A = self.rB_in_A<br>
<br>
        poserr[F] += delta_p_A + rA - rB_A<br>
<!-- END SCAT CODE -->
</body>
</html>
