#pragma once

#include <optional>

#include <termin/camera/camera_component.hpp>
#include <termin/render/render_camera.hpp>

namespace termin {

inline RenderCamera make_render_camera(const CameraComponent& camera, std::optional<double> aspect_override = std::nullopt) {
    RenderCamera result;
    result.view = camera.get_view_matrix();
    result.projection = aspect_override
        ? camera.compute_projection_matrix(*aspect_override)
        : camera.get_projection_matrix();
    result.position = camera.get_position();
    result.near_clip = camera.near_clip;
    result.far_clip = camera.far_clip;
    return result;
}

} // namespace termin
