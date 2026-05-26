#!/usr/bin/env python3
# coding:utf-8

import unittest
import numpy as np
import warnings
from termin.fem.assembler import (
    MatrixAssembler,
    spring_element,
    conductance_element,
    LoadContribution,
    ConstraintContribution,
    BilinearContribution
)


class TestSpringSystem(unittest.TestCase):
    """Тесты для системы пружин"""
    
    def test_two_springs_with_load(self):
        """
        Простая система из двух пружин:
        u1=0 ---[k1]--- u2 ---[k2]--- u3
                         ↓F
        """
        # Создать сборщик
        assembler = MatrixAssembler()
        
        # Добавить переменные (перемещения узлов)
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        u3 = assembler.add_variable("u3")
        
        # Добавить пружины
        k1 = 1000.0  # Н/м
        k2 = 2000.0  # Н/м
        
        assembler.add_contribution(spring_element(u1, u2, k1))
        assembler.add_contribution(spring_element(u2, u3, k2))
        
        # Граничное условие: u1 = 0 (закреплен)
        assembler.add_contribution(ConstraintContribution(u1, value=0.0))
        
        # Нагрузка: F = 100 Н на узел u2
        F = 100.0  # Н
        assembler.add_contribution(LoadContribution(u2, load=F))
        
        # Решить
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Проверить результаты
        self.assertAlmostEqual(u1.value, 0.0, places=6)
        self.assertAlmostEqual(u2.value, 0.1, places=6)
        self.assertAlmostEqual(u3.value, 0.1, places=6)
        
        # Проверка: сила в пружинах
        F1 = k1 * (u2.value - u1.value)
        F2 = k2 * (u3.value - u2.value)
        self.assertAlmostEqual(F1, F, places=6)
        self.assertAlmostEqual(F2, 0.0, places=6)
    
    def test_single_spring(self):
        """Тест одной пружины"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        
        k = 500.0  # Н/м
        assembler.add_contribution(spring_element(u1, u2, k))
        
        # Закрепить u1
        assembler.add_contribution(ConstraintContribution(u1, value=0.0))
        
        # Нагрузка на u2
        F = 50.0  # Н
        assembler.add_contribution(LoadContribution(u2, load=F))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Ожидаемое перемещение: u2 = F/k = 50/500 = 0.1
        self.assertAlmostEqual(u1.value, 0.0, places=6)
        self.assertAlmostEqual(u2.value, 0.1, places=6)


class TestElectricalCircuit(unittest.TestCase):
    """Тесты для электрических цепей"""
    
    def test_voltage_divider(self):
        """
        Делитель напряжения:
        V1=5V ---[R1]--- V2 ---[R2]--- V3=0V(GND)
        """
        assembler = MatrixAssembler()
        
        # Узлы (потенциалы)
        V1 = assembler.add_variable("V1")
        V2 = assembler.add_variable("V2")
        V3 = assembler.add_variable("V3")
        
        # Резисторы (через проводимость G = 1/R)
        R1 = 1000.0  # Ом
        R2 = 2000.0  # Ом
        G1 = 1.0 / R1
        G2 = 1.0 / R2
        
        assembler.add_contribution(conductance_element(V1, V2, G1))
        assembler.add_contribution(conductance_element(V2, V3, G2))
        
        # Граничные условия
        assembler.add_contribution(ConstraintContribution(V1, value=5.0))  # источник
        assembler.add_contribution(ConstraintContribution(V3, value=0.0))  # земля
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Проверить результаты
        self.assertAlmostEqual(V1.value, 5.0, places=6)
        self.assertAlmostEqual(V3.value, 0.0, places=6)
        
        # Аналитическое решение для делителя: V2 = V1 * R2/(R1+R2)
        V2_expected = 5.0 * R2 / (R1 + R2)
        self.assertAlmostEqual(V2.value, V2_expected, places=6)
        self.assertAlmostEqual(V2.value, 3.333333, places=5)
    
    def test_simple_resistor_circuit(self):
        """Простая цепь с одним резистором"""
        assembler = MatrixAssembler()
        
        V1 = assembler.add_variable("V1")
        V2 = assembler.add_variable("V2")
        
        R = 100.0  # Ом
        G = 1.0 / R
        
        assembler.add_contribution(conductance_element(V1, V2, G))
        
        # V1 = 10V, V2 = 0V
        assembler.add_contribution(ConstraintContribution(V1, value=10.0))
        assembler.add_contribution(ConstraintContribution(V2, value=0.0))
        
        assembler.solve_stiffness_problem()
        
        self.assertAlmostEqual(V1.value, 10.0, places=6)
        self.assertAlmostEqual(V2.value, 0.0, places=6)


class TestMultiDimensional(unittest.TestCase):
    """Тесты для многомерных систем"""
    
    def test_2d_displacement(self):
        """
        2D вектор - несколько компонент у переменной
        """
        assembler = MatrixAssembler()
        
        # Узел с двумя степенями свободы (ux, uy)
        u1 = assembler.add_variable("u1", size=2)  # [ux, uy]
        u2 = assembler.add_variable("u2", size=2)  # [ux, uy]
        
        # Простая "пружина" в 2D (изотропная жесткость)
        k = 1000.0
        K_2d = k * np.array([
            [ 1,  0, -1,  0],
            [ 0,  1,  0, -1],
            [-1,  0,  1,  0],
            [ 0, -1,  0,  1]
        ])
        
        assembler.add_contribution(BilinearContribution([u1, u2], K_2d))
        
        # Закрепить u1
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=0))  # ux = 0
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=1))  # uy = 0
        
        # Нагрузка на u2
        assembler.add_contribution(LoadContribution(u2, load=[100.0, 50.0]))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Проверить результаты
        np.testing.assert_array_almost_equal(u1.value, [0.0, 0.0], decimal=6)
        np.testing.assert_array_almost_equal(u2.value, [0.1, 0.05], decimal=6)
    
    def test_2d_anisotropic_element(self):
        """Тест анизотропного 2D элемента"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1", size=2)
        u2 = assembler.add_variable("u2", size=2)
        
        # Анизотропная жесткость (разная в x и y)
        kx = 1000.0
        ky = 500.0
        K_2d = np.array([
            [ kx,   0, -kx,   0],
            [  0,  ky,   0, -ky],
            [-kx,   0,  kx,   0],
            [  0, -ky,   0,  ky]
        ])
        
        assembler.add_contribution(BilinearContribution([u1, u2], K_2d))
        
        # Закрепить u1
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=0))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=1))
        
        # Одинаковая нагрузка в обоих направлениях
        F = 100.0
        assembler.add_contribution(LoadContribution(u2, load=[F, F]))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assembler.solve_stiffness_problem()
        
        # Ожидаемые перемещения: ux = F/kx, uy = F/ky
        expected_ux = F / kx
        expected_uy = F / ky
        
        self.assertAlmostEqual(u2.value[0], expected_ux, places=6)
        self.assertAlmostEqual(u2.value[1], expected_uy, places=6)


