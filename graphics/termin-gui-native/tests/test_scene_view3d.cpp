#ifdef NDEBUG
#undef NDEBUG
#endif

#include <termin/gui_native/tc_document.hpp>
#include <termin/gui_native/widgets.hpp>

#include <cassert>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <memory>

#include <termin/geom/mat44.hpp>
#include <termin_visual_scene/items/primitive_item3d.hpp>

using namespace termin::gui_native;
using namespace termin::visual;

namespace {

    tc_mat44 identity_matrix() {
        return termin::Mat44::identity().to_tc_mat44();
    }

    SceneView3DCamera identity_camera(double x = 0.0) {
        return {identity_matrix(), identity_matrix(), {x, 0.0, 0.0}};
    }

    std::shared_ptr<PrimitiveGeometry3D> centered_triangle() {
        auto geometry = std::make_shared<PrimitiveGeometry3D>();
        geometry->vertices = {
            {{-0.5f, -0.5f, 0.5f}, {1.0f, 0.0f, 0.0f, 1.0f}},
            {{0.5f, -0.5f, 0.5f}, {0.0f, 1.0f, 0.0f, 1.0f}},
            {{0.0f, 0.5f, 0.5f}, {0.0f, 0.0f, 1.0f, 1.0f}},
        };
        geometry->triangles = {0, 1, 2};
        geometry->triangle_parts = {42};
        return geometry;
    }

    void test_independent_views_resize_and_ray_projection() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle left_scene_handle = tc_visual_scene3d_create();
        const tc_visual_scene3d_handle right_scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D left_scene{left_scene_handle};
        TcVisualScene3D right_scene{right_scene_handle};

        auto* left = new SceneView3D(left_scene);
        auto* right = new SceneView3D(right_scene);
        const tc_widget_handle left_handle = document.adopt(left);
        const tc_widget_handle right_handle = document.adopt(right);
        assert(document.add_root(*left));
        assert(document.add_root(*right));
        left->layout(document_handle, {0.0f, 0.0f, 200.0f, 100.0f});
        right->layout(document_handle, {220.0f, 0.0f, 80.0f, 160.0f});
        left->set_camera(identity_camera(1.0));
        right->set_camera(identity_camera(2.0));
        int provider_calls = 0;
        right->set_camera_provider([&](ViewportSurfaceSize size) -> std::optional<SceneView3DCamera> {
            ++provider_calls;
            assert((size == ViewportSurfaceSize{80, 160}));
            return identity_camera(3.0);
        });

        assert((left->framebuffer_size() == ViewportSurfaceSize{200, 100}));
        assert((right->framebuffer_size() == ViewportSurfaceSize{80, 160}));
        assert(left->camera().world_position.x == 1.0);
        // Providers are sampled by the render-preparation phase; the last
        // valid camera remains usable for input until then.
        assert(right->camera().world_position.x == 2.0);
        assert(provider_calls == 0);
        const auto left_ray = left->world_ray(100.0f, 50.0f);
        const auto right_ray = right->world_ray(260.0f, 80.0f);
        assert(left_ray && right_ray);
        assert(std::abs(left_ray->origin.x) < 1.0e-12);
        assert(std::abs(left_ray->origin.y) < 1.0e-12);
        assert(std::abs(left_ray->origin.z) < 1.0e-12);
        assert(std::abs(left_ray->direction.z - 1.0) < 1.0e-12);
        assert(std::abs(right_ray->direction.z - 1.0) < 1.0e-12);

        left->layout(document_handle, {0.0f, 0.0f, 301.0f, 181.0f});
        assert((left->framebuffer_size() == ViewportSurfaceSize{301, 181}));
        const auto resized_ray = left->world_ray(150.5f, 90.5f);
        assert(resized_ray);
        assert(std::abs(resized_ray->direction.x) < 1.0e-12);
        assert(std::abs(resized_ray->direction.y) < 1.0e-12);

