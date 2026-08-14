import math

import pytest

from termin.geombase import Mat44f, Pose3, Vec3
from termin.mesh.surface_edge_query import (
    _surface_edge_axis_length_metric,
    _world_normal_to_mesh_query,
)
from termin.scene import TcScene, TransformKind


def test_surface_edge_affine_helpers_use_exact_basis_and_named_metric_policy():
    scene = TcScene.create("surface-edge-affine-policy")
    parent = scene.create_entity("parent")
    child = parent.create_child("child")
    parent.transform.set_local_scale(2.0, 1.0, 1.0)
    child.transform.set_local_rotation(Pose3.rotateZ(math.pi / 4.0).ang)

    assert child.transform.kind == TransformKind.Affine

    mesh_offset = Mat44f.identity()
    metric = _surface_edge_axis_length_metric(child.transform, mesh_offset)
    expected_length = math.sqrt(2.5)
    assert metric.x == pytest.approx(expected_length)
    assert metric.y == pytest.approx(expected_length)
    assert metric.z == pytest.approx(1.0)

    local_normal = _world_normal_to_mesh_query(
        child.transform,
        mesh_offset,
        Vec3.unit_x(),
        metric,
    )
    inv_sqrt_two = 1.0 / math.sqrt(2.0)
    assert local_normal.x == pytest.approx(inv_sqrt_two)
    assert local_normal.y == pytest.approx(-inv_sqrt_two)
    assert local_normal.z == pytest.approx(0.0)

    scene.destroy()
