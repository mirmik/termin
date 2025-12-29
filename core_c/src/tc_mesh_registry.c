#include "tc_mesh_registry.h"
#include "tc_resource_map.h"
#include "tc_log.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// ============================================================================
// Global state
// ============================================================================

static tc_resource_map* g_meshes = NULL;
static uint64_t g_next_uuid = 1;

// ============================================================================
// Internal helpers
// ============================================================================

static void generate_uuid(char* out_uuid) {
    snprintf(out_uuid, 40, "mesh-%016llx", (unsigned long long)g_next_uuid++);
}

static void mesh_destructor(void* ptr) {
    tc_mesh* mesh = (tc_mesh*)ptr;
    if (!mesh) return;
    if (mesh->vertices) free(mesh->vertices);
    if (mesh->indices) free(mesh->indices);
    free(mesh);
}

// ============================================================================
// Lifecycle
// ============================================================================

void tc_mesh_init(void) {
    if (g_meshes) {
        tc_log_warn("tc_mesh_init: already initialized");
        return;
    }
    g_meshes = tc_resource_map_new(mesh_destructor);
    g_next_uuid = 1;
    tc_log_debug("tc_mesh_init: mesh registry initialized");
}

void tc_mesh_shutdown(void) {
    if (!g_meshes) {
        tc_log_warn("tc_mesh_shutdown: not initialized");
        return;
    }
    size_t count = tc_resource_map_count(g_meshes);
    tc_log_debug("tc_mesh_shutdown: freeing %zu meshes", count);
    tc_resource_map_free(g_meshes);
    g_meshes = NULL;
    g_next_uuid = 1;
}

// ============================================================================
// Mesh operations
// ============================================================================

tc_mesh* tc_mesh_add(const char* uuid) {
    // Auto-initialize if needed
    if (!g_meshes) {
        tc_log_debug("tc_mesh_add: auto-initializing registry");
        tc_mesh_init();
    }

    char uuid_buf[40];
    const char* final_uuid;

    if (uuid && uuid[0] != '\0') {
        if (tc_mesh_contains(uuid)) {
            tc_log_warn("tc_mesh_add: uuid '%s' already exists", uuid);
            return NULL;
        }
        final_uuid = uuid;
    } else {
        generate_uuid(uuid_buf);
        final_uuid = uuid_buf;
    }

    tc_mesh* mesh = (tc_mesh*)calloc(1, sizeof(tc_mesh));
    if (!mesh) {
        tc_log_error("tc_mesh_add: allocation failed");
        return NULL;
    }

    strncpy(mesh->uuid, final_uuid, sizeof(mesh->uuid) - 1);
    mesh->uuid[sizeof(mesh->uuid) - 1] = '\0';
    mesh->version = 1;
    mesh->ref_count = 1;
    mesh->name = NULL;

    if (!tc_resource_map_add(g_meshes, mesh->uuid, mesh)) {
        tc_log_error("tc_mesh_add: failed to add to map");
        free(mesh);
        return NULL;
    }

    tc_log_debug("tc_mesh_add: created '%s' (ref=1)", mesh->uuid);
    return mesh;
}

tc_mesh* tc_mesh_get(const char* uuid) {
    if (!g_meshes) {
        tc_log_warn("tc_mesh_get: registry not initialized");
        return NULL;
    }
    tc_mesh* mesh = (tc_mesh*)tc_resource_map_get(g_meshes, uuid);
    if (!mesh) {
        tc_log_debug("tc_mesh_get: '%s' not found", uuid ? uuid : "(null)");
    }
    return mesh;
}

static int debug_count = 0;

TC_API tc_mesh* tc_mesh_get_or_create(const char* uuid) {
    static int call_id = 0;
    int my_call_id = call_id++;

    fprintf(stderr, "[TRACE] tc_mesh_get_or_create ENTER call_id=%d uuid=%.16s this_func=%p\n",
            my_call_id, uuid ? uuid : "(null)", (void*)&tc_mesh_get_or_create);
    fflush(stderr);

    // Auto-initialize if needed
    if (!g_meshes) {
        tc_log_debug("tc_mesh_get_or_create: auto-initializing registry (g_meshes=%p)", (void*)&g_meshes);
        tc_mesh_init();
    }
    if (!uuid || uuid[0] == '\0') {
        tc_log_warn("tc_mesh_get_or_create: empty uuid");
        return NULL;
    }

    // Try to get existing
    tc_mesh* mesh = (tc_mesh*)tc_resource_map_get(g_meshes, uuid);
    if (mesh) {
        mesh->ref_count++;
        tc_log_debug("tc_mesh_get_or_create: reusing '%s' [%s] (ref=%u)",
            mesh->name ? mesh->name : "?", uuid, mesh->ref_count);
        fprintf(stderr, "[TRACE] tc_mesh_get_or_create EXIT call_id=%d REUSE ref=%u\n", my_call_id, mesh->ref_count);
        fflush(stderr);
        return mesh;
    }

    // Create new
    tc_log_debug("tc_mesh_get_or_create: creating new [%s] (g_meshes=%p) (debug_count=%d)", uuid, (void*)g_meshes, debug_count++);
    mesh = tc_mesh_add(uuid);
    fprintf(stderr, "[TRACE] tc_mesh_get_or_create EXIT call_id=%d NEW mesh=%p\n", my_call_id, (void*)mesh);
    fflush(stderr);
    return mesh;
}

