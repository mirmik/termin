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

    bool tracking_active() const { return tracking_active_; }
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

    bool grabbed() const { return owner_ != nullptr; }

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

    bool holding_object() const { return grabbed_entity_.valid(); }
    void release_grabbed(XrGrabInteractableComponent* expected = nullptr);

private:
    Entity grabbed_entity_;
    Pose3 hand_from_object_{};
    bool was_pressed_ = false;
    bool logged_missing_tracker_ = false;

    void acquire_nearest(const Pose3& hand_world_pose);
};

ENTITY_API const char* xr_tracked_pose_kind_to_string(XrTrackedPoseKind kind);
ENTITY_API XrTrackedPoseKind xr_tracked_pose_kind_from_string(const std::string& value);

} // namespace termin
