#pragma once

#include "termin/editor/gizmo.hpp"
#include "termin/editor/gizmo_types.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/render/types.hpp"

#include <vector>
#include <optional>

namespace termin {

class ImmediateRenderer;
class SolidPrimitiveRenderer;
class GraphicsBackend;

// ============================================================
// GizmoHit
// ============================================================

struct GizmoHit {
    Gizmo* gizmo;
    GizmoCollider collider;
    float t;  // distance along ray
};

// ============================================================
// GizmoManager
// ============================================================

class GizmoManager {
public:
    // Gizmo list
    std::vector<Gizmo*> _gizmos;

    // Drag state
    Gizmo* _active_gizmo = nullptr;
    GizmoCollider* _active_collider = nullptr;
    Vec3f _drag_start_ray_origin;
    Vec3f _drag_start_ray_dir;
    Vec3f _last_drag_position;
    bool _has_last_drag_position = false;

    // Hover state
    Gizmo* _hovered_gizmo = nullptr;
    int _hovered_collider_id = -1;

    // Solid renderer (lazy initialized)
    SolidPrimitiveRenderer* _solid_renderer = nullptr;
    bool _owns_solid_renderer = false;

public:
    GizmoManager() = default;
    ~GizmoManager();

    // Non-copyable
    GizmoManager(const GizmoManager&) = delete;
    GizmoManager& operator=(const GizmoManager&) = delete;

    bool is_dragging() const { return _active_gizmo != nullptr; }

    void add_gizmo(Gizmo* gizmo);
    void remove_gizmo(Gizmo* gizmo);
    void clear();

    // Rendering
    void render(
        ImmediateRenderer* renderer,
        GraphicsBackend* graphics,
        const Mat44f& view_matrix,
        const Mat44f& proj_matrix
    );

    // Picking
    std::optional<GizmoHit> raycast(const Vec3f& ray_origin, const Vec3f& ray_dir);

    // Mouse events (return true if handled)
    bool on_mouse_move(const Vec3f& ray_origin, const Vec3f& ray_dir);
    bool on_mouse_down(const Vec3f& ray_origin, const Vec3f& ray_dir);
    bool on_mouse_up();

private:
    void _end_drag();
    void _update_drag(const Vec3f& ray_origin, const Vec3f& ray_dir);

    std::optional<Vec3f> _project_ray_to_constraint(
        const Vec3f& ray_origin,
        const Vec3f& ray_dir,
        const DragConstraint& constraint
    );

    SolidPrimitiveRenderer* _ensure_solid_renderer();
};

} // namespace termin
