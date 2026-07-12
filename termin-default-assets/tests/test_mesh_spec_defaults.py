import json

import numpy as np

from termin.default_assets.mesh.mesh_spec import DEFAULT_AXIS_X, DEFAULT_AXIS_Y, DEFAULT_AXIS_Z, MeshSpec


def test_mesh_spec_defaults_convert_unity_style_to_termin_axes() -> None:
    spec = MeshSpec()
    vertices = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    normals = np.array([[0.0, 1.0, 0.0]], dtype=np.float32)

    assert (spec.axis_x, spec.axis_y, spec.axis_z) == (
        DEFAULT_AXIS_X,
        DEFAULT_AXIS_Y,
        DEFAULT_AXIS_Z,
    )
    assert spec.apply_to_vertices(vertices).tolist() == [[1.0, 3.0, 2.0]]
    assert spec.apply_to_normals(normals).tolist() == [[0.0, 0.0, 1.0]]


def test_mesh_spec_uuid_only_meta_uses_default_axis_conversion(tmp_path) -> None:
    meta_path = tmp_path / "tree.obj.meta"
    meta_path.write_text(json.dumps({"uuid": "tree-uuid"}), encoding="utf-8")

    spec = MeshSpec.load(meta_path)

    assert (spec.axis_x, spec.axis_y, spec.axis_z) == ("x", "z", "y")


def test_mesh_spec_explicit_identity_axes_are_preserved(tmp_path) -> None:
    meta_path = tmp_path / "legacy.obj.meta"
    meta_path.write_text(
        json.dumps({"axis_x": "x", "axis_y": "y", "axis_z": "z"}),
        encoding="utf-8",
    )

    spec = MeshSpec.load(meta_path)
    vertices = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)

    assert (spec.axis_x, spec.axis_y, spec.axis_z) == ("x", "y", "z")
    assert spec.apply_to_vertices(vertices).tolist() == [[1.0, 2.0, 3.0]]


def test_mesh_spec_preserves_ccw_winding_across_default_axis_reflection() -> None:
    spec = MeshSpec()
    vertices = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float32,
    )
    indices = np.array([0, 1, 2], dtype=np.uint32)

    transformed_vertices = spec.apply_to_vertices(vertices)
    transformed_indices = spec.apply_to_triangle_indices(indices)
    p0, p1, p2 = transformed_vertices[transformed_indices]
    transformed_normal = spec.apply_to_normals(
        np.array([[0.0, 0.0, 1.0]], dtype=np.float32)
    )[0]

    assert spec.reverses_orientation()
    assert transformed_indices.tolist() == [0, 2, 1]
    assert np.dot(np.cross(p1 - p0, p2 - p0), transformed_normal) > 0.0


def test_mesh_spec_identity_transform_keeps_triangle_indices() -> None:
    spec = MeshSpec(axis_x="x", axis_y="y", axis_z="z")
    indices = np.array([0, 1, 2], dtype=np.uint32)

    assert not spec.reverses_orientation()
    assert spec.apply_to_triangle_indices(indices) is indices


def test_mesh_spec_negative_scale_keeps_winding_and_normals_consistent() -> None:
    spec = MeshSpec(scale=-2.0, axis_x="x", axis_y="y", axis_z="z")
    vertices = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=np.float32,
    )
    indices = spec.apply_to_triangle_indices(
        np.array([0, 1, 2], dtype=np.uint32)
    )
    transformed = spec.apply_to_vertices(vertices)
    normal = spec.apply_to_normals(
        np.array([[0.0, 0.0, 1.0]], dtype=np.float32)
    )[0]
    p0, p1, p2 = transformed[indices]

    assert indices.tolist() == [0, 2, 1]
    assert normal.tolist() == [0.0, 0.0, -1.0]
    assert np.dot(np.cross(p1 - p0, p2 - p0), normal) > 0.0
