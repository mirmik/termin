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
    &quot;&quot;&quot;Возвращает кососимметричную матрицу для вектора v.&quot;&quot;&quot;<br>
    return np.array([[0, -v[2], v[1]],<br>
                     [v[2], 0, -v[0]],<br>
                     [-v[1], v[0], 0]])<br>
<br>
class RigidBody3D(Contribution):<br>
<br>
    def __init__(self, inertia: SpatialInertia3D,<br>
                 gravity=np.array([0,0,-9.81]),<br>
                 assembler=None, name=&quot;rbody3d&quot;):<br>
        self.acceleration_var = Variable(name+&quot;_acc&quot;, size=6, tag=&quot;acceleration&quot;)<br>
        self.velocity_var = Variable(name+&quot;_vel&quot;, size=6, tag=&quot;velocity&quot;)<br>
        self.pose_var = Variable(name+&quot;_pose&quot;, size=7, tag=&quot;position&quot;)<br>
        self.gravity = gravity<br>
        self.spatial_local = inertia   # spatial inertia in body frame<br>
        super().__init__([self.acceleration_var, self.velocity_var, self.pose_var], assembler=assembler)<br>
<br>
    def pose(self):<br>
        return Pose3.from_vector_vw_order(self.pose_var.value)<br>
<br>
    def set_pose(self, pose: Pose3):<br>
        self.pose_var.value = pose.to_vector_vw_order()<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        pose = self.pose()<br>
<br>
        Iw=self.contribute_mass_matrix(matrices, index_maps)<br>
<br>
        idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
        Fg_screw = Iw.gravity_wrench(self.gravity)   # 6×1 vector<br>
        Fg = Fg_screw.to_vw_array()  # in world frame<br>
        b = matrices[&quot;load&quot;]<br>
        for i in range(6):<br>
            b[idx[i]] += Fg[i]<br>
<br>
    def contribute_mass_matrix(self, matrices, index_maps):<br>
        pose = self.pose()<br>
        I_origin = self.spatial_local.at_body_origin()<br>
        Iw = I_origin.rotate_by(pose)<br>
<br>
        A = matrices[&quot;mass&quot;]<br>
        idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]<br>
        A[np.ix_(idx, idx)] += Iw.to_matrix_vw_order()<br>
        return Iw<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps):<br>
        self.contribute_mass_matrix(matrices, index_maps)<br>
        <br>
    def finish_timestep(self, dt):<br>
        old_velocity = self.velocity_var.value.copy()<br>
        self.velocity_var.value += self.acceleration_var.value * dt<br>
        delta_scr = Screw3(lin=old_velocity[0:3]*dt, ang=old_velocity[3:6]*dt)<br>
        delta_pose = delta_scr.to_pose()<br>
        curpose = Pose3.from_vector_vw_order(self.pose_var.value)<br>
        newpose = curpose * delta_pose<br>
        self.pose_var.value = newpose.to_vector_vw_order()<br>
