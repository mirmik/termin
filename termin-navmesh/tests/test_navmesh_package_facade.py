"""Tests for the public termin.navmesh package facade."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _subprocess_env() -> dict[str, str]:
    return {
        **os.environ,
        "TERMIN_SDK": str(REPO_ROOT / "sdk"),
    }


def _run_clean_import_probe(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=_subprocess_env(),
        check=False,
        capture_output=True,
        text=True,
    )


def test_navmesh_top_level_import_is_lightweight() -> None:
    result = _run_clean_import_probe(
        "import sys\n"
        "import termin.navmesh\n"
        "assert 'termin.navmesh._navmesh_native' not in sys.modules\n"
        "assert 'termin.voxels._voxels_native' not in sys.modules\n"
        "assert 'termin.render' not in sys.modules\n"
    )

    assert result.returncode == 0, result.stderr


def test_navmesh_data_exports_are_lightweight() -> None:
    result = _run_clean_import_probe(
        "import sys\n"
        "from termin.navmesh import NavMeshConfig\n"
        "assert NavMeshConfig.__name__ == 'NavMeshConfig'\n"
        "assert 'termin.navmesh._navmesh_native' not in sys.modules\n"
        "assert 'termin.voxels._voxels_native' not in sys.modules\n"
        "assert 'termin.render' not in sys.modules\n"
    )

    assert result.returncode == 0, result.stderr


def test_navmesh_polygon_builder_export_does_not_load_native_modules() -> None:
    result = _run_clean_import_probe(
        "import sys\n"
        "from termin.navmesh import PolygonBuilder\n"
        "assert PolygonBuilder.__name__ == 'PolygonBuilder'\n"
        "assert 'termin.navmesh._navmesh_native' not in sys.modules\n"
        "assert 'termin.voxels._voxels_native' not in sys.modules\n"
        "assert 'termin.render' not in sys.modules\n"
    )

    assert result.returncode == 0, result.stderr


def test_navmesh_native_exports_load_native_module_separately() -> None:
    result = _run_clean_import_probe(
        "import sys\n"
        "try:\n"
        "    from termin.navmesh import RecastNavMeshBuilderComponent\n"
        "except ImportError as exc:\n"
        "    print(str(exc))\n"
        "    raise SystemExit(77)\n"
        "assert RecastNavMeshBuilderComponent.__name__ == 'RecastNavMeshBuilderComponent'\n"
        "assert 'termin.navmesh._navmesh_native' in sys.modules\n"
    )

    if result.returncode == 77:
        pytest.skip(result.stdout.strip())
    assert result.returncode == 0, result.stderr
