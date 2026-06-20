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
    tgfx::FontAtlas* ensure_font() const;

public:
    explicit WorldTextComponent(const char* type_name = "WorldTextComponent");
    ~WorldTextComponent() override;

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
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;
    bool draw_tgfx2(tgfx::RenderContext2& ctx2,
                    const RenderContext& context,
                    const std::string& phase_mark,
                    tc_material_phase* phase,
                    int geometry_id = 0) override;
    bool supports_direct_tgfx2_draw(
        const std::string& phase_mark,
        int geometry_id,
        DirectTgfx2DrawKind kind
    ) const override;
    tc_mesh* get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const override;
    std::vector<GeometryDrawCall> get_geometry_draws(const std::string* phase_mark = nullptr) override;
};

INSPECT_FIELD_CALLBACK(WorldTextComponent, std::string, text, "Text", "string",
    [](WorldTextComponent* self) -> std::string& { return self->text; },
    [](WorldTextComponent* self, const std::string& value) { self->set_text(value); })

INSPECT_FIELD_CALLBACK(WorldTextComponent, std::string, font_path, "Font Path", "string",
    [](WorldTextComponent* self) -> std::string& { return self->font_path; },
    [](WorldTextComponent* self, const std::string& value) { self->set_font_path(value); })

INSPECT_FIELD_CALLBACK(WorldTextComponent, std::string, phase_mark, "Phase Mark", "string",
    [](WorldTextComponent* self) -> std::string& { return self->phase_mark; },
    [](WorldTextComponent* self, const std::string& value) { self->set_phase_mark(value); })

INSPECT_FIELD_ACCESSORS(WorldTextComponent, tc_vec3, local_offset, "Local Offset", "vec3",
    [](WorldTextComponent* self) {
        return tc_vec3{self->local_offset.x, self->local_offset.y, self->local_offset.z};
    },
    [](WorldTextComponent* self, tc_vec3 value) {
        self->set_local_offset(Vec3{value.x, value.y, value.z});
    })

INSPECT_FIELD_ACCESSORS(WorldTextComponent, tc_vec3, plane_normal, "Plane Normal", "vec3",
    [](WorldTextComponent* self) {
        return tc_vec3{self->plane_normal.x, self->plane_normal.y, self->plane_normal.z};
    },
    [](WorldTextComponent* self, tc_vec3 value) {
        self->set_plane_normal(Vec3{value.x, value.y, value.z});
    })

INSPECT_FIELD_ACCESSORS(WorldTextComponent, tc_vec3, text_up, "Text Up", "vec3",
    [](WorldTextComponent* self) {
        return tc_vec3{self->text_up.x, self->text_up.y, self->text_up.z};
    },
    [](WorldTextComponent* self, tc_vec3 value) {
        self->set_text_up(Vec3{value.x, value.y, value.z});
    })

INSPECT_FIELD_CALLBACK(WorldTextComponent, Vec4, color, "Color", "color",
    [](WorldTextComponent* self) -> Vec4& { return self->color; },
    [](WorldTextComponent* self, const Vec4& value) { self->set_color(value); })

INSPECT_FIELD_CALLBACK(WorldTextComponent, float, size, "Size", "float",
    [](WorldTextComponent* self) -> float& { return self->size; },
    [](WorldTextComponent* self, const float& value) { self->set_size(value); },
    0.001, 10.0, 0.01)

INSPECT_FIELD_ACCESSORS_CHOICES(WorldTextComponent, int, anchor, "Anchor", "enum",
    [](WorldTextComponent* self) -> int { return static_cast<int>(self->anchor); },
    [](WorldTextComponent* self, int value) { self->set_anchor(static_cast<WorldTextAnchor>(value)); },
    {"0", "Left"},
    {"1", "Center"},
    {"2", "Right"})

INSPECT_FIELD_ACCESSORS_CHOICES(WorldTextComponent, int, orientation, "Orientation", "enum",
    [](WorldTextComponent* self) -> int { return static_cast<int>(self->orientation); },
    [](WorldTextComponent* self, int value) { self->set_orientation(static_cast<WorldTextOrientation>(value)); },
    {"0", "Billboard"},
    {"1", "Fixed"})

INSPECT_FIELD_CALLBACK(WorldTextComponent, int, priority, "Priority", "int",
    [](WorldTextComponent* self) -> int& { return self->priority; },
    [](WorldTextComponent* self, const int& value) { self->set_priority(value); },
    -32768, 32767, 1)

INSPECT_FIELD_CALLBACK(WorldTextComponent, bool, depth_test, "Depth Test", "bool",
    [](WorldTextComponent* self) -> bool& { return self->depth_test; },
    [](WorldTextComponent* self, const bool& value) { self->set_depth_test(value); })

INSPECT_FIELD_CALLBACK(WorldTextComponent, bool, depth_write, "Depth Write", "bool",
    [](WorldTextComponent* self) -> bool& { return self->depth_write; },
    [](WorldTextComponent* self, const bool& value) { self->set_depth_write(value); })

INSPECT_FIELD_CALLBACK(WorldTextComponent, bool, blend, "Blend", "bool",
    [](WorldTextComponent* self) -> bool& { return self->blend; },
    [](WorldTextComponent* self, const bool& value) { self->set_blend(value); })

INSPECT_FIELD_CALLBACK(WorldTextComponent, bool, cull, "Cull", "bool",
    [](WorldTextComponent* self) -> bool& { return self->cull; },
    [](WorldTextComponent* self, const bool& value) { self->set_cull(value); })

REGISTER_COMPONENT(WorldTextComponent, Component);

} // namespace termin
