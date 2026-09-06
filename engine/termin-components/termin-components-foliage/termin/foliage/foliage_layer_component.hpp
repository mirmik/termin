#pragma once

#include <string>
#include <array>
#include <optional>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/export.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/render_context.hpp>
#include <termin/render/render_item_submission.hpp>
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

        // Explicit simulation time: rendering never advances or samples a wall clock.
        // Prototype roots are at local Z=0; height controls the bend envelope.
        double motion_time = 0.0;
        double prototype_height = 1.0;
        double wind_strength = 0.0;
        double wind_speed = 1.5;
        double wind_wavelength = 8.0;
        double wind_direction_degrees = 0.0;
        double interaction_x = 0.0;
        double interaction_y = 0.0;
        double interaction_z = 0.0;
        double interaction_radius = 0.0;
        double interaction_strength = 0.0;

        FoliageLayerComponent();

        static void register_type();

        // Conservative world bounds for placement, scaled prototype and maximum
        // motion. Not yet consumed by the render collector (which draws all batches).
        std::optional<std::array<float, 6>> compute_world_bounds() const;

        tc_phase_mask get_phase_mask() const override;
        bool collect_render_items(const tc_render_item_collect_context& context, tc_render_item_sink& sink) override;
        bool encode_render_item_tgfx2(tgfx::RenderContext2& ctx2,
                                      const tc_render_item& item,
                                      const RenderItemDrawSubmitRequest& request);
    };

} // namespace termin
