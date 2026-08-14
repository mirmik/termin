#include "guard_main.h"

#include "termin/editor/editor_interaction_system.hpp"
#include "termin/editor/component_editor_visual.hpp"
#include "termin/editor/gizmo_visual_item3d.hpp"
#include <termin_visual_scene/native_visual_item3d.hpp>

#if defined(TERMIN_HAS_RECAST)
#include <termin/navmesh/off_mesh_link_component.hpp>
#endif

#include <cmath>
#include <memory>
#include <vector>

namespace {

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
