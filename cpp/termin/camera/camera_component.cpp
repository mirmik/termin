#include "camera_component.hpp"
#include "../entity/component_registry.hpp"

#include <algorithm>
#include <cmath>

namespace termin {

CameraComponent::CameraComponent() {
    // Link to type registry for proper type identification
    link_type_entry("CameraComponent");
}

std::string CameraComponent::get_projection_type_str() const {
    return projection_type == CameraProjection::Perspective ? "perspective" : "orthographic";
}

void CameraComponent::set_projection_type_str(const std::string& type) {
    if (type == "orthographic") {
        projection_type = CameraProjection::Orthographic;
    } else {
        projection_type = CameraProjection::Perspective;
    }
}

double CameraComponent::get_fov_degrees() const {
    return fov_y * 180.0 / M_PI;
}

void CameraComponent::set_fov_degrees(double deg) {
    fov_y = deg * M_PI / 180.0;
}

void CameraComponent::set_aspect(double a) {
    aspect = a;
}

Mat44 CameraComponent::get_view_matrix() const {
    if (!entity().valid()) {
        return Mat44::identity();
    }

    // Get global pose (ignore scale for view matrix)
    GeneralPose3 gpose = entity().transform().global_pose();
    Pose3 pose(gpose.ang, gpose.lin);
    Pose3 inv_pose = pose.inverse();
    return inv_pose.as_mat44();
}

Mat44 CameraComponent::get_projection_matrix() const {
    return compute_projection_matrix(aspect);
}

Mat44 CameraComponent::compute_projection_matrix(double aspect_override) const {
    if (projection_type == CameraProjection::Orthographic) {
        double top = ortho_size;
        double bottom = -ortho_size;
        double right = ortho_size * aspect_override;
        double left = -right;
        return Mat44::orthographic(left, right, bottom, top, near_clip, far_clip);
    } else {
        return Mat44::perspective(fov_y, std::max(1e-6, aspect_override), near_clip, far_clip);
    }
}

Vec3 CameraComponent::get_position() const {
    if (!entity().valid()) {
        return Vec3::zero();
    }
    return entity().transform().global_position();
}

void CameraComponent::add_viewport(const TcViewport& vp) {
    if (!vp.is_valid()) return;
    for (auto& v : viewports_) {
        if (v.ptr_ == vp.ptr_) return;
    }
    viewports_.push_back(vp);
}

void CameraComponent::remove_viewport(const TcViewport& vp) {
    viewports_.erase(
        std::remove_if(viewports_.begin(), viewports_.end(),
            [&vp](const TcViewport& v) { return v.ptr_ == vp.ptr_; }),
        viewports_.end()
    );
}

bool CameraComponent::has_viewport(const TcViewport& vp) const {
    for (const auto& v : viewports_) {
        if (v.ptr_ == vp.ptr_) return true;
    }
    return false;
}

size_t CameraComponent::viewport_count() const {
    return viewports_.size();
}

TcViewport CameraComponent::viewport_at(size_t index) const {
    return index < viewports_.size() ? viewports_[index] : TcViewport();
}

void CameraComponent::clear_viewports() {
    viewports_.clear();
}

void CameraComponent::on_scene_inactive() {
    clear_viewports();
}

std::pair<Vec3, Vec3> CameraComponent::screen_point_to_ray(double x, double y, int vp_x, int vp_y, int vp_w, int vp_h) const {
    // Use viewport aspect for calculation
    double vp_aspect = static_cast<double>(vp_w) / std::max(1, vp_h);

    // Normalized device coordinates
    double nx = ((x - vp_x) / vp_w) * 2.0 - 1.0;
    double ny = ((y - vp_y) / vp_h) * -2.0 + 1.0;

    // Compute projection matrix with viewport aspect (without copying self)
    Mat44 proj_matrix = compute_projection_matrix(vp_aspect);
    Mat44 pv = proj_matrix * get_view_matrix();
    Mat44 inv_pv = pv.inverse();

    // Transform near and far points
    Vec3 p_near = inv_pv.transform_point(Vec3{nx, ny, -1.0});
    Vec3 p_far = inv_pv.transform_point(Vec3{nx, ny, 1.0});

    Vec3 direction = (p_far - p_near).normalized();
    return {p_near, direction};
}

REGISTER_COMPONENT(CameraComponent, CxxComponent);

} // namespace termin
