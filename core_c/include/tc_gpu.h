// tc_gpu.h - GPU operations vtable
// Allows core_c to perform GPU operations via callbacks from rendering backend
#pragma once

#include "tc_types.h"
#include "tc_texture.h"
#include "tc_shader.h"
#include "tc_mesh.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// GPU Operations vtable
// ============================================================================

typedef struct tc_gpu_ops {
    // Texture operations
    // Upload texture to GPU, returns GPU texture ID (0 on failure)
    uint32_t (*texture_upload)(
        const uint8_t* data,
        int width,
        int height,
        int channels,
        bool mipmap,
        bool clamp
    );

    // Bind texture to unit
    void (*texture_bind)(uint32_t gpu_id, int unit);

    // Delete GPU texture
    void (*texture_delete)(uint32_t gpu_id);

    // Shader operations
    // Compile shader, returns GPU program ID (0 on failure)
    uint32_t (*shader_compile)(
        const char* vertex_source,
        const char* fragment_source,
        const char* geometry_source  // may be NULL
    );

    // Use shader program
    void (*shader_use)(uint32_t gpu_id);

    // Delete shader program
    void (*shader_delete)(uint32_t gpu_id);

    // Mesh operations
    // Upload mesh to GPU, returns GPU VAO ID (0 on failure)
    uint32_t (*mesh_upload)(const tc_mesh* mesh);

    // Draw mesh
    void (*mesh_draw)(uint32_t gpu_id);

    // Delete GPU mesh
    void (*mesh_delete)(uint32_t gpu_id);

    // User data (passed to callbacks if needed)
    void* user_data;
} tc_gpu_ops;

// ============================================================================
// GPU ops registration
// ============================================================================

// Set the GPU operations vtable (called by rendering backend during init)
TC_API void tc_gpu_set_ops(const tc_gpu_ops* ops);

// Get current GPU operations vtable (returns NULL if not set)
TC_API const tc_gpu_ops* tc_gpu_get_ops(void);

// Check if GPU ops are available
TC_API bool tc_gpu_available(void);

// ============================================================================
// Texture GPU operations
// ============================================================================

// Bind texture to unit, uploading if needed
// Returns true if bind succeeded
TC_API bool tc_texture_bind_gpu(tc_texture* tex, int unit);

// Force re-upload texture to GPU
TC_API bool tc_texture_upload_gpu(tc_texture* tex);

// Delete texture from GPU (keeps CPU data)
TC_API void tc_texture_delete_gpu(tc_texture* tex);

// Check if texture needs GPU upload (version mismatch)
TC_API bool tc_texture_needs_upload(const tc_texture* tex);

// ============================================================================
// Shader GPU operations
// ============================================================================

// Compile shader if not already compiled
// Returns GPU program ID (0 on failure)
TC_API uint32_t tc_shader_compile_gpu(tc_shader* shader);

// Use shader program
TC_API void tc_shader_use_gpu(tc_shader* shader);

// Delete shader from GPU
TC_API void tc_shader_delete_gpu(tc_shader* shader);

// ============================================================================
// Mesh GPU operations
// ============================================================================

// Upload mesh to GPU if not already uploaded
// Returns GPU VAO ID (0 on failure)
TC_API uint32_t tc_mesh_upload_gpu(tc_mesh* mesh);

// Draw mesh (must be uploaded first)
TC_API void tc_mesh_draw_gpu(tc_mesh* mesh);

// Delete mesh from GPU
TC_API void tc_mesh_delete_gpu(tc_mesh* mesh);

#ifdef __cplusplus
}
#endif
