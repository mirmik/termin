#pragma once

#include <cstddef>
#include <string>

#include <termin/geom/mat44.hpp>
#include <termin/geom/color.hpp>
#include <termin/render/drawable.hpp>
#include <tgfx/tgfx_material_handle.hpp>

extern "C" {
#include <core/tc_component.h>
#include <core/tc_render_item.h>
}

namespace termin {

    struct ENTITY_API LineBatchRenderItemDesc {
        const tc_vec3* points = nullptr;
        size_t point_count = 0;
        TcMaterial material;
        TcMaterial shadow_fallback_material;
        float width = 0.1f;
        bool cast_shadow = false;
        int tube_sides = 6;
        int geometry_id = 0;
        Mat44f model_matrix = Mat44f::identity();
        bool has_override_color = false;
        // Internal render-item override (for example an ID-pass value), already
        // in the GPU-ready linear domain. This is not an authored color API.
        LinearColor override_color{1.0f, 1.0f, 1.0f, 1.0f};
    };

    ENTITY_API bool emit_line_batch_render_items(tc_component* component,
                                                 const tc_render_item_collect_context& context,
                                                 tc_render_item_sink& sink,
                                                 const LineBatchRenderItemDesc& desc);

} // namespace termin
