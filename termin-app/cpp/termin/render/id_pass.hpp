#pragma once

#include <termin/render/geometry_pass_base.hpp>
#include "tgfx2/handles.hpp"
#include "tgfx2/i_render_device.hpp"

namespace termin {

class IdPass : public GeometryPassBase {
public:
    IdPass(
        const std::string& input_res = "empty",
        const std::string& output_res = "id",
        const std::string& pass_name = "IdPass"
    ) : GeometryPassBase(pass_name, input_res, output_res) {}

    ~IdPass() override { release_tgfx2_resources(); }

    void destroy() override {
        GeometryPassBase::destroy();
        release_tgfx2_resources();
    }

    // tgfx2-native IdPass entry — requires ctx.ctx2 to be non-null.
    void execute_with_data_tgfx2(
        ExecuteContext& ctx,
        const Rect4i& rect,
        tc_scene_handle scene,
        const Mat44f& view,
        const Mat44f& projection,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    void execute(ExecuteContext& ctx) override;

    std::vector<ResourceSpec> get_resource_specs() const override {
        return make_resource_specs();
    }

protected:
    const char* vertex_shader_source() const override;
    const char* fragment_shader_source() const override;
    std::array<float, 4> clear_color() const override { return {0.0f, 0.0f, 0.0f, 0.0f}; }
    const char* phase_name() const override { return "pick"; }

    bool entity_filter(const Entity& ent) const override {
        return ent.pickable();
    }

    int get_pick_id(const Entity& ent) const override {
        return static_cast<int>(ent.pick_id());
    }

private:
    static void id_to_rgb(int id, float& r, float& g, float& b);

    // Lazy tgfx2 resources (shader + UBO) used by execute_with_data_tgfx2.
    tgfx::IRenderDevice* device2_ = nullptr;
    tgfx::ShaderHandle id_vs2_;
    tgfx::ShaderHandle id_fs2_;
    tgfx::BufferHandle per_frame_ubo_;

    void ensure_tgfx2_resources(tgfx::IRenderDevice& device);
    void release_tgfx2_resources();
};

} // namespace termin
