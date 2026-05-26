import json

import numpy as np

from termin.loaders.mesh_spec import DEFAULT_AXIS_X, DEFAULT_AXIS_Y, DEFAULT_AXIS_Z, MeshSpec


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
