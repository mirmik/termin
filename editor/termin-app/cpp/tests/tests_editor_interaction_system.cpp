#include "guard_main.h"

#include "termin/editor/component_editor_visual.hpp"
#include "termin/editor/editor_interaction_system.hpp"
#include "termin/editor/gizmo_visual_item3d.hpp"
#include <termin/camera/camera_component.hpp>
#include <termin_visual_scene/native_visual_item3d.hpp>
#include <tgfx/resources/tc_mesh.h>

#include <render/tc_render_target.h>

#if defined(TERMIN_HAS_RECAST)
#include <termin/navmesh/off_mesh_link_component.hpp>
#endif

#include <algorithm>
#include <cmath>
#include <limits>
#include <memory>
#include <vector>

namespace termin {

    struct EditorInteractionSystemTestAccess {
        static bool populate_surface_projection(SurfacePickResult& result,
                                                const Mat44& projection,
                                                const Mat44& view,
                                                const Vec2& pixel_center,
                                                double depth,
                                                const Rect2& framebuffer_rect,
                                                ScreenRayError* error = nullptr) {
            return EditorInteractionSystem::_try_populate_surface_projection(
                result, projection, view, pixel_center, depth, framebuffer_rect, error);
        }

        static bool build_surface_mesh_ray(const Ray3& world_ray,
                                           const Affine3d& entity_affine,
                                           const Mat44f& mesh_offset,
                                           tc_mesh_ray& ray) {
            return EditorInteractionSystem::_try_build_surface_mesh_ray(world_ray, entity_affine, mesh_offset, ray);
        }

        static bool apply_surface_mesh_hit(SurfacePickResult& result,
                                           const tc_mesh_hit& hit,
                                           const Mat44f& mesh_offset,
                                           const Affine3d& entity_affine) {
            return EditorInteractionSystem::_try_apply_surface_mesh_hit(result, hit, mesh_offset, entity_affine);
        }
    };

} // namespace termin

namespace {

    constexpr double kPi = 3.14159265358979323846;

    struct RecordingGizmoState {
        std::vector<int> hover_enter;
        std::vector<int> hover_exit;
        std::vector<int> clicks;
        std::vector<int> releases;
        std::vector<int> cancels;
        int drags = 0;
    };

    class RecordingGizmo final : public termin::Gizmo {
    public:
        explicit RecordingGizmo(std::shared_ptr<RecordingGizmoState> state)
            : state(std::move(state)) {}

        std::vector<termin::GizmoCollider> get_colliders() override {
            return {
                {1,
                 termin::SphereGeometry{{5.0f, 0.0f, 0.0f}, 0.5f},
                 termin::AxisConstraint{{0.0f, 0.0f, 0.0f}, {1.0f, 0.0f, 0.0f}}},
                {2, termin::SphereGeometry{{10.0f, 0.0f, 0.0f}, 0.5f}, termin::NoDrag{}},
            };
        }

        void on_hover_enter(int collider_id) override {
            state->hover_enter.push_back(collider_id);
        }
        void on_hover_exit(int collider_id) override {
            state->hover_exit.push_back(collider_id);
        }
        void on_click(int collider_id, const termin::Vec3f*) override {
            state->clicks.push_back(collider_id);
        }
        void on_drag(int, const termin::Vec3f&, const termin::Vec3f&) override {
            ++state->drags;
        }
        void on_release(int collider_id) override {
            state->releases.push_back(collider_id);
        }
        void on_cancel(int collider_id) override {
            state->cancels.push_back(collider_id);
        }

        std::shared_ptr<RecordingGizmoState> state;
    };

    class TestOverlayItem final : public termin::visual::NativeVisualItem3D,
                                  public termin::EditorOverlayDrawable3D {
    public:
        TestOverlayItem(double distance, std::uint64_t part)
            : NativeVisualItem3D("termin.editor.test.OverlayItem3D"),
              distance(distance),
              part(part) {}

        std::optional<termin::visual::VisualBounds3D> local_bounds() const override {
            return termin::visual::VisualBounds3D{{-1.0, -1.0, -1.0}, {1.0, 1.0, 1.0}};
        }

        std::optional<termin::visual::HitCandidate3D>
        hit_test(const termin::visual::HitTestContext3D&) const override {
            if (!hittable)
                return std::nullopt;
            return termin::visual::HitCandidate3D{distance, part};
        }

        bool paint(termin::visual::GraphicItemPaintContext3D& context) const override {
            const termin::EditorOverlayDrawPacket3D packet{this};
            return context.submit(termin::EditorOverlayDrawProtocol3D, &packet, sizeof(packet));
        }

        bool draw(const termin::EditorOverlayDrawContext3D& context) const override {
            ++draw_calls;
            last_draw_item = context.item;
            return draw_result;
        }

        double distance = 1.0;
        std::uint64_t part = 0;
        bool hittable = true;
        bool draw_result = true;
        mutable int draw_calls = 0;
        mutable termin::visual::VisualItem3DHandle last_draw_item = tc_visual_item3d_handle_invalid();
    };

