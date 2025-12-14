"""
Сохранение и загрузка воксельных сеток.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from termin.voxels.grid import VoxelGrid


VOXEL_FILE_EXTENSION = ".voxels"
VOXEL_FORMAT_VERSION = "1.1"  # 1.1: added surface_normals


class VoxelPersistence:
    """
    Сохранение и загрузка VoxelGrid в файл .voxels.

    Формат — JSON с gzip+base64 данными чанков.
    """

    @staticmethod
    def save(grid: VoxelGrid, path: Union[str, Path]) -> None:
        """
        Сохранить воксельную сетку в файл.

        Args:
            grid: Сетка для сохранения.
            path: Путь к файлу (.voxels).
        """
        path = Path(path)

        data = {
            "version": VOXEL_FORMAT_VERSION,
            "name": grid.name,
            "cell_size": grid.cell_size,
            "chunks": {},
        }

        for (cx, cy, cz), chunk in grid.iter_chunks():
            if chunk.is_empty:
                continue
            key = f"{cx},{cy},{cz}"
            data["chunks"][key] = chunk.serialize()

        # Сохраняем нормали поверхностных вокселей
        if grid.surface_normals:
            normals_data = {}
            for (vx, vy, vz), normal in grid.surface_normals.items():
                key = f"{vx},{vy},{vz}"
                normals_data[key] = normal.tolist()
            data["surface_normals"] = normals_data

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(path: Union[str, Path]) -> VoxelGrid:
        """
        Загрузить воксельную сетку из файла.

        Args:
            path: Путь к файлу (.voxels).

        Returns:
            Загруженная VoxelGrid.

        Raises:
            ValueError: Если формат файла неверный.
            FileNotFoundError: Если файл не найден.
        """
        import numpy as np

        path = Path(path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        version = data.get("version", "")
        if not version.startswith("1."):
            raise ValueError(f"Unsupported voxel format version: {version}")

        name = data.get("name", "")
        cell_size = data.get("cell_size", 0.25)

        # Создаём сетку с origin в (0,0,0) — локальные координаты
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=cell_size, name=name)

        from termin.voxels.chunk import VoxelChunk

        for key, chunk_data in data.get("chunks", {}).items():
            parts = key.split(",")
            if len(parts) != 3:
                continue
            cx, cy, cz = int(parts[0]), int(parts[1]), int(parts[2])
            chunk = VoxelChunk.deserialize(chunk_data)
            if not chunk.is_empty:
                grid._chunks[(cx, cy, cz)] = chunk

        # Загружаем нормали поверхностных вокселей
        for key, normal_list in data.get("surface_normals", {}).items():
            parts = key.split(",")
            if len(parts) != 3:
                continue
            vx, vy, vz = int(parts[0]), int(parts[1]), int(parts[2])
            grid.set_surface_normal(vx, vy, vz, np.array(normal_list, dtype=np.float32))

        return grid

    @staticmethod
    def get_info(path: Union[str, Path]) -> dict:
        """
        Получить информацию о воксельном файле без полной загрузки.

        Args:
            path: Путь к файлу.

        Returns:
            Словарь с информацией: cell_size, chunk_count, voxel_count, bounds.
        """
        path = Path(path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("name", "")
        cell_size = data.get("cell_size", 0.25)
        chunks = data.get("chunks", {})

        chunk_count = len(chunks)
        voxel_count = sum(c.get("count", 0) for c in chunks.values())

        # Вычисляем bounds по ключам чанков
        bounds_min = None
        bounds_max = None

        from termin.voxels.chunk import CHUNK_SIZE

        for key in chunks.keys():
            parts = key.split(",")
            if len(parts) != 3:
                continue
            cx, cy, cz = int(parts[0]), int(parts[1]), int(parts[2])

            chunk_min = (cx * CHUNK_SIZE, cy * CHUNK_SIZE, cz * CHUNK_SIZE)
            chunk_max = ((cx + 1) * CHUNK_SIZE - 1, (cy + 1) * CHUNK_SIZE - 1, (cz + 1) * CHUNK_SIZE - 1)

            if bounds_min is None:
                bounds_min = list(chunk_min)
                bounds_max = list(chunk_max)
            else:
                for i in range(3):
                    bounds_min[i] = min(bounds_min[i], chunk_min[i])
                    bounds_max[i] = max(bounds_max[i], chunk_max[i])

        return {
            "name": name,
            "cell_size": cell_size,
            "chunk_count": chunk_count,
            "voxel_count": voxel_count,
            "bounds_min": bounds_min,
            "bounds_max": bounds_max,
        }