bool tc_mesh_remove(const char* uuid) {
    if (!g_meshes) {
        tc_log_warn("tc_mesh_remove: registry not initialized");
        return false;
    }
    bool removed = tc_resource_map_remove(g_meshes, uuid);
    if (removed) {
        tc_log_debug("tc_mesh_remove: removed '%s'", uuid ? uuid : "(null)");
    } else {
        tc_log_warn("tc_mesh_remove: '%s' not found", uuid ? uuid : "(null)");
    }
    return removed;
}

bool tc_mesh_contains(const char* uuid) {
    if (!g_meshes) return false;
    return tc_resource_map_contains(g_meshes, uuid);
}

size_t tc_mesh_count(void) {
    if (!g_meshes) return 0;
    return tc_resource_map_count(g_meshes);
}

// ============================================================================
// Mesh data helpers
// ============================================================================

bool tc_mesh_set_vertices(
    tc_mesh* mesh,
    const void* data,
    size_t vertex_count,
    const tc_vertex_layout* layout
) {
    if (!mesh || !layout) return false;

    size_t data_size = vertex_count * layout->stride;

    void* new_vertices = NULL;
    if (data_size > 0) {
        new_vertices = malloc(data_size);
        if (!new_vertices) return false;
        if (data) {
            memcpy(new_vertices, data, data_size);
        } else {
            memset(new_vertices, 0, data_size);
        }
    }

    if (mesh->vertices) free(mesh->vertices);

    mesh->vertices = new_vertices;
    mesh->vertex_count = vertex_count;
    mesh->layout = *layout;
    mesh->version++;

    return true;
}

bool tc_mesh_set_indices(
    tc_mesh* mesh,
    const uint32_t* data,
    size_t index_count
) {
    if (!mesh) return false;

    size_t data_size = index_count * sizeof(uint32_t);

    uint32_t* new_indices = NULL;
    if (data_size > 0) {
        new_indices = (uint32_t*)malloc(data_size);
        if (!new_indices) return false;
        if (data) {
            memcpy(new_indices, data, data_size);
        } else {
            memset(new_indices, 0, data_size);
        }
    }

    if (mesh->indices) free(mesh->indices);

    mesh->indices = new_indices;
    mesh->index_count = index_count;
    mesh->version++;

    return true;
}

bool tc_mesh_set_data(
    tc_mesh* mesh,
    const char* name,
    const void* vertices,
    size_t vertex_count,
    const tc_vertex_layout* layout,
    const uint32_t* indices,
    size_t index_count
) {
    if (!mesh || !layout || !name) return false;

    mesh->name = tc_intern_string(name);

    size_t vertex_size = vertex_count * layout->stride;
    void* new_vertices = NULL;
    if (vertex_size > 0) {
        new_vertices = malloc(vertex_size);
        if (!new_vertices) return false;
        if (vertices) {
            memcpy(new_vertices, vertices, vertex_size);
        } else {
            memset(new_vertices, 0, vertex_size);
        }
    }

    size_t index_size = index_count * sizeof(uint32_t);
    uint32_t* new_indices = NULL;
    if (index_size > 0) {
        new_indices = (uint32_t*)malloc(index_size);
        if (!new_indices) {
            free(new_vertices);
            return false;
        }
        if (indices) {
            memcpy(new_indices, indices, index_size);
        } else {
            memset(new_indices, 0, index_size);
        }
    }

    if (mesh->vertices) free(mesh->vertices);
    if (mesh->indices) free(mesh->indices);

    mesh->vertices = new_vertices;
    mesh->vertex_count = vertex_count;
    mesh->layout = *layout;
    mesh->indices = new_indices;
    mesh->index_count = index_count;
    mesh->version++;

    return true;
}
