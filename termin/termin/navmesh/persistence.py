"""
Сохранение и загрузка NavMesh.

Supports both JSON (.navmesh) and binary formats.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Union
import numpy as np

from termin.navmesh.types import NavMesh, NavPolygon


NAVMESH_FILE_EXTENSION = ".navmesh"
NAVMESH_FORMAT_VERSION = "1.0"

# Binary format magic and version
NAVMESH_BINARY_MAGIC = b"TNAV"
NAVMESH_BINARY_VERSION = 1


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
            # Контуры (опционально) — конвертируем numpy.int32 в int
            if polygon.outer_contour is not None:
                poly_data["outer_contour"] = [int(i) for i in polygon.outer_contour]
            if polygon.holes:
                poly_data["holes"] = [[int(i) for i in hole] for hole in polygon.holes]
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
            content = f.read()

        return NavMeshPersistence.load_from_content(content)

    @staticmethod
    def load_from_content(content: str) -> NavMesh:
        """
        Загрузить NavMesh из JSON содержимого.

        Args:
            content: JSON строка с данными NavMesh.

        Returns:
            Загруженный NavMesh.

        Raises:
            ValueError: Если формат файла неверный.
        """
        data = json.loads(content)

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
                outer_contour=poly_data.get("outer_contour"),
                holes=poly_data.get("holes", []),
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

    # === Binary serialization ===

    @staticmethod
    def to_bytes(navmesh: NavMesh) -> bytes:
        """
        Serialize NavMesh to binary format.

        Binary format:
            - 4 bytes: magic "TNAV"
            - 4 bytes: version (uint32)
            - 4 bytes: name length (uint32)
            - N bytes: name (utf-8)
            - 4 bytes: cell_size (float32)
            - 12 bytes: origin (3 x float32)
            - 4 bytes: polygon count (uint32)
            - For each polygon:
                - 4 bytes: vertex count (uint32)
                - N*12 bytes: vertices (N x 3 x float32)
                - 4 bytes: triangle count (uint32)
                - M*12 bytes: triangles (M x 3 x uint32)
                - 12 bytes: normal (3 x float32)
                - 4 bytes: neighbor count (uint32)
                - K*4 bytes: neighbors (K x int32)

        Args:
            navmesh: NavMesh to serialize.

        Returns:
            Binary data.
        """
        parts: list[bytes] = []

        # Header
        parts.append(NAVMESH_BINARY_MAGIC)
        parts.append(struct.pack("<I", NAVMESH_BINARY_VERSION))

        # Name
        name_bytes = navmesh.name.encode("utf-8")
        parts.append(struct.pack("<I", len(name_bytes)))
        parts.append(name_bytes)

        # Cell size and origin
        parts.append(struct.pack("<f", navmesh.cell_size))
        parts.append(navmesh.origin.astype(np.float32).tobytes())

        # Polygons
        parts.append(struct.pack("<I", len(navmesh.polygons)))

        for polygon in navmesh.polygons:
            # Vertices
            vertices = polygon.vertices.astype(np.float32)
            parts.append(struct.pack("<I", len(vertices)))
            parts.append(vertices.tobytes())

            # Triangles
            triangles = polygon.triangles.astype(np.uint32)
            parts.append(struct.pack("<I", len(triangles)))
            parts.append(triangles.tobytes())

            # Normal
            parts.append(polygon.normal.astype(np.float32).tobytes())

            # Neighbors
            parts.append(struct.pack("<I", len(polygon.neighbors)))
            if polygon.neighbors:
                parts.append(struct.pack(f"<{len(polygon.neighbors)}i", *polygon.neighbors))

        return b"".join(parts)

    @staticmethod
    def from_bytes(data: bytes) -> NavMesh:
        """
        Deserialize NavMesh from binary format.

        Args:
            data: Binary data.

        Returns:
            Deserialized NavMesh.

        Raises:
            ValueError: If data format is invalid.
        """
        offset = 0

        # Magic
        magic = data[offset:offset + 4]
        offset += 4
        if magic != NAVMESH_BINARY_MAGIC:
            raise ValueError(f"Invalid navmesh binary magic: {magic!r}")

        # Version
        version, = struct.unpack_from("<I", data, offset)
        offset += 4
        if version != NAVMESH_BINARY_VERSION:
            raise ValueError(f"Unsupported navmesh binary version: {version}")

        # Name
        name_len, = struct.unpack_from("<I", data, offset)
        offset += 4
        name = data[offset:offset + name_len].decode("utf-8")
        offset += name_len

        # Cell size and origin
        cell_size, = struct.unpack_from("<f", data, offset)
        offset += 4
        origin = np.frombuffer(data, dtype=np.float32, count=3, offset=offset).copy()
        offset += 12

        # Polygons
        polygon_count, = struct.unpack_from("<I", data, offset)
        offset += 4

        polygons: list[NavPolygon] = []

        for _ in range(polygon_count):
            # Vertices
            vertex_count, = struct.unpack_from("<I", data, offset)
            offset += 4
            vertices = np.frombuffer(data, dtype=np.float32, count=vertex_count * 3, offset=offset).copy()
            vertices = vertices.reshape((vertex_count, 3))
            offset += vertex_count * 12

            # Triangles
            triangle_count, = struct.unpack_from("<I", data, offset)
            offset += 4
            triangles = np.frombuffer(data, dtype=np.uint32, count=triangle_count * 3, offset=offset).copy()
            triangles = triangles.reshape((triangle_count, 3)).astype(np.int32)
            offset += triangle_count * 12

            # Normal
            normal = np.frombuffer(data, dtype=np.float32, count=3, offset=offset).copy()
            offset += 12

            # Neighbors
            neighbor_count, = struct.unpack_from("<I", data, offset)
            offset += 4
            if neighbor_count > 0:
                neighbors = list(struct.unpack_from(f"<{neighbor_count}i", data, offset))
                offset += neighbor_count * 4
            else:
                neighbors = []

            polygon = NavPolygon(
                vertices=vertices,
                triangles=triangles,
                normal=normal,
                neighbors=neighbors,
            )
            polygons.append(polygon)

        return NavMesh(
            polygons=polygons,
            cell_size=cell_size,
            origin=origin,
            name=name,
        )
