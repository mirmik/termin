#pragma once

#include <termin/camera/camera_component.hpp>
#include <functional>

namespace termin {

    // Viewport-owned camera: projection animation never depends on scene membership.
    class EditorCameraComponent : public CameraComponent {
    public:
        EditorCameraComponent();
        static void register_type();

        std::function<void()> request_render_callback;
        double transition_duration = 0.2;

        void enter_axis_view(double focus_distance);
        void leave_axis_view();
        void reset_projection_transition();
        void finish_projection_transition();
        void set_projection_type_str(const std::string& type) override;
        void update(float dt) override;
        Mat44 compute_projection_matrix(double aspect_override) const override;
        bool axis_view() const { return axis_view_; }
        bool transitioning() const { return blend_ != (axis_view_ ? 1.0 : 0.0); }
        std::string navigation_projection_type() const {
            return temporary_orthographic_ ? "perspective" : get_projection_type_str();
        }
        double navigation_ortho_size() const { return temporary_orthographic_ ? original_ortho_size_ : ortho_size; }

    private:
        void request_frame();
        bool axis_view_ = false;
        bool temporary_orthographic_ = false;
        double blend_ = 0.0;
        double focus_distance_ = 1.0;
        double initial_ortho_size_ = 1.0;
        double original_ortho_size_ = 5.0;
        Quat axis_rotation_ = Quat::identity();
    };

} // namespace termin
