"""
VoxelDisplayComponent — компонент для отображения .voxels файла.

Реализует протокол Drawable и рендерит воксели напрямую.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Set

import numpy as np

from termin.visualization.core.component import Component
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import MeshDrawable
from termin.mesh.mesh import Mesh3
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.material import MaterialPhase
    from termin.visualization.render.render_context import RenderContext
    from termin.voxels.grid import VoxelGrid


# Вершины единичного куба (центрирован в origin)
_CUBE_VERTICES = np.array([
    # Front face
    [-0.5, -0.5,  0.5],
    [ 0.5, -0.5,  0.5],
    [ 0.5,  0.5,  0.5],
    [-0.5,  0.5,  0.5],
    # Back face
    [-0.5, -0.5, -0.5],
    [-0.5,  0.5, -0.5],
    [ 0.5,  0.5, -0.5],
    [ 0.5, -0.5, -0.5],
    # Top face
    [-0.5,  0.5, -0.5],
    [-0.5,  0.5,  0.5],
    [ 0.5,  0.5,  0.5],
    [ 0.5,  0.5, -0.5],
    # Bottom face
    [-0.5, -0.5, -0.5],
    [ 0.5, -0.5, -0.5],
    [ 0.5, -0.5,  0.5],
    [-0.5, -0.5,  0.5],
    # Right face
    [ 0.5, -0.5, -0.5],
    [ 0.5,  0.5, -0.5],
    [ 0.5,  0.5,  0.5],
    [ 0.5, -0.5,  0.5],
    # Left face
    [-0.5, -0.5, -0.5],
    [-0.5, -0.5,  0.5],
    [-0.5,  0.5,  0.5],
    [-0.5,  0.5, -0.5],
], dtype=np.float32)

_CUBE_TRIANGLES = np.array([
    [0, 1, 2], [0, 2, 3],       # front
    [4, 5, 6], [4, 6, 7],       # back
    [8, 9, 10], [8, 10, 11],    # top
    [12, 13, 14], [12, 14, 15], # bottom
    [16, 17, 18], [16, 18, 19], # right
    [20, 21, 22], [20, 22, 23], # left
], dtype=np.int32)

_CUBE_NORMALS = np.array([
    # Front
    [0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1],
    # Back
    [0, 0, -1], [0, 0, -1], [0, 0, -1], [0, 0, -1],
    # Top
    [0, 1, 0], [0, 1, 0], [0, 1, 0], [0, 1, 0],
    # Bottom
    [0, -1, 0], [0, -1, 0], [0, -1, 0], [0, -1, 0],
    # Right
    [1, 0, 0], [1, 0, 0], [1, 0, 0], [1, 0, 0],
    # Left
    [-1, 0, 0], [-1, 0, 0], [-1, 0, 0], [-1, 0, 0],
], dtype=np.float32)

VERTS_PER_CUBE = 24
TRIS_PER_CUBE = 12
CUBE_SCALE = 0.85  # Размер кубика относительно ячейки
MAX_VOXELS = 100_000


def _get_grid_name(comp: "VoxelDisplayComponent") -> str:
    """Получить имя загруженной сетки."""
    if comp._grid is not None:
        return comp._grid.name or "(unnamed)"
    return "(not loaded)"


class VoxelDisplayComponent(Component):
    """
    Компонент для отображения воксельной сетки из .voxels файла.

    Реализует протокол Drawable — рендерит воксели напрямую без MeshRenderer.
    """

    inspect_fields = {
        "grid_name": InspectField(
            label="Grid Name",
            kind="string",
            getter=_get_grid_name,
            non_serializable=True,
        ),
        "voxel_file": InspectField(
            path="voxel_file",
            label="Voxel File",
            kind="string",
        ),
    }

    serializable_fields = ["voxel_file"]

    def __init__(self, voxel_file: str = "") -> None:
        super().__init__()
        self._voxel_file = voxel_file
        self._grid: Optional["VoxelGrid"] = None
        self._mesh_drawable: Optional[MeshDrawable] = None
        self._material = Material(
            color=(0.2, 0.6, 1.0, 0.7),
            phase_mark="editor",
        )
        self._needs_reload = True

    @property
    def voxel_file(self) -> str:
        """Путь к .voxels файлу."""
        return self._voxel_file

    @voxel_file.setter
    def voxel_file(self, value: str) -> None:
        if self._voxel_file != value:
            self._voxel_file = value
            self._needs_reload = True

    @property
    def grid(self) -> Optional["VoxelGrid"]:
        """Загруженная воксельная сетка."""
        return self._grid

    # --- Drawable protocol ---

    @property
    def phase_marks(self) -> Set[str]:
        """Фазы рендеринга."""
        if self._material is None:
            return set()
        return {p.phase_mark for p in self._material.phases}

    def draw_geometry(self, context: "RenderContext") -> None:
        """Рисует геометрию вокселей."""
        if self._mesh_drawable is None:
            return
        self._mesh_drawable.draw(context)

    def get_phases(self, phase_mark: str | None = None) -> List["MaterialPhase"]:
        """Возвращает MaterialPhases для рендеринга."""
        if self._material is None:
            return []

        if phase_mark is None:
            result = list(self._material.phases)
        else:
            result = [p for p in self._material.phases if p.phase_mark == phase_mark]

        result.sort(key=lambda p: p.priority)
        return result

    # --- Логика загрузки и построения меша ---

    def _resolve_path(self, path_str: str) -> Path:
        """Разрешить путь относительно директории проекта."""
        path = Path(path_str)
        if path.is_absolute():
            return path

        from termin.editor.project_browser import ProjectBrowser
        project_root = ProjectBrowser.current_project_path
        if project_root is not None:
            return project_root / path
        return path

    def _load_file(self) -> bool:
        """Загрузить .voxels файл."""
        if not self._voxel_file:
            self._grid = None
            return False

        try:
            from termin.voxels.persistence import VoxelPersistence

            resolved_path = self._resolve_path(self._voxel_file)
            if not resolved_path.exists():
                print(f"VoxelDisplayComponent: file not found: {resolved_path}")
                self._grid = None
                return False

            self._grid = VoxelPersistence.load(resolved_path)
            print(f"VoxelDisplayComponent: loaded {self._grid.voxel_count} voxels from {resolved_path}")
            return True
        except Exception as e:
            print(f"VoxelDisplayComponent: failed to load {self._voxel_file}: {e}")
            self._grid = None
            return False

    def _rebuild_mesh(self) -> None:
        """Перестроить меш из воксельной сетки."""
        # Очищаем старый меш
        if self._mesh_drawable is not None:
            self._mesh_drawable.delete()
            self._mesh_drawable = None

        if self._grid is None:
            return

        voxel_count = self._grid.voxel_count
        if voxel_count == 0:
            return

        # Ограничение для производительности
        if voxel_count > MAX_VOXELS:
            print(f"VoxelDisplayComponent: too many voxels ({voxel_count}), showing first {MAX_VOXELS}")
            voxel_count = MAX_VOXELS

        # Выделяем массивы
        vertices = np.zeros((voxel_count * VERTS_PER_CUBE, 3), dtype=np.float32)
        triangles = np.zeros((voxel_count * TRIS_PER_CUBE, 3), dtype=np.int32)
        normals = np.zeros((voxel_count * VERTS_PER_CUBE, 3), dtype=np.float32)

        cell_size = self._grid.cell_size
        idx = 0

        for vx, vy, vz, vtype in self._grid.iter_non_empty():
            if idx >= MAX_VOXELS:
                break

            # Позиция центра вокселя
            center = self._grid.voxel_to_world(vx, vy, vz)

            # Смещаем и масштабируем вершины куба
            v_start = idx * VERTS_PER_CUBE
            v_end = v_start + VERTS_PER_CUBE
            vertices[v_start:v_end] = _CUBE_VERTICES * (cell_size * CUBE_SCALE) + center
            normals[v_start:v_end] = _CUBE_NORMALS

            # Смещаем индексы треугольников
            t_start = idx * TRIS_PER_CUBE
            t_end = t_start + TRIS_PER_CUBE
            triangles[t_start:t_end] = _CUBE_TRIANGLES + v_start

            idx += 1

        # Обрезаем если меньше max_voxels
        if idx < MAX_VOXELS:
            vertices = vertices[:idx * VERTS_PER_CUBE]
            triangles = triangles[:idx * TRIS_PER_CUBE]
            normals = normals[:idx * VERTS_PER_CUBE]

        mesh = Mesh3(
            vertices=vertices,
            triangles=triangles,
        )
        mesh.vertex_normals = normals
        self._mesh_drawable = MeshDrawable(mesh, name="voxel_display")

    # --- Lifecycle ---

    def on_added(self, scene: "Scene") -> None:
        """При добавлении в сцену загрузить файл и построить меш."""
        if self._needs_reload:
            self._load_file()
            self._rebuild_mesh()
            self._needs_reload = False

    def on_removed(self) -> None:
        """Очистить меш при удалении."""
        if self._mesh_drawable is not None:
            self._mesh_drawable.delete()
            self._mesh_drawable = None

    def update(self, dt: float) -> None:
        """Обновить меш если нужно."""
        if self._needs_reload:
            self._load_file()
            self._rebuild_mesh()
            self._needs_reload = False

    def reload(self) -> None:
        """Перезагрузить файл вручную."""
        self._needs_reload = True

    @classmethod
    def deserialize(cls, data: dict, context) -> "VoxelDisplayComponent":
        """Десериализовать компонент."""
        return cls(
            voxel_file=data.get("voxel_file", ""),
        )