<br>
    def matrix_of_transform_from_minimal_coordinates(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Матрица перехода от минимальных координат, где повот выражен в углах в собственной системе координат, к спатиал позе с кватернионом. Матрица 7×6 .&quot;&quot;&quot;<br>
        <br>
<br>
class ForceOnBody3D(Contribution):<br>
    &quot;&quot;&quot;<br>
    Внешняя сила и момент, приложенные к твердому телу в 3D.<br>
    &quot;&quot;&quot;<br>
    def __init__(self,<br>
                 body: RigidBody3D,<br>
                 force: np.ndarray = np.zeros(3),     # Fx, Fy, Fz<br>
                 torque: np.ndarray = np.zeros(3),    # τx, τy, τz<br>
                 assembler=None):<br>
        &quot;&quot;&quot;<br>
        Args:<br>
            force: Внешняя сила (3,)<br>
            torque: Внешний момент (3,)<br>
        &quot;&quot;&quot;<br>
        self.body = body<br>
        self.velocity = body.velocity  # PoseVariable<br>
        self.force = np.asarray(force, float)<br>
        self.torque = np.asarray(torque, float)<br>
<br>
        super().__init__([], assembler=assembler)  # переменных нет<br>
<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Добавить вклад в вектор нагрузок b.<br>
        &quot;&quot;&quot;<br>
        b = matrices[&quot;load&quot;]<br>
        amap = index_maps[&quot;acceleration&quot;]<br>
<br>
        # v_idx: три индекса линейной части<br>
        # w_idx: три индекса угловой части<br>
        v_idx = amap[self.acceleration][0:3]<br>
        w_idx = amap[self.acceleration][3:6]<br>
<br>
        # Линейная сила<br>
        b[v_idx[0]] += self.force[0]<br>
        b[v_idx[1]] += self.force[1]<br>
        b[v_idx[2]] += self.force[2]<br>
<br>
        # Момент<br>
        b[w_idx[0]] += self.torque[0]<br>
        b[w_idx[1]] += self.torque[1]<br>
        b[w_idx[2]] += self.torque[2]<br>
<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Внешние силы не участвуют в позиционной коррекции.<br>
        &quot;&quot;&quot;<br>
        pass<br>
<br>
class FixedRotationJoint3D(Contribution):<br>
    &quot;&quot;&quot;<br>
    3D фиксированная точка (ground spherical joint).<br>
    <br>
    Условие:<br>
        p + R * r_local = joint_world<br>
    <br>
    Скоростная связь:<br>
        v + ω × r = 0<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self, <br>
                 body,                      # RigidBody3D<br>
                 joint_point: np.ndarray,   # мировая точка (3,)<br>
                 assembler=None):<br>
<br>
        self.body = body<br>
        self.joint_point = np.asarray(joint_point, float)<br>
<br>
        # внутренняя сила — 3 компоненты<br>
        self.internal_force = Variable(<br>
            &quot;F_fixed3d&quot;,<br>
            size=3,<br>
            tag=&quot;force&quot;<br>
        )<br>
<br>
        # вычисляем локальную точку (обратное преобразование)<br>
        pose = self.body.pose()<br>
        self.r_local = pose.inverse_transform_point(self.joint_point)<br>
<br>
        # актуализируем r в мировых<br>
        self.update_radius()<br>
<br>
        super().__init__([self.body.acceleration_var, self.internal_force], assembler=assembler)<br>
<br>
    # -----------------------------------------------------------<br>
<br>
    def update_radius(self):<br>
        &quot;&quot;&quot;Обновить мировой радиус r = R * r_local.&quot;&quot;&quot;<br>
        pose = self.body.pose()<br>
        self.r = pose.transform_vector(self.r_local)<br>
        self.radius = self.r<br>
<br>
    # -----------------------------------------------------------<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Вклад в матрицу holonomic.<br>
        Ограничение: e = p + r - j = 0.<br>
        Якобиан: [ I3 | -skew(r) ].<br>
        &quot;&quot;&quot;<br>
        self.update_radius()<br>
<br>
        H = matrices[&quot;holonomic&quot;]<br>
<br>
        amap = index_maps[&quot;acceleration&quot;]<br>
        cmap = index_maps[&quot;force&quot;]<br>
<br>
        # индексы скоростей тела<br>
        v_idx = amap[self.body.acceleration_var]      # 6 индексов<br>
        # индексы внутренних сил<br>
        f_idx = cmap[self.internal_force]     # 3 индексов<br>
<br>
        # --- Заполняем якобиан ---<br>
        # H[f, v]<br>
        # линейные скорости: +I<br>
        H[f_idx[0], v_idx[0]] += 1<br>
        H[f_idx[1], v_idx[1]] += 1<br>
        H[f_idx[2], v_idx[2]] += 1<br>
<br>
        # угловые скорости: -[r]_×<br>
        S = skew(self.r)<br>
        # порядок v_idx[3:6] — (wx, wy, wz)<br>
        H[np.ix_(f_idx, v_idx[3:6])] -= S<br>
<br>
<br>
    # -----------------------------------------------------------<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps):<br>
        &quot;&quot;&quot;<br>
        Для коррекции ограничений делаем то же самое.<br>
        &quot;&quot;&quot;<br>
        self.update_radius()<br>
        self.contribute(matrices, index_maps)<br>
        <br>
        poserr = matrices[&quot;position_error&quot;]<br>
        f_idx = index_maps[&quot;force&quot;][self.internal_force]<br>
