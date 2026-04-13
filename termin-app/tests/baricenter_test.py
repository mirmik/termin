import unittest
import numpy as np
from termin.geomalgo.baricenter import baricoords_of_point_simplex


class TestBaricentricCoordinates(unittest.TestCase):
    """Тесты для функции baricoords_of_point_simplex"""
    
    def test_triangle_center(self):
        """Центр треугольника имеет координаты (1/3, 1/3, 1/3)"""
        simplex = np.array([[0.0, 0.0],
                            [1.0, 0.0],
                            [0.0, 1.0]])
        point = np.array([1.0/3, 1.0/3])
        coords = baricoords_of_point_simplex(point, simplex)
        
        expected = np.array([1.0/3, 1.0/3, 1.0/3])
        np.testing.assert_allclose(coords, expected, rtol=1e-10)
        self.assertAlmostEqual(np.sum(coords), 1.0)
    
    def test_triangle_vertex(self):
        """Вершина треугольника имеет координату 1 в соответствующей позиции"""
        simplex = np.array([[0.0, 0.0],
                            [1.0, 0.0],
                            [0.0, 1.0]])
        
        # Первая вершина
        point = np.array([0.0, 0.0])
        coords = baricoords_of_point_simplex(point, simplex)
        expected = np.array([1.0, 0.0, 0.0])
        np.testing.assert_allclose(coords, expected, atol=1e-10)
        
        # Вторая вершина
        point = np.array([1.0, 0.0])
        coords = baricoords_of_point_simplex(point, simplex)
        expected = np.array([0.0, 1.0, 0.0])
        np.testing.assert_allclose(coords, expected, atol=1e-10)
        
        # Третья вершина
        point = np.array([0.0, 1.0])
        coords = baricoords_of_point_simplex(point, simplex)
        expected = np.array([0.0, 0.0, 1.0])
        np.testing.assert_allclose(coords, expected, atol=1e-10)
    
    def test_triangle_edge_midpoint(self):
        """Середина ребра имеет координаты (0.5, 0.5, 0) для соответствующих вершин"""
        simplex = np.array([[0.0, 0.0],
                            [1.0, 0.0],
                            [0.0, 1.0]])
        
        # Середина между V0 и V1
        point = np.array([0.5, 0.0])
        coords = baricoords_of_point_simplex(point, simplex)
        expected = np.array([0.5, 0.5, 0.0])
        np.testing.assert_allclose(coords, expected, atol=1e-10)
    
    def test_segment_1d(self):
        """Отрезок в 1D пространстве"""
        simplex = np.array([[0.0],
                            [1.0]])
        point = np.array([0.3])
        coords = baricoords_of_point_simplex(point, simplex)
        
        expected = np.array([0.7, 0.3])
        np.testing.assert_allclose(coords, expected, atol=1e-10)
        self.assertAlmostEqual(np.sum(coords), 1.0)
        
        # Проверка реконструкции
        reconstructed = coords @ simplex
        np.testing.assert_allclose(reconstructed, point, atol=1e-10)
    
    def test_tetrahedron_center(self):
        """Центр тетраэдра имеет координаты (1/4, 1/4, 1/4, 1/4)"""
        simplex = np.array([[0.0, 0.0, 0.0],
                            [1.0, 0.0, 0.0],
                            [0.0, 1.0, 0.0],
                            [0.0, 0.0, 1.0]])
        point = np.array([0.25, 0.25, 0.25])
        coords = baricoords_of_point_simplex(point, simplex)
        
        expected = np.array([0.25, 0.25, 0.25, 0.25])
        np.testing.assert_allclose(coords, expected, atol=1e-10)
        self.assertAlmostEqual(np.sum(coords), 1.0)
    
    def test_point_outside_simplex(self):
        """Точка вне симплекса имеет отрицательные координаты"""
        simplex = np.array([[0.0, 0.0],
                            [1.0, 0.0],
                            [0.0, 1.0]])
        point = np.array([2.0, 2.0])
        coords = baricoords_of_point_simplex(point, simplex)
        
        # Сумма всё равно должна быть 1
        self.assertAlmostEqual(np.sum(coords), 1.0)
        
        # Некоторые координаты должны быть отрицательными
        self.assertTrue(np.any(coords < 0))
        
        # Но точка должна корректно реконструироваться
        reconstructed = coords @ simplex
        np.testing.assert_allclose(reconstructed, point, atol=1e-10)
    
    def test_reconstruction(self):
        """Проверка что точка корректно реконструируется из барицентрических координат"""
        simplex = np.array([[1.0, 2.0],
                            [3.0, 1.0],
                            [2.0, 4.0]])
        point = np.array([2.0, 2.5])
        
        coords = baricoords_of_point_simplex(point, simplex)
        reconstructed = coords @ simplex
        
        np.testing.assert_allclose(reconstructed, point, atol=1e-10)
        self.assertAlmostEqual(np.sum(coords), 1.0)
    
    def test_arbitrary_triangle(self):
        """Произвольный треугольник с нестандартными координатами"""
        simplex = np.array([[1.0, 1.0],
                            [4.0, 2.0],
                            [2.0, 5.0]])
        point = np.array([2.5, 2.5])
        
        coords = baricoords_of_point_simplex(point, simplex)
        
        # Проверяем основные свойства
        self.assertAlmostEqual(np.sum(coords), 1.0)
        
        # Реконструкция должна давать исходную точку
        reconstructed = coords @ simplex
        np.testing.assert_allclose(reconstructed, point, atol=1e-10)
    
    def test_invalid_simplex_too_few_vertices(self):
        """Слишком мало вершин для данной размерности"""
        # 2 вершины в 2D пространстве (нужно 3 для треугольника)
        simplex = np.array([[0.0, 0.0],
                            [1.0, 0.0]])
        point = np.array([0.5, 0.0])
        
        with self.assertRaises(ValueError) as context:
            baricoords_of_point_simplex(point, simplex)
        
        self.assertIn("expected 3 vertices", str(context.exception))
    
    def test_invalid_simplex_too_many_vertices(self):
        """Слишком много вершин для данной размерности"""
        # 4 вершины в 2D пространстве (должно быть 3)
        simplex = np.array([[0.0, 0.0],
                            [1.0, 0.0],
                            [0.0, 1.0],
                            [0.5, 0.5]])
        point = np.array([0.3, 0.3])
        
        with self.assertRaises(ValueError) as context:
            baricoords_of_point_simplex(point, simplex)
        
        self.assertIn("expected 3 vertices", str(context.exception))


if __name__ == '__main__':
    unittest.main()
