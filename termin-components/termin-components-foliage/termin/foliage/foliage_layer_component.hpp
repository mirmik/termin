#pragma once

#include <string>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/export.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/render/render_context.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

namespace termin {

class ENTITY_API FoliageLayerComponent : public CxxComponent, public Drawable {
public:
    bool enabled = true;
    std::string foliage_uuid;
    TcMesh prototype_mesh;
    TcMaterial material;
    std::string layer_name = "foliage";
    double density = 1.0;
    double min_spacing = 0.25;
    double scale_min = 1.0;
    double scale_max = 1.0;
    double slope_limit_degrees = 50.0;

    FoliageLayerComponent();

    static void register_type();

    tc_phase_mask get_phase_mask() const override;
    bool collect_render_items(
        const tc_render_item_collect_context& context,
        tc_render_item_sink& sink
    ) override;
    bool encode_render_item_tgfx2(
        tgfx::RenderContext2& ctx2,
        const tc_render_item& item,
        const RenderItemDrawSubmitRequest& request);
};

} // namespace termin
