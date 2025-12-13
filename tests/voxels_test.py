"""
Тесты для системы вокселей.
"""

import unittest
import numpy as np

from termin.voxels.chunk import VoxelChunk, CHUNK_SIZE
from termin.voxels.grid import VoxelGrid
from termin.voxels.intersection import triangle_aabb_intersect, triangle_aabb
from termin.voxels.voxelizer import MeshVoxelizer, VOXEL_SURFACE


class VoxelChunkTest(unittest.TestCase):
    """Тесты для VoxelChunk."""

    def test_empty_chunk(self):
        """Новый чанк должен быть пустым."""
        chunk = VoxelChunk()
        self.assertTrue(chunk.is_empty)
        self.assertEqual(chunk.non_empty_count, 0)

    def test_set_get(self):
        """Установка и чтение вокселя."""
        chunk = VoxelChunk()
        chunk.set(0, 0, 0, 1)

        self.assertEqual(chunk.get(0, 0, 0), 1)
        self.assertEqual(chunk.non_empty_count, 1)
        self.assertFalse(chunk.is_empty)

    def test_set_multiple(self):
        """Установка нескольких вокселей."""
        chunk = VoxelChunk()
        chunk.set(0, 0, 0, 1)
        chunk.set(1, 2, 3, 2)
        chunk.set(15, 15, 15, 3)

        self.assertEqual(chunk.get(0, 0, 0), 1)
        self.assertEqual(chunk.get(1, 2, 3), 2)
        self.assertEqual(chunk.get(15, 15, 15), 3)
        self.assertEqual(chunk.non_empty_count, 3)

    def test_overwrite_voxel(self):
        """Перезапись вокселя не должна менять счётчик."""
        chunk = VoxelChunk()
        chunk.set(0, 0, 0, 1)
        chunk.set(0, 0, 0, 2)

        self.assertEqual(chunk.get(0, 0, 0), 2)
        self.assertEqual(chunk.non_empty_count, 1)

    def test_clear_voxel(self):
        """Очистка вокселя (установка в 0)."""
        chunk = VoxelChunk()
        chunk.set(0, 0, 0, 1)
        chunk.set(0, 0, 0, 0)

        self.assertEqual(chunk.get(0, 0, 0), 0)
        self.assertEqual(chunk.non_empty_count, 0)
        self.assertTrue(chunk.is_empty)

    def test_fill(self):
        """Заполнение всего чанка."""
        chunk = VoxelChunk()
        chunk.fill(1)

        self.assertEqual(chunk.non_empty_count, CHUNK_SIZE ** 3)
        self.assertEqual(chunk.get(0, 0, 0), 1)
        self.assertEqual(chunk.get(15, 15, 15), 1)

    def test_clear(self):
        """Очистка всего чанка."""
        chunk = VoxelChunk()
        chunk.fill(1)
        chunk.clear()

        self.assertTrue(chunk.is_empty)
        self.assertEqual(chunk.non_empty_count, 0)

    def test_iter_non_empty(self):
        """Итерация по непустым вокселям."""
        chunk = VoxelChunk()
        chunk.set(1, 2, 3, 1)
        chunk.set(4, 5, 6, 2)

        voxels = list(chunk.iter_non_empty())
        self.assertEqual(len(voxels), 2)

        # Проверяем что оба вокселя есть
        coords = {(v[0], v[1], v[2]) for v in voxels}
        self.assertIn((1, 2, 3), coords)
        self.assertIn((4, 5, 6), coords)

    def test_serialization_roundtrip(self):
        """Сериализация и десериализация."""
        chunk = VoxelChunk()
        chunk.set(0, 0, 0, 1)
        chunk.set(5, 10, 15, 2)
        chunk.set(15, 15, 15, 255)

        data = chunk.serialize()
        restored = VoxelChunk.deserialize(data)

        self.assertEqual(restored.get(0, 0, 0), 1)
        self.assertEqual(restored.get(5, 10, 15), 2)
        self.assertEqual(restored.get(15, 15, 15), 255)
        self.assertEqual(restored.non_empty_count, 3)


