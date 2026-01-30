// tc_scene.h - Scene (owns entity pool + component scheduler)
#ifndef TC_SCENE_H
#define TC_SCENE_H

#include "tc_types.h"
#include "tc_scene_pool.h"
#include "tc_entity_pool.h"
#include "tc_component.h"
#include "tc_scene_lighting.h"
#include "tc_scene_skybox.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Scene Mode
// ============================================================================

typedef enum tc_scene_mode {
    TC_SCENE_MODE_INACTIVE = 0,  // Loaded but not updated
    TC_SCENE_MODE_STOP = 1,      // Editor update (gizmos, selection)
    TC_SCENE_MODE_PLAY = 2       // Full simulation
} tc_scene_mode;

// ============================================================================
// Scene Creation / Destruction
// ============================================================================

// Create a new scene (allocates from global pool)
TC_API tc_scene_handle tc_scene_new(void);

// Create a new scene with a name
TC_API tc_scene_handle tc_scene_new_named(const char* name);

// Free a scene (returns to pool)
TC_API void tc_scene_free(tc_scene_handle h);

// Check if scene handle is valid and alive
TC_API bool tc_scene_alive(tc_scene_handle h);

// Get the entity pool owned by this scene
TC_API tc_entity_pool* tc_scene_entity_pool(tc_scene_handle h);

// ============================================================================
// Component Registration
// ============================================================================

// Register component for lifecycle management
// Adds to pending_start if not started
// Adds to update_list/fixed_update_list based on flags
TC_API void tc_scene_register_component(tc_scene_handle h, tc_component* c);

// Unregister component from lifecycle management
TC_API void tc_scene_unregister_component(tc_scene_handle h, tc_component* c);

// ============================================================================
// Update Loop
// ============================================================================

// Main update - executes full update cycle:
// 1. Process pending_start (call start() on enabled components)
// 2. Fixed update loop (accumulator-based)
// 3. Regular update
TC_API void tc_scene_update(tc_scene_handle h, double dt);

// Editor update - only updates components with active_in_editor=true
TC_API void tc_scene_editor_update(tc_scene_handle h, double dt);

// Before render - call before_render() on all components that implement it
// Should be called once per frame, before rendering begins
TC_API void tc_scene_before_render(tc_scene_handle h);

// Notify all components that scene started in editor mode
TC_API void tc_scene_notify_editor_start(tc_scene_handle h);

// Notify all components that scene is becoming inactive
TC_API void tc_scene_notify_scene_inactive(tc_scene_handle h);

// Notify all components that scene is becoming active
TC_API void tc_scene_notify_scene_active(tc_scene_handle h);

// ============================================================================
// Fixed Timestep Configuration
// ============================================================================

TC_API double tc_scene_fixed_timestep(tc_scene_handle h);
TC_API void tc_scene_set_fixed_timestep(tc_scene_handle h, double dt);

TC_API double tc_scene_accumulated_time(tc_scene_handle h);
TC_API void tc_scene_reset_accumulated_time(tc_scene_handle h);

// ============================================================================
// Component Queries
// ============================================================================

TC_API size_t tc_scene_entity_count(tc_scene_handle h);
TC_API size_t tc_scene_pending_start_count(tc_scene_handle h);
TC_API size_t tc_scene_update_list_count(tc_scene_handle h);
TC_API size_t tc_scene_fixed_update_list_count(tc_scene_handle h);

// ============================================================================
// Python Wrapper Access
// ============================================================================

// Set/get Python Scene wrapper for callbacks from C to Python
TC_API void tc_scene_set_py_wrapper(tc_scene_handle h, void* py_wrapper);
TC_API void* tc_scene_get_py_wrapper(tc_scene_handle h);

// ============================================================================
// Entity Queries
// ============================================================================

// Find entity by name in scene's pool
// Returns invalid entity id if not found
TC_API tc_entity_id tc_scene_find_entity_by_name(tc_scene_handle h, const char* name);

// ============================================================================
// Component Type Lists (intrusive linked lists by type_name)
// ============================================================================

// Get first component of given type (head of intrusive list)
// Returns NULL if no components of that type
TC_API tc_component* tc_scene_first_component_of_type(tc_scene_handle h, const char* type_name);

// Iterate: use component->type_next to get next component of same type
// Example:
//   for (tc_component* c = tc_scene_first_component_of_type(h, "LightComponent");
//        c != NULL; c = c->type_next) { ... }

