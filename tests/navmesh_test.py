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

    def _make_2x2_region(self, grid: VoxelGrid, x: int, y: int, z: int, normal: np.ndarray):
        """Создать 2x2 площадку вокселей."""
        for dx in range(2):
            for dy in range(2):
                grid.set(x + dx, y + dy, z, 2)
                grid.add_surface_normal(x + dx, y + dy, z, normal)

    def test_2x2_region(self):
        """Площадка 2x2 = один регион с контуром из 4 точек."""
        grid = VoxelGrid(cell_size=1.0)
        self._make_2x2_region(grid, 0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        polygon = navmesh.polygons[0]
        self.assertEqual(len(polygon.voxel_coords), 4)
        self.assertIsNotNone(polygon.outer_contour)
        self.assertEqual(len(polygon.outer_contour), 4)

    def test_two_regions_different_normals(self):
        """Две площадки с разными нормалями = два региона."""
        grid = VoxelGrid(cell_size=1.0)
        # Площадка 1: нормаль вверх (+Z)
        self._make_2x2_region(grid, 0, 0, 0, np.array([0, 0, 1]))
        # Площадка 2: нормаль вверх, но отдельно (не связана)
        self._make_2x2_region(grid, 10, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        # Два несвязных региона = два полигона
        self.assertEqual(navmesh.polygon_count(), 2)

    def test_normal_threshold(self):
        """Порог нормали: похожие нормали объединяются."""
        grid = VoxelGrid(cell_size=1.0)

        # Нормали отличаются на ~10° — должны объединиться при threshold=0.9
        n1 = np.array([0, 0, 1], dtype=np.float32)
        n2 = np.array([0.17, 0, 0.985], dtype=np.float32)  # ~10°
        n2 /= np.linalg.norm(n2)

        # Проверяем что dot > 0.9
        self.assertGreater(np.dot(n1, n2), 0.9)

        # Два соседних 2x2 блока с похожими нормалями
        for x in range(2):
            for y in range(2):
                grid.set(x, y, 0, 2)
                grid.add_surface_normal(x, y, 0, n1)
        for x in range(2, 4):
            for y in range(2):
                grid.set(x, y, 0, 2)
                grid.add_surface_normal(x, y, 0, n2)

        builder = PolygonBuilder(NavMeshConfig(normal_threshold=0.9))
        navmesh = builder.build(grid)

        # Должны объединиться в один регион
        self.assertEqual(navmesh.polygon_count(), 1)

    def test_disconnected_same_normal(self):
        """Несвязные площадки с одинаковой нормалью = разные регионы."""
        grid = VoxelGrid(cell_size=1.0)
        self._make_2x2_region(grid, 0, 0, 0, np.array([0, 0, 1]))
        self._make_2x2_region(grid, 10, 10, 10, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 2)


class VoxelContourTest(unittest.TestCase):
    """Тесты для извлечения контуров из вокселей."""

    def test_2x2_contour_vertices(self):
        """Контур 2x2 площадки = 4 вершины (центры граничных вокселей)."""
        grid = VoxelGrid(cell_size=1.0)
        for x in range(2):
            for y in range(2):
                grid.set(x, y, 0, 2)
                grid.add_surface_normal(x, y, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        polygon = navmesh.polygons[0]
        # 4 граничных вокселя = 4 вершины контура
        self.assertEqual(len(polygon.vertices), 4)
        self.assertEqual(len(polygon.outer_contour), 4)

    def test_3x3_contour_vertices(self):
        """Контур 3x3 площадки = 8 вершин (центральный воксель не граничный)."""
        grid = VoxelGrid(cell_size=1.0)
        for x in range(3):
            for y in range(3):
                grid.set(x, y, 0, 2)
                grid.add_surface_normal(x, y, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        polygon = navmesh.polygons[0]
        # 8 граничных вокселей (все кроме центра) = 8 вершин контура
        self.assertEqual(len(polygon.vertices), 8)
        self.assertEqual(len(polygon.outer_contour), 8)

    def test_l_shape_contour(self):
        """L-образная форма: 3 вокселя = 3 вершины контура."""
        grid = VoxelGrid(cell_size=1.0)
        # L-форма:
        # ■
        # ■ ■
        grid.set(0, 0, 0, 2)
        grid.set(0, 1, 0, 2)
        grid.set(1, 0, 0, 2)
        for x, y in [(0, 0), (0, 1), (1, 0)]:
            grid.add_surface_normal(x, y, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        polygon = navmesh.polygons[0]
        # Все 3 вокселя граничные = 3 вершины контура
        self.assertEqual(len(polygon.vertices), 3)

    def test_contour_no_mesh(self):
        """Контур без меша: пустой массив треугольников."""
        grid = VoxelGrid(cell_size=1.0)
        for x in range(2):
            for y in range(2):
                grid.set(x, y, 0, 2)
                grid.add_surface_normal(x, y, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        polygon = navmesh.polygons[0]
        # Меш пустой
        self.assertEqual(len(polygon.triangles), 0)


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


class AreConnected26Test(unittest.TestCase):
    """Тесты для are_connected_26."""

    def test_empty_list(self):
        """Пустой список — тривиально связан."""
        from termin.navmesh.region_growing import are_connected_26
        self.assertTrue(are_connected_26([]))

    def test_single_voxel(self):
        """Один воксель — тривиально связан."""
        from termin.navmesh.region_growing import are_connected_26
        self.assertTrue(are_connected_26([(0, 0, 0)]))

    def test_two_adjacent_face(self):
        """Два соседних вокселя по грани — связаны."""
        from termin.navmesh.region_growing import are_connected_26
        voxels = [(0, 0, 0), (1, 0, 0)]
        self.assertTrue(are_connected_26(voxels))

    def test_two_adjacent_edge(self):
        """Два соседних вокселя по ребру — связаны (26-connectivity)."""
        from termin.navmesh.region_growing import are_connected_26
        voxels = [(0, 0, 0), (1, 1, 0)]
        self.assertTrue(are_connected_26(voxels))

    def test_two_adjacent_corner(self):
        """Два соседних вокселя по углу — связаны (26-connectivity)."""
        from termin.navmesh.region_growing import are_connected_26
        voxels = [(0, 0, 0), (1, 1, 1)]
        self.assertTrue(are_connected_26(voxels))

    def test_two_disconnected(self):
        """Два несвязных вокселя — НЕ связаны."""
        from termin.navmesh.region_growing import are_connected_26
        voxels = [(0, 0, 0), (3, 0, 0)]
        self.assertFalse(are_connected_26(voxels))

    def test_three_in_line(self):
        """Три вокселя в линию — связаны."""
        from termin.navmesh.region_growing import are_connected_26
        voxels = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
        self.assertTrue(are_connected_26(voxels))

    def test_three_one_disconnected(self):
        """Три вокселя, один отдельно — НЕ связаны."""
        from termin.navmesh.region_growing import are_connected_26
        voxels = [(0, 0, 0), (1, 0, 0), (5, 0, 0)]
        self.assertFalse(are_connected_26(voxels))

    def test_l_shape(self):
        """L-образная форма — связаны."""
        from termin.navmesh.region_growing import are_connected_26
        voxels = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        self.assertTrue(are_connected_26(voxels))

    def test_diagonal_line(self):
        """Диагональная линия — связаны (26-connectivity)."""
        from termin.navmesh.region_growing import are_connected_26
        voxels = [(0, 0, 0), (1, 1, 0), (2, 2, 0)]
        self.assertTrue(are_connected_26(voxels))

    def test_two_clusters_not_connected(self):
        """Два кластера — НЕ связаны."""
        from termin.navmesh.region_growing import are_connected_26
        voxels = [(0, 0, 0), (1, 0, 0), (10, 0, 0), (11, 0, 0)]
        self.assertFalse(are_connected_26(voxels))


if __name__ == "__main__":
    unittest.main()
