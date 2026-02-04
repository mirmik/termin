#include "resources/tc_mesh.h"
#include "resources/tc_mesh_registry.h"
#include "tc_log.h"
#include <string.h>
#include <stdio.h>

// ============================================================================
// Attribute type helpers
// ============================================================================

size_t tc_attrib_type_size(tc_attrib_type type) {
    switch (type) {
        case TC_ATTRIB_FLOAT32: return 4;
        case TC_ATTRIB_INT32:   return 4;
        case TC_ATTRIB_UINT32:  return 4;
        case TC_ATTRIB_INT16:   return 2;
        case TC_ATTRIB_UINT16:  return 2;
        case TC_ATTRIB_INT8:    return 1;
        case TC_ATTRIB_UINT8:   return 1;
        default:                return 0;
    }
}

// ============================================================================
// Vertex layout functions
// ============================================================================

void tc_vertex_layout_init(tc_vertex_layout* layout) {
    if (!layout) return;
    memset(layout, 0, sizeof(tc_vertex_layout));
}

bool tc_vertex_layout_add(
    tc_vertex_layout* layout,
    const char* name,
    uint8_t size,
    tc_attrib_type type,
    uint8_t location
) {
    if (!layout || !name) return false;
    if (layout->attrib_count >= TC_VERTEX_ATTRIBS_MAX) return false;

    tc_vertex_attrib* attr = &layout->attribs[layout->attrib_count];

    // Copy name (truncate if too long)
    strncpy(attr->name, name, TC_ATTRIB_NAME_MAX - 1);
    attr->name[TC_ATTRIB_NAME_MAX - 1] = '\0';

    attr->size = size;
    attr->type = (uint8_t)type;
    attr->location = location;
    attr->offset = layout->stride;

    // Update stride
    layout->stride += (uint16_t)(size * tc_attrib_type_size(type));
    layout->attrib_count++;

    return true;
}

const tc_vertex_attrib* tc_vertex_layout_find(
    const tc_vertex_layout* layout,
    const char* name
) {
    if (!layout || !name) return NULL;

    for (uint8_t i = 0; i < layout->attrib_count; i++) {
        if (strcmp(layout->attribs[i].name, name) == 0) {
            return &layout->attribs[i];
        }
    }
    return NULL;
}

// ============================================================================
// Predefined layouts
// Standard attribute locations: 0=position, 1=normal, 2=uv, 3=tangent/joints, 4=weights, 5=color
// ============================================================================

tc_vertex_layout tc_vertex_layout_pos(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    return layout;
}

tc_vertex_layout tc_vertex_layout_pos_normal(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "normal", 3, TC_ATTRIB_FLOAT32, 1);
    return layout;
}

tc_vertex_layout tc_vertex_layout_pos_normal_uv(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "normal", 3, TC_ATTRIB_FLOAT32, 1);
    tc_vertex_layout_add(&layout, "uv", 2, TC_ATTRIB_FLOAT32, 2);
    return layout;
}

tc_vertex_layout tc_vertex_layout_pos_normal_uv_tangent(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "normal", 3, TC_ATTRIB_FLOAT32, 1);
    tc_vertex_layout_add(&layout, "uv", 2, TC_ATTRIB_FLOAT32, 2);
    tc_vertex_layout_add(&layout, "tangent", 4, TC_ATTRIB_FLOAT32, 3);
    return layout;
}

tc_vertex_layout tc_vertex_layout_pos_normal_uv_color(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "normal", 3, TC_ATTRIB_FLOAT32, 1);
    tc_vertex_layout_add(&layout, "uv", 2, TC_ATTRIB_FLOAT32, 2);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32, 5);
    return layout;
}

tc_vertex_layout tc_vertex_layout_skinned(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32, 0);
    tc_vertex_layout_add(&layout, "normal", 3, TC_ATTRIB_FLOAT32, 1);
    tc_vertex_layout_add(&layout, "uv", 2, TC_ATTRIB_FLOAT32, 2);
    tc_vertex_layout_add(&layout, "joints", 4, TC_ATTRIB_FLOAT32, 3);
    tc_vertex_layout_add(&layout, "weights", 4, TC_ATTRIB_FLOAT32, 4);
    return layout;
}

// ============================================================================
// Reference counting
// ============================================================================

void tc_mesh_add_ref(tc_mesh* mesh) {
    if (mesh) {
        mesh->header.ref_count++;
    }
}

bool tc_mesh_release(tc_mesh* mesh) {
    if (!mesh) {
        return false;
    }
    if (mesh->header.ref_count == 0) {
        tc_log(TC_LOG_WARN, "[tc_mesh_release] uuid=%s name=%s refcount already zero!",
               mesh->header.uuid, mesh->header.name ? mesh->header.name : "(null)");
        return false;
    }

    mesh->header.ref_count--;

    if (mesh->header.ref_count == 0) {
        tc_mesh_remove(mesh->header.uuid);
        return true;
    }
    return false;
}

// ============================================================================
// UUID computation (FNV-1a hash)
// ============================================================================

static uint64_t fnv1a_hash(const uint8_t* data, size_t len) {
    uint64_t hash = 14695981039346656037ULL;
    for (size_t i = 0; i < len; i++) {
        hash ^= data[i];
        hash *= 1099511628211ULL;
    }
    return hash;
}

void tc_mesh_compute_uuid(
    const void* vertices, size_t vertex_size,
    const uint32_t* indices, size_t index_count,
    char* uuid_out
) {
    // Hash vertices
    uint64_t h1 = fnv1a_hash((const uint8_t*)vertices, vertex_size);

    // Hash indices
    uint64_t h2 = fnv1a_hash((const uint8_t*)indices, index_count * sizeof(uint32_t));

    // Combine hashes
    uint64_t combined = h1 ^ (h2 * 1099511628211ULL);

    // Format as hex string (16 chars)
    snprintf(uuid_out, 40, "%016llx", (unsigned long long)combined);
}
