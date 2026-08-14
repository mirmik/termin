#pragma once

#include "termin/editor/editor_overlay_scene3d.hpp"

#include <array>
#include <optional>
#include <string>

#include <termin_visual_scene/native_visual_item3d.hpp>

extern "C" {
#include "core/tc_camera_capability.h"
}

namespace termin {

    class EditorInteractionSystem;

    struct CameraFrustumCorners {
        std::array<Vec3, 8> points;
    };

    bool compute_camera_frustum_corners(const tc_camera_data& camera,
                                        CameraFrustumCorners& out,
                                        std::string* error = nullptr);

    class CameraFrustumOverlayItem3D final : public visual::NativeVisualItem3D,
                                             public EditorOverlayDrawable3D {
    private:
        EditorInteractionSystem* _system = nullptr;

    public:
        explicit CameraFrustumOverlayItem3D(EditorInteractionSystem* system);

        std::optional<visual::VisualBounds3D> local_bounds() const override;
        std::optional<visual::HitCandidate3D>
        hit_test(const visual::HitTestContext3D& context) const override;
        bool paint(visual::GraphicItemPaintContext3D& context) const override;
        bool draw(const EditorOverlayDrawContext3D& context) const override;
    };

} // namespace termin