    termin::Ray3 test_ray() {
        return {{0.0, 0.0, 0.0}, {1.0, 0.0, 0.0}};
    }

    termin::Ray3 test_ray_from(double x, double y = 0.0) {
        return {{x, y, 0.0}, {1.0, 0.0, 0.0}};
    }

} // namespace

TEST_CASE("Editor surface projection preserves pixel-center and view-depth semantics") {
    const termin::Rect2 framebuffer{0.0, 0.0, 800.0, 600.0};
    const termin::Vec2 pixel_center{523.5, 187.5};
    const termin::Mat44 view = termin::Mat44::look_at({3.0, -7.0, 4.0}, {-1.0, 2.0, 0.5});
    const termin::Mat44 projections[] = {
        termin::Mat44::perspective(55.0 * kPi / 180.0, framebuffer.width / framebuffer.height, 0.1, 200.0),
        termin::Mat44::orthographic(-6.0, 6.0, -4.5, 4.5, 0.1, 200.0),
    };

    for (const termin::Mat44& projection : projections) {
        termin::SurfacePickResult result;
        termin::ScreenRayError error = termin::ScreenRayError::InvalidProjection;
        REQUIRE(termin::EditorInteractionSystemTestAccess::populate_surface_projection(
            result, projection, view, pixel_center, 0.625, framebuffer, &error));

        CHECK(error == termin::ScreenRayError::None);
        CHECK(result.has_world_point);
        CHECK(result.world_point.is_finite());
        CHECK(std::isfinite(result.view_depth));
        CHECK(result.view_depth > 0.0);
        CHECK(std::abs(result.reproject_screen_error) <= 1.0e-8);
        CHECK(std::abs(result.reproject_depth_error) <= 1.0e-10);
    }
}

TEST_CASE("Editor surface projection rejects invalid camera math without publishing a world point") {
    const termin::Rect2 framebuffer{0.0, 0.0, 800.0, 600.0};
    const termin::Vec2 pixel_center{400.5, 300.5};
    const termin::Vec3 sentinel{11.0, 12.0, 13.0};
    termin::SurfacePickResult result;
    result.world_point = sentinel;
    termin::ScreenRayError error = termin::ScreenRayError::None;

    CHECK_FALSE(termin::EditorInteractionSystemTestAccess::populate_surface_projection(
        result, termin::Mat44::zero(), termin::Mat44::identity(), pixel_center, 0.5, framebuffer, &error));
    CHECK(error == termin::ScreenRayError::SingularProjectionView);
    CHECK_FALSE(result.has_world_point);
    CHECK(result.world_point == sentinel);

    termin::Mat44 non_finite_projection = termin::Mat44::identity();
    non_finite_projection(0, 0) = std::numeric_limits<double>::quiet_NaN();
    CHECK_FALSE(termin::EditorInteractionSystemTestAccess::populate_surface_projection(
        result, non_finite_projection, termin::Mat44::identity(), pixel_center, 0.5, framebuffer, &error));
    CHECK(error == termin::ScreenRayError::NonFiniteProjectionView);
    CHECK_FALSE(result.has_world_point);
    CHECK(result.world_point == sentinel);

    CHECK_FALSE(
        termin::EditorInteractionSystemTestAccess::populate_surface_projection(result,
                                                                               termin::Mat44::identity(),
                                                                               termin::Mat44::identity(),
                                                                               pixel_center,
                                                                               std::numeric_limits<double>::infinity(),
                                                                               framebuffer,
                                                                               &error));
    CHECK(error == termin::ScreenRayError::InvalidClipDepth);
    CHECK_FALSE(result.has_world_point);
    CHECK(result.world_point == sentinel);
}

TEST_CASE("Editor mesh refinement uses the canonical orthographic screen ray") {
    const termin::Rect2 framebuffer{0.0, 0.0, 800.0, 600.0};
    const termin::Vec2 pixel_center{713.5, 129.5};
    const termin::Mat44 projection = termin::Mat44::orthographic(-8.0, 8.0, -6.0, 6.0, 0.1, 500.0);
    const termin::Mat44 view = termin::Mat44::look_at({12.0, -7.0, 3.0}, {12.0, 8.0, 3.0});

    termin::Ray3 world_ray;
    REQUIRE(termin::try_unproject_screen_ray(projection, view, pixel_center, framebuffer, world_ray));

    tc_mesh_ray mesh_ray{};
    REQUIRE(termin::EditorInteractionSystemTestAccess::build_surface_mesh_ray(
        world_ray, termin::Affine3d::identity(), termin::Mat44f::identity(), mesh_ray));

    CHECK_EQ(mesh_ray.origin.x, guard::Approx(static_cast<float>(world_ray.origin.x)).epsilon(1.0e-5));
    CHECK_EQ(mesh_ray.origin.y, guard::Approx(static_cast<float>(world_ray.origin.y)).epsilon(1.0e-5));
    CHECK_EQ(mesh_ray.origin.z, guard::Approx(static_cast<float>(world_ray.origin.z)).epsilon(1.0e-5));
    CHECK_EQ(mesh_ray.direction.x, guard::Approx(static_cast<float>(world_ray.direction.x)).epsilon(1.0e-6));
    CHECK_EQ(mesh_ray.direction.y, guard::Approx(static_cast<float>(world_ray.direction.y)).epsilon(1.0e-6));
    CHECK_EQ(mesh_ray.direction.z, guard::Approx(static_cast<float>(world_ray.direction.z)).epsilon(1.0e-6));

    termin::Ray3 center_ray;
    REQUIRE(termin::try_unproject_screen_ray(projection, view, {400.5, 300.5}, framebuffer, center_ray));
    CHECK((world_ray.origin - center_ray.origin).norm() > 1.0);
    CHECK_EQ(world_ray.direction.x, guard::Approx(center_ray.direction.x).epsilon(1.0e-12));
    CHECK_EQ(world_ray.direction.y, guard::Approx(center_ray.direction.y).epsilon(1.0e-12));
    CHECK_EQ(world_ray.direction.z, guard::Approx(center_ray.direction.z).epsilon(1.0e-12));
}

