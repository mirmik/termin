#include "tc_mesh.h"
#include <string.h>

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
    tc_attrib_type type
) {
    if (!layout || !name) return false;
    if (layout->attrib_count >= TC_VERTEX_ATTRIBS_MAX) return false;

    tc_vertex_attrib* attr = &layout->attribs[layout->attrib_count];

    // Copy name (truncate if too long)
    strncpy(attr->name, name, TC_ATTRIB_NAME_MAX - 1);
    attr->name[TC_ATTRIB_NAME_MAX - 1] = '\0';

    attr->size = size;
    attr->type = (uint8_t)type;
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
// ============================================================================

tc_vertex_layout tc_vertex_layout_pos(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32);
    return layout;
}

tc_vertex_layout tc_vertex_layout_pos_normal(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32);
    tc_vertex_layout_add(&layout, "normal", 3, TC_ATTRIB_FLOAT32);
    return layout;
}

tc_vertex_layout tc_vertex_layout_pos_normal_uv(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32);
    tc_vertex_layout_add(&layout, "normal", 3, TC_ATTRIB_FLOAT32);
    tc_vertex_layout_add(&layout, "uv", 2, TC_ATTRIB_FLOAT32);
    return layout;
}

tc_vertex_layout tc_vertex_layout_pos_normal_uv_color(void) {
    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);
    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32);
    tc_vertex_layout_add(&layout, "normal", 3, TC_ATTRIB_FLOAT32);
    tc_vertex_layout_add(&layout, "uv", 2, TC_ATTRIB_FLOAT32);
    tc_vertex_layout_add(&layout, "color", 4, TC_ATTRIB_FLOAT32);
    return layout;
}
