#pragma once

#include <termin/navmesh/termin_navmesh_components_api.hpp>

#include "core/tc_scene.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef void tc_pathfinding_world;

TERMIN_NAVMESH_COMPONENTS_API void tc_pathfinding_world_extension_init(void);
TERMIN_NAVMESH_COMPONENTS_API tc_pathfinding_world* tc_pathfinding_world_get_scene(tc_scene_handle scene);
TERMIN_NAVMESH_COMPONENTS_API tc_pathfinding_world* tc_pathfinding_world_ensure_scene(tc_scene_handle scene);

#ifdef __cplusplus
}
#endif
