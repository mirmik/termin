"""Compatibility import path for the canonical navmesh runtime resource."""

from __future__ import annotations

from termin.navmesh._navmesh_native import TcNavMesh

NavMeshHandle = TcNavMesh

__all__ = ["NavMeshHandle"]