        assert(tc_ui_document_destroy_widget(document_handle, left_handle));
        assert(tc_ui_document_destroy_widget(document_handle, right_handle));
        tc_visual_scene3d_destroy(left_scene_handle);
        tc_visual_scene3d_destroy(right_scene_handle);
        tc_ui_document_destroy(document_handle);
    }

    void test_invalid_projection_inputs_reject_world_ray() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        auto* view = new SceneView3D();
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));

        view->layout(document_handle, {0.0f, 0.0f, 0.0f, 100.0f});
        assert(!view->world_ray(0.0f, 50.0f));

        view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
        assert(!view->world_ray(std::numeric_limits<float>::quiet_NaN(), 50.0f));
        assert(!view->world_ray(50.0f, std::numeric_limits<float>::infinity()));

        SceneView3DCamera camera = identity_camera();
        camera.projection_matrix = {};
        view->set_camera(camera);
        assert(!view->world_ray(50.0f, 50.0f));

        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        tc_ui_document_destroy(document_handle);
    }

    void test_projection_failure_cancels_active_scene_pointer_without_fallback() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D scene{scene_handle};
        const auto item_handle = scene.adopt(std::make_unique<PrimitiveItem3D>(centered_triangle()));
        assert(item_handle);

        auto* view = new SceneView3D(scene);
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));
        view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
        view->set_camera(identity_camera());

        int downs = 0;
        int moves = 0;
        int ups = 0;
        int cancels = 0;
        int cancel_recaptures = 0;
        int actions = 0;
        int fallback_calls = 0;
        view->interaction().set_target_pointer_handler(*item_handle, [&](const TargetPointerEvent3D& event) {
            if (event.kind == TargetPointerEventKind3D::Down)
                ++downs;
            else if (event.kind == TargetPointerEventKind3D::Move)
                ++moves;
            else if (event.kind == TargetPointerEventKind3D::Up)
                ++ups;
            else if (event.kind == TargetPointerEventKind3D::Cancel) {
                ++cancels;
                assert(tc_ui_document_set_pointer_capture(document_handle, view_handle));
                ++cancel_recaptures;
            }
        });
        view->interaction().set_action_handler(*item_handle, [&](const ActionEvent3D&) { ++actions; });
        view->set_fallback_pointer_handler(
            [&](SceneView3D&, const tc_ui_pointer_event&, const std::optional<termin::Ray3>&) {
                ++fallback_calls;
                return true;
            });
        const auto dispatch = [&](tc_ui_pointer_event event) {
            return view->pointer_event(document_handle, &event);
        };
        const auto make_singular = [&] {
            SceneView3DCamera camera = identity_camera();
            camera.projection_matrix = {};
            view->set_camera(camera);
        };

        // A failed Move cancels the captured target from its last valid ray,
        // releases UI capture, and consumes the remaining Up without routing
        // it as a new event.
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_DOWN, 50.0f, 50.0f, 1, 1, 0}) == TC_UI_EVENT_HANDLED);
        assert(downs == 1);
        assert(tc_widget_handle_eq(document.pointer_capture(), view_handle));
        make_singular();
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_MOVE, 55.0f, 55.0f, 0, 0, 0}) == TC_UI_EVENT_HANDLED);
        assert(cancels == 1);
        assert(cancel_recaptures == 1);
        assert(moves == 0);
        assert(fallback_calls == 0);
        assert(tc_visual_item3d_handle_is_invalid(view->interaction().captured(1)));
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));

        view->set_camera(identity_camera());
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_UP, 55.0f, 55.0f, 1, 1, 0}) == TC_UI_EVENT_HANDLED);
        assert(ups == 0);
        assert(actions == 0);
        assert(fallback_calls == 0);

        // A failed terminal Up cancels immediately and does not leave a tail
        // state behind.
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_DOWN, 50.0f, 50.0f, 1, 1, 0}) == TC_UI_EVENT_HANDLED);
        assert(downs == 2);
        make_singular();
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_UP, 50.0f, 50.0f, 1, 1, 0}) == TC_UI_EVENT_HANDLED);
        assert(cancels == 2);
        assert(cancel_recaptures == 2);
        assert(ups == 0);
        assert(actions == 0);
        assert(fallback_calls == 0);
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));

        // Explicit cancellation must also reach the scene controller when the
        // current camera can no longer produce a fresh ray.
        view->set_camera(identity_camera());
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_DOWN, 50.0f, 50.0f, 1, 1, 0}) == TC_UI_EVENT_HANDLED);
        assert(downs == 3);
        make_singular();
        tc_ui_pointer_event cancel{};
        cancel.type = TC_UI_POINTER_CANCEL;
        cancel.x = 50.0f;
        cancel.y = 50.0f;
        cancel.cancel_reason = TC_UI_POINTER_CANCEL_EXPLICIT;
        assert(dispatch(cancel) == TC_UI_EVENT_HANDLED);
        assert(cancels == 3);
        assert(cancel_recaptures == 3);
        assert(fallback_calls == 0);
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));

        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        tc_visual_scene3d_destroy(scene_handle);
        tc_ui_document_destroy(document_handle);
    }

    void test_projection_failure_clears_hover_before_optional_fallback() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D scene{scene_handle};
        const auto item_handle = scene.adopt(std::make_unique<PrimitiveItem3D>(centered_triangle()));
        assert(item_handle);

        auto* view = new SceneView3D(scene);
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));
        view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
        view->set_camera(identity_camera());

        int enters = 0;
        int leaves = 0;
        int fallback_calls = 0;
        view->interaction().set_target_pointer_handler(*item_handle, [&](const TargetPointerEvent3D& event) {
            if (event.kind == TargetPointerEventKind3D::Enter)
                ++enters;
            else if (event.kind == TargetPointerEventKind3D::Leave)
                ++leaves;
        });
        view->set_fallback_pointer_handler(
            [&](SceneView3D&, const tc_ui_pointer_event&, const std::optional<termin::Ray3>& ray) {
                assert(!ray);
                assert(leaves == 1);
                ++fallback_calls;
                return true;
            });
        const auto dispatch = [&](tc_ui_pointer_event event) {
            return view->pointer_event(document_handle, &event);
        };

        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_MOVE, 50.0f, 50.0f, 0, 0, 0}) == TC_UI_EVENT_HANDLED);
        assert(enters == 1);
        assert(leaves == 0);
        assert(!tc_visual_item3d_handle_is_invalid(view->interaction().hovered(1)));

        SceneView3DCamera singular = identity_camera();
        singular.projection_matrix = {};
        view->set_camera(singular);
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_MOVE, 50.0f, 50.0f, 0, 0, 0}) == TC_UI_EVENT_HANDLED);
        assert(leaves == 1);
        assert(fallback_calls == 1);
        assert(tc_visual_item3d_handle_is_invalid(view->interaction().hovered(1)));
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));

        // No pressed sequence was active, so the failure did not quarantine
        // later valid input.
        view->set_camera(identity_camera());
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_MOVE, 50.0f, 50.0f, 0, 0, 0}) == TC_UI_EVENT_HANDLED);
        assert(enters == 2);
        assert(fallback_calls == 1);

        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        tc_visual_scene3d_destroy(scene_handle);
        tc_ui_document_destroy(document_handle);
    }

    void test_item_capture_is_local_and_fallback_receives_only_unhandled_pointer() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D scene{scene_handle};
        const auto item_handle = scene.adopt(std::make_unique<PrimitiveItem3D>(centered_triangle()));
        assert(item_handle);

        auto* view = new SceneView3D(scene);
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));
        view->layout(document_handle, {10.0f, 20.0f, 200.0f, 100.0f});
        view->set_camera(identity_camera());
        int actions = 0;
        int fallback_calls = 0;
        view->interaction().set_action_handler(*item_handle, [&](const ActionEvent3D& action) {
            assert(action.part == 42);
            ++actions;
        });
        view->set_fallback_pointer_handler(
            [&](SceneView3D&, const tc_ui_pointer_event&, const std::optional<termin::Ray3>& ray) {
                assert(ray);
                ++fallback_calls;
                return true;
            });
        const auto dispatch = [&](tc_ui_pointer_event event) {
            return view->pointer_event(document_handle, &event);
        };

        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_DOWN, 110.0f, 70.0f, 0, 1, 0}) == TC_UI_EVENT_HANDLED);
        assert(fallback_calls == 0);
        assert(tc_widget_handle_eq(document.pointer_capture(), view_handle));
        tc_ui_pointer_event wheel{};
        wheel.type = TC_UI_POINTER_WHEEL;
        wheel.x = 110.0f;
        wheel.y = 70.0f;
        wheel.wheel_y = 1.0f;
        assert(dispatch(wheel) == TC_UI_EVENT_HANDLED);
        tc_ui_pointer_event leave{};
        leave.type = TC_UI_POINTER_LEAVE;
        leave.x = 110.0f;
        leave.y = 70.0f;
        assert(dispatch(leave) == TC_UI_EVENT_HANDLED);
        assert(fallback_calls == 0);
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_MOVE, 400.0f, 400.0f, 0, 0, 0}) == TC_UI_EVENT_HANDLED);
        assert(fallback_calls == 0);
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_UP, 110.0f, 70.0f, 0, 1, 0}) == TC_UI_EVENT_HANDLED);
        assert(actions == 1);
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));

        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_DOWN, 205.0f, 115.0f, 0, 1, 0}) == TC_UI_EVENT_HANDLED);
        assert(fallback_calls == 1);
        assert(tc_widget_handle_eq(document.pointer_capture(), view_handle));
        assert(dispatch(tc_ui_pointer_event{TC_UI_POINTER_UP, 205.0f, 115.0f, 0, 1, 0}) == TC_UI_EVENT_HANDLED);
        assert(fallback_calls == 2);
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));

        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        tc_visual_scene3d_destroy(scene_handle);
        tc_ui_document_destroy(document_handle);
    }

    void test_scene_replacement_cancels_reentrant_scene_and_fallback_sequences() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle first_scene_handle = tc_visual_scene3d_create();
        const tc_visual_scene3d_handle second_scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D first_scene{first_scene_handle};
        TcVisualScene3D second_scene{second_scene_handle};
        const auto item_handle = first_scene.adopt(std::make_unique<PrimitiveItem3D>(centered_triangle()));
        assert(item_handle);

        auto* view = new SceneView3D(first_scene);
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));
        view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
        view->set_camera(identity_camera());

        int scene_downs = 0;
        int scene_cancels = 0;
        int fallback_downs = 0;
        int fallback_cancels = 0;
        view->interaction().set_target_pointer_handler(*item_handle, [&](const TargetPointerEvent3D& event) {
            if (event.kind == TargetPointerEventKind3D::Down) {
                ++scene_downs;
                // Reentrant replacement used to let the stale route result
                // resurrect capture in the new scene after this callback.
                view->set_scene(second_scene);
            } else if (event.kind == TargetPointerEventKind3D::Cancel) {
                ++scene_cancels;
            }
        });
        view->set_fallback_pointer_handler(
            [&](SceneView3D&, const tc_ui_pointer_event& event, const std::optional<termin::Ray3>&) {
                if (event.type == TC_UI_POINTER_DOWN)
                    ++fallback_downs;
                else if (event.type == TC_UI_POINTER_CANCEL)
                    ++fallback_cancels;
                return true;
            });

        tc_ui_pointer_event down{TC_UI_POINTER_DOWN, 50.0f, 50.0f, 0, 1, 0};
        assert(document.dispatch_pointer_event(down) == TC_UI_EVENT_HANDLED);
        assert(scene_downs == 1);
        assert(scene_cancels == 1);
        assert(tc_visual_item3d_handle_is_invalid(view->interaction().captured(1)));
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));
        assert(tc_widget_handle_is_invalid(tc_ui_document_pressed_widget(document_handle)));

        tc_ui_pointer_event up{TC_UI_POINTER_UP, 50.0f, 50.0f, 0, 1, 0};
        assert(document.dispatch_pointer_event(up) == TC_UI_EVENT_HANDLED);
        assert(fallback_downs == 0);
        assert(fallback_cancels == 0);

        // An empty scene routes the next sequence to fallback. Replacing that
        // scene must send its terminal Cancel through the document, clear both
        // pressed/capture state, and quarantine the matching Up.
        down.x = 90.0f;
        down.y = 90.0f;
        assert(document.dispatch_pointer_event(down) == TC_UI_EVENT_HANDLED);
        assert(fallback_downs == 1);
        assert(tc_widget_handle_eq(document.pointer_capture(), view_handle));
        view->set_scene(first_scene);
        assert(fallback_cancels == 1);
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));
        assert(tc_widget_handle_is_invalid(tc_ui_document_pressed_widget(document_handle)));
        up.x = 90.0f;
        up.y = 90.0f;
        assert(document.dispatch_pointer_event(up) == TC_UI_EVENT_HANDLED);
        assert(fallback_downs == 1);
        assert(fallback_cancels == 1);

        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        tc_visual_scene3d_destroy(first_scene_handle);
        tc_visual_scene3d_destroy(second_scene_handle);
        tc_ui_document_destroy(document_handle);
    }

    void test_reentrant_fallback_down_does_not_restore_pointer_ownership() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle first_scene_handle = tc_visual_scene3d_create();
        const tc_visual_scene3d_handle second_scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D first_scene{first_scene_handle};
        TcVisualScene3D second_scene{second_scene_handle};

        auto* view = new SceneView3D(first_scene);
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));
        view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
        view->set_camera(identity_camera());

        int downs = 0;
        int moves = 0;
        int ups = 0;
        int cancels = 0;
        view->set_fallback_pointer_handler(
            [&](SceneView3D&, const tc_ui_pointer_event& event, const std::optional<termin::Ray3>&) {
                if (event.type == TC_UI_POINTER_DOWN) {
                    ++downs;
                    // This replacement occurs before fallback ownership has
                    // been published by the outer Down.
                    view->set_scene(second_scene);
                } else if (event.type == TC_UI_POINTER_MOVE) {
                    ++moves;
                } else if (event.type == TC_UI_POINTER_UP) {
                    ++ups;
                } else if (event.type == TC_UI_POINTER_CANCEL) {
                    ++cancels;
                }
                return true;
            });

        tc_ui_pointer_event event{TC_UI_POINTER_DOWN, 90.0f, 90.0f, 0, 1, 0};
        assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
        assert(downs == 1);
        assert(cancels == 1);
        assert(tc_visual_scene3d_handle_eq(view->scene().handle(), second_scene_handle));
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));
        assert(tc_widget_handle_is_invalid(tc_ui_document_pressed_widget(document_handle)));

        event.type = TC_UI_POINTER_UP;
        assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
        assert(ups == 0);
        event.type = TC_UI_POINTER_MOVE;
        assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
        assert(moves == 1);

        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        tc_visual_scene3d_destroy(first_scene_handle);
        tc_visual_scene3d_destroy(second_scene_handle);
        tc_ui_document_destroy(document_handle);
    }

    void test_enter_replacement_aborts_old_scene_route_before_down_publication() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle first_scene_handle = tc_visual_scene3d_create();
        const tc_visual_scene3d_handle second_scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D first_scene{first_scene_handle};
        TcVisualScene3D second_scene{second_scene_handle};
        const auto item_handle = first_scene.adopt(std::make_unique<PrimitiveItem3D>(centered_triangle()));
        assert(item_handle);

        auto* view = new SceneView3D(first_scene);
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));
        view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
        view->set_camera(identity_camera());

        int enters = 0;
        int leaves = 0;
        int downs = 0;
        bool first_scene_destroyed = false;
        view->interaction().set_target_pointer_handler(*item_handle, [&](const TargetPointerEvent3D& event) {
            if (event.kind == TargetPointerEventKind3D::Enter) {
                ++enters;
                view->set_scene(second_scene);
                tc_visual_scene3d_destroy(first_scene_handle);
                first_scene_destroyed = true;
            } else if (event.kind == TargetPointerEventKind3D::Leave) {
                ++leaves;
            } else if (event.kind == TargetPointerEventKind3D::Down) {
                ++downs;
            }
        });

        tc_ui_pointer_event event{TC_UI_POINTER_DOWN, 50.0f, 50.0f, 0, 1, 0};
        assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
        assert(enters == 1);
        assert(leaves == 1);
        assert(downs == 0);
        assert(first_scene_destroyed);
        assert(tc_visual_scene3d_handle_eq(view->scene().handle(), second_scene_handle));
        assert(tc_visual_item3d_handle_is_invalid(view->interaction().hovered(1)));
        assert(tc_visual_item3d_handle_is_invalid(view->interaction().pressed(1)));
        assert(tc_visual_item3d_handle_is_invalid(view->interaction().captured(1)));
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));
        assert(tc_widget_handle_is_invalid(tc_ui_document_pressed_widget(document_handle)));

        event.type = TC_UI_POINTER_UP;
        assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        tc_visual_scene3d_destroy(second_scene_handle);
        tc_ui_document_destroy(document_handle);
    }

    void test_leave_replacement_does_not_repeat_old_scene_leave() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle first_scene_handle = tc_visual_scene3d_create();
        const tc_visual_scene3d_handle second_scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D first_scene{first_scene_handle};
        TcVisualScene3D second_scene{second_scene_handle};
        const auto item_handle = first_scene.adopt(std::make_unique<PrimitiveItem3D>(centered_triangle()));
        assert(item_handle);

        auto* view = new SceneView3D(first_scene);
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));
        view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
        view->set_camera(identity_camera());

        int enters = 0;
        int leaves = 0;
        bool first_scene_destroyed = false;
        view->interaction().set_target_pointer_handler(*item_handle, [&](const TargetPointerEvent3D& event) {
            if (event.kind == TargetPointerEventKind3D::Enter) {
                ++enters;
            } else if (event.kind == TargetPointerEventKind3D::Leave) {
                ++leaves;
                view->set_scene(second_scene);
                tc_visual_scene3d_destroy(first_scene_handle);
                first_scene_destroyed = true;
            }
        });

        tc_ui_pointer_event event{TC_UI_POINTER_MOVE, 50.0f, 50.0f, 0, 0, 0};
        assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
        assert(enters == 1);
        assert(leaves == 0);
        event.x = 90.0f;
        event.y = 90.0f;
        assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
        assert(leaves == 1);
        assert(first_scene_destroyed);
        assert(tc_visual_scene3d_handle_eq(view->scene().handle(), second_scene_handle));
        assert(tc_visual_item3d_handle_is_invalid(view->interaction().hovered(1)));
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));

        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        tc_visual_scene3d_destroy(second_scene_handle);
        tc_ui_document_destroy(document_handle);
    }

    void test_reentrant_terminal_up_replacement_does_not_quarantine_hover() {
        {
            const tc_ui_document_handle document_handle = tc_ui_document_create();
            TcDocument document(document_handle);
            const tc_visual_scene3d_handle first_scene_handle = tc_visual_scene3d_create();
            const tc_visual_scene3d_handle second_scene_handle = tc_visual_scene3d_create();
            TcVisualScene3D first_scene{first_scene_handle};
            TcVisualScene3D second_scene{second_scene_handle};
            const auto item_handle = first_scene.adopt(std::make_unique<PrimitiveItem3D>(centered_triangle()));
            assert(item_handle);

            auto* view = new SceneView3D(first_scene);
            const tc_widget_handle view_handle = document.adopt(view);
            assert(document.add_root(*view));
            view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
            view->set_camera(identity_camera());

            int target_ups = 0;
            int target_cancels = 0;
            int fallback_moves = 0;
            bool target_recaptured_ui_pointer = false;
            view->interaction().set_target_pointer_handler(*item_handle, [&](const TargetPointerEvent3D& event) {
                if (event.kind == TargetPointerEventKind3D::Up) {
                    ++target_ups;
                    target_recaptured_ui_pointer = tc_ui_document_set_pointer_capture(document_handle, view_handle);
                    view->set_scene(second_scene);
                } else if (event.kind == TargetPointerEventKind3D::Cancel) {
                    ++target_cancels;
                }
            });
            view->set_fallback_pointer_handler(
                [&](SceneView3D&, const tc_ui_pointer_event& event, const std::optional<termin::Ray3>&) {
                    if (event.type == TC_UI_POINTER_MOVE)
                        ++fallback_moves;
                    return true;
                });

            tc_ui_pointer_event event{TC_UI_POINTER_DOWN, 50.0f, 50.0f, 0, 1, 0};
            assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
            event.type = TC_UI_POINTER_UP;
            assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
            assert(target_ups == 1);
            assert(target_cancels == 0);
            assert(target_recaptured_ui_pointer);
            assert(tc_widget_handle_is_invalid(document.pointer_capture()));
            event.type = TC_UI_POINTER_MOVE;
            assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
            assert(fallback_moves == 1);

            assert(tc_ui_document_destroy_widget(document_handle, view_handle));
            tc_visual_scene3d_destroy(first_scene_handle);
            tc_visual_scene3d_destroy(second_scene_handle);
            tc_ui_document_destroy(document_handle);
        }

        {
            const tc_ui_document_handle document_handle = tc_ui_document_create();
            TcDocument document(document_handle);
            const tc_visual_scene3d_handle first_scene_handle = tc_visual_scene3d_create();
            const tc_visual_scene3d_handle second_scene_handle = tc_visual_scene3d_create();
            TcVisualScene3D first_scene{first_scene_handle};
            TcVisualScene3D second_scene{second_scene_handle};

            auto* view = new SceneView3D(first_scene);
            const tc_widget_handle view_handle = document.adopt(view);
            assert(document.add_root(*view));
            view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
            view->set_camera(identity_camera());

            int fallback_ups = 0;
            int fallback_cancels = 0;
            int fallback_moves = 0;
            bool fallback_recaptured_ui_pointer = false;
            view->set_fallback_pointer_handler(
                [&](SceneView3D&, const tc_ui_pointer_event& event, const std::optional<termin::Ray3>&) {
                    if (event.type == TC_UI_POINTER_UP) {
                        ++fallback_ups;
                        fallback_recaptured_ui_pointer =
                            tc_ui_document_set_pointer_capture(document_handle, view_handle);
                        view->set_fallback_pointer_handler([&](SceneView3D&,
                                                               const tc_ui_pointer_event& replacement_event,
                                                               const std::optional<termin::Ray3>&) {
                            if (replacement_event.type == TC_UI_POINTER_MOVE)
                                ++fallback_moves;
                            return true;
                        });
                        view->set_scene(second_scene);
                    } else if (event.type == TC_UI_POINTER_CANCEL) {
                        ++fallback_cancels;
                    } else if (event.type == TC_UI_POINTER_MOVE) {
                        ++fallback_moves;
                    }
                    return true;
                });

            tc_ui_pointer_event event{TC_UI_POINTER_DOWN, 90.0f, 90.0f, 0, 1, 0};
            assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
            assert(tc_widget_handle_eq(document.pointer_capture(), view_handle));
            event.type = TC_UI_POINTER_UP;
            assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
            assert(fallback_ups == 1);
            assert(fallback_cancels == 0);
            assert(fallback_recaptured_ui_pointer);
            assert(tc_widget_handle_is_invalid(document.pointer_capture()));
            event.type = TC_UI_POINTER_MOVE;
            assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
            assert(fallback_moves == 1);

            assert(tc_ui_document_destroy_widget(document_handle, view_handle));
            tc_visual_scene3d_destroy(first_scene_handle);
            tc_visual_scene3d_destroy(second_scene_handle);
            tc_ui_document_destroy(document_handle);
        }
    }

    void test_cancel_callback_replacement_is_non_recursive_and_wins_outer_replacement() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle first_scene_handle = tc_visual_scene3d_create();
        const tc_visual_scene3d_handle outer_scene_handle = tc_visual_scene3d_create();
        const tc_visual_scene3d_handle nested_scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D first_scene{first_scene_handle};
        TcVisualScene3D outer_scene{outer_scene_handle};
        TcVisualScene3D nested_scene{nested_scene_handle};
        const auto item_handle = first_scene.adopt(std::make_unique<PrimitiveItem3D>(centered_triangle()));
        assert(item_handle);

        auto* view = new SceneView3D(first_scene);
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));
        view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
        view->set_camera(identity_camera());

        int cancels = 0;
        bool recaptured_ui_pointer_during_cancel = false;
        view->interaction().set_target_pointer_handler(*item_handle, [&](const TargetPointerEvent3D& event) {
            if (event.kind == TargetPointerEventKind3D::Cancel) {
                ++cancels;
                recaptured_ui_pointer_during_cancel = tc_ui_document_set_pointer_capture(document_handle, view_handle);
                view->set_scene(nested_scene);
            }
        });

        tc_ui_pointer_event event{TC_UI_POINTER_DOWN, 50.0f, 50.0f, 0, 1, 0};
        assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
        assert(tc_widget_handle_eq(document.pointer_capture(), view_handle));
        view->set_scene(outer_scene);
        assert(cancels == 1);
        assert(recaptured_ui_pointer_during_cancel);
        assert(tc_visual_scene3d_handle_eq(view->scene().handle(), nested_scene_handle));
        assert(tc_widget_handle_is_invalid(document.pointer_capture()));
        assert(tc_widget_handle_is_invalid(tc_ui_document_pressed_widget(document_handle)));
        assert(tc_visual_item3d_handle_is_invalid(view->interaction().captured(1)));

        event.type = TC_UI_POINTER_UP;
        assert(document.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED);
        assert(cancels == 1);

        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        tc_visual_scene3d_destroy(first_scene_handle);
        tc_visual_scene3d_destroy(outer_scene_handle);
        tc_visual_scene3d_destroy(nested_scene_handle);
        tc_ui_document_destroy(document_handle);
    }

    void test_destroy_cancels_capture_and_releases_callbacks_without_owning_scene() {
        const tc_ui_document_handle document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const tc_visual_scene3d_handle scene_handle = tc_visual_scene3d_create();
        TcVisualScene3D scene{scene_handle};
        auto* view = new SceneView3D(scene);
        const tc_widget_handle view_handle = document.adopt(view);
        assert(document.add_root(*view));
        view->layout(document_handle, {0.0f, 0.0f, 100.0f, 100.0f});
        view->set_camera(identity_camera());

        auto lifetime = std::make_shared<int>(7);
        std::weak_ptr<int> weak_lifetime = lifetime;
        int cancel_calls = 0;
        view->set_fallback_pointer_handler([lifetime, &cancel_calls](SceneView3D&,
                                                                     const tc_ui_pointer_event& event,
                                                                     const std::optional<termin::Ray3>&) {
            if (event.type == TC_UI_POINTER_CANCEL)
                ++cancel_calls;
            return true;
        });
        lifetime.reset();
        tc_ui_pointer_event down{TC_UI_POINTER_DOWN, 90.0f, 90.0f, 0, 1, 0};
        assert(view->pointer_event(document_handle, &down) == TC_UI_EVENT_HANDLED);
        assert(tc_widget_handle_eq(document.pointer_capture(), view_handle));

        assert(tc_ui_document_destroy_widget(document_handle, view_handle));
        assert(cancel_calls == 1);
        assert(weak_lifetime.expired());
        assert(tc_visual_scene3d_is_valid(scene_handle));
        tc_visual_scene3d_destroy(scene_handle);
        tc_ui_document_destroy(document_handle);
    }

} // namespace

int main() {
    test_independent_views_resize_and_ray_projection();
    test_invalid_projection_inputs_reject_world_ray();
    test_projection_failure_cancels_active_scene_pointer_without_fallback();
    test_projection_failure_clears_hover_before_optional_fallback();
    test_item_capture_is_local_and_fallback_receives_only_unhandled_pointer();
    test_scene_replacement_cancels_reentrant_scene_and_fallback_sequences();
    test_reentrant_fallback_down_does_not_restore_pointer_ownership();
    test_enter_replacement_aborts_old_scene_route_before_down_publication();
    test_leave_replacement_does_not_repeat_old_scene_leave();
    test_reentrant_terminal_up_replacement_does_not_quarantine_hover();
    test_cancel_callback_replacement_is_non_recursive_and_wins_outer_replacement();
    test_destroy_cancels_capture_and_releases_callbacks_without_owning_scene();
    return EXIT_SUCCESS;
}
