// tc_transform.c - Transform implementation
#include "../include/tc_transform.h"
#include "../include/tc_entity.h"
#include <stdlib.h>
#include <string.h>

// ============================================================================
// Internal structure
// ============================================================================

#define TC_TRANSFORM_INITIAL_CHILDREN 4

struct tc_transform {
    tc_general_pose3 local_pose;

    // Hierarchy
    tc_transform* parent;
    tc_transform** children;
    size_t children_count;
    size_t children_capacity;

    // Back-pointer to owning entity
    tc_entity* entity;

    // Cached global pose
    tc_general_pose3 cached_global_pose;
    bool dirty;

    // Version tracking
    uint32_t version;
};

// ============================================================================
// Creation / Destruction
// ============================================================================

tc_transform* tc_transform_new(void) {
    tc_transform* t = (tc_transform*)calloc(1, sizeof(tc_transform));
    if (!t) return NULL;

    t->local_pose = tc_gpose_identity();
    t->parent = NULL;
    t->children = NULL;
    t->children_count = 0;
    t->children_capacity = 0;
    t->entity = NULL;
    t->cached_global_pose = tc_gpose_identity();
    t->dirty = true;
    t->version = 0;

    return t;
}

tc_transform* tc_transform_new_with_pose(tc_general_pose3 pose) {
    tc_transform* t = tc_transform_new();
    if (t) {
        t->local_pose = pose;
    }
    return t;
}

void tc_transform_free(tc_transform* t) {
    if (!t) return;

    // Unparent
    tc_transform_unparent(t);

    // Detach all children
    for (size_t i = 0; i < t->children_count; i++) {
        if (t->children[i]) {
            t->children[i]->parent = NULL;
        }
    }

    free(t->children);
    free(t);
}

// ============================================================================
// Pose Access
// ============================================================================

tc_general_pose3 tc_transform_local_pose(const tc_transform* t) {
    return t ? t->local_pose : tc_gpose_identity();
}

void tc_transform_set_local_pose(tc_transform* t, tc_general_pose3 pose) {
    if (!t) return;
    t->local_pose = pose;
    tc_transform_mark_dirty(t);
}

static void tc_transform_update_cache(const tc_transform* t) {
    if (!t->dirty) return;

    tc_transform* mut_t = (tc_transform*)t;  // const_cast for cache update

    if (t->parent) {
        tc_general_pose3 parent_global = tc_transform_global_pose(t->parent);
        mut_t->cached_global_pose = tc_gpose_mul(parent_global, t->local_pose);
    } else {
        mut_t->cached_global_pose = t->local_pose;
    }

    mut_t->dirty = false;
}

tc_general_pose3 tc_transform_global_pose(const tc_transform* t) {
    if (!t) return tc_gpose_identity();
    tc_transform_update_cache(t);
    return t->cached_global_pose;
}

void tc_transform_set_global_pose(tc_transform* t, tc_general_pose3 pose) {
    if (!t) return;

    if (t->parent) {
        tc_general_pose3 parent_global = tc_transform_global_pose(t->parent);
        tc_general_pose3 parent_inv = tc_gpose_inverse(parent_global);
        t->local_pose = tc_gpose_mul(parent_inv, pose);
    } else {
        t->local_pose = pose;
    }

    tc_transform_mark_dirty(t);
}

tc_vec3 tc_transform_position(const tc_transform* t) {
    return t ? t->local_pose.position : tc_vec3_zero();
}

void tc_transform_set_position(tc_transform* t, tc_vec3 pos) {
    if (!t) return;
    t->local_pose.position = pos;
    tc_transform_mark_dirty(t);
}

tc_quat tc_transform_rotation(const tc_transform* t) {
    return t ? t->local_pose.rotation : tc_quat_identity();
}

void tc_transform_set_rotation(tc_transform* t, tc_quat rot) {
    if (!t) return;
    t->local_pose.rotation = rot;
    tc_transform_mark_dirty(t);
}

tc_vec3 tc_transform_scale(const tc_transform* t) {
    return t ? t->local_pose.scale : tc_vec3_one();
}

void tc_transform_set_scale(tc_transform* t, tc_vec3 scale) {
    if (!t) return;
    t->local_pose.scale = scale;
    tc_transform_mark_dirty(t);
}

tc_vec3 tc_transform_global_position(const tc_transform* t) {
    tc_general_pose3 gp = tc_transform_global_pose(t);
    return gp.position;
}

tc_quat tc_transform_global_rotation(const tc_transform* t) {
    tc_general_pose3 gp = tc_transform_global_pose(t);
    return gp.rotation;
}

// ============================================================================
// Hierarchy
// ============================================================================

static void tc_transform_ensure_children_capacity(tc_transform* t) {
    if (t->children_count >= t->children_capacity) {
        size_t new_capacity = t->children_capacity == 0
            ? TC_TRANSFORM_INITIAL_CHILDREN
            : t->children_capacity * 2;
        tc_transform** new_children = (tc_transform**)realloc(
            t->children, new_capacity * sizeof(tc_transform*));
        if (!new_children) return;
        t->children = new_children;
        t->children_capacity = new_capacity;
    }
}

