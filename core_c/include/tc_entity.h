// tc_entity.h - Entity (game object container)
#ifndef TC_ENTITY_H
#define TC_ENTITY_H

#include "tc_types.h"
#include "tc_transform.h"
#include "tc_component.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Entity Creation / Destruction
// ============================================================================

TC_API tc_entity* tc_entity_new(const char* name);
TC_API tc_entity* tc_entity_new_with_uuid(const char* name, const char* uuid);
TC_API tc_entity* tc_entity_new_with_pose(tc_general_pose3 pose, const char* name);
TC_API void tc_entity_free(tc_entity* e);

// ============================================================================
// Identity
// ============================================================================

TC_API const char* tc_entity_uuid(const tc_entity* e);
TC_API uint64_t tc_entity_runtime_id(const tc_entity* e);
TC_API uint32_t tc_entity_pick_id(tc_entity* e);  // Lazily computed

TC_API const char* tc_entity_name(const tc_entity* e);
TC_API void tc_entity_set_name(tc_entity* e, const char* name);

// ============================================================================
// Transform Access
// ============================================================================

TC_API tc_transform* tc_entity_transform(tc_entity* e);

// Convenience shortcuts (delegate to transform)
TC_API tc_general_pose3 tc_entity_local_pose(const tc_entity* e);
TC_API void tc_entity_set_local_pose(tc_entity* e, tc_general_pose3 pose);
TC_API tc_general_pose3 tc_entity_global_pose(const tc_entity* e);
TC_API void tc_entity_set_global_pose(tc_entity* e, tc_general_pose3 pose);

// ============================================================================
// Flags
// ============================================================================

TC_API bool tc_entity_visible(const tc_entity* e);
TC_API void tc_entity_set_visible(tc_entity* e, bool v);

TC_API bool tc_entity_active(const tc_entity* e);
TC_API void tc_entity_set_active(tc_entity* e, bool v);

TC_API bool tc_entity_pickable(const tc_entity* e);
TC_API void tc_entity_set_pickable(tc_entity* e, bool v);

TC_API bool tc_entity_selectable(const tc_entity* e);
TC_API void tc_entity_set_selectable(tc_entity* e, bool v);

TC_API bool tc_entity_serializable(const tc_entity* e);
TC_API void tc_entity_set_serializable(tc_entity* e, bool v);

TC_API int tc_entity_priority(const tc_entity* e);
TC_API void tc_entity_set_priority(tc_entity* e, int p);

TC_API uint64_t tc_entity_layer(const tc_entity* e);
TC_API void tc_entity_set_layer(tc_entity* e, uint64_t layer);

TC_API uint64_t tc_entity_flags(const tc_entity* e);
TC_API void tc_entity_set_flags(tc_entity* e, uint64_t flags);

// ============================================================================
// Component Management
// ============================================================================

TC_API void tc_entity_add_component(tc_entity* e, tc_component* c);
TC_API void tc_entity_remove_component(tc_entity* e, tc_component* c);
TC_API tc_component* tc_entity_get_component(tc_entity* e, const char* type_name);
TC_API size_t tc_entity_component_count(const tc_entity* e);
TC_API tc_component* tc_entity_component_at(tc_entity* e, size_t index);

// ============================================================================
// Hierarchy (shortcuts to transform, with entity resolution)
// ============================================================================

TC_API void tc_entity_set_parent(tc_entity* e, tc_entity* parent);
TC_API tc_entity* tc_entity_parent(const tc_entity* e);
TC_API size_t tc_entity_children_count(const tc_entity* e);
TC_API tc_entity* tc_entity_child_at(const tc_entity* e, size_t index);

// ============================================================================
// Scene
// ============================================================================

TC_API void tc_entity_set_scene(tc_entity* e, void* scene);
TC_API void* tc_entity_scene(const tc_entity* e);

// ============================================================================
// User Data (for language bindings)
// ============================================================================

TC_API void tc_entity_set_data(tc_entity* e, void* data);
TC_API void* tc_entity_data(const tc_entity* e);

// ============================================================================
// Lifecycle
// ============================================================================

TC_API void tc_entity_update(tc_entity* e, float dt);
TC_API void tc_entity_fixed_update(tc_entity* e, float dt);
TC_API void tc_entity_on_added_to_scene(tc_entity* e, void* scene);
TC_API void tc_entity_on_removed_from_scene(tc_entity* e);

// ============================================================================
// EntityHandle - lazy reference by UUID
// ============================================================================

static inline tc_entity_handle tc_entity_handle_empty(void) {
#ifdef __cplusplus
    tc_entity_handle h = {};
#else
    tc_entity_handle h = {{0}};
#endif
    return h;
}

TC_API tc_entity_handle tc_entity_handle_from_uuid(const char* uuid);
TC_API tc_entity_handle tc_entity_handle_from_entity(const tc_entity* e);
TC_API tc_entity* tc_entity_handle_get(tc_entity_handle h);
TC_API bool tc_entity_handle_is_valid(tc_entity_handle h);

// ============================================================================
// Entity Registry (global lookup)
// ============================================================================

TC_API tc_entity* tc_entity_registry_find_by_uuid(const char* uuid);
TC_API tc_entity* tc_entity_registry_find_by_runtime_id(uint64_t id);
TC_API tc_entity* tc_entity_registry_find_by_pick_id(uint32_t id);

TC_API size_t tc_entity_registry_count(void);
TC_API tc_entity* tc_entity_registry_at(size_t index);

// Snapshot for iteration safety
TC_API size_t tc_entity_registry_snapshot(tc_entity** out, size_t max_count);

#ifdef __cplusplus
}
#endif

#endif // TC_ENTITY_H
