#pragma once

#include "termin/editor/gizmo_types.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/render/types.hpp"

#include <vector>

namespace termin {

class ImmediateRenderer;
class SolidPrimitiveRenderer;
class GraphicsBackend;

// ============================================================
// Gizmo Base Class
// ============================================================

class Gizmo {
public:
    bool visible = true;

    virtual ~Gizmo() = default;

    // Draw opaque geometry using ImmediateRenderer
    virtual void draw(ImmediateRenderer* renderer) {}

    // Draw opaque geometry using SolidPrimitiveRenderer (more efficient)
    virtual void draw_solid(
        SolidPrimitiveRenderer* renderer,
        GraphicsBackend* graphics,
        const Mat44f& view,
        const Mat44f& proj
    ) {}

    // Draw transparent geometry
    virtual void draw_transparent(ImmediateRenderer* renderer) {}

    virtual void draw_transparent_solid(
        SolidPrimitiveRenderer* renderer,
        GraphicsBackend* graphics,
        const Mat44f& view,
        const Mat44f& proj
    ) {}

    // Whether this gizmo uses SolidPrimitiveRenderer
    virtual bool uses_solid_renderer() const { return false; }

    // Get colliders for picking
    virtual std::vector<GizmoCollider> get_colliders() = 0;

    // Event callbacks
    virtual void on_hover_enter(int collider_id) {}
    virtual void on_hover_exit(int collider_id) {}
    virtual void on_click(int collider_id, const Vec3f* hit_position) {}
    virtual void on_drag(int collider_id, const Vec3f& position, const Vec3f& delta) {}
    virtual void on_release(int collider_id) {}
};

} // namespace termin
