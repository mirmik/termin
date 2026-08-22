#pragma once

#include <cstdint>
#include <string>

#include <tc_value.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/vec4.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/render/sprite_asset.hpp>
#include <termin/render/world2d_quad_geometry.hpp>

namespace termin {

    class ENTITY_API SpriteRenderer2D : public Component, public Drawable {
    public:
        std::string sprite_uuid;
        Vec4 tint{1.0, 1.0, 1.0, 1.0};
        bool flip_x = false;
        bool flip_y = false;
        int sorting_layer = 0;
        int order_in_layer = 0;
        bool visible = true;

    private:
        mutable uint32_t last_missing_asset_version_ = UINT32_MAX;

        bool resolved_quad(TcSpriteAsset& out_asset,
                           World2DQuadRect& out_rect,
                           float& out_u0,
                           float& out_v0,
                           float& out_u1,
                           float& out_v1) const;

    public:
        explicit SpriteRenderer2D(const char* type_name = "SpriteRenderer2D");
        ~SpriteRenderer2D() override = default;

        static void register_type();

        void set_sprite_uuid(const std::string& value);
        void set_tint(const Vec4& value);
        void set_flip_x(bool value);
        void set_flip_y(bool value);
        void set_sorting_layer(int value);
        void set_order_in_layer(int value);
        void set_visible(bool value);

        tc_value serialize_data() const override;
        void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;

        tc_phase_mask get_phase_mask() const override;
        bool collect_render_items(const tc_render_item_collect_context& context, tc_render_item_sink& sink) override;

        AABB world_bounds() const;
        bool ray_intersects(const Ray3& ray, double* out_ray_parameter = nullptr) const;
    };

} // namespace termin
