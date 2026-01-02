// tc_scene_registry.h - Global scene registry
#pragma once

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Lifecycle (called from tc_init/tc_shutdown)
// ============================================================================

TC_API void tc_scene_registry_init(void);
TC_API void tc_scene_registry_shutdown(void);

// ============================================================================
// Scene registration (called automatically by tc_scene_new/tc_scene_free)
// ============================================================================

// Register scene in registry, assigns unique ID
// Returns scene ID (>= 0) or -1 on error
TC_API int tc_scene_registry_add(tc_scene* scene, const char* name);

// Unregister scene from registry
TC_API void tc_scene_registry_remove(tc_scene* scene);

// Get scene name
TC_API const char* tc_scene_registry_get_name(const tc_scene* scene);

// Set scene name
TC_API void tc_scene_registry_set_name(tc_scene* scene, const char* name);

// ============================================================================
// Queries
// ============================================================================

// Get number of registered scenes
TC_API size_t tc_scene_registry_count(void);

// ============================================================================
// Scene info for debugging
// ============================================================================

typedef struct tc_scene_info {
    int id;                    // Scene ID in registry
    const char* name;          // Scene name
    size_t entity_count;       // Number of entities
    size_t pending_count;      // Pending start components
    size_t update_count;       // Update list count
    size_t fixed_update_count; // Fixed update list count
} tc_scene_info;

// Get info for all scenes (caller must free() returned array)
// Returns NULL if no scenes, sets *count to number of entries
TC_API tc_scene_info* tc_scene_registry_get_all_info(size_t* count);

// ============================================================================
// Iteration
// ============================================================================

// Iterator callback: return true to continue, false to stop
typedef bool (*tc_scene_iter_fn)(tc_scene* scene, int id, void* user_data);

// Iterate over all scenes
TC_API void tc_scene_registry_foreach(tc_scene_iter_fn callback, void* user_data);

// ============================================================================
// Entity enumeration for a scene
// ============================================================================

typedef struct tc_scene_entity_info {
    const char* name;
    const char* uuid;
    size_t component_count;
    bool visible;
    bool active;
} tc_scene_entity_info;

// Get entity info for a scene by scene ID
// Returns array of tc_scene_entity_info (caller must free)
// Sets *count to number of entities
TC_API tc_scene_entity_info* tc_scene_get_entities(int scene_id, size_t* count);

// ============================================================================
// Component type enumeration for a scene
// ============================================================================

typedef struct tc_scene_component_type_info {
    const char* type_name;
    size_t count;
} tc_scene_component_type_info;

// Get component type counts for a scene by scene ID
// Returns array of tc_scene_component_type_info (caller must free)
// Sets *count to number of types with count > 0
TC_API tc_scene_component_type_info* tc_scene_get_component_types(int scene_id, size_t* count);

#ifdef __cplusplus
}
#endif