class VoxelGridTest(unittest.TestCase):
    """Тесты для VoxelGrid."""

    def test_empty_grid(self):
        """Новая сетка должна быть пустой."""
        grid = VoxelGrid()
        self.assertEqual(grid.voxel_count, 0)
        self.assertEqual(grid.chunk_count, 0)

    def test_set_get(self):
        """Установка и чтение вокселя."""
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=1.0)
        grid.set(0, 0, 0, 1)

        self.assertEqual(grid.get(0, 0, 0), 1)
        self.assertEqual(grid.voxel_count, 1)
        self.assertEqual(grid.chunk_count, 1)

    def test_negative_coords(self):
        """Отрицательные координаты вокселей."""
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=1.0)
        grid.set(-1, -1, -1, 1)
        grid.set(-17, -17, -17, 2)  # -17 в чанке (-2,-2,-2), -1 в чанке (-1,-1,-1)

        self.assertEqual(grid.get(-1, -1, -1), 1)
        self.assertEqual(grid.get(-17, -17, -17), 2)
        self.assertEqual(grid.chunk_count, 2)  # Разные чанки

    def test_world_to_voxel(self):
        """Преобразование мировых координат в индексы."""
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=0.5)

        # (0.1, 0.1, 0.1) -> воксель (0, 0, 0)
        vx, vy, vz = grid.world_to_voxel(np.array([0.1, 0.1, 0.1]))
        self.assertEqual((vx, vy, vz), (0, 0, 0))

        # (0.6, 0.6, 0.6) -> воксель (1, 1, 1)
        vx, vy, vz = grid.world_to_voxel(np.array([0.6, 0.6, 0.6]))
        self.assertEqual((vx, vy, vz), (1, 1, 1))

        # (-0.1, -0.1, -0.1) -> воксель (-1, -1, -1)
        vx, vy, vz = grid.world_to_voxel(np.array([-0.1, -0.1, -0.1]))
        self.assertEqual((vx, vy, vz), (-1, -1, -1))

    def test_world_to_voxel_with_origin(self):
        """Преобразование с ненулевым origin."""
        grid = VoxelGrid(origin=(10, 20, 30), cell_size=0.5)

        # (10.1, 20.1, 30.1) -> воксель (0, 0, 0)
        vx, vy, vz = grid.world_to_voxel(np.array([10.1, 20.1, 30.1]))
        self.assertEqual((vx, vy, vz), (0, 0, 0))

    def test_voxel_to_world(self):
        """Преобразование индексов в мировые координаты."""
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=0.5)

        # Воксель (0, 0, 0) -> центр (0.25, 0.25, 0.25)
        world = grid.voxel_to_world(0, 0, 0)
        np.testing.assert_array_almost_equal(world, [0.25, 0.25, 0.25])

        # Воксель (1, 1, 1) -> центр (0.75, 0.75, 0.75)
        world = grid.voxel_to_world(1, 1, 1)
        np.testing.assert_array_almost_equal(world, [0.75, 0.75, 0.75])

    def test_voxel_to_chunk_positive(self):
        """Разбиение на chunk и local для положительных координат."""
        grid = VoxelGrid()

        chunk_key, local = grid.voxel_to_chunk(0, 0, 0)
        self.assertEqual(chunk_key, (0, 0, 0))
        self.assertEqual(local, (0, 0, 0))

        chunk_key, local = grid.voxel_to_chunk(15, 15, 15)
        self.assertEqual(chunk_key, (0, 0, 0))
        self.assertEqual(local, (15, 15, 15))

        chunk_key, local = grid.voxel_to_chunk(16, 16, 16)
        self.assertEqual(chunk_key, (1, 1, 1))
        self.assertEqual(local, (0, 0, 0))

    def test_voxel_to_chunk_negative(self):
        """Разбиение на chunk и local для отрицательных координат."""
        grid = VoxelGrid()

        chunk_key, local = grid.voxel_to_chunk(-1, -1, -1)
        self.assertEqual(chunk_key, (-1, -1, -1))
        self.assertEqual(local, (15, 15, 15))

        chunk_key, local = grid.voxel_to_chunk(-16, -16, -16)
        self.assertEqual(chunk_key, (-1, -1, -1))
        self.assertEqual(local, (0, 0, 0))

        chunk_key, local = grid.voxel_to_chunk(-17, -17, -17)
        self.assertEqual(chunk_key, (-2, -2, -2))
        self.assertEqual(local, (15, 15, 15))

    def test_set_at_world(self):
        """Установка вокселя по мировым координатам."""
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=0.5)
        grid.set_at_world(np.array([0.3, 0.3, 0.3]), 1)

        self.assertEqual(grid.get(0, 0, 0), 1)

    def test_auto_chunk_creation(self):
        """Автоматическое создание чанков."""
        grid = VoxelGrid()
        grid.set(0, 0, 0, 1)
        grid.set(100, 100, 100, 1)

        self.assertEqual(grid.chunk_count, 2)

    def test_auto_chunk_deletion(self):
        """Автоматическое удаление пустых чанков."""
        grid = VoxelGrid()
        grid.set(0, 0, 0, 1)
        self.assertEqual(grid.chunk_count, 1)

        grid.set(0, 0, 0, 0)
        self.assertEqual(grid.chunk_count, 0)

    def test_bounds(self):
        """Вычисление bounds."""
        grid = VoxelGrid()
        grid.set(0, 0, 0, 1)
        grid.set(20, 30, 40, 1)

        bounds = grid.bounds()
        self.assertIsNotNone(bounds)
        min_v, max_v = bounds

        # Минимум должен быть (0, 0, 0)
        self.assertEqual(min_v, (0, 0, 0))
        # Максимум в пределах чанков
        self.assertGreaterEqual(max_v[0], 20)
        self.assertGreaterEqual(max_v[1], 30)
        self.assertGreaterEqual(max_v[2], 40)

    def test_iter_non_empty(self):
        """Итерация по непустым вокселям."""
        grid = VoxelGrid()
        grid.set(0, 0, 0, 1)
        grid.set(1, 2, 3, 2)
        grid.set(-5, -5, -5, 3)

        voxels = list(grid.iter_non_empty())
        self.assertEqual(len(voxels), 3)

        coords = {(v[0], v[1], v[2]) for v in voxels}
        self.assertIn((0, 0, 0), coords)
        self.assertIn((1, 2, 3), coords)
        self.assertIn((-5, -5, -5), coords)

    def test_clear(self):
        """Очистка сетки."""
        grid = VoxelGrid()
        grid.set(0, 0, 0, 1)
        grid.set(100, 100, 100, 1)
        grid.clear()

        self.assertEqual(grid.voxel_count, 0)
        self.assertEqual(grid.chunk_count, 0)

    def test_serialization_roundtrip(self):
        """Сериализация и десериализация."""
        grid = VoxelGrid(origin=(10.0, 20.0, 30.0), cell_size=0.25)
        grid.set(0, 0, 0, 1)
        grid.set(100, 100, 100, 2)
        grid.set(-50, -50, -50, 3)

        data = grid.serialize()
        restored = VoxelGrid.deserialize(data)

        self.assertEqual(restored.cell_size, 0.25)
        np.testing.assert_array_almost_equal(restored.origin, [10.0, 20.0, 30.0])
        self.assertEqual(restored.get(0, 0, 0), 1)
        self.assertEqual(restored.get(100, 100, 100), 2)
        self.assertEqual(restored.get(-50, -50, -50), 3)
        self.assertEqual(restored.voxel_count, 3)


