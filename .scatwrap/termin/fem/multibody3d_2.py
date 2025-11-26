<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/fem/multibody3d_2.py</title>
</head>
<body>
<pre><code>

from typing import List, Dict
import numpy as np
from termin.fem.assembler import Variable, Contribution
from termin.geombase.pose3 import Pose3
from termin.geombase.screw import Screw3
from termin.fem.inertia3d import SpatialInertia3D

def skew(v: np.ndarray) -&gt; np.ndarray:
    &quot;&quot;&quot;Возвращает кососимметричную матрицу для вектора v.&quot;&quot;&quot;
    return np.array([[0, -v[2], v[1]],
                     [v[2], 0, -v[0]],
                     [-v[1], v[0], 0]])

class RigidBody3D(Contribution):

    def __init__(self, inertia: SpatialInertia3D,
                 gravity=np.array([0,0,-9.81]),
                 assembler=None, name=&quot;rbody3d&quot;):
        self.acceleration_var = Variable(name+&quot;_acc&quot;, size=6, tag=&quot;acceleration&quot;)
        self.velocity_var = Variable(name+&quot;_vel&quot;, size=6, tag=&quot;velocity&quot;)
        self.pose_var = Variable(name+&quot;_pose&quot;, size=7, tag=&quot;position&quot;)
        self.gravity = gravity
        self.spatial_local = inertia   # spatial inertia in body frame
        super().__init__([self.acceleration_var, self.velocity_var, self.pose_var], assembler=assembler)

    def pose(self):
        return Pose3.from_vector_vw_order(self.pose_var.value)

    def set_pose(self, pose: Pose3):
        self.pose_var.value = pose.to_vector_vw_order()

    def contribute(self, matrices, index_maps):
        pose = self.pose()

        Iw=self.contribute_mass_matrix(matrices, index_maps)

        idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]
        Fg_screw = Iw.gravity_wrench(self.gravity)   # 6×1 vector
        Fg = Fg_screw.to_vw_array()  # in world frame
        b = matrices[&quot;load&quot;]
        for i in range(6):
            b[idx[i]] += Fg[i]

    def contribute_mass_matrix(self, matrices, index_maps):
        pose = self.pose()
        I_origin = self.spatial_local.at_body_origin()
        Iw = I_origin.rotate_by(pose)

        A = matrices[&quot;mass&quot;]
        idx = index_maps[&quot;acceleration&quot;][self.acceleration_var]
        A[np.ix_(idx, idx)] += Iw.to_matrix_vw_order()
        return Iw

    def contribute_for_constraints_correction(self, matrices, index_maps):
        self.contribute_mass_matrix(matrices, index_maps)
        
    def finish_timestep(self, dt):
        old_velocity = self.velocity_var.value.copy()
        self.velocity_var.value += self.acceleration_var.value * dt
        delta_scr = Screw3(lin=old_velocity[0:3]*dt, ang=old_velocity[3:6]*dt)
        delta_pose = delta_scr.to_pose()
        curpose = Pose3.from_vector_vw_order(self.pose_var.value)
        newpose = curpose * delta_pose
        self.pose_var.value = newpose.to_vector_vw_order()

    def matrix_of_transform_from_minimal_coordinates(self) -&gt; np.ndarray:
        &quot;&quot;&quot;Матрица перехода от минимальных координат, где повот выражен в углах в собственной системе координат, к спатиал позе с кватернионом. Матрица 7×6 .&quot;&quot;&quot;
        

class ForceOnBody3D(Contribution):
    &quot;&quot;&quot;
    Внешняя сила и момент, приложенные к твердому телу в 3D.
    &quot;&quot;&quot;
    def __init__(self,
                 body: RigidBody3D,
                 force: np.ndarray = np.zeros(3),     # Fx, Fy, Fz
                 torque: np.ndarray = np.zeros(3),    # τx, τy, τz
                 assembler=None):
        &quot;&quot;&quot;
        Args:
            force: Внешняя сила (3,)
            torque: Внешний момент (3,)
        &quot;&quot;&quot;
        self.body = body
        self.velocity = body.velocity  # PoseVariable
        self.force = np.asarray(force, float)
        self.torque = np.asarray(torque, float)

        super().__init__([], assembler=assembler)  # переменных нет


    def contribute(self, matrices, index_maps):
        &quot;&quot;&quot;
        Добавить вклад в вектор нагрузок b.
        &quot;&quot;&quot;
        b = matrices[&quot;load&quot;]
        amap = index_maps[&quot;acceleration&quot;]

        # v_idx: три индекса линейной части
        # w_idx: три индекса угловой части
        v_idx = amap[self.acceleration][0:3]
        w_idx = amap[self.acceleration][3:6]

        # Линейная сила
        b[v_idx[0]] += self.force[0]
        b[v_idx[1]] += self.force[1]
        b[v_idx[2]] += self.force[2]

        # Момент
        b[w_idx[0]] += self.torque[0]
        b[w_idx[1]] += self.torque[1]
        b[w_idx[2]] += self.torque[2]


    def contribute_for_constraints_correction(self, matrices, index_maps):
        &quot;&quot;&quot;
        Внешние силы не участвуют в позиционной коррекции.
        &quot;&quot;&quot;
        pass