<br>
<br>
        # --- Позиционная ошибка ---<br>
        pose = self.body.pose()<br>
        p = pose.lin<br>
        e = p + self.r - self.joint_point<br>
<br>
        poserr[f_idx[0]] += e[0]<br>
        poserr[f_idx[1]] += e[1]<br>
        poserr[f_idx[2]] += e[2]<br>
<br>
<br>
class RevoluteJoint3D(Contribution):<br>
    &quot;&quot;&quot;<br>
    3D револьвентный шарнир в смысле 2D-версии:<br>
    совпадение двух точек на двух телах.<br>
    <br>
    Ограничения: (pA + rA) - (pB + rB) = 0   (3 eq)<br>
    Не ограничивает ориентацию!<br>
    Даёт 3 степени свободы на вращение.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self,<br>
                 bodyA,<br>
                 bodyB,<br>
                 joint_point_world: np.ndarray,<br>
                 assembler=None):<br>
<br>
        self.bodyA = bodyA<br>
        self.bodyB = bodyB<br>
<br>
        # Внутренняя реакция — вектор из 3 компонент<br>
        self.internal_force = Variable(&quot;F_rev3d&quot;, size=3,<br>
                                       tag=&quot;force&quot;)<br>
<br>
        # локальные точки крепления<br>
        poseA = self.bodyA.pose()<br>
        poseB = self.bodyB.pose()<br>
<br>
        self.rA_local = poseA.inverse_transform_point(joint_point_world)<br>
        self.rB_local = poseB.inverse_transform_point(joint_point_world)<br>
<br>
        # обновляем мировую геометрию<br>
        self.update_kinematics()<br>
<br>
        super().__init__([bodyA.velocity, bodyB.velocity, self.internal_force],<br>
                         assembler=assembler)<br>
<br>
    # --------------------------------------------------------------<br>
<br>
    def update_kinematics(self):<br>
        poseA = self.bodyA.pose()<br>
        poseB = self.bodyB.pose()<br>
<br>
        self.pA = poseA.lin<br>
        self.pB = poseB.lin<br>
<br>
        self.rA = poseA.transform_vector(self.rA_local)<br>
        self.rB = poseB.transform_vector(self.rB_local)<br>
<br>
    # --------------------------------------------------------------<br>
<br>
    def contribute(self, matrices, index_maps):<br>
        self.update_kinematics()<br>
<br>
        H = matrices[&quot;holonomic&quot;]<br>
<br>
        amap = index_maps[&quot;acceleration&quot;]<br>
        cmap = index_maps[&quot;force&quot;]<br>
<br>
        vA = amap[self.bodyA.velocity]<br>
        vB = amap[self.bodyB.velocity]<br>
<br>
        F = cmap[self.internal_force]  # 3 строки<br>
<br>
        # Матрицы скосов радиусов<br>
        SA = skew(self.rA)<br>
        SB = skew(self.rB)<br>
<br>
        # dφ/dvA_lin = +I<br>
        H[np.ix_(F, vA[0:3])] += np.eye(3)<br>
<br>
        # dφ/dvA_ang = -skew(rA)<br>
        H[np.ix_(F, vA[3:6])] += -SA<br>
<br>
        # dφ/dvB_lin = -I<br>
        H[np.ix_(F, vB[0:3])] += -np.eye(3)<br>
<br>
        # dφ/dvB_ang = +skew(rB)<br>
        H[np.ix_(F, vB[3:6])] += SB<br>
<br>
<br>
    # --------------------------------------------------------------<br>
<br>
    def contribute_for_constraints_correction(self, matrices, index_maps):<br>
        self.update_kinematics()<br>
        self.contribute(matrices, index_maps)<br>
        cmap = index_maps[&quot;force&quot;]<br>
        F = cmap[self.internal_force]  # 3 строки<br>
        poserr = matrices[&quot;position_error&quot;]<br>
        # позиционная ошибка: φ = (pA+rA) - (pB+rB)<br>
        err = (self.pA + self.rA) - (self.pB + self.rB)<br>
<br>
        poserr[F[0]] += err[0]<br>
        poserr[F[1]] += err[1]<br>
        poserr[F[2]] += err[2]<br>
<!-- END SCAT CODE -->
</body>
</html>
