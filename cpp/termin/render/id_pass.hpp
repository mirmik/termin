#pragma once

#include "termin/render/geometry_pass_base.hpp"

namespace termin {

// Pick shader sources
extern const char* ID_PASS_VERT;
extern const char* ID_PASS_FRAG;

/**
 * ID pass - renders entity pick IDs to texture for picking.
 *
 * Output: RGB texture with entity pick IDs encoded as colors.
 */
class IdPass : public GeometryPassBase {
public:
    IdPass(
        const std::string& input_res = "empty",
        const std::string& output_res = "id",
        const std::string& pass_name = "IdPass"
    ) : GeometryPassBase(pass_name, input_res, output_res) {}

    void execute_with_data(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        tc_scene* scene,
        const Mat44f& view,
        const Mat44f& projection,
        uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL
    );

    void execute(
        GraphicsBackend* graphics,
        const FBOMap& reads_fbos,
        const FBOMap& writes_fbos,
        const Rect4i& rect,
        void* scene,
        void* camera,
        const std::vector<Light*>* lights = nullptr
    ) override {
        // Legacy - not used
    }

    std::vector<ResourceSpec> get_resource_specs() const override {
        return make_resource_specs();
    }

protected:
    const char* vertex_shader_source() const override { return ID_PASS_VERT; }
    const char* fragment_shader_source() const override { return ID_PASS_FRAG; }
    std::array<float, 4> clear_color() const override { return {0.0f, 0.0f, 0.0f, 0.0f}; }
    const char* phase_name() const override { return "pick"; }

    bool entity_filter(const Entity& ent) const override {
        return ent.pickable();
    }

    int get_pick_id(const Entity& ent) const override {
        return static_cast<int>(ent.pick_id());
    }

private:
    // Convert pick ID to RGB color
    static void id_to_rgb(int id, float& r, float& g, float& b);
};

} // namespace termin
