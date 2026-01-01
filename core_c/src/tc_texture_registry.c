#include "tc_texture_registry.h"
#include "tc_resource_map.h"
#include "tc_log.h"
#include "termin_core.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

// ============================================================================
// Global state
// ============================================================================

static tc_resource_map* g_textures = NULL;
static uint64_t g_next_uuid = 1;

// ============================================================================
// Internal helpers
// ============================================================================

static void generate_uuid(char* out_uuid) {
    snprintf(out_uuid, 40, "tex-%016llx", (unsigned long long)g_next_uuid++);
}

static void texture_destructor(void* ptr) {
    tc_texture* tex = (tc_texture*)ptr;
    if (!tex) return;
    if (tex->data) free(tex->data);
    free(tex);
}

// ============================================================================
// Lifecycle
// ============================================================================

void tc_texture_init(void) {
    if (g_textures) {
        tc_log_warn("tc_texture_init: already initialized");
        return;
    }
    g_textures = tc_resource_map_new(texture_destructor);
    g_next_uuid = 1;
}

void tc_texture_shutdown(void) {
    if (!g_textures) {
        tc_log_warn("tc_texture_shutdown: not initialized");
        return;
    }
    tc_resource_map_free(g_textures);
    g_textures = NULL;
    g_next_uuid = 1;
}

// ============================================================================
// Texture operations
// ============================================================================

tc_texture* tc_texture_add(const char* uuid) {
    // Auto-initialize if needed
    if (!g_textures) {
        tc_texture_init();
    }

    char uuid_buf[40];
    const char* final_uuid;

    if (uuid && uuid[0] != '\0') {
        if (tc_texture_contains(uuid)) {
            tc_log_warn("tc_texture_add: uuid '%s' already exists", uuid);
            return NULL;
        }
        final_uuid = uuid;
    } else {
        generate_uuid(uuid_buf);
        final_uuid = uuid_buf;
    }

    tc_texture* tex = (tc_texture*)calloc(1, sizeof(tc_texture));
    if (!tex) {
        tc_log_error("tc_texture_add: allocation failed");
        return NULL;
    }

    strncpy(tex->uuid, final_uuid, sizeof(tex->uuid) - 1);
    tex->uuid[sizeof(tex->uuid) - 1] = '\0';
    tex->version = 1;
    tex->ref_count = 0;
    tex->flip_y = 1;  // Default for OpenGL
    tex->name = NULL;
    tex->source_path = NULL;

    if (!tc_resource_map_add(g_textures, tex->uuid, tex)) {
        tc_log_error("tc_texture_add: failed to add to map");
        free(tex);
        return NULL;
    }

    return tex;
}

tc_texture* tc_texture_get(const char* uuid) {
    if (!g_textures) {
        return NULL;
    }
    return (tc_texture*)tc_resource_map_get(g_textures, uuid);
}

// Helper struct for name search
typedef struct {
    const char* name;
    tc_texture* result;
} name_search_ctx;

static bool name_search_callback(const tc_texture* tex, void* user_data) {
    name_search_ctx* ctx = (name_search_ctx*)user_data;
    if (tex->name && strcmp(tex->name, ctx->name) == 0) {
        ctx->result = (tc_texture*)tex;
        return false;  // Stop iteration
    }
    return true;  // Continue
}

tc_texture* tc_texture_get_by_name(const char* name) {
    if (!g_textures || !name) {
        return NULL;
    }
    name_search_ctx ctx = { name, NULL };
    tc_texture_foreach(name_search_callback, &ctx);
    return ctx.result;
}

tc_texture* tc_texture_get_or_create(const char* uuid) {
    // Auto-initialize if needed
    if (!g_textures) {
        tc_texture_init();
    }
    if (!uuid || uuid[0] == '\0') {
        tc_log_warn("tc_texture_get_or_create: empty uuid");
        return NULL;
    }

    tc_texture* tex = (tc_texture*)tc_resource_map_get(g_textures, uuid);
    if (tex) {
        return tex;
    }

    return tc_texture_add(uuid);
}

bool tc_texture_remove(const char* uuid) {
    if (!g_textures) {
        tc_log_warn("tc_texture_remove: registry not initialized");
        return false;
    }
    return tc_resource_map_remove(g_textures, uuid);
}

bool tc_texture_contains(const char* uuid) {
    if (!g_textures) return false;
    return tc_resource_map_contains(g_textures, uuid);
}

size_t tc_texture_count(void) {
    if (!g_textures) return 0;
    return tc_resource_map_count(g_textures);
}

// ============================================================================
// Helper functions
// ============================================================================

size_t tc_texture_format_bpp(tc_texture_format format) {
    switch (format) {
        case TC_TEXTURE_RGBA8: return 4;
        case TC_TEXTURE_RGB8: return 3;
        case TC_TEXTURE_RG8: return 2;
        case TC_TEXTURE_R8: return 1;
        case TC_TEXTURE_RGBA16F: return 8;
        case TC_TEXTURE_RGB16F: return 6;
        default: return 4;
    }
}

