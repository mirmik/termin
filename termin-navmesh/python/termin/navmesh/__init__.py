"""NavMesh public package facade.

This package exposes the Recast-backed C++ NavMesh builder and a pure-Python
algorithmic stack (region growing, triangulation, pathfinding, etc.) as
submodules.

Top-level ``import termin.navmesh`` is intentionally lightweight: native Recast
bindings and higher-level builder/display modules are loaded only when their
public names are requested.
"""

from __future__ import annotations

_DATA_EXPORT_NAMES = frozenset(
    {
        "NavMesh",
        "NavMeshConfig",
        "NavPolygon",
        "Portal",
    }
)

_NATIVE_EXPORT_NAMES = frozenset(
    {
        "DetourClosestPointResult",
        "DetourPathfindingWorldComponent",
        "DetourRaycastResult",
        "NavMeshKeeperComponent",
        "OffMeshLinkComponent",
        "OffMeshLinkType",
        "RecastNavMeshBuilderComponent",
        "RecastBuildResult",
        "TcNavMesh",
        "clear_navmesh_load_callback",
        "declare_navmesh_asset",
        "set_navmesh_load_callback",
        "set_detour_navmesh_asset_data",
    }
)


def _load_data_exports() -> dict[str, object]:
    from termin.navmesh.types import NavMesh, NavMeshConfig, NavPolygon, Portal

    exports = {
        "NavMesh": NavMesh,
        "NavMeshConfig": NavMeshConfig,
        "NavPolygon": NavPolygon,
        "Portal": Portal,
    }
    globals().update(exports)
    return exports


def _load_native_exports() -> dict[str, object]:
    try:
        from termin_nanobind.runtime import preload_sdk_libs

        # _navmesh_native pulls in entity_lib, navmesh_lib, render_lib, Recast.
        # Preloading entity_lib resolves the whole chain via SDK RPATH.
        preload_sdk_libs("entity_lib")

        from termin.navmesh._navmesh_native import (
            DetourClosestPointResult,
            DetourPathfindingWorldComponent,
            DetourRaycastResult,
            NavMeshKeeperComponent,
            OffMeshLinkComponent,
            OffMeshLinkType,
            RecastNavMeshBuilderComponent,
            RecastBuildResult,
            TcNavMesh,
            clear_navmesh_load_callback,
            declare_navmesh_asset,
            set_detour_navmesh_asset_data,
            set_navmesh_load_callback,
        )
    except ImportError as exc:
        try:
            from tcbase import log

            log.error("[termin.navmesh] native bindings are unavailable")
        except ImportError:
            pass
        raise ImportError("termin.navmesh native bindings are unavailable") from exc

    exports = {
        "DetourClosestPointResult": DetourClosestPointResult,
        "DetourPathfindingWorldComponent": DetourPathfindingWorldComponent,
        "DetourRaycastResult": DetourRaycastResult,
        "NavMeshKeeperComponent": NavMeshKeeperComponent,
        "OffMeshLinkComponent": OffMeshLinkComponent,
        "OffMeshLinkType": OffMeshLinkType,
        "RecastNavMeshBuilderComponent": RecastNavMeshBuilderComponent,
        "RecastBuildResult": RecastBuildResult,
        "TcNavMesh": TcNavMesh,
        "clear_navmesh_load_callback": clear_navmesh_load_callback,
        "declare_navmesh_asset": declare_navmesh_asset,
        "set_navmesh_load_callback": set_navmesh_load_callback,
        "set_detour_navmesh_asset_data": set_detour_navmesh_asset_data,
    }
    globals().update(exports)
    return exports


def __getattr__(name: str):
    if name == "NavMeshAsset":
        from termin.default_assets.navmesh.asset import NavMeshAsset

        globals()["NavMeshAsset"] = NavMeshAsset
        return NavMeshAsset

    if name == "NavMeshHandle":
        from termin.default_assets.navmesh.handle import NavMeshHandle

        globals()["NavMeshHandle"] = NavMeshHandle
        return NavMeshHandle

    if name == "PolygonBuilder":
        from termin.navmesh.polygon_builder import PolygonBuilder

        globals()["PolygonBuilder"] = PolygonBuilder
        return PolygonBuilder

    if name in _DATA_EXPORT_NAMES:
        return _load_data_exports()[name]

    if name in _NATIVE_EXPORT_NAMES:
        return _load_native_exports()[name]

    raise AttributeError(f"module 'termin.navmesh' has no attribute {name!r}")


__all__ = [
    "NavMesh",
    "NavMeshConfig",
    "NavPolygon",
    "PolygonBuilder",
    "Portal",
    "DetourClosestPointResult",
    "DetourPathfindingWorldComponent",
    "DetourRaycastResult",
    "NavMeshKeeperComponent",
    "OffMeshLinkComponent",
    "OffMeshLinkType",
    "RecastNavMeshBuilderComponent",
    "RecastBuildResult",
    "TcNavMesh",
    "clear_navmesh_load_callback",
    "declare_navmesh_asset",
    "set_navmesh_load_callback",
    "set_detour_navmesh_asset_data",
]
