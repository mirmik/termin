// tc_render.c - High-level render API implementation
#include "tc_render.h"
#include "tc_log.h"
#include <stdlib.h>
#include <string.h>

// ============================================================================
// Global render operations (set by graphics backend)
// ============================================================================

static tc_render_ops g_render_ops = {0};

void tc_render_set_ops(const tc_render_ops* ops) {
    if (ops) {
        g_render_ops = *ops;
    } else {
        memset(&g_render_ops, 0, sizeof(g_render_ops));
    }
}

const tc_render_ops* tc_render_get_ops(void) {
    return &g_render_ops;
}

// ============================================================================
// FBO Pool implementation
// ============================================================================

#define MAX_FBO_ENTRIES 256

typedef struct {
    char* key;
    void* fbo;
    int width;
    int height;
    int samples;
    char* format;
    bool external;  // External FBOs are not destroyed by pool
} tc_fbo_entry;

struct tc_fbo_pool {
    tc_fbo_entry entries[MAX_FBO_ENTRIES];
    size_t count;
};

tc_fbo_pool* tc_fbo_pool_create(void) {
    tc_fbo_pool* pool = (tc_fbo_pool*)calloc(1, sizeof(tc_fbo_pool));
    return pool;
}

void tc_fbo_pool_destroy(tc_fbo_pool* pool) {
    if (!pool) return;

    for (size_t i = 0; i < pool->count; i++) {
        free(pool->entries[i].key);
        free(pool->entries[i].format);
        if (!pool->entries[i].external && pool->entries[i].fbo && g_render_ops.destroy_fbo) {
            g_render_ops.destroy_fbo(pool->entries[i].fbo);
        }
    }
    free(pool);
}

static tc_fbo_entry* find_entry(tc_fbo_pool* pool, const char* key) {
    for (size_t i = 0; i < pool->count; i++) {
        if (strcmp(pool->entries[i].key, key) == 0) {
            return &pool->entries[i];
        }
    }
    return NULL;
}

void* tc_fbo_pool_ensure(
    tc_fbo_pool* pool,
    const char* key,
    int width,
    int height,
    int samples,
    const char* format
) {
    if (!pool || !key) return NULL;

    tc_fbo_entry* entry = find_entry(pool, key);

    if (entry) {
        // Resize if needed
        if (entry->fbo && (entry->width != width || entry->height != height)) {
            if (g_render_ops.resize_fbo) {
                g_render_ops.resize_fbo(entry->fbo, width, height);
            }
            entry->width = width;
            entry->height = height;
        }
        return entry->fbo;
    }

    // Create new entry
    if (pool->count >= MAX_FBO_ENTRIES) {
        tc_log(TC_LOG_ERROR, "[tc_fbo_pool] Too many FBO entries");
        return NULL;
    }

    entry = &pool->entries[pool->count++];
    entry->key = strdup(key);
    entry->width = width;
    entry->height = height;
    entry->samples = samples;
    entry->format = format ? strdup(format) : NULL;
    entry->external = false;

    if (g_render_ops.create_fbo) {
        entry->fbo = g_render_ops.create_fbo(width, height, samples, format);
    } else {
        entry->fbo = NULL;
    }

    return entry->fbo;
}

void* tc_fbo_pool_get(tc_fbo_pool* pool, const char* key) {
    if (!pool || !key) return NULL;
    tc_fbo_entry* entry = find_entry(pool, key);
    return entry ? entry->fbo : NULL;
}

void tc_fbo_pool_set(tc_fbo_pool* pool, const char* key, void* fbo) {
    if (!pool || !key) return;

    tc_fbo_entry* entry = find_entry(pool, key);
    if (entry) {
        // Don't destroy old external FBO
        if (!entry->external && entry->fbo && g_render_ops.destroy_fbo) {
            g_render_ops.destroy_fbo(entry->fbo);
        }
        entry->fbo = fbo;
        entry->external = true;
        return;
    }

    // Create new entry
    if (pool->count >= MAX_FBO_ENTRIES) {
        tc_log(TC_LOG_ERROR, "[tc_fbo_pool] Too many FBO entries");
        return;
    }

    entry = &pool->entries[pool->count++];
    entry->key = strdup(key);
    entry->fbo = fbo;
    entry->width = 0;
    entry->height = 0;
    entry->samples = 1;
    entry->format = NULL;
    entry->external = true;
}

void tc_fbo_pool_clear(tc_fbo_pool* pool) {
    if (!pool) return;

    for (size_t i = 0; i < pool->count; i++) {
        free(pool->entries[i].key);
        free(pool->entries[i].format);
        if (!pool->entries[i].external && pool->entries[i].fbo && g_render_ops.destroy_fbo) {
            g_render_ops.destroy_fbo(pool->entries[i].fbo);
        }
    }
    pool->count = 0;
}

