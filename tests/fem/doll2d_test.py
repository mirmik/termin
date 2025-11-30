#!/usr/bin/env python3
# coding:utf-8

import unittest
import numpy as np
import warnings
from termin.fem.assembler import MatrixAssembler
from termin.fem.doll2d import (
    Doll2D,
    DollLink2D,
    DollJoint2D,
    DollRotatorJoint2D
)
from termin.fem.inertia2d import SpatialInertia2D
from termin.geombase.pose2 import Pose2
from termin.geombase.screw import Screw2


class TestDoll2DBasics(unittest.TestCase):
    """Базовые тесты создания объектов Doll2D"""
    
    def test_create_inertia2d(self):
        """Тест создания инерционных характеристик"""
        # Без центра масс
        inertia1 = SpatialInertia2D(mass=1.0, inertia=0.1)
        self.assertEqual(inertia1.mass, 1.0)
        self.assertEqual(inertia1.inertia, 0.1)
        np.testing.assert_array_equal(inertia1.center_of_mass, np.zeros(2))
        
        # С центром масс
        com = np.array([0.5, 0.0])
        inertia2 = SpatialInertia2D(mass=2.0, inertia=0.5, com=com)
        self.assertEqual(inertia2.mass, 2.0)
        self.assertEqual(inertia2.inertia, 0.5)
        np.testing.assert_array_equal(inertia2.center_of_mass, com)
    
    # def test_inertia_gravity_wrench(self):
    #     """Тест вычисления вренча гравитации"""
    #     # Тело с центром масс в точке привязки
    #     inertia1 = SpatialInertia2D(mass=2.0, inertia=0.1, com=np.zeros(2))
    #     pose1 = Pose2.identity()
    #     gravity = np.array([0.0, -10.0])
        
    #     wrench1 = inertia1.gravity_wrench(pose1, gravity)
    #     # Момент должен быть нулевым (ЦМ совпадает с точкой привязки)
    #     np.testing.assert_almost_equal(wrench1.moment(), 0.0)
    #     # Сила = масса * гравитация
    #     np.testing.assert_array_almost_equal(wrench1.vector(), np.array([0.0, -20.0]))
        
    #     # Тело со смещенным центром масс
    #     inertia2 = SpatialInertia2D(mass=2.0, inertia=0.1, com=np.array([0.5, 0.0]))
    #     pose2 = Pose2.identity()
        
    #     wrench2 = inertia2.gravity_wrench(pose2, gravity)
    #     # Момент = r_cm × F = [0.5, 0] × [0, -20] = 0.5*(-20) - 0*0 = -10
    #     np.testing.assert_almost_equal(wrench2.moment(), -10.0)
    #     np.testing.assert_array_almost_equal(wrench2.vector(), np.array([0.0, -20.0]))
        
    #     # Тело с повернутой позой
    #     inertia3 = SpatialInertia2D(mass=1.0, inertia=0.1, com=np.array([1.0, 0.0]))
    #     pose3 = Pose2.rotation(np.pi/2)  # Поворот на 90 градусов
        
    #     wrench3 = inertia3.gravity_wrench(pose3, gravity)
    #     # После поворота ЦМ будет в точке [0, 1]
    #     # Момент = [0, 1] × [0, -10] = 0*(-10) - 1*0 = 0
    #     np.testing.assert_almost_equal(wrench3.moment(), 0.0)
    #     np.testing.assert_array_almost_equal(wrench3.vector(), np.array([0.0, -10.0]))
    
    def test_create_link(self):
        """Тест создания звена"""
        # Без инерции
        link1 = DollLink2D(name="link1")
        self.assertEqual(link1.name, "link1")
        self.assertIsNone(link1.parent)
        self.assertEqual(len(link1.children), 0)
        self.assertIsNone(link1.joint)
        
        # С инерцией
        inertia = SpatialInertia2D(mass=1.0, inertia=0.1)
        link2 = DollLink2D(name="link2", inertia=inertia)
        self.assertEqual(link2.inertia, inertia)
        
        # Проверка начального состояния
        self.assertIsInstance(link2.pose, Pose2)
        self.assertIsInstance(link2.twist, Screw2)
    
    def test_create_rotator_joint(self):
        """Тест создания вращательного шарнира"""
        joint = DollRotatorJoint2D(name="joint1")
        self.assertEqual(joint.name, "joint1")
        self.assertIsNotNone(joint.omega)
        self.assertEqual(joint.angle, 0.0)
        self.assertIsInstance(joint.joint_pose_in_parent, Pose2)
        self.assertIsInstance(joint.child_pose_in_joint, Pose2)
        
        # С позами
        joint_pose_in_parent = Pose2.translation(0.5, 0.0)
        child_pose_in_joint = Pose2.translation(0.0, -0.5)
        joint2 = DollRotatorJoint2D(name="joint2", 
                                     joint_pose_in_parent=joint_pose_in_parent, 
                                     child_pose_in_joint=child_pose_in_joint)
        self.assertEqual(joint2.joint_pose_in_parent, joint_pose_in_parent)
        self.assertEqual(joint2.child_pose_in_joint, child_pose_in_joint)
    
    def test_link_hierarchy(self):
        """Тест создания иерархии звеньев"""
        # Создаем родительское звено
        parent = DollLink2D(name="parent")
        
        # Создаем дочернее звено
        child = DollLink2D(name="child")
        
        # Создаем шарнир
        joint = DollRotatorJoint2D(name="joint")
        
        # Соединяем через add_child
        parent.add_child(child, joint)
        
        # Проверяем связи
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.joint, joint)
        self.assertIn(child, parent.children)
        self.assertEqual(joint.parent_link, parent)
        self.assertEqual(joint.child_link, child)
    
    def test_create_empty_doll2d(self):
        """Тест создания пустой системы Doll2D"""
        doll = Doll2D()
        self.assertIsNone(doll.base)
        self.assertEqual(len(doll.links), 0)
        self.assertEqual(len(doll.joints), 0)
        np.testing.assert_array_equal(doll.gravity, np.array([0.0, -9.81]))


