#pragma once

#include <memory>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include <tc_value.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/render/drawable.hpp>
#include <termin/render/render_item_submission.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

namespace termin {

enum class LineRenderMode {
    WorldBillboard = 0,
    ScreenSpace = 1,
    WorldMesh = 2,
    RawLines = 3,
    WorldTube = 4,
};

} // namespace termin

namespace tgfx {
class ScreenSpaceLineRenderer;
class WorldSpaceLineRenderer;
class WorldTubeLineRenderer;
} // namespace tgfx

namespace termin {

class ENTITY_API LineRenderer : public Component, public Drawable {
public:
    TcMaterial material;
    float width = 0.1f;
    LineRenderMode render_mode = LineRenderMode::WorldBillboard;
    bool raw_lines = false;
    bool cast_shadow = false;
    tc_vec3 up_hint = {0.0, 1.0, 0.0};
    int tube_sides = 6;

private:
    std::vector<tc_vec3> points_;
    TcMesh mesh_;
    mutable std::unique_ptr<tgfx::ScreenSpaceLineRenderer> screen_space_renderer_;
    mutable std::unique_ptr<tgfx::WorldSpaceLineRenderer> world_space_renderer_;
    mutable std::unique_ptr<tgfx::WorldTubeLineRenderer> world_tube_renderer_;
    bool dirty_ = true;

    static TcMaterial default_material();
    TcMaterial effective_material() const;
    bool effective_render_mode(LineRenderMode& mode) const;
    void rebuild_geometry();
    void ensure_geometry();
    tc_mesh* current_mesh_ptr() const;

public:
    explicit LineRenderer(const char* type_name = "LineRenderer");
    ~LineRenderer() override;

    static void register_type();

    const std::vector<tc_vec3>& points() const { return points_; }
    void set_points(const std::vector<tc_vec3>& points);
    void set_points(std::vector<tc_vec3>&& points);
    void clear_points();
    void add_point(const tc_vec3& point);
    void set_width(float value);
    void set_render_mode(LineRenderMode value);
    void set_raw_lines(bool value);
    void set_cast_shadow(bool value);
    void set_up_hint(const tc_vec3& value);
    void set_tube_sides(int value);
    void set_material(const TcMaterial& value);
    void set_material_by_name(const std::string& name);

    tc_value serialize_points() const;
    void deserialize_points(const tc_value* value);
    tc_value serialize_data() const override;
    void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override;

    std::set<std::string> get_phase_marks() const override;
    std::set<std::string> phase_marks() const { return get_phase_marks(); }
    TcShader override_shader(
        const std::string& phase_mark,
        int geometry_id,
        TcShader original_shader
    ) override;
    TcShader override_shader_with_context(
        const ShaderOverrideContext& context
    ) override;
    void collect_shader_usages(
        const std::string& phase_mark,
        int geometry_id,
        TcShader original_shader,
        const std::function<void(TcShader)>& emit
    ) override;
    void collect_shader_usages_with_context(
        const ShaderOverrideContext& context,
        const std::function<void(TcShader)>& emit
    ) override;
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;
    bool collect_render_items(
        const tc_render_item_collect_context& context,
        tc_render_item_sink& sink
    ) override;
    bool encode_render_item_tgfx2(
        tgfx::RenderContext2& ctx2,
        const tc_render_item& item,
        const RenderItemDrawSubmitRequest& request);
    bool needs_lighting_ubo_tgfx2(const std::string& phase_mark, int geometry_id) const override;
    tc_mesh* get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const override;
    std::vector<GeometryDrawCall> get_geometry_draws(
        const RenderContext& context,
        const std::string* phase_mark = nullptr
    ) override;
    TcMesh get_mesh();
};

} // namespace termin
