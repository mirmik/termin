// tc_gpu_context.c - Per-context GPU resource state implementation
#include "tc_gpu_context.h"
#include "tc_gpu.h"
#include "tc_log.h"
#include <stdlib.h>
#include <string.h>

// Thread-local current GPU context
static _Thread_local tc_gpu_context* g_current_gpu_context = NULL;

// Defined in tc_gpu.c — we update it for backward compatibility
extern _Thread_local uintptr_t g_current_context_key;

// ============================================================================
// Internal: grow array to fit index
// ============================================================================

static bool ensure_slot_capacity(
    void** array,
    uint32_t* capacity,
    uint32_t required_index,
    size_t item_size,
    int32_t init_version
) {
    if (required_index < *capacity) {
        return true;
    }

    uint32_t new_cap = *capacity;
    if (new_cap == 0) new_cap = 64;
    while (new_cap <= required_index) {
        new_cap *= 2;
    }

    void* new_array = realloc(*array, new_cap * item_size);
    if (!new_array) {
        tc_log(TC_LOG_ERROR, "tc_gpu_context: realloc failed (cap %u -> %u)", *capacity, new_cap);
        return false;
    }

    // Zero-init new slots
    memset((char*)new_array + (*capacity) * item_size, 0,
           (new_cap - *capacity) * item_size);

    // Set version = -1 for new slots
    if (init_version == -1) {
        if (item_size == sizeof(tc_gpu_slot)) {
            tc_gpu_slot* slots = (tc_gpu_slot*)new_array;
            for (uint32_t i = *capacity; i < new_cap; i++) {
                slots[i].version = -1;
            }
        } else if (item_size == sizeof(tc_gpu_mesh_slot)) {
            tc_gpu_mesh_slot* slots = (tc_gpu_mesh_slot*)new_array;
            for (uint32_t i = *capacity; i < new_cap; i++) {
                slots[i].version = -1;
            }
        }
    }

    *array = new_array;
    *capacity = new_cap;
    return true;
}

// ============================================================================
// Lifecycle
// ============================================================================

tc_gpu_context* tc_gpu_context_new(uintptr_t key) {
    tc_gpu_context* ctx = (tc_gpu_context*)calloc(1, sizeof(tc_gpu_context));
    if (!ctx) {
        tc_log(TC_LOG_ERROR, "tc_gpu_context_new: alloc failed");
        return NULL;
    }
    ctx->key = key;
    ctx->owns_shared_resources = true;
    return ctx;
}

void tc_gpu_context_free(tc_gpu_context* ctx) {
    if (!ctx) return;

    const tc_gpu_ops* ops = tc_gpu_get_ops();

    if (ops) {
        // Always delete per-context VAOs
        for (uint32_t i = 0; i < ctx->mesh_capacity; i++) {
            if (ctx->meshes[i].vao != 0 && ops->mesh_delete) {
                ops->mesh_delete(ctx->meshes[i].vao);
            }
        }

        // Shared resources only from primary context
        if (ctx->owns_shared_resources) {
            for (uint32_t i = 0; i < ctx->texture_capacity; i++) {
                if (ctx->textures[i].gl_id != 0 && ops->texture_delete) {
                    ops->texture_delete(ctx->textures[i].gl_id);
                }
            }
            for (uint32_t i = 0; i < ctx->shader_capacity; i++) {
                if (ctx->shaders[i].gl_id != 0 && ops->shader_delete) {
                    ops->shader_delete(ctx->shaders[i].gl_id);
                }
            }
            for (uint32_t i = 0; i < ctx->mesh_capacity; i++) {
                if (ctx->meshes[i].vbo != 0 && ops->buffer_delete) {
                    ops->buffer_delete(ctx->meshes[i].vbo);
                }
                if (ctx->meshes[i].ebo != 0 && ops->buffer_delete) {
                    ops->buffer_delete(ctx->meshes[i].ebo);
                }
            }
        }

        // Backend-specific resources (VAOs are per-context, VBOs may be shared)
        if (ctx->backend_ui_vao != 0 && ops->mesh_delete) {
            ops->mesh_delete(ctx->backend_ui_vao);
        }
        if (ctx->backend_immediate_vao != 0 && ops->mesh_delete) {
            ops->mesh_delete(ctx->backend_immediate_vao);
        }
        if (ctx->owns_shared_resources) {
            if (ctx->backend_ui_vbo != 0 && ops->buffer_delete) {
                ops->buffer_delete(ctx->backend_ui_vbo);
            }
            if (ctx->backend_immediate_vbo != 0 && ops->buffer_delete) {
                ops->buffer_delete(ctx->backend_immediate_vbo);
            }
        }
    }

    free(ctx->textures);
    free(ctx->shaders);
    free(ctx->meshes);
    free(ctx);
}

// ============================================================================
// Thread-local current context
// ============================================================================

void tc_gpu_set_context(tc_gpu_context* ctx) {
    g_current_gpu_context = ctx;
    // Backward compatibility: update legacy context key
    g_current_context_key = ctx ? ctx->key : 0;
}

tc_gpu_context* tc_gpu_get_context(void) {
    return g_current_gpu_context;
}

// ============================================================================
// Slot access
// ============================================================================

tc_gpu_slot* tc_gpu_context_texture_slot(tc_gpu_context* ctx, uint32_t index) {
    if (!ctx) return NULL;
    if (!ensure_slot_capacity(
            (void**)&ctx->textures, &ctx->texture_capacity,
            index, sizeof(tc_gpu_slot), -1)) {
        return NULL;
    }
    return &ctx->textures[index];
}

tc_gpu_slot* tc_gpu_context_shader_slot(tc_gpu_context* ctx, uint32_t index) {
    if (!ctx) return NULL;
    if (!ensure_slot_capacity(
            (void**)&ctx->shaders, &ctx->shader_capacity,
            index, sizeof(tc_gpu_slot), -1)) {
        return NULL;
    }
    return &ctx->shaders[index];
}

tc_gpu_mesh_slot* tc_gpu_context_mesh_slot(tc_gpu_context* ctx, uint32_t index) {
    if (!ctx) return NULL;
    if (!ensure_slot_capacity(
            (void**)&ctx->meshes, &ctx->mesh_capacity,
            index, sizeof(tc_gpu_mesh_slot), -1)) {
        return NULL;
    }
    return &ctx->meshes[index];
}
