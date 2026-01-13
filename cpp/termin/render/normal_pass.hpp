#pragma once

#include "termin/render/geometry_pass_base.hpp"

namespace termin {

// Normal shader sources
extern const char* NORMAL_PASS_VERT;
extern const char* NORMAL_PASS_FRAG;

/**
 * Normal pass - renders world-space normals to texture.
 *
 * Output: RGB texture with normals encoded as (normal * 0.5 + 0.5)
 */
class NormalPass : public GeometryPassBase {
public:
    NormalPass(
        const std::string& input_res = "empty_normal",
        const std::string& output_res = "normal",
        const std::string& pass_name = "Normal"
    ) : GeometryPassBase(pass_name, input_res, output_res) {}

    void execute_with_data(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene* scene,
        const Mat44f& view,
        const Mat44f& projection,
        int64_t context_key,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    ) {
        execute_geometry_pass(graphics, writes_fbos, rect, scene, view, projection, context_key, layer_mask);
    }

    void execute(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        void* scene,
        void* camera,
        int64_t context_key,
        const std::vector<Light*>* lights = nullptr
    ) override {
        // Legacy - not used
    }

    std::vector<ResourceSpec> get_resource_specs() const override {
        return make_resource_specs();
    }

protected:
    const char* vertex_shader_source() const override { return NORMAL_PASS_VERT; }
    const char* fragment_shader_source() const override { return NORMAL_PASS_FRAG; }
    std::array<float, 4> clear_color() const override { return {0.5f, 0.5f, 0.5f, 1.0f}; }
    const char* phase_name() const override { return "normal"; }
};

} // namespace termin
