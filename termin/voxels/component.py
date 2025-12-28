"""
VoxelGridComponent — компонент Entity для хранения воксельной сетки.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from termin.visualization.core.python_component import PythonComponent
from termin.voxels.grid import VoxelGrid

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class VoxelGridComponent(PythonComponent):
    """
    Компонент, хранящий воксельную сетку.

    Используется для:
    - Хранения промежуточных данных вокселизации
    - Визуализации вокселей в редакторе
    - Сериализации/десериализации воксельных данных
    """

    def __init__(
        self,
        origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
        cell_size: float = 0.25,
    ) -> None:
        super().__init__()
        self._grid = VoxelGrid(origin=origin, cell_size=cell_size)
        self._visualizer: Optional["VoxelVisualizer"] = None
        self._visualization_dirty = True

    @property
    def grid(self) -> VoxelGrid:
        """Воксельная сетка."""
        return self._grid

    @grid.setter
    def grid(self, value: VoxelGrid) -> None:
        self._grid = value
        self._visualization_dirty = True

    def mark_dirty(self) -> None:
        """Пометить визуализацию как требующую обновления."""
        self._visualization_dirty = True

    def on_added(self, scene: "Scene") -> None:
        """Создать визуализатор при добавлении в сцену."""
        from termin.voxels.visualization import VoxelVisualizer

        if self._visualizer is None and self.entity is not None:
            self._visualizer = VoxelVisualizer(self._grid, self.entity)
            self._visualization_dirty = True

    def on_removed(self) -> None:
        """Очистить визуализатор при удалении."""
        if self._visualizer is not None:
            self._visualizer.cleanup()
            self._visualizer = None

    def update(self, dt: float) -> None:
        """Обновить визуализацию если нужно."""
        if self._visualization_dirty and self._visualizer is not None:
            self._visualizer.rebuild()
            self._visualization_dirty = False
