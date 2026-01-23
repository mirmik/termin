#pragma once

#include "../entity/component.hpp"
#include "../entity/component_registry.hpp"
#include "../entity/entity.hpp"
#include "../geom/mat44.hpp"
#include "../geom/pose3.hpp"
#include "../geom/general_pose3.hpp"
#include "../viewport/tc_viewport_handle.hpp"
#include "camera.hpp"

#include <vector>
#include <algorithm>
#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

// CameraComponent - component that provides view/projection matrices.
// Uses entity transform for view matrix computation.
class CameraComponent : public CxxComponent {
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

    // INSPECT_FIELD registrations
    INSPECT_FIELD(CameraComponent, near_clip, "Near Clip", "double", 0.001, 10000.0, 0.01)
    INSPECT_FIELD(CameraComponent, far_clip, "Far Clip", "double", 0.01, 100000.0, 1.0)
    INSPECT_FIELD(CameraComponent, ortho_size, "Ortho Size", "double", 0.1, 1000.0, 0.5)

    CameraComponent() {
        set_type_name("CameraComponent");
    }

    // Get projection type as string
    std::string get_projection_type_str() const {
        return projection_type == CameraProjection::Perspective ? "perspective" : "orthographic";
    }

    // Set projection type from string
    void set_projection_type_str(const std::string& type) {
        if (type == "orthographic") {
            projection_type = CameraProjection::Orthographic;
        } else {
            projection_type = CameraProjection::Perspective;
        }
    }

    // Get FOV in degrees
    double get_fov_degrees() const {
        return fov_y * 180.0 / M_PI;
    }

    // Set FOV in degrees
    void set_fov_degrees(double deg) {
        fov_y = deg * M_PI / 180.0;
    }

    // Set aspect ratio
    void set_aspect(double a) {
        aspect = a;
    }

    // Get view matrix (from entity transform)
    Mat44 get_view_matrix() const {
        if (!entity.valid()) {
            return Mat44::identity();
        }

        // Get global pose (ignore scale for view matrix)
        GeneralPose3 gpose = entity.transform().global_pose();
        Pose3 pose(gpose.ang, gpose.lin);
        Pose3 inv_pose = pose.inverse();
        return inv_pose.as_mat44();
    }

    // Get projection matrix
    Mat44 get_projection_matrix() const {
        if (projection_type == CameraProjection::Orthographic) {
            double top = ortho_size;
            double bottom = -ortho_size;
            double right = ortho_size * aspect;
            double left = -right;
            return Mat44::orthographic(left, right, bottom, top, near_clip, far_clip);
        } else {
            return Mat44::perspective(fov_y, std::max(1e-6, aspect), near_clip, far_clip);
        }
    }

    // Get camera world position
    Vec3 get_position() const {
        if (!entity.valid()) {
            return Vec3::zero();
        }
        return entity.transform().global_position();
    }

    // Viewport management (stored as TcViewport with reference counting)
    void add_viewport(const TcViewport& vp) {
        if (!vp.is_valid()) return;
        for (auto& v : viewports_) {
            if (v.ptr_ == vp.ptr_) return;
        }
        viewports_.push_back(vp);
    }

    void remove_viewport(const TcViewport& vp) {
        viewports_.erase(
            std::remove_if(viewports_.begin(), viewports_.end(),
                [&vp](const TcViewport& v) { return v.ptr_ == vp.ptr_; }),
            viewports_.end()
        );
    }

    bool has_viewport(const TcViewport& vp) const {
        for (const auto& v : viewports_) {
            if (v.ptr_ == vp.ptr_) return true;
        }
        return false;
    }

    size_t viewport_count() const {
        return viewports_.size();
    }

    TcViewport viewport_at(size_t index) const {
        return index < viewports_.size() ? viewports_[index] : TcViewport();
    }

    void clear_viewports() {
        viewports_.clear();
    }

    // Lifecycle
    void on_scene_inactive() override {
        clear_viewports();
    }

    // Screen point to ray (requires viewport rect)
    // Returns (origin, direction) pair
    std::pair<Vec3, Vec3> screen_point_to_ray(double x, double y, int vp_x, int vp_y, int vp_w, int vp_h) const {
        // Use viewport aspect for calculation
        double vp_aspect = static_cast<double>(vp_w) / std::max(1, vp_h);

        // Normalized device coordinates
        double nx = ((x - vp_x) / vp_w) * 2.0 - 1.0;
        double ny = ((y - vp_y) / vp_h) * -2.0 + 1.0;

        // Compute inverse PV matrix with viewport aspect
        CameraComponent temp = *this;
        temp.aspect = vp_aspect;
        Mat44 pv = temp.get_projection_matrix() * get_view_matrix();
        Mat44 inv_pv = pv.inverse();

        // Transform near and far points
        Vec3 p_near = inv_pv.transform_point(Vec3{nx, ny, -1.0});
        Vec3 p_far = inv_pv.transform_point(Vec3{nx, ny, 1.0});

        Vec3 direction = (p_far - p_near).normalized();
        return {p_near, direction};
    }

private:
    std::vector<TcViewport> viewports_;
};

REGISTER_COMPONENT(CameraComponent, CxxComponent);

} // namespace termin