uint8_t tc_texture_format_channels(tc_texture_format format) {
    switch (format) {
        case TC_TEXTURE_RGBA8:
        case TC_TEXTURE_RGBA16F: return 4;
        case TC_TEXTURE_RGB8:
        case TC_TEXTURE_RGB16F: return 3;
        case TC_TEXTURE_RG8: return 2;
        case TC_TEXTURE_R8: return 1;
        default: return 4;
    }
}

// ============================================================================
// Reference counting
// ============================================================================

void tc_texture_add_ref(tc_texture* tex) {
    if (tex) tex->ref_count++;
}

bool tc_texture_release(tc_texture* tex) {
    if (!tex) return false;
    if (tex->ref_count > 0) {
        tex->ref_count--;
    }
    // Note: actual cleanup happens via registry removal
    return tex->ref_count == 0;
}

// ============================================================================
// Texture data helpers
// ============================================================================

bool tc_texture_set_data(
    tc_texture* tex,
    const void* data,
    uint32_t width,
    uint32_t height,
    uint8_t channels,
    const char* name,
    const char* source_path
) {
    if (!tex) return false;

    size_t data_size = (size_t)width * height * channels;

    void* new_data = NULL;
    if (data_size > 0) {
        new_data = malloc(data_size);
        if (!new_data) return false;
        if (data) {
            memcpy(new_data, data, data_size);
        } else {
            memset(new_data, 0, data_size);
        }
    }

    if (tex->data) free(tex->data);

    tex->data = new_data;
    tex->width = width;
    tex->height = height;
    tex->channels = channels;
    tex->format = TC_TEXTURE_RGBA8;  // Default
    tex->version++;

    if (name) {
        tex->name = tc_intern_string(name);
    }
    if (source_path) {
        tex->source_path = tc_intern_string(source_path);
    }

    return true;
}

void tc_texture_set_transforms(
    tc_texture* tex,
    bool flip_x,
    bool flip_y,
    bool transpose
) {
    if (!tex) return;
    tex->flip_x = flip_x ? 1 : 0;
    tex->flip_y = flip_y ? 1 : 0;
    tex->transpose = transpose ? 1 : 0;
    tex->version++;
}

// ============================================================================
// UUID computation
// ============================================================================

void tc_texture_compute_uuid(
    const void* data, size_t size,
    uint32_t width, uint32_t height, uint8_t channels,
    char* uuid_out
) {
    // FNV-1a hash
    uint64_t hash = 14695981039346656037ULL;
    const uint8_t* bytes = (const uint8_t*)data;

    // Hash dimensions first
    uint32_t dims[3] = { width, height, channels };
    for (size_t i = 0; i < sizeof(dims); i++) {
        hash ^= ((const uint8_t*)dims)[i];
        hash *= 1099511628211ULL;
    }

    // Hash data
    for (size_t i = 0; i < size; i++) {
        hash ^= bytes[i];
        hash *= 1099511628211ULL;
    }

    snprintf(uuid_out, 40, "%016llx", (unsigned long long)hash);
}

// ============================================================================
// Iteration
// ============================================================================

typedef struct {
    tc_texture_iter_fn callback;
    void* user_data;
} texture_iter_ctx;

static bool texture_iter_adapter(const char* uuid, void* resource, void* ctx_ptr) {
    (void)uuid;
    texture_iter_ctx* ctx = (texture_iter_ctx*)ctx_ptr;
    return ctx->callback((const tc_texture*)resource, ctx->user_data);
}

void tc_texture_foreach(tc_texture_iter_fn callback, void* user_data) {
    if (!g_textures || !callback) return;
    texture_iter_ctx ctx = { callback, user_data };
    tc_resource_map_foreach(g_textures, texture_iter_adapter, &ctx);
}

// Helper struct for collecting info
typedef struct {
    tc_texture_info* infos;
    size_t count;
    size_t capacity;
} info_collector;

static bool collect_texture_info(const tc_texture* tex, void* user_data) {
    info_collector* collector = (info_collector*)user_data;

    tc_texture_info info;
    strncpy(info.uuid, tex->uuid, sizeof(info.uuid) - 1);
    info.uuid[sizeof(info.uuid) - 1] = '\0';
    info.name = tex->name;
    info.source_path = tex->source_path;
    info.ref_count = tex->ref_count;
    info.version = tex->version;
    info.width = tex->width;
    info.height = tex->height;
    info.channels = tex->channels;
    info.format = tex->format;
    info.memory_bytes = (size_t)tex->width * tex->height * tex->channels;

    collector->infos[collector->count++] = info;
    return true;
}

tc_texture_info* tc_texture_get_all_info(size_t* count) {
    if (!count) return NULL;
    *count = 0;

    if (!g_textures) return NULL;

    size_t tex_count = tc_resource_map_count(g_textures);
    if (tex_count == 0) return NULL;

    tc_texture_info* infos = (tc_texture_info*)malloc(tex_count * sizeof(tc_texture_info));
    if (!infos) {
        tc_log_error("tc_texture_get_all_info: allocation failed");
        return NULL;
    }

    info_collector collector = { infos, 0, tex_count };
    tc_texture_foreach(collect_texture_info, &collector);

    *count = collector.count;
    return infos;
}
