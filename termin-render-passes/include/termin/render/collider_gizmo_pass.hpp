#pragma once

#include "termin/render/frame_pass.hpp"
#include "termin/render/execute_context.hpp"
#include "termin/render_passes/export.h"
#include <tgfx2/immediate_renderer.hpp>
#include <termin/geom/mat44.hpp>

namespace termin {
namespace colliders { class ConvexHullCollider; }

// Collider wireframe color (green) - defined in cpp file
extern TERMIN_RENDER_PASSES_API const Color4 COLLIDER_GIZMO_COLOR;

// ColliderGizmoPass renders collider wireframes for editor visualization.
// It iterates over all ColliderComponent instances in the scene and draws
// wireframe representations via ImmediateRenderer (tgfx2-native).
// Supports Box, Sphere, Capsule, and ConvexHull collider types.
class TERMIN_RENDER_PASSES_API ColliderGizmoPass : public CxxFramePass {
private:
    ImmediateRenderer _renderer;

public:
    // Configuration
    std::string input_res = "color";
    std::string output_res = "color";
    bool depth_test = false;

    // INSPECT_FIELD registrations
    INSPECT_FIELD(ColliderGizmoPass, input_res, "Input Resource", "string")
    INSPECT_FIELD(ColliderGizmoPass, output_res, "Output Resource", "string")
    INSPECT_FIELD(ColliderGizmoPass, depth_test, "Depth Test", "bool")
    INSPECT_TYPE_METADATA(ColliderGizmoPass, graph, make_pass_graph_metadata(
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}},
        {{"input_res", "output_res"}}
    ))

    static void register_type();

    ColliderGizmoPass(
        const std::string& input_res = "color",
        const std::string& output_res = "color",
        const std::string& pass_name = "ColliderGizmo",
        bool depth_test = false
    );

    virtual ~ColliderGizmoPass() = default;

    // CxxFramePass overrides
    void execute(ExecuteContext& ctx) override;
    std::set<const char*> compute_reads() const override;
    std::set<const char*> compute_writes() const override;
    std::vector<std::pair<std::string, std::string>> get_inplace_aliases() const override;

    // Internal draw methods (called from callback) — emit primitives
    // into the pass-owned ImmediateRenderer.
    void _draw_box_internal(const Mat44f& entity_world, const float* box_size);
    void _draw_sphere_internal(const Mat44f& entity_world, float radius);
    void _draw_capsule_internal(const Mat44f& entity_world, float height, float radius);
    void _draw_convex_hull_internal(const Mat44f& entity_world, const colliders::ConvexHullCollider* hull);

};

} // namespace termin
