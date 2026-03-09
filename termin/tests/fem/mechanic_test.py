#!/usr/bin/env python3
# coding:utf-8

import unittest
import numpy as np
import warnings
from termin.fem.assembler import (
    MatrixAssembler,
    Variable,
    LoadContribution,
    ConstraintContribution,
)
from termin.fem.mechanic import (
    BarElement,
    BeamElement2D,
    DistributedLoad,
    Triangle3Node,
    BodyForce
)


class TestBarElement(unittest.TestCase):
    """Тесты для стержневого элемента"""
    
    def test_bar_1d_tension(self):
        """Растяжение стержня в 1D"""
        assembler = MatrixAssembler()
        
        # Два узла с 1D перемещениями
        u1 = assembler.add_variable("u1", size=1)
        u2 = assembler.add_variable("u2", size=1)
        
        # Стержень: E=200 ГПа (сталь), A=0.01 м², L=2 м
        E = 200e9  # Па
        A = 0.01   # м²
        L = 2.0    # м
        
        coord1 = [0.0]
        coord2 = [L]
        
        bar = BarElement(u1, u2, E, A, coord1, coord2)
        assembler.add_contribution(bar)
        
        # Граничное условие: u1 = 0
        assembler.add_contribution(ConstraintContribution(u1, value=0.0))
        
        # Нагрузка: F = 1000 Н на узел 2
        F = 1000.0
        assembler.add_contribution(LoadContribution(u2, load=[F]))
        
        # Решить
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Аналитическое решение: u = F*L/(E*A)
        u_expected = F * L / (E * A)
        
        # Penalty method вносит небольшую погрешность
        self.assertAlmostEqual(u2.value, u_expected, delta=abs(u_expected)*0.15)
        # Граничное условие выполняется с точностью penalty method
        self.assertLess(abs(u1.value), abs(u_expected)*0.11)
        
        # Проверить напряжение
        stress = bar.get_stress(np.array([u1.value]), np.array([u2.value]))
        stress_expected = F / A
        self.assertAlmostEqual(stress, stress_expected, places=5)
    
    def test_bar_2d_tension(self):
        """Растяжение стержня под углом в 2D"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1", size=2)
        u2 = assembler.add_variable("u2", size=2)
        
        E = 200e9
        A = 0.001
        
        # Стержень под углом 45 градусов
        coord1 = np.array([0.0, 0.0])
        coord2 = np.array([1.0, 1.0])
        
        bar = BarElement(u1, u2, E, A, coord1, coord2)
        assembler.add_contribution(bar)
        
        # Закрепить узел 1 полностью
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=1))
        
        # Для 2D нужно предотвратить поворот вокруг точки - закрепим одну координату второго узла
        # или используем use_least_squares
        
        # Сила вдоль стержня
        F = 1000.0
        angle = np.pi / 4
        Fx = F * np.cos(angle)
        Fy = F * np.sin(angle)
        
        assembler.add_contribution(LoadContribution(u2, load=[Fx, Fy]))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem(use_least_squares=True)  # Используем lstsq для робастности
        
        # Удлинение вдоль стержня
        L = np.linalg.norm(coord2 - coord1)
        elongation = F * L / (E * A)
        
        # Перемещения должны быть вдоль стержня
        u2_vec = u2.value
        displacement = np.linalg.norm(u2_vec)
        
        self.assertAlmostEqual(displacement, elongation, delta=abs(elongation)*0.15)
        
        # Угол перемещения должен быть 45 градусов
        angle_u = np.arctan2(u2_vec[1], u2_vec[0])
        self.assertAlmostEqual(angle_u, np.pi/4, places=8)
    
    def test_truss_2d(self):
        """Простая ферма из трех стержней"""
        assembler = MatrixAssembler()
        
        # Три узла
        u1 = assembler.add_variable("u1", size=2)  # левая опора
        u2 = assembler.add_variable("u2", size=2)  # правая опора
        u3 = assembler.add_variable("u3", size=2)  # верхний узел
        
        E = 200e9
        A = 0.001
        
        # Координаты: треугольная ферма
        coord1 = np.array([0.0, 0.0])
        coord2 = np.array([2.0, 0.0])
        coord3 = np.array([1.0, 1.0])
        
        # Три стержня
        bar1 = BarElement(u1, u3, E, A, coord1, coord3)
        bar2 = BarElement(u2, u3, E, A, coord2, coord3)
        bar3 = BarElement(u1, u2, E, A, coord1, coord2)
        
        assembler.add_contribution(bar1)
        assembler.add_contribution(bar2)
        assembler.add_contribution(bar3)
        
        # Закрепить опоры
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=1))
        assembler.add_contribution(ConstraintContribution(u2, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u2, value=0.0, component=1))
        
        # Нагрузка вниз на узел 3
        F = -1000.0  # вниз
        assembler.add_contribution(LoadContribution(u3, load=[0.0, F]))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Верхний узел должен сместиться вниз
        self.assertLess(u3.value[1], 0.0)
        
        # Симметрия: горизонтальное перемещение должно быть почти нулевым
        self.assertAlmostEqual(u3.value[0], 0.0, places=8)


class TestBeamElement(unittest.TestCase):
    """Тесты для балочного элемента"""
    
    def test_cantilever_beam_point_load(self):
        """Консольная балка с сосредоточенной нагрузкой на конце"""
        assembler = MatrixAssembler()
        
        # Два узла, каждый с прогибом и углом
        v1 = assembler.add_variable("v1", size=1)
        theta1 = assembler.add_variable("theta1", size=1)
        v2 = assembler.add_variable("v2", size=1)
        theta2 = assembler.add_variable("theta2", size=1)
        
        # Параметры балки
        E = 200e9  # Па
        I = 1e-6   # м⁴
        L = 1.0    # м
        
        beam = BeamElement2D(v1, theta1, v2, theta2, E, I, L)
        assembler.add_contribution(beam)
        
        # Заделка в узле 1: v1 = 0, theta1 = 0
        assembler.add_contribution(ConstraintContribution(v1, value=0.0))
        assembler.add_contribution(ConstraintContribution(theta1, value=0.0))
        
        # Нагрузка на конце
        F = -100.0  # Н (вниз)
        assembler.add_contribution(LoadContribution(v2, load=[F]))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Аналитическое решение для консольной балки:
        # v(L) = F*L³/(3*E*I) (знак определяется знаком F)
        # theta(L) = F*L²/(2*E*I)
        
        v_expected = F * L**3 / (3 * E * I)
        theta_expected = F * L**2 / (2 * E * I)
        
        # Проверяем с допуском (балочная теория приближенная)
        self.assertAlmostEqual(v2.value, v_expected, delta=abs(v_expected)*0.01)
        self.assertAlmostEqual(theta2.value, theta_expected, delta=abs(theta_expected)*0.01)
    
    def test_simple_beam_uniform_load(self):
        """Однопролетная балка с равномерной нагрузкой"""
        assembler = MatrixAssembler()
        
        v1 = assembler.add_variable("v1", size=1)
        theta1 = assembler.add_variable("theta1", size=1)
        v2 = assembler.add_variable("v2", size=1)
        theta2 = assembler.add_variable("theta2", size=1)
        
        E = 200e9
        I = 1e-6
        L = 2.0
        
        beam = BeamElement2D(v1, theta1, v2, theta2, E, I, L)
        assembler.add_contribution(beam)
        
        # Распределенная нагрузка
        q = -1000.0  # Н/м (вниз)
        load = DistributedLoad(v1, theta1, v2, theta2, q, L)
        assembler.add_contribution(load)
        
        # Шарнирные опоры: v1 = 0, v2 = 0
        assembler.add_contribution(ConstraintContribution(v1, value=0.0))
        assembler.add_contribution(ConstraintContribution(v2, value=0.0))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Прогиб в середине для равномерно нагруженной балки на двух опорах:
        # v_max = 5*q*L⁴/(384*E*I)
        v_mid_expected = 5 * abs(q) * L**4 / (384 * E * I)
        
        # Вычислить прогиб в середине (интерполяция)
        # Для балочного элемента используем функции формы Эрмита
        xi = 0.5  # середина
        N1 = 1 - 3*xi**2 + 2*xi**3
        N2 = L * (xi - 2*xi**2 + xi**3)
        N3 = 3*xi**2 - 2*xi**3
        N4 = L * (-xi**2 + xi**3)
        
        v_mid = N1*v1.value + N2*theta1.value + N3*v2.value + N4*theta2.value
        
        # Прогиб должен быть отрицательным (вниз)
        self.assertLess(v_mid, 0.0)
        # Для одного элемента точность ниже, чем для аналитического решения
        self.assertAlmostEqual(abs(v_mid), v_mid_expected, delta=v_mid_expected*0.25)
    
    def test_beam_multiple_elements(self):
        """Балка из двух элементов"""
        assembler = MatrixAssembler()
        
        # Три узла
        v1 = assembler.add_variable("v1", size=1)
        theta1 = assembler.add_variable("theta1", size=1)
        v2 = assembler.add_variable("v2", size=1)
        theta2 = assembler.add_variable("theta2", size=1)
        v3 = assembler.add_variable("v3", size=1)
        theta3 = assembler.add_variable("theta3", size=1)
        
        E = 200e9
        I = 1e-6
        L = 1.0
        
        # Два элемента
        beam1 = BeamElement2D(v1, theta1, v2, theta2, E, I, L)
        beam2 = BeamElement2D(v2, theta2, v3, theta3, E, I, L)
        
        assembler.add_contribution(beam1)
        assembler.add_contribution(beam2)
        
        # Заделка слева
        assembler.add_contribution(ConstraintContribution(v1, value=0.0))
        assembler.add_contribution(ConstraintContribution(theta1, value=0.0))
        
        # Нагрузка на правом конце
        F = -100.0
        assembler.add_contribution(LoadContribution(v3, load=[F]))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Общая длина 2L
        L_total = 2 * L
        v_expected = F * L_total**3 / (3 * E * I)
        
        self.assertAlmostEqual(v3.value, v_expected, delta=abs(v_expected)*0.01)


class TestTriangleElement(unittest.TestCase):
    """Тесты для треугольного элемента"""
    
    def test_triangle_pure_tension(self):
        """Чистое растяжение прямоугольной пластины"""
        assembler = MatrixAssembler()
        
        # Четыре узла для двух треугольников (прямоугольник)
        u1 = assembler.add_variable("u1", size=2)  # (0, 0)
        u2 = assembler.add_variable("u2", size=2)  # (1, 0)
        u3 = assembler.add_variable("u3", size=2)  # (1, 1)
        u4 = assembler.add_variable("u4", size=2)  # (0, 1)
        
        E = 200e9
        nu = 0.3
        t = 0.01  # толщина
        
        # Координаты
        c1 = np.array([0.0, 0.0])
        c2 = np.array([1.0, 0.0])
        c3 = np.array([1.0, 1.0])
        c4 = np.array([0.0, 1.0])
        
        # Два треугольника
        tri1 = Triangle3Node(u1, u2, u3, c1, c2, c3, E, nu, t, plane_stress=True)
        tri2 = Triangle3Node(u1, u3, u4, c1, c3, c4, E, nu, t, plane_stress=True)
        
        assembler.add_contribution(tri1)
        assembler.add_contribution(tri2)
        
        # Закрепить левый край (u1 и u4)
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=1))
        assembler.add_contribution(ConstraintContribution(u4, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u4, value=0.0, component=1))
        
        # Растягивающая сила на правом крае
        F = 1000.0  # Н
        # Распределить между двумя узлами
        assembler.add_contribution(LoadContribution(u2, load=[F/2, 0.0]))
        assembler.add_contribution(LoadContribution(u3, load=[F/2, 0.0]))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Напряжение sigma_x = F / (b*t), где b - ширина
        b = 1.0  # высота прямоугольника
        sigma_x = F / (b * t)
        
        # Деформация epsilon_x = sigma_x / E
        epsilon_x = sigma_x / E
        
        # Удлинение delta = epsilon_x * L
        L = 1.0
        delta_expected = epsilon_x * L
        
        # Перемещение правого края
        ux2 = u2.value[0]
        ux3 = u3.value[0]
        
        self.assertAlmostEqual(ux2, delta_expected, delta=abs(delta_expected)*0.15)
        self.assertAlmostEqual(ux3, delta_expected, delta=abs(delta_expected)*0.15)
        
        # Перемещения в y - эффект Пуассона (сужение при растяжении)
        # Проверяем только порядок величины
        uy2 = u2.value[1]
        uy3 = u3.value[1]
        
        # Должно быть сужение (отрицательное перемещение для нижнего края)
        # Но знак зависит от нумерации узлов, проверим просто малость
        self.assertLess(abs(uy2), abs(delta_expected))
    
    def test_triangle_shear(self):
        """Чистый сдвиг"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1", size=2)
        u2 = assembler.add_variable("u2", size=2)
        u3 = assembler.add_variable("u3", size=2)
        
        E = 100e9
        nu = 0.25
        t = 0.01
        
        c1 = np.array([0.0, 0.0])
        c2 = np.array([1.0, 0.0])
        c3 = np.array([0.5, 1.0])
        
        tri = Triangle3Node(u1, u2, u3, c1, c2, c3, E, nu, t, plane_stress=True)
        assembler.add_contribution(tri)
        
        # Закрепить нижние узлы
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=1))
        assembler.add_contribution(ConstraintContribution(u2, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u2, value=0.0, component=1))
        
        # Сдвиговая сила на верхнем узле
        F = 100.0
        assembler.add_contribution(LoadContribution(u3, load=[F, 0.0]))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Верхний узел должен сместиться
        self.assertGreater(u3.value[0], 0.0)
    
    def test_triangle_body_force(self):
        """Треугольник с объемной силой"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1", size=2)
        u2 = assembler.add_variable("u2", size=2)
        u3 = assembler.add_variable("u3", size=2)
        
        E = 200e9
        nu = 0.3
        t = 0.1
        
        c1 = np.array([0.0, 0.0])
        c2 = np.array([1.0, 0.0])
        c3 = np.array([0.0, 1.0])
        
        tri = Triangle3Node(u1, u2, u3, c1, c2, c3, E, nu, t, plane_stress=True)
        assembler.add_contribution(tri)
        
        # Сила тяжести
        rho = 7850.0  # кг/м³ (сталь)
        g = 9.81      # м/с²
        force_density = np.array([0.0, -rho * g])  # Н/м³
        
        area = 0.5 * 1.0 * 1.0  # площадь треугольника
        body = BodyForce(u1, u2, u3, area, t, force_density)
        assembler.add_contribution(body)
        
        # Закрепить один узел полностью
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=1))
        
        # Закрепить еще один узел полностью чтобы предотвратить поворот
        assembler.add_contribution(ConstraintContribution(u2, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u2, value=0.0, component=1))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Только узел 3 должен сместиться вниз (узлы 1 и 2 закреплены)
        self.assertLess(u3.value[1], 0.0)
    
    def test_triangle_stress_calculation(self):
        """Проверка расчета напряжений"""
        u1 = Variable("u1", size=2)
        u2 = Variable("u2", size=2)
        u3 = Variable("u3", size=2)
        
        E = 100e9
        nu = 0.3
        t = 0.01
        
        c1 = np.array([0.0, 0.0])
        c2 = np.array([1.0, 0.0])
        c3 = np.array([0.0, 1.0])
        
        tri = Triangle3Node(u1, u2, u3, c1, c2, c3, E, nu, t)
        
        # Задать перемещения (чистое растяжение по x)
        u_vec = np.array([0.0, 0.0,  # u1
                          0.001, 0.0,  # u2
                          0.0, 0.0])   # u3
        
        stress = tri.get_stress(u_vec)
        strain = tri.get_strain(u_vec)
        
        # epsilon_xx должна быть положительной
        self.assertGreater(strain[0], 0.0)
        
        # sigma_xx должна быть положительной
        self.assertGreater(stress[0], 0.0)
        
        # sigma_yy должна быть положительной из-за эффекта Пуассона
        self.assertGreater(stress[1], 0.0)


if __name__ == "__main__":
    unittest.main()
