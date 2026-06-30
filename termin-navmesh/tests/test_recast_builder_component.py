"""Tests for native Recast builder component behavior."""

from __future__ import annotations

import numpy as np
import pytest


try:
    from termin.navmesh import RecastNavMeshBuilderComponent
except ImportError as exc:  # pragma: no cover - depends on built SDK availability.
    pytestmark = pytest.mark.skip(reason=str(exc))


def _unit_cube_geometry() -> tuple[np.ndarray, np.ndarray]:
    vertices = np.array(
        [
            [-0.5, -0.5, -0.5],
            [0.5, -0.5, -0.5],
            [0.5, 0.5, -0.5],
            [-0.5, 0.5, -0.5],
            [-0.5, -0.5, 0.5],
            [0.5, -0.5, 0.5],
            [0.5, 0.5, 0.5],
            [-0.5, 0.5, 0.5],
        ],
        dtype=np.float32,
    )
    triangles = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 6, 5],
            [4, 7, 6],
            [0, 4, 5],
            [0, 5, 1],
            [1, 5, 6],
            [1, 6, 2],
            [2, 6, 7],
            [2, 7, 3],
            [3, 7, 4],
            [3, 4, 0],
        ],
        dtype=np.int32,
    )
    return vertices, triangles


def test_recast_builder_reports_empty_poly_mesh_as_failure() -> None:
    builder = RecastNavMeshBuilderComponent()
    builder.cell_size = 0.3
    builder.cell_height = 0.2
    builder.agent_height = 2.0
    builder.agent_radius = 0.5
    builder.agent_max_climb = 0.4
    builder.min_region_area = 8
    builder.merge_region_area = 20
    builder.build_detail_mesh = True

    vertices, triangles = _unit_cube_geometry()
    result = builder.build(vertices, triangles)

    assert not result.success
    assert result.poly_count() == 0
    assert "empty polygon mesh" in result.error
