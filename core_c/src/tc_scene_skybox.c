// tc_scene_skybox.c - Scene skybox implementation
#include "../include/tc_scene_skybox.h"
#include "../include/tc_scene.h"
#include "../include/tc_mesh.h"
#include "../include/tc_mesh_registry.h"
#include "../include/tc_material.h"
#include "../include/tc_resource.h"
#include "../include/tc_gpu.h"
#include <stdlib.h>
#include <string.h>

// Skybox cube geometry - 8 vertices, 12 triangles
static const float SKYBOX_VERTICES[8 * 3] = {
    -1.0f, -1.0f, -1.0f,
     1.0f, -1.0f, -1.0f,
     1.0f,  1.0f, -1.0f,
    -1.0f,  1.0f, -1.0f,
    -1.0f, -1.0f,  1.0f,
     1.0f, -1.0f,  1.0f,
     1.0f,  1.0f,  1.0f,
    -1.0f,  1.0f,  1.0f,
};

static const uint32_t SKYBOX_INDICES[12 * 3] = {
    0, 1, 2,  0, 2, 3,  // back
    4, 6, 5,  4, 7, 6,  // front
    0, 4, 5,  0, 5, 1,  // bottom
    3, 2, 6,  3, 6, 7,  // top
    1, 5, 6,  1, 6, 2,  // right
    0, 3, 7,  0, 7, 4,  // left
};

// Create skybox cube mesh
static tc_mesh* create_skybox_cube_mesh(void) {
    // Try to find existing skybox mesh
    tc_mesh_handle h = tc_mesh_find("__builtin_skybox_cube");
    if (tc_mesh_is_valid(h)) {
        tc_mesh* mesh = tc_mesh_get(h);
        if (mesh) {
            tc_mesh_add_ref(mesh);
            return mesh;
        }
    }

    // Create new mesh
    h = tc_mesh_create("__builtin_skybox_cube");
    if (!tc_mesh_is_valid(h)) {
        return NULL;
    }

    tc_mesh* mesh = tc_mesh_get(h);
    if (!mesh) {
        return NULL;
    }

    // Setup position-only layout
    mesh->layout = tc_vertex_layout_pos();

    // Allocate and copy vertices
    size_t vertex_size = 8 * mesh->layout.stride;
    mesh->vertices = malloc(vertex_size);
    if (!mesh->vertices) {
        tc_mesh_destroy(h);
        return NULL;
    }
    memcpy(mesh->vertices, SKYBOX_VERTICES, vertex_size);
    mesh->vertex_count = 8;

    // Allocate and copy indices
    size_t index_size = 36 * sizeof(uint32_t);
    mesh->indices = (uint32_t*)malloc(index_size);
    if (!mesh->indices) {
        free(mesh->vertices);
        mesh->vertices = NULL;
        tc_mesh_destroy(h);
        return NULL;
    }
    memcpy(mesh->indices, SKYBOX_INDICES, index_size);
    mesh->index_count = 36;

    mesh->draw_mode = TC_DRAW_TRIANGLES;

    // Mark as loaded
    mesh->header.version = 1;

    // Add ref for the caller
    tc_mesh_add_ref(mesh);

    return mesh;
}

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

tc_mesh* tc_scene_skybox_ensure_mesh(tc_scene_skybox* skybox) {
    if (!skybox) return NULL;
    if (skybox->mesh) return skybox->mesh;

    // Create skybox mesh lazily
    skybox->mesh = create_skybox_cube_mesh();
    return skybox->mesh;
}
