// tc_skeleton.h - Skeleton data structures for skeletal animation
#pragma once

#include <geom/tc_mat44.h>
#include <geom/tc_quat.h>
#include <tcbase/tc_binding_types.h>
#include <tcbase/tc_resource.h>
#include <tcbase/tc_types.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Skeleton handle - safe reference to skeleton in pool
// ============================================================================

TC_DEFINE_HANDLE(tc_skeleton_handle)

// ============================================================================
// Bone data
// ============================================================================

#define TC_BONE_NAME_MAX 64

typedef struct tc_bone {
    char name[TC_BONE_NAME_MAX];
    int32_t index;
    int32_t parent_index; // -1 for root bones

    // Typed values retain the historical packed binary order. The matrix is
    // column-major, matching the project-wide tc_mat44 convention.
    tc_mat44 inverse_bind_matrix;

    // Bind pose local transform
    tc_vec3 bind_translation;
    tc_quat bind_rotation;
    tc_vec3 bind_scale;
} tc_bone;

// Owned transform values for transactional bulk skeleton replacement. Only
// name is borrowed for the duration of tc_skeleton_replace_bones().
typedef struct tc_skeleton_bone_desc {
    const char* name;
    int32_t parent_index;
    tc_mat44 inverse_bind_matrix;
    tc_vec3 bind_translation;
    tc_quat bind_rotation;
    tc_vec3 bind_scale;
} tc_skeleton_bone_desc;

#ifdef __cplusplus
static_assert(sizeof(tc_bone) == 280, "tc_bone packed ABI size changed");
static_assert(alignof(tc_bone) == alignof(double), "tc_bone packed ABI alignment changed");
static_assert(offsetof(tc_bone, inverse_bind_matrix) == 72, "tc_bone inverse-bind offset changed");
static_assert(offsetof(tc_bone, bind_translation) == 200, "tc_bone translation offset changed");
static_assert(offsetof(tc_bone, bind_rotation) == 224, "tc_bone rotation offset changed");
static_assert(offsetof(tc_bone, bind_scale) == 256, "tc_bone scale offset changed");
#else
_Static_assert(sizeof(tc_bone) == 280, "tc_bone packed ABI size changed");
_Static_assert(_Alignof(tc_bone) == _Alignof(double), "tc_bone packed ABI alignment changed");
_Static_assert(offsetof(tc_bone, inverse_bind_matrix) == 72, "tc_bone inverse-bind offset changed");
_Static_assert(offsetof(tc_bone, bind_translation) == 200, "tc_bone translation offset changed");
_Static_assert(offsetof(tc_bone, bind_rotation) == 224, "tc_bone rotation offset changed");
_Static_assert(offsetof(tc_bone, bind_scale) == 256, "tc_bone scale offset changed");
#endif

// ============================================================================
// Skeleton data
// ============================================================================

typedef struct tc_skeleton {
    tc_resource_header header; // common resource fields

    const tc_bone* bones; // immutable array of bones (owned, malloc'd)
    size_t bone_count;

    const int32_t* root_indices; // immutable root indices (owned, malloc'd)
    size_t root_count;
} tc_skeleton;

// ============================================================================
// Bone helpers
// ============================================================================

// Initialize bone to identity
static inline void tc_bone_init(tc_bone* bone) {
    if (!bone)
        return;
    bone->name[0] = '\0';
    bone->index = 0;
    bone->parent_index = -1;

    bone->inverse_bind_matrix = tc_mat44_identity();
    bone->bind_translation = tc_vec3_zero();
    bone->bind_rotation = tc_quat_identity();
    bone->bind_scale = tc_vec3_one();
}

static inline bool tc_bone_is_root(const tc_bone* bone) {
    return bone && bone->parent_index < 0;
}

// ============================================================================
// Reference counting
// ============================================================================

TC_API void tc_skeleton_add_ref(tc_skeleton* skeleton);
TC_API bool tc_skeleton_release(tc_skeleton* skeleton);

#ifdef __cplusplus
}
#endif