TEST_CASE("Editor mesh refinement preserves centered large-world entity coordinates") {
    const termin::Affine3d entity_affine =
        termin::Affine3d::trs({1.0e12 + 1234.0, -1.0e12 + 5678.0, 1.0e12 - 910.0},
                              termin::Quat::from_axis_angle(termin::Vec3::unit_z(), 0.83),
                              {1.75, 0.65, 2.25});
    const termin::Vec3 expected_origin{3.25, -2.5, 7.75};
    const termin::Vec3 expected_direction{0.2, 0.9, -0.35};
    const termin::Ray3 world_ray{
        entity_affine.transform_point(expected_origin),
        entity_affine.transform_vector(expected_direction),
    };

    tc_mesh_ray mesh_ray{};
    REQUIRE(termin::EditorInteractionSystemTestAccess::build_surface_mesh_ray(
        world_ray, entity_affine, termin::Mat44f::identity(), mesh_ray));

    const termin::Vec3f expected_normalized_direction = expected_direction.to_float().normalized();
    CHECK_EQ(mesh_ray.origin.x, guard::Approx(static_cast<float>(expected_origin.x)).epsilon(2.0e-4));
    CHECK_EQ(mesh_ray.origin.y, guard::Approx(static_cast<float>(expected_origin.y)).epsilon(2.0e-4));
    CHECK_EQ(mesh_ray.origin.z, guard::Approx(static_cast<float>(expected_origin.z)).epsilon(2.0e-4));
    CHECK_EQ(mesh_ray.direction.x, guard::Approx(expected_normalized_direction.x).epsilon(1.0e-5));
    CHECK_EQ(mesh_ray.direction.y, guard::Approx(expected_normalized_direction.y).epsilon(1.0e-5));
    CHECK_EQ(mesh_ray.direction.z, guard::Approx(expected_normalized_direction.z).epsilon(1.0e-5));
}

TEST_CASE("Editor mesh refinement transforms oblique normals by both affine inverse transposes") {
    const termin::Mat44f mesh_offset =
        termin::Mat44f::translation({3.0, -2.0, 1.0}) *
        termin::Mat44f::rotation(termin::Quat::from_axis_angle(termin::Vec3{0.25, 1.0, -0.4}.normalized(), 0.63)) *
        termin::Mat44f::scale({2.5, 0.6, 1.75});
    const termin::Affine3d entity_affine =
        termin::Affine3d::trs({1.0e6, -2.0e6, 3.0e6},
                              termin::Quat::from_axis_angle(termin::Vec3{-0.5, 0.2, 1.0}.normalized(), -0.47),
                              {0.8, 1.9, 1.25});

    const termin::Vec3 local_tangent0{1.0, 2.0, -0.5};
    const termin::Vec3 local_tangent1{-0.3, 0.4, 1.2};
    const termin::Vec3 local_normal = local_tangent0.cross(local_tangent1).normalized();
    tc_mesh_hit hit{};
    hit.position = {0.25f, -0.75f, 1.5f};
    hit.normal = local_normal.to_float();
    hit.triangle_index = 17;
    hit.indices[0] = 3;
    hit.indices[1] = 7;
    hit.indices[2] = 11;

    termin::SurfacePickResult result;
    REQUIRE(termin::EditorInteractionSystemTestAccess::apply_surface_mesh_hit(result, hit, mesh_offset, entity_affine));
    REQUIRE(result.has_mesh_hit);

    const termin::Vec3 world_tangent0 =
        entity_affine.transform_vector(mesh_offset.transform_direction(local_tangent0.to_float()).to_double());
    const termin::Vec3 world_tangent1 =
        entity_affine.transform_vector(mesh_offset.transform_direction(local_tangent1.to_float()).to_double());
    CHECK(std::abs(result.mesh_normal.dot(world_tangent0.normalized())) < 2.0e-6);
    CHECK(std::abs(result.mesh_normal.dot(world_tangent1.normalized())) < 2.0e-6);
    CHECK_EQ(result.mesh_normal.norm(), guard::Approx(1.0).epsilon(1.0e-12));
    CHECK_EQ(result.mesh_triangle_index, 17);
    CHECK(result.mesh_indices == termin::Vec3i(3, 7, 11));
}

