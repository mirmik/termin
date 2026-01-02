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

// ============================================================================
// Python Wrapper Access
// ============================================================================

// Set/get Python Scene wrapper for callbacks from C to Python
TC_API void tc_scene_set_py_wrapper(tc_scene* s, void* py_wrapper);
TC_API void* tc_scene_get_py_wrapper(tc_scene* s);

// ============================================================================
// Component Type Lists (intrusive linked lists by type_name)
// ============================================================================

// Get first component of given type (head of intrusive list)
// Returns NULL if no components of that type
TC_API tc_component* tc_scene_first_component_of_type(tc_scene* s, const char* type_name);

// Iterate: use component->type_next to get next component of same type
// Example:
//   for (tc_component* c = tc_scene_first_component_of_type(s, "LightComponent");
//        c != NULL; c = c->type_next) { ... }

// Count components of a type (O(n) - iterates the list)
TC_API size_t tc_scene_count_components_of_type(tc_scene* s, const char* type_name);

// Callback for iterating components. Return true to continue, false to stop.
typedef bool (*tc_component_iter_fn)(tc_component* c, void* user_data);

// Iterate all components of a type with callback (no allocations)
TC_API void tc_scene_foreach_component_of_type(
    tc_scene* s,
    const char* type_name,
    tc_component_iter_fn callback,
    void* user_data
);

// ============================================================================
// Component Type Enumeration
// ============================================================================

// Info for one component type in a scene
typedef struct tc_scene_component_type {
    const char* type_name;  // Interned string, valid while scene exists
    size_t count;           // Number of components of this type
} tc_scene_component_type;

// Get all component types present in scene with their counts
// Returns array of tc_scene_component_type (caller must free)
// Sets *out_count to number of types
TC_API tc_scene_component_type* tc_scene_get_all_component_types(
    tc_scene* s,
    size_t* out_count
);

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_H
