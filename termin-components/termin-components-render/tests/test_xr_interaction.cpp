#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cmath>
#include <utility>

#include <termin/input/xr_input.hpp>
#include <termin/tc_scene.hpp>
#include <termin/xr/xr_interaction_components.hpp>
#include <termin/xr/xr_origin_component.hpp>

namespace {

bool near(const termin::Vec3& a, const termin::Vec3& b, double epsilon = 1.0e-9) {
    return (a - b).norm() <= epsilon;
}

} // namespace

TEST_CASE("XR direct grab follows tracked grip pose, preserves offset and releases") {
    using namespace termin;

    xr::XrRigInputState input;
    input.id = "xr-interaction-test";
    xr::XrInput::register_state(input.id, &input);

    TcSceneRef scene = TcSceneRef::create("xr-interaction-test-scene");
    Entity origin_entity = scene.create_entity("XrOrigin");
    origin_entity.transform().set_local_position({10.0, 2.0, 1.0});
    origin_entity.add_component(new XrOriginComponent());

    Entity hand_entity = scene.create_entity("LeftHand");
    hand_entity.set_parent(origin_entity);
    auto* tracker = new XrTrackedPoseComponent();
    tracker->input_device_id = input.id;
    tracker->hand = xr::XrHand::Left;
    hand_entity.add_component(tracker);
    auto* interactor = new XrDirectGrabInteractorComponent();
    interactor->reach = 0.2;
    hand_entity.add_component(interactor);

    Entity cube = scene.create_entity("GrabCube");
    cube.transform().set_global_position({10.1, 2.0, 1.0});
    auto* interactable = new XrGrabInteractableComponent();
    interactable->grab_radius = 0.05;
    cube.add_component(interactable);

    input.left.grip_pose.active = true;
    input.left.grip_pose.pose = Pose3::identity();
    input.left.select.active = true;
    input.left.select.value = 0.8;
    tracker->update(0.0f);
    interactor->update(0.0f);
    REQUIRE(interactor->holding_object());
    REQUIRE(interactable->grabbed());
    CHECK(near(cube.transform().global_position(), Vec3{10.1, 2.0, 1.0}));

    input.left.grip_pose.pose.lin = {0.5, 0.25, 0.0};
    tracker->update(0.0f);
    interactor->update(0.0f);
    CHECK(near(cube.transform().global_position(), Vec3{10.6, 2.25, 1.0}));

    input.left.select.value = 0.0;
    interactor->update(0.0f);
    CHECK_FALSE(interactor->holding_object());
    CHECK_FALSE(interactable->grabbed());

    xr::XrInput::unregister_state(input.id);
    scene.destroy();
}

TEST_CASE("XR direct grab releases immediately when tracking becomes inactive") {
    using namespace termin;

    xr::XrRigInputState input;
    input.id = "xr-tracking-loss-test";
    xr::XrInput::register_state(input.id, &input);

    TcSceneRef scene = TcSceneRef::create("xr-tracking-loss-test-scene");
    Entity origin_entity = scene.create_entity("XrOrigin");
    origin_entity.add_component(new XrOriginComponent());
    Entity hand_entity = scene.create_entity("RightHand");
    hand_entity.set_parent(origin_entity);
    auto* tracker = new XrTrackedPoseComponent();
    tracker->input_device_id = input.id;
    tracker->hand = xr::XrHand::Right;
    hand_entity.add_component(tracker);
    auto* interactor = new XrDirectGrabInteractorComponent();
    hand_entity.add_component(interactor);
    Entity cube = scene.create_entity("GrabCube");
    auto* interactable = new XrGrabInteractableComponent();
    cube.add_component(interactable);

    input.right.grip_pose.active = true;
    input.right.select.active = true;
    input.right.select.value = 1.0;
    tracker->update(0.0f);
    interactor->update(0.0f);
    REQUIRE(interactor->holding_object());

    input.right.grip_pose.active = false;
    tracker->update(0.0f);
    interactor->update(0.0f);
    CHECK_FALSE(interactor->holding_object());
    CHECK_FALSE(interactable->grabbed());

    xr::XrInput::unregister_state(input.id);
    scene.destroy();
}

TEST_CASE("XR direct grab ownership prevents another hand from stealing") {
    using namespace termin;

    xr::XrRigInputState input;
    input.id = "xr-ownership-test";
    xr::XrInput::register_state(input.id, &input);

    TcSceneRef scene = TcSceneRef::create("xr-ownership-test-scene");
    Entity origin_entity = scene.create_entity("XrOrigin");
    origin_entity.add_component(new XrOriginComponent());

    auto make_hand = [&](const char* name, xr::XrHand hand) {
        Entity hand_entity = scene.create_entity(name);
        hand_entity.set_parent(origin_entity);
        auto* tracker = new XrTrackedPoseComponent();
        tracker->input_device_id = input.id;
        tracker->hand = hand;
        hand_entity.add_component(tracker);
        auto* interactor = new XrDirectGrabInteractorComponent();
        hand_entity.add_component(interactor);
        return std::pair{tracker, interactor};
    };
    auto [left_tracker, left_interactor] = make_hand("LeftHand", xr::XrHand::Left);
    auto [right_tracker, right_interactor] = make_hand("RightHand", xr::XrHand::Right);

    Entity cube = scene.create_entity("GrabCube");
    auto* interactable = new XrGrabInteractableComponent();
    cube.add_component(interactable);

    input.left.grip_pose.active = true;
    input.left.select.active = true;
    input.left.select.value = 1.0;
    input.right.grip_pose.active = true;
    input.right.select.active = true;
    input.right.select.value = 1.0;
    left_tracker->update(0.0f);
    right_tracker->update(0.0f);
    left_interactor->update(0.0f);
    right_interactor->update(0.0f);
    CHECK(left_interactor->holding_object());
    CHECK_FALSE(right_interactor->holding_object());

    input.left.select.value = 0.0;
    left_interactor->update(0.0f);
    CHECK_FALSE(interactable->grabbed());

    // A continuously held trigger is not a new acquisition gesture.
    right_interactor->update(0.0f);
    CHECK_FALSE(right_interactor->holding_object());
    input.right.select.value = 0.0;
    right_interactor->update(0.0f);
    input.right.select.value = 1.0;
    right_interactor->update(0.0f);
    CHECK(right_interactor->holding_object());

    xr::XrInput::unregister_state(input.id);
    scene.destroy();
}
