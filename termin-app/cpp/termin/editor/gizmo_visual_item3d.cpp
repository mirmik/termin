#include "termin/editor/gizmo_visual_item3d.hpp"

#include "termin/render/solid_primitive_renderer.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

#include <tcbase/tc_log.h>
#include <tgfx2/immediate_renderer.hpp>
#include <tgfx2/render_context.hpp>

namespace termin {
    namespace {

        Vec3f to_vec3f(tc_vec3 value) {
            return {static_cast<float>(value.x), static_cast<float>(value.y), static_cast<float>(value.z)};
        }

        Mat44 to_mat44(const Mat44f& value) {
            Mat44 result;
            for (std::size_t index = 0; index < 16; ++index)
                result.data[index] = value.data[index];
            return result;
        }

    } // namespace

    GizmoVisualItem3D::GizmoVisualItem3D(std::unique_ptr<Gizmo> gizmo)
        : NativeVisualItem3D("termin.editor.GizmoVisualItem3D"),
          _owned_gizmo(std::move(gizmo)),
          _gizmo(_owned_gizmo.get()) {
        if (!_gizmo)
            tc_log(TC_LOG_ERROR, "[GizmoVisualItem3D] constructed without an owned gizmo");
    }

    GizmoVisualItem3D::GizmoVisualItem3D(Gizmo& borrowed_gizmo)
        : NativeVisualItem3D("termin.editor.GizmoVisualItem3D"),
          _gizmo(&borrowed_gizmo) {}

    GizmoVisualItem3D::~GizmoVisualItem3D() = default;

    std::optional<visual::VisualBounds3D> GizmoVisualItem3D::local_bounds() const {
        // Legacy colliders are already authored in world space. This adapter
        // deliberately stays identity-transformed and does not invent a
        // second bounds representation during migration.
        return std::nullopt;
    }

    std::optional<visual::HitCandidate3D>
    GizmoVisualItem3D::hit_test(const visual::HitTestContext3D& context) const {
        if (!_gizmo || !_gizmo->visible)
            return std::nullopt;
        const Vec3f origin = to_vec3f(context.world_ray.origin);
        const Vec3f direction = to_vec3f(context.world_ray.direction);
        std::optional<visual::HitCandidate3D> nearest;
        for (const auto& collider : _gizmo->get_colliders()) {
            const auto distance = collider.ray_intersect(origin, direction);
            if (distance && *distance > 0.0f && (!nearest || *distance < nearest->distance))
                nearest = visual::HitCandidate3D{*distance, static_cast<std::uint64_t>(collider.id)};
        }
        return nearest;
    }

    bool GizmoVisualItem3D::paint(visual::GraphicItemPaintContext3D& context) const {
        const EditorOverlayDrawPacket3D packet{this};
        return context.submit(EditorOverlayDrawProtocol3D, &packet, sizeof(packet));
    }

    bool GizmoVisualItem3D::draw(const EditorOverlayDrawContext3D& context) const {
        if (!_gizmo || !_gizmo->visible)
            return true;
        if (!context.renderer || !context.render_context) {
            tc_log(TC_LOG_ERROR, "[GizmoVisualItem3D] renderer and render context are required");
            return false;
        }

        if (_gizmo->uses_solid_renderer()) {
            if (!_solid_renderer)
                _solid_renderer = std::make_unique<SolidPrimitiveRenderer>();
            _solid_renderer->begin(context.render_context, context.view, context.projection, true, false);
            _gizmo->draw_solid(_solid_renderer.get(), context.render_context, context.view, context.projection);
            _solid_renderer->end();
            _solid_renderer->begin(context.render_context, context.view, context.projection, true, true);
            _gizmo->draw_transparent_solid(
                _solid_renderer.get(), context.render_context, context.view, context.projection);
            _solid_renderer->end();
        } else {
            const Mat44 view = to_mat44(context.view);
            const Mat44 projection = to_mat44(context.projection);
            context.renderer->begin();
            _gizmo->draw(context.renderer);
            context.renderer->flush(context.render_context, view, projection, true, false);
            context.renderer->begin();
            _gizmo->draw_transparent(context.renderer);
            context.renderer->flush(context.render_context, view, projection, true, true);
        }
        context.render_context->set_blend(false);
        return true;
    }

