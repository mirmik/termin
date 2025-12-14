"""
VoxelGrid — контейнер чанков с мировыми координатами.
"""

from __future__ import annotations

from typing import Iterator, Optional
import numpy as np

from termin.voxels.chunk import VoxelChunk, CHUNK_SIZE


class VoxelGrid:
    """
    Разреженная сетка вокселей на основе чанков.

    Attributes:
        origin: Мировые координаты угла сетки (минимум по X, Y, Z).
        cell_size: Размер одного вокселя в мировых единицах.
    """

    __slots__ = ("_origin", "_cell_size", "_chunks", "_name")

    def __init__(
        self,
        origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
        cell_size: float = 0.25,
        name: str = "",
    ) -> None:
        self._origin = np.array(origin, dtype=np.float32)
        self._cell_size = cell_size
        self._chunks: dict[tuple[int, int, int], VoxelChunk] = {}
        self._name = name

    @property
    def origin(self) -> np.ndarray:
        """Мировые координаты угла сетки."""
        return self._origin

    @origin.setter
    def origin(self, value: tuple[float, float, float]) -> None:
        self._origin = np.array(value, dtype=np.float32)

    @property
    def cell_size(self) -> float:
        """Размер вокселя в мировых единицах."""
        return self._cell_size

    @cell_size.setter
    def cell_size(self, value: float) -> None:
        self._cell_size = value

    @property
    def name(self) -> str:
        """Имя воксельной сетки."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    @property
    def chunk_count(self) -> int:
        """Количество аллоцированных чанков."""
        return len(self._chunks)

    @property
    def voxel_count(self) -> int:
        """Общее количество непустых вокселей."""
        return sum(c.non_empty_count for c in self._chunks.values())

    # ----------------------------------------------------------------
    # Координатные преобразования
    # ----------------------------------------------------------------

    def world_to_voxel(self, world_pos: np.ndarray) -> tuple[int, int, int]:
        """Преобразовать мировые координаты в индексы вокселя."""
        local = (world_pos - self._origin) / self._cell_size
        return int(np.floor(local[0])), int(np.floor(local[1])), int(np.floor(local[2]))

    def voxel_to_world(self, vx: int, vy: int, vz: int) -> np.ndarray:
        """Преобразовать индексы вокселя в мировые координаты (центр вокселя)."""
        return self._origin + (np.array([vx, vy, vz]) + 0.5) * self._cell_size

    def voxel_to_chunk(self, vx: int, vy: int, vz: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        """
        Разбить глобальные индексы вокселя на chunk key и локальные индексы.

        Python floor division и modulo корректно работают с отрицательными числами:
        -1 // 16 = -1, -1 % 16 = 15

        Returns:
            ((chunk_x, chunk_y, chunk_z), (local_x, local_y, local_z))
        """
        cx = vx // CHUNK_SIZE
        cy = vy // CHUNK_SIZE
        cz = vz // CHUNK_SIZE
        lx = vx % CHUNK_SIZE
        ly = vy % CHUNK_SIZE
        lz = vz % CHUNK_SIZE
        return (cx, cy, cz), (lx, ly, lz)

    # ----------------------------------------------------------------
    # Доступ к вокселям
    # ----------------------------------------------------------------

    def get(self, vx: int, vy: int, vz: int) -> int:
        """Получить тип вокселя по глобальным индексам."""
        chunk_key, (lx, ly, lz) = self.voxel_to_chunk(vx, vy, vz)
        chunk = self._chunks.get(chunk_key)
        if chunk is None:
            return 0
        return chunk.get(lx, ly, lz)

    def set(self, vx: int, vy: int, vz: int, value: int) -> None:
        """Установить тип вокселя по глобальным индексам."""
        chunk_key, (lx, ly, lz) = self.voxel_to_chunk(vx, vy, vz)

        if value == 0:
            # Удаляем воксель — чанк может стать пустым
            chunk = self._chunks.get(chunk_key)
            if chunk is not None:
                chunk.set(lx, ly, lz, 0)
                if chunk.is_empty:
                    del self._chunks[chunk_key]
        else:
            # Добавляем воксель — создаём чанк если нужно
            chunk = self._chunks.get(chunk_key)
            if chunk is None:
                chunk = VoxelChunk()
                self._chunks[chunk_key] = chunk
            chunk.set(lx, ly, lz, value)

    def get_at_world(self, world_pos: np.ndarray) -> int:
        """Получить тип вокселя по мировым координатам."""
        vx, vy, vz = self.world_to_voxel(world_pos)
        return self.get(vx, vy, vz)

    def set_at_world(self, world_pos: np.ndarray, value: int) -> None:
        """Установить тип вокселя по мировым координатам."""
        vx, vy, vz = self.world_to_voxel(world_pos)
        self.set(vx, vy, vz, value)

    def get_chunk(self, cx: int, cy: int, cz: int) -> Optional[VoxelChunk]:
        """Получить чанк по координатам чанка."""
        return self._chunks.get((cx, cy, cz))

    # ----------------------------------------------------------------
    # Итерация
    # ----------------------------------------------------------------

    def iter_chunks(self) -> Iterator[tuple[tuple[int, int, int], VoxelChunk]]:
        """Итератор по всем чанкам: (chunk_key, chunk)."""
        yield from self._chunks.items()

    def iter_non_empty(self) -> Iterator[tuple[int, int, int, int]]:
        """
        Итератор по всем непустым вокселям.

        Yields:
            (voxel_x, voxel_y, voxel_z, type) в глобальных координатах.
        """
        for (cx, cy, cz), chunk in self._chunks.items():
            base_x = cx * CHUNK_SIZE
            base_y = cy * CHUNK_SIZE
            base_z = cz * CHUNK_SIZE
            for lx, ly, lz, vtype in chunk.iter_non_empty():
                yield base_x + lx, base_y + ly, base_z + lz, vtype

    # ----------------------------------------------------------------
    # Операции
    # ----------------------------------------------------------------

    def clear(self) -> None:
        """Очистить всю сетку."""
        self._chunks.clear()

    def bounds(self) -> Optional[tuple[tuple[int, int, int], tuple[int, int, int]]]:
        """
        Получить bounding box в координатах вокселей.

        Returns:
            ((min_x, min_y, min_z), (max_x, max_y, max_z)) или None если пусто.
        """
        if not self._chunks:
            return None

        chunk_keys = list(self._chunks.keys())
        min_cx = min(k[0] for k in chunk_keys)
        min_cy = min(k[1] for k in chunk_keys)
        min_cz = min(k[2] for k in chunk_keys)
        max_cx = max(k[0] for k in chunk_keys)
        max_cy = max(k[1] for k in chunk_keys)
        max_cz = max(k[2] for k in chunk_keys)

        return (
            (min_cx * CHUNK_SIZE, min_cy * CHUNK_SIZE, min_cz * CHUNK_SIZE),
            ((max_cx + 1) * CHUNK_SIZE - 1, (max_cy + 1) * CHUNK_SIZE - 1, (max_cz + 1) * CHUNK_SIZE - 1),
        )

    def world_bounds(self) -> Optional[tuple[np.ndarray, np.ndarray]]:
        """
        Получить bounding box в мировых координатах.

        Returns:
            (min_corner, max_corner) или None если пусто.
        """
        voxel_bounds = self.bounds()
        if voxel_bounds is None:
            return None

        (min_v, max_v) = voxel_bounds
        min_world = self._origin + np.array(min_v) * self._cell_size
        max_world = self._origin + (np.array(max_v) + 1) * self._cell_size
        return min_world, max_world

    # ----------------------------------------------------------------
    # Fill interior
    # ----------------------------------------------------------------

    def fill_interior(self, fill_value: int = 1) -> int:
        """
        Заполняет внутреннее пространство замкнутого меша.

        Алгоритм: flood fill снаружи, всё недостижимое — внутри.

        Args:
            fill_value: Тип вокселя для заполнения.

        Returns:
            Количество заполненных вокселей.
        """
        from collections import deque

        voxel_bounds = self.bounds()
        if voxel_bounds is None:
            return 0

        (min_x, min_y, min_z), (max_x, max_y, max_z) = voxel_bounds

        # Расширяем bounds на 1 чтобы гарантировать что угол снаружи
        min_x -= 1
        min_y -= 1
        min_z -= 1
        max_x += 1
        max_y += 1
        max_z += 1

        # BFS от угла — помечаем всё достижимое снаружи
        outside: set[tuple[int, int, int]] = set()
        queue: deque[tuple[int, int, int]] = deque()
        start = (min_x, min_y, min_z)
        queue.append(start)
        outside.add(start)

        neighbors = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]

        while queue:
            x, y, z = queue.popleft()

            for dx, dy, dz in neighbors:
                nx, ny, nz = x + dx, y + dy, z + dz

                # Проверяем bounds
                if nx < min_x or nx > max_x:
                    continue
                if ny < min_y or ny > max_y:
                    continue
                if nz < min_z or nz > max_z:
                    continue

                if (nx, ny, nz) in outside:
                    continue

                # Если solid — не проходим
                if self.get(nx, ny, nz) != 0:
                    continue

                outside.add((nx, ny, nz))
                queue.append((nx, ny, nz))

        # Заполняем всё что не outside и не solid
        filled_count = 0
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                for z in range(min_z, max_z + 1):
                    if (x, y, z) not in outside and self.get(x, y, z) == 0:
                        self.set(x, y, z, fill_value)
                        filled_count += 1

        return filled_count

    # ----------------------------------------------------------------
    # Сериализация
    # ----------------------------------------------------------------

    def serialize(self) -> dict:
        """Сериализовать сетку в dict."""
        return {
            "origin": self._origin.tolist(),
            "cell_size": self._cell_size,
            "chunks": {
                f"{cx},{cy},{cz}": chunk.serialize()
                for (cx, cy, cz), chunk in self._chunks.items()
            },
        }

    @classmethod
    def deserialize(cls, data: dict) -> VoxelGrid:
        """Десериализовать сетку из dict."""
        grid = cls(
            origin=tuple(data["origin"]),
            cell_size=data["cell_size"],
        )

        for key_str, chunk_data in data.get("chunks", {}).items():
            cx, cy, cz = map(int, key_str.split(","))
            chunk = VoxelChunk.deserialize(chunk_data)
            if not chunk.is_empty:
                grid._chunks[(cx, cy, cz)] = chunk

        return grid
