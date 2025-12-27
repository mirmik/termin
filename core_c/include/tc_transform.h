// tc_transform.h - Hierarchical transform
#ifndef TC_TRANSFORM_H
#define TC_TRANSFORM_H

#include "tc_types.h"
#include "tc_pose.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Transform structure (opaque in header, defined in .c)
// ============================================================================

// Transform manages:
// - Local pose (position, rotation, scale relative to parent)
// - Parent/children hierarchy
// - Cached global pose with dirty tracking
// - Version numbers for change propagation

// ============================================================================
// Creation / Destruction
// ============================================================================

TC_API tc_transform* tc_transform_new(void);
TC_API tc_transform* tc_transform_new_with_pose(tc_general_pose3 pose);
TC_API void tc_transform_free(tc_transform* t);

// ============================================================================
// Pose Access
// ============================================================================

TC_API tc_general_pose3 tc_transform_local_pose(const tc_transform* t);
TC_API void tc_transform_set_local_pose(tc_transform* t, tc_general_pose3 pose);

TC_API tc_general_pose3 tc_transform_global_pose(const tc_transform* t);
TC_API void tc_transform_set_global_pose(tc_transform* t, tc_general_pose3 pose);

// Convenience accessors
TC_API tc_vec3 tc_transform_position(const tc_transform* t);
TC_API void tc_transform_set_position(tc_transform* t, tc_vec3 pos);

TC_API tc_quat tc_transform_rotation(const tc_transform* t);
TC_API void tc_transform_set_rotation(tc_transform* t, tc_quat rot);

TC_API tc_vec3 tc_transform_scale(const tc_transform* t);
TC_API void tc_transform_set_scale(tc_transform* t, tc_vec3 scale);

TC_API tc_vec3 tc_transform_global_position(const tc_transform* t);
TC_API tc_quat tc_transform_global_rotation(const tc_transform* t);

// ============================================================================
// Hierarchy
// ============================================================================

TC_API void tc_transform_add_child(tc_transform* parent, tc_transform* child);
TC_API void tc_transform_remove_child(tc_transform* parent, tc_transform* child);
TC_API void tc_transform_set_parent(tc_transform* child, tc_transform* parent);
TC_API void tc_transform_unparent(tc_transform* t);

TC_API tc_transform* tc_transform_parent(const tc_transform* t);
TC_API size_t tc_transform_children_count(const tc_transform* t);
TC_API tc_transform* tc_transform_child_at(const tc_transform* t, size_t index);

// ============================================================================
// Entity back-pointer
// ============================================================================

TC_API tc_entity* tc_transform_entity(const tc_transform* t);
TC_API void tc_transform_set_entity(tc_transform* t, tc_entity* e);

// ============================================================================
// Dirty Tracking
// ============================================================================

TC_API bool tc_transform_is_dirty(const tc_transform* t);
TC_API void tc_transform_mark_dirty(tc_transform* t);
TC_API uint32_t tc_transform_version(const tc_transform* t);

// ============================================================================
// Matrix
// ============================================================================

TC_API void tc_transform_world_matrix(const tc_transform* t, tc_mat44* out);
TC_API void tc_transform_local_matrix(const tc_transform* t, tc_mat44* out);

// ============================================================================
// Transform operations
// ============================================================================

// Move by delta in local space
TC_API void tc_transform_translate(tc_transform* t, tc_vec3 delta);

// Rotate by quaternion in local space
TC_API void tc_transform_rotate(tc_transform* t, tc_quat delta);

// Look at target point (world space)
TC_API void tc_transform_look_at(tc_transform* t, tc_vec3 target, tc_vec3 up);

// Transform point from local to world space
TC_API tc_vec3 tc_transform_local_to_world(const tc_transform* t, tc_vec3 point);

// Transform point from world to local space
TC_API tc_vec3 tc_transform_world_to_local(const tc_transform* t, tc_vec3 point);

#ifdef __cplusplus
}
#endif

#endif // TC_TRANSFORM_H
