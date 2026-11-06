#pragma once

#include <termin/camera/orbit_camera.hpp>

#include "tcplot/retained_chart3d.h"

namespace tcplot::detail {

    inline tc_orbit_camera3d_state camera_state(const termin::OrbitCamera& camera) {
        return {camera.target.x,
                camera.target.y,
                camera.target.z,
                camera.distance,
                camera.azimuth,
                camera.elevation,
                camera.fov_y,
                camera.near_clip,
                camera.far_clip,
                static_cast<tc_camera_projection3d>(camera.projection_type),
                camera.ortho_size};
    }

    inline void apply_camera_state(termin::OrbitCamera& camera, const tc_orbit_camera3d_state& state) {
        camera.target = {state.target_x, state.target_y, state.target_z};
        camera.distance = state.distance;
        camera.azimuth = state.azimuth;
        camera.elevation = state.elevation;
        camera.fov_y = state.fov_y;
        camera.near_clip = state.near_clip;
        camera.far_clip = state.far_clip;
        camera.projection_type = static_cast<termin::CameraProjection>(state.projection_type);
        camera.ortho_size = state.ortho_size;
    }

    inline termin::OrbitCamera camera_from_state(const tc_orbit_camera3d_state& state) {
        termin::OrbitCamera camera;
        apply_camera_state(camera, state);
        return camera;
    }

} // namespace tcplot::detail
