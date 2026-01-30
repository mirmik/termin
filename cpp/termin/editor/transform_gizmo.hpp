#pragma once

#include "termin/editor/gizmo.hpp"
#include "termin/editor/gizmo_types.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/geom/general_pose3.hpp"
#include "termin/render/types.hpp"

#include <functional>
#include <optional>
#include <string>

namespace termin {

class Entity;
class SolidPrimitiveRenderer;
class GraphicsBackend;

// ============================================================
// TransformElement
// ============================================================

enum class TransformElement {
    TRANSLATE_X = 0,
    TRANSLATE_Y = 1,
    TRANSLATE_Z = 2,
    TRANSLATE_XY = 3,
    TRANSLATE_XZ = 4,
    TRANSLATE_YZ = 5,
    ROTATE_X = 6,
    ROTATE_Y = 7,
    ROTATE_Z = 8,
};

// ============================================================
// TransformGizmo
// ============================================================

class TransformGizmo : public Gizmo {
public:
    // Callbacks
    std::function<void()> on_transform_changed;
    // Called when drag ends with (old_pose, new_pose) for undo support
    std::function<void(const GeneralPose3&, const GeneralPose3&)> on_drag_end;

    // Configuration
    float size = 1.5f;
    std::string orientation_mode = "local";  // "local" or "world"

private:
    // Target entity
    Entity* _target = nullptr;
    Vec3f _target_position{0.0f, 0.0f, 0.0f};

    // Undo support - pose at drag start
    GeneralPose3 _drag_start_pose;

    // Screen scale (adjusted based on camera distance)
    float _screen_scale = 1.0f;

    // Hover/active state
    std::optional<TransformElement> _hovered_element;
    std::optional<TransformElement> _active_element;

    // Geometry parameters
    float _arrow_length = 1.0f;
    float _shaft_radius = 0.02f;
    float _head_radius = 0.06f;
    float _head_length_ratio = 0.2f;
    float _ring_major_radius = 0.75f;
    float _ring_minor_radius = 0.02f;
    float _plane_offset = 0.25f;
    float _plane_size = 0.2f;
    float _pick_tolerance = 0.03f;

    // Translation drag state
    Vec3f _grab_offset{0.0f, 0.0f, 0.0f};
    bool _has_grab_offset = false;
    Vec3f _drag_axis{0.0f, 0.0f, 0.0f};
    Vec3f _drag_center{0.0f, 0.0f, 0.0f};

    // Rotation drag state
    float _rot_start_angle = 0.0f;
    float _rot_start_quat[4] = {0.0f, 0.0f, 0.0f, 1.0f};
    Vec3f _rot_vec0{0.0f, 0.0f, 0.0f};
    bool _has_rot_vec0 = false;
    Vec3f _rot_axis{0.0f, 0.0f, 0.0f};

public:
    TransformGizmo() { visible = false; }
    ~TransformGizmo() override = default;

    // Target
    Entity* target() const { return _target; }
    void set_target(Entity* entity);

    void set_screen_scale(float scale) { _screen_scale = scale; }
    void set_orientation_mode(const std::string& mode) { orientation_mode = mode; }
    void set_drag_end_handler(std::function<void(const GeneralPose3&, const GeneralPose3&)> handler) { on_drag_end = handler; }

    // Gizmo interface
    bool uses_solid_renderer() const override { return true; }

    void draw_solid(
        SolidPrimitiveRenderer* renderer,
        GraphicsBackend* graphics,
        const Mat44f& view,
        const Mat44f& proj
    ) override;

    void draw_transparent_solid(
        SolidPrimitiveRenderer* renderer,
        GraphicsBackend* graphics,
        const Mat44f& view,
        const Mat44f& proj
    ) override;

    std::vector<GizmoCollider> get_colliders() override;

    void on_hover_enter(int collider_id) override;
    void on_hover_exit(int collider_id) override;
    void on_click(int collider_id, const Vec3f* hit_position) override;
    void on_drag(int collider_id, const Vec3f& position, const Vec3f& delta) override;
    void on_release(int collider_id) override;

private:
    void _update_position();
    Vec3f _get_position();
    Vec3f _get_world_axis(const std::string& axis);

    Color4 _get_color(const std::string& axis, TransformElement element);
    Color4 _get_plane_color(const std::string& plane, TransformElement element);

    float _scaled(float value) const { return value * size * _screen_scale; }

    void _apply_translation(const Vec3f& projected_position);
    void _apply_rotation(TransformElement element, const Vec3f& plane_hit);

    static bool _is_translate_element(TransformElement e);
    static bool _is_plane_element(TransformElement e);
    static bool _is_rotate_element(TransformElement e);
    static std::string _get_axis_for_element(TransformElement e);

    // Quaternion helpers
    static void _quat_rotate(const float* q, const Vec3f& v, Vec3f& out);
    static void _quat_mul(const float* q1, const float* q2, float* out);
};

} // namespace termin
