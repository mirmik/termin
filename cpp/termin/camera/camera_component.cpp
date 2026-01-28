#include "camera_component.hpp"
#include "../entity/component_registry.hpp"

#ifdef TERMIN_HAS_NANOBIND
#include "tc_inspect.hpp"
#else
#include "tc_inspect_cpp.hpp"
#endif

extern "C" {
#include "tc_value.h"
}

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

std::string CameraComponent::get_fov_mode_str() const {
    switch (fov_mode) {
        case FovMode::FixHorizontal: return "FixHorizontal";
        case FovMode::FixVertical: return "FixVertical";
        case FovMode::FixBoth: return "FixBoth";
        default: return "FixHorizontal";
    }
}

void CameraComponent::set_fov_mode_str(const std::string& mode) {
    if (mode == "FixVertical") {
        fov_mode = FovMode::FixVertical;
    } else if (mode == "FixBoth") {
        fov_mode = FovMode::FixBoth;
    } else {
        fov_mode = FovMode::FixHorizontal;
    }
}

double CameraComponent::get_fov_x_degrees() const {
    return fov_x * 180.0 / M_PI;
}

void CameraComponent::set_fov_x_degrees(double deg) {
    fov_x = deg * M_PI / 180.0;
}

double CameraComponent::get_fov_y_degrees() const {
    return fov_y * 180.0 / M_PI;
}

void CameraComponent::set_fov_y_degrees(double deg) {
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
        double safe_aspect = std::max(1e-6, aspect_override);

        switch (fov_mode) {
            case FovMode::FixHorizontal: {
                // Compute vertical FOV from horizontal FOV and aspect
                double computed_fov_y = 2.0 * std::atan(std::tan(fov_x * 0.5) / safe_aspect);
                return Mat44::perspective(computed_fov_y, safe_aspect, near_clip, far_clip);
            }
            case FovMode::FixVertical: {
                // Use vertical FOV directly
                return Mat44::perspective(fov_y, safe_aspect, near_clip, far_clip);
            }
            case FovMode::FixBoth: {
                // Use both FOVs independently (may cause distortion)
                return Mat44::perspective_fov_xy(fov_x, fov_y, near_clip, far_clip);
            }
            default:
                return Mat44::perspective(fov_y, safe_aspect, near_clip, far_clip);
        }
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

// Register fov_mode field with choices
static struct _FovModeFieldRegistrar {
    _FovModeFieldRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "CameraComponent";
        info.path = "fov_mode";
        info.label = "FOV Mode";
        info.kind = "string";

        info.choices.push_back({"FixHorizontal", "Fix Horizontal"});
        info.choices.push_back({"FixVertical", "Fix Vertical"});
        info.choices.push_back({"FixBoth", "Fix Both"});

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<CameraComponent*>(obj);
            return tc_value_string(c->get_fov_mode_str().c_str());
        };

        info.setter = [](void* obj, tc_value value, tc_scene*) {
            auto* c = static_cast<CameraComponent*>(obj);
            if (value.type == TC_VALUE_STRING && value.data.s) {
                c->set_fov_mode_str(value.data.s);
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("CameraComponent", std::move(info));
    }
} _fov_mode_registrar;

} // namespace termin