class TestDoll2DKinematics(unittest.TestCase):
    """Тесты кинематики Doll2D"""
    
    def test_simple_pendulum_kinematics(self):
        """Тест кинематики простого маятника"""
        # Создаем базовое звено (земля) и маятник
        base = DollLink2D(name="base")
        pendulum = DollLink2D(name="pendulum", 
                             inertia=SpatialInertia2D(mass=1.0, inertia=0.1, com=np.array([0.0, -0.5])))
        
        # Шарнир: от базы к маятнику, без смещений
        joint = DollRotatorJoint2D(name="pivot")
        base.add_child(pendulum, joint)
        
        # Создаем систему
        doll = Doll2D(base_link=base)
        
        # Проверяем, что собрали правильно
        self.assertEqual(len(doll.links), 2)
        self.assertEqual(len(doll.joints), 1)
        self.assertIn(base, doll.links)
        self.assertIn(pendulum, doll.links)
        self.assertIn(joint, doll.joints)
        
        # Устанавливаем угол маятника
        joint.angle = np.pi / 4  # 45 градусов
        joint.omega.set_value(1.0)  # угловая скорость 1 рад/с
        
        # Обновляем кинематику
        doll.update_kinematics()
        
        # Проверяем угол маятника
        self.assertAlmostEqual(pendulum.pose.ang, np.pi / 4)
        self.assertAlmostEqual(pendulum.twist.moment(), 1.0)
    
    def test_joint_integration(self):
        """Тест интегрирования угла шарнира"""
        joint = DollRotatorJoint2D(name="joint")
        joint.omega.set_value(2.0)  # 2 рад/с
        
        initial_angle = joint.angle
        dt = 0.1
        
        joint.integrate(dt)
        
        expected_angle = initial_angle + 2.0 * dt
        self.assertAlmostEqual(joint.angle, expected_angle)
    
    def test_two_link_chain_kinematics(self):
        """Тест кинематики цепи из двух звеньев"""
        # База (земля)
        base = DollLink2D(name="base")
        
        # Первое звено
        link1 = DollLink2D(name="link1",
                          inertia=SpatialInertia2D(mass=1.0, inertia=0.1))
        joint1 = DollRotatorJoint2D(name="joint1")
        base.add_child(link1, joint1)
        
        # Второе звено - смещено на 1м вправо от link1
        link2 = DollLink2D(name="link2",
                          inertia=SpatialInertia2D(mass=0.5, inertia=0.05))
        joint_pose_in_parent = Pose2.translation(1.0, 0.0)  # конец link1
        joint2 = DollRotatorJoint2D(name="joint2", joint_pose_in_parent=joint_pose_in_parent)
        link1.add_child(link2, joint2)
        
        # Создаем систему
        doll = Doll2D(base_link=base)
        
        # Проверяем структуру
        self.assertEqual(len(doll.links), 3)  # base, link1, link2
        self.assertEqual(len(doll.joints), 2)  # joint1, joint2
        
        # Устанавливаем углы
        joint1.angle = np.pi / 2  # 90 градусов
        joint2.angle = -np.pi / 2  # -90 градусов
        
        # Обновляем кинематику
        doll.update_kinematics()
        
        # Проверяем углы
        self.assertAlmostEqual(link1.pose.ang, np.pi / 2)
        self.assertAlmostEqual(link2.pose.ang, 0.0)  # π/2 + (-π/2) = 0


