#include "gizmo_manager.hpp"
#include "termin/render/immediate_renderer.hpp"
#include "termin/render/solid_primitive_renderer.hpp"
#include "tgfx/graphics_backend.hpp"

extern "C" {
#include "tc_profiler.h"
}

#include <algorithm>

namespace termin {

GizmoManager::~GizmoManager() {
    if (_owns_solid_renderer && _solid_renderer) {
        delete _solid_renderer;
    }
    if (_active_collider) {
        delete _active_collider;
    }
}

void GizmoManager::add_gizmo(Gizmo* gizmo) {
    if (std::find(_gizmos.begin(), _gizmos.end(), gizmo) == _gizmos.end()) {
        _gizmos.push_back(gizmo);
    }
}

void GizmoManager::remove_gizmo(Gizmo* gizmo) {
    auto it = std::find(_gizmos.begin(), _gizmos.end(), gizmo);
    if (it != _gizmos.end()) {
        _gizmos.erase(it);
        if (_active_gizmo == gizmo) {
            _end_drag();
        }
        if (_hovered_gizmo == gizmo) {
            _hovered_gizmo = nullptr;
            _hovered_collider_id = -1;
        }
    }
}

void GizmoManager::clear() {
    _end_drag();
    _gizmos.clear();
    _hovered_gizmo = nullptr;
    _hovered_collider_id = -1;
}

SolidPrimitiveRenderer* GizmoManager::_ensure_solid_renderer() {
    if (!_solid_renderer) {
        _solid_renderer = new SolidPrimitiveRenderer();
        _owns_solid_renderer = true;
    }
    return _solid_renderer;
}

void GizmoManager::render(
    ImmediateRenderer* renderer,
    GraphicsBackend* graphics,
    const Mat44f& view_matrix,
    const Mat44f& proj_matrix
) {
    bool profile = tc_profiler_enabled();
    if (profile) tc_profiler_begin_section("GizmoManager::render");

    // Separate gizmos by renderer type
    std::vector<Gizmo*> solid_gizmos;
    std::vector<Gizmo*> immediate_gizmos;

    for (Gizmo* gizmo : _gizmos) {
        if (gizmo->visible) {
            if (gizmo->uses_solid_renderer()) {
                solid_gizmos.push_back(gizmo);
            } else {
                immediate_gizmos.push_back(gizmo);
            }
        }
    }

    // Pass 1: Opaque geometry

    // Solid renderer gizmos
    if (!solid_gizmos.empty()) {
        SolidPrimitiveRenderer* solid = _ensure_solid_renderer();
        solid->begin(graphics, view_matrix, proj_matrix, true, false);
        for (Gizmo* gizmo : solid_gizmos) {
            gizmo->draw_solid(solid, graphics, view_matrix, proj_matrix);
        }
        solid->end();
    }

    // Immediate renderer gizmos
    if (!immediate_gizmos.empty()) {
        renderer->begin();
        for (Gizmo* gizmo : immediate_gizmos) {
            gizmo->draw(renderer);
        }
        // Convert Mat44f to Mat44 for flush
        Mat44 view_d, proj_d;
        for (int i = 0; i < 16; ++i) {
            view_d.data[i] = view_matrix.data[i];
            proj_d.data[i] = proj_matrix.data[i];
        }
        renderer->flush(graphics, view_d, proj_d, true, false);
    }

    // Pass 2: Transparent geometry

    // Solid renderer transparent
    if (!solid_gizmos.empty()) {
        SolidPrimitiveRenderer* solid = _ensure_solid_renderer();
        solid->begin(graphics, view_matrix, proj_matrix, true, true);
        for (Gizmo* gizmo : solid_gizmos) {
            gizmo->draw_transparent_solid(solid, graphics, view_matrix, proj_matrix);
        }
        solid->end();
    }

    // Immediate renderer transparent
    if (!immediate_gizmos.empty()) {
        renderer->begin();
        for (Gizmo* gizmo : immediate_gizmos) {
            gizmo->draw_transparent(renderer);
        }
        Mat44 view_d, proj_d;
        for (int i = 0; i < 16; ++i) {
            view_d.data[i] = view_matrix.data[i];
            proj_d.data[i] = proj_matrix.data[i];
        }
        renderer->flush(graphics, view_d, proj_d, true, true);
    }

    // Restore default state
    graphics->set_blend(false);

    if (profile) tc_profiler_end_section();
}

std::optional<GizmoHit> GizmoManager::raycast(const Vec3f& ray_origin, const Vec3f& ray_dir) {
    std::optional<GizmoHit> best_hit;

    for (Gizmo* gizmo : _gizmos) {
        if (!gizmo->visible) continue;

        std::vector<GizmoCollider> colliders = gizmo->get_colliders();
        for (const auto& collider : colliders) {
            auto t = collider.ray_intersect(ray_origin, ray_dir);
            if (t.has_value()) {
                if (!best_hit.has_value() || t.value() < best_hit->t) {
                    best_hit = GizmoHit{gizmo, collider, t.value()};
                }
            }
        }
    }

    return best_hit;
}

bool GizmoManager::on_mouse_move(const Vec3f& ray_origin, const Vec3f& ray_dir) {
    if (_active_gizmo != nullptr) {
        _update_drag(ray_origin, ray_dir);
        return true;
    }

    // Update hover state
    auto hit = raycast(ray_origin, ray_dir);
    Gizmo* new_hovered = hit.has_value() ? hit->gizmo : nullptr;
    int new_collider_id = hit.has_value() ? hit->collider.id : -1;

    if (_hovered_gizmo != new_hovered || _hovered_collider_id != new_collider_id) {
        // Exit old hover
        if (_hovered_gizmo != nullptr) {
            _hovered_gizmo->on_hover_exit(_hovered_collider_id);
        }

        // Enter new hover
        _hovered_gizmo = new_hovered;
        _hovered_collider_id = new_collider_id;

        if (_hovered_gizmo != nullptr) {
            _hovered_gizmo->on_hover_enter(_hovered_collider_id);
        }
    }

    return false;
}

bool GizmoManager::on_mouse_down(const Vec3f& ray_origin, const Vec3f& ray_dir) {
    auto hit = raycast(ray_origin, ray_dir);
    if (!hit.has_value()) {
        return false;
    }

    _active_gizmo = hit->gizmo;

    // Store active collider (need to allocate since we need it for drag)
    if (_active_collider) {
        delete _active_collider;
    }
    _active_collider = new GizmoCollider(hit->collider);

    _drag_start_ray_origin = ray_origin;
    _drag_start_ray_dir = ray_dir;

    // Compute initial drag position
    auto pos = _project_ray_to_constraint(ray_origin, ray_dir, _active_collider->constraint);
    if (pos.has_value()) {
        _last_drag_position = pos.value();
        _has_last_drag_position = true;
    } else {
        _has_last_drag_position = false;
    }

    _active_gizmo->on_click(
        _active_collider->id,
        _has_last_drag_position ? &_last_drag_position : nullptr
    );

    return true;
}

bool GizmoManager::on_mouse_up() {
    if (_active_gizmo == nullptr) {
        return false;
    }

    _active_gizmo->on_release(_active_collider->id);
    _end_drag();
    return true;
}

void GizmoManager::_end_drag() {
    _active_gizmo = nullptr;
    if (_active_collider) {
        delete _active_collider;
        _active_collider = nullptr;
    }
    _has_last_drag_position = false;
}

void GizmoManager::_update_drag(const Vec3f& ray_origin, const Vec3f& ray_dir) {
    if (_active_gizmo == nullptr || _active_collider == nullptr) {
        return;
    }

    // Check for NoDrag
    if (std::holds_alternative<NoDrag>(_active_collider->constraint)) {
        return;
    }

    auto new_position = _project_ray_to_constraint(ray_origin, ray_dir, _active_collider->constraint);
    if (!new_position.has_value()) {
        return;
    }

    Vec3f delta{0.0f, 0.0f, 0.0f};
    if (_has_last_drag_position) {
        delta = new_position.value() - _last_drag_position;
    }

    _last_drag_position = new_position.value();
    _has_last_drag_position = true;

    _active_gizmo->on_drag(
        _active_collider->id,
        new_position.value(),
        delta
    );
}

std::optional<Vec3f> GizmoManager::_project_ray_to_constraint(
    const Vec3f& ray_origin,
    const Vec3f& ray_dir,
    const DragConstraint& constraint
) {
    if (std::holds_alternative<AxisConstraint>(constraint)) {
        const auto& c = std::get<AxisConstraint>(constraint);
        return closest_point_on_axis(ray_origin, ray_dir, c.origin, c.axis);
    }
    else if (std::holds_alternative<PlaneConstraint>(constraint)) {
        const auto& c = std::get<PlaneConstraint>(constraint);
        return ray_plane_intersect(ray_origin, ray_dir, c.origin, c.normal);
    }
    else if (std::holds_alternative<AngleConstraint>(constraint)) {
        const auto& c = std::get<AngleConstraint>(constraint);
        // For rotation, return point on plane (angle computed by gizmo)
        return ray_plane_intersect(ray_origin, ray_dir, c.center, c.axis);
    }
    else if (std::holds_alternative<RadiusConstraint>(constraint)) {
        const auto& c = std::get<RadiusConstraint>(constraint);
        // Project to plane through center perpendicular to Y (simplified)
        return ray_plane_intersect(ray_origin, ray_dir, c.center, Vec3f{0.0f, 1.0f, 0.0f});
    }
    else if (std::holds_alternative<NoDrag>(constraint)) {
        return std::nullopt;
    }

    return std::nullopt;
}

} // namespace termin
