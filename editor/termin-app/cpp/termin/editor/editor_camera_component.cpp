#include "editor_camera_component.hpp"

#include <termin/camera/orbit_camera_controller.hpp>
#include <termin/entity/component_registry.hpp>
#include <tcbase/tc_log.h>

#include <algorithm>
#include <cmath>

namespace termin {

    EditorCameraComponent::EditorCameraComponent() : CameraComponent("EditorCameraComponent") {
        set_has_update(true);
        set_active_in_editor(true);
    }

    void EditorCameraComponent::register_type() {
        if (ComponentRegistry::instance().has("EditorCameraComponent")) {
            return;
        }
        auto descriptor = ComponentTypeDescriptorBuilder::native<EditorCameraComponent>(
            "EditorCameraComponent", "termin-app", "CameraComponent");
        descriptor.category("Editor");
        (void)descriptor.commit();
    }

    void EditorCameraComponent::request_frame() {
        if (request_render_callback) {
            request_render_callback();
        }
    }

    void EditorCameraComponent::enter_axis_view(double focus_distance) {
        if (!std::isfinite(focus_distance) || focus_distance <= 0.0) {
            tc_log_error("EditorCameraComponent: axis view requires a positive finite focus distance");
            return;
        }
        if (entity().valid()) {
            axis_rotation_ = entity().transform().global_rotation();
        }
        if (axis_view_) {
            request_frame();
            return;
        }
        // A camera already configured as orthographic stays orthographic on rotation.
        if (!temporary_orthographic_ && projection_type == CameraProjection::Orthographic) {
            request_frame();
            return;
        }
        if (!temporary_orthographic_) {
            focus_distance_ = focus_distance;
            original_ortho_size_ = ortho_size;
            const Mat44 perspective = compute_perspective_matrix(aspect);
            initial_ortho_size_ = focus_distance_ / -perspective(2, 1);
            ortho_size = initial_ortho_size_;
            temporary_orthographic_ = true;
        }
        axis_view_ = true;
        projection_type = CameraProjection::Orthographic;
        request_frame();
    }

    void EditorCameraComponent::leave_axis_view() {
        if (!axis_view_) {
            return;
        }
        // Orthographic wheel zoom changes image scale rather than camera position.
        // Transfer that zoom to orbit distance before returning to the original FOV.
        if (blend_ == 1.0 && entity().valid()) {
            if (auto* orbit = entity().get_component<OrbitCameraController>()) {
                const double zoom = std::max(1e-6, ortho_size / initial_ortho_size_);
                if (std::abs(zoom - 1.0) > 1e-12) {
                    const double new_distance = std::clamp(focus_distance_ * zoom,
                                                          orbit->min_radius, orbit->max_radius);
                    const auto transform = entity().transform();
                    const Quat rotation = transform.global_rotation();
                    const Vec3 position = transform.global_position() +
                        rotation.rotate(Vec3::unit_y()) * (orbit->radius - new_distance);
                    orbit->radius = new_distance;
                    entity().transform().relocate(Pose3{rotation, position});
                    orbit->_sync_from_transform();
                    initial_ortho_size_ *= new_distance / focus_distance_;
                    focus_distance_ = new_distance;
                }
            }
        }
        axis_view_ = false;
        projection_type = CameraProjection::Perspective;
        request_frame();
    }

    void EditorCameraComponent::reset_projection_transition() {
        if (temporary_orthographic_) {
            projection_type = CameraProjection::Perspective;
            ortho_size = original_ortho_size_;
        }
        axis_view_ = false;
        temporary_orthographic_ = false;
        blend_ = 0.0;
    }

    void EditorCameraComponent::set_projection_type_str(const std::string& type) {
        reset_projection_transition();
        CameraComponent::set_projection_type_str(type);
        request_frame();
    }

    void EditorCameraComponent::finish_projection_transition() {
        blend_ = axis_view_ ? 1.0 : 0.0;
        if (!axis_view_) {
            reset_projection_transition();
        }
        request_frame();
    }

    void EditorCameraComponent::update(float dt) {
        if (axis_view_ && entity().valid()) {
            const Quat rotation = entity().transform().global_rotation();
            const double dot = rotation.x * axis_rotation_.x + rotation.y * axis_rotation_.y +
                               rotation.z * axis_rotation_.z + rotation.w * axis_rotation_.w;
            if (std::abs(dot) < 1.0 - 1e-10) {
                leave_axis_view();
            }
        }
        if (!transitioning()) {
            return;
        }
        if (!std::isfinite(dt) || dt < 0.0f) {
            tc_log_error("EditorCameraComponent: invalid projection transition dt");
            return;
        }
        const double step = std::isfinite(transition_duration) && transition_duration > 0.0
                                ? dt / transition_duration : 1.0;
        blend_ = axis_view_ ? std::min(1.0, blend_ + step) : std::max(0.0, blend_ - step);
        if (!axis_view_ && blend_ == 0.0) {
            reset_projection_transition();
        }
        request_frame();
    }

    Mat44 EditorCameraComponent::compute_projection_matrix(double aspect_override) const {
        if (!temporary_orthographic_) {
            return CameraComponent::compute_projection_matrix(aspect_override);
        }
        const Mat44 perspective = compute_perspective_matrix(aspect_override);
        const double zoom = std::max(1e-6, ortho_size / initial_ortho_size_);
        Mat44 ortho = Mat44::orthographic(-1.0, 1.0, -1.0, 1.0, near_clip, far_clip);
        ortho(0, 0) = perspective(0, 0) / (focus_distance_ * zoom);
        ortho(2, 1) = perspective(2, 1) / (focus_distance_ * zoom);
        Mat44 result;
        // At the focus plane perspective w / distance == orthographic w == 1.
        // Interpolating these homogeneous matrices keeps all plane points fixed.
        const double t = blend_ * blend_ * (3.0 - 2.0 * blend_);
        for (int i = 0; i < 16; ++i) {
            result.data[i] = (1.0 - t) * perspective.data[i] / focus_distance_ + t * ortho.data[i];
        }
        return result;
    }

} // namespace termin
