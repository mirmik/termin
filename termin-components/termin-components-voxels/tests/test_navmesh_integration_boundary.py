import ast
from pathlib import Path

import numpy as np

from termin.navmesh.ribbon_geometry import build_line_ribbon


REPO_ROOT = Path(__file__).resolve().parents[3]
VOXEL_COMPONENTS_ROOT = REPO_ROOT / "termin-components" / "termin-components-voxels"
NAVMESH_ROOT = REPO_ROOT / "termin-navmesh"


def _install_requires(package_root: Path) -> set[str]:
    tree = ast.parse((package_root / "setup.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "install_requires":
                continue
            assert isinstance(keyword.value, (ast.List, ast.Tuple))
            return {
                element.value
                for element in keyword.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            }
    raise AssertionError(f"{package_root / 'setup.py'} has no literal install_requires")


def test_navmesh_integration_dependency_points_from_voxel_components() -> None:
    assert "termin-navmesh" in _install_requires(VOXEL_COMPONENTS_ROOT)
    assert "termin-components-voxels" not in _install_requires(NAVMESH_ROOT)


def test_voxel_components_do_not_import_private_navmesh_symbols() -> None:
    violations = []
    source_root = VOXEL_COMPONENTS_ROOT / "python"
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if node.module.startswith("termin.navmesh"):
                for alias in node.names:
                    if alias.name.startswith("_"):
                        violations.append(
                            f"{path.relative_to(VOXEL_COMPONENTS_ROOT)}: "
                            f"{node.module}.{alias.name}"
                        )
    assert violations == []


def test_public_line_ribbon_geometry_is_deterministic() -> None:
    vertices, triangles = build_line_ribbon(
        [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0)],
        0.5,
        np.array([0.0, 0.0, 1.0], dtype=np.float32),
    )

    np.testing.assert_allclose(
        vertices,
        np.array(
            [
                [0.0, -0.25, 0.0],
                [0.0, 0.25, 0.0],
                [2.0, -0.25, 0.0],
                [2.0, 0.25, 0.0],
            ],
            dtype=np.float32,
        ),
    )
    np.testing.assert_array_equal(
        triangles,
        np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int32),
    )
