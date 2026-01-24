#pragma once

#include "../export.hpp"
#include "../entity/component.hpp"
#include "../entity/entity.hpp"
#include "../geom/mat44.hpp"
#include "../geom/pose3.hpp"
#include "../geom/general_pose3.hpp"
#include "../viewport/tc_viewport_handle.hpp"
#include "camera.hpp"

#include <vector>
#include <string>
#include <utility>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

// CameraComponent - component that provides view/projection matrices.
// Uses entity transform for view matrix computation.
class ENTITY_API CameraComponent : public CxxComponent {
public:
    // Projection type
    CameraProjection projection_type = CameraProjection::Perspective;

    // Common parameters
    double near_clip = 0.1;
    double far_clip = 100.0;

    // Perspective parameters
    double fov_y = M_PI / 3.0;  // 60 degrees
    double aspect = 1.0;

    // Orthographic parameters
    double ortho_size = 5.0;  // Half-height

private:
    std::vector<TcViewport> viewports_;

public:
    // INSPECT_FIELD registrations
    INSPECT_FIELD(CameraComponent, near_clip, "Near Clip", "double", 0.001, 10000.0, 0.01)
    INSPECT_FIELD(CameraComponent, far_clip, "Far Clip", "double", 0.01, 100000.0, 1.0)
    INSPECT_FIELD(CameraComponent, ortho_size, "Ortho Size", "double", 0.1, 1000.0, 0.5)

    CameraComponent();

    // Projection type accessors
    std::string get_projection_type_str() const;
    void set_projection_type_str(const std::string& type);

    // FOV accessors (degrees)
    double get_fov_degrees() const;
    void set_fov_degrees(double deg);

    // Aspect ratio
    void set_aspect(double a);

    // Matrix getters
    Mat44 get_view_matrix() const;
    Mat44 get_projection_matrix() const;

    // Camera world position
    Vec3 get_position() const;

    // Viewport management
    void add_viewport(const TcViewport& vp);
    void remove_viewport(const TcViewport& vp);
    bool has_viewport(const TcViewport& vp) const;
    size_t viewport_count() const;
    TcViewport viewport_at(size_t index) const;
    void clear_viewports();

    // Lifecycle
    void on_scene_inactive() override;

    // Screen point to ray (returns origin, direction pair)
    std::pair<Vec3, Vec3> screen_point_to_ray(double x, double y, int vp_x, int vp_y, int vp_w, int vp_h) const;
};

} // namespace termin