    void GizmoVisualItem3D::bind_controller(visual::SceneInteraction3D& interaction) {
        const auto item_handle = handle();
        if (tc_visual_item3d_handle_is_invalid(item_handle)) {
            tc_log(TC_LOG_ERROR, "[GizmoVisualItem3D] cannot bind controller before scene adoption");
            return;
        }
        interaction.set_target_pointer_handler(item_handle, [this](const auto& event) { _on_pointer(event); });
    }

    std::optional<GizmoCollider> GizmoVisualItem3D::_collider_for_part(std::uint64_t part) const {
        if (!_gizmo || part > static_cast<std::uint64_t>(std::numeric_limits<int>::max()))
            return std::nullopt;
        const int collider_id = static_cast<int>(part);
        for (const auto& collider : _gizmo->get_colliders()) {
            if (collider.id == collider_id)
                return collider;
        }
        return std::nullopt;
    }

    void GizmoVisualItem3D::_on_pointer(const visual::TargetPointerEvent3D& event) {
        if (!_gizmo)
            return;
        const int collider_id = static_cast<int>(event.part);
        switch (event.kind) {
        case visual::TargetPointerEventKind3D::Enter:
            _gizmo->on_hover_enter(collider_id);
            break;
        case visual::TargetPointerEventKind3D::Leave:
            _gizmo->on_hover_exit(collider_id);
            break;
        case visual::TargetPointerEventKind3D::Down: {
            _active_collider = _collider_for_part(event.part);
            if (!_active_collider) {
                tc_log(TC_LOG_ERROR, "[GizmoVisualItem3D] pressed collider part is no longer available");
                return;
            }
            const Vec3f origin = to_vec3f(event.pointer_event.world_ray.origin);
            const Vec3f direction = to_vec3f(event.pointer_event.world_ray.direction);
            const auto position = _project_ray_to_constraint(origin, direction, _active_collider->constraint);
            _has_last_drag_position = position.has_value();
            if (position)
                _last_drag_position = *position;
            _gizmo->on_click(collider_id, position ? &*position : nullptr);
            break;
        }
        case visual::TargetPointerEventKind3D::Move:
            if (event.captured)
                _update_drag(event.pointer_event);
            break;
        case visual::TargetPointerEventKind3D::Up:
            if (_active_collider)
                _gizmo->on_release(_active_collider->id);
            _reset_drag();
            break;
        case visual::TargetPointerEventKind3D::Cancel:
            if (_active_collider)
                _gizmo->on_cancel(_active_collider->id);
            _reset_drag();
            break;
        }
    }

    void GizmoVisualItem3D::_update_drag(const visual::PointerEvent3D& event) {
        if (!_active_collider || std::holds_alternative<NoDrag>(_active_collider->constraint))
            return;
        const auto position = _project_ray_to_constraint(to_vec3f(event.world_ray.origin),
                                                         to_vec3f(event.world_ray.direction),
                                                         _active_collider->constraint);
        if (!position)
            return;
        Vec3f delta{};
        if (_has_last_drag_position)
            delta = *position - _last_drag_position;
        _last_drag_position = *position;
        _has_last_drag_position = true;
        _gizmo->on_drag(_active_collider->id, *position, delta);
    }

    std::optional<Vec3f> GizmoVisualItem3D::_project_ray_to_constraint(const Vec3f& ray_origin,
                                                                       const Vec3f& ray_direction,
                                                                       const DragConstraint& constraint) {
        if (const auto* axis = std::get_if<AxisConstraint>(&constraint))
            return closest_point_on_axis(ray_origin, ray_direction, axis->origin, axis->axis);
        if (const auto* plane = std::get_if<PlaneConstraint>(&constraint))
            return ray_plane_intersect(ray_origin, ray_direction, plane->origin, plane->normal);
        if (const auto* angle = std::get_if<AngleConstraint>(&constraint))
            return ray_plane_intersect(ray_origin, ray_direction, angle->center, angle->axis);
        if (const auto* radius = std::get_if<RadiusConstraint>(&constraint))
            return ray_plane_intersect(ray_origin, ray_direction, radius->center, Vec3f{0.0f, 1.0f, 0.0f});
        return std::nullopt;
    }

    void GizmoVisualItem3D::_reset_drag() {
        _active_collider.reset();
        _has_last_drag_position = false;
    }

} // namespace termin
