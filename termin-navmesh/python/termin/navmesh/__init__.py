"""NavMesh Python bindings (thin facade over _navmesh_native).

This package exposes the Recast-backed C++ NavMesh builder and a pure-Python
algorithmic stack (region growing, triangulation, pathfinding, etc.) as
submodules.

Top-level __init__ only loads the native module and its type registrations.
Algorithmic submodules (pathfinding, builder_component, display_component,
...) are imported on demand via ``from termin.navmesh.<module> import ...``
because they depend on higher-level termin Python modules that may not be
available in all deployments.
"""

from termin_nanobind.runtime import preload_sdk_libs

# _navmesh_native pulls in entity_lib, navmesh_lib, render_lib, Recast.
# Preloading entity_lib resolves the whole chain via SDK RPATH.
preload_sdk_libs("entity_lib")

from termin.navmesh._navmesh_native import (
    RecastNavMeshBuilderComponent as _RecastNavMeshBuilderComponent,
    RecastBuildResult,
)

# Keep public name so `termin.navmesh.RecastNavMeshBuilderComponent` works.
RecastNavMeshBuilderComponent = _RecastNavMeshBuilderComponent

__all__ = [
    "RecastNavMeshBuilderComponent",
    "RecastBuildResult",
]
