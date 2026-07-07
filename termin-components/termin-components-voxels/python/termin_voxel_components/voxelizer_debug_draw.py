"""Debug draw table for VoxelizerComponent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from termin.render.drawable import RenderItem


@dataclass(frozen=True)
class VoxelizerDebugLayer:
    enabled: Callable[[Any], bool]
    mesh: Callable[[Any], Any]
    material: Callable[[Any], Any]
    geometry_id: Callable[[Any], int]
    configure_phases: Callable[[Any, list[Any]], None] | None = None


def _apply_voxel_display_params(
    phase,
    color_below: np.ndarray,
    color_above: np.ndarray,
    slice_axis: np.ndarray,
    fill_percent: float,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
) -> None:
    slice_axis_fill = np.array(
        [slice_axis[0], slice_axis[1], slice_axis[2], fill_percent],
        dtype=np.float32,
    )
    padded_bounds_min = np.array(
        [bounds_min[0], bounds_min[1], bounds_min[2], 0.0],
        dtype=np.float32,
    )
    padded_bounds_max = np.array(
        [bounds_max[0], bounds_max[1], bounds_max[2], 0.0],
        dtype=np.float32,
    )

    phase.set_param("u_color_below", color_below)
    phase.set_param("u_color_above", color_above)
    phase.set_param("u_slice_axis_fill_percent", slice_axis_fill)
    phase.set_param("u_bounds_min", padded_bounds_min)
    phase.set_param("u_bounds_max", padded_bounds_max)


def _configure_vertex_color_voxel_phases(component, phases: list[Any]) -> None:
    white_color = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
    z_axis = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    for phase in phases:
        _apply_voxel_display_params(
            phase,
            white_color,
            white_color,
            z_axis,
            1.0,
            component._debug_bounds_min,
            component._debug_bounds_max,
        )


def _configure_inner_contour_phases(component, phases: list[Any]) -> None:
    color = np.array([1.0, 0.5, 0.0, 0.5], dtype=np.float32)
    z_axis = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    for phase in phases:
        _apply_voxel_display_params(
            phase,
            color,
            color,
            z_axis,
            1.0,
            component._debug_bounds_min,
            component._debug_bounds_max,
        )


VOXELIZER_DEBUG_LAYERS = (
    VoxelizerDebugLayer(
        enabled=lambda component: component.show_region_voxels,
        mesh=lambda component: component._debug_region_voxels_mesh,
        material=lambda component: component._get_or_create_debug_material(),
        geometry_id=lambda component: component.GEOMETRY_REGIONS,
        configure_phases=_configure_vertex_color_voxel_phases,
    ),
    VoxelizerDebugLayer(
        enabled=lambda component: component.show_sparse_boundary,
        mesh=lambda component: component._debug_sparse_boundary_mesh,
        material=lambda component: component._get_or_create_debug_material(),
        geometry_id=lambda component: component.GEOMETRY_SPARSE_BOUNDARY,
        configure_phases=_configure_vertex_color_voxel_phases,
    ),
    VoxelizerDebugLayer(
        enabled=lambda component: component.show_sparse_boundary,
        mesh=lambda component: component._debug_inner_contour_mesh,
        material=lambda component: component._get_or_create_transparent_material(),
        geometry_id=lambda component: component.GEOMETRY_INNER_CONTOUR,
        configure_phases=_configure_inner_contour_phases,
    ),
    VoxelizerDebugLayer(
        enabled=lambda component: component.show_simplified_contours,
        mesh=lambda component: component._debug_simplified_contours_mesh,
        material=lambda component: component._get_or_create_line_material(),
        geometry_id=lambda component: component.GEOMETRY_SIMPLIFIED_CONTOURS,
    ),
    VoxelizerDebugLayer(
        enabled=lambda component: component.show_bridged_contours,
        mesh=lambda component: component._debug_bridged_contours_mesh,
        material=lambda component: component._get_or_create_line_material(),
        geometry_id=lambda component: component.GEOMETRY_BRIDGED_CONTOURS,
    ),
    VoxelizerDebugLayer(
        enabled=lambda component: component.show_triangulated,
        mesh=lambda component: component._debug_triangulated_mesh,
        material=lambda component: component._get_or_create_line_material(),
        geometry_id=lambda component: component.GEOMETRY_TRIANGULATED,
    ),
)


class VoxelizerDebugDrawService:
    def phase_marks(self, component) -> set[str]:
        marks: set[str] = set()
        for layer in VOXELIZER_DEBUG_LAYERS:
            if layer.enabled(component):
                mat = layer.material(component)
                marks.update(p.phase_mark for p in mat.phases)
        return marks

    def collect_render_items(
        self,
        component,
        phase_mark: str,
    ) -> list[RenderItem]:
        result: list[RenderItem] = []
        for layer in VOXELIZER_DEBUG_LAYERS:
            if not layer.enabled(component):
                continue
            mesh = layer.mesh(component)
            if mesh is None or not mesh.is_valid:
                continue

            mat = layer.material(component)
            if phase_mark == "":
                phases = list(mat.phases)
            else:
                phases = [p for p in mat.phases if p.phase_mark == phase_mark]
            if layer.configure_phases is not None:
                layer.configure_phases(component, phases)

            phases.sort(key=lambda p: p.priority)
            geometry_id = layer.geometry_id(component)
            result.extend(
                RenderItem.mesh(mesh=mesh, phase=p, geometry_id=geometry_id)
                for p in phases
            )

        return result
