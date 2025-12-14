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
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)

    def test_two_voxels_same_normal(self):
        """Два соседних вокселя с одинаковой нормалью = один регион."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set(1, 0, 0, 2)
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        grid.add_surface_normal(1, 0, 0, np.array([0, 0, 1]))

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
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        grid.add_surface_normal(1, 0, 0, np.array([1, 0, 0]))

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

        grid.add_surface_normal(0, 0, 0, n1)
        grid.add_surface_normal(1, 0, 0, n2)

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
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        grid.add_surface_normal(5, 5, 5, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 2)


class ContourBuildingTest(unittest.TestCase):
    """Тесты для построения контура (лицевых граней)."""

    def test_single_voxel_contour(self):
        """Контур одного вокселя — 4 вершины (лицевая грань)."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        # Одна лицевая грань = 4 вершины
        self.assertEqual(len(navmesh.polygons[0].vertices), 4)

    def test_two_adjacent_voxels_shared_vertices(self):
        """Два смежных вокселя — общие вершины на границе лицевых граней."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set(1, 0, 0, 2)
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        grid.add_surface_normal(1, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        # Две лицевые грани рядом = 6 уникальных вершин (2 общих)
        self.assertEqual(len(navmesh.polygons[0].vertices), 6)


class TriangulationTest(unittest.TestCase):
    """Тесты для триангуляции."""

    def test_triangulation_produces_triangles(self):
        """Триангуляция создаёт треугольники."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        self.assertGreater(len(navmesh.polygons[0].triangles), 0)

        # Все индексы треугольников валидны
        polygon = navmesh.polygons[0]
        max_idx = len(polygon.vertices) - 1
        for tri in polygon.triangles:
            self.assertTrue(all(0 <= idx <= max_idx for idx in tri))


