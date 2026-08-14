#pragma once

#include <string>

#include <termin/entity/component.hpp>
#include <termin/export.hpp>
#include <termin/geom/pose3.hpp>
#include <termin/input/xr_input.hpp>

namespace termin {

    enum class XrTrackedPoseKind {
        Grip,
        Aim,
    };

    class XrDirectGrabInteractorComponent;

    class ENTITY_API XrTrackedPoseComponent : public CxxComponent {
    public:
        std::string input_device_id = "xr";
        xr::XrHand hand = xr::XrHand::Left;
        XrTrackedPoseKind pose_kind = XrTrackedPoseKind::Grip;

        XrTrackedPoseComponent();

        static void register_type();
        void update(float dt) override;

        bool tracking_active() const {
            return tracking_active_;
        }
        std::string get_hand_str() const;
        void set_hand_str(const std::string& value);
        std::string get_pose_kind_str() const;
        void set_pose_kind_str(const std::string& value);

    private:
        bool tracking_active_ = false;
        bool logged_missing_input_ = false;
        bool logged_missing_origin_ = false;
    };

    class ENTITY_API XrGrabInteractableComponent : public CxxComponent {
    public:
        double grab_radius = 0.12;
        bool grabbable = true;

        XrGrabInteractableComponent();

        static void register_type();
        void on_removed() override;
        void on_destroy() override;

        bool grabbed() const {
            return owner_ != nullptr;
        }

    private:
        XrDirectGrabInteractorComponent* owner_ = nullptr;

        friend class XrDirectGrabInteractorComponent;
    };

    class ENTITY_API XrDirectGrabInteractorComponent : public CxxComponent {
    public:
        double reach = 0.18;
        double select_threshold = 0.55;

        XrDirectGrabInteractorComponent();

        static void register_type();
        void update(float dt) override;
        void on_removed() override;
        void on_destroy() override;
        void on_scene_inactive() override;

        bool holding_object() const {
            return grabbed_entity_.valid();
        }
        void release_grabbed(XrGrabInteractableComponent* expected = nullptr);

    private:
        Entity grabbed_entity_;
        Pose3 hand_from_object_{};
        bool was_pressed_ = false;
        bool logged_missing_tracker_ = false;

        void acquire_nearest(const Pose3& hand_world_pose);
    };

    class ENTITY_API XrRayInteractorComponent : public CxxComponent {
    public:
        double max_distance = 5.0;
        double select_threshold = 0.55;

        XrRayInteractorComponent();

        static void register_type();
        void update(float dt) override;
        void on_removed() override;
        void on_destroy() override;
        void on_scene_inactive() override;

        bool pointing() const {
            return pointing_;
        }
        bool captured() const {
            return captured_surface_.valid();
        }
        double visible_ray_length() const {
            return visible_ray_length_;
        }

    private:
        struct SurfaceRef {
            tc_entity_handle entity = TC_ENTITY_HANDLE_INVALID;
            std::string source_id;

            bool valid() const {
                return tc_entity_handle_valid(entity) && !source_id.empty();
            }
            void clear() {
                entity = TC_ENTITY_HANDLE_INVALID;
                source_id.clear();
            }
        };

        SurfaceRef hovered_surface_;
        SurfaceRef captured_surface_;
        bool was_pressed_ = false;
        bool pointing_ = false;
        double visible_ray_length_ = 0.0;
        bool logged_missing_tracker_ = false;
        bool logged_missing_line_renderer_ = false;
        void reset_interaction(bool cancel_capture, bool clear_runtime_visual);
    };

    ENTITY_API const char* xr_tracked_pose_kind_to_string(XrTrackedPoseKind kind);
    ENTITY_API XrTrackedPoseKind xr_tracked_pose_kind_from_string(const std::string& value);

} // namespace termin
