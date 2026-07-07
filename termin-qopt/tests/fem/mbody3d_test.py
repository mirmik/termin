#!/usr/bin/env python3
# coding:utf-8

import unittest
import numpy as np
from termin.fem.dynamic_assembler import DynamicMatrixAssembler
from termin.fem.multibody3d_3 import (
    RigidBody3D, FixedRotationJoint3D #ForceOnBody3D, , RevoluteJoint3D
)
from termin.geombase import Pose3, Vec3
from numpy import linalg
from termin.fem.inertia3d import SpatialInertia3D


class TestIntegrationMultibody3D(unittest.TestCase):
    """Интеграционные тесты для многотельной системы"""

    def test_rigid_body_with_gravity(self):
        """Создание простой системы с одним твердым телом и гравитацией"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(mass=2.0, inertia=np.diag([1.0, 1.0, 1.0]), com=np.zeros(3)),
            gravity=np.array([0.0, 0.0, -9.81]),
            assembler=assembler)

        index_map = assembler.index_map()
        self.assertIn(body.acceleration_var, index_map)

        matrices = assembler.assemble()

        self.assertIn("mass", matrices)
        self.assertIn("load", matrices)
        self.assertIn("stiffness", matrices)
        self.assertIn("damping", matrices)

        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)

        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], -9.81)

    def test_rigid_body_with_gravity_noncentral_x(self):
        """Создание простой системы с одним твердым телом и гравитацией"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(mass=2.0, inertia=np.diag([1.0, 1.0, 1.0]), com=np.array([1.5, 0.0, 0.0])),
            gravity=np.array([0.0, 0.0, -9.81]),
            assembler=assembler)

        index_map = assembler.index_map()
        self.assertIn(body.acceleration_var, index_map)

        matrices = assembler.assemble()

        self.assertIn("mass", matrices)
        self.assertIn("load", matrices)
        self.assertIn("stiffness", matrices)
        self.assertIn("damping", matrices)

        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)




        x = linalg.solve(A_ext, b_ext)




        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], -9.81)
        assert np.isclose(x[3], 0.0)
        assert np.isclose(x[4], 0.0)
        assert np.isclose(x[5], 0.0)

    def test_rigid_body_with_gravity_noncentral_y(self):
        """Создание простой системы с одним твердым телом и гравитацией"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(mass=2.0, inertia=np.diag([1.0, 1.0, 1.0]), com=np.array([0.0, 1.5, 0.0])),
            gravity=np.array([0.0, 0.0, -9.81]),
            assembler=assembler)

        index_map = assembler.index_map()
        self.assertIn(body.acceleration_var, index_map)

        matrices = assembler.assemble()

        self.assertIn("mass", matrices)
        self.assertIn("load", matrices)
        self.assertIn("stiffness", matrices)
        self.assertIn("damping", matrices)

        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)
        x = linalg.solve(A_ext, b_ext)




        x = linalg.solve(A_ext, b_ext)



        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], -9.81)
        assert np.isclose(x[3], 0.0)
        assert np.isclose(x[4], 0.0)
        assert np.isclose(x[5], 0.0)
    
    def test_rigid_body_with_fixed_rotation_joint(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(mass=5.0, inertia=np.diag([5.0, 5.0, 5.0]), com=np.zeros(3)),
            gravity=np.array([0.0, 0.0, -10.00]),
            assembler=assembler)

        body.set_pose(Pose3(lin=Vec3([1.0, 0.0, 0.0])))

        joint = FixedRotationJoint3D(
            body=body,
            assembler=assembler,
            coords_of_joint = np.array([0.0, 0.0, 0.0]))

        
        assert joint.radius is not None
        assert joint.radius()[0] == -1.0
        assert joint.radius()[1] == 0.0
        assert assembler.total_variables_by_tag("acceleration") == 6
        assert assembler.total_variables_by_tag("force") == 3

        index_maps = assembler.index_maps()
        self.assertIn("acceleration", index_maps)
        self.assertIn("force", index_maps)
        self.assertEqual(len(index_maps["force"]), 1)
        self.assertEqual(len(index_maps["acceleration"]), 1)
        self.assertIn(body.acceleration_var, index_maps["acceleration"])
        self.assertIn(joint.internal_force, index_maps["force"])

        matrices = assembler.assemble()
        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)        
        x = linalg.solve(A_ext, b_ext)

        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], -5.0)

    def test_rigid_body_with_fixed_rotation_joint_outcenter(self):
        """Создание простой системы с одним твердым телом и фиксированным шарниром"""
        assembler = DynamicMatrixAssembler()
        
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(mass=5.0, inertia=np.diag([5.0, 5.0, 5.0]), com=np.array([0.75, 0.0, 0.0])),
            gravity=np.array([0.0, 0.0, -10.00]),
            assembler=assembler)

        body.set_pose(Pose3(lin=Vec3([0.25, 0.0, 0.0])))
        #body.acceleration_var.set_value_by_rank(np.array([0.0, 0.0, 1.0, 0.0, 0.0, 0.0]), rank=1)

        joint = FixedRotationJoint3D(
            body=body,
            assembler=assembler,
            coords_of_joint = np.array([0.0, 0.0, 0.0]))

        #joint.update_radius()

        assert joint.radius is not None
        assert assembler.total_variables_by_tag("acceleration") == 6
        assert assembler.total_variables_by_tag("force") == 3

        index_maps = assembler.index_maps()
        self.assertIn("acceleration", index_maps)
        self.assertIn("force", index_maps)
        self.assertEqual(len(index_maps["force"]), 1)
        self.assertEqual(len(index_maps["acceleration"]), 1)
        self.assertIn(body.acceleration_var, index_maps["acceleration"])
        self.assertIn(joint.internal_force, index_maps["force"])

        matrices = assembler.assemble()
        A_ext, b_ext, variables = assembler.assemble_extended_system(matrices)        
        x = linalg.solve(A_ext, b_ext)

        assert np.isclose(x[0], 0.0)
        assert np.isclose(x[1], 0.0)
        assert np.isclose(x[2], -1.25)
        assert np.isclose(x[3], 0.0)
        assert np.isclose(x[4], 5.0)
        assert np.isclose(x[5], 0.0)
        assert np.isclose(x[6], 0.0)
        assert np.isclose(x[7], 0.0)
        assert np.isclose(x[8], 25.0)


class TestIntegrationDynamics(unittest.TestCase):
    """Тесты интеграции во времени"""

    def _step_simulation(self, assembler):
        """Один шаг симуляции"""
        matrices = assembler.assemble()
        A_ext, b_ext, _ = assembler.assemble_extended_system(matrices)
        x_ext = np.linalg.solve(A_ext, b_ext)
        q_ddot, _, _ = assembler.sort_results(x_ext)
        assembler.integrate_with_constraint_projection(q_ddot, matrices)
        return q_ddot

    def test_free_fall_integration(self):
        """Свободное падение: z(t) = z0 + v0*t + 0.5*g*t²"""
        assembler = DynamicMatrixAssembler()
        dt = 0.01
        assembler.time_step = dt

        g = -10.0
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=1.0,
                inertia=np.diag([1.0, 1.0, 1.0]),
                com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, g]),
            assembler=assembler
        )

        z0 = 10.0
        body.set_pose(Pose3(lin=Vec3([0.0, 0.0, z0])))

        t_total = 0.2
        n_steps = int(t_total / dt)

        for _ in range(n_steps):
            self._step_simulation(assembler)

        # Ожидаемое положение: z = z0 + 0.5*g*t² = 10 + 0.5*(-10)*1² = 5
        z_expected = z0 + 0.5 * g * t_total**2
        z_actual = body.pose().lin[2]

        self.assertAlmostEqual(z_actual, z_expected, delta=0.1)

    def test_free_fall_velocity(self):
        """Свободное падение: v(t) = v0 + g*t"""
        assembler = DynamicMatrixAssembler()
        dt = 0.01
        assembler.time_step = dt

        g = -10.0
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=1.0,
                inertia=np.diag([1.0, 1.0, 1.0]),
                com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, g]),
            assembler=assembler
        )

        t_total = 0.2
        n_steps = int(t_total / dt)

        for _ in range(n_steps):
            self._step_simulation(assembler)

        # Ожидаемая скорость: vz = g*t = -10*1 = -10
        vz_expected = g * t_total
        vz_actual = body.velocity_var.value[2]

        self.assertAlmostEqual(vz_actual, vz_expected, delta=0.1)

    def test_energy_conservation_linear(self):
        """Сохранение кинетической энергии: тело с начальной скоростью без гравитации"""
        assembler = DynamicMatrixAssembler()
        dt = 0.01
        assembler.time_step = dt

        mass = 2.0
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=mass,
                inertia=np.diag([1.0, 1.0, 1.0]),
                com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, 0.0]),  # Без гравитации
            assembler=assembler
        )

        # Начальная скорость
        v0 = np.array([1.0, 2.0, 3.0])
        body.velocity_var.value[0:3] = v0

        # Начальная кинетическая энергия: E = 0.5 * m * v²
        E0 = 0.5 * mass * np.dot(v0, v0)

        t_total = 0.1
        n_steps = int(t_total / dt)

        for _step in range(n_steps):
            self._step_simulation(assembler)

        # Финальная энергия
        v_final = body.velocity_var.value[0:3]
        E_final = 0.5 * mass * np.dot(v_final, v_final)

        self.assertAlmostEqual(E_final, E0, delta=E0 * 0.01)  # 1% tolerance

    def test_energy_conservation_rotation(self):
        """Сохранение кинетической энергии вращения вокруг главной оси"""
        assembler = DynamicMatrixAssembler()
        dt = 0.01
        assembler.time_step = dt

        I_diag = np.array([1.0, 2.0, 3.0])  # Разные моменты инерции
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=1.0,
                inertia=np.diag(I_diag),
                com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, 0.0]),  # Без гравитации
            assembler=assembler
        )

        # Вращение вокруг оси Z (главная ось)
        omega0 = np.array([0.0, 0.0, 5.0])
        body.velocity_var.value[3:6] = omega0

        # Начальная энергия: E = 0.5 * I_z * omega_z²
        E0 = 0.5 * I_diag[2] * omega0[2]**2

        t_total = 0.2
        n_steps = int(t_total / dt)

        for _step in range(n_steps):
            self._step_simulation(assembler)

        # Финальная энергия
        omega_final = body.velocity_var.value[3:6]
        E_final = 0.5 * np.dot(I_diag * omega_final, omega_final)

        self.assertAlmostEqual(E_final, E0, delta=E0 * 0.01)

    def test_angular_momentum_conservation(self):
        """Сохранение углового момента свободного тела"""
        assembler = DynamicMatrixAssembler()
        dt = 0.01
        assembler.time_step = dt

        I_diag = np.array([1.0, 2.0, 3.0])
        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=1.0,
                inertia=np.diag(I_diag),
                com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, 0.0]),
            assembler=assembler
        )

        # Вращение вокруг оси Z
        omega0 = np.array([0.0, 0.0, 5.0])
        body.velocity_var.value[3:6] = omega0

        # Угловой момент L = I * omega (в локальной СК)
        L0 = I_diag * omega0
        L0_magnitude = np.linalg.norm(L0)

        t_total = 0.2
        n_steps = int(t_total / dt)

        for _ in range(n_steps):
            self._step_simulation(assembler)

        omega_final = body.velocity_var.value[3:6]
        L_final = I_diag * omega_final
        L_final_magnitude = np.linalg.norm(L_final)

        self.assertAlmostEqual(L_final_magnitude, L0_magnitude, delta=L0_magnitude * 0.01)

    def test_uniform_rotation(self):
        """Равномерное вращение вокруг главной оси: omega = const"""
        assembler = DynamicMatrixAssembler()
        dt = 0.01
        assembler.time_step = dt

        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=1.0,
                inertia=np.diag([1.0, 1.0, 1.0]),  # Симметричное тело
                com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, 0.0]),
            assembler=assembler
        )

        omega0 = 5.0
        body.velocity_var.value[3:6] = np.array([0.0, 0.0, omega0])

        t_total = 0.1
        n_steps = int(t_total / dt)

        for _ in range(n_steps):
            self._step_simulation(assembler)

        omega_final = body.velocity_var.value[5]

        self.assertAlmostEqual(omega_final, omega0, delta=0.01)

    def test_pendulum_small_oscillations(self):
        """Маятник: малые колебания, период T = 2π√(L/g)"""
        assembler = DynamicMatrixAssembler()
        dt = 0.001
        assembler.time_step = dt

        L = 1.0  # Длина маятника
        g = 10.0
        mass = 1.0

        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=mass,
                inertia=np.diag([0.01, 0.01, 0.01]),  # Точечная масса
                com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler
        )

        # Начальное положение: смещение на малый угол от вертикали
        theta0 = 0.1  # радианы
        x0 = L * np.sin(theta0)
        z0 = -L * np.cos(theta0)
        body.set_pose(Pose3(lin=Vec3([x0, 0.0, z0])))

        _joint = FixedRotationJoint3D(
            body=body,
            assembler=assembler,
            coords_of_joint=np.array([0.0, 0.0, 0.0])
        )

        # Теоретический период T ≈ 1.99s, симулируем половину периода
        t_total = 0.5
        n_steps = int(t_total / dt)

        for _step in range(n_steps):
            self._step_simulation(assembler)

        # После половины периода маятник должен быть примерно в противоположной точке
        x_final = body.pose().lin[0]


        # Проверяем что маятник качнулся в другую сторону
        self.assertLess(x_final, 0)  # должен быть отрицательным

    def test_total_energy_pendulum(self):
        """Маятник: сохранение полной механической энергии E = T + U"""
        assembler = DynamicMatrixAssembler()
        dt = 0.001
        assembler.time_step = dt

        L = 1.0
        g = 10.0
        mass = 1.0

        body = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=mass,
                inertia=np.diag([0.01, 0.01, 0.01]),
                com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler
        )

        theta0 = 0.3
        x0 = L * np.sin(theta0)
        z0 = -L * np.cos(theta0)
        body.set_pose(Pose3(lin=Vec3([x0, 0.0, z0])))

        _joint = FixedRotationJoint3D(
            body=body,
            assembler=assembler,
            coords_of_joint=np.array([0.0, 0.0, 0.0])
        )

        def compute_energy():
            pos = body.pose().lin
            vel = body.velocity_var.value[0:3]
            T = 0.5 * mass * np.dot(vel, vel)
            U = mass * g * pos[2]  # потенциальная энергия (z вверх)
            return T + U

        E0 = compute_energy()

        # Симулируем 0.5 секунды
        t_total = 0.5
        n_steps = int(t_total / dt)

        for _step in range(n_steps):
            self._step_simulation(assembler)

        E_final = compute_energy()


        # Энергия должна сохраняться с точностью 5%
        self.assertAlmostEqual(E_final, E0, delta=abs(E0) * 0.05)


class TestRevoluteJoint(unittest.TestCase):
    """Тесты RevoluteJoint3D"""

    def _step_simulation(self, assembler):
        """Один шаг симуляции"""
        matrices = assembler.assemble()
        A_ext, b_ext, _ = assembler.assemble_extended_system(matrices)
        x_ext = np.linalg.solve(A_ext, b_ext)
        q_ddot, _, _ = assembler.sort_results(x_ext)
        assembler.integrate_with_constraint_projection(q_ddot, matrices)
        return q_ddot

    def test_revolute_joint_symmetry(self):
        """RevoluteJoint должен быть симметричен при перестановке тел A и B"""
        from termin.fem.multibody3d_3 import RevoluteJoint3D

        # Конфигурация: два тела соединены шарниром
        def run_simulation(swap_bodies=False):
            assembler = DynamicMatrixAssembler()
            dt = 0.001
            assembler.time_step = dt

            bodyA = RigidBody3D(
                inertia=SpatialInertia3D.from_matrix(
                    mass=1.0, inertia=np.diag([0.1, 0.1, 0.1]), com=np.zeros(3)
                ),
                gravity=np.array([0.0, 0.0, -10.0]),
                assembler=assembler,
                name="bodyA"
            )
            bodyA.set_pose(Pose3(lin=Vec3([0.0, 0.0, 0.0])))

            bodyB = RigidBody3D(
                inertia=SpatialInertia3D.from_matrix(
                    mass=1.0, inertia=np.diag([0.1, 0.1, 0.1]), com=np.zeros(3)
                ),
                gravity=np.array([0.0, 0.0, -10.0]),
                assembler=assembler,
                name="bodyB"
            )
            bodyB.set_pose(Pose3(lin=Vec3([1.0, 0.0, 0.0])))

            # Фиксируем bodyA в начале координат
            _joint_fixed = FixedRotationJoint3D(
                body=bodyA,
                assembler=assembler,
                coords_of_joint=np.array([0.0, 0.0, 0.0])
            )

            # Соединяем A и B шарниром
            joint_coords = np.array([0.5, 0.0, 0.0])
            if swap_bodies:
                _joint_rev = RevoluteJoint3D(
                    bodyA=bodyB,
                    bodyB=bodyA,
                    coords_of_joint=joint_coords,
                    assembler=assembler
                )
            else:
                _joint_rev = RevoluteJoint3D(
                    bodyA=bodyA,
                    bodyB=bodyB,
                    coords_of_joint=joint_coords,
                    assembler=assembler
                )

            # Симуляция - 100 шагов достаточно
            positions = []
            for step in range(100):
                self._step_simulation(assembler)
                if step % 20 == 0:
                    positions.append(bodyB.pose().lin.copy())

            return positions

        pos_normal = run_simulation(swap_bodies=False)
        pos_swapped = run_simulation(swap_bodies=True)

        # Траектории должны быть одинаковыми
        for i, (p1, p2) in enumerate(zip(pos_normal, pos_swapped, strict=True)):
            diff = np.linalg.norm(p1 - p2)
            self.assertLess(diff, 0.1, f"Trajectories diverge at step {i*50}")

    def test_double_pendulum_energy(self):
        """Двойной маятник: сохранение полной энергии"""
        from termin.fem.multibody3d_3 import RevoluteJoint3D

        assembler = DynamicMatrixAssembler()
        dt = 0.001
        assembler.time_step = dt

        L1, L2 = 1.0, 1.0
        m1, m2 = 1.0, 1.0
        g = 10.0

        # Первое тело (верхний маятник)
        body1 = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=m1, inertia=np.diag([0.01, 0.01, 0.01]), com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler,
            name="body1"
        )
        theta1 = 0.2
        body1.set_pose(Pose3(lin=Vec3([L1 * np.sin(theta1), 0.0, -L1 * np.cos(theta1)])))

        # Второе тело (нижний маятник)
        body2 = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=m2, inertia=np.diag([0.01, 0.01, 0.01]), com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler,
            name="body2"
        )
        theta2 = 0.1
        pos2 = body1.pose().lin + np.array([L2 * np.sin(theta2), 0.0, -L2 * np.cos(theta2)])
        body2.set_pose(Pose3(lin=Vec3(pos2)))

        # Фиксируем первое тело в начале координат
        _joint_fixed = FixedRotationJoint3D(
            body=body1,
            assembler=assembler,
            coords_of_joint=np.array([0.0, 0.0, 0.0])
        )

        # Соединяем тела шарниром
        _joint_rev = RevoluteJoint3D(
            bodyA=body1,
            bodyB=body2,
            coords_of_joint=body1.pose().lin.copy(),
            assembler=assembler
        )

        def compute_energy():
            p1 = body1.pose().lin
            p2 = body2.pose().lin
            v1 = body1.velocity_var.value[0:3]
            v2 = body2.velocity_var.value[0:3]
            T = 0.5 * m1 * np.dot(v1, v1) + 0.5 * m2 * np.dot(v2, v2)
            U = m1 * g * p1[2] + m2 * g * p2[2]
            return T + U

        E0 = compute_energy()

        # Симуляция на 0.2 секунды
        n_steps = int(0.2 / dt)

        for _step in range(n_steps):
            self._step_simulation(assembler)

        E_final = compute_energy()


        # Энергия должна сохраняться с точностью 10% (двойной маятник более чувствителен)
        self.assertAlmostEqual(E_final, E0, delta=abs(E0) * 0.1)

    def test_vertical_double_pendulum_exact(self):
        """Точно как у пользователя: закреп в (0,0,0), body1 в (0,2,0), body2 в (0,4,0)"""
        from termin.fem.multibody3d_3 import RevoluteJoint3D

        assembler = DynamicMatrixAssembler()
        dt = 0.001
        assembler.time_step = dt

        g = 10.0
        m1, m2 = 1.0, 1.0

        # Точно как указал пользователь
        pos1 = np.array([0.0, 2.0, 0.0])
        pos2 = np.array([0.0, 4.0, 0.0])
        anchor = np.array([0.0, 0.0, 0.0])

        body1 = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=m1, inertia=np.diag([0.1, 0.1, 0.1]), com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler,
            name="body1"
        )
        body1.set_pose(Pose3(lin=Vec3(pos1)))

        body2 = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=m2, inertia=np.diag([0.1, 0.1, 0.1]), com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler,
            name="body2"
        )
        body2.set_pose(Pose3(lin=Vec3(pos2)))

        # Фиксируем body1 в (0, 0, 0)
        _joint_fixed = FixedRotationJoint3D(
            body=body1,
            assembler=assembler,
            coords_of_joint=anchor
        )

        # RevoluteJoint между body1 и body2 в позиции body1 = (0, 2, 0)
        _joint_rev = RevoluteJoint3D(
            bodyA=body1,
            bodyB=body2,
            coords_of_joint=pos1.copy(),
            assembler=assembler
        )

        # Выведем начальное состояние

        # L1 = расстояние от anchor до body1, L2 = расстояние от body1 до body2
        L1 = np.linalg.norm(pos1 - anchor)
        L2 = np.linalg.norm(pos2 - pos1)

        # Симуляция на 0.2 секунды
        n_steps = int(0.2 / dt)
        for _step in range(n_steps):
            matrices = assembler.assemble()
            A_ext, b_ext, _ = assembler.assemble_extended_system(matrices)
            x_ext = np.linalg.solve(A_ext, b_ext)
            q_ddot, _, _ = assembler.sort_results(x_ext)
            assembler.integrate_with_constraint_projection(q_ddot, matrices)

        # Проверка
        p1_final = body1.pose().lin
        p2_final = body2.pose().lin
        L1_final = np.linalg.norm(p1_final - anchor)
        L2_final = np.linalg.norm(p2_final - p1_final)

        self.assertAlmostEqual(L1_final, L1, delta=0.1)
        self.assertAlmostEqual(L2_final, L2, delta=0.1)

    def test_vertical_double_pendulum(self):
        """Вертикальный двойной маятник со смещением для ненулевой энергии"""
        from termin.fem.multibody3d_3 import RevoluteJoint3D

        assembler = DynamicMatrixAssembler()
        dt = 0.001
        assembler.time_step = dt

        g = 10.0
        m1, m2 = 1.0, 1.0

        # Смещённое от вертикали для ненулевой потенциальной энергии
        pos1 = np.array([0.0, 1.9, -0.6])  # |pos1| ≈ 2.0
        pos2 = np.array([0.0, 3.8, -1.2])  # |pos2 - pos1| ≈ 2.0

        body1 = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=m1, inertia=np.diag([0.1, 0.1, 0.1]), com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler,
            name="body1"
        )
        body1.set_pose(Pose3(lin=Vec3(pos1)))

        body2 = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=m2, inertia=np.diag([0.1, 0.1, 0.1]), com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler,
            name="body2"
        )
        body2.set_pose(Pose3(lin=Vec3(pos2)))

        # Фиксируем первое тело в (0, 0, 0)
        _joint_fixed = FixedRotationJoint3D(
            body=body1,
            assembler=assembler,
            coords_of_joint=np.array([0.0, 0.0, 0.0])
        )

        # Соединяем тела шарниром в (0, 2, 0) - позиция body1
        _joint_rev = RevoluteJoint3D(
            bodyA=body1,
            bodyB=body2,
            coords_of_joint=pos1.copy(),
            assembler=assembler
        )

        def compute_energy():
            p1 = body1.pose().lin
            p2 = body2.pose().lin
            v1 = body1.velocity_var.value[0:3]
            v2 = body2.velocity_var.value[0:3]
            omega1 = body1.velocity_var.value[3:6]
            omega2 = body2.velocity_var.value[3:6]

            I1 = np.diag([0.1, 0.1, 0.1])
            I2 = np.diag([0.1, 0.1, 0.1])

            T = 0.5 * m1 * np.dot(v1, v1) + 0.5 * m2 * np.dot(v2, v2)
            T += 0.5 * np.dot(omega1, I1 @ omega1) + 0.5 * np.dot(omega2, I2 @ omega2)
            U = m1 * g * p1[2] + m2 * g * p2[2]
            return T + U

        E0 = compute_energy()

        # Симуляция на 0.2 секунды
        n_steps = int(0.2 / dt)

        for _step in range(n_steps):
            self._step_simulation(assembler)

        E_final = compute_energy()

        # Проверяем что длины рычагов сохраняются
        p1_final = body1.pose().lin
        p2_final = body2.pose().lin
        L1_final = np.linalg.norm(p1_final)
        L2_final = np.linalg.norm(p2_final - p1_final)

        self.assertAlmostEqual(L1_final, 2.0, delta=0.1)
        self.assertAlmostEqual(L2_final, 2.0, delta=0.1)
        self.assertAlmostEqual(E_final, E0, delta=abs(E0) * 0.1)

    def test_double_pendulum_with_spin(self):
        """Двойной маятник с начальным вращением вдоль оси подвеса"""
        from termin.fem.multibody3d_3 import RevoluteJoint3D

        assembler = DynamicMatrixAssembler()
        dt = 0.001
        assembler.time_step = dt

        L1, L2 = 1.0, 1.0
        m1, m2 = 1.0, 1.0
        g = 10.0

        # Первое тело (верхний маятник)
        body1 = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=m1, inertia=np.diag([0.1, 0.1, 0.1]), com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler,
            name="body1"
        )
        # Начальное положение под углом
        theta1 = 0.2
        pos1 = np.array([L1 * np.sin(theta1), 0.0, -L1 * np.cos(theta1)])
        body1.set_pose(Pose3(lin=Vec3(pos1)))

        # Начальное вращение вдоль оси Y (ось подвеса) - высокая скорость
        omega_spin = 10.0
        omega1 = np.array([0.0, omega_spin, 0.0])
        body1.velocity_var.value[3:6] = omega1
        # Ограничение в локальной СК: v_lin + ω × r_local = 0
        # r_local - вектор от центра тела к точке крепления
        # Точка крепления в (0,0,0), центр в pos1, так что r_local = -pos1
        r1_local = -pos1  # вектор от центра тела к точке крепления
        v1 = -np.cross(omega1, r1_local)  # v_lin = -ω × r_local
        body1.velocity_var.value[0:3] = v1

        # Второе тело (нижний маятник)
        body2 = RigidBody3D(
            inertia=SpatialInertia3D.from_matrix(
                mass=m2, inertia=np.diag([0.1, 0.1, 0.1]), com=np.zeros(3)
            ),
            gravity=np.array([0.0, 0.0, -g]),
            assembler=assembler,
            name="body2"
        )
        theta2 = 0.1
        pos2 = pos1 + np.array([L2 * np.sin(theta2), 0.0, -L2 * np.cos(theta2)])
        body2.set_pose(Pose3(lin=Vec3(pos2)))

        # Второе тело тоже вращается (та же угловая скорость для совместимости)
        omega2 = np.array([0.0, omega_spin, 0.0])
        body2.velocity_var.value[3:6] = omega2
        # Ограничение для RevoluteJoint в СК body1:
        # Скорость точки крепления (pos1) от body1: v1 + ω1 × 0 = v1 (т.к. pos1 = центр body1)
        # Скорость точки крепления от body2: v2 + ω2 × r2_local
        # r2_local - вектор от центра body2 к точке крепления (pos1)
        r2_local = pos1 - pos2
        # Условие совместимости скоростей: v1 = v2 + ω2 × r2_local
        v2 = v1 - np.cross(omega2, r2_local)
        body2.velocity_var.value[0:3] = v2

        # Фиксируем первое тело в начале координат (ось Y)
        _joint_fixed = FixedRotationJoint3D(
            body=body1,
            assembler=assembler,
            coords_of_joint=np.array([0.0, 0.0, 0.0])
        )

        # Соединяем тела шарниром (ось Y)
        _joint_rev = RevoluteJoint3D(
            bodyA=body1,
            bodyB=body2,
            coords_of_joint=pos1.copy(),
            assembler=assembler
        )

        def compute_energy():
            p1 = body1.pose().lin
            p2 = body2.pose().lin
            v1 = body1.velocity_var.value[0:3]
            v2 = body2.velocity_var.value[0:3]
            omega1 = body1.velocity_var.value[3:6]
            omega2 = body2.velocity_var.value[3:6]

            I1 = np.diag([0.1, 0.1, 0.1])
            I2 = np.diag([0.1, 0.1, 0.1])

            # Кинетическая энергия (линейная + вращательная)
            T = 0.5 * m1 * np.dot(v1, v1) + 0.5 * m2 * np.dot(v2, v2)
            T += 0.5 * np.dot(omega1, I1 @ omega1) + 0.5 * np.dot(omega2, I2 @ omega2)

            # Потенциальная энергия
            U = m1 * g * p1[2] + m2 * g * p2[2]
            return T + U

        E0 = compute_energy()

        # Симуляция на 0.2 секунды
        n_steps = int(0.2 / dt)

        for _step in range(n_steps):
            self._step_simulation(assembler)

        E_final = compute_energy()

        # Энергия должна сохраняться с точностью 10%
        self.assertAlmostEqual(E_final, E0, delta=abs(E0) * 0.1)


if __name__ == "__main__":
    unittest.main()