class TestMatrixAssembler(unittest.TestCase):
    """Тесты базовой функциональности MatrixAssembler"""
    
    def test_add_variable(self):
        """Тест добавления переменных"""
        assembler = MatrixAssembler()
        
        v1 = assembler.add_variable("v1")
        v2 = assembler.add_variable("v2", size=2)
        v3 = assembler.add_variable("v3", size=3)
        
        # Проверить, что индексы правильные
        self.assertIsNotNone(v1)
        self.assertIsNotNone(v2)
        self.assertIsNotNone(v3)
    
    def test_constraint_contribution(self):
        """Тест граничных условий"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        
        # Простая пружина
        k = 100.0
        assembler.add_contribution(spring_element(u1, u2, k))
        
        # Закрепить оба узла на разных значениях
        assembler.add_contribution(ConstraintContribution(u1, value=1.0))
        assembler.add_contribution(ConstraintContribution(u2, value=3.0))
        
        assembler.solve_stiffness_problem()
        
        # Оба узла должны быть на заданных значениях
        self.assertAlmostEqual(u1.value, 1.0, places=6)
        self.assertAlmostEqual(u2.value, 3.0, places=6)


class TestMatrixConditioning(unittest.TestCase):
    """Тесты для проверки обусловленности матриц"""
    
    def test_diagnose_matrix(self):
        """Тест метода диагностики матрицы"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        
        k = 1000.0
        assembler.add_contribution(spring_element(u1, u2, k))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, penalty=1e8))
        assembler.add_contribution(LoadContribution(u2, load=100.0))
        
        info = assembler.diagnose_matrix()
        
        # Проверить наличие всех ключей
        self.assertIn('condition_number', info)
        self.assertIn('is_symmetric', info)
        self.assertIn('rank', info)
        self.assertIn('quality', info)
        
        # Матрица должна быть симметричной
        self.assertTrue(info['is_symmetric'])
        
        # Матрица должна иметь полный ранг
        self.assertEqual(info['rank'], 2)
        self.assertTrue(info['is_full_rank'])
    
    def test_well_conditioned_system(self):
        """Тест хорошо обусловленной системы"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        
        k = 1000.0
        assembler.add_contribution(spring_element(u1, u2, k))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, penalty=1e8))
        assembler.add_contribution(LoadContribution(u2, load=100.0))
        
        info = assembler.diagnose_matrix()
        
        # Число обусловленности должно быть разумным
        self.assertLess(info['condition_number'], 1e10)
        self.assertIn(info['quality'], ['excellent', 'good', 'acceptable'])
    
    def test_ill_conditioned_warning(self):
        """Тест предупреждения о плохой обусловленности"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        
        k = 1000.0
        assembler.add_contribution(spring_element(u1, u2, k))
        # Очень большой penalty
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, penalty=1e15))
        assembler.add_contribution(LoadContribution(u2, load=100.0))
        
        # Должно выдать предупреждение
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            solution = assembler.solve_stiffness_problem(check_conditioning=True)
            
            # Проверить, что было предупреждение
            self.assertGreater(len(w), 0)
            self.assertTrue(any('обусловлена' in str(warning.message) or 
                               'conditioned' in str(warning.message).lower() 
                               for warning in w))
    
    def test_singular_matrix_error(self):
        """Тест ошибки при вырожденной матрице (без граничных условий)"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        u3 = assembler.add_variable("u3")
        
        # Только пружины, без закреплений - свободное перемещение
        k = 1000.0
        assembler.add_contribution(spring_element(u1, u2, k))
        assembler.add_contribution(spring_element(u2, u3, k))
        assembler.add_contribution(LoadContribution(u2, load=100.0))
        
        # Диагностика должна показать неполный ранг
        info = assembler.diagnose_matrix()
        self.assertFalse(info['is_full_rank'])
        self.assertLess(info['rank'], info['expected_rank'])
        
        # Попытка решения должна вызвать ошибку
        with self.assertRaises(RuntimeError):
            assembler.solve_stiffness_problem(check_conditioning=False, use_least_squares=False)
    
    def test_least_squares_solver(self):
        """Тест решателя методом наименьших квадратов"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        
        k = 1000.0
        assembler.add_contribution(spring_element(u1, u2, k))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0))
        assembler.add_contribution(LoadContribution(u2, load=100.0))
        
        # Решить через least squares
        assembler.solve_stiffness_problem(use_least_squares=True, check_conditioning=False)
        
        # Результат должен быть близок к точному
        self.assertAlmostEqual(u1.value, 0.0, places=5)
        self.assertAlmostEqual(u2.value, 0.1, places=5)
    
    def test_penalty_comparison(self):
        """Тест сравнения разных значений penalty"""
        results = {}
        
        for penalty in [1e8, 1e10, 1e12]:
            assembler = MatrixAssembler()
            
            u1 = assembler.add_variable("u1")
            u2 = assembler.add_variable("u2")
            
            k = 1000.0
            assembler.add_contribution(spring_element(u1, u2, k))
            assembler.add_contribution(ConstraintContribution(u1, value=0.0, penalty=penalty))
            assembler.add_contribution(LoadContribution(u2, load=100.0))
            
            assembler.solve_stiffness_problem(check_conditioning=False)
            results[penalty] = u2.value
        
        # Все результаты должны быть близки друг к другу
        expected = 0.1
        for penalty, value in results.items():
            self.assertAlmostEqual(value, expected, places=3,
                                 msg=f"Penalty={penalty} дал неверный результат")
    
    def test_symmetric_matrix(self):
        """Тест симметричности матрицы жёсткости"""
        assembler = MatrixAssembler()
        
        # Создать несколько узлов
        nodes = [assembler.add_variable(f"u{i}") for i in range(4)]
        
        # Пружины
        k = 1000.0
        for i in range(3):
            assembler.add_contribution(spring_element(nodes[i], nodes[i+1], k))
        
        # Граничные условия
        assembler.add_contribution(ConstraintContribution(nodes[0], value=0.0))
        
        # Нагрузка
        assembler.add_contribution(LoadContribution(nodes[2], load=100.0))
        
        # Собрать матрицу и проверить симметричность
        A, b = assembler.assemble()
        
        self.assertTrue(np.allclose(A, A.T), "Матрица жёсткости должна быть симметричной")
    
    def test_positive_definite(self):
        """Тест положительной определённости матрицы"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        
        k = 1000.0
        assembler.add_contribution(spring_element(u1, u2, k))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0, penalty=1e8))
        assembler.add_contribution(LoadContribution(u2, load=100.0))
        
        info = assembler.diagnose_matrix()
        
        # Матрица должна быть положительно определённой
        if info.get('is_positive_definite') is not None:
            self.assertTrue(info['is_positive_definite'])
            self.assertGreater(info['min_eigenvalue'], 0)
    
    def test_print_diagnose(self):
        """Тест человекочитаемого вывода диагностики"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1")
        u2 = assembler.add_variable("u2")
        
        k = 1000.0
        assembler.add_contribution(spring_element(u1, u2, k))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0))
        assembler.add_contribution(LoadContribution(u2, load=100.0))
        
        # Просто проверяем, что не падает
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            assembler.print_diagnose()
            output = sys.stdout.getvalue()
            
            # Проверяем наличие ключевых слов
            self.assertIn('DIAGNOSTICS', output)
            self.assertIn('dimensions', output)
            self.assertIn('rank', output)
            self.assertIn('Conditioning', output)
        finally:
            sys.stdout = old_stdout


