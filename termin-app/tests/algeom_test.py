"""Тесты для модуля алгебраической геометрии."""
import unittest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from termin.algeom import (
    fit_ellipsoid,
    fit_quadric,
    fit_hyperboloid,
    fit_paraboloid,
    evaluate_ellipsoid,
    ellipsoid_contains,
    ellipsoid_equation,
    ellipsoid_volume
)


class TestFitEllipsoid(unittest.TestCase):
    """Тесты для подгонки эллипсоида по точкам."""
    
    def test_sphere_basic(self):
        """Сфера радиуса 2"""
        # Генерируем точки на сфере
        n = 30
        theta = np.linspace(0, 2*np.pi, n)
        phi = np.linspace(0, np.pi, n // 2)
        
        points = []
        for p in phi:
            for t in theta:
                x = 2 * np.sin(p) * np.cos(t)
                y = 2 * np.sin(p) * np.sin(t)
                z = 2 * np.cos(p)
                points.append([x, y, z])
        
        points = np.array(points)
        A, center, radii, axes = fit_ellipsoid(points)
        
        # Проверяем, что все полуоси примерно равны 2
        np.testing.assert_allclose(radii, [2, 2, 2], rtol=0.01, atol=1e-10)
        
        # Проверяем, что центр близок к нулю
        np.testing.assert_allclose(center, [0, 0, 0], atol=0.1)
    
    def test_ellipsoid_3d(self):
        """Эллипсоид с полуосями a=3, b=2, c=1"""
        # Генерируем точки на эллипсоиде
        n = 30
        theta = np.linspace(0, 2*np.pi, n)
        phi = np.linspace(0, np.pi, n // 2)
        
        a, b, c = 3.0, 2.0, 1.0
        
        points = []
        for p in phi:
            for t in theta:
                x = a * np.sin(p) * np.cos(t)
                y = b * np.sin(p) * np.sin(t)
                z = c * np.cos(p)
                points.append([x, y, z])
        
        points = np.array(points)
        A, center, radii, axes = fit_ellipsoid(points)
        
        # Проверяем полуоси (с небольшой погрешностью из-за дискретизации)
        expected_radii = np.array([a, b, c])
        np.testing.assert_allclose(radii, expected_radii, rtol=0.01, atol=1e-10)
        
        # Центр должен быть близок к нулю
        np.testing.assert_allclose(center, [0, 0, 0], atol=0.1)
    
    def test_ellipsoid_2d(self):
        """Эллипс на плоскости с полуосями a=5, b=3"""
        # Генерируем точки на эллипсе
        t = np.linspace(0, 2*np.pi, 100)
        a, b = 5.0, 3.0
        
        x = a * np.cos(t)
        y = b * np.sin(t)
        points = np.column_stack([x, y])
        
        A, center, radii, axes = fit_ellipsoid(points)
        
        # Проверяем полуоси
        np.testing.assert_allclose(radii, [a, b], rtol=0.01, atol=1e-10)
        
        # Центр близок к нулю
        np.testing.assert_allclose(center, [0, 0], atol=0.1)
    
    def test_ellipsoid_with_offset(self):
        """Эллипсоид со смещённым центром"""
        # Эллипсоид с центром в (1, 2, 3)
        center_true = np.array([1.0, 2.0, 3.0])
        a, b, c = 4.0, 3.0, 2.0
        
        n = 30
        theta = np.linspace(0, 2*np.pi, n)
        phi = np.linspace(0, np.pi, n // 2)
        
        points = []
        for p in phi:
            for t in theta:
                x = center_true[0] + a * np.sin(p) * np.cos(t)
                y = center_true[1] + b * np.sin(p) * np.sin(t)
                z = center_true[2] + c * np.cos(p)
                points.append([x, y, z])
        
        points = np.array(points)
        A, center, radii, axes = fit_ellipsoid(points)
        
        # Проверяем центр
        np.testing.assert_allclose(center, center_true, atol=0.1)
        
        # Проверяем полуоси
        np.testing.assert_allclose(radii, [a, b, c], rtol=0.01, atol=1e-10)
    
    def test_ellipsoid_with_fixed_center(self):
        """Подгонка эллипсоида с заданным центром"""
        center_fixed = np.array([0.0, 0.0, 0.0])
        a, b, c = 2.0, 1.5, 1.0
        
        # Генерируем точки
        n = 30
        theta = np.linspace(0, 2*np.pi, n)
        phi = np.linspace(0, np.pi, n // 2)
        
        points = []
        for p in phi:
            for t in theta:
                x = a * np.sin(p) * np.cos(t)
                y = b * np.sin(p) * np.sin(t)
                z = c * np.cos(p)
                points.append([x, y, z])
        
        points = np.array(points)
        A, center, radii, axes = fit_ellipsoid(points, center=center_fixed)
        
        # Центр должен быть точно равен заданному
        np.testing.assert_array_equal(center, center_fixed)
        
        # Полуоси должны совпадать
        np.testing.assert_allclose(radii, [a, b, c], rtol=0.01, atol=1e-10)
    
    def test_rotated_ellipsoid(self):
        """Эллипсоид с поворотом"""
        # Создаём эллипсоид, повёрнутый на 45° вокруг оси Z
        angle = np.pi / 4
        R = np.array([
            [np.cos(angle), -np.sin(angle), 0],
            [np.sin(angle), np.cos(angle), 0],
            [0, 0, 1]
        ])
        
        a, b, c = 3.0, 2.0, 1.0
        
        n = 30
        theta = np.linspace(0, 2*np.pi, n)
        phi = np.linspace(0, np.pi, n // 2)
        
        points = []
        for p in phi:
            for t in theta:
                # Точка на стандартном эллипсоиде
                point = np.array([
                    a * np.sin(p) * np.cos(t),
                    b * np.sin(p) * np.sin(t),
                    c * np.cos(p)
                ])
                # Поворачиваем
                rotated = R @ point
                points.append(rotated)
        
        points = np.array(points)
        A, center, radii, axes = fit_ellipsoid(points)
        
        # Полуоси должны совпадать (инвариантны к повороту)
        np.testing.assert_allclose(radii, [a, b, c], rtol=0.01, atol=1e-10)
        
        # Центр близок к нулю
        np.testing.assert_allclose(center, [0, 0, 0], atol=0.1)
    
    def test_insufficient_points(self):
        """Ошибка при недостаточном количестве точек"""
        # Для 3D нужно минимум 9 точек
        points = np.random.randn(5, 3)
        
        with self.assertRaises(ValueError) as ctx:
            fit_ellipsoid(points)
        
        self.assertIn("Недостаточно точек", str(ctx.exception))
    
    def test_noisy_data(self):
        """Подгонка с зашумлёнными данными"""
        a, b, c = 2.0, 1.5, 1.0
        
        # Генерируем точки с шумом
        n = 50
        theta = np.linspace(0, 2*np.pi, n)
        phi = np.linspace(0, np.pi, n // 2)
        
        points = []
        for p in phi:
            for t in theta:
                x = a * np.sin(p) * np.cos(t)
                y = b * np.sin(p) * np.sin(t)
                z = c * np.cos(p)
                # Добавляем шум
                noise = np.random.randn(3) * 0.05
                points.append(np.array([x, y, z]) + noise)
        
        points = np.array(points)
        A, center, radii, axes = fit_ellipsoid(points)
        
        # С шумом точность снижается, но должна быть разумной
        np.testing.assert_allclose(radii, [a, b, c], rtol=0.1)


class TestEvaluateEllipsoid(unittest.TestCase):
    """Тесты для вычисления значений квадратичной формы."""
    
    def test_points_on_surface(self):
        """Точки на поверхности дают значение ≈ 1"""
        # Создаём единичную сферу
        A = np.eye(3)
        center = np.zeros(3)
        
        # Точки на единичной сфере
        points = np.array([
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1],
            [1/np.sqrt(2), 1/np.sqrt(2), 0]
        ])
        
        values = evaluate_ellipsoid(points, A, center)
        
        np.testing.assert_allclose(values, [1, 1, 1, 1], atol=1e-10)
    
    def test_points_inside(self):
        """Точки внутри дают значение < 1"""
        A = np.eye(3)
        center = np.zeros(3)
        
        # Точки внутри единичной сферы
        points = np.array([
            [0, 0, 0],  # Центр
            [0.5, 0, 0],
            [0.3, 0.3, 0.3]
        ])
        
        values = evaluate_ellipsoid(points, A, center)
        
        self.assertTrue(np.all(values < 1))
        self.assertAlmostEqual(values[0], 0)  # Центр
    
    def test_points_outside(self):
        """Точки снаружи дают значение > 1"""
        A = np.eye(3)
        center = np.zeros(3)
        
        # Точки снаружи единичной сферы
        points = np.array([
            [2, 0, 0],
            [1.5, 1.5, 0]
        ])
        
        values = evaluate_ellipsoid(points, A, center)
        
        self.assertTrue(np.all(values > 1))


class TestEllipsoidEquation(unittest.TestCase):
    """Тесты для форматирования уравнения эллипсоида."""
    
    def test_sphere_equation(self):
        """Уравнение единичной сферы"""
        A = np.eye(3)
        center = np.zeros(3)
        
        eq = ellipsoid_equation(A, center)
        
        # Проверяем, что строка содержит базовую структуру
        self.assertIsInstance(eq, str)
        self.assertIn("x-c", eq.lower())
    
    def test_ellipsoid_with_center(self):
        """Уравнение эллипсоида со смещённым центром"""
        A = np.diag([1/4, 1/9, 1/16])
        center = np.array([1.0, 2.0, 3.0])
        
        eq = ellipsoid_equation(A, center)
        
        self.assertIsInstance(eq, str)
        # Проверяем, что центр представлен в уравнении
        self.assertIn("1.", eq)  # содержит координату 1.0
        self.assertIn("2.", eq)  # содержит координату 2.0
        self.assertIn("3.", eq)  # содержит координату 3.0


class TestEllipsoidVolume(unittest.TestCase):
    """Тесты для вычисления объёма эллипсоида."""
    
    def test_unit_sphere_2d(self):
        """Площадь единичного круга: π"""
        radii = np.array([1.0, 1.0])
        volume = ellipsoid_volume(radii)
        
        expected = np.pi
        np.testing.assert_allclose(volume, expected, rtol=1e-10)
    
    def test_unit_sphere_3d(self):
        """Объём единичной сферы: 4π/3"""
        radii = np.array([1.0, 1.0, 1.0])
        volume = ellipsoid_volume(radii)
        
        expected = 4 * np.pi / 3
        np.testing.assert_allclose(volume, expected, rtol=1e-10)
    
    def test_ellipsoid_2d(self):
        """Площадь эллипса с полуосями a=3, b=2"""
        radii = np.array([3.0, 2.0])
        volume = ellipsoid_volume(radii)
        
        # S = π*a*b
        expected = np.pi * 3 * 2
        np.testing.assert_allclose(volume, expected, rtol=1e-10)
    
    def test_ellipsoid_3d(self):
        """Объём эллипсоида с полуосями a=3, b=2, c=1"""
        radii = np.array([3.0, 2.0, 1.0])
        volume = ellipsoid_volume(radii)
        
        # V = (4π/3)*a*b*c
        expected = (4 * np.pi / 3) * 3 * 2 * 1
        np.testing.assert_allclose(volume, expected, rtol=1e-10)
    
    def test_unit_sphere_4d(self):
        """Объём единичной гиперсферы в 4D: π²/2"""
        radii = np.array([1.0, 1.0, 1.0, 1.0])
        volume = ellipsoid_volume(radii)
        
        expected = np.pi**2 / 2
        np.testing.assert_allclose(volume, expected, rtol=1e-10)


class TestEllipsoidContains(unittest.TestCase):
    """Тесты для проверки принадлежности точек эллипсоиду."""
    
    def test_sphere_contains(self):
        """Проверка точек относительно единичной сферы"""
        A = np.eye(3)
        center = np.zeros(3)
        
        points = np.array([
            [0, 0, 0],      # Внутри (центр)
            [0.5, 0, 0],    # Внутри
            [1, 0, 0],      # На поверхности
            [2, 0, 0]       # Снаружи
        ])
        
        result = ellipsoid_contains(points, A, center)
        
        expected = np.array([True, True, True, False])
        np.testing.assert_array_equal(result, expected)
    
    def test_ellipsoid_contains(self):
        """Проверка для эллипсоида"""
        # Эллипсоид с полуосями 2, 1.5, 1
        radii = np.array([2, 1.5, 1])
        A = np.diag(1 / radii**2)
        center = np.zeros(3)
        
        points = np.array([
            [0, 0, 0],          # Центр - внутри
            [2, 0, 0],          # На границе по X
            [0, 1.5, 0],        # На границе по Y
            [0, 0, 1],          # На границе по Z
            [3, 0, 0],          # Снаружи
            [1, 0.5, 0.3]       # Внутри
        ])
        
        result = ellipsoid_contains(points, A, center)
        
        # Первые 4 точки внутри/на границе, 5-я снаружи, 6-я внутри
        self.assertTrue(result[0])
        self.assertTrue(result[1])
        self.assertTrue(result[2])
        self.assertTrue(result[3])
        self.assertFalse(result[4])
        self.assertTrue(result[5])


class TestFitHyperboloid(unittest.TestCase):
    """Тесты для подгонки гиперболоида."""
    
    def test_one_sheet_hyperboloid(self):
        """Однополостный гиперболоид: x²/4 + y²/4 - z² = 1"""
        # Генерируем точки на однополостном гиперболоиде
        n = 30
        u = np.linspace(0, 2*np.pi, n)
        v = np.linspace(-1, 1, n // 2)
        
        points = []
        for vv in v:
            for uu in u:
                x = 2 * np.cosh(vv) * np.cos(uu)
                y = 2 * np.cosh(vv) * np.sin(uu)
                z = 2 * np.sinh(vv)
                points.append([x, y, z])
        
        points = np.array(points)
        A, center, eigvals, eigvecs, htype = fit_hyperboloid(points)
        
        # Проверяем тип
        self.assertEqual(htype, "one-sheet")
        
        # Центр близок к нулю
        np.testing.assert_allclose(center, [0, 0, 0], atol=0.1)
        
        # Проверяем знаки собственных значений: 2 положительных, 1 отрицательное
        pos_count = np.sum(eigvals > 0)
        neg_count = np.sum(eigvals < 0)
        self.assertEqual(pos_count, 2)
        self.assertEqual(neg_count, 1)
    
    def test_two_sheet_hyperboloid(self):
        """Двуполостный гиперболоид: x² - y²/4 - z²/4 = 1"""
        # Генерируем точки на двуполостном гиперболоиде (только правая полость)
        n = 30
        u = np.linspace(0, 2*np.pi, n)
        v = np.linspace(1.2, 3, n // 2)  # v >= 1 для существования sqrt
        
        points = []
        for vv in v:
            for uu in u:
                x = vv
                y = 2 * np.sqrt(vv**2 - 1) * np.cos(uu)
                z = 2 * np.sqrt(vv**2 - 1) * np.sin(uu)
                points.append([x, y, z])
        
        points = np.array(points)
        A, center, eigvals, eigvecs, htype = fit_hyperboloid(points)
        
        # Проверяем тип
        self.assertEqual(htype, "two-sheet")
        
        # Проверяем знаки: 1 положительное, 2 отрицательных
        pos_count = np.sum(eigvals > 0)
        neg_count = np.sum(eigvals < 0)
        self.assertEqual(pos_count, 1)
        self.assertEqual(neg_count, 2)
    
    def test_ellipsoid_rejects(self):
        """Эллипсоид должен быть отклонён"""
        # Генерируем точки на сфере
        n = 30
        theta = np.linspace(0, 2*np.pi, n)
        phi = np.linspace(0, np.pi, n // 2)
        
        points = []
        for p in phi:
            for t in theta:
                x = 2 * np.sin(p) * np.cos(t)
                y = 2 * np.sin(p) * np.sin(t)
                z = 2 * np.cos(p)
                points.append([x, y, z])
        
        points = np.array(points)
        
        with self.assertRaises(ValueError) as ctx:
            fit_hyperboloid(points)
        
        self.assertIn("одного знака", str(ctx.exception))


class TestFitParaboloid(unittest.TestCase):
    """Тесты для подгонки параболоида."""
    
    def test_paraboloid_of_revolution(self):
        """Параболоид вращения: z = x² + y²"""
        # Генерируем точки
        x = np.linspace(-2, 2, 30)
        y = np.linspace(-2, 2, 30)
        X, Y = np.meshgrid(x, y)
        Z = X**2 + Y**2
        
        points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        A, b, c, vertex, eigvals, eigvecs = fit_paraboloid(points)
        
        # Проверяем матрицу A: должна быть близка к [[1, 0], [0, 1]]
        expected_A = np.eye(2)
        np.testing.assert_allclose(A, expected_A, rtol=0.01, atol=1e-10)
        
        # Вершина в начале координат
        np.testing.assert_allclose(vertex, [0, 0], atol=0.1)
        
        # Константа близка к нулю
        self.assertAlmostEqual(c, 0, delta=0.1)
        
        # Собственные значения положительны (выпуклый параболоид)
        self.assertTrue(np.all(eigvals > 0))
    
    def test_elliptic_paraboloid(self):
        """Эллиптический параболоид: z = 2x² + 3y²"""
        x = np.linspace(-2, 2, 25)
        y = np.linspace(-2, 2, 25)
        X, Y = np.meshgrid(x, y)
        Z = 2*X**2 + 3*Y**2
        
        points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        A, b, c, vertex, eigvals, eigvecs = fit_paraboloid(points)
        
        # Матрица должна быть диагональной с элементами [2, 3]
        np.testing.assert_allclose(A, np.diag([2, 3]), rtol=0.01, atol=1e-10)
        
        # Вершина в начале
        np.testing.assert_allclose(vertex, [0, 0], atol=0.1)
        
        # Оба собственных значения положительны
        self.assertTrue(np.all(eigvals > 0))
    
    def test_hyperbolic_paraboloid(self):
        """Гиперболический параболоид (седло): z = x² - y²"""
        x = np.linspace(-2, 2, 25)
        y = np.linspace(-2, 2, 25)
        X, Y = np.meshgrid(x, y)
        Z = X**2 - Y**2
        
        points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        A, b, c, vertex, eigvals, eigvecs = fit_paraboloid(points)
        
        # Матрица с разными знаками: [[1, 0], [0, -1]]
        expected_A = np.diag([1, -1])
        np.testing.assert_allclose(A, expected_A, rtol=0.01, atol=1e-10)
        
        # Седловая точка в начале
        np.testing.assert_allclose(vertex, [0, 0], atol=0.1)
        
        # Собственные значения разных знаков
        self.assertTrue(eigvals[0] * eigvals[1] < 0)
    
    def test_shifted_paraboloid(self):
        """Параболоид со смещённой вершиной: z = (x-1)² + 2(y-2)²"""
        x = np.linspace(-1, 3, 25)
        y = np.linspace(0, 4, 25)
        X, Y = np.meshgrid(x, y)
        Z = (X - 1)**2 + 2*(Y - 2)**2
        
        points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        A, b, c, vertex, eigvals, eigvecs = fit_paraboloid(points)
        
        # Вершина в (1, 2)
        np.testing.assert_allclose(vertex, [1, 2], atol=0.1)
        
        # Матрица коэффициентов
        np.testing.assert_allclose(A, np.diag([1, 2]), rtol=0.05, atol=1e-10)


if __name__ == '__main__':
    unittest.main()
