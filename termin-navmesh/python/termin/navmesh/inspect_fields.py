"""Shared inspect field definitions for navmesh builder components."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from termin.inspect import InspectField
from termin.voxels import VoxelizeSource


VOXELIZE_SOURCE_CHOICES = [
    (VoxelizeSource.CURRENT_MESH, "Current Mesh"),
    (VoxelizeSource.ALL_DESCENDANTS, "All Descendants"),
]

NAVMESH_POLYGON_BUILD_FIELD_NAMES = [
    "normal_angle",
    "contour_simplify",
    "max_edge_length",
    "min_edge_length",
    "min_contour_edge_length",
    "max_vertex_valence",
    "use_delaunay_flip",
    "use_valence_flip",
    "use_angle_flip",
    "use_cvt_smoothing",
    "use_edge_collapse",
    "use_second_pass",
]

NAVMESH_WATERSHED_FIELD_NAMES = [
    "use_watershed",
    "watershed_smoothing",
]

NAVMESH_DEBUG_FIELD_NAMES = [
    "show_region_voxels",
    "show_simplified_contours",
    "show_triangulated",
]

NAVMESH_WATERSHED_DEBUG_FIELD_NAMES = [
    "show_distance_field",
    "show_local_maxima",
    "show_peaks",
    "show_watershed_regions",
    "color_seed",
]


def make_voxelize_source_field() -> InspectField:
    return InspectField(
        path="voxelize_source",
        label="Source",
        kind="enum",
        choices=VOXELIZE_SOURCE_CHOICES,
    )


def make_navmesh_polygon_build_fields(
    *,
    include_watershed: bool = False,
) -> dict[str, InspectField]:
    fields = {
        "normal_angle": InspectField(
            path="normal_angle",
            label="Region Merge Angle (°)",
            kind="float",
            min=0.0,
            max=90.0,
            step=1.0,
        ),
        "contour_simplify": InspectField(
            path="contour_simplify",
            label="Contour Simplify",
            kind="float",
            min=0.0,
            max=10.0,
            step=0.1,
        ),
        "max_edge_length": InspectField(
            path="max_edge_length",
            label="Max Edge Length",
            kind="float",
            min=0.0,
            max=10.0,
            step=0.1,
        ),
        "min_edge_length": InspectField(
            path="min_edge_length",
            label="Min Edge Length",
            kind="float",
            min=0.0,
            max=5.0,
            step=0.05,
        ),
        "min_contour_edge_length": InspectField(
            path="min_contour_edge_length",
            label="Min Contour Edge",
            kind="float",
            min=0.0,
            max=5.0,
            step=0.05,
        ),
        "max_vertex_valence": InspectField(
            path="max_vertex_valence",
            label="Max Vertex Valence",
            kind="int",
            min=0,
            max=20,
            step=1,
        ),
        "use_delaunay_flip": InspectField(
            path="use_delaunay_flip",
            label="Delaunay Flip",
            kind="bool",
        ),
        "use_valence_flip": InspectField(
            path="use_valence_flip",
            label="Valence Flip",
            kind="bool",
        ),
        "use_angle_flip": InspectField(
            path="use_angle_flip",
            label="Angle Flip",
            kind="bool",
        ),
        "use_cvt_smoothing": InspectField(
            path="use_cvt_smoothing",
            label="CVT Smoothing",
            kind="bool",
        ),
        "use_edge_collapse": InspectField(
            path="use_edge_collapse",
            label="Edge Collapse",
            kind="bool",
        ),
        "use_second_pass": InspectField(
            path="use_second_pass",
            label="Second Pass",
            kind="bool",
        ),
    }
    if include_watershed:
        fields.update({
            "use_watershed": InspectField(
                path="use_watershed",
                label="Watershed Split",
                kind="bool",
            ),
            "watershed_smoothing": InspectField(
                path="watershed_smoothing",
                label="Smoothing",
                kind="int",
                min=0,
                max=10,
                step=1,
            ),
        })
    return fields


def make_navmesh_debug_fields(
    names: Iterable[str],
) -> dict[str, InspectField]:
    field_defs = {
        "show_region_voxels": InspectField(
            path="show_region_voxels",
            label="Show Regions",
            kind="bool",
        ),
        "show_sparse_boundary": InspectField(
            path="show_sparse_boundary",
            label="Show Sparse Boundary",
            kind="bool",
        ),
        "show_simplified_contours": InspectField(
            path="show_simplified_contours",
            label="Show Simplified Contours",
            kind="bool",
        ),
        "show_bridged_contours": InspectField(
            path="show_bridged_contours",
            label="Show Bridged Contours",
            kind="bool",
        ),
        "show_triangulated": InspectField(
            path="show_triangulated",
            label="Show Triangulated",
            kind="bool",
        ),
        "show_distance_field": InspectField(
            path="show_distance_field",
            label="Show Distance Field",
            kind="bool",
        ),
        "show_local_maxima": InspectField(
            path="show_local_maxima",
            label="Show Local Maxima",
            kind="bool",
        ),
        "show_peaks": InspectField(
            path="show_peaks",
            label="Show Peaks (after plateau)",
            kind="bool",
        ),
        "show_watershed_regions": InspectField(
            path="show_watershed_regions",
            label="Show Watershed",
            kind="bool",
        ),
        "color_seed": InspectField(
            path="color_seed",
            label="Color Seed",
            kind="int",
            min=0,
            max=1000,
            step=1,
        ),
    }
    return {name: field_defs[name] for name in names}


def make_button_field(
    label: str,
    action: Callable[[Any], None],
) -> InspectField:
    return InspectField(
        label=label,
        kind="button",
        action=action,
        is_serializable=False,
    )
