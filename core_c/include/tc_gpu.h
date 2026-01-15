// tc_gpu.h - GPU operations vtable
// Allows core_c to perform GPU operations via callbacks from rendering backend
#pragma once

#include "tc_types.h"
#include "tc_texture.h"
#include "tc_shader.h"
#include "tc_mesh.h"
#include "tc_material.h"

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
    // Preprocess shader source (resolve #include), returns new string (caller frees) or NULL
    char* (*shader_preprocess)(const char* source, const char* source_name);

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

    // Uniform setters (gpu_id must be active program)
    void (*shader_set_int)(uint32_t gpu_id, const char* name, int value);
    void (*shader_set_float)(uint32_t gpu_id, const char* name, float value);
    void (*shader_set_vec2)(uint32_t gpu_id, const char* name, float x, float y);
    void (*shader_set_vec3)(uint32_t gpu_id, const char* name, float x, float y, float z);
    void (*shader_set_vec4)(uint32_t gpu_id, const char* name, float x, float y, float z, float w);
    void (*shader_set_mat4)(uint32_t gpu_id, const char* name, const float* data, bool transpose);
    void (*shader_set_mat4_array)(uint32_t gpu_id, const char* name, const float* data, int count, bool transpose);
    void (*shader_set_block_binding)(uint32_t gpu_id, const char* block_name, int binding_point);

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

// Set shader preprocessor callback (called from Python after fallback loader is set up)
// This is separate from tc_gpu_ops because it needs to be set after module init
typedef char* (*tc_shader_preprocess_fn)(const char* source, const char* source_name);
TC_API void tc_gpu_set_shader_preprocess(tc_shader_preprocess_fn fn);

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

// Uniform setters (shader must be in use)
TC_API void tc_shader_set_int(tc_shader* shader, const char* name, int value);
TC_API void tc_shader_set_float(tc_shader* shader, const char* name, float value);
TC_API void tc_shader_set_vec2(tc_shader* shader, const char* name, float x, float y);
TC_API void tc_shader_set_vec3(tc_shader* shader, const char* name, float x, float y, float z);
TC_API void tc_shader_set_vec4(tc_shader* shader, const char* name, float x, float y, float z, float w);
TC_API void tc_shader_set_mat4(tc_shader* shader, const char* name, const float* data, bool transpose);
TC_API void tc_shader_set_mat4_array(tc_shader* shader, const char* name, const float* data, int count, bool transpose);
TC_API void tc_shader_set_block_binding(tc_shader* shader, const char* block_name, int binding_point);

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

// ============================================================================
// Material GPU operations
// ============================================================================

// Apply material phase for rendering:
// 1. Compile and use shader
// 2. Bind textures
// 3. Apply uniform values
// Returns true if successful
TC_API bool tc_material_phase_apply_gpu(tc_material_phase* phase);

// Apply material uniforms only (shader must already be in use)
TC_API void tc_material_phase_apply_uniforms(tc_material_phase* phase, tc_shader* shader);

// Apply material textures only
TC_API void tc_material_phase_apply_textures(tc_material_phase* phase);

// Apply material phase with MVP matrices (shader must already be in use)
// Sets u_model, u_view, u_projection, binds textures, applies uniforms
TC_API void tc_material_phase_apply_with_mvp(
    tc_material_phase* phase,
    tc_shader* shader,
    const float* model,      // 16 floats
    const float* view,       // 16 floats
    const float* projection  // 16 floats
);

#ifdef __cplusplus
}
#endif