// Count components of a type (O(n) - iterates the list)
TC_API size_t tc_scene_count_components_of_type(tc_scene_handle h, const char* type_name);

// Callback for iterating components. Return true to continue, false to stop.
typedef bool (*tc_component_iter_fn)(tc_component* c, void* user_data);

// Iterate all components of a type with callback (no allocations)
TC_API void tc_scene_foreach_component_of_type(
    tc_scene_handle h,
    const char* type_name,
    tc_component_iter_fn callback,
    void* user_data
);

// ============================================================================
// Drawable Component Iteration
// ============================================================================

// Filter flags for drawable iteration
typedef enum tc_drawable_filter_flags {
    TC_DRAWABLE_FILTER_NONE = 0,
    TC_DRAWABLE_FILTER_ENABLED = 1 << 0,        // Only enabled components
    TC_DRAWABLE_FILTER_VISIBLE = 1 << 1,        // Only visible entities
    TC_DRAWABLE_FILTER_ENTITY_ENABLED = 1 << 2, // Only enabled entities
    TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR = 1 << 3 // Only components with active_in_editor=true
} tc_drawable_filter_flags;

// Iterate all drawable components in scene with optional filtering
// filter_flags: combination of tc_drawable_filter_flags
// layer_mask: bitmask for layer filtering (0 = all layers)
TC_API void tc_scene_foreach_drawable(
    tc_scene_handle h,
    tc_component_iter_fn callback,
    void* user_data,
    int filter_flags,
    uint64_t layer_mask
);

// ============================================================================
// Input Handler Component Iteration
// ============================================================================

// Iterate all input handler components in scene
// filter_flags: combination of tc_drawable_filter_flags (reused for consistency)
TC_API void tc_scene_foreach_input_handler(
    tc_scene_handle h,
    tc_component_iter_fn callback,
    void* user_data,
    int filter_flags
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
    tc_scene_handle h,
    size_t* out_count
);

// ============================================================================
// Scene Mode
// ============================================================================

// Get/set scene mode (INACTIVE, STOP, PLAY)
TC_API tc_scene_mode tc_scene_get_mode(tc_scene_handle h);
TC_API void tc_scene_set_mode(tc_scene_handle h, tc_scene_mode mode);

// ============================================================================
// Scene Name (delegates to pool)
// ============================================================================

TC_API const char* tc_scene_get_name(tc_scene_handle h);
TC_API void tc_scene_set_name(tc_scene_handle h, const char* name);

// ============================================================================
// Collision World
// ============================================================================

// Get the collision world (C++ CollisionWorld*)
TC_API void* tc_scene_get_collision_world(tc_scene_handle h);

// Set the collision world (called from C++ TcScene)
TC_API void tc_scene_set_collision_world(tc_scene_handle h, void* cw);

// ============================================================================
// Skybox
// ============================================================================

TC_API tc_scene_skybox* tc_scene_get_skybox(tc_scene_handle h);
TC_API void tc_scene_set_skybox_type(tc_scene_handle h, int type);
TC_API int tc_scene_get_skybox_type(tc_scene_handle h);
TC_API void tc_scene_set_skybox_color(tc_scene_handle h, float r, float g, float b);
TC_API void tc_scene_get_skybox_color(tc_scene_handle h, float* r, float* g, float* b);
TC_API void tc_scene_set_skybox_top_color(tc_scene_handle h, float r, float g, float b);
TC_API void tc_scene_get_skybox_top_color(tc_scene_handle h, float* r, float* g, float* b);
TC_API void tc_scene_set_skybox_bottom_color(tc_scene_handle h, float r, float g, float b);
TC_API void tc_scene_get_skybox_bottom_color(tc_scene_handle h, float* r, float* g, float* b);
TC_API void tc_scene_set_skybox_mesh(tc_scene_handle h, struct tc_mesh* mesh);
TC_API struct tc_mesh* tc_scene_get_skybox_mesh(tc_scene_handle h);
TC_API void tc_scene_set_skybox_material(tc_scene_handle h, struct tc_material* material);
TC_API struct tc_material* tc_scene_get_skybox_material(tc_scene_handle h);

// ============================================================================
// Lighting
// ============================================================================

TC_API tc_scene_lighting* tc_scene_get_lighting(tc_scene_handle h);
TC_API void tc_scene_set_ambient(tc_scene_handle h, float r, float g, float b, float intensity);
TC_API void tc_scene_set_shadow_settings(tc_scene_handle h, int method, float softness, float bias);

#ifdef __cplusplus
}
#endif

#endif // TC_SCENE_H
