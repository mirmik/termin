#include "collider_gizmo_pass.hpp"
#include "tgfx/handles.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/entity/entity.hpp"
#include "termin/colliders/collider_component.hpp"
#include "termin/colliders/convex_hull_collider.hpp"
#include "termin/geom/quat.hpp"
#include "termin/geom/mat44.hpp"
#include "tc_log.hpp"

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

// Get model matrix from tc_component's owner entity
Mat44f get_entity_world_matrix(tc_component* c) {
    if (!c || !tc_entity_handle_valid(c->owner)) {
        return mat4_identity();
    }

    tc_entity_pool* pool = tc_entity_pool_registry_get(c->owner.pool);
    if (!pool) {
        return mat4_identity();
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
    // Column 0: X axis
    sx = std::sqrt(m.data[0]*m.data[0] + m.data[1]*m.data[1] + m.data[2]*m.data[2]);
    // Column 1: Y axis
    sy = std::sqrt(m.data[4]*m.data[4] + m.data[5]*m.data[5] + m.data[6]*m.data[6]);
    // Column 2: Z axis
    sz = std::sqrt(m.data[8]*m.data[8] + m.data[9]*m.data[9] + m.data[10]*m.data[10]);
}

// Callback data for collider iteration
struct ColliderDrawData {
    ColliderGizmoPass* pass;
    WireframeRenderer* renderer;
};

// Callback for tc_scene_foreach_component_of_type
bool draw_collider_callback(tc_component* c, void* user_data) {
    auto* data = static_cast<ColliderDrawData*>(user_data);

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

    // Extract scale from world matrix
    float sx, sy, sz;
    extract_scale_from_matrix(world, sx, sy, sz);

    const auto& type = col->collider_type;

    if (type == "Box") {
        data->pass->_draw_box_internal(data->renderer, world, size);
    }
    else if (type == "Sphere") {
        float uniform_size = std::min({size[0], size[1], size[2]});
        float uniform_scale = std::min({sx, sy, sz});
        float radius = (uniform_size / 2.0f) * uniform_scale;
        if (radius > 0) {
            data->pass->_draw_sphere_internal(data->renderer, world, radius);
        }
    }
    else if (type == "Capsule") {
        float height = size[2] * sz;
        float radius = (std::min(size[0], size[1]) / 2.0f) * std::min(sx, sy);
        if (radius > 0) {
            data->pass->_draw_capsule_internal(data->renderer, world, height, radius);
        }
    }
    else if (type == "ConvexHull") {
        auto* primitive = col->collider();
        if (primitive && primitive->type() == colliders::ColliderType::ConvexHull) {
            auto* hull = static_cast<const colliders::ConvexHullCollider*>(primitive);
            data->pass->_draw_convex_hull_internal(data->renderer, world, hull);
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
    if (!ctx.scene.valid()) {
        return;
    }

    tc_scene_handle scene = ctx.scene.handle();

    // Get output FBO
    auto it = ctx.writes_fbos.find(output_res);
    if (it == ctx.writes_fbos.end() || it->second == nullptr) {
        return;
    }

    FramebufferHandle* fb = dynamic_cast<FramebufferHandle*>(it->second);
    if (!fb) {
        return;
    }

    // Get camera matrices
    if (!ctx.camera) {
        return;
    }

    Mat44 view64 = ctx.camera->get_view_matrix();
    Mat44 proj64 = ctx.camera->get_projection_matrix();
    Mat44f view = view64.to_float();
    Mat44f proj = proj64.to_float();

    // Bind FBO and set viewport
    ctx.graphics->bind_framebuffer(fb);
    ctx.graphics->set_viewport(0, 0, fb->get_width(), fb->get_height());

    // Begin wireframe rendering
    _renderer.begin(ctx.graphics, view, proj, depth_test);

    // Iterate over all ColliderComponent instances
    ColliderDrawData data;
    data.pass = this;
    data.renderer = &_renderer;

    tc_scene_foreach_component_of_type(scene, "ColliderComponent", draw_collider_callback, &data);

    // End wireframe rendering
    _renderer.end();
}

void ColliderGizmoPass::_draw_box(const Mat44f& entity_world, const float* box_size) {
    _draw_box_internal(&_renderer, entity_world, box_size);
}

void ColliderGizmoPass::_draw_box_internal(WireframeRenderer* renderer, const Mat44f& entity_world, const float* box_size) {
    // Unit box is -0.5 to +0.5, so scale by full size
    Mat44f scale = mat4_scale(box_size[0], box_size[1], box_size[2]);
    Mat44f model = entity_world * scale;
    renderer->draw_box(model, COLLIDER_GIZMO_COLOR);
}

void ColliderGizmoPass::_draw_sphere(const Mat44f& entity_world, float radius) {
    _draw_sphere_internal(&_renderer, entity_world, radius);
}

void ColliderGizmoPass::_draw_sphere_internal(WireframeRenderer* renderer, const Mat44f& entity_world, float radius) {
    // Extract position from entity world matrix
    float cx = entity_world.data[12];
    float cy = entity_world.data[13];
    float cz = entity_world.data[14];

    // Draw 3 orthogonal circles at entity position
    // XY plane
    Mat44f model_xy = mat4_translate(cx, cy, cz) * mat4_scale_uniform(radius);
    renderer->draw_circle(model_xy, COLLIDER_GIZMO_COLOR);

    // XZ plane (rotate unit circle from XY to XZ)
    float rot_xz[9] = {
        1, 0, 0,
        0, 0, -1,
        0, 1, 0
    };
    Mat44f model_xz = mat4_translate(cx, cy, cz) * mat4_from_rotation_matrix(rot_xz) * mat4_scale_uniform(radius);
    renderer->draw_circle(model_xz, COLLIDER_GIZMO_COLOR);

    // YZ plane (rotate unit circle from XY to YZ)
    float rot_yz[9] = {
        0, 0, 1,
        0, 1, 0,
        -1, 0, 0
    };
    Mat44f model_yz = mat4_translate(cx, cy, cz) * mat4_from_rotation_matrix(rot_yz) * mat4_scale_uniform(radius);
    renderer->draw_circle(model_yz, COLLIDER_GIZMO_COLOR);
}

void ColliderGizmoPass::_draw_capsule(const Mat44f& entity_world, float height, float radius) {
    _draw_capsule_internal(&_renderer, entity_world, height, radius);
}

void ColliderGizmoPass::_draw_capsule_internal(WireframeRenderer* renderer, const Mat44f& entity_world, float height, float radius) {
    // Extract position from entity world matrix
    float cx = entity_world.data[12];
    float cy = entity_world.data[13];
    float cz = entity_world.data[14];

    // Extract entity's local axes from world matrix (columns 0, 1, 2)
    // Column 0 = X axis
    float xx = entity_world.data[0];
    float xy = entity_world.data[1];
    float xz = entity_world.data[2];
    // Column 1 = Y axis
    float yx = entity_world.data[4];
    float yy = entity_world.data[5];
    float yz = entity_world.data[6];
    // Column 2 = Z axis (capsule axis)
    float zx = entity_world.data[8];
    float zy = entity_world.data[9];
    float zz = entity_world.data[10];

    // Normalize axes (remove scale)
    float x_len = std::sqrt(xx*xx + xy*xy + xz*xz);
    float y_len = std::sqrt(yx*yx + yy*yy + yz*yz);
    float z_len = std::sqrt(zx*zx + zy*zy + zz*zz);

    if (x_len > 1e-6f) { xx /= x_len; xy /= x_len; xz /= x_len; }
    if (y_len > 1e-6f) { yx /= y_len; yy /= y_len; yz /= y_len; }
    if (z_len > 1e-6f) { zx /= z_len; zy /= z_len; zz /= z_len; }

    float half_height = height * 0.5f;

    // Endpoints along capsule axis (Z)
    float a_x = cx - zx * half_height;
    float a_y = cy - zy * half_height;
    float a_z = cz - zz * half_height;

    float b_x = cx + zx * half_height;
    float b_y = cy + zy * half_height;
    float b_z = cz + zz * half_height;

    // Build rotation matrix from entity's actual axes (row-major for mat4_from_rotation_matrix)
    // Rows are: (x component of each axis), (y component), (z component)
    float rot[9] = {
        xx, yx, zx,
        xy, yy, zy,
        xz, yz, zz
    };

    // Draw circles at endpoints in entity's local XY plane
    Mat44f model_a = mat4_translate(a_x, a_y, a_z) * mat4_from_rotation_matrix(rot) * mat4_scale_uniform(radius);
    Mat44f model_b = mat4_translate(b_x, b_y, b_z) * mat4_from_rotation_matrix(rot) * mat4_scale_uniform(radius);

    renderer->draw_circle(model_a, COLLIDER_GIZMO_COLOR);
    renderer->draw_circle(model_b, COLLIDER_GIZMO_COLOR);

    // Use entity's X and Y axes as tangent and bitangent
    float tx = xx, ty = xy, tz = xz;
    float bx = yx, by = yy, bz = yz;

    // Draw 4 connecting lines
    for (int i = 0; i < 4; ++i) {
        float angle = 3.14159265f * i / 2.0f;  // 0, 90, 180, 270 degrees
        float cos_a = std::cos(angle);
        float sin_a = std::sin(angle);

        float ox = radius * (cos_a * tx + sin_a * bx);
        float oy = radius * (cos_a * ty + sin_a * by);
        float oz = radius * (cos_a * tz + sin_a * bz);

        float start_x = a_x + ox;
        float start_y = a_y + oy;
        float start_z = a_z + oz;

        float end_x = b_x + ox;
        float end_y = b_y + oy;
        float end_z = b_z + oz;

        // Line direction
        float lx = end_x - start_x;
        float ly = end_y - start_y;
        float lz = end_z - start_z;
        float line_len = std::sqrt(lx*lx + ly*ly + lz*lz);

        if (line_len > 1e-6f) {
            float line_dir[3] = {lx / line_len, ly / line_len, lz / line_len};
            float line_rot[9];
            rotation_matrix_align_z_to_axis(line_dir, line_rot);

            Mat44f model_line = mat4_translate(start_x, start_y, start_z)
                              * mat4_from_rotation_matrix(line_rot)
                              * mat4_scale(1, 1, line_len);
            renderer->draw_line(model_line, COLLIDER_GIZMO_COLOR);
        }
    }

    // Draw hemisphere arcs at each end
    float tangents[2][3] = {{tx, ty, tz}, {bx, by, bz}};
    float neg_tangents[2][3] = {{-tx, -ty, -tz}, {-bx, -by, -bz}};

    for (int t = 0; t < 2; ++t) {
        float* basis_vec = tangents[t];
        float* other_vec = (t == 0) ? tangents[1] : neg_tangents[0];

        // Arc at start (pointing away from end)
        float arc_rot_a[9] = {
            basis_vec[0], -zx, other_vec[0],
            basis_vec[1], -zy, other_vec[1],
            basis_vec[2], -zz, other_vec[2]
        };
        Mat44f model_arc_a = mat4_translate(a_x, a_y, a_z)
                           * mat4_from_rotation_matrix(arc_rot_a)
                           * mat4_scale_uniform(radius);
        renderer->draw_arc(model_arc_a, COLLIDER_GIZMO_COLOR);

        // Arc at end (pointing away from start)
        float arc_rot_b[9] = {
            basis_vec[0], zx, -other_vec[0],
            basis_vec[1], zy, -other_vec[1],
            basis_vec[2], zz, -other_vec[2]
        };
        Mat44f model_arc_b = mat4_translate(b_x, b_y, b_z)
                           * mat4_from_rotation_matrix(arc_rot_b)
                           * mat4_scale_uniform(radius);
        renderer->draw_arc(model_arc_b, COLLIDER_GIZMO_COLOR);
    }
}

void ColliderGizmoPass::_draw_convex_hull_internal(
    WireframeRenderer* renderer, const Mat44f& entity_world,
    const colliders::ConvexHullCollider* hull)
{
    if (!hull || hull->edges.empty() || hull->vertices.empty()) return;

    // Draw each precomputed edge as a line
    for (const auto& [i, j] : hull->edges) {
        const Vec3& va = hull->vertices[i];
        const Vec3& vb = hull->vertices[j];

        // Transform local vertices by entity world matrix
        // world * [x, y, z, 1]
        float ax = entity_world.data[0] * (float)va.x + entity_world.data[4] * (float)va.y + entity_world.data[8]  * (float)va.z + entity_world.data[12];
        float ay = entity_world.data[1] * (float)va.x + entity_world.data[5] * (float)va.y + entity_world.data[9]  * (float)va.z + entity_world.data[13];
        float az = entity_world.data[2] * (float)va.x + entity_world.data[6] * (float)va.y + entity_world.data[10] * (float)va.z + entity_world.data[14];

        float bx = entity_world.data[0] * (float)vb.x + entity_world.data[4] * (float)vb.y + entity_world.data[8]  * (float)vb.z + entity_world.data[12];
        float by = entity_world.data[1] * (float)vb.x + entity_world.data[5] * (float)vb.y + entity_world.data[9]  * (float)vb.z + entity_world.data[13];
        float bz = entity_world.data[2] * (float)vb.x + entity_world.data[6] * (float)vb.y + entity_world.data[10] * (float)vb.z + entity_world.data[14];

        float dx = bx - ax, dy = by - ay, dz = bz - az;
        float len = std::sqrt(dx * dx + dy * dy + dz * dz);
        if (len < 1e-6f) continue;

        float dir[3] = {dx / len, dy / len, dz / len};
        float rot[9];
        rotation_matrix_align_z_to_axis(dir, rot);

        Mat44f model = mat4_translate(ax, ay, az)
                     * mat4_from_rotation_matrix(rot)
                     * mat4_scale(1, 1, len);
        renderer->draw_line(model, COLLIDER_GIZMO_COLOR);
    }
}

// Register ColliderGizmoPass in tc_pass_registry
TC_REGISTER_FRAME_PASS(ColliderGizmoPass);

} // namespace termin
