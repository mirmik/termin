// tc_scene_skybox.c - Scene skybox implementation
#include "../include/tc_scene_skybox.h"
#include "../include/tc_scene.h"
#include "../include/tc_mesh.h"
#include "../include/tc_material.h"

// Internal accessor - tc_scene struct is defined in tc_scene.c
// We need to access skybox field. Define a minimal struct here.
struct tc_scene_skybox_accessor {
    char _padding[sizeof(void*) * 6 + sizeof(double) * 2 + sizeof(void*) * 2];
    // After: pool, pending_start, update_list, fixed_update_list, before_render_list (ComponentList has items, count, cap = 3 pointers each)
    // Needs proper offset calculation
};

// Get skybox from scene - implemented via tc_scene_get_skybox
// The actual struct layout is in tc_scene.c, so we expose a getter there

void tc_scene_skybox_init(tc_scene_skybox* skybox) {
    if (!skybox) return;
    skybox->type = TC_SKYBOX_GRADIENT;
    // Solid color: blue-ish default
    skybox->color[0] = 0.5f;
    skybox->color[1] = 0.7f;
    skybox->color[2] = 0.9f;
    // Gradient top: sky blue
    skybox->top_color[0] = 0.4f;
    skybox->top_color[1] = 0.6f;
    skybox->top_color[2] = 0.9f;
    // Gradient bottom: warm horizon
    skybox->bottom_color[0] = 0.6f;
    skybox->bottom_color[1] = 0.5f;
    skybox->bottom_color[2] = 0.4f;
    skybox->mesh = NULL;
    skybox->material = NULL;
}

void tc_scene_skybox_free(tc_scene_skybox* skybox) {
    if (!skybox) return;
    if (skybox->mesh) {
        tc_mesh_release(skybox->mesh);
        skybox->mesh = NULL;
    }
    if (skybox->material) {
        tc_material_release(skybox->material);
        skybox->material = NULL;
    }
}
