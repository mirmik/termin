#pragma once

#include <string>
#include <utility>
#include <vector>

#include <tc_value.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/line_batch_render_item.hpp>
#include <termin/render/render_item_submission.hpp>
#include <tgfx/tgfx_material_handle.hpp>

namespace termin {

    class ENTITY_API LineRenderer : public Component, public Drawable {
    public:
        TcMaterial material;
        float width = 0.1f;
        bool cast_shadow = false;
        int tube_sides = 6;

    private:
        std::vector<tc_vec3> points_;

        static TcMaterial default_material();
        TcMaterial effective_material() const;

    public:
        explicit LineRenderer(const char* type_name = "LineRenderer");
        ~LineRenderer() override;

        static void register_type();

        const std::vector<tc_vec3>& points() const {
            return points_;
        }
        void set_points(const std::vector<tc_vec3>& points);
        void set_points(std::vector<tc_vec3>&& points);
        void clear_points();
        void add_point(const tc_vec3& point);
        void set_segment(const tc_vec3& start, const tc_vec3& end);
        void set_width(float value);
        void set_cast_shadow(bool value);
        void set_tube_sides(int value);
        void set_material(const TcMaterial& value);
        void set_material_by_name(const std::string& name);

        tc_value serialize_points() const;
        void deserialize_points(const tc_value* value);
        tc_value serialize_data() const override;
        void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;

        tc_phase_mask get_phase_mask() const override;
        bool collect_render_items(const tc_render_item_collect_context& context, tc_render_item_sink& sink) override;
        bool encode_render_item_tgfx2(tgfx::RenderContext2& ctx2,
                                      const tc_render_item& item,
                                      const RenderItemDrawSubmitRequest& request);
    };

} // namespace termin
