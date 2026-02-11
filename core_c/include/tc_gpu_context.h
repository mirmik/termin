// tc_gpu_context.h - Per-context GPU resource state
// Stores GL object IDs for each OpenGL context (textures, shaders, mesh VAOs/VBOs)
#pragma once

#include "tc_types.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// GPU resource slots (per-resource, per-context state)
// ============================================================================

// Slot for texture or shader: one GL ID + version for staleness check
typedef struct tc_gpu_slot {
    uint32_t gl_id;
    int32_t  version;    // -1 = never uploaded
} tc_gpu_slot;

// Slot for mesh: VAO is per-context, VBO/EBO may be shared
typedef struct tc_gpu_mesh_slot {
    uint32_t vao;
    uint32_t vbo;
    uint32_t ebo;
    int32_t  version;    // -1 = never uploaded
} tc_gpu_mesh_slot;

// ============================================================================
// GPU Context
// ============================================================================

// Holds all GL resource IDs for one OpenGL context.
// Indexed by pool_index of each resource.
typedef struct tc_gpu_context {
    // Texture GL IDs indexed by texture pool index
    tc_gpu_slot* textures;
    uint32_t texture_capacity;

    // Shader program IDs indexed by shader pool index
    tc_gpu_slot* shaders;
    uint32_t shader_capacity;

    // Mesh VAO/VBO/EBO indexed by mesh pool index
    tc_gpu_mesh_slot* meshes;
    uint32_t mesh_capacity;

    // Backend-specific resources (UI drawing, immediate mode)
    uint32_t backend_ui_vao;
    uint32_t backend_ui_vbo;
    uint32_t backend_immediate_vao;
    uint32_t backend_immediate_vbo;

    // Context identity (same as render surface context key)
    uintptr_t key;

    // If true, this context owns shared GL resources (textures, shaders, VBO/EBO).
    // Only the primary context should delete them; secondary contexts only delete VAOs.
    bool owns_shared_resources;
} tc_gpu_context;

// ============================================================================
// Lifecycle
// ============================================================================

// Create new GPU context with given key. All slots start empty.
TC_API tc_gpu_context* tc_gpu_context_new(uintptr_t key);

// Destroy GPU context and free all associated GL resources.
// Must be called with the corresponding GL context active.
TC_API void tc_gpu_context_free(tc_gpu_context* ctx);

// ============================================================================
// Thread-local current context
// ============================================================================

// Set current GPU context for this thread (call after glMakeCurrent).
TC_API void tc_gpu_set_context(tc_gpu_context* ctx);

// Get current GPU context (NULL if not set).
TC_API tc_gpu_context* tc_gpu_get_context(void);

// ============================================================================
// Slot access (auto-grow arrays if needed)
// ============================================================================

// Get texture slot for given pool index. Grows array if needed.
TC_API tc_gpu_slot* tc_gpu_context_texture_slot(tc_gpu_context* ctx, uint32_t index);

// Get shader slot for given pool index. Grows array if needed.
TC_API tc_gpu_slot* tc_gpu_context_shader_slot(tc_gpu_context* ctx, uint32_t index);

// Get mesh slot for given pool index. Grows array if needed.
TC_API tc_gpu_mesh_slot* tc_gpu_context_mesh_slot(tc_gpu_context* ctx, uint32_t index);

#ifdef __cplusplus
}
#endif
