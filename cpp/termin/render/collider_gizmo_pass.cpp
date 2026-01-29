#include "collider_gizmo_pass.hpp"
#include "termin/render/handles.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/entity/entity.hpp"
#include "tc_log.hpp"

extern "C" {
#include "tc_scene.h"
#include "tc_component.h"
#include "tc_inspect.h"
#include "tc_value.h"
}

#include <cstring>
#include <cmath>

namespace termin {

// Collider wireframe color (green)
const Color4 COLLIDER_GIZMO_COLOR = {0.2f, 0.9f, 0.2f, 1.0f};

namespace {

// Get model matrix from tc_component's owner entity
Mat44f get_entity_world_matrix(tc_component* c) {
    if (!c || !c->owner_pool) {
        return mat4_identity();
    }

    double m[16];
    tc_entity_pool_get_world_matrix(c->owner_pool, c->owner_entity_id, m);

    Mat44f result;
    for (int i = 0; i < 16; ++i) {
        result.data[i] = static_cast<float>(m[i]);
    }
    return result;
}

// Callback data for collider iteration
struct ColliderDrawData {
    ColliderGizmoPass* pass;
    WireframeRenderer* renderer;
};

// Callback for tc_scene_foreach_component_of_type
bool draw_collider_callback(tc_component* c, void* user_data) {
    auto* data = static_cast<ColliderDrawData*>(user_data);

    // Check if enabled
    if (!c->enabled) {
        return true;  // continue iteration
    }

    // Get collider type
    const char* collider_type = tc_component_get_field_string(c, "collider_type");
    if (!collider_type) {
        return true;
    }

    // Get entity world matrix
    Mat44f world = get_entity_world_matrix(c);

    if (strcmp(collider_type, "Box") == 0) {
        // Get box_size - can be Vec3 or tuple (list)
        tc_value size_val = tc_component_inspect_get(c, "box_size");
        float box_size[3] = {1.0f, 1.0f, 1.0f};  // default
        bool got_size = false;

        if (size_val.type == TC_VALUE_VEC3) {
            box_size[0] = static_cast<float>(size_val.data.v3.x);
            box_size[1] = static_cast<float>(size_val.data.v3.y);
            box_size[2] = static_cast<float>(size_val.data.v3.z);
            got_size = true;
        }
        else if (size_val.type == TC_VALUE_LIST && size_val.data.list.count >= 3) {
            // tuple in Python becomes list
            for (int i = 0; i < 3; ++i) {
                tc_value& item = size_val.data.list.items[i];
                if (item.type == TC_VALUE_FLOAT) {
                    box_size[i] = item.data.f;
                } else if (item.type == TC_VALUE_DOUBLE) {
                    box_size[i] = static_cast<float>(item.data.d);
                } else if (item.type == TC_VALUE_INT) {
                    box_size[i] = static_cast<float>(item.data.i);
                }
            }
            got_size = true;
        }

        if (got_size) {
            data->pass->_draw_box_internal(data->renderer, world, box_size);
        }
    }
    else if (strcmp(collider_type, "Sphere") == 0) {
        float radius = tc_component_get_field_float(c, "sphere_radius");
        if (radius > 0) {
            data->pass->_draw_sphere_internal(data->renderer, world, radius);
        }
    }
    else if (strcmp(collider_type, "Capsule") == 0) {
        float height = tc_component_get_field_float(c, "capsule_height");
        float radius = tc_component_get_field_float(c, "capsule_radius");
        if (radius > 0) {
            data->pass->_draw_capsule_internal(data->renderer, world, height, radius);
        }
    }

    return true;  // continue iteration
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

    tc_scene* scene = ctx.scene.ptr();
    if (!scene) {
        return;
    }

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
    // Extract position and axis from entity world matrix
    float cx = entity_world.data[12];
    float cy = entity_world.data[13];
    float cz = entity_world.data[14];

    // Capsule axis is Z in local space
    // Extract Z axis from entity rotation (column 2 of 3x3 rotation part)
    float ax = entity_world.data[8];
    float ay = entity_world.data[9];
    float az = entity_world.data[10];

    // Normalize axis
    float len = std::sqrt(ax*ax + ay*ay + az*az);
    if (len > 1e-6f) {
        ax /= len;
        ay /= len;
        az /= len;
    } else {
        ax = 0; ay = 0; az = 1;
    }

    float half_height = height * 0.5f;

    // Endpoints
    float a_x = cx - ax * half_height;
    float a_y = cy - ay * half_height;
    float a_z = cz - az * half_height;

    float b_x = cx + ax * half_height;
    float b_y = cy + ay * half_height;
    float b_z = cz + az * half_height;

    // Build rotation matrix that aligns Z to capsule axis
    float rot[9];
    rotation_matrix_align_z_to_axis(&ax, rot);

    // Draw circles at endpoints
    Mat44f model_a = mat4_translate(a_x, a_y, a_z) * mat4_from_rotation_matrix(rot) * mat4_scale_uniform(radius);
    Mat44f model_b = mat4_translate(b_x, b_y, b_z) * mat4_from_rotation_matrix(rot) * mat4_scale_uniform(radius);

    renderer->draw_circle(model_a, COLLIDER_GIZMO_COLOR);
    renderer->draw_circle(model_b, COLLIDER_GIZMO_COLOR);

    // Build tangent and bitangent for connecting lines
    float up[3] = {0, 0, 1};
    if (std::abs(ax*up[0] + ay*up[1] + az*up[2]) > 0.99f) {
        up[0] = 0; up[1] = 1; up[2] = 0;
    }

    // tangent = cross(axis, up)
    float tx = ay * up[2] - az * up[1];
    float ty = az * up[0] - ax * up[2];
    float tz = ax * up[1] - ay * up[0];
    float tlen = std::sqrt(tx*tx + ty*ty + tz*tz);
    if (tlen > 1e-6f) {
        tx /= tlen; ty /= tlen; tz /= tlen;
    }

    // bitangent = cross(axis, tangent)
    float bx = ay * tz - az * ty;
    float by = az * tx - ax * tz;
    float bz = ax * ty - ay * tx;

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
            basis_vec[0], -ax, other_vec[0],
            basis_vec[1], -ay, other_vec[1],
            basis_vec[2], -az, other_vec[2]
        };
        Mat44f model_arc_a = mat4_translate(a_x, a_y, a_z)
                           * mat4_from_rotation_matrix(arc_rot_a)
                           * mat4_scale_uniform(radius);
        renderer->draw_arc(model_arc_a, COLLIDER_GIZMO_COLOR);

        // Arc at end (pointing away from start)
        float arc_rot_b[9] = {
            basis_vec[0], ax, -other_vec[0],
            basis_vec[1], ay, -other_vec[1],
            basis_vec[2], az, -other_vec[2]
        };
        Mat44f model_arc_b = mat4_translate(b_x, b_y, b_z)
                           * mat4_from_rotation_matrix(arc_rot_b)
                           * mat4_scale_uniform(radius);
        renderer->draw_arc(model_arc_b, COLLIDER_GIZMO_COLOR);
    }
}

// Register ColliderGizmoPass in tc_pass_registry
TC_REGISTER_FRAME_PASS(ColliderGizmoPass);

} // namespace termin
