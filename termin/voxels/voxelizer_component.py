"""
VoxelizerComponent — компонент для вокселизации меша из инспектора.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from termin.visualization.core.component import Component
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


def _voxelize_action(component: "VoxelizerComponent") -> None:
    """Действие кнопки вокселизации."""
    component.voxelize()


class VoxelizerComponent(Component):
    """
    Компонент для вокселизации меша entity.

    Добавляется к entity с MeshRenderer.
    В инспекторе показывает кнопку "Voxelize" и настройки.
    По нажатию кнопки вокселизирует меш и сохраняет в файл.
    """

    inspect_fields = {
        "cell_size": InspectField(
            path="cell_size",
            label="Cell Size",
            kind="float",
            min=0.01,
            max=10.0,
            step=0.05,
        ),
        "output_path": InspectField(
            path="output_path",
            label="Output Path",
            kind="string",
        ),
        "voxelize_btn": InspectField(
            label="Voxelize Mesh",
            kind="button",
            action=_voxelize_action,
            non_serializable=True,
        ),
    }

    serializable_fields = ["cell_size", "output_path"]

    def __init__(
        self,
        cell_size: float = 0.25,
        output_path: str = "",
    ) -> None:
        super().__init__()
        self.cell_size = cell_size
        self.output_path = output_path
        self._last_voxel_count: int = 0

    def voxelize(self) -> bool:
        """
        Вокселизировать меш entity и сохранить в файл.

        Returns:
            True если успешно, False если ошибка.
        """
        from termin.visualization.render.components import MeshRenderer
        from termin.voxels.grid import VoxelGrid
        from termin.voxels.voxelizer import MeshVoxelizer
        from termin.voxels.persistence import VoxelPersistence

        if self.entity is None:
            print("VoxelizerComponent: no entity")
            return False

        # Ищем MeshRenderer на этом entity
        renderer: Optional[MeshRenderer] = None
        for comp in self.entity.components:
            if isinstance(comp, MeshRenderer):
                renderer = comp
                break

        if renderer is None:
            print("VoxelizerComponent: no MeshRenderer on entity")
            return False

        mesh_drawable = renderer.mesh
        if mesh_drawable is None:
            print("VoxelizerComponent: MeshRenderer has no mesh")
            return False

        mesh = mesh_drawable.mesh
        if mesh is None:
            print("VoxelizerComponent: mesh is None")
            return False

        # Определяем путь для сохранения
        output = self.output_path.strip()
        if not output:
            # Генерируем имя по умолчанию
            entity_name = self.entity.name or "entity"
            output = f"{entity_name}.voxels"

        if not output.endswith(".voxels"):
            output += ".voxels"

        # Вокселизируем меш в локальных координатах (без трансформа)
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=self.cell_size)
        voxelizer = MeshVoxelizer(grid)

        # Вокселизируем без трансформа — в локальной СК меша
        count = voxelizer.voxelize_mesh(mesh, transform_matrix=None)

        self._last_voxel_count = grid.voxel_count

        # Сохраняем
        try:
            output_path = Path(output)
            # Создаём директорию если не существует
            if output_path.parent and not output_path.parent.exists():
                output_path.parent.mkdir(parents=True, exist_ok=True)

            VoxelPersistence.save(grid, output_path)
            print(f"VoxelizerComponent: saved {grid.voxel_count} voxels to {output_path.absolute()}")
            return True
        except Exception as e:
            print(f"VoxelizerComponent: failed to save: {e}")
            return False

    @classmethod
    def deserialize(cls, data: dict, context) -> "VoxelizerComponent":
        """Десериализовать компонент."""
        return cls(
            cell_size=data.get("cell_size", 0.25),
            output_path=data.get("output_path", ""),
        )
