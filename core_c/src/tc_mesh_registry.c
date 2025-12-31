#include "tc_mesh_registry.h"
#include "tc_resource_map.h"
#include "tc_log.h"
#include "termin_core.h"
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
}

void tc_mesh_shutdown(void) {
    if (!g_meshes) {
        tc_log_warn("tc_mesh_shutdown: not initialized");
        return;
    }
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
    mesh->ref_count = 0;  // No owners yet
    mesh->name = NULL;

    if (!tc_resource_map_add(g_meshes, mesh->uuid, mesh)) {
        tc_log_error("tc_mesh_add: failed to add to map");
        free(mesh);
        return NULL;
    }

    return mesh;
}

tc_mesh* tc_mesh_get(const char* uuid) {
    if (!g_meshes) {
        tc_log_warn("tc_mesh_get: registry not initialized");
        return NULL;
    }
    return (tc_mesh*)tc_resource_map_get(g_meshes, uuid);
}

tc_mesh* tc_mesh_get_or_create(const char* uuid) {
    // Auto-initialize if needed
    if (!g_meshes) {
        tc_mesh_init();
    }
    if (!uuid || uuid[0] == '\0') {
        tc_log_warn("tc_mesh_get_or_create: empty uuid");
        return NULL;
    }

    // Try to get existing (no ref increment - caller must take ownership)
    tc_mesh* mesh = (tc_mesh*)tc_resource_map_get(g_meshes, uuid);
    if (mesh) {
        return mesh;
    }

    // Create new
    return tc_mesh_add(uuid);
}

bool tc_mesh_remove(const char* uuid) {
    if (!g_meshes) {
        tc_log_warn("tc_mesh_remove: registry not initialized");
        return false;
    }
    return tc_resource_map_remove(g_meshes, uuid);
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
    const void* vertices,
    size_t vertex_count,
    const tc_vertex_layout* layout,
    const uint32_t* indices,
    size_t index_count,
    const char* name
) {
    if (!mesh || !layout) return false;

    if (name) {
        mesh->name = tc_intern_string(name);
    }

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

// ============================================================================
// Iteration
// ============================================================================

// Adapter for tc_resource_map_foreach -> tc_mesh_iter_fn
typedef struct {
    tc_mesh_iter_fn callback;
    void* user_data;
} mesh_iter_ctx;

static bool mesh_iter_adapter(const char* uuid, void* resource, void* ctx_ptr) {
    (void)uuid;
    mesh_iter_ctx* ctx = (mesh_iter_ctx*)ctx_ptr;
    return ctx->callback((const tc_mesh*)resource, ctx->user_data);
}

void tc_mesh_foreach(tc_mesh_iter_fn callback, void* user_data) {
    if (!g_meshes || !callback) return;
    mesh_iter_ctx ctx = { callback, user_data };
    tc_resource_map_foreach(g_meshes, mesh_iter_adapter, &ctx);
}

// Helper struct for collecting mesh info
typedef struct {
    tc_mesh_info* infos;
    size_t count;
    size_t capacity;
} info_collector;

static bool collect_mesh_info(const tc_mesh* mesh, void* user_data) {
    info_collector* collector = (info_collector*)user_data;

    tc_mesh_info info;
    strncpy(info.uuid, mesh->uuid, sizeof(info.uuid) - 1);
    info.uuid[sizeof(info.uuid) - 1] = '\0';
    info.name = mesh->name;
    info.ref_count = mesh->ref_count;
    info.version = mesh->version;
    info.vertex_count = mesh->vertex_count;
    info.index_count = mesh->index_count;
    info.stride = mesh->layout.stride;
    info.memory_bytes = mesh->vertex_count * mesh->layout.stride +
                        mesh->index_count * sizeof(uint32_t);

    collector->infos[collector->count++] = info;
    return true;
}

tc_mesh_info* tc_mesh_get_all_info(size_t* count) {
    if (!count) return NULL;
    *count = 0;

    if (!g_meshes) return NULL;

    size_t mesh_count = tc_resource_map_count(g_meshes);
    if (mesh_count == 0) return NULL;

    tc_mesh_info* infos = (tc_mesh_info*)malloc(mesh_count * sizeof(tc_mesh_info));
    if (!infos) {
        tc_log_error("tc_mesh_get_all_info: allocation failed");
        return NULL;
    }

    info_collector collector = { infos, 0, mesh_count };
    tc_mesh_foreach(collect_mesh_info, &collector);

    *count = collector.count;
    return infos;
}