class TriangleAABBIntersectTest(unittest.TestCase):
    """Тесты для triangle_aabb_intersect."""

    def test_triangle_inside_box(self):
        """Треугольник полностью внутри куба."""
        v0 = np.array([0.0, 0.0, 0.0])
        v1 = np.array([0.1, 0.0, 0.0])
        v2 = np.array([0.0, 0.1, 0.0])
        center = np.array([0.0, 0.0, 0.0])
        half_size = np.array([1.0, 1.0, 1.0])

        self.assertTrue(triangle_aabb_intersect(v0, v1, v2, center, half_size))

    def test_triangle_outside_box(self):
        """Треугольник далеко от куба."""
        v0 = np.array([10.0, 10.0, 10.0])
        v1 = np.array([11.0, 10.0, 10.0])
        v2 = np.array([10.0, 11.0, 10.0])
        center = np.array([0.0, 0.0, 0.0])
        half_size = np.array([1.0, 1.0, 1.0])

        self.assertFalse(triangle_aabb_intersect(v0, v1, v2, center, half_size))

    def test_triangle_crosses_box(self):
        """Треугольник пересекает куб."""
        v0 = np.array([-2.0, 0.0, 0.0])
        v1 = np.array([2.0, 0.0, 0.0])
        v2 = np.array([0.0, 2.0, 0.0])
        center = np.array([0.0, 0.0, 0.0])
        half_size = np.array([1.0, 1.0, 1.0])

        self.assertTrue(triangle_aabb_intersect(v0, v1, v2, center, half_size))

    def test_triangle_touches_box_corner(self):
        """Треугольник касается угла куба."""
        v0 = np.array([1.0, 1.0, 1.0])
        v1 = np.array([2.0, 1.0, 1.0])
        v2 = np.array([1.0, 2.0, 1.0])
        center = np.array([0.0, 0.0, 0.0])
        half_size = np.array([1.0, 1.0, 1.0])

        self.assertTrue(triangle_aabb_intersect(v0, v1, v2, center, half_size))

    def test_triangle_parallel_to_face_outside(self):
        """Треугольник параллелен грани, но снаружи."""
        v0 = np.array([-0.5, -0.5, 2.0])
        v1 = np.array([0.5, -0.5, 2.0])
        v2 = np.array([0.0, 0.5, 2.0])
        center = np.array([0.0, 0.0, 0.0])
        half_size = np.array([1.0, 1.0, 1.0])

        self.assertFalse(triangle_aabb_intersect(v0, v1, v2, center, half_size))

    def test_triangle_parallel_to_face_inside(self):
        """Треугольник параллелен грани и пересекает её."""
        v0 = np.array([-0.5, -0.5, 0.5])
        v1 = np.array([0.5, -0.5, 0.5])
        v2 = np.array([0.0, 0.5, 0.5])
        center = np.array([0.0, 0.0, 0.0])
        half_size = np.array([1.0, 1.0, 1.0])

        self.assertTrue(triangle_aabb_intersect(v0, v1, v2, center, half_size))

    def test_large_triangle_around_small_box(self):
        """Большой треугольник вокруг маленького куба."""
        v0 = np.array([-10.0, -10.0, 0.0])
        v1 = np.array([10.0, -10.0, 0.0])
        v2 = np.array([0.0, 10.0, 0.0])
        center = np.array([0.0, 0.0, 0.0])
        half_size = np.array([0.1, 0.1, 0.1])

        self.assertTrue(triangle_aabb_intersect(v0, v1, v2, center, half_size))


