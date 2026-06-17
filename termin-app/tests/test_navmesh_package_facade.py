"""Tests for the public termin.navmesh package facade."""

from __future__ import annotations

import sys

import pytest


def _native_module_loaded() -> bool:
    return "termin.navmesh._navmesh_native" in sys.modules


def test_navmesh_top_level_import_is_lightweight():
    import termin.navmesh  # noqa: F401

    assert not _native_module_loaded()


def test_navmesh_data_exports_are_lightweight():
    from termin.navmesh import NavMeshConfig

    assert NavMeshConfig.__name__ == "NavMeshConfig"
    assert not _native_module_loaded()


def test_navmesh_polygon_builder_is_public_export():
    try:
        from termin.navmesh import PolygonBuilder
    except ImportError as exc:
        if "Cannot find libtermin_base" in str(exc):
            pytest.skip("PolygonBuilder import needs a built Termin SDK for tcbase")
        raise

    assert PolygonBuilder.__name__ == "PolygonBuilder"
    assert not _native_module_loaded()
