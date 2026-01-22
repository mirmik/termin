// tc_render.h - High-level render API
#ifndef TC_RENDER_H
#define TC_RENDER_H

#include "tc_pass.h"
#include "tc_pipeline.h"
#include "tc_frame_graph.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// FBO Pool - manages framebuffer allocation and caching
// ============================================================================

typedef struct tc_fbo_pool tc_fbo_pool;

// Create FBO pool with GPU operations
TC_API tc_fbo_pool* tc_fbo_pool_create(void);
TC_API void tc_fbo_pool_destroy(tc_fbo_pool* pool);

// Get or create FBO by key
// Returns opaque FBO handle (actual type depends on graphics backend)
TC_API void* tc_fbo_pool_ensure(
    tc_fbo_pool* pool,
    const char* key,
    int width,
    int height,
    int samples,
    const char* format
);

// Get existing FBO (returns NULL if not found)
TC_API void* tc_fbo_pool_get(tc_fbo_pool* pool, const char* key);

// Set FBO for key (for external FBOs like display)
TC_API void tc_fbo_pool_set(tc_fbo_pool* pool, const char* key, void* fbo);

// Clear all FBOs from pool
TC_API void tc_fbo_pool_clear(tc_fbo_pool* pool);

// ============================================================================
// Resources - FBO mapping from alias groups
// ============================================================================

typedef struct tc_resources tc_resources;

// Allocate resources based on frame graph alias groups
TC_API tc_resources* tc_resources_allocate(
    tc_frame_graph* fg,
    tc_fbo_pool* pool,
    tc_resource_spec* specs,
    size_t spec_count,
    void* target_fbo,
    int width,
    int height
);

// Get FBO for resource name
TC_API void* tc_resources_get(tc_resources* res, const char* name);

// Destroy resources (does not destroy FBOs in pool)
TC_API void tc_resources_destroy(tc_resources* res);

// ============================================================================
// Render execution
// ============================================================================

// Execute render pass with resources
TC_API void tc_render_execute_pass(
    tc_pass* pass,
    tc_resources* resources,
    tc_execute_context* base_ctx
);

// Execute full pipeline
TC_API void tc_render_pipeline(
    tc_pipeline* pipeline,
    tc_fbo_pool* pool,
    void* target_fbo,
    int width,
    int height,
    tc_scene* scene,
    void* camera,
    void* graphics,
    int64_t context_key
);

// ============================================================================
// Callbacks for graphics operations (set by backend)
// ============================================================================

typedef struct {
    // FBO operations
    void* (*create_fbo)(int width, int height, int samples, const char* format);
    void (*destroy_fbo)(void* fbo);
    void (*resize_fbo)(void* fbo, int width, int height);
    void (*bind_fbo)(void* fbo);

    // Clear operations
    void (*clear_color)(float r, float g, float b, float a);
    void (*clear_depth)(float depth);
    void (*clear_color_depth)(float r, float g, float b, float a);

    // State
    void (*set_viewport)(int x, int y, int w, int h);
    void (*reset_state)(void);
} tc_render_ops;

TC_API void tc_render_set_ops(const tc_render_ops* ops);
TC_API const tc_render_ops* tc_render_get_ops(void);

#ifdef __cplusplus
}
#endif

#endif // TC_RENDER_H