void tc_transform_add_child(tc_transform* parent, tc_transform* child) {
    if (!parent || !child || child->parent == parent) return;

    // Remove from old parent
    tc_transform_unparent(child);

    // Add to new parent
    tc_transform_ensure_children_capacity(parent);
    parent->children[parent->children_count++] = child;
    child->parent = parent;

    tc_transform_mark_dirty(child);
}

void tc_transform_remove_child(tc_transform* parent, tc_transform* child) {
    if (!parent || !child || child->parent != parent) return;

    for (size_t i = 0; i < parent->children_count; i++) {
        if (parent->children[i] == child) {
            // Shift remaining children
            for (size_t j = i; j < parent->children_count - 1; j++) {
                parent->children[j] = parent->children[j + 1];
            }
            parent->children_count--;
            child->parent = NULL;
            tc_transform_mark_dirty(child);
            return;
        }
    }
}

void tc_transform_set_parent(tc_transform* child, tc_transform* parent) {
    if (!child) return;
    if (parent) {
        tc_transform_add_child(parent, child);
    } else {
        tc_transform_unparent(child);
    }
}

void tc_transform_unparent(tc_transform* t) {
    if (!t || !t->parent) return;
    tc_transform_remove_child(t->parent, t);
}

tc_transform* tc_transform_parent(const tc_transform* t) {
    return t ? t->parent : NULL;
}

size_t tc_transform_children_count(const tc_transform* t) {
    return t ? t->children_count : 0;
}

tc_transform* tc_transform_child_at(const tc_transform* t, size_t index) {
    if (!t || index >= t->children_count) return NULL;
    return t->children[index];
}

// ============================================================================
// Entity back-pointer
// ============================================================================

tc_entity* tc_transform_entity(const tc_transform* t) {
    return t ? t->entity : NULL;
}

void tc_transform_set_entity(tc_transform* t, tc_entity* e) {
    if (t) t->entity = e;
}

// ============================================================================
// Dirty Tracking
// ============================================================================

bool tc_transform_is_dirty(const tc_transform* t) {
    return t ? t->dirty : false;
}

void tc_transform_mark_dirty(tc_transform* t) {
    if (!t || t->dirty) return;

    t->dirty = true;
    t->version++;

    // Propagate to children
    for (size_t i = 0; i < t->children_count; i++) {
        tc_transform_mark_dirty(t->children[i]);
    }
}

uint32_t tc_transform_version(const tc_transform* t) {
    return t ? t->version : 0;
}

// ============================================================================
// Matrix
// ============================================================================

void tc_transform_world_matrix(const tc_transform* t, tc_mat44* out) {
    if (!t || !out) return;
    tc_general_pose3 gp = tc_transform_global_pose(t);
    tc_gpose_to_mat44(gp, out);
}

void tc_transform_local_matrix(const tc_transform* t, tc_mat44* out) {
    if (!t || !out) return;
    tc_gpose_to_mat44(t->local_pose, out);
}

// ============================================================================
// Transform operations
// ============================================================================

void tc_transform_translate(tc_transform* t, tc_vec3 delta) {
    if (!t) return;
    t->local_pose.position = tc_vec3_add(t->local_pose.position, delta);
    tc_transform_mark_dirty(t);
}

void tc_transform_rotate(tc_transform* t, tc_quat delta) {
    if (!t) return;
    t->local_pose.rotation = tc_quat_mul(t->local_pose.rotation, delta);
    tc_transform_mark_dirty(t);
}

void tc_transform_look_at(tc_transform* t, tc_vec3 target, tc_vec3 up) {
    if (!t) return;

    tc_vec3 pos = tc_transform_global_position(t);
    tc_vec3 forward = tc_vec3_normalize(tc_vec3_sub(target, pos));
    tc_vec3 right = tc_vec3_normalize(tc_vec3_cross(up, forward));
    tc_vec3 new_up = tc_vec3_cross(forward, right);

    // Build rotation matrix and convert to quaternion
    // This is a simplified version - full implementation would be more robust
    double trace = right.x + new_up.y + forward.z;
    tc_quat q;

    if (trace > 0) {
        double s = 0.5 / sqrt(trace + 1.0);
        q.w = 0.25 / s;
        q.x = (new_up.z - forward.y) * s;
        q.y = (forward.x - right.z) * s;
        q.z = (right.y - new_up.x) * s;
    } else {
        // Handle edge cases...
        q = tc_quat_identity();
    }

    tc_transform_set_rotation(t, tc_quat_normalize(q));
}

tc_vec3 tc_transform_local_to_world(const tc_transform* t, tc_vec3 point) {
    tc_general_pose3 gp = tc_transform_global_pose(t);
    return tc_gpose_transform_point(gp, point);
}

tc_vec3 tc_transform_world_to_local(const tc_transform* t, tc_vec3 point) {
    tc_general_pose3 gp = tc_transform_global_pose(t);
    tc_general_pose3 inv = tc_gpose_inverse(gp);
    return tc_gpose_transform_point(inv, point);
}
