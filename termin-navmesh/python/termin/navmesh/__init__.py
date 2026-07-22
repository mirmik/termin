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
        "DetourNavMeshTileBuildResult",
        "DetourPathfindingWorldComponent",
        "DetourQuerySession",
        "DetourRaycastResult",
        "MeshSource",
        "NavMeshKeeperComponent",
        "PathfindingWorld",
        "PathfindingWorldCandidate",
        "PathfindingWorldPointCandidate",
        "PathfindingWorldPathResult",
        "OffMeshLinkComponent",
        "OffMeshLinkType",
        "RecastNavMeshBuilderComponent",
        "RecastBuildResult",
        "NavMeshHandle",
        "TcNavMesh",
        "clear_navmesh_load_callback",
        "declare_navmesh_asset",
        "navmesh_bake_frame_from_pose",
        "navmesh_bake_visitor_registration_owner",
        "navmesh_bake_to_world_point",
        "navmesh_world_to_bake_point",
        "set_navmesh_bake_visitor_registration_owner",
        "set_navmesh_load_callback",
        "set_detour_navmesh_asset_data",
        "tc_navmesh_get_all_info",
        "unregister_navmesh_bake_visitor_owner",
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

        # _navmesh_native is owned by termin-navmesh and pulls in the
        # Recast-backed component library through SDK RPATH.
        preload_sdk_libs("termin_navmesh_components")

        from termin.navmesh._navmesh_native import (
            DetourClosestPointResult,
            DetourNavMeshTileBuildResult,
            DetourPathfindingWorldComponent,
            DetourQuerySession,
            DetourRaycastResult,
            MeshSource,
            NavMeshKeeperComponent,
            PathfindingWorld,
            PathfindingWorldCandidate,
            PathfindingWorldPointCandidate,
            PathfindingWorldPathResult,
            OffMeshLinkComponent,
            OffMeshLinkType,
            RecastNavMeshBuilderComponent,
            RecastBuildResult,
            NavMeshHandle,
            TcNavMesh,
            clear_navmesh_load_callback,
            declare_navmesh_asset,
            navmesh_bake_frame_from_pose,
            navmesh_bake_visitor_registration_owner,
            navmesh_bake_to_world_point,
            navmesh_world_to_bake_point,
            set_detour_navmesh_asset_data,
            tc_navmesh_get_all_info,
            set_navmesh_bake_visitor_registration_owner,
            set_navmesh_load_callback,
            unregister_navmesh_bake_visitor_owner,
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
        "DetourNavMeshTileBuildResult": DetourNavMeshTileBuildResult,
        "DetourPathfindingWorldComponent": DetourPathfindingWorldComponent,
        "DetourQuerySession": DetourQuerySession,
        "DetourRaycastResult": DetourRaycastResult,
        "MeshSource": MeshSource,
        "NavMeshKeeperComponent": NavMeshKeeperComponent,
        "PathfindingWorld": PathfindingWorld,
        "PathfindingWorldCandidate": PathfindingWorldCandidate,
        "PathfindingWorldPointCandidate": PathfindingWorldPointCandidate,
        "PathfindingWorldPathResult": PathfindingWorldPathResult,
        "OffMeshLinkComponent": OffMeshLinkComponent,
        "OffMeshLinkType": OffMeshLinkType,
        "RecastNavMeshBuilderComponent": RecastNavMeshBuilderComponent,
        "RecastBuildResult": RecastBuildResult,
        "NavMeshHandle": NavMeshHandle,
        "TcNavMesh": TcNavMesh,
        "clear_navmesh_load_callback": clear_navmesh_load_callback,
        "declare_navmesh_asset": declare_navmesh_asset,
        "navmesh_bake_frame_from_pose": navmesh_bake_frame_from_pose,
        "navmesh_bake_visitor_registration_owner": navmesh_bake_visitor_registration_owner,
        "navmesh_bake_to_world_point": navmesh_bake_to_world_point,
        "navmesh_world_to_bake_point": navmesh_world_to_bake_point,
        "set_navmesh_bake_visitor_registration_owner": set_navmesh_bake_visitor_registration_owner,
        "set_navmesh_load_callback": set_navmesh_load_callback,
        "set_detour_navmesh_asset_data": set_detour_navmesh_asset_data,
        "tc_navmesh_get_all_info": tc_navmesh_get_all_info,
        "unregister_navmesh_bake_visitor_owner": unregister_navmesh_bake_visitor_owner,
    }
    globals().update(exports)
    return exports


def __getattr__(name: str):
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
    "DetourNavMeshTileBuildResult",
    "DetourPathfindingWorldComponent",
    "DetourQuerySession",
    "DetourRaycastResult",
    "MeshSource",
    "NavMeshKeeperComponent",
    "PathfindingWorld",
    "PathfindingWorldCandidate",
    "PathfindingWorldPointCandidate",
    "PathfindingWorldPathResult",
    "OffMeshLinkComponent",
    "OffMeshLinkType",
    "RecastNavMeshBuilderComponent",
    "RecastBuildResult",
    "NavMeshHandle",
    "TcNavMesh",
    "clear_navmesh_load_callback",
    "declare_navmesh_asset",
    "navmesh_bake_frame_from_pose",
    "navmesh_bake_visitor_registration_owner",
    "navmesh_bake_to_world_point",
    "navmesh_world_to_bake_point",
    "set_navmesh_bake_visitor_registration_owner",
    "set_navmesh_load_callback",
    "set_detour_navmesh_asset_data",
    "tc_navmesh_get_all_info",
    "unregister_navmesh_bake_visitor_owner",
]