TEST_CASE("Editor mesh refinement rejects singular offsets and degenerate ray or normal") {
    const termin::Affine3d identity = termin::Affine3d::identity();
    tc_mesh_ray mesh_ray{};
    CHECK_FALSE(termin::EditorInteractionSystemTestAccess::build_surface_mesh_ray(
        {{0.0, 0.0, 0.0}, {0.0, 1.0, 0.0}}, identity, termin::Mat44f::scale({0.0, 1.0, 1.0}), mesh_ray));
    termin::Ray3 degenerate_ray;
    degenerate_ray.origin = termin::Vec3::zero();
    degenerate_ray.direction = termin::Vec3::zero();
    CHECK_FALSE(termin::EditorInteractionSystemTestAccess::build_surface_mesh_ray(
        degenerate_ray, identity, termin::Mat44f::identity(), mesh_ray));

    termin::SurfacePickResult result;
    result.has_world_point = true;
    result.world_point = {0.0, 5.0, 0.0};
    result.mesh_point = {11.0, 12.0, 13.0};
    result.mesh_normal = {14.0, 15.0, 16.0};
    result.mesh_triangle_index = 23;
    result.mesh_indices = {29, 31, 37};
    tc_mesh_hit hit{};
    hit.position = {1.0f, 2.0f, 3.0f};
    hit.normal = {0.0f, 0.0f, 1.0f};
    CHECK_FALSE(termin::EditorInteractionSystemTestAccess::apply_surface_mesh_hit(
        result, hit, termin::Mat44f::scale({1.0, 0.0, 1.0}), identity));
    CHECK(result.has_world_point);
    CHECK_FALSE(result.has_mesh_hit);
    CHECK(result.mesh_point == termin::Vec3(11.0, 12.0, 13.0));
    CHECK(result.mesh_normal == termin::Vec3(14.0, 15.0, 16.0));
    CHECK_EQ(result.mesh_triangle_index, 23);
    CHECK(result.mesh_indices == termin::Vec3i(29, 31, 37));

    hit.normal = {0.0f, 0.0f, 0.0f};
    CHECK_FALSE(termin::EditorInteractionSystemTestAccess::apply_surface_mesh_hit(
        result, hit, termin::Mat44f::identity(), identity));
    CHECK(result.has_world_point);
    CHECK_FALSE(result.has_mesh_hit);
    CHECK(result.mesh_point == termin::Vec3(11.0, 12.0, 13.0));
    CHECK(result.mesh_normal == termin::Vec3(14.0, 15.0, 16.0));
}

TEST_CASE("EditorInteractionSystem ignores release without scene press") {
    termin::EditorInteractionSystem interaction;
    CHECK_EQ(interaction.overlay_scene().scene().size(), 2);
    int click_callbacks = 0;
    interaction.on_entity_click = [&](auto&&...) -> bool {
        click_callbacks += 1;
        return false;
    };

    interaction.on_mouse_button(
        0, TC_INPUT_RELEASE, 0, 1, 12.0f, 34.0f, TC_VIEWPORT_HANDLE_INVALID, TC_DISPLAY_HANDLE_INVALID);
    interaction.after_render();

    CHECK_EQ(click_callbacks, 0);
}

TEST_CASE("Editor overlay scene paints nearest target and preserves capture") {
    termin::EditorOverlayScene3D overlay;

    auto far = std::make_unique<TestOverlayItem>(8.0, 80);
    auto near = std::make_unique<TestOverlayItem>(2.0, 20);
    auto* near_ptr = near.get();
    const auto far_handle = overlay.scene().adopt(std::move(far));
    const auto near_handle = overlay.scene().adopt(std::move(near));
    REQUIRE(far_handle.has_value());
    REQUIRE(near_handle.has_value());

    std::vector<termin::visual::TargetPointerEventKind3D> events;
    overlay.interaction().set_target_pointer_handler(*near_handle, [&](const auto& event) {
        events.push_back(event.kind);
        CHECK_EQ(event.part, 20);
    });

    CHECK(overlay.route_pointer(termin::visual::PointerEventKind3D::Down, test_ray(), 1));
    near_ptr->hittable = false;
    CHECK(overlay.route_pointer(termin::visual::PointerEventKind3D::Move, test_ray(), 1));
    CHECK(overlay.route_pointer(termin::visual::PointerEventKind3D::Up, test_ray(), 1));
    CHECK(events[1] == termin::visual::TargetPointerEventKind3D::Down);
    CHECK(events[events.size() - 2] == termin::visual::TargetPointerEventKind3D::Move);
    CHECK(events.back() == termin::visual::TargetPointerEventKind3D::Up);

    CHECK(overlay.paint(nullptr, nullptr, termin::Mat44f::identity(), termin::Mat44f::identity(), 640, 480));
    CHECK_EQ(near_ptr->draw_calls, 1);
    CHECK(tc_visual_item3d_handle_eq(near_ptr->last_draw_item, *near_handle));

    near_ptr->hittable = true;
    CHECK(overlay.route_pointer(termin::visual::PointerEventKind3D::Down, test_ray(), 1));
    overlay.clear();
    CHECK(events[events.size() - 2] == termin::visual::TargetPointerEventKind3D::Cancel);
    CHECK(events.back() == termin::visual::TargetPointerEventKind3D::Leave);
    CHECK_EQ(overlay.scene().size(), 0);
    CHECK_FALSE(overlay.route_pointer(termin::visual::PointerEventKind3D::Down, test_ray(), 1));
}

