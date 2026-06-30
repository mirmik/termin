"""VoxelizerComponent inspector actions."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from tcbase import log
from termin_voxel_components.voxelize_enums import VoxelizeMode, VoxelizeSource


class VoxelizerActionService:
    """Runs VoxelizerComponent actions while the component owns UI/debug state."""

    def voxelize(self, component) -> bool:
        from termin.voxels.grid import VoxelGrid
        from termin.voxels.native_voxelizer import voxelize_mesh_native
        from termin.voxels.persistence import VoxelPersistence
        from termin.voxels.voxelizer import VOXEL_SOLID

        log.warning("VoxelizerComponent: starting voxelization")
        if component.entity is None:
            log.error("VoxelizerComponent: no entity")
            return False

        root_world = component.entity.model_matrix()
        root_inv = np.linalg.inv(root_world)

        recurse = (component.voxelize_source == VoxelizeSource.ALL_DESCENDANTS)
        meshes = component._collect_meshes_from_entity(
            component.entity,
            root_inv,
            recurse=recurse,
        )

        if not meshes:
            log.error("VoxelizerComponent: no meshes found")
            return False

        if len(meshes) > 1:
            log.warning(f"VoxelizerComponent: found {len(meshes)} meshes")

        mesh = component._create_combined_mesh(meshes)
        if mesh is None:
            log.error("VoxelizerComponent: failed to create mesh")
            return False

        name = component.grid_name.strip()
        if not name:
            name = component.entity.name or "voxel_grid"

        output = component.output_path.strip()
        if not output:
            output = f"{name}.voxels"
        if not output.endswith(".voxels"):
            output += ".voxels"

        grid = VoxelGrid(origin=(0, 0, 0), cell_size=component.cell_size, name=name)
        mode = component.voxelize_mode

        if mode == VoxelizeMode.FULL_GRID:
            vertices = mesh.vertices
            if vertices is None or len(vertices) == 0:
                log.error("VoxelizerComponent: mesh has no vertices")
                return False

            mesh_min = vertices.min(axis=0)
            mesh_max = vertices.max(axis=0)
            voxel_min = grid.world_to_voxel(mesh_min)
            voxel_max = grid.world_to_voxel(mesh_max)

            fill_count = 0
            for vx in range(voxel_min[0], voxel_max[0] + 1):
                for vy in range(voxel_min[1], voxel_max[1] + 1):
                    for vz in range(voxel_min[2], voxel_max[2] + 1):
                        grid.set(vx, vy, vz, VOXEL_SOLID)
                        fill_count += 1
            log.warning(f"VoxelizerComponent: filled {fill_count} voxels in bounds")
        else:
            grid = voxelize_mesh_native(
                mesh,
                cell_size=component.cell_size,
                fill_interior=(mode >= VoxelizeMode.FILLED),
                mark_surface=(mode >= VoxelizeMode.MARKED),
                clear_interior=(mode >= VoxelizeMode.SURFACE_ONLY),
                compute_normals=(mode >= VoxelizeMode.WITH_NORMALS),
            )
            grid.name = name

        component._last_voxel_count = grid.voxel_count
        component._debug_grid = grid
        component._rebuild_voxel_display_mesh()

        try:
            output_path = Path(output)
            if output_path.parent and not output_path.parent.exists():
                output_path.parent.mkdir(parents=True, exist_ok=True)

            VoxelPersistence.save(grid, output_path)
            log.warning(f"VoxelizerComponent: saved to {output_path.absolute()}")
            return True
        except Exception as e:
            log.error(f"VoxelizerComponent: failed to save: {e}")
            return False

    def build_navmesh(self, component) -> bool:
        import math

        from termin.navmesh import NavMeshConfig, PolygonBuilder
        from termin.navmesh.persistence import NavMeshPersistence
        from termin_assets import get_resource_manager

        name = component.grid_name.strip()
        if not name:
            if component.entity is not None:
                name = component.entity.name or "voxel_grid"
            else:
                name = "voxel_grid"

        rm = get_resource_manager()
        if rm is None:
            log.error("VoxelizerComponent: resource manager is not configured.")
            return False
        grid = rm.get_voxel_grid(name)

        if grid is None:
            log.error(f"VoxelizerComponent: voxel grid '{name}' not found. Run Voxelize first.")
            return False

        if not grid.surface_normals:
            log.error("VoxelizerComponent: voxel grid has no surface normals. Use WITH_NORMALS mode.")
            return False

        normal_threshold = math.cos(math.radians(component.normal_angle))
        contour_epsilon = component.contour_simplify * grid.cell_size

        config = NavMeshConfig(
            normal_threshold=normal_threshold,
            contour_epsilon=contour_epsilon,
            max_edge_length=component.max_edge_length,
            min_edge_length=component.min_edge_length,
            min_contour_edge_length=component.min_contour_edge_length,
            max_vertex_valence=component.max_vertex_valence,
            use_delaunay_flip=component.use_delaunay_flip,
            use_valence_flip=component.use_valence_flip,
            use_angle_flip=component.use_angle_flip,
            use_cvt_smoothing=component.use_cvt_smoothing,
            use_edge_collapse=component.use_edge_collapse,
            use_second_pass=component.use_second_pass,
        )
        builder = PolygonBuilder(config)

        navmesh = builder.build(
            grid,
            do_expand_regions=False,
            share_boundary=False,
            project_contours=False,
            stitch_contours=False,
        )

        component._debug_regions = builder._last_regions
        component._debug_grid = grid
        log.warning(f"VoxelizerComponent: saved {len(component._debug_regions)} regions for debug")

        component._rebuild_debug_mesh()
        component._build_debug_mesh_from_navmesh(navmesh)

        log.warning(
            "VoxelizerComponent: built NavMesh with "
            f"{navmesh.polygon_count()} polygons, {navmesh.triangle_count()} triangles"
        )

        output = component.navmesh_output_path.strip()
        if not output:
            output = f"{name}.navmesh"
        if not output.endswith(".navmesh"):
            output += ".navmesh"

        navmesh.name = name
        rm.register_navmesh(name, navmesh)
        log.warning(f"VoxelizerComponent: registered NavMesh '{name}'")

        try:
            output_path = Path(output)
            if output_path.parent and not output_path.parent.exists():
                output_path.parent.mkdir(parents=True, exist_ok=True)

            NavMeshPersistence.save(navmesh, output_path)
            log.warning(f"VoxelizerComponent: saved NavMesh to {output_path.absolute()}")
            return True
        except Exception as e:
            log.error(f"VoxelizerComponent: failed to save NavMesh: {e}")
            return False
