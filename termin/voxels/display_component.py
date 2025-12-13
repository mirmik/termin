"""
VoxelDisplayComponent — компонент для отображения .voxels файла.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from termin.visualization.core.component import Component
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.voxels.grid import VoxelGrid
    from termin.voxels.visualization import VoxelVisualizer


class VoxelDisplayComponent(Component):
    """
    Компонент для отображения воксельной сетки из .voxels файла.

    Загружает файл и визуализирует воксели в локальной системе координат entity.
    """

    inspect_fields = {
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
        self._visualizer: Optional["VoxelVisualizer"] = None
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

    def _rebuild_visualization(self) -> None:
        """Перестроить визуализацию."""
        from termin.voxels.visualization import VoxelVisualizer

        # Очищаем старую визуализацию
        if self._visualizer is not None:
            self._visualizer.cleanup()
            self._visualizer = None

        if self._grid is None or self.entity is None:
            return

        self._visualizer = VoxelVisualizer(self._grid, self.entity)
        self._visualizer.rebuild()

    def on_added(self, scene: "Scene") -> None:
        """При добавлении в сцену загрузить файл и создать визуализацию."""
        if self._needs_reload:
            self._load_file()
            self._rebuild_visualization()
            self._needs_reload = False

    def on_removed(self) -> None:
        """Очистить визуализацию при удалении."""
        if self._visualizer is not None:
            self._visualizer.cleanup()
            self._visualizer = None

    def update(self, dt: float) -> None:
        """Обновить визуализацию если нужно."""
        if self._needs_reload:
            self._load_file()
            self._rebuild_visualization()
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
