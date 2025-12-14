"""
VoxelizerComponent — компонент для вокселизации меша из инспектора.
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from termin.visualization.core.component import Component
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class VoxelizeMode(IntEnum):
    """Режимы вокселизации (стадии пайплайна)."""
    SHELL = 0           # Только поверхность меша
    FILLED = 1          # Поверхность + заполнение внутри
    MARKED = 2          # Заполнение + пометка поверхности (SOLID + SURFACE)
    SURFACE_ONLY = 3    # Только поверхность (внутренние удалены)
    FULL_GRID = 4       # Заполнить всю сетку (без вокселизации меша)


def _voxelize_action(component: "VoxelizerComponent") -> None:
    """Действие кнопки вокселизации."""
    component.voxelize()


class VoxelizerComponent(Component):
    """
    Компонент для вокселизации меша entity.

    Добавляется к entity с MeshRenderer.
    В инспекторе показывает кнопку "Voxelize" и настройки.
    По нажатию кнопки вокселизирует меш, регистрирует в ResourceManager и сохраняет в файл.
    """

    inspect_fields = {
        "grid_name": InspectField(
            path="grid_name",
            label="Grid Name",
            kind="string",
        ),
        "cell_size": InspectField(
            path="cell_size",
            label="Cell Size",
            kind="float",
            min=0.001,
            max=10.0,
            step=0.001,
        ),
        "voxelize_mode": InspectField(
            path="voxelize_mode",
            label="Mode",
            kind="enum",
            choices=[
                (VoxelizeMode.SHELL, "Shell (surface only)"),
                (VoxelizeMode.FILLED, "Filled (interior)"),
                (VoxelizeMode.MARKED, "Marked (surface tagged)"),
                (VoxelizeMode.SURFACE_ONLY, "Surface Only (interior removed)"),
                (VoxelizeMode.FULL_GRID, "Full Grid (fill bounds)"),
            ],
        ),
        "output_path": InspectField(
            path="output_path",
            label="Output Path",
            kind="string",
        ),
        "voxelize_btn": InspectField(
            label="Voxelize",
            kind="button",
            action=_voxelize_action,
            non_serializable=True,
        ),
    }

    serializable_fields = ["grid_name", "cell_size", "output_path", "voxelize_mode"]

    def __init__(
        self,
        grid_name: str = "",
        cell_size: float = 0.25,
        output_path: str = "",
        voxelize_mode: VoxelizeMode = VoxelizeMode.SHELL,
    ) -> None:
        super().__init__()
        self.grid_name = grid_name
        self.cell_size = cell_size
        self.output_path = output_path
        self.voxelize_mode = voxelize_mode
        self._last_voxel_count: int = 0

    def voxelize(self) -> bool:
        """
        Вокселизировать меш entity, зарегистрировать в ResourceManager и сохранить в файл.

        Returns:
            True если успешно, False если ошибка.
        """
        from termin.visualization.render.components import MeshRenderer
        from termin.visualization.core.resources import ResourceManager
        from termin.voxels.grid import VoxelGrid
        from termin.voxels.voxelizer import MeshVoxelizer, VOXEL_SOLID, VOXEL_SURFACE
        from termin.voxels.persistence import VoxelPersistence
        import numpy as np

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

        # Определяем имя сетки
        name = self.grid_name.strip()
        if not name:
            name = self.entity.name or "voxel_grid"

        # Определяем путь для сохранения
        output = self.output_path.strip()
        if not output:
            output = f"{name}.voxels"

        if not output.endswith(".voxels"):
            output += ".voxels"

        # Создаём пустую сетку
        grid = VoxelGrid(origin=(0, 0, 0), cell_size=self.cell_size, name=name)

        mode = self.voxelize_mode

        if mode == VoxelizeMode.FULL_GRID:
            # Режим заполнения всей сетки — вычисляем bounds меша и заполняем
            vertices = mesh.vertices
            if vertices is None or len(vertices) == 0:
                print("VoxelizerComponent: mesh has no vertices")
                return False

            mesh_min = vertices.min(axis=0)
            mesh_max = vertices.max(axis=0)

            # Преобразуем в индексы вокселей
            voxel_min = grid.world_to_voxel(mesh_min)
            voxel_max = grid.world_to_voxel(mesh_max)

            # Заполняем все воксели в bounds
            fill_count = 0
            for vx in range(voxel_min[0], voxel_max[0] + 1):
                for vy in range(voxel_min[1], voxel_max[1] + 1):
                    for vz in range(voxel_min[2], voxel_max[2] + 1):
                        grid.set(vx, vy, vz, VOXEL_SOLID)
                        fill_count += 1
            print(f"VoxelizerComponent: filled {fill_count} voxels in bounds")
        else:
            # Стадия 1: Вокселизируем меш (поверхность)
            voxelizer = MeshVoxelizer(grid)
            voxelizer.voxelize_mesh(mesh, transform_matrix=None)
            print(f"VoxelizerComponent: voxelized mesh, {grid.voxel_count} surface voxels")

            # Стадия 2: Заполняем внутреннее пространство (FILLED и выше)
            if mode >= VoxelizeMode.FILLED:
                filled = grid.fill_interior()
                print(f"VoxelizerComponent: filled {filled} interior voxels")

            # Стадия 3: Помечаем поверхность (MARKED и выше)
            if mode >= VoxelizeMode.MARKED:
                marked = grid.mark_surface(VOXEL_SURFACE)
                print(f"VoxelizerComponent: marked {marked} surface voxels")

            # Стадия 4: Удаляем внутренние (SURFACE_ONLY)
            if mode >= VoxelizeMode.SURFACE_ONLY:
                cleared = grid.clear_by_type(VOXEL_SOLID)
                print(f"VoxelizerComponent: cleared {cleared} interior voxels")

        self._last_voxel_count = grid.voxel_count

        # Регистрируем в ResourceManager
        rm = ResourceManager.instance()
        rm.register_voxel_grid(name, grid)
        print(f"VoxelizerComponent: registered '{name}' with {grid.voxel_count} voxels")

        # Сохраняем в файл
        try:
            output_path = Path(output)

            # Если путь относительный, разрешаем относительно директории проекта
            if not output_path.is_absolute():
                from termin.editor.project_browser import ProjectBrowser
                project_root = ProjectBrowser.current_project_path
                if project_root is not None:
                    output_path = project_root / output_path

            # Создаём директорию если не существует
            if output_path.parent and not output_path.parent.exists():
                output_path.parent.mkdir(parents=True, exist_ok=True)

            VoxelPersistence.save(grid, output_path)
            print(f"VoxelizerComponent: saved to {output_path.absolute()}")
            return True
        except Exception as e:
            print(f"VoxelizerComponent: failed to save: {e}")
            return False

    @classmethod
    def deserialize(cls, data: dict, context) -> "VoxelizerComponent":
        """Десериализовать компонент."""
        # Поддержка старого формата с fill_interior/extract_surface
        mode_value = data.get("voxelize_mode")
        if mode_value is None:
            # Конвертируем старые флаги в новый режим
            fill_interior = data.get("fill_interior", False)
            extract_surface = data.get("extract_surface", False)
            if extract_surface:
                mode_value = VoxelizeMode.SURFACE_ONLY
            elif fill_interior:
                mode_value = VoxelizeMode.FILLED
            else:
                mode_value = VoxelizeMode.SHELL
        else:
            mode_value = VoxelizeMode(mode_value)

        return cls(
            grid_name=data.get("grid_name", ""),
            cell_size=data.get("cell_size", 0.25),
            output_path=data.get("output_path", ""),
            voxelize_mode=mode_value,
        )