class TriangleAABBTest(unittest.TestCase):
    """Тесты для triangle_aabb."""

    def test_simple_triangle(self):
        """AABB простого треугольника."""
        v0 = np.array([0.0, 0.0, 0.0])
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])

        min_c, max_c = triangle_aabb(v0, v1, v2)

        np.testing.assert_array_equal(min_c, [0.0, 0.0, 0.0])
        np.testing.assert_array_equal(max_c, [1.0, 1.0, 0.0])

    def test_negative_coords(self):
        """AABB треугольника с отрицательными координатами."""
        v0 = np.array([-1.0, -2.0, -3.0])
        v1 = np.array([1.0, 2.0, 3.0])
        v2 = np.array([0.0, 0.0, 0.0])

        min_c, max_c = triangle_aabb(v0, v1, v2)

        np.testing.assert_array_equal(min_c, [-1.0, -2.0, -3.0])
        np.testing.assert_array_equal(max_c, [1.0, 2.0, 3.0])


class MeshVoxelizerTest(unittest.TestCase):
    """Тесты для MeshVoxelizer."""

    def test_voxelize_single_triangle(self):
        """Вокселизация одного треугольника."""
        from termin.mesh.mesh import Mesh3

        # Треугольник в плоскости XY
        vertices = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, 1.0, 0.0],
        ], dtype=np.float32)
        triangles = np.array([[0, 1, 2]], dtype=np.int32)
        mesh = Mesh3(vertices=vertices, triangles=triangles)

        grid = VoxelGrid(origin=(-1, -1, -1), cell_size=0.25)
        voxelizer = MeshVoxelizer(grid)
        count = voxelizer.voxelize_mesh(mesh)

        self.assertGreater(count, 0)
        self.assertGreater(grid.voxel_count, 0)

    def test_voxelize_cube(self):
        """Вокселизация куба."""
        from termin.mesh.mesh import CubeMesh

        mesh = CubeMesh(size=1.0)  # Куб от -0.5 до 0.5

        grid = VoxelGrid(origin=(-1, -1, -1), cell_size=0.25)
        voxelizer = MeshVoxelizer(grid)
        count = voxelizer.voxelize_mesh(mesh)

        self.assertGreater(count, 0)

        # Проверяем что воксели есть на поверхности куба
        # Центр грани Z=0.5 должен быть заполнен
        has_top_face = False
        for vx, vy, vz, vtype in grid.iter_non_empty():
            world = grid.voxel_to_world(vx, vy, vz)
            if abs(world[2] - 0.5) < 0.2:  # Близко к верхней грани
                has_top_face = True
                break

        self.assertTrue(has_top_face, "Should have voxels on top face")

    def test_voxelize_with_transform(self):
        """Вокселизация с трансформацией."""
        from termin.mesh.mesh import Mesh3

        # Треугольник в origin
        vertices = np.array([
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ], dtype=np.float32)
        triangles = np.array([[0, 1, 2]], dtype=np.int32)
        mesh = Mesh3(vertices=vertices, triangles=triangles)

        # Трансформация: сдвиг на (10, 10, 10)
        transform = np.eye(4, dtype=np.float32)
        transform[:3, 3] = [10, 10, 10]

        grid = VoxelGrid(origin=(9, 9, 9), cell_size=0.25)
        voxelizer = MeshVoxelizer(grid)
        count = voxelizer.voxelize_mesh(mesh, transform_matrix=transform)

        self.assertGreater(count, 0)

        # Проверяем что воксели около (10, 10, 10)
        has_voxel_near_target = False
        for vx, vy, vz, vtype in grid.iter_non_empty():
            world = grid.voxel_to_world(vx, vy, vz)
            if world[0] > 9 and world[1] > 9 and world[2] > 9:
                has_voxel_near_target = True
                break

        self.assertTrue(has_voxel_near_target)

    def test_empty_mesh(self):
        """Пустой меш не должен создавать вокселей."""
        from termin.mesh.mesh import Mesh3

        # Mesh3 требует массивы, создаём пустые
        vertices = np.array([], dtype=np.float32).reshape(0, 3)
        triangles = np.array([], dtype=np.int32).reshape(0, 3)
        mesh = Mesh3(vertices=vertices, triangles=triangles)

        grid = VoxelGrid()
        voxelizer = MeshVoxelizer(grid)
        count = voxelizer.voxelize_mesh(mesh)

        self.assertEqual(count, 0)
        self.assertEqual(grid.voxel_count, 0)


