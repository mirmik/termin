#include "collider_gizmo_pass.hpp"
#include "tgfx/handles.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/render/tgfx2_bridge.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/enums.hpp"
#include "tgfx2/opengl/opengl_render_device.hpp"
#include <termin/entity/entity.hpp>
#include <components/collider_component.hpp>
#include "termin/colliders/convex_hull_collider.hpp"
#include <termin/geom/quat.hpp>
#include <termin/geom/mat44.hpp>
#include <tcbase/tc_log.hpp>

extern "C" {
#include "core/tc_scene.h"
#include "core/tc_component.h"
}

#include <algorithm>
#include <cstring>
#include <cmath>

namespace termin {

// Collider wireframe color (green)
const Color4 COLLIDER_GIZMO_COLOR = {0.2f, 0.9f, 0.2f, 1.0f};

namespace {

// Transform a local-space point by a Mat44f (column-major).
Vec3 transform_point(const Mat44f& m, float lx, float ly, float lz) {
    float wx = m.data[0] * lx + m.data[4] * ly + m.data[8]  * lz + m.data[12];
    float wy = m.data[1] * lx + m.data[5] * ly + m.data[9]  * lz + m.data[13];
    float wz = m.data[2] * lx + m.data[6] * ly + m.data[10] * lz + m.data[14];
    return Vec3(wx, wy, wz);
}

// Get model matrix from tc_component's owner entity
Mat44f get_entity_world_matrix(tc_component* c) {
    if (!c || !tc_entity_handle_valid(c->owner)) {
        return Mat44f::identity();
    }

    tc_entity_pool* pool = tc_entity_pool_registry_get(c->owner.pool);
    if (!pool) {
        return Mat44f::identity();
    }

    double m[16];
    tc_entity_pool_get_world_matrix(pool, c->owner.id, m);

    Mat44f result;
    for (int i = 0; i < 16; ++i) {
        result.data[i] = static_cast<float>(m[i]);
    }
    return result;
}

// Extract scale from world matrix (length of each column)
void extract_scale_from_matrix(const Mat44f& m, float& sx, float& sy, float& sz) {
    sx = std::sqrt(m.data[0]*m.data[0] + m.data[1]*m.data[1] + m.data[2]*m.data[2]);
    sy = std::sqrt(m.data[4]*m.data[4] + m.data[5]*m.data[5] + m.data[6]*m.data[6]);
    sz = std::sqrt(m.data[8]*m.data[8] + m.data[9]*m.data[9] + m.data[10]*m.data[10]);
}

// Callback for tc_scene_foreach_component_of_type
bool draw_collider_callback(tc_component* c, void* user_data) {
    auto* pass = static_cast<ColliderGizmoPass*>(user_data);

    if (!c->enabled) {
        return true;
    }

    CxxComponent* cxx = CxxComponent::from_tc(c);
    if (!cxx) return true;
    auto* col = static_cast<ColliderComponent*>(cxx);

    Mat44f world = get_entity_world_matrix(c);

    // Apply collider offset if enabled
    if (col->collider_offset_enabled) {
        const auto& pos = col->collider_offset_position;
        const auto& euler = col->collider_offset_euler;

        constexpr double deg2rad = 3.14159265358979323846 / 180.0;
        Quat rx = Quat::from_axis_angle(Vec3(1,0,0), euler.x * deg2rad);
        Quat ry = Quat::from_axis_angle(Vec3(0,1,0), euler.y * deg2rad);
        Quat rz = Quat::from_axis_angle(Vec3(0,0,1), euler.z * deg2rad);
        Quat rotation = rz * ry * rx;

        Mat44f offset = Mat44f::compose(Vec3(pos.x, pos.y, pos.z), rotation, Vec3(1,1,1));
        world = world * offset;
    }

    float size[3] = {
        static_cast<float>(col->box_size.x),
        static_cast<float>(col->box_size.y),
        static_cast<float>(col->box_size.z)
    };

    float sx, sy, sz;
    extract_scale_from_matrix(world, sx, sy, sz);

    const auto& type = col->collider_type;

    if (type == "Box") {
        pass->_draw_box_internal(world, size);
    }
    else if (type == "Sphere") {
        float uniform_size = std::min({size[0], size[1], size[2]});
        float uniform_scale = std::min({sx, sy, sz});
        float radius = (uniform_size / 2.0f) * uniform_scale;
        if (radius > 0) {
            pass->_draw_sphere_internal(world, radius);
        }
    }
    else if (type == "Capsule") {
        float height = size[2] * sz;
        float radius = (std::min(size[0], size[1]) / 2.0f) * std::min(sx, sy);
        if (radius > 0) {
            pass->_draw_capsule_internal(world, height, radius);
        }
    }
    else if (type == "ConvexHull") {
        auto* primitive = col->collider();
        if (primitive && primitive->type() == colliders::ColliderType::ConvexHull) {
            auto* hull = static_cast<const colliders::ConvexHullCollider*>(primitive);
            pass->_draw_convex_hull_internal(world, hull);
        }
    }

    return true;
}

} // anonymous namespace

ColliderGizmoPass::ColliderGizmoPass(
    const std::string& input_res,
    const std::string& output_res,
    const std::string& pass_name,
    bool depth_test
) : input_res(input_res),
    output_res(output_res),
    depth_test(depth_test)
{
    set_pass_name(pass_name);
}

std::set<const char*> ColliderGizmoPass::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> ColliderGizmoPass::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>> ColliderGizmoPass::get_inplace_aliases() const {
    return {{input_res, output_res}};
}

void ColliderGizmoPass::execute(ExecuteContext& ctx) {
    if (!ctx.scene.valid() || !ctx.ctx2 || !ctx.camera) {
        return;
    }

    tc_scene_handle scene = ctx.scene.handle();

    auto color_it = ctx.tex2_writes.find(output_res);
    if (color_it == ctx.tex2_writes.end() || !color_it->second) {
        return;
    }
    tgfx::TextureHandle color_tex2 = color_it->second;

    tgfx::TextureHandle depth_tex2;
    if (depth_test) {
        auto depth_it = ctx.tex2_depth_writes.find(output_res);
        if (depth_it != ctx.tex2_depth_writes.end()) {
            depth_tex2 = depth_it->second;
        }
    }

    Mat44 view = ctx.camera->get_view_matrix();
    Mat44 proj = ctx.camera->get_projection_matrix();

    // Begin fresh per-frame (no accumulation across frames).
    _renderer.begin();

    // Walk scene and emit primitives into _renderer.
    tc_scene_foreach_component_of_type(scene, "ColliderComponent", draw_collider_callback, this);

    auto out_desc = ctx.ctx2->device().texture_desc(color_tex2);
    const int w = static_cast<int>(out_desc.width);
    const int h = static_cast<int>(out_desc.height);

    ctx.ctx2->begin_pass(color_tex2, depth_tex2, nullptr, 1.0f, false);
    ctx.ctx2->set_viewport(0, 0, w, h);

    // Collider gizmo always goes into line_vertices (no-depth) unless
    // depth_test is enabled — in that case we accumulate into the
    // depth-tested list. Since the immediate-mode emitters branch on
    // the `depth_test` arg we pass at emit time, call the right flush.
    if (depth_test) {
        _renderer.flush_depth(ctx.ctx2, view, proj, /*blend=*/true);
    } else {
        _renderer.flush(ctx.ctx2, view, proj, /*depth_test=*/false, /*blend=*/true);
    }

    ctx.ctx2->end_pass();
    // color_tex2/depth_tex2 are persistent FBOPool wrappers — do not destroy.
}

// ============================================================================
// Primitive emitters — transform local-space unit primitives by entity_world
// and enqueue lines into the pass-owned ImmediateRenderer.
// ============================================================================

void ColliderGizmoPass::_draw_box_internal(const Mat44f& entity_world, const float* box_size) {
    // Unit box [-0.5, 0.5]^3 scaled by box_size.
    Mat44f scale = Mat44f::scale(Vec3(box_size[0], box_size[1], box_size[2]));
    Mat44f model = entity_world * scale;

    // 8 corners of the unit box
    Vec3 corners[8] = {
        transform_point(model, -0.5f, -0.5f, -0.5f),
        transform_point(model, +0.5f, -0.5f, -0.5f),
        transform_point(model, +0.5f, +0.5f, -0.5f),
        transform_point(model, -0.5f, +0.5f, -0.5f),
        transform_point(model, -0.5f, -0.5f, +0.5f),
        transform_point(model, +0.5f, -0.5f, +0.5f),
        transform_point(model, +0.5f, +0.5f, +0.5f),
        transform_point(model, -0.5f, +0.5f, +0.5f),
    };

    // 12 edges
    static const int edges[12][2] = {
        {0, 1}, {1, 2}, {2, 3}, {3, 0},  // bottom
        {4, 5}, {5, 6}, {6, 7}, {7, 4},  // top
        {0, 4}, {1, 5}, {2, 6}, {3, 7},  // vertical
    };

    for (int i = 0; i < 12; ++i) {
        _renderer.line(corners[edges[i][0]], corners[edges[i][1]],
                       COLLIDER_GIZMO_COLOR, depth_test);
    }
}

void ColliderGizmoPass::_draw_sphere_internal(const Mat44f& entity_world, float radius) {
    // Entity center in world space.
    Vec3 center(entity_world.data[12], entity_world.data[13], entity_world.data[14]);

    // ImmediateRenderer::circle(center, normal, radius) draws a circle
    // in the plane perpendicular to `normal`, centered at `center`.
    // Draw 3 orthogonal circles along world X/Y/Z for the sphere gizmo.
    _renderer.circle(center, Vec3(0, 0, 1), radius, COLLIDER_GIZMO_COLOR, 32, depth_test);
    _renderer.circle(center, Vec3(0, 1, 0), radius, COLLIDER_GIZMO_COLOR, 32, depth_test);
    _renderer.circle(center, Vec3(1, 0, 0), radius, COLLIDER_GIZMO_COLOR, 32, depth_test);
}

void ColliderGizmoPass::_draw_capsule_internal(const Mat44f& entity_world, float height, float radius) {
    // Entity position + local axes extracted from the world matrix.
    float cx = entity_world.data[12];
    float cy = entity_world.data[13];
    float cz = entity_world.data[14];

    float xx = entity_world.data[0], xy = entity_world.data[1], xz = entity_world.data[2];
    float yx = entity_world.data[4], yy = entity_world.data[5], yz = entity_world.data[6];
    float zx = entity_world.data[8], zy = entity_world.data[9], zz = entity_world.data[10];

    // Normalize axes (remove scale).
    float x_len = std::sqrt(xx*xx + xy*xy + xz*xz);
    float y_len = std::sqrt(yx*yx + yy*yy + yz*yz);
    float z_len = std::sqrt(zx*zx + zy*zy + zz*zz);
    if (x_len > 1e-6f) { xx /= x_len; xy /= x_len; xz /= x_len; }
    if (y_len > 1e-6f) { yx /= y_len; yy /= y_len; yz /= y_len; }
    if (z_len > 1e-6f) { zx /= z_len; zy /= z_len; zz /= z_len; }

    float half_height = height * 0.5f;

    // Capsule axis is entity local Z.
    Vec3 axis(zx, zy, zz);
    Vec3 pa(cx - zx * half_height, cy - zy * half_height, cz - zz * half_height);
    Vec3 pb(cx + zx * half_height, cy + zy * half_height, cz + zz * half_height);

    // Tangent / bitangent = entity local X / Y.
    Vec3 tangent(xx, xy, xz);
    Vec3 bitangent(yx, yy, yz);

    // End cap circles (in entity's XY plane, so normal = Z axis).
    _renderer.circle(pa, axis, radius, COLLIDER_GIZMO_COLOR, 32, depth_test);
    _renderer.circle(pb, axis, radius, COLLIDER_GIZMO_COLOR, 32, depth_test);

    // 4 connecting lines between the two end circles.
    for (int i = 0; i < 4; ++i) {
        float angle = 3.14159265f * i / 2.0f;  // 0, 90, 180, 270 deg
        float cos_a = std::cos(angle);
        float sin_a = std::sin(angle);

        Vec3 offset(
            radius * (cos_a * tangent.x + sin_a * bitangent.x),
            radius * (cos_a * tangent.y + sin_a * bitangent.y),
            radius * (cos_a * tangent.z + sin_a * bitangent.z)
        );

        Vec3 start(pa.x + offset.x, pa.y + offset.y, pa.z + offset.z);
        Vec3 end  (pb.x + offset.x, pb.y + offset.y, pb.z + offset.z);
        _renderer.line(start, end, COLLIDER_GIZMO_COLOR, depth_test);
    }

    // Hemisphere arcs at each end. The capsule end is a hemisphere, so
    // draw two half-circles through the pole in two perpendicular
    // planes: (axis, tangent) and (axis, bitangent).
    constexpr int arc_segments = 16;
    auto emit_arc = [&](const Vec3& center, const Vec3& pole_dir,
                        const Vec3& ring_dir) {
        // Half circle from ring_dir, sweeping through pole_dir, back to -ring_dir.
        // Points: angle ∈ [0, pi], p = cos(a)*ring_dir + sin(a)*pole_dir.
        std::vector<Vec3> pts;
        pts.reserve(arc_segments + 1);
        for (int i = 0; i <= arc_segments; ++i) {
            float a = 3.14159265f * i / arc_segments;
            float c = std::cos(a), s = std::sin(a);
            pts.emplace_back(
                center.x + radius * (c * ring_dir.x + s * pole_dir.x),
                center.y + radius * (c * ring_dir.y + s * pole_dir.y),
                center.z + radius * (c * ring_dir.z + s * pole_dir.z)
            );
        }
        _renderer.polyline(pts, COLLIDER_GIZMO_COLOR, /*closed=*/false, depth_test);
    };

    // End A: pole points away from B (i.e. along -axis).
    Vec3 neg_axis(-axis.x, -axis.y, -axis.z);
    emit_arc(pa, neg_axis, tangent);
    emit_arc(pa, neg_axis, bitangent);

    // End B: pole points away from A (i.e. along +axis).
    emit_arc(pb, axis, tangent);
    emit_arc(pb, axis, bitangent);
}

void ColliderGizmoPass::_draw_convex_hull_internal(
    const Mat44f& entity_world,
    const colliders::ConvexHullCollider* hull
) {
    if (!hull || hull->edges.empty() || hull->vertices.empty()) return;

    for (const auto& [i, j] : hull->edges) {
        const Vec3& va = hull->vertices[i];
        const Vec3& vb = hull->vertices[j];
        Vec3 a = transform_point(entity_world,
                                 static_cast<float>(va.x),
                                 static_cast<float>(va.y),
                                 static_cast<float>(va.z));
        Vec3 b = transform_point(entity_world,
                                 static_cast<float>(vb.x),
                                 static_cast<float>(vb.y),
                                 static_cast<float>(vb.z));
        _renderer.line(a, b, COLLIDER_GIZMO_COLOR, depth_test);
    }
}

// Register ColliderGizmoPass in tc_pass_registry
TC_REGISTER_FRAME_PASS(ColliderGizmoPass);

} // namespace termin
