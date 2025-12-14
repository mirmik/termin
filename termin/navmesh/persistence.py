"""
Сохранение и загрузка NavMesh.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union
import numpy as np

from termin.navmesh.types import NavMesh, NavPolygon


NAVMESH_FILE_EXTENSION = ".navmesh"
NAVMESH_FORMAT_VERSION = "1.0"


class NavMeshPersistence:
    """
    Сохранение и загрузка NavMesh в файл .navmesh.

    Формат — JSON с массивами вершин и треугольников.
    """

    @staticmethod
    def save(navmesh: NavMesh, path: Union[str, Path]) -> None:
        """
        Сохранить NavMesh в файл.

        Args:
            navmesh: NavMesh для сохранения.
            path: Путь к файлу (.navmesh).
        """
        path = Path(path)

        data = {
            "version": NAVMESH_FORMAT_VERSION,
            "name": navmesh.name,
            "cell_size": navmesh.cell_size,
            "origin": navmesh.origin.tolist(),
            "polygons": [],
        }

        for polygon in navmesh.polygons:
            poly_data = {
                "vertices": polygon.vertices.tolist(),
                "triangles": polygon.triangles.tolist(),
                "normal": polygon.normal.tolist(),
                "voxel_coords": polygon.voxel_coords,
                "neighbors": polygon.neighbors,
            }
            data["polygons"].append(poly_data)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(path: Union[str, Path]) -> NavMesh:
        """
        Загрузить NavMesh из файла.

        Args:
            path: Путь к файлу (.navmesh).

        Returns:
            Загруженный NavMesh.

        Raises:
            ValueError: Если формат файла неверный.
            FileNotFoundError: Если файл не найден.
        """
        path = Path(path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        version = data.get("version", "")
        if not version.startswith("1."):
            raise ValueError(f"Unsupported navmesh format version: {version}")

        navmesh = NavMesh(
            cell_size=data.get("cell_size", 0.25),
            origin=np.array(data.get("origin", [0, 0, 0]), dtype=np.float32),
            name=data.get("name", ""),
        )

        for poly_data in data.get("polygons", []):
            polygon = NavPolygon(
                vertices=np.array(poly_data["vertices"], dtype=np.float32),
                triangles=np.array(poly_data["triangles"], dtype=np.int32),
                normal=np.array(poly_data["normal"], dtype=np.float32),
                voxel_coords=[tuple(c) for c in poly_data.get("voxel_coords", [])],
                neighbors=poly_data.get("neighbors", []),
            )
            navmesh.polygons.append(polygon)

        return navmesh

    @staticmethod
    def get_info(path: Union[str, Path]) -> dict:
        """
        Получить информацию о navmesh файле без полной загрузки.

        Args:
            path: Путь к файлу.

        Returns:
            Словарь с информацией: polygon_count, triangle_count, vertex_count.
        """
        path = Path(path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        polygons = data.get("polygons", [])
        polygon_count = len(polygons)
        triangle_count = sum(len(p.get("triangles", [])) for p in polygons)
        vertex_count = sum(len(p.get("vertices", [])) for p in polygons)

        return {
            "name": data.get("name", ""),
            "cell_size": data.get("cell_size", 0.25),
            "polygon_count": polygon_count,
            "triangle_count": triangle_count,
            "vertex_count": vertex_count,
        }
