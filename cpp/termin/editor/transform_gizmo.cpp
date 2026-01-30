#include "transform_gizmo.hpp"
#include "termin/entity/entity.hpp"
#include "termin/render/solid_primitive_renderer.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/geom/quat.hpp"

#include <cmath>

namespace termin {

namespace {

// Axis colors
const Color4 AXIS_COLOR_X{0.9f, 0.2f, 0.2f, 1.0f};
const Color4 AXIS_COLOR_Y{0.2f, 0.9f, 0.2f, 1.0f};
const Color4 AXIS_COLOR_Z{0.2f, 0.2f, 0.9f, 1.0f};

// Plane colors
const Color4 PLANE_COLOR_XY{0.9f, 0.9f, 0.2f, 0.3f};
const Color4 PLANE_COLOR_XZ{0.9f, 0.2f, 0.9f, 0.3f};
const Color4 PLANE_COLOR_YZ{0.2f, 0.9f, 0.9f, 0.3f};

const Color4 HOVER_COLOR{1.0f, 0.7f, 0.2f, 1.0f};
const Color4 ACTIVE_COLOR{1.0f, 1.0f, 1.0f, 1.0f};

const float PLANE_ALPHA = 0.3f;

Color4 get_axis_color(const std::string& axis) {
    if (axis == "x") return AXIS_COLOR_X;
    if (axis == "y") return AXIS_COLOR_Y;
    if (axis == "z") return AXIS_COLOR_Z;
    return AXIS_COLOR_X;
}

Color4 get_plane_base_color(const std::string& plane) {
    if (plane == "xy") return PLANE_COLOR_XY;
    if (plane == "xz") return PLANE_COLOR_XZ;
    if (plane == "yz") return PLANE_COLOR_YZ;
    return PLANE_COLOR_XY;
}

// Build rotation matrix that aligns Z axis to target direction
Mat44f rotation_align_z_to(const Vec3f& target) {
    float length = target.norm();
    if (length < 1e-6f) {
        return Mat44f::identity();
    }

    Vec3f z_new = target / length;

    Vec3f up{0.0f, 0.0f, 1.0f};
    if (std::abs(z_new.dot(up)) > 0.99f) {
        up = Vec3f{0.0f, 1.0f, 0.0f};
    }

    Vec3f x_new = up.cross(z_new).normalized();
    Vec3f y_new = z_new.cross(x_new);

    Mat44f m = Mat44f::identity();
    m.data[0] = x_new.x; m.data[4] = y_new.x; m.data[8]  = z_new.x;
    m.data[1] = x_new.y; m.data[5] = y_new.y; m.data[9]  = z_new.y;
    m.data[2] = x_new.z; m.data[6] = y_new.z; m.data[10] = z_new.z;
    return m;
}

// Compose TRS matrix
Mat44f compose_trs(const Vec3f& translate, const Mat44f& rotate, float scale) {
    Mat44f m = Mat44f::identity();

    // Apply scale to rotation columns
    m.data[0]  = rotate.data[0] * scale;
    m.data[1]  = rotate.data[1] * scale;
    m.data[2]  = rotate.data[2] * scale;
    m.data[4]  = rotate.data[4] * scale;
    m.data[5]  = rotate.data[5] * scale;
    m.data[6]  = rotate.data[6] * scale;
    m.data[8]  = rotate.data[8] * scale;
    m.data[9]  = rotate.data[9] * scale;
    m.data[10] = rotate.data[10] * scale;

    // Translation
    m.data[12] = translate.x;
    m.data[13] = translate.y;
    m.data[14] = translate.z;

    return m;
}

} // anonymous namespace

// ============================================================
// TransformGizmo Implementation
// ============================================================

void TransformGizmo::set_target(Entity* entity) {
    _target = entity;
    visible = (_target != nullptr);
    if (_target != nullptr) {
        _update_position();
    }
}

void TransformGizmo::_update_position() {
    if (_target != nullptr && _target->valid()) {
        GeneralPose3 pose = _target->transform().global_pose();
        _target_position = Vec3f{
            static_cast<float>(pose.lin.x),
            static_cast<float>(pose.lin.y),
            static_cast<float>(pose.lin.z)
        };
    }
}

Vec3f TransformGizmo::_get_position() {
    if (_target != nullptr) {
        _update_position();
    }
    return _target_position;
}

Vec3f TransformGizmo::_get_world_axis(const std::string& axis) {
    Vec3f base;
    if (axis == "x") base = Vec3f{1.0f, 0.0f, 0.0f};
    else if (axis == "y") base = Vec3f{0.0f, 1.0f, 0.0f};
    else base = Vec3f{0.0f, 0.0f, 1.0f};

    if (orientation_mode == "world" || _target == nullptr) {
        return base;
    }

    // Local orientation: rotate by entity's rotation
    GeneralPose3 pose = _target->transform().global_pose();
    float q[4] = {
        static_cast<float>(pose.ang.x),
        static_cast<float>(pose.ang.y),
        static_cast<float>(pose.ang.z),
        static_cast<float>(pose.ang.w)
    };
    Vec3f result;
    _quat_rotate(q, base, result);
    return result;
}

Color4 TransformGizmo::_get_color(const std::string& axis, TransformElement element) {
    if (_active_element.has_value() && _active_element.value() == element) {
        return ACTIVE_COLOR;
    }
    if (_hovered_element.has_value() && _hovered_element.value() == element) {
        return HOVER_COLOR;
    }
    return get_axis_color(axis);
}

Color4 TransformGizmo::_get_plane_color(const std::string& plane, TransformElement element) {
    Color4 base = get_plane_base_color(plane);

    if (_active_element.has_value() && _active_element.value() == element) {
        return Color4{ACTIVE_COLOR.r, ACTIVE_COLOR.g, ACTIVE_COLOR.b, PLANE_ALPHA};
    }
    if (_hovered_element.has_value() && _hovered_element.value() == element) {
        return Color4{HOVER_COLOR.r, HOVER_COLOR.g, HOVER_COLOR.b, PLANE_ALPHA};
    }
    return base;
}

void TransformGizmo::draw_solid(
    SolidPrimitiveRenderer* renderer,
    GraphicsBackend* graphics,
    const Mat44f& view,
    const Mat44f& proj
) {
    if (!visible || _target == nullptr) return;

    Vec3f origin = _get_position();

    // Draw translation arrows
    struct AxisDef { std::string name; TransformElement element; };
    AxisDef axes[] = {
        {"x", TransformElement::TRANSLATE_X},
        {"y", TransformElement::TRANSLATE_Y},
        {"z", TransformElement::TRANSLATE_Z},
    };

    for (const auto& ax : axes) {
        Vec3f axis_dir = _get_world_axis(ax.name);
        Color4 color = _get_color(ax.name, ax.element);
        renderer->draw_arrow(
            origin,
            axis_dir,
            _scaled(_arrow_length),
            color,
            _scaled(_shaft_radius),
            _scaled(_head_radius),
            _head_length_ratio
        );
    }

    // Draw rotation rings
    AxisDef ring_axes[] = {
        {"x", TransformElement::ROTATE_X},
        {"y", TransformElement::ROTATE_Y},
        {"z", TransformElement::ROTATE_Z},
    };

    for (const auto& ax : ring_axes) {
        Vec3f ring_axis = _get_world_axis(ax.name);
        Color4 color = _get_color(ax.name, ax.element);

        // Build model matrix for torus
        Mat44f rot = rotation_align_z_to(ring_axis);
        float scale = _scaled(_ring_major_radius);
        Mat44f model = compose_trs(origin, rot, scale);
        renderer->draw_torus(model, color);
    }
}

void TransformGizmo::draw_transparent_solid(
    SolidPrimitiveRenderer* renderer,
    GraphicsBackend* graphics,
    const Mat44f& view,
    const Mat44f& proj
) {
    if (!visible || _target == nullptr) return;

    Vec3f origin = _get_position();

    Vec3f axis_x = _get_world_axis("x");
    Vec3f axis_y = _get_world_axis("y");
    Vec3f axis_z = _get_world_axis("z");
    float off = _scaled(_plane_offset);
    float sz = _scaled(_plane_size);

    struct PlaneDef {
        std::string name;
        TransformElement element;
        Vec3f a1, a2;
    };
    PlaneDef planes[] = {
        {"xy", TransformElement::TRANSLATE_XY, axis_x, axis_y},
        {"xz", TransformElement::TRANSLATE_XZ, axis_z, axis_x},
        {"yz", TransformElement::TRANSLATE_YZ, axis_y, axis_z},
    };

    for (const auto& pl : planes) {
        Color4 color = _get_plane_color(pl.name, pl.element);

        // Position the quad
        Vec3f p0 = origin + pl.a1 * off + pl.a2 * off;

        // Build rotation: columns are a1, a2, cross(a1, a2)
        Vec3f normal = pl.a1.cross(pl.a2);
        Mat44f rot = Mat44f::identity();
        rot.data[0] = pl.a1.x; rot.data[4] = pl.a2.x; rot.data[8]  = normal.x;
        rot.data[1] = pl.a1.y; rot.data[5] = pl.a2.y; rot.data[9]  = normal.y;
        rot.data[2] = pl.a1.z; rot.data[6] = pl.a2.z; rot.data[10] = normal.z;

        Mat44f model = compose_trs(p0, rot, sz);
        renderer->draw_quad(model, color);
    }
}

std::vector<GizmoCollider> TransformGizmo::get_colliders() {
    std::vector<GizmoCollider> colliders;

    if (!visible || _target == nullptr) {
        return colliders;
    }

    Vec3f origin = _get_position();
    float tol = _scaled(_pick_tolerance);

    // Translation arrows (cylinders)
    struct AxisDef { std::string name; TransformElement element; };
    AxisDef axes[] = {
        {"x", TransformElement::TRANSLATE_X},
        {"y", TransformElement::TRANSLATE_Y},
        {"z", TransformElement::TRANSLATE_Z},
    };

    for (const auto& ax : axes) {
        Vec3f axis_dir = _get_world_axis(ax.name);
        float arrow_len = _scaled(_arrow_length);
        Vec3f shaft_end = origin + axis_dir * (arrow_len * (1.0f - _head_length_ratio));
        Vec3f tip = origin + axis_dir * arrow_len;

        // Shaft
        colliders.push_back(GizmoCollider{
            static_cast<int>(ax.element),
            CylinderGeometry{origin, shaft_end, _scaled(_shaft_radius) + tol},
            AxisConstraint{origin, axis_dir}
        });

        // Head
        colliders.push_back(GizmoCollider{
            static_cast<int>(ax.element),
            CylinderGeometry{shaft_end, tip, _scaled(_head_radius) + tol},
            AxisConstraint{origin, axis_dir}
        });
    }

    // Rotation rings (tori)
    AxisDef ring_axes[] = {
        {"x", TransformElement::ROTATE_X},
        {"y", TransformElement::ROTATE_Y},
        {"z", TransformElement::ROTATE_Z},
    };

    for (const auto& ax : ring_axes) {
        Vec3f ring_axis = _get_world_axis(ax.name);
        colliders.push_back(GizmoCollider{
            static_cast<int>(ax.element),
            TorusGeometry{origin, ring_axis, _scaled(_ring_major_radius), _scaled(_ring_minor_radius) + tol},
            AngleConstraint{origin, ring_axis}
        });
    }

    // Plane handles (quads)
    Vec3f axis_x = _get_world_axis("x");
    Vec3f axis_y = _get_world_axis("y");
    Vec3f axis_z = _get_world_axis("z");
    float off = _scaled(_plane_offset);
    float sz = _scaled(_plane_size);

    struct PlaneDef {
        std::string name;
        TransformElement element;
        Vec3f a1, a2, normal;
    };
    PlaneDef planes[] = {
        {"xy", TransformElement::TRANSLATE_XY, axis_x, axis_y, axis_z},
        {"xz", TransformElement::TRANSLATE_XZ, axis_z, axis_x, axis_y},
        {"yz", TransformElement::TRANSLATE_YZ, axis_y, axis_z, axis_x},
    };

    for (const auto& pl : planes) {
        Vec3f p0 = origin + pl.a1 * off + pl.a2 * off;
        Vec3f p1 = origin + pl.a1 * (off + sz) + pl.a2 * off;
        Vec3f p2 = origin + pl.a1 * (off + sz) + pl.a2 * (off + sz);
        Vec3f p3 = origin + pl.a1 * off + pl.a2 * (off + sz);

        colliders.push_back(GizmoCollider{
            static_cast<int>(pl.element),
            QuadGeometry{p0, p1, p2, p3, pl.normal},
            PlaneConstraint{origin, pl.normal}
        });
    }

    return colliders;
}

void TransformGizmo::on_hover_enter(int collider_id) {
    _hovered_element = static_cast<TransformElement>(collider_id);
}

void TransformGizmo::on_hover_exit(int collider_id) {
    if (_hovered_element.has_value() &&
        static_cast<int>(_hovered_element.value()) == collider_id) {
        _hovered_element = std::nullopt;
    }
}

void TransformGizmo::on_click(int collider_id, const Vec3f* hit_position) {
    TransformElement element = static_cast<TransformElement>(collider_id);
    _active_element = element;

    Vec3f origin = _get_position();
    _drag_center = origin;

    // Translation
    if (_is_translate_element(element) || _is_plane_element(element)) {
        std::string axis = _get_axis_for_element(element);
        _drag_axis = _get_world_axis(axis);

        if (hit_position != nullptr) {
            _grab_offset = origin - *hit_position;
            _has_grab_offset = true;
        } else {
            _grab_offset = Vec3f{0.0f, 0.0f, 0.0f};
            _has_grab_offset = false;
        }
    }

    // Rotation
    if (_is_rotate_element(element)) {
        if (_target != nullptr) {
            GeneralPose3 pose = _target->transform().global_pose();
            _rot_start_quat[0] = static_cast<float>(pose.ang.x);
            _rot_start_quat[1] = static_cast<float>(pose.ang.y);
            _rot_start_quat[2] = static_cast<float>(pose.ang.z);
            _rot_start_quat[3] = static_cast<float>(pose.ang.w);
        }
        _rot_start_angle = 0.0f;

        std::string axis = _get_axis_for_element(element);
        _rot_axis = _get_world_axis(axis);

        if (hit_position != nullptr) {
            Vec3f v0 = *hit_position - origin;
            // Project onto plane perpendicular to rotation axis
            v0 = v0 - _rot_axis * v0.dot(_rot_axis);
            float norm_v0 = v0.norm();

            if (norm_v0 > 1e-6f) {
                _rot_vec0 = v0 / norm_v0;
                _has_rot_vec0 = true;
            } else {
                // Use arbitrary vector in plane
                Vec3f tangent, bitangent;
                build_basis(_rot_axis, tangent, bitangent);
                _rot_vec0 = tangent;
                _has_rot_vec0 = true;
            }
        } else {
            _has_rot_vec0 = false;
        }
    }
}

void TransformGizmo::on_drag(int collider_id, const Vec3f& position, const Vec3f& delta) {
    if (_target == nullptr) return;

    TransformElement element = static_cast<TransformElement>(collider_id);

    if (_is_translate_element(element) || _is_plane_element(element)) {
        _apply_translation(position);
    } else if (_is_rotate_element(element)) {
        _apply_rotation(element, position);
    }

    if (on_transform_changed) {
        on_transform_changed();
    }
}

void TransformGizmo::on_release(int collider_id) {
    _active_element = std::nullopt;
    _has_grab_offset = false;
    _has_rot_vec0 = false;
}

void TransformGizmo::_apply_translation(const Vec3f& projected_position) {
    Vec3f new_position = projected_position;
    if (_has_grab_offset) {
        new_position = projected_position + _grab_offset;
    }

    GeneralPose3 old_pose = _target->transform().global_pose();
    GeneralPose3 new_pose = old_pose;
    new_pose.lin = Vec3{new_position.x, new_position.y, new_position.z};

    _target->transform().relocate_global(new_pose);
}

void TransformGizmo::_apply_rotation(TransformElement element, const Vec3f& plane_hit) {
    if (!_has_rot_vec0) return;

    Vec3f origin = _drag_center;
    Vec3f axis_dir = _rot_axis;

    // Compute current vector from center to hit point
    Vec3f v1 = plane_hit - origin;
    // Project onto plane perpendicular to axis
    v1 = v1 - axis_dir * v1.dot(axis_dir);
    float norm_v1 = v1.norm();
    if (norm_v1 < 1e-6f) return;
    v1 = v1 / norm_v1;

    // Compute angle between initial reference vector and current vector
    float dot = _rot_vec0.dot(v1);
    if (dot > 1.0f) dot = 1.0f;
    if (dot < -1.0f) dot = -1.0f;

    Vec3f cross_prod = _rot_vec0.cross(v1);
    float sin_angle = cross_prod.norm();
    float sign = cross_prod.dot(axis_dir) >= 0 ? 1.0f : -1.0f;

    float angle = std::atan2(sin_angle, dot) * sign;

    // Build rotation quaternion
    float half = angle * 0.5f;
    float s = std::sin(half);
    float c = std::cos(half);
    float dq[4] = {axis_dir.x * s, axis_dir.y * s, axis_dir.z * s, c};

    // Apply to start rotation
    float new_quat[4];
    _quat_mul(dq, _rot_start_quat, new_quat);

    // Normalize
    float norm_q = std::sqrt(
        new_quat[0] * new_quat[0] +
        new_quat[1] * new_quat[1] +
        new_quat[2] * new_quat[2] +
        new_quat[3] * new_quat[3]
    );
    if (norm_q > 0.0f) {
        new_quat[0] /= norm_q;
        new_quat[1] /= norm_q;
        new_quat[2] /= norm_q;
        new_quat[3] /= norm_q;
    }

    GeneralPose3 new_pose;
    new_pose.lin = Vec3{origin.x, origin.y, origin.z};
    new_pose.ang = Quat{new_quat[0], new_quat[1], new_quat[2], new_quat[3]};
    new_pose.scale = _target->transform().global_pose().scale;

    _target->transform().relocate_global(new_pose);
}

bool TransformGizmo::_is_translate_element(TransformElement e) {
    return e == TransformElement::TRANSLATE_X ||
           e == TransformElement::TRANSLATE_Y ||
           e == TransformElement::TRANSLATE_Z;
}

bool TransformGizmo::_is_plane_element(TransformElement e) {
    return e == TransformElement::TRANSLATE_XY ||
           e == TransformElement::TRANSLATE_XZ ||
           e == TransformElement::TRANSLATE_YZ;
}

bool TransformGizmo::_is_rotate_element(TransformElement e) {
    return e == TransformElement::ROTATE_X ||
           e == TransformElement::ROTATE_Y ||
           e == TransformElement::ROTATE_Z;
}

std::string TransformGizmo::_get_axis_for_element(TransformElement e) {
    switch (e) {
        case TransformElement::TRANSLATE_X:
        case TransformElement::ROTATE_X:
            return "x";
        case TransformElement::TRANSLATE_Y:
        case TransformElement::ROTATE_Y:
            return "y";
        case TransformElement::TRANSLATE_Z:
        case TransformElement::ROTATE_Z:
            return "z";
        default:
            return "x";
    }
}

void TransformGizmo::_quat_rotate(const float* q, const Vec3f& v, Vec3f& out) {
    // Rotate vector by quaternion (x, y, z, w)
    float qx = q[0], qy = q[1], qz = q[2], qw = q[3];

    // t = 2 * cross(q.xyz, v)
    float tx = 2.0f * (qy * v.z - qz * v.y);
    float ty = 2.0f * (qz * v.x - qx * v.z);
    float tz = 2.0f * (qx * v.y - qy * v.x);

    // out = v + qw * t + cross(q.xyz, t)
    out.x = v.x + qw * tx + (qy * tz - qz * ty);
    out.y = v.y + qw * ty + (qz * tx - qx * tz);
    out.z = v.z + qw * tz + (qx * ty - qy * tx);
}

void TransformGizmo::_quat_mul(const float* q1, const float* q2, float* out) {
    // Multiply two quaternions (x, y, z, w)
    float x1 = q1[0], y1 = q1[1], z1 = q1[2], w1 = q1[3];
    float x2 = q2[0], y2 = q2[1], z2 = q2[2], w2 = q2[3];

    out[0] = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2;
    out[1] = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2;
    out[2] = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2;
    out[3] = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2;
}

} // namespace termin
