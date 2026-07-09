#pragma once

#include <cstddef>
#include <functional>
#include <string>

#include <termin/geom/mat44.hpp>
#include <termin/render/drawable.hpp>
#include <tgfx/tgfx_material_handle.hpp>

extern "C" {
#include <core/tc_component.h>
#include <core/tc_render_item.h>
}

namespace termin {

enum class LineRenderMode {
    WorldBillboard = 0,
    ScreenSpace = 1,
    WorldMesh = 2,
    RawLines = 3,
    WorldTube = 4,
};

struct ENTITY_API LineBatchRenderItemDesc {
    const tc_vec3* points = nullptr;
    size_t point_count = 0;
    TcMaterial material;
    TcMaterial shadow_fallback_material;
    float width = 0.1f;
    LineRenderMode render_mode = LineRenderMode::WorldBillboard;
    bool cast_shadow = false;
    tc_vec3 up_hint = {0.0, 1.0, 0.0};
    int tube_sides = 6;
    int geometry_id = 0;
    Mat44f model_matrix = Mat44f::identity();
    bool has_override_color = false;
    tc_render_item_vec4 override_color{1.0, 1.0, 1.0, 1.0};
};

ENTITY_API bool emit_line_batch_render_items(
    tc_component* component,
    const tc_render_item_collect_context& context,
    tc_render_item_sink& sink,
    const LineBatchRenderItemDesc& desc);

ENTITY_API TcShader override_line_batch_shader(
    const ShaderOverrideContext& context,
    LineRenderMode mode,
    bool cast_shadow);

ENTITY_API void collect_line_batch_shader_usages(
    const ShaderOverrideContext& context,
    LineRenderMode mode,
    bool cast_shadow,
    const std::function<void(TcShader)>& emit);

ENTITY_API bool line_batch_needs_lighting_ubo_tgfx2(
    const std::string& phase_mark,
    LineRenderMode mode,
    bool cast_shadow);

} // namespace termin
