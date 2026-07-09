#pragma once

#include <memory>
#include <set>
#include <string>
#include <vector>

#include <tc_value.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/geom/vec4.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/render_item_submission.hpp>
#include <tgfx/tgfx_material_handle.hpp>

namespace tgfx {
class FontAtlas;
class Text3DRenderer;
} // namespace tgfx

namespace termin {

enum class WorldTextAnchor {
    Left = 0,
    Center = 1,
    Right = 2,
};

enum class WorldTextOrientation {
    Billboard = 0,
    Fixed = 1,
};

class ENTITY_API WorldTextComponent : public Component, public Drawable {
public:
    std::string text = "";
    std::string font_path = "";
    std::string phase_mark = "transparent";
    Vec3 local_offset{0.0, 0.0, 0.0};
    Vec3 plane_normal{0.0, 0.0, 1.0};
    Vec3 text_up{0.0, 1.0, 0.0};
    Vec4 color{1.0, 1.0, 1.0, 1.0};
    float size = 0.35f;
    WorldTextAnchor anchor = WorldTextAnchor::Center;
    WorldTextOrientation orientation = WorldTextOrientation::Billboard;
    int priority = 0;
    bool depth_test = true;
    bool depth_write = false;
    bool blend = true;
    bool cull = false;

private:
    mutable TcMaterial material_;
    mutable std::unique_ptr<tgfx::FontAtlas> font_;
    mutable std::string loaded_font_path_;
    mutable std::unique_ptr<tgfx::Text3DRenderer> renderer_;

    TcMaterial effective_material() const;
    tc_material_phase* sync_material_phase() const;
    tgfx::FontAtlas* ensure_font(const char* captured_font_path) const;

public:
    explicit WorldTextComponent(const char* type_name = "WorldTextComponent");
    ~WorldTextComponent() override;

    static void register_type();

    void set_text(const std::string& value);
    void set_font_path(const std::string& value);
    void set_phase_mark(const std::string& value);
    void set_local_offset(const Vec3& value);
    void set_plane_normal(const Vec3& value);
    void set_text_up(const Vec3& value);
    void set_color(const Vec4& value);
    void set_size(float value);
    void set_anchor(WorldTextAnchor value);
    void set_orientation(WorldTextOrientation value);
    void set_priority(int value);
    void set_depth_test(bool value);
    void set_depth_write(bool value);
    void set_blend(bool value);
    void set_cull(bool value);

    std::string anchor_name() const;
    void set_anchor_name(const std::string& value);
    std::string orientation_name() const;
    void set_orientation_name(const std::string& value);

    tc_value serialize_data() const override;
    void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;

    std::set<std::string> get_phase_marks() const override;
    std::set<std::string> phase_marks() const { return get_phase_marks(); }
    void collect_shader_usages(
        const std::string& phase_mark,
        int geometry_id,
        TcShader original_shader,
        const std::function<void(TcShader)>& emit
    ) override;
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