class VoxelFaceMeshTest(unittest.TestCase):
    """Тесты для построения меша из граней вокселей."""

    def test_single_voxel_face_count(self):
        """Один воксель: 1 лицевая грань = 1 квад = 2 треугольника."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        polygon = navmesh.polygons[0]

        # 1 квад = 2 треугольника
        self.assertEqual(len(polygon.triangles), 2)
        # 4 уникальных вершины (углы лицевой грани)
        self.assertEqual(len(polygon.vertices), 4)

    def test_single_voxel_normals(self):
        """Нормали лицевых треугольников совпадают с нормалью региона."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)
        polygon = navmesh.polygons[0]

        region_normal = polygon.normal

        # Хотя бы 2 треугольника (лицевая грань) должны иметь нормаль по направлению региона
        aligned_count = 0
        for tri in polygon.triangles:
            v0, v1, v2 = polygon.vertices[tri]
            edge1 = v1 - v0
            edge2 = v2 - v0
            tri_normal = np.cross(edge1, edge2)
            norm_len = np.linalg.norm(tri_normal)
            if norm_len > 1e-6:
                tri_normal = tri_normal / norm_len
                dot = np.dot(tri_normal, region_normal)
                if dot > 0.9:  # Почти параллельны
                    aligned_count += 1

        # Лицевая грань = 2 треугольника
        self.assertGreaterEqual(aligned_count, 2, f"Expected at least 2 triangles aligned with region normal, got {aligned_count}")

    def test_two_adjacent_voxels_horizontal(self):
        """Два смежных вокселя по горизонтали: 2 лицевых грани с общими вершинами."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.set(1, 0, 0, 2)
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        grid.add_surface_normal(1, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        polygon = navmesh.polygons[0]

        # 2 лицевые грани = 4 треугольника
        self.assertEqual(len(polygon.triangles), 4)
        # 6 уникальных вершин (общие 2 вершины на границе)
        self.assertEqual(len(polygon.vertices), 6)

    def test_step_voxels(self):
        """Ступенька: два вокселя на разных уровнях = 2 лицевые + 1 боковая."""
        grid = VoxelGrid(cell_size=1.0)
        # Воксель на уровне 0
        grid.set(0, 0, 0, 2)
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))
        # Воксель на уровне 1, смещённый по X
        grid.set(1, 0, 1, 2)
        grid.add_surface_normal(1, 0, 1, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        self.assertEqual(navmesh.polygon_count(), 1)
        polygon = navmesh.polygons[0]

        # 2 лицевые грани + 1 боковая = 6 треугольников
        self.assertEqual(len(polygon.triangles), 6)

    def test_step_with_side_face(self):
        """Ступенька с боковой гранью: сосед ярусом ниже по X."""
        grid = VoxelGrid(cell_size=1.0)
        # Воксель на уровне z=1 (верхний)
        grid.set(0, 0, 1, 2)
        grid.add_surface_normal(0, 0, 1, np.array([0, 0, 1]))
        # Воксель на уровне z=0 (нижний), смещён по X
        grid.set(1, 0, 0, 2)
        grid.add_surface_normal(1, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        polygon = navmesh.polygons[0]

        # 2 лицевые грани + 1 боковая = 3 квада = 6 треугольников
        self.assertEqual(len(polygon.triangles), 6)

        # Проверяем что нет дублирующихся рёбер (max 2)
        edge_count = {}
        for tri in polygon.triangles:
            for i in range(3):
                v0, v1 = tri[i], tri[(i + 1) % 3]
                edge = (min(v0, v1), max(v0, v1))
                edge_count[edge] = edge_count.get(edge, 0) + 1

        for edge, count in edge_count.items():
            self.assertIn(count, [1, 2], f"Edge {edge} has {count} triangles")

    def test_staircase(self):
        """Лестница из 3 ступенек: каждая выше предыдущей."""
        grid = VoxelGrid(cell_size=1.0)
        # Три ступеньки: (0,0,0), (1,0,1), (2,0,2)
        for i in range(3):
            grid.set(i, 0, i, 2)
            grid.add_surface_normal(i, 0, i, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        polygon = navmesh.polygons[0]

        # 3 лицевые грани + 2 боковые (между ступеньками) = 5 квадов = 10 треугольников
        self.assertEqual(len(polygon.triangles), 10)

        # Проверяем что нет дублирующихся рёбер
        edge_count = {}
        for tri in polygon.triangles:
            for i in range(3):
                v0, v1 = tri[i], tri[(i + 1) % 3]
                edge = (min(v0, v1), max(v0, v1))
                edge_count[edge] = edge_count.get(edge, 0) + 1

        for edge, count in edge_count.items():
            self.assertIn(count, [1, 2], f"Edge {edge} has {count} triangles")

    def test_no_side_faces_same_level(self):
        """Соседи на том же уровне не генерируют боковые грани."""
        grid = VoxelGrid(cell_size=1.0)
        # Три вокселя в ряд на одном уровне
        for i in range(3):
            grid.set(i, 0, 0, 2)
            grid.add_surface_normal(i, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)

        polygon = navmesh.polygons[0]

        # Только 3 лицевые грани = 6 треугольников (без боковых)
        self.assertEqual(len(polygon.triangles), 6)

    def test_staircase_mesh_integrity(self):
        """Лестница: проверка целостности меша (нет дыр)."""
        grid = VoxelGrid(cell_size=1.0)
        # Три ступеньки
        for i in range(3):
            grid.set(i, 0, i, 2)
            grid.add_surface_normal(i, 0, i, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)
        polygon = navmesh.polygons[0]

        # Проверяем целостность: каждое ребро 1 или 2 раза
        edge_count = {}
        for tri_idx, tri in enumerate(polygon.triangles):
            for i in range(3):
                v0, v1 = int(tri[i]), int(tri[(i + 1) % 3])
                edge = (min(v0, v1), max(v0, v1))
                if edge not in edge_count:
                    edge_count[edge] = []
                edge_count[edge].append(tri_idx)

        # Выводим проблемные рёбра
        bad_edges = [(e, tris) for e, tris in edge_count.items() if len(tris) > 2]
        if bad_edges:
            print(f"\nEdges with >2 triangles:")
            for edge, tris in bad_edges:
                v0_pos = polygon.vertices[edge[0]]
                v1_pos = polygon.vertices[edge[1]]
                print(f"  Edge {edge}: {v0_pos} -> {v1_pos}")
                for t in tris:
                    tri = polygon.triangles[t]
                    print(f"    Triangle {t}: {tri}")

        # Проверяем boundary рёбра образуют замкнутый контур
        boundary_edges = [e for e, tris in edge_count.items() if len(tris) == 1]
        if boundary_edges:
            from collections import defaultdict
            adj = defaultdict(list)
            for v0, v1 in boundary_edges:
                adj[v0].append(v1)
                adj[v1].append(v0)

            # Каждая вершина должна иметь чётную степень
            odd_vertices = [(v, len(neighbors)) for v, neighbors in adj.items() if len(neighbors) % 2 != 0]
            if odd_vertices:
                print(f"\nVertices with odd degree (holes):")
                for v, deg in odd_vertices:
                    print(f"  Vertex {v}: {polygon.vertices[v]}, degree={deg}")

            self.assertEqual(len(odd_vertices), 0, f"Found {len(odd_vertices)} vertices with odd degree")

        for edge, tris in edge_count.items():
            self.assertIn(len(tris), [1, 2], f"Edge {edge} has {len(tris)} triangles")

    def test_no_holes_in_mesh(self):
        """Меш не должен иметь дыр — все boundary рёбра образуют замкнутый контур."""
        grid = VoxelGrid(cell_size=1.0)
        grid.set(0, 0, 0, 2)
        grid.add_surface_normal(0, 0, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid)
        polygon = navmesh.polygons[0]

        # Собираем boundary рёбра (которые принадлежат только 1 треугольнику)
        edge_count = {}
        for tri in polygon.triangles:
            for i in range(3):
                v0, v1 = tri[i], tri[(i + 1) % 3]
                edge = (min(v0, v1), max(v0, v1))
                edge_count[edge] = edge_count.get(edge, 0) + 1

        boundary_edges = {e for e, c in edge_count.items() if c == 1}

        # Строим граф смежности boundary вершин
        from collections import defaultdict
        adj = defaultdict(set)
        for v0, v1 in boundary_edges:
            adj[v0].add(v1)
            adj[v1].add(v0)

        # Каждая boundary вершина должна иметь чётное число соседей (для замкнутого контура)
        for v, neighbors in adj.items():
            self.assertEqual(len(neighbors) % 2, 0, f"Vertex {v} has odd degree {len(neighbors)} — hole detected")

    def test_contour_extraction(self):
        """Извлечение контура из меша граней."""
        grid = VoxelGrid(cell_size=1.0)
        # 2x2 площадка вокселей
        for x in range(2):
            for y in range(2):
                grid.set(x, y, 0, 2)
                grid.add_surface_normal(x, y, 0, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid, extract_contours=True)

        self.assertEqual(navmesh.polygon_count(), 1)
        polygon = navmesh.polygons[0]

        # Должен быть внешний контур
        self.assertIsNotNone(polygon.outer_contour)
        self.assertGreater(len(polygon.outer_contour), 0)

        # Внешний контур 2x2 площадки = 8 вершин (периметр квадрата 2x2)
        self.assertEqual(len(polygon.outer_contour), 8)

        # Без дыр
        self.assertEqual(len(polygon.holes), 0)

    def test_contour_extraction_staircase(self):
        """Извлечение контура из лестницы."""
        grid = VoxelGrid(cell_size=1.0)
        # Лестница из 3 ступенек
        for i in range(3):
            grid.set(i, 0, i, 2)
            grid.add_surface_normal(i, 0, i, np.array([0, 0, 1]))

        builder = PolygonBuilder()
        navmesh = builder.build(grid, extract_contours=True)

        self.assertEqual(navmesh.polygon_count(), 1)
        polygon = navmesh.polygons[0]

        # Должен быть внешний контур
        self.assertIsNotNone(polygon.outer_contour)
        self.assertGreater(len(polygon.outer_contour), 0)


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
