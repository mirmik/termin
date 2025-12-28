// tc_scene.h - Scene (owns entity pool + component scheduler)
#ifndef TC_SCENE_H
#define TC_SCENE_H

#include "tc_types.h"
#include "tc_entity_pool.h"
#include "tc_component.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Scene Creation / Destruction
// ============================================================================

TC_API tc_scene* tc_scene_new(void);
TC_API void tc_scene_free(tc_scene* s);

// Get the entity pool owned by this scene
TC_API tc_entity_pool* tc_scene_entity_pool(tc_scene* s);

// ============================================================================
// Component Registration
// ============================================================================

// Register component for lifecycle management
// Adds to pending_start if not started
// Adds to update_list/fixed_update_list based on flags
TC_API void tc_scene_register_component(tc_scene* s, tc_component* c);

// Unregister component from lifecycle management
TC_API void tc_scene_unregister_component(tc_scene* s, tc_component* c);

// ============================================================================
// Update Loop
// ============================================================================

// Main update - executes full update cycle:
// 1. Process pending_start (call start() on enabled components)
// 2. Fixed update loop (accumulator-based)
// 3. Regular update
TC_API void tc_scene_update(tc_scene* s, double dt);

// Editor update - only updates components with active_in_editor=true
TC_API void tc_scene_editor_update(tc_scene* s, double dt);

// ============================================================================
// Fixed Timestep Configuration
// ============================================================================

TC_API double tc_scene_fixed_timestep(const tc_scene* s);
TC_API void tc_scene_set_fixed_timestep(tc_scene* s, double dt);

TC_API double tc_scene_accumulated_time(const tc_scene* s);
TC_API void tc_scene_reset_accumulated_time(tc_scene* s);

// ============================================================================
// Component Queries
// ============================================================================

TC_API size_t tc_scene_entity_count(const tc_scene* s);
TC_API size_t tc_scene_pending_start_count(const tc_scene* s);
TC_API size_t tc_scene_update_list_count(const tc_scene* s);
TC_API size_t tc_scene_fixed_update_list_count(const tc_scene* s);

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_H