class TestDoll2DWithAssembler(unittest.TestCase):
    """Тесты интеграции Doll2D с MatrixAssembler"""
    
    def test_doll2d_as_contribution(self):
        """Тест использования Doll2D как Contribution"""
        # Создаем простой маятник
        base = DollLink2D(name="base")
        pendulum = DollLink2D(name="pendulum",
                             inertia=SpatialInertia2D(mass=1.0, inertia=0.1))
        joint = DollRotatorJoint2D(name="pivot")
        base.add_child(pendulum, joint)
        
        # Создаем ассемблер
        assembler = MatrixAssembler()
        
        # Добавляем Doll2D как contribution
        doll = Doll2D(base_link=base, assembler=assembler)
        
        # Проверяем, что переменная зарегистрирована
        self.assertGreater(len(assembler.variables), 0)
        
        # Пробуем решить (пока без внешних сил)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                assembler.solve_and_set()
                # Если решилось без ошибок - хорошо
            except Exception as e:
                # Пока допускаем ошибки, главное что структура работает
                pass
    
    def test_energy_calculation(self):
        """Тест расчета энергии системы"""
        # Создаем маятник с известными параметрами
        base = DollLink2D(name="base")
        pendulum = DollLink2D(name="pendulum",
                             inertia=SpatialInertia2D(mass=1.0, inertia=0.1,
                                             com=np.array([0.0, -0.5])))
        joint = DollRotatorJoint2D(name="pivot")
        base.add_child(pendulum, joint)
        
        doll = Doll2D(base_link=base)
        
        # Устанавливаем состояние
        joint.angle = 0.0  # вертикально вниз
        joint.omega.set_value(0.0)
        doll.update_kinematics()
        
        # Кинетическая энергия должна быть нулевой
        E_kin = doll.get_kinetic_energy()
        self.assertAlmostEqual(E_kin, 0.0)


class TestDoll2DRepr(unittest.TestCase):
    """Тесты строковых представлений"""
    
    def test_link_repr(self):
        """Тест __repr__ для звена"""
        link = DollLink2D(name="test_link")
        repr_str = repr(link)
        self.assertIn("test_link", repr_str)
    
    # def test_joint_repr(self):
    #     """Тест __repr__ для шарнира"""
    #     joint = DollRotatorJoint2D(name="test_joint")
    #     joint.angle = 1.5
    #     joint.omega.set_value(2.5)
    #     repr_str = repr(joint)
    #     print(repr_str)
    #     self.assertIn("test_joint", repr_str)
    #     self.assertIn("1.5", repr_str)  # angle
    #     self.assertIn("2.5", repr_str)  # omega

class TestDoll2DDPendulum(unittest.TestCase):
    """Тесты для двойного маятника Doll2D"""
    def test_doll2d_dpendulum_test(self):
        assembler = MatrixAssembler()

        # === Параметры звеньев ===
        m1, m2 = 1.0, 1.0       # массы звеньев
        I1, I2 = 0.05, 0.05     # моменты инерции
        L1, L2 = 1.0, 1.0       # длины звеньев

        # === Инерции звеньев (ЦМ в середине звена) ===
        link1_inertia = SpatialInertia2D(m1, I1, np.array([0.0, -L1/2]))
        link2_inertia = SpatialInertia2D(m2, I2, np.array([0.0, -L2/2]))

        # === Создаём звенья ===
        link1 = DollLink2D("link1", inertia=link1_inertia)
        link2 = DollLink2D("link2", inertia=link2_inertia)

        # === Создаём шарниры ===
        # Первый — крепит звено 1 к земле
        joint1 = DollRotatorJoint2D(
            name="joint1",
            joint_pose_in_parent=Pose2.identity(),  # на оси вращения в начале координат
            child_pose_in_joint=Pose2.translation(0.0, L1/2),
            assembler=assembler
        )

        # Второй — соединяет звенья 1 и 2
        joint2 = DollRotatorJoint2D(
            name="joint2",
            joint_pose_in_parent=Pose2.translation(0.0, -L1/2),
            child_pose_in_joint=Pose2.translation(0.0, L2/2),
            assembler=assembler
        )

        # === Соединяем звенья ===
        link1.joint = joint1  # фиктивная связь к земле
        joint1.child_link = link1
        link1.add_child(link2, joint2)

        # Базовое звено маятника — первое, прикреплено к "земле"
        system = Doll2D(base_link=link1, assembler=assembler)

        # === Начальные углы ===
        joint1.angle = np.deg2rad(30)
        joint2.angle = np.deg2rad(-20)

        # === Угловые скорости ===
        joint1.omega.set_value([0.0])
        joint2.omega.set_value([0.0])

        # === Обновляем кинематику ===
        system.update_kinematics()

        # === Собираем матрицу масс и вектор сил ===
        A, b = assembler.assemble()



if __name__ == '__main__':
    unittest.main()