class FixedRotationJoint3D(Contribution):
    &quot;&quot;&quot;
    3D фиксированная точка (ground spherical joint).
    
    Условие:
        p + R * r_local = joint_world
    
    Скоростная связь:
        v + ω × r = 0
    &quot;&quot;&quot;

    def __init__(self, 
                 body,                      # RigidBody3D
                 joint_point: np.ndarray,   # мировая точка (3,)
                 assembler=None):

        self.body = body
        self.joint_point = np.asarray(joint_point, float)

        # внутренняя сила — 3 компоненты
        self.internal_force = Variable(
            &quot;F_fixed3d&quot;,
            size=3,
            tag=&quot;force&quot;
        )

        # вычисляем локальную точку (обратное преобразование)
        pose = self.body.pose()
        self.r_local = pose.inverse_transform_point(self.joint_point)

        # актуализируем r в мировых
        self.update_radius()

        super().__init__([self.body.acceleration_var, self.internal_force], assembler=assembler)

    # -----------------------------------------------------------

    def update_radius(self):
        &quot;&quot;&quot;Обновить мировой радиус r = R * r_local.&quot;&quot;&quot;
        pose = self.body.pose()
        self.r = pose.transform_vector(self.r_local)
        self.radius = self.r

    # -----------------------------------------------------------

    def contribute(self, matrices, index_maps):
        &quot;&quot;&quot;
        Вклад в матрицу holonomic.
        Ограничение: e = p + r - j = 0.
        Якобиан: [ I3 | -skew(r) ].
        &quot;&quot;&quot;
        self.update_radius()

        H = matrices[&quot;holonomic&quot;]

        amap = index_maps[&quot;acceleration&quot;]
        cmap = index_maps[&quot;force&quot;]

        # индексы скоростей тела
        v_idx = amap[self.body.acceleration_var]      # 6 индексов
        # индексы внутренних сил
        f_idx = cmap[self.internal_force]     # 3 индексов

        # --- Заполняем якобиан ---
        # H[f, v]
        # линейные скорости: +I
        H[f_idx[0], v_idx[0]] += 1
        H[f_idx[1], v_idx[1]] += 1
        H[f_idx[2], v_idx[2]] += 1

        # угловые скорости: -[r]_×
        S = skew(self.r)
        # порядок v_idx[3:6] — (wx, wy, wz)
        H[np.ix_(f_idx, v_idx[3:6])] -= S


    # -----------------------------------------------------------

    def contribute_for_constraints_correction(self, matrices, index_maps):
        &quot;&quot;&quot;
        Для коррекции ограничений делаем то же самое.
        &quot;&quot;&quot;
        self.update_radius()
        self.contribute(matrices, index_maps)
        
        poserr = matrices[&quot;position_error&quot;]
        f_idx = index_maps[&quot;force&quot;][self.internal_force]


        # --- Позиционная ошибка ---
        pose = self.body.pose()
        p = pose.lin
        e = p + self.r - self.joint_point

        poserr[f_idx[0]] += e[0]
        poserr[f_idx[1]] += e[1]
        poserr[f_idx[2]] += e[2]


class RevoluteJoint3D(Contribution):
    &quot;&quot;&quot;
    3D револьвентный шарнир в смысле 2D-версии:
    совпадение двух точек на двух телах.
    
    Ограничения: (pA + rA) - (pB + rB) = 0   (3 eq)
    Не ограничивает ориентацию!
    Даёт 3 степени свободы на вращение.
    &quot;&quot;&quot;

    def __init__(self,
                 bodyA,
                 bodyB,
                 joint_point_world: np.ndarray,
                 assembler=None):

        self.bodyA = bodyA
        self.bodyB = bodyB

        # Внутренняя реакция — вектор из 3 компонент
        self.internal_force = Variable(&quot;F_rev3d&quot;, size=3,
                                       tag=&quot;force&quot;)

        # локальные точки крепления
        poseA = self.bodyA.pose()
        poseB = self.bodyB.pose()

        self.rA_local = poseA.inverse_transform_point(joint_point_world)
        self.rB_local = poseB.inverse_transform_point(joint_point_world)

        # обновляем мировую геометрию
        self.update_kinematics()

        super().__init__([bodyA.velocity, bodyB.velocity, self.internal_force],
                         assembler=assembler)

    # --------------------------------------------------------------

    def update_kinematics(self):
        poseA = self.bodyA.pose()
        poseB = self.bodyB.pose()

        self.pA = poseA.lin
        self.pB = poseB.lin

        self.rA = poseA.transform_vector(self.rA_local)
        self.rB = poseB.transform_vector(self.rB_local)

    # --------------------------------------------------------------

    def contribute(self, matrices, index_maps):
        self.update_kinematics()

        H = matrices[&quot;holonomic&quot;]

        amap = index_maps[&quot;acceleration&quot;]
        cmap = index_maps[&quot;force&quot;]

        vA = amap[self.bodyA.velocity]
        vB = amap[self.bodyB.velocity]

        F = cmap[self.internal_force]  # 3 строки

        # Матрицы скосов радиусов
        SA = skew(self.rA)
        SB = skew(self.rB)

        # dφ/dvA_lin = +I
        H[np.ix_(F, vA[0:3])] += np.eye(3)

        # dφ/dvA_ang = -skew(rA)
        H[np.ix_(F, vA[3:6])] += -SA

        # dφ/dvB_lin = -I
        H[np.ix_(F, vB[0:3])] += -np.eye(3)

        # dφ/dvB_ang = +skew(rB)
        H[np.ix_(F, vB[3:6])] += SB


    # --------------------------------------------------------------

    def contribute_for_constraints_correction(self, matrices, index_maps):
        self.update_kinematics()
        self.contribute(matrices, index_maps)
        cmap = index_maps[&quot;force&quot;]
        F = cmap[self.internal_force]  # 3 строки
        poserr = matrices[&quot;position_error&quot;]
        # позиционная ошибка: φ = (pA+rA) - (pB+rB)
        err = (self.pA + self.rA) - (self.pB + self.rB)

        poserr[F[0]] += err[0]
        poserr[F[1]] += err[1]
        poserr[F[2]] += err[2]
</code></pre>
</body>
</html>
