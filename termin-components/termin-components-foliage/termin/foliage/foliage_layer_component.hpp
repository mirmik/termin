#pragma once

#include <functional>
#include <string>
#include <set>
#include <vector>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/export.hpp>
#include <termin/render/drawable.hpp>
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

    std::set<std::string> get_phase_marks() const override;
    void draw_geometry(const RenderContext& context, int geometry_id = 0) override;
    std::vector<GeometryDrawCall> get_geometry_draws(
        const RenderContext& context,
        const std::string* phase_mark = nullptr
    ) override;
    tc_mesh* get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const override;
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
    bool draw_tgfx2(
        tgfx::RenderContext2& ctx2,
        const RenderContext& context,
        const std::string& phase_mark,
        tc_material_phase* phase,
        int geometry_id
    ) override;
    bool supports_direct_tgfx2_draw(
        const std::string& phase_mark,
        int geometry_id,
        DirectTgfx2DrawKind kind
    ) const override;
};

} // namespace termin
