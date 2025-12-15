"""
VoxelizerComponent — компонент для вокселизации меша из инспектора.

Реализует протокол Drawable для отладочной визуализации регионов.
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Set

import numpy as np

from termin.visualization.core.component import Component
from termin.visualization.core.material import Material
from termin.visualization.core.mesh import Mesh3, MeshDrawable
from termin.visualization.render.drawable import GeometryDrawCall
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.render_context import RenderContext
    from termin.voxels.grid import VoxelGrid


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
    REGIONS_BASIC = 0       # Регионы до расширения
    REGIONS_EXPANDED = 1    # Регионы после расширения
    STITCHED = 2            # Сшитые полигоны (plane intersections)
    WITH_CONTOURS = 3       # + извлечённые контуры
    SIMPLIFIED = 4          # + упрощённые контуры (Douglas-Peucker)
    FINAL = 5               # Перетриангулированное (ear clipping)


def _voxelize_action(component: "VoxelizerComponent") -> None:
    """Действие кнопки вокселизации."""
    component.voxelize()


def _build_navmesh_action(component: "VoxelizerComponent") -> None:
    """Действие кнопки построения NavMesh."""
    component.build_navmesh()


def _set_debug_region(component: "VoxelizerComponent", value: int) -> None:
    """Setter для debug_region_idx — перестраивает отладочный меш."""
    component.debug_region_idx = value
    component._rebuild_debug_mesh()


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
        "normal_angle": InspectField(
            path="normal_angle",
            label="Region Merge Angle (°)",
            kind="float",
            min=0.0,
            max=90.0,
            step=1.0,
        ),
        "navmesh_stage": InspectField(
            path="navmesh_stage",
            label="NavMesh Stage",
            kind="enum",
            choices=[
                (NavMeshStage.REGIONS_BASIC, "1. Regions (basic)"),
                (NavMeshStage.REGIONS_EXPANDED, "2. Regions (expanded)"),
                (NavMeshStage.STITCHED, "3. Stitched (plane intersections)"),
                (NavMeshStage.WITH_CONTOURS, "4. With Contours"),
                (NavMeshStage.SIMPLIFIED, "5. Simplified (Douglas-Peucker)"),
                (NavMeshStage.FINAL, "6. Final (Ear Clipping)"),
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
        # --- Debug ---
        "debug_region_idx": InspectField(
            path="debug_region_idx",
            label="Debug Region",
            kind="int",
            min=-1,
            max=1000,
            setter=_set_debug_region,
        ),
        "debug_show_contour": InspectField(
            path="debug_show_contour",
            label="Show Contour",
            kind="bool",
        ),
    }

    serializable_fields = ["grid_name", "cell_size", "output_path", "voxelize_mode", "navmesh_output_path", "normal_angle", "navmesh_stage", "contour_epsilon", "debug_region_idx"]

    def __init__(
        self,
        grid_name: str = "",
        cell_size: float = 0.25,
        output_path: str = "",
        voxelize_mode: VoxelizeMode = VoxelizeMode.SHELL,
        navmesh_output_path: str = "",
        normal_angle: float = 25.0,
        navmesh_stage: NavMeshStage = NavMeshStage.REGIONS_BASIC,
        contour_epsilon: float = 0.1,
        debug_region_idx: int = -1,
    ) -> None:
        super().__init__()
        self.grid_name = grid_name
        self.cell_size = cell_size
        self.output_path = output_path
        self.voxelize_mode = voxelize_mode
        self.navmesh_output_path = navmesh_output_path
        self.normal_angle = normal_angle
        self.navmesh_stage = navmesh_stage
        self.contour_epsilon = contour_epsilon
        self._last_voxel_count: int = 0

        # Debug visualization
        self.debug_region_idx: int = debug_region_idx
        self.debug_show_contour: bool = True
        self._debug_regions: list[tuple[list[tuple[int, int, int]], np.ndarray]] = []
        self._debug_grid: Optional["VoxelGrid"] = None
        self._debug_mesh_drawable: Optional[MeshDrawable] = None
        self._debug_contour_drawable: Optional[MeshDrawable] = None
        self._debug_material: Optional[Material] = None

    # --- Drawable protocol ---

    @property
    def phase_marks(self) -> Set[str]:
        """Фазы рендеринга для отладочной визуализации."""
        mat = self._get_or_create_debug_material()
        return {p.phase_mark for p in mat.phases}

    def draw_geometry(self, context: "RenderContext", geometry_id: str = "") -> None:
        """Рисует отладочную геометрию."""
        if self._debug_mesh_drawable is not None:
            self._debug_mesh_drawable.draw(context)
        if self.debug_show_contour and self._debug_contour_drawable is not None:
            self._debug_contour_drawable.draw(context)

    def get_geometry_draws(self, phase_mark: str | None = None) -> List[GeometryDrawCall]:
        """Возвращает GeometryDrawCalls для отладочного рендеринга."""
        mat = self._get_or_create_debug_material()

        if phase_mark is None:
            phases = list(mat.phases)
        else:
            phases = [p for p in mat.phases if p.phase_mark == phase_mark]

        phases.sort(key=lambda p: p.priority)
        return [GeometryDrawCall(phase=p) for p in phases]

    def _get_or_create_debug_material(self) -> Material:
        """Создаёт материал для отладочной визуализации."""
        if self._debug_material is None:
            from termin.voxels.voxel_shader import voxel_display_shader
            from termin.visualization.render.renderpass import RenderState

            shader = voxel_display_shader()
            self._debug_material = Material(
                shader=shader,
                color=(1.0, 0.5, 0.0, 0.8),  # Оранжевый для отладки
                phase_mark="editor",
                render_state=RenderState(
                    depth_test=True,
                    depth_write=True,
                    blend=True,
                    cull=True,
                ),
            )
        return self._debug_material

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
        # Конвертируем угол в косинус для threshold
        import math
        normal_threshold = math.cos(math.radians(self.normal_angle))

        config = NavMeshConfig(
            normal_threshold=normal_threshold,
            contour_epsilon=self.contour_epsilon,
        )
        builder = PolygonBuilder(config)

        # Выбираем стадию алгоритма
        stage = self.navmesh_stage
        expand_regions = stage >= NavMeshStage.REGIONS_EXPANDED
        stitch_polygons = stage >= NavMeshStage.STITCHED
        extract_contours = stage >= NavMeshStage.WITH_CONTOURS
        simplify_contours = stage >= NavMeshStage.SIMPLIFIED
        retriangulate = stage >= NavMeshStage.FINAL

        navmesh = builder.build(
            grid,
            expand_regions=expand_regions,
            stitch_polygons=stitch_polygons,
            extract_contours=extract_contours,
            simplify_contours=simplify_contours,
            retriangulate=retriangulate,
        )

        # Сохраняем регионы и grid для отладочной визуализации
        self._debug_regions = builder._last_regions
        self._debug_grid = grid
        print(f"VoxelizerComponent: saved {len(self._debug_regions)} regions for debug")

        # Перестраиваем отладочный меш
        self._rebuild_debug_mesh()

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

    def _rebuild_debug_mesh(self) -> None:
        """Перестроить отладочный меш для выбранного региона."""
        from termin.voxels.display_component import (
            _CUBE_VERTICES, _CUBE_TRIANGLES, _CUBE_NORMALS,
            VERTS_PER_CUBE, TRIS_PER_CUBE, CUBE_SCALE,
        )

        # Очищаем старые drawable
        if self._debug_mesh_drawable is not None:
            self._debug_mesh_drawable.delete()
            self._debug_mesh_drawable = None
        if self._debug_contour_drawable is not None:
            self._debug_contour_drawable.delete()
            self._debug_contour_drawable = None

        if not self._debug_regions or self._debug_grid is None:
            return

        region_idx = self.debug_region_idx
        if region_idx < 0 or region_idx >= len(self._debug_regions):
            print(f"VoxelizerComponent: region {region_idx} out of range (0-{len(self._debug_regions)-1})")
            return

        region_voxels, region_normal = self._debug_regions[region_idx]
        if not region_voxels:
            return

        grid = self._debug_grid
        cell_size = grid.cell_size

        # Строим меш из вокселей региона
        voxel_count = len(region_voxels)
        vertices = np.zeros((voxel_count * VERTS_PER_CUBE, 3), dtype=np.float32)
        triangles = np.zeros((voxel_count * TRIS_PER_CUBE, 3), dtype=np.int32)
        normals = np.zeros((voxel_count * VERTS_PER_CUBE, 3), dtype=np.float32)

        cube_size = cell_size * CUBE_SCALE

        for i, (vx, vy, vz) in enumerate(region_voxels):
            center = grid.voxel_to_world(vx, vy, vz)
            v_offset = i * VERTS_PER_CUBE
            t_offset = i * TRIS_PER_CUBE

            # Масштабируем и смещаем вершины куба
            vertices[v_offset:v_offset + VERTS_PER_CUBE] = (
                _CUBE_VERTICES * cube_size + center
            )
            triangles[t_offset:t_offset + TRIS_PER_CUBE] = (
                _CUBE_TRIANGLES + v_offset
            )
            normals[v_offset:v_offset + VERTS_PER_CUBE] = _CUBE_NORMALS

        mesh = Mesh3(vertices=vertices, triangles=triangles, normals=normals)
        self._debug_mesh_drawable = MeshDrawable(mesh)

        # Строим контур региона
        self._rebuild_debug_contour(region_voxels, region_normal, grid)

        print(f"VoxelizerComponent: debug mesh built for region {region_idx} ({voxel_count} voxels)")

    def _rebuild_debug_contour(
        self,
        voxels: list[tuple[int, int, int]],
        normal: np.ndarray,
        grid: "VoxelGrid",
    ) -> None:
        """Построить отладочный контур для региона."""
        from termin.navmesh.polygon_builder import PolygonBuilder
        from termin.navmesh.display_component import _build_line_ribbon

        # Используем тот же алгоритм что и для NavMesh
        builder = PolygonBuilder()
        polygon = builder._extract_contour_from_voxels(voxels, normal, grid)

        if polygon is None or polygon.outer_contour is None:
            return

        # Строим ribbon для контура
        contour_width = grid.cell_size * 0.1
        up_hint = np.array(normal, dtype=np.float32)

        outer = polygon.outer_contour
        verts = polygon.vertices

        if len(outer) < 2:
            return

        # Замыкаем контур
        points = [tuple(verts[idx]) for idx in outer]
        points.append(points[0])

        ribbon_verts, ribbon_tris = _build_line_ribbon(points, contour_width, up_hint)

        if len(ribbon_tris) > 0:
            mesh = Mesh3(vertices=ribbon_verts, triangles=ribbon_tris)
            self._debug_contour_drawable = MeshDrawable(mesh)

    @classmethod
    def deserialize(cls, data: dict, context) -> "VoxelizerComponent":
        """Десериализовать компонент."""
        return cls(
            grid_name=data.get("grid_name", ""),
            cell_size=data.get("cell_size", 0.25),
            output_path=data.get("output_path", ""),
            voxelize_mode=VoxelizeMode(data.get("voxelize_mode", VoxelizeMode.SHELL)),
            navmesh_output_path=data.get("navmesh_output_path", ""),
            normal_angle=data.get("normal_angle", 25.0),
            navmesh_stage=NavMeshStage(data.get("navmesh_stage", NavMeshStage.REGIONS_BASIC)),
            contour_epsilon=data.get("contour_epsilon", 0.1),
            debug_region_idx=data.get("debug_region_idx", -1),
        )
