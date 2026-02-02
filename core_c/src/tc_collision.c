/**
 * @file tc_collision.c
 * @brief C API implementation for collision detection.
 */

#include "tc_collision.h"
#include "tc_scene.h"
#include <stdlib.h>
#include <string.h>

// Forward declarations for C++ collision world functions
#ifdef __cplusplus
extern "C" {
#endif

void tc_collision_world_update_all(void* cw);
size_t tc_collision_world_detect_contacts(void* cw, tc_contact_manifold** out_manifolds);

#ifdef __cplusplus
}
#endif

// Static storage for collision results
static tc_contact_manifold* s_manifolds = NULL;
static size_t s_manifold_count = 0;

void tc_scene_collision_update(tc_scene_handle scene) {
    void* cw = tc_scene_get_collision_world(scene);
    if (cw) {
        tc_collision_world_update_all(cw);
    }
}

int tc_scene_has_collisions(tc_scene_handle scene) {
    void* cw = tc_scene_get_collision_world(scene);
    if (!cw) return 0;

    tc_contact_manifold* manifolds = NULL;
    size_t count = tc_collision_world_detect_contacts(cw, &manifolds);
    return count > 0 ? 1 : 0;
}

size_t tc_scene_collision_count(tc_scene_handle scene) {
    return s_manifold_count;
}

tc_contact_manifold* tc_scene_detect_collisions(tc_scene_handle scene, size_t* out_count) {
    void* cw = tc_scene_get_collision_world(scene);

    if (out_count) *out_count = 0;
    if (!cw) return NULL;

    // Call the C++ implementation
    s_manifold_count = tc_collision_world_detect_contacts(cw, &s_manifolds);

    if (out_count) *out_count = s_manifold_count;
    return s_manifolds;
}

tc_contact_manifold* tc_scene_get_collision(tc_scene_handle scene, size_t index) {
    (void)scene;
    if (index >= s_manifold_count) return NULL;
    return &s_manifolds[index];
}
