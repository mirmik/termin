"""Tests for the public termin.navmesh package facade."""

from __future__ import annotations

import subprocess
import sys

import pytest


def _run_clean_import_probe(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )


def test_navmesh_top_level_import_is_lightweight():
    result = _run_clean_import_probe(
        "import sys\n"
        "import termin.navmesh\n"
        "assert 'termin.navmesh._navmesh_native' not in sys.modules\n"
    )

    assert result.returncode == 0, result.stderr


def test_navmesh_data_exports_are_lightweight():
    result = _run_clean_import_probe(
        "import sys\n"
        "from termin.navmesh import NavMeshConfig\n"
        "assert NavMeshConfig.__name__ == 'NavMeshConfig'\n"
        "assert 'termin.navmesh._navmesh_native' not in sys.modules\n"
    )

    assert result.returncode == 0, result.stderr


def test_navmesh_polygon_builder_is_public_export():
    result = _run_clean_import_probe(
        "import sys\n"
        "try:\n"
        "    from termin.navmesh import PolygonBuilder\n"
        "except ImportError as exc:\n"
        "    if 'Cannot find libtermin_base' in str(exc):\n"
        "        print('PolygonBuilder import needs a built Termin SDK for tcbase')\n"
        "        raise SystemExit(77)\n"
        "    raise\n"
        "assert PolygonBuilder.__name__ == 'PolygonBuilder'\n"
        "assert 'termin.navmesh._navmesh_native' not in sys.modules\n"
    )

    if result.returncode == 77:
        pytest.skip(result.stdout.strip())
    assert result.returncode == 0, result.stderr