// ============================================================================
// Resources implementation
// ============================================================================

#define MAX_RESOURCE_ENTRIES 256

typedef struct {
    char* name;
    void* fbo;
} tc_resource_entry;

struct tc_resources {
    tc_resource_entry entries[MAX_RESOURCE_ENTRIES];
    size_t count;
};

static void resources_set(tc_resources* res, const char* name, void* fbo) {
    if (!res || !name) return;

    // Check if exists
    for (size_t i = 0; i < res->count; i++) {
        if (strcmp(res->entries[i].name, name) == 0) {
            res->entries[i].fbo = fbo;
            return;
        }
    }

    // Add new
    if (res->count >= MAX_RESOURCE_ENTRIES) {
        tc_log(TC_LOG_ERROR, "[tc_resources] Too many resource entries");
        return;
    }

    res->entries[res->count].name = strdup(name);
    res->entries[res->count].fbo = fbo;
    res->count++;
}

tc_resources* tc_resources_allocate(
    tc_frame_graph* fg,
    tc_fbo_pool* pool,
    tc_resource_spec* specs,
    size_t spec_count,
    void* target_fbo,
    int width,
    int height
) {
    if (!fg || !pool) return NULL;

    tc_resources* res = (tc_resources*)calloc(1, sizeof(tc_resources));
    if (!res) return NULL;

    // Set OUTPUT and DISPLAY to target
    resources_set(res, "OUTPUT", target_fbo);
    resources_set(res, "DISPLAY", target_fbo);

    // Get canonical resources from frame graph
    const char* canonical_names[256];
    size_t canon_count = tc_frame_graph_get_canonical_resources(fg, canonical_names, 256);

    for (size_t i = 0; i < canon_count; i++) {
        const char* canon = canonical_names[i];

        // Skip DISPLAY/OUTPUT
        if (strcmp(canon, "DISPLAY") == 0 || strcmp(canon, "OUTPUT") == 0) {
            // Get all aliases and set to target
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count; j++) {
                resources_set(res, aliases[j], target_fbo);
            }
            continue;
        }

        // Find spec for this resource
        tc_resource_spec* spec = NULL;
        for (size_t j = 0; j < spec_count; j++) {
            if (strcmp(specs[j].resource, canon) == 0) {
                spec = &specs[j];
                break;
            }
        }

        // If no spec by canonical name, try aliases
        if (!spec) {
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count && !spec; j++) {
                for (size_t k = 0; k < spec_count; k++) {
                    if (strcmp(specs[k].resource, aliases[j]) == 0) {
                        spec = &specs[k];
                        break;
                    }
                }
            }
        }

        // Determine resource type
        const char* resource_type = "fbo";
        if (spec && spec->resource_type[0] != '\0') {
            resource_type = spec->resource_type;
        }

        // Skip non-FBO resources for now (shadow_map_array etc.)
        if (strcmp(resource_type, "fbo") != 0) {
            const char* aliases[64];
            size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
            for (size_t j = 0; j < alias_count; j++) {
                resources_set(res, aliases[j], NULL);
            }
            continue;
        }

        // Determine size
        int fbo_width = width;
        int fbo_height = height;
        int samples = 1;
        const char* format = "";

        if (spec) {
            if (spec->fixed_width > 0) fbo_width = spec->fixed_width;
            if (spec->fixed_height > 0) fbo_height = spec->fixed_height;
            samples = spec->samples > 0 ? spec->samples : 1;
            format = spec->format;
        }

        // Get or create FBO
        void* fbo = tc_fbo_pool_ensure(pool, canon, fbo_width, fbo_height, samples, format);

        // Set for all aliases
        const char* aliases[64];
        size_t alias_count = tc_frame_graph_get_alias_group(fg, canon, aliases, 64);
        for (size_t j = 0; j < alias_count; j++) {
            resources_set(res, aliases[j], fbo);
        }
    }

    return res;
}

void* tc_resources_get(tc_resources* res, const char* name) {
    if (!res || !name) return NULL;

    for (size_t i = 0; i < res->count; i++) {
        if (strcmp(res->entries[i].name, name) == 0) {
            return res->entries[i].fbo;
        }
    }
    return NULL;
}

void tc_resources_destroy(tc_resources* res) {
    if (!res) return;

    for (size_t i = 0; i < res->count; i++) {
        free(res->entries[i].name);
    }
    free(res);
}

// ============================================================================
// Render execution
// ============================================================================