TEST_CASE("Editor overlay cancels and contains a pointer sequence when its screen ray disappears") {
    tc_scene_handle scene = tc_scene_new_named("editor-overlay-ray-loss-test");
    REQUIRE(tc_scene_alive(scene));
    tc_entity_pool_handle scene_pool = tc_entity_pool_registry_find(tc_scene_entity_pool(scene));
    REQUIRE(tc_entity_pool_handle_valid(scene_pool));

    termin::Entity camera_entity = termin::Entity::create(scene_pool, "editor-overlay-ray-loss-camera");
    auto* camera = new termin::CameraComponent();
    camera_entity.add_component(camera);

    tc_render_target_handle render_target = tc_render_target_new("editor-overlay-ray-loss-target");
    REQUIRE(tc_render_target_handle_valid(render_target));
    tc_render_target_set_scene(render_target, scene);
    tc_render_target_set_camera(render_target, camera->tc_component_ptr());

    tc_viewport_handle viewport = tc_viewport_new("editor-overlay-ray-loss-viewport", scene);
    REQUIRE(tc_viewport_handle_valid(viewport));
    tc_viewport_set_render_target(viewport, render_target);
    tc_viewport_set_pixel_rect(viewport, 0, 0, 640, 480);

    termin::EditorInteractionSystem interaction;
    auto item = std::make_unique<TestOverlayItem>(0.25, 42);
    const auto item_handle = interaction.overlay_scene().scene().adopt(std::move(item));
    REQUIRE(item_handle.has_value());

    std::vector<termin::visual::TargetPointerEventKind3D> overlay_events;
    interaction.overlay_scene().interaction().set_target_pointer_handler(
        *item_handle, [&](const auto& event) { overlay_events.push_back(event.kind); });
    std::vector<std::string> viewport_events;
    interaction.on_viewport_pointer_event = [&](const termin::ViewportPointerEvent& event) {
        viewport_events.push_back(event.phase);
        return true;
    };

    // Hover does not own the physical sequence. Ray loss still emits Leave
    // and clears the stale overlay state, but the underlying viewport may
    // handle that Move.
    interaction.on_mouse_move(310.0f, 240.0f, 0.0f, 0.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    REQUIRE(interaction.overlay_scene().interaction().hovered_hit(1).has_value());
    CHECK(viewport_events.empty());
    tc_render_target_set_camera(render_target, nullptr);
    interaction.on_mouse_move(315.0f, 240.0f, 5.0f, 0.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    CHECK_FALSE(interaction.overlay_scene().interaction().hovered_hit(1).has_value());
    REQUIRE_EQ(viewport_events.size(), 1);
    CHECK_EQ(viewport_events.front(), "move");
    REQUIRE(!overlay_events.empty());
    CHECK(overlay_events.back() == termin::visual::TargetPointerEventKind3D::Leave);
    viewport_events.clear();
    tc_render_target_set_camera(render_target, camera->tc_component_ptr());

    interaction.on_mouse_button(0, TC_INPUT_PRESS, 0, 1, 320.0f, 240.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    REQUIRE(interaction.overlay_scene().interaction().pressed_hit(1).has_value());
    REQUIRE(interaction.overlay_scene().interaction().captured_hit(1).has_value());
    CHECK(viewport_events.empty());

    // Losing the camera makes the optional ray fail. The active overlay drag
    // is cancelled immediately, while both this Move and the matching Up stay
    // contained inside the overlay-owned pointer sequence.
    tc_render_target_set_camera(render_target, nullptr);
    interaction.on_mouse_move(330.0f, 240.0f, 10.0f, 0.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    CHECK_FALSE(interaction.overlay_scene().interaction().pressed_hit(1).has_value());
    CHECK_FALSE(interaction.overlay_scene().interaction().captured_hit(1).has_value());
    CHECK(viewport_events.empty());

    interaction.on_mouse_button(0, TC_INPUT_RELEASE, 0, 1, 330.0f, 240.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    CHECK(viewport_events.empty());

    int cancel_count = 0;
    for (const auto event : overlay_events) {
        if (event == termin::visual::TargetPointerEventKind3D::Cancel)
            ++cancel_count;
    }
    CHECK_EQ(cancel_count, 1);

    // Rebuilding editor visuals during a captured sequence also terminates
    // overlay ownership and contains the physical tail until Up.
    tc_render_target_set_camera(render_target, camera->tc_component_ptr());
    interaction.on_mouse_button(0, TC_INPUT_PRESS, 0, 1, 320.0f, 240.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    REQUIRE(interaction.overlay_scene().interaction().captured_hit(1).has_value());
    interaction.set_gizmo_target({});
    CHECK_FALSE(interaction.overlay_scene().interaction().captured_hit(1).has_value());
    interaction.on_mouse_move(325.0f, 240.0f, 5.0f, 0.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    interaction.on_mouse_button(0, TC_INPUT_RELEASE, 0, 1, 325.0f, 240.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    CHECK(viewport_events.empty());

    // A new valid overlay sequence is also cancelled and consumed when its Up
    // arrives with an invalid viewport. There is no suppression left after
    // that Up: an unrelated invalid Move is allowed to reach the viewport.
    tc_render_target_set_camera(render_target, camera->tc_component_ptr());
    interaction.on_mouse_button(0, TC_INPUT_PRESS, 0, 1, 320.0f, 240.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    REQUIRE(interaction.overlay_scene().interaction().captured_hit(1).has_value());
    interaction.on_mouse_button(
        0, TC_INPUT_RELEASE, 0, 1, 320.0f, 240.0f, TC_VIEWPORT_HANDLE_INVALID, TC_DISPLAY_HANDLE_INVALID);
    CHECK_FALSE(interaction.overlay_scene().interaction().pressed_hit(1).has_value());
    CHECK_FALSE(interaction.overlay_scene().interaction().captured_hit(1).has_value());
    CHECK(viewport_events.empty());

    interaction.on_mouse_move(340.0f, 240.0f, 10.0f, 0.0f, TC_VIEWPORT_HANDLE_INVALID, TC_DISPLAY_HANDLE_INVALID);
    REQUIRE_EQ(viewport_events.size(), 1);
    CHECK_EQ(viewport_events.front(), "move");

    tc_viewport_free(viewport);
    tc_render_target_free(render_target);
    tc_entity_free(camera_entity.handle());
    tc_scene_free(scene);
}

TEST_CASE("Editor interaction focus loss cancels an active overlay capture") {
    termin::EditorInteractionSystem interaction;
    auto item = std::make_unique<TestOverlayItem>(0.25, 17);
    const auto item_handle = interaction.overlay_scene().scene().adopt(std::move(item));
    REQUIRE(item_handle.has_value());
    std::vector<termin::visual::TargetPointerEventKind3D> events;
    interaction.overlay_scene().interaction().set_target_pointer_handler(
        *item_handle, [&](const auto& event) { events.push_back(event.kind); });

    REQUIRE(interaction.overlay_scene().route_pointer(termin::visual::PointerEventKind3D::Down, test_ray(), 1));
    REQUIRE(interaction.overlay_scene().interaction().captured_hit(1).has_value());

    interaction.on_focus_lost();

    CHECK_FALSE(interaction.overlay_scene().interaction().pressed_hit(1).has_value());
    CHECK_FALSE(interaction.overlay_scene().interaction().captured_hit(1).has_value());
    REQUIRE(!events.empty());
    CHECK(events[events.size() - 2] == termin::visual::TargetPointerEventKind3D::Cancel);
    CHECK(events.back() == termin::visual::TargetPointerEventKind3D::Leave);

    std::vector<std::string> viewport_events;
    interaction.on_viewport_pointer_event = [&](const termin::ViewportPointerEvent& event) {
        viewport_events.push_back(event.phase);
        return true;
    };
    interaction.on_mouse_button(
        0, TC_INPUT_RELEASE, 0, 1, 0.0f, 0.0f, TC_VIEWPORT_HANDLE_INVALID, TC_DISPLAY_HANDLE_INVALID);
    CHECK(viewport_events.empty());
    CHECK(std::count(events.begin(), events.end(), termin::visual::TargetPointerEventKind3D::Up) == 0);

    interaction.on_mouse_move(1.0f, 0.0f, 1.0f, 0.0f, TC_VIEWPORT_HANDLE_INVALID, TC_DISPLAY_HANDLE_INVALID);
    REQUIRE_EQ(viewport_events.size(), 1);
    CHECK_EQ(viewport_events.front(), "move");
}

TEST_CASE("Editor gizmo target change invalidates an in-flight overlay Enter") {
    tc_scene_handle scene = tc_scene_new_named("editor-overlay-enter-reentrant-test");
    REQUIRE(tc_scene_alive(scene));
    tc_entity_pool_handle scene_pool = tc_entity_pool_registry_find(tc_scene_entity_pool(scene));
    REQUIRE(tc_entity_pool_handle_valid(scene_pool));
    termin::Entity camera_entity = termin::Entity::create(scene_pool, "editor-overlay-enter-camera");
    auto* camera = new termin::CameraComponent();
    camera_entity.add_component(camera);
    termin::Entity target = termin::Entity::create(scene_pool, "overlay-enter-reentrant-target");

    tc_render_target_handle render_target = tc_render_target_new("editor-overlay-enter-target");
    REQUIRE(tc_render_target_handle_valid(render_target));
    tc_render_target_set_scene(render_target, scene);
    tc_render_target_set_camera(render_target, camera->tc_component_ptr());
    tc_viewport_handle viewport = tc_viewport_new("editor-overlay-enter-viewport", scene);
    REQUIRE(tc_viewport_handle_valid(viewport));
    tc_viewport_set_render_target(viewport, render_target);
    tc_viewport_set_pixel_rect(viewport, 0, 0, 640, 480);

    termin::EditorInteractionSystem interaction;
    auto item = std::make_unique<TestOverlayItem>(0.25, 19);
    const auto item_handle = interaction.overlay_scene().scene().adopt(std::move(item));
    REQUIRE(item_handle.has_value());

    int enter_count = 0;
    int up_count = 0;
    interaction.overlay_scene().interaction().set_target_pointer_handler(*item_handle, [&](const auto& event) {
        if (event.kind == termin::visual::TargetPointerEventKind3D::Enter) {
            ++enter_count;
            interaction.set_gizmo_target(target);
        } else if (event.kind == termin::visual::TargetPointerEventKind3D::Up) {
            ++up_count;
        }
    });
    std::vector<std::string> viewport_events;
    interaction.on_viewport_pointer_event = [&](const termin::ViewportPointerEvent& event) {
        viewport_events.push_back(event.phase);
        return true;
    };

    interaction.on_mouse_button(0, TC_INPUT_PRESS, 0, 1, 320.0f, 240.0f, viewport, TC_DISPLAY_HANDLE_INVALID);

    CHECK_EQ(enter_count, 1);
    CHECK_FALSE(interaction.overlay_scene().interaction().hovered_hit(1).has_value());
    CHECK_FALSE(interaction.overlay_scene().interaction().pressed_hit(1).has_value());
    CHECK_FALSE(interaction.overlay_scene().interaction().captured_hit(1).has_value());
    CHECK(viewport_events.empty());

    interaction.on_mouse_button(0, TC_INPUT_RELEASE, 0, 1, 320.0f, 240.0f, viewport, TC_DISPLAY_HANDLE_INVALID);
    CHECK_EQ(up_count, 0);
    CHECK(viewport_events.empty());

    interaction.set_gizmo_target({});
    tc_viewport_free(viewport);
    tc_render_target_free(render_target);
    tc_entity_free(target.handle());
    tc_entity_free(camera_entity.handle());
    tc_scene_free(scene);
}

TEST_CASE("Editor gizmo target cancellation is reentrant and the nested transition wins") {
    termin::EditorInteractionSystem interaction;
    auto item = std::make_unique<TestOverlayItem>(0.25, 23);
    const auto item_handle = interaction.overlay_scene().scene().adopt(std::move(item));
    REQUIRE(item_handle.has_value());
    termin::Entity outer_target =
        termin::Entity::create(termin::Entity::standalone_pool_handle(), "overlay-outer-target");
    termin::Entity nested_target =
        termin::Entity::create(termin::Entity::standalone_pool_handle(), "overlay-nested-target");

    int cancel_count = 0;
    interaction.overlay_scene().interaction().set_target_pointer_handler(*item_handle, [&](const auto& event) {
        if (event.kind == termin::visual::TargetPointerEventKind3D::Cancel) {
            ++cancel_count;
            interaction.set_gizmo_target(nested_target);
        }
    });
    REQUIRE(interaction.overlay_scene().route_pointer(termin::visual::PointerEventKind3D::Down, test_ray(), 1));
    REQUIRE(interaction.overlay_scene().interaction().captured_hit(1).has_value());

    interaction.set_gizmo_target(outer_target);

    CHECK_EQ(cancel_count, 1);
    CHECK(interaction.transform_gizmo()->target() == nested_target);
    CHECK_FALSE(interaction.overlay_scene().interaction().pressed_hit(1).has_value());
    CHECK_FALSE(interaction.overlay_scene().interaction().captured_hit(1).has_value());

    interaction.set_gizmo_target({});
    tc_entity_free(outer_target.handle());
    tc_entity_free(nested_target.handle());
}

TEST_CASE("TransformGizmo drag is captured and cancelled by the editor overlay") {
    termin::EditorInteractionSystem interaction;
    termin::Entity target =
        termin::Entity::create(termin::Entity::standalone_pool_handle(), "transform-overlay-target");
    interaction.set_gizmo_target(target);

    const termin::Ray3 press_ray{{0.5, 0.0, -0.2}, {0.0, 0.0, 1.0}};
    REQUIRE(interaction.overlay_scene().route_pointer(
        termin::visual::PointerEventKind3D::Down, press_ray, 1));
    REQUIRE(interaction.overlay_scene().interaction().captured_hit(1).has_value());
    CHECK_EQ(interaction.overlay_scene().interaction().captured_hit(1)->part,
             static_cast<std::uint64_t>(termin::TransformElement::TRANSLATE_X));

    const termin::Ray3 drag_ray{{0.8, 0.0, -0.2}, {0.0, 0.0, 1.0}};
    REQUIRE(interaction.overlay_scene().route_pointer(
        termin::visual::PointerEventKind3D::Move, drag_ray, 1));
    CHECK(target.transform().global_position().x > 0.2);

    CHECK_FALSE(interaction.overlay_scene().interaction().cancel_all(interaction.overlay_scene().scene()));
    CHECK(std::abs(target.transform().global_position().x) < 1.0e-9);
    CHECK_FALSE(interaction.overlay_scene().interaction().captured_hit(1).has_value());

    tc_entity_free(target.handle());
}

TEST_CASE("Gizmo visual item routes stable collider parts through retained interaction") {
    termin::EditorOverlayScene3D overlay;
    auto state = std::make_shared<RecordingGizmoState>();
    auto item = std::make_unique<termin::GizmoVisualItem3D>(std::make_unique<RecordingGizmo>(state));
    auto* adapter = item.get();
    const auto handle = overlay.scene().adopt(std::move(item));
    REQUIRE(handle.has_value());
    adapter->bind_controller(overlay.interaction());

    CHECK(overlay.route_pointer(termin::visual::PointerEventKind3D::Move, test_ray()));
    CHECK_EQ(state->hover_enter.back(), 1);
    CHECK(overlay.route_pointer(termin::visual::PointerEventKind3D::Down, test_ray(), 1));
    CHECK_EQ(state->clicks.back(), 1);

    // Capture retains part 1 even while the current ray misses every collider.
    CHECK(overlay.route_pointer(
        termin::visual::PointerEventKind3D::Move, test_ray_from(0.0, 5.0), 1));
    CHECK_EQ(state->drags, 1);
    CHECK(overlay.route_pointer(
        termin::visual::PointerEventKind3D::Up, test_ray_from(0.0, 5.0), 1));
    CHECK_EQ(state->releases.back(), 1);

    CHECK(overlay.route_pointer(termin::visual::PointerEventKind3D::Move, test_ray_from(7.0)));
    CHECK_EQ(state->hover_enter.back(), 2);
    CHECK(overlay.route_pointer(termin::visual::PointerEventKind3D::Down, test_ray_from(7.0), 1));
    CHECK_EQ(state->clicks.back(), 2);
    overlay.clear();
    CHECK_EQ(state->cancels.back(), 2);
    CHECK_EQ(state->hover_exit.back(), 2);
}

#if defined(TERMIN_HAS_RECAST)
TEST_CASE("OffMeshLink provider contributes two safe retained endpoint parts") {
    termin::Entity entity = termin::Entity::create(termin::Entity::standalone_pool_handle(), "off-mesh-link");
    auto* link = new termin::OffMeshLinkComponent();
    entity.add_component(link);

    termin::TransformGizmo transform_gizmo;
    termin::ComponentEditorVisualContext context{&transform_gizmo};
    std::vector<termin::ComponentEditorVisualContribution> contributions;
    termin::ComponentEditorVisualRegistry::instance().collect_overlay_items(
        entity, link->c_component(), context, contributions);
    REQUIRE_EQ(contributions.size(), 1);

    termin::EditorOverlayScene3D overlay;
    auto contribution = std::move(contributions.front());
    const auto handle = overlay.scene().adopt(std::move(contribution.item));
    REQUIRE(handle.has_value());
    REQUIRE(static_cast<bool>(contribution.bind_controller));
    contribution.bind_controller(overlay.interaction(), *handle);

    CHECK(overlay.route_pointer(
        termin::visual::PointerEventKind3D::Down, {{-2.0, 0.0, 0.0}, {1.0, 0.0, 0.0}}, 1));
    CHECK(transform_gizmo.has_target());
    CHECK(overlay.interaction().captured_hit(1)->part == 1);
    CHECK(overlay.route_pointer(
        termin::visual::PointerEventKind3D::Up, {{-2.0, 0.0, 0.0}, {1.0, 0.0, 0.0}}, 1));

    CHECK(overlay.route_pointer(
        termin::visual::PointerEventKind3D::Down, {{-2.0, 1.0, -1.0}, {1.0, 0.0, 0.0}}, 1));
    CHECK(transform_gizmo.has_target());
    CHECK(overlay.interaction().captured_hit(1)->part == 2);

    // Removing only the component leaves both the visual controller and the
    // transform target with a resolvable invalid state, never a raw pointer.
    tc_component* component = link->c_component();
    entity.remove_component_ptr(component);
    CHECK_FALSE(transform_gizmo.has_target());
    CHECK(overlay.route_pointer(
        termin::visual::PointerEventKind3D::Move, {{-2.0, 1.0, -1.0}, {1.0, 0.0, 0.0}}, 1));
    overlay.clear();
    tc_entity_free(entity.handle());
}
#endif
