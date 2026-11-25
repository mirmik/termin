#pragma once

#include "termin_visual_scene/tc_visual_scene3d.h"

#ifdef __cplusplus
extern "C" {
#endif

enum tc_visual_annotation_kind3d {
    TC_VISUAL_ANNOTATION_LINE = 0,
    TC_VISUAL_ANNOTATION_ARROW = 1,
    TC_VISUAL_ANNOTATION_DISC = 2,
    TC_VISUAL_ANNOTATION_RING = 3,
    TC_VISUAL_ANNOTATION_QUAD = 4,
};

// Points are local XYZ anchors. A line or arrow uses two, a marker uses
// one, and a filled convex quad uses four in perimeter order. Width,
// marker radius (ring centerline), and maximum arrowhead length are in DIPs.
// rgba is packed 0xRRGGBBAA, sRGB with straight alpha.
typedef struct tc_visual_annotation3d {
    uint32_t kind;
    uint32_t rgba;
    float points[4][3];
    float width_dip;
    float radius_dip;
    float head_dip;
} tc_visual_annotation3d;

#define TC_VISUAL_ANNOTATION_PROTOCOL_3D "termin.visual.annotation.v1"

// Commands are submitted in painter's order and borrowed during submit.
typedef struct tc_visual_annotation_packet3d {
    const tc_visual_annotation3d* commands;
    size_t count;
} tc_visual_annotation_packet3d;

// Creates an empty item owned by the scene. Use the standard item API for
// visibility, parenting, transforms, and destruction.
TERMIN_VISUAL_SCENE_API tc_visual_item3d_handle tc_visual_annotation_item3d_create(tc_visual_scene3d_handle scene);

// Copies the batch. A count of zero clears it. On failure the old batch
// remains available. Like the scene, mutation and painting are serialized
// by the caller.
TERMIN_VISUAL_SCENE_API bool tc_visual_annotation_item3d_set(tc_visual_scene3d_handle scene,
                                                             tc_visual_item3d_handle item,
                                                             const tc_visual_annotation3d* commands,
                                                             size_t count);

#ifdef __cplusplus
}
#endif