class TestVariableSolution(unittest.TestCase):
    """Тесты для сохранения решения в переменные"""
    
    def test_set_solution_to_variables(self):
        """Проверка метода set_solution_to_variables"""
        assembler = MatrixAssembler()
        
        # Скалярные переменные
        u1 = assembler.add_variable("u1", size=1)
        u2 = assembler.add_variable("u2", size=1)
        
        # Простая система
        assembler.add_contribution(spring_element(u1, u2, 1000.0))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0))
        assembler.add_contribution(LoadContribution(u2, load=[100.0]))
        
        # Решить
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            x = assembler.solve_stiffness_problem()
        
        # Сохранить в переменные
        assembler.set_solution_to_variables(x)
        
        # Проверить что значения сохранены
        self.assertIsNotNone(u1.value)
        self.assertIsNotNone(u2.value)
        
        # Проверить правильность значений
        self.assertAlmostEqual(u1.value, 0.0, delta=1e-6)
        self.assertAlmostEqual(u2.value, 0.1, delta=1e-6)
        
        # Проверить что это скаляры (не массивы)
        self.assertIsInstance(u1.value, (float, np.floating))
        self.assertIsInstance(u2.value, (float, np.floating))
    
    def test_set_solution_vector_variables(self):
        """Проверка сохранения векторных переменных"""
        assembler = MatrixAssembler()
        
        # Векторные переменные
        u1 = assembler.add_variable("u1", size=3)
        u2 = assembler.add_variable("u2", size=3)
        
        # Три независимые пружины (по одной на каждую степень свободы)
        for i in range(3):
            k_row = [0.0] * 6
            k_row[i] = 1000.0
            k_row[i + 3] = -1000.0
            K_row = np.zeros((6, 6))
            K_row[i, :] = k_row
            k_row2 = [0.0] * 6
            k_row2[i] = -1000.0
            k_row2[i + 3] = 1000.0
            K_row[i + 3, :] = k_row2
            assembler.add_contribution(BilinearContribution([u1, u2], K_row))
        
        # Закрепить первый узел
        for i in range(3):
            assembler.add_contribution(ConstraintContribution(u1, value=0.0, component=i))
        
        # Нагрузка на второй узел
        assembler.add_contribution(LoadContribution(u2, load=[100.0, 200.0, 300.0]))
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            x = assembler.solve_stiffness_problem(check_conditioning=False)
        
        assembler.set_solution_to_variables(x)
        
        # Проверить что значения сохранены
        self.assertIsNotNone(u1.value)
        self.assertIsNotNone(u2.value)
        
        # Для векторов должны быть numpy массивы
        self.assertIsInstance(u1.value, np.ndarray)
        self.assertIsInstance(u2.value, np.ndarray)
        
        # Проверить размерность
        self.assertEqual(len(u1.value), 3)
        self.assertEqual(len(u2.value), 3)
        
        # Проверить значения
        np.testing.assert_allclose(u1.value, [0.0, 0.0, 0.0], atol=1e-5)
        # Перемещения должны быть положительными
        self.assertGreater(u2.value[0], 0.0)
        self.assertGreater(u2.value[1], 0.0)
        self.assertGreater(u2.value[2], 0.0)
    
    def test_solve_and_set(self):
        """Проверка метода solve_and_set"""
        assembler = MatrixAssembler()
        
        u1 = assembler.add_variable("u1", size=1)
        u2 = assembler.add_variable("u2", size=1)
        u3 = assembler.add_variable("u3", size=1)
        
        # Три узла, две пружины
        k1, k2 = 1000.0, 2000.0
        assembler.add_contribution(spring_element(u1, u2, k1))
        assembler.add_contribution(spring_element(u2, u3, k2))
        assembler.add_contribution(ConstraintContribution(u1, value=0.0))
        assembler.add_contribution(LoadContribution(u2, load=[100.0]))
        
        # Решить и сохранить одним вызовом
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            x = assembler.solve_stiffness_problem()
        
        # Проверить что все переменные заполнены
        self.assertIsNotNone(u1.value)
        self.assertIsNotNone(u2.value)
        self.assertIsNotNone(u3.value)
        
        # Проверить что можно работать напрямую с переменными
        self.assertAlmostEqual(u1.value, 0.0, delta=1e-6)
        self.assertGreater(u2.value, 0.0)
        self.assertGreater(u3.value, u2.value)
        
        # Проверить что возвращенное значение x соответствует переменным
        # x содержит все значения подряд
        self.assertAlmostEqual(u1.value, x[0], places=10)
        self.assertAlmostEqual(u2.value, x[1], places=10)
        self.assertAlmostEqual(u3.value, x[2], places=10)


if __name__ == "__main__":
    unittest.main()

