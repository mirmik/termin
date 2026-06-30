from termin.navmesh.inspect_fields import (
    NAVMESH_POLYGON_BUILD_FIELD_NAMES,
    VOXELIZE_SOURCE_CHOICES,
    make_navmesh_debug_fields,
    make_navmesh_polygon_build_fields,
    make_voxelize_source_field,
)
from termin.voxels import VoxelizeSource


def test_shared_voxelize_source_field_uses_canonical_enum_choices():
    field = make_voxelize_source_field()

    assert field.path == "voxelize_source"
    assert field.kind == "enum"
    assert field.choices == VOXELIZE_SOURCE_CHOICES
    assert field.choices == [
        (VoxelizeSource.CURRENT_MESH, "Current Mesh"),
        (VoxelizeSource.ALL_DESCENDANTS, "All Descendants"),
    ]


def test_shared_navmesh_polygon_fields_preserve_builder_schema():
    fields = make_navmesh_polygon_build_fields(include_watershed=True)

    assert list(fields) == [
        *NAVMESH_POLYGON_BUILD_FIELD_NAMES,
        "use_watershed",
        "watershed_smoothing",
    ]
    assert fields["normal_angle"].label == "Region Merge Angle (°)"
    assert fields["normal_angle"].min == 0.0
    assert fields["normal_angle"].max == 90.0
    assert fields["contour_simplify"].step == 0.1
    assert fields["max_vertex_valence"].kind == "int"
    assert fields["use_second_pass"].kind == "bool"
    assert fields["watershed_smoothing"].kind == "int"


def test_debug_field_factory_selects_component_specific_subset():
    fields = make_navmesh_debug_fields((
        "show_region_voxels",
        "show_sparse_boundary",
        "show_triangulated",
    ))

    assert list(fields) == [
        "show_region_voxels",
        "show_sparse_boundary",
        "show_triangulated",
    ]
    assert fields["show_sparse_boundary"].label == "Show Sparse Boundary"
    assert fields["show_triangulated"].kind == "bool"