class VoxelPersistenceTest(unittest.TestCase):
    """Тесты для VoxelPersistence."""

    def test_save_load_roundtrip(self):
        """Сохранение и загрузка файла."""
        import tempfile
        import os
        from termin.voxels.persistence import VoxelPersistence

        grid = VoxelGrid(origin=(0, 0, 0), cell_size=0.5)
        grid.set(0, 0, 0, 1)
        grid.set(10, 20, 30, 2)
        grid.set(-5, -5, -5, 3)

        with tempfile.NamedTemporaryFile(suffix=".voxels", delete=False) as f:
            temp_path = f.name

        try:
            VoxelPersistence.save(grid, temp_path)
            loaded = VoxelPersistence.load(temp_path)

            self.assertEqual(loaded.cell_size, 0.5)
            self.assertEqual(loaded.get(0, 0, 0), 1)
            self.assertEqual(loaded.get(10, 20, 30), 2)
            self.assertEqual(loaded.get(-5, -5, -5), 3)
            self.assertEqual(loaded.voxel_count, 3)
        finally:
            os.unlink(temp_path)

    def test_get_info(self):
        """Получение информации о файле."""
        import tempfile
        import os
        from termin.voxels.persistence import VoxelPersistence

        grid = VoxelGrid(origin=(0, 0, 0), cell_size=0.25)
        grid.set(0, 0, 0, 1)
        grid.set(100, 100, 100, 1)

        with tempfile.NamedTemporaryFile(suffix=".voxels", delete=False) as f:
            temp_path = f.name

        try:
            VoxelPersistence.save(grid, temp_path)
            info = VoxelPersistence.get_info(temp_path)

            self.assertEqual(info["cell_size"], 0.25)
            self.assertEqual(info["voxel_count"], 2)
            self.assertGreaterEqual(info["chunk_count"], 1)
            self.assertIsNotNone(info["bounds_min"])
            self.assertIsNotNone(info["bounds_max"])
        finally:
            os.unlink(temp_path)

    def test_load_preserves_origin_zero(self):
        """Загруженная сетка имеет origin в (0,0,0)."""
        import tempfile
        import os
        from termin.voxels.persistence import VoxelPersistence

        # Создаём сетку с ненулевым origin
        grid = VoxelGrid(origin=(100, 200, 300), cell_size=0.5)
        grid.set(0, 0, 0, 1)

        with tempfile.NamedTemporaryFile(suffix=".voxels", delete=False) as f:
            temp_path = f.name

        try:
            VoxelPersistence.save(grid, temp_path)
            loaded = VoxelPersistence.load(temp_path)

            # Origin сбрасывается в (0,0,0) — локальные координаты
            np.testing.assert_array_equal(loaded.origin, [0, 0, 0])
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()
