// tc_scene.h - Scene (entity world + component scheduler)
//
// Manages:
// - Entity list sorted by priority
// - Component lifecycle (pending_start, update_list, fixed_update_list)
// - Update loop execution (start -> fixed_update -> update)
//
#ifndef TC_SCENE_H
#define TC_SCENE_H

#include "tc_types.h"
#include "tc_entity.h"
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
// Entity Management
// ============================================================================

// Add entity to scene (sorted by priority)
// Calls on_added_to_scene on entity and registers all components
TC_API void tc_scene_add_entity(tc_scene* s, tc_entity* e);

// Remove entity from scene
// Calls on_removed_from_scene on entity and unregisters all components
TC_API void tc_scene_remove_entity(tc_scene* s, tc_entity* e);

// Get entity count
TC_API size_t tc_scene_entity_count(const tc_scene* s);

// Get entity by index
TC_API tc_entity* tc_scene_get_entity(tc_scene* s, size_t index);

// Find entity by UUID (searches recursively through hierarchy)
TC_API tc_entity* tc_scene_find_by_uuid(tc_scene* s, const char* uuid);

// Find entity by runtime ID
TC_API tc_entity* tc_scene_find_by_runtime_id(tc_scene* s, uint64_t runtime_id);

// ============================================================================
// Component Registration
// ============================================================================

// Register component for lifecycle management
// Called automatically when entity is added to scene
// Adds to update_list/fixed_update_list based on has_update/has_fixed_update
// Adds to pending_start if not started
TC_API void tc_scene_register_component(tc_scene* s, tc_component* c);

// Unregister component from lifecycle management
// Called automatically when entity is removed from scene
TC_API void tc_scene_unregister_component(tc_scene* s, tc_component* c);

// ============================================================================
// Update Loop
// ============================================================================

// Main update - executes full update cycle:
// 1. Process pending_start (call start() on enabled components)
// 2. Fixed update loop (accumulator-based, calls fixed_update at fixed timestep)
// 3. Regular update (calls update() with full dt)
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

// Get counts
TC_API size_t tc_scene_pending_start_count(const tc_scene* s);
TC_API size_t tc_scene_update_list_count(const tc_scene* s);
TC_API size_t tc_scene_fixed_update_list_count(const tc_scene* s);

// Find first component by type name
TC_API tc_component* tc_scene_find_component(tc_scene* s, const char* type_name);

// ============================================================================
// Callbacks (for Python/C++ integration)
// ============================================================================

// Callback types
typedef void (*tc_scene_entity_callback)(tc_scene* s, tc_entity* e, void* user_data);
typedef void (*tc_scene_component_callback)(tc_scene* s, tc_component* c, void* user_data);

// Set callbacks for entity add/remove events
TC_API void tc_scene_set_on_entity_added(tc_scene* s, tc_scene_entity_callback cb, void* user_data);
TC_API void tc_scene_set_on_entity_removed(tc_scene* s, tc_scene_entity_callback cb, void* user_data);

// Set callbacks for component register/unregister events
TC_API void tc_scene_set_on_component_registered(tc_scene* s, tc_scene_component_callback cb, void* user_data);
TC_API void tc_scene_set_on_component_unregistered(tc_scene* s, tc_scene_component_callback cb, void* user_data);

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_H
