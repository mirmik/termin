#pragma once

#include "termin/editor/gizmo.hpp"

#include <array>
#include <string>

extern "C" {
#include "core/tc_camera_capability.h"
}

namespace termin {

class EditorInteractionSystem;

struct CameraFrustumCorners {
    std::array<Vec3, 8> points;
};

bool compute_camera_frustum_corners(
    const tc_camera_data& camera,
    CameraFrustumCorners& out,
    std::string* error = nullptr
);

class CameraFrustumDebugGizmo final : public Gizmo {
public:
    explicit CameraFrustumDebugGizmo(EditorInteractionSystem* system);

    void draw(ImmediateRenderer* renderer) override;
    std::vector<GizmoCollider> get_colliders() override;

private:
    EditorInteractionSystem* _system = nullptr;
};

} // namespace termin
