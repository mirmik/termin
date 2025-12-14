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
    WITH_NORMALS = 4    # Поверхность + нормали
    FULL_GRID = 5       # Заполнить всю сетку (без вокселизации меша)


class NavMeshStage(IntEnum):
    """Стадии алгоритма построения NavMesh."""
    TRIANGLES = 0       # Только треугольники (Alpha Shape)
    WITH_CONTOURS = 1   # + извлечённые контуры
    SIMPLIFIED = 2      # + упрощённые контуры (Douglas-Peucker)
    FINAL = 3           # Перетриангулированное (ear clipping)


def _voxelize_action(component: "VoxelizerComponent") -> None:
    """Действие кнопки вокселизации."""
    component.voxelize()


def _build_navmesh_action(component: "VoxelizerComponent") -> None:
    """Действие кнопки построения NavMesh."""
    component.build_navmesh()


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
                (VoxelizeMode.WITH_NORMALS, "With Normals"),
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
        # --- NavMesh ---
        "navmesh_output_path": InspectField(
            path="navmesh_output_path",
            label="NavMesh Path",
            kind="string",
        ),
        "normal_threshold": InspectField(
            path="normal_threshold",
            label="Normal Threshold",
            kind="float",
            min=0.0,
            max=1.0,
            step=0.01,
        ),
        "navmesh_stage": InspectField(
            path="navmesh_stage",
            label="NavMesh Stage",
            kind="enum",
            choices=[
                (NavMeshStage.TRIANGLES, "1. Triangles (Alpha Shape)"),
                (NavMeshStage.WITH_CONTOURS, "2. With Contours"),
                (NavMeshStage.SIMPLIFIED, "3. Simplified (Douglas-Peucker)"),
                (NavMeshStage.FINAL, "4. Final (Ear Clipping)"),
            ],
        ),
        "contour_epsilon": InspectField(
            path="contour_epsilon",
            label="Contour Epsilon",
            kind="float",
            min=0.001,
            max=1.0,
            step=0.001,
        ),
        "build_navmesh_btn": InspectField(
            label="Build NavMesh",
            kind="button",
            action=_build_navmesh_action,
            non_serializable=True,
        ),
    }

    serializable_fields = ["grid_name", "cell_size", "output_path", "voxelize_mode", "navmesh_output_path", "normal_threshold", "navmesh_stage", "contour_epsilon"]

    def __init__(
        self,
        grid_name: str = "",
        cell_size: float = 0.25,
        output_path: str = "",
        voxelize_mode: VoxelizeMode = VoxelizeMode.SHELL,
        navmesh_output_path: str = "",
        normal_threshold: float = 0.9,
        navmesh_stage: NavMeshStage = NavMeshStage.TRIANGLES,
        contour_epsilon: float = 0.1,
    ) -> None:
        super().__init__()
        self.grid_name = grid_name
        self.cell_size = cell_size
        self.output_path = output_path
        self.voxelize_mode = voxelize_mode
        self.navmesh_output_path = navmesh_output_path
        self.normal_threshold = normal_threshold
        self.navmesh_stage = navmesh_stage
        self.contour_epsilon = contour_epsilon
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
        from termin.voxels.voxelizer import VOXEL_SOLID
        from termin.voxels.persistence import VoxelPersistence
        from termin.voxels.native_voxelizer import voxelize_mesh_native

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
            # C++ native voxelization
            grid = voxelize_mesh_native(
                mesh,
                cell_size=self.cell_size,
                fill_interior=(mode >= VoxelizeMode.FILLED),
                mark_surface=(mode >= VoxelizeMode.MARKED),
                clear_interior=(mode >= VoxelizeMode.SURFACE_ONLY),
                compute_normals=(mode >= VoxelizeMode.WITH_NORMALS),
            )
            grid.name = name

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

    def build_navmesh(self) -> bool:
        """
        Построить NavMesh из воксельной сетки.

        Требует предварительной вокселизации с нормалями (режим WITH_NORMALS).

        Returns:
            True если успешно, False если ошибка.
        """
        from termin.visualization.core.resources import ResourceManager
        from termin.navmesh import PolygonBuilder, NavMeshConfig
        from termin.navmesh.persistence import NavMeshPersistence

        # Определяем имя сетки
        name = self.grid_name.strip()
        if not name:
            if self.entity is not None:
                name = self.entity.name or "voxel_grid"
            else:
                name = "voxel_grid"

        # Получаем воксельную сетку из ResourceManager
        rm = ResourceManager.instance()
        grid = rm.get_voxel_grid(name)

        if grid is None:
            print(f"VoxelizerComponent: voxel grid '{name}' not found. Run Voxelize first.")
            return False

        if not grid.surface_normals:
            print("VoxelizerComponent: voxel grid has no surface normals. Use WITH_NORMALS mode.")
            return False

        # Строим NavMesh
        config = NavMeshConfig(
            normal_threshold=self.normal_threshold,
            contour_epsilon=self.contour_epsilon,
        )
        builder = PolygonBuilder(config)

        # Выбираем стадию алгоритма
        stage = self.navmesh_stage
        extract_contours = stage >= NavMeshStage.WITH_CONTOURS
        simplify_contours = stage >= NavMeshStage.SIMPLIFIED
        retriangulate = stage >= NavMeshStage.FINAL

        navmesh = builder.build(
            grid,
            extract_contours=extract_contours,
            simplify_contours=simplify_contours,
            retriangulate=retriangulate,
        )

        print(f"VoxelizerComponent: built NavMesh (stage {stage.name}) with {navmesh.polygon_count()} polygons, {navmesh.triangle_count()} triangles")

        # Определяем путь для сохранения
        output = self.navmesh_output_path.strip()
        if not output:
            output = f"{name}.navmesh"

        if not output.endswith(".navmesh"):
            output += ".navmesh"

        # Устанавливаем имя navmesh (такое же как у voxel grid)
        navmesh.name = name

        # Регистрируем в ResourceManager
        rm.register_navmesh(name, navmesh)
        print(f"VoxelizerComponent: registered NavMesh '{name}'")

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

            NavMeshPersistence.save(navmesh, output_path)
            print(f"VoxelizerComponent: saved NavMesh to {output_path.absolute()}")
            return True
        except Exception as e:
            print(f"VoxelizerComponent: failed to save NavMesh: {e}")
            return False

    @classmethod
    def deserialize(cls, data: dict, context) -> "VoxelizerComponent":
        """Десериализовать компонент."""
        return cls(
            grid_name=data.get("grid_name", ""),
            cell_size=data.get("cell_size", 0.25),
            output_path=data.get("output_path", ""),
            voxelize_mode=VoxelizeMode(data.get("voxelize_mode", VoxelizeMode.SHELL)),
            navmesh_output_path=data.get("navmesh_output_path", ""),
            normal_threshold=data.get("normal_threshold", 0.9),
            navmesh_stage=NavMeshStage(data.get("navmesh_stage", NavMeshStage.TRIANGLES)),
            contour_epsilon=data.get("contour_epsilon", 0.1),
        )
