"""
Тесты для NavMesh.
"""

import os
import tempfile
import unittest
import numpy as np

from termin.voxels.grid import VoxelGrid
from termin.navmesh.types import NavMeshConfig, NavPolygon, NavMesh
from termin.navmesh.polygon_builder import PolygonBuilder
from termin.navmesh.persistence import NavMeshPersistence


class NavMeshTypesTest(unittest.TestCase):
    """Тесты для базовых типов NavMesh."""

    def test_config_defaults(self):
        """Конфигурация по умолчанию."""
        config = NavMeshConfig()
        self.assertAlmostEqual(config.normal_threshold, 0.9)
        self.assertEqual(config.min_region_voxels, 1)

    def test_navmesh_empty(self):
        """Пустой NavMesh."""
        mesh = NavMesh()
        self.assertEqual(mesh.polygon_count(), 0)
        self.assertEqual(mesh.triangle_count(), 0)
        self.assertEqual(mesh.vertex_count(), 0)


class RegionGrowingTest(unittest.TestCase):
    """Тесты для Region Growing алгоритма."""

    def test_single_voxel_region(self):
        """Один воксель = один регион."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)  # VOXEL_SURFACE
        grid.set_surface_normal(0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)

    def test_two_voxels_same_normal(self):
        """Два соседних вокселя с одинаковой нормалью = один регион."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set(1, 0, 0, 2)
        grid.set_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        grid.set_surface_normal(1, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        self.assertEqual(len(navmesh.polygons[0].voxel_coords), 2)

    def test_two_voxels_different_normals(self):
        """Два вокселя с разными нормалями = два региона."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set(1, 0, 0, 2)
        # Нормали перпендикулярны — точно разные регионы
        grid.set_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        grid.set_surface_normal(1, 0, 0, np.array([1, 0, 0]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 2)

    def test_normal_threshold(self):
        """Порог нормали: похожие нормали объединяются."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set(1, 0, 0, 2)

        # Нормали отличаются на ~10° — должны объединиться при threshold=0.9
        n1 = np.array([0, 0, 1], dtype=np.float32)
        n2 = np.array([0.17, 0, 0.985], dtype=np.float32)  # ~10°
        n2 /= np.linalg.norm(n2)

        grid.set_surface_normal(0, 0, 0, n1)
        grid.set_surface_normal(1, 0, 0, n2)

        # Проверяем что dot > 0.9
        self.assertGreater(np.dot(n1, n2), 0.9)

        builder = PolygonBuilder(NavMeshConfig(normal_threshold=0.9))
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)

    def test_disconnected_same_normal(self):
        """Несвязные воксели с одинаковой нормалью = разные регионы."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set(5, 5, 5, 2)  # Далеко
        grid.set_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        grid.set_surface_normal(5, 5, 5, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 2)


class ContourBuildingTest(unittest.TestCase):
    """Тесты для построения контура."""

    def test_single_voxel_contour(self):
        """Контур одного вокселя — 8 вершин (куб без внутренних)."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set_surface_normal(0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        # Один куб = 8 уникальных вершин
        self.assertEqual(len(navmesh.polygons[0].vertices), 8)

    def test_two_adjacent_voxels_shared_vertices(self):
        """Два смежных вокселя — общие вершины на границе."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set(1, 0, 0, 2)
        grid.set_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        grid.set_surface_normal(1, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        # Два куба рядом = 12 уникальных вершин (а не 16)
        self.assertEqual(len(navmesh.polygons[0].vertices), 12)


class TriangulationTest(unittest.TestCase):
    """Тесты для триангуляции."""

    def test_convex_hull_triangle(self):
        """Выпуклая оболочка 3 точек = 3 точки."""
        builder = PolygonBuilder()

        points = np.array([
            [0, 0],
            [1, 0],
            [0.5, 1],
        ])

        hull = builder._convex_hull_2d(points)
        self.assertEqual(len(hull), 3)

    def test_convex_hull_square(self):
        """Выпуклая оболочка квадрата = 4 точки."""
        builder = PolygonBuilder()

        points = np.array([
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 1],
        ])

        hull = builder._convex_hull_2d(points)
        self.assertEqual(len(hull), 4)

    def test_triangulation_produces_triangles(self):
        """Триангуляция создаёт треугольники."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set_surface_normal(0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        self.assertGreater(len(navmesh.polygons[0].triangles), 0)

        # Все индексы треугольников валидны
        polygon = navmesh.polygons[0]
        max_idx = len(polygon.vertices) - 1
        for tri in polygon.triangles:
            self.assertTrue(all(0 <= idx <= max_idx for idx in tri))


class EmptyGridTest(unittest.TestCase):
    """Тесты для пустой сетки."""

    def test_empty_grid(self):
        """Пустая сетка = пустой NavMesh."""
        grid = VoxelGrid(cell_size=1.0)
        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 0)

    def test_voxels_without_normals(self):
        """Воксели без нормалей игнорируются."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)  # Есть воксель, но нет нормали

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 0)


class PersistenceTest(unittest.TestCase):
    """Тесты для сохранения/загрузки NavMesh."""

    def test_save_load_empty(self):
        """Сохранение и загрузка пустого NavMesh."""
        navmesh = NavMesh(cell_size=0.5)

        with tempfile.NamedTemporaryFile(suffix=".navmesh", delete=False) as f:
            path = f.name

        try:
            NavMeshPersistence.save(navmesh, path)
            loaded = NavMeshPersistence.load(path)

            self.assertEqual(loaded.polygon_count(), 0)
            self.assertAlmostEqual(loaded.cell_size, 0.5)
        finally:
            os.unlink(path)

    def test_save_load_with_polygon(self):
        """Сохранение и загрузка NavMesh с полигоном."""
        navmesh = NavMesh(cell_size=0.25)
        polygon = NavPolygon(
            vertices=np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=np.float32),
            triangles=np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int32),
            normal=np.array([0, 0, 1], dtype=np.float32),
            voxel_coords=[(0, 0, 0), (1, 0, 0)],
        )
        navmesh.polygons.append(polygon)

        with tempfile.NamedTemporaryFile(suffix=".navmesh", delete=False) as f:
            path = f.name

        try:
            NavMeshPersistence.save(navmesh, path)
            loaded = NavMeshPersistence.load(path)

            self.assertEqual(loaded.polygon_count(), 1)
            self.assertEqual(len(loaded.polygons[0].vertices), 4)
            self.assertEqual(len(loaded.polygons[0].triangles), 2)
            np.testing.assert_array_almost_equal(loaded.polygons[0].normal, [0, 0, 1])
        finally:
            os.unlink(path)

    def test_get_info(self):
        """Получение информации о файле без полной загрузки."""
        navmesh = NavMesh(cell_size=0.25)
        for _ in range(3):
            polygon = NavPolygon(
                vertices=np.array([[0, 0, 0], [1, 0, 0], [0.5, 1, 0]], dtype=np.float32),
                triangles=np.array([[0, 1, 2]], dtype=np.int32),
                normal=np.array([0, 0, 1], dtype=np.float32),
            )
            navmesh.polygons.append(polygon)

        with tempfile.NamedTemporaryFile(suffix=".navmesh", delete=False) as f:
            path = f.name

        try:
            NavMeshPersistence.save(navmesh, path)
            info = NavMeshPersistence.get_info(path)

            self.assertEqual(info["polygon_count"], 3)
            self.assertEqual(info["triangle_count"], 3)
            self.assertEqual(info["vertex_count"], 9)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
