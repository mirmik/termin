"""Compatibility re-export for navmesh assets.

Canonical implementation lives in :mod:`termin.default_assets.navmesh.asset`.
"""

from termin.default_assets.navmesh.asset import DetourNavMeshData, DetourNavMeshTileData, NavMeshAsset

__all__ = ["DetourNavMeshData", "DetourNavMeshTileData", "NavMeshAsset"]
