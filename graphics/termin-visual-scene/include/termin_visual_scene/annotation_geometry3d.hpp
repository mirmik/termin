#pragma once

#include "termin_visual_scene/tc_visual_annotation3d.h"
#include <termin/geom/mat44.hpp>
#include <vector>

namespace termin::visual {

    // Append an ordered overlay packet to the tgfx2 immediate triangle stream.
    // Output is in Termin clip coordinates and uses linear RGBA, including
    // fractional pixel coverage. Flush with identity view and projection.
    TERMIN_VISUAL_SCENE_API void append_annotation_triangles(std::vector<float>& vertices,
                                                             const tc_visual_annotation_packet3d& packet,
                                                             const tc_affine3d& world_from_local,
                                                             const Mat44& view_projection,
                                                             uint32_t width,
                                                             uint32_t height,
                                                             float pixels_per_dip);
} // namespace termin::visual
