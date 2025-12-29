// tc_mesh.h - Mesh data structures with flexible vertex layouts
#pragma once

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Vertex attribute types
// ============================================================================

typedef enum tc_attrib_type {
    TC_ATTRIB_FLOAT32 = 0,
    TC_ATTRIB_INT32   = 1,
    TC_ATTRIB_UINT32  = 2,
    TC_ATTRIB_INT16   = 3,
    TC_ATTRIB_UINT16  = 4,
    TC_ATTRIB_INT8    = 5,
    TC_ATTRIB_UINT8   = 6,
} tc_attrib_type;

// ============================================================================
// Vertex attribute descriptor
// ============================================================================

#define TC_ATTRIB_NAME_MAX 32
#define TC_VERTEX_ATTRIBS_MAX 8

typedef struct tc_vertex_attrib {
    char name[TC_ATTRIB_NAME_MAX];  // "position", "normal", "uv", "color", ...
    uint8_t size;                    // number of components: 1, 2, 3, 4
    uint8_t type;                    // tc_attrib_type
    uint16_t offset;                 // byte offset from vertex start
} tc_vertex_attrib;

// ============================================================================
// Vertex layout - describes vertex format
// ============================================================================

typedef struct tc_vertex_layout {
    uint16_t stride;                              // bytes per vertex
    uint8_t attrib_count;                         // number of attributes
    uint8_t _pad;
    tc_vertex_attrib attribs[TC_VERTEX_ATTRIBS_MAX];
} tc_vertex_layout;

// ============================================================================
// Mesh data
// ============================================================================

typedef struct tc_mesh {
    void* vertices;              // raw vertex data blob
    size_t vertex_count;
    uint32_t* indices;           // triangle indices (3 per triangle)
    size_t index_count;          // total indices (not triangles)
    tc_vertex_layout layout;
    uint32_t version;            // incremented on data change (for GPU sync)
    uint32_t ref_count;          // reference count for ownership
    char uuid[40];               // unique identifier (hash of data)
    const char* name;            // human-readable name for debugging (interned string)
} tc_mesh;

// ============================================================================
// Mesh helper functions
// ============================================================================

// Get size in bytes of an attribute type
TC_API size_t tc_attrib_type_size(tc_attrib_type type);

// Calculate total vertex data size
static inline size_t tc_mesh_vertices_size(const tc_mesh* mesh) {
    return mesh->vertex_count * mesh->layout.stride;
}

// Calculate total index data size
static inline size_t tc_mesh_indices_size(const tc_mesh* mesh) {
    return mesh->index_count * sizeof(uint32_t);
}

// Get triangle count
static inline size_t tc_mesh_triangle_count(const tc_mesh* mesh) {
    return mesh->index_count / 3;
}

// ============================================================================
// Vertex layout builder helpers
// ============================================================================

// Initialize empty layout
TC_API void tc_vertex_layout_init(tc_vertex_layout* layout);

// Add attribute to layout (updates stride automatically)
// Returns false if max attributes reached
TC_API bool tc_vertex_layout_add(
    tc_vertex_layout* layout,
    const char* name,
    uint8_t size,
    tc_attrib_type type
);

// Find attribute by name, returns NULL if not found
TC_API const tc_vertex_attrib* tc_vertex_layout_find(
    const tc_vertex_layout* layout,
    const char* name
);

// ============================================================================
// Predefined layouts
// ============================================================================

// Position only: vec3 position
TC_API tc_vertex_layout tc_vertex_layout_pos(void);

// Position + Normal: vec3 position, vec3 normal
TC_API tc_vertex_layout tc_vertex_layout_pos_normal(void);

// Position + Normal + UV (Mesh3 compatible): vec3 position, vec3 normal, vec2 uv
TC_API tc_vertex_layout tc_vertex_layout_pos_normal_uv(void);

// Position + Normal + UV + Color: vec3 position, vec3 normal, vec2 uv, vec4 color
TC_API tc_vertex_layout tc_vertex_layout_pos_normal_uv_color(void);

// Skinned mesh: vec3 position, vec3 normal, vec2 uv, vec4 joints, vec4 weights
TC_API tc_vertex_layout tc_vertex_layout_skinned(void);

// ============================================================================
// Reference counting
// ============================================================================

// Increment reference count
TC_API void tc_mesh_add_ref(tc_mesh* mesh);

// Decrement reference count. Returns true if mesh was destroyed (ref_count reached 0)
TC_API bool tc_mesh_release(tc_mesh* mesh);

// ============================================================================
// UUID computation
// ============================================================================

// Compute UUID from mesh data (FNV-1a hash)
// Result is written to uuid_out (must be at least 40 bytes)
TC_API void tc_mesh_compute_uuid(
    const void* vertices, size_t vertex_size,
    const uint32_t* indices, size_t index_count,
    char* uuid_out
);

#ifdef __cplusplus
}
#endif