void tc_render_execute_pass(
    tc_pass* pass,
    tc_resources* resources,
    tc_execute_context* base_ctx
) {
    if (!pass || !resources || !base_ctx) return;

    // Build reads/writes FBO maps
    const char* reads[16];
    const char* writes[8];
    size_t read_count = tc_pass_get_reads(pass, reads, 16);
    size_t write_count = tc_pass_get_writes(pass, writes, 8);

    // Create context with resolved FBOs
    tc_execute_context ctx = *base_ctx;

    // For now, store resolved FBOs in a simple way
    // In real implementation, this would be a proper map
    void* read_fbos[16];
    void* write_fbos[8];

    for (size_t i = 0; i < read_count; i++) {
        read_fbos[i] = tc_resources_get(resources, reads[i]);
    }
    for (size_t i = 0; i < write_count; i++) {
        write_fbos[i] = tc_resources_get(resources, writes[i]);
    }

    ctx.reads_fbos = read_fbos;
    ctx.writes_fbos = write_fbos;

    // Execute pass
    tc_pass_execute(pass, &ctx);
}

void tc_render_pipeline(
    tc_pipeline* pipeline,
    tc_fbo_pool* pool,
    void* target_fbo,
    int width,
    int height,
    tc_scene* scene,
    void* camera,
    void* graphics
) {
    if (!pipeline || !pool) return;

    // Build frame graph
    tc_frame_graph* fg = tc_frame_graph_build(pipeline);
    if (!fg) {
        tc_log(TC_LOG_ERROR, "[tc_render_pipeline] Failed to build frame graph");
        return;
    }

    if (tc_frame_graph_get_error(fg) != TC_FG_OK) {
        tc_log(TC_LOG_ERROR, "[tc_render_pipeline] Frame graph error: %s",
               tc_frame_graph_get_error_message(fg));
        tc_frame_graph_destroy(fg);
        return;
    }

    // Collect resource specs from passes
    tc_resource_spec specs[128];
    size_t spec_count = tc_pipeline_collect_specs(pipeline, specs, 128);

    // Allocate resources
    tc_resources* resources = tc_resources_allocate(
        fg, pool, specs, spec_count, target_fbo, width, height
    );

    if (!resources) {
        tc_log(TC_LOG_ERROR, "[tc_render_pipeline] Failed to allocate resources");
        tc_frame_graph_destroy(fg);
        return;
    }

    // Clear resources according to specs
    for (size_t i = 0; i < spec_count; i++) {
        tc_resource_spec* spec = &specs[i];
        if (strcmp(spec->resource_type, "fbo") != 0) continue;
        if (!spec->has_clear_color && !spec->has_clear_depth) continue;

        void* fbo = tc_resources_get(resources, spec->resource);
        if (!fbo) continue;

        if (g_render_ops.bind_fbo) g_render_ops.bind_fbo(fbo);

        int fb_w = spec->fixed_width > 0 ? spec->fixed_width : width;
        int fb_h = spec->fixed_height > 0 ? spec->fixed_height : height;
        if (g_render_ops.set_viewport) g_render_ops.set_viewport(0, 0, fb_w, fb_h);

        if (spec->has_clear_color && spec->has_clear_depth && g_render_ops.clear_color_depth) {
            g_render_ops.clear_color_depth(
                spec->clear_color[0], spec->clear_color[1],
                spec->clear_color[2], spec->clear_color[3]
            );
        } else if (spec->has_clear_color && g_render_ops.clear_color) {
            g_render_ops.clear_color(
                spec->clear_color[0], spec->clear_color[1],
                spec->clear_color[2], spec->clear_color[3]
            );
        } else if (spec->has_clear_depth && g_render_ops.clear_depth) {
            g_render_ops.clear_depth(spec->clear_depth);
        }
    }

    // Execute passes
    size_t schedule_count = tc_frame_graph_schedule_count(fg);

    tc_execute_context base_ctx = {0};
    base_ctx.graphics = graphics;
    base_ctx.rect_x = 0;
    base_ctx.rect_y = 0;
    base_ctx.rect_width = width;
    base_ctx.rect_height = height;
    base_ctx.scene = scene;
    base_ctx.camera = camera;
    base_ctx.layer_mask = 0xFFFFFFFFFFFFFFFF;

    for (size_t i = 0; i < schedule_count; i++) {
        tc_pass* pass = tc_frame_graph_schedule_at(fg, i);
        if (!pass) continue;

        if (g_render_ops.reset_state) g_render_ops.reset_state();

        tc_render_execute_pass(pass, resources, &base_ctx);
    }

    // Cleanup
    tc_resources_destroy(resources);
    tc_frame_graph_destroy(fg);
}
