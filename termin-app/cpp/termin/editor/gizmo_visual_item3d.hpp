#pragma once

#include "termin/editor/editor_overlay_scene3d.hpp"
#include "termin/editor/gizmo.hpp"

#include <memory>
#include <optional>

#include <termin_visual_scene/native_visual_item3d.hpp>

namespace termin {

    // Transitional retained wrapper for a legacy world-space Gizmo. Picking
    // and interaction are owned here; VisualScene3D sees an ordinary item and
    // one editor draw protocol packet.
    class GizmoVisualItem3D final : public visual::NativeVisualItem3D,
                                    public EditorOverlayDrawable3D {
    public:
        explicit GizmoVisualItem3D(std::unique_ptr<Gizmo> gizmo);
        explicit GizmoVisualItem3D(Gizmo& borrowed_gizmo);
        ~GizmoVisualItem3D() override;

        Gizmo* gizmo() noexcept {
            return _gizmo;
        }
        const Gizmo* gizmo() const noexcept {
            return _gizmo;
        }

        std::optional<visual::VisualBounds3D> local_bounds() const override;
        std::optional<visual::HitCandidate3D>
        hit_test(const visual::HitTestContext3D& context) const override;
        bool paint(visual::GraphicItemPaintContext3D& context) const override;
        bool draw(const EditorOverlayDrawContext3D& context) const override;

        void bind_controller(visual::SceneInteraction3D& interaction);

    private:
        void _on_pointer(const visual::TargetPointerEvent3D& event);
        std::optional<GizmoCollider> _collider_for_part(std::uint64_t part) const;
        static std::optional<Vec3f>
        _project_ray_to_constraint(const Vec3f& ray_origin, const Vec3f& ray_direction, const DragConstraint& constraint);
        void _update_drag(const visual::PointerEvent3D& event);
        void _reset_drag();

        std::unique_ptr<Gizmo> _owned_gizmo;
        Gizmo* _gizmo = nullptr;
        mutable std::unique_ptr<SolidPrimitiveRenderer> _solid_renderer;
        std::optional<GizmoCollider> _active_collider;
        Vec3f _last_drag_position{};
        bool _has_last_drag_position = false;
    };

} // namespace termin
