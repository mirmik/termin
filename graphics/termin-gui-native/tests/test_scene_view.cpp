#ifdef NDEBUG
#undef NDEBUG
#endif

#include <termin/gui_native/tc_document.hpp>
#include <termin/gui_native/widget_bindings_c_api.h>
#include <termin/gui_native/widgets.hpp>

#include <cassert>
#include <cmath>
#include <cstdlib>
#include <memory>
#include <vector>

#include <tcbase/input_enums.hpp>
#include <termin_visual_scene/builtin_items2d.hpp>
#include <termin_visual_scene/interaction2d.hpp>

using namespace termin::gui_native;
using namespace termin::visual;

namespace {

    std::vector<const tc_ui_draw_command*> commands_of_type(const tc_ui_draw_list* draw_list,
                                                            tc_ui_draw_command_type type) {
        std::vector<const tc_ui_draw_command*> result;
        for (std::size_t index = 0; index < tc_ui_draw_list_command_count(draw_list); ++index) {
            const auto* command = tc_ui_draw_list_command_at(draw_list, index);
            if (command && command->type == type)
                result.push_back(command);
        }
        return result;
    }

    std::vector<std::size_t> command_indices(const tc_ui_draw_list* draw_list, tc_ui_draw_command_type type) {
        std::vector<std::size_t> result;
        for (std::size_t index = 0; index < tc_ui_draw_list_command_count(draw_list); ++index) {
            const auto* command = tc_ui_draw_list_command_at(draw_list, index);
            if (command && command->type == type)
                result.push_back(index);
        }
        return result;
    }

    tgfx::FillPaint fill(float r, float g, float b, float a = 1.0f) {
        return {{r, g, b, a}};
    }

    bool handle_eq(GraphicItemHandle left, GraphicItemHandle right) {
        return left.scene_id == right.scene_id && left.index == right.index && left.generation == right.generation;
    }

    template <typename Item, typename... Args>
    Item* adopt(TcVisualScene& scene, GraphicItem2D* parent, Args&&... args) {
        auto item = std::make_unique<Item>(std::forward<Args>(args)...);
        auto* result = item.get();
        assert(scene.adopt(std::move(item), parent));
        return result;
    }

    void test_scene_uses_generation_handles_and_canonical_hit_testing() {
        const auto scene_handle = tc_visual_scene_create();
        TcVisualScene scene{scene_handle};
        auto* back =
            adopt<RectItem2D>(scene, nullptr, termin::Rect2f{0.0f, 0.0f, 100.0f, 80.0f}, fill(0.2f, 0.3f, 0.4f));
        auto* child = adopt<RectItem2D>(scene, back, termin::Rect2f{0.0f, 0.0f, 20.0f, 10.0f}, fill(0.7f, 0.2f, 0.2f));
        auto* front =
            adopt<RectItem2D>(scene, nullptr, termin::Rect2f{0.0f, 0.0f, 100.0f, 80.0f}, fill(0.3f, 0.6f, 0.4f));
        back->set_local_transform(termin::Affine2f::translation({10.0f, 20.0f}));
        child->set_local_transform(termin::Affine2f::translation({5.0f, 7.0f}));
        child->set_z_order(10);
        front->set_local_transform(termin::Affine2f::translation({20.0f, 30.0f}));
        front->set_z_order(20);
        const auto back_handle = back->handle();

        const auto front_hit = hit_test(scene, {25.0f, 35.0f});
        assert(front_hit && handle_eq(*front_hit, front->handle()));
        front->set_enabled(false);
        const auto child_hit = hit_test(scene, {16.0f, 28.0f});
        assert(child_hit && handle_eq(*child_hit, child->handle()));
        assert(scene.destroy(back_handle));
        assert(!scene.contains(back_handle));
        assert(scene.contains(front->handle()));

        auto* replacement =
            adopt<RectItem2D>(scene, nullptr, termin::Rect2f{0.0f, 0.0f, 20.0f, 20.0f}, fill(0.8f, 0.8f, 0.2f));
        assert(replacement->handle().generation != back_handle.generation ||
               replacement->handle().index != back_handle.index);
        tc_visual_scene_destroy(scene_handle);
    }

    void test_view_transform_forwarding_pan_zoom_and_draw_list_bridge() {
        const auto document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const auto scene_handle = tc_visual_scene_create();
        TcVisualScene scene{scene_handle};
        auto* item =
            adopt<RectItem2D>(scene, nullptr, termin::Rect2f{0.0f, 0.0f, 80.0f, 40.0f}, fill(0.8f, 0.2f, 0.1f));
        item->set_local_transform(termin::Affine2f::translation({10.0f, 20.0f}));
        auto* view = new SceneView(scene);
        const auto view_handle = document.adopt(view);
        assert(document.add_root(*view));
        document.layout_roots({100.0f, 50.0f, 400.0f, 300.0f});
        assert(view->world_to_screen({10.0f, 20.0f}).x == 110.0f);

        auto* draw_list = tc_ui_draw_list_create();
        auto* context = tc_ui_paint_context_create(draw_list);
        document.paint_roots(context);
        assert(commands_of_type(draw_list, TC_UI_DRAW_CANVAS2D_LIST).size() == 1);
        assert(!commands_of_type(draw_list, TC_UI_DRAW_LINE).empty());

        bool forwarded = false;
        view->set_pointer_handler([&](SceneView&, tc_ui_point world, const tc_ui_pointer_event& event) {
            forwarded = event.type == TC_UI_POINTER_DOWN && std::isfinite(world.x);
            return forwarded;
        });
        assert(document.dispatch_pointer_event({TC_UI_POINTER_DOWN, 120.0f, 80.0f, 0, 1, 0, 0.0f, 0.0f}) ==
               TC_UI_EVENT_HANDLED);
        assert(forwarded);
        view->set_pointer_handler({});
        document.dispatch_pointer_event({TC_UI_POINTER_UP, 120.0f, 80.0f, 0, 1, 0, 0.0f, 0.0f});

        assert(document.dispatch_pointer_event({TC_UI_POINTER_DOWN, 300.0f, 200.0f, 2, 1, 0, 0.0f, 0.0f}) ==
               TC_UI_EVENT_HANDLED);
        assert(document.dispatch_pointer_event({TC_UI_POINTER_MOVE, 320.0f, 230.0f, 2, 0, 0, 0.0f, 0.0f}) ==
               TC_UI_EVENT_HANDLED);
        assert(view->offset().x == 20.0f && view->offset().y == 30.0f);
        document.dispatch_pointer_event({TC_UI_POINTER_UP, 320.0f, 230.0f, 2, 1, 0, 0.0f, 0.0f});

        const tc_ui_point anchor{250.0f, 160.0f};
        const auto before = view->screen_to_world(anchor);
        document.dispatch_pointer_event({TC_UI_POINTER_WHEEL, anchor.x, anchor.y, 0, 0, 0, 0.0f, 1.0f});
        const auto after = view->screen_to_world(anchor);
        assert(view->zoom() > 1.0f);
        assert(std::fabs(before.x - after.x) < 0.001f);
        assert(std::fabs(before.y - after.y) < 0.001f);

        tc_ui_paint_context_destroy(context);
        tc_ui_draw_list_destroy(draw_list);
        assert(tc_ui_document_destroy_widget(document.get(), view_handle));
        tc_ui_document_destroy(document_handle);
        tc_visual_scene_destroy(scene_handle);
    }

    void test_widget_portal_has_separate_document_lifetime() {
        const auto document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const auto scene_handle = tc_visual_scene_create();
        TcVisualScene scene{scene_handle};
        auto* item =
            adopt<RectItem2D>(scene, nullptr, termin::Rect2f{0.0f, 0.0f, 100.0f, 30.0f}, fill(0.2f, 0.2f, 0.25f));
        item->set_local_transform(termin::Affine2f::translation({15.0f, 12.0f}));
        auto* button = new Button("Embedded");
        const auto button_handle = document.adopt(button);
        auto* view = new SceneView(scene);
        const auto view_handle = document.adopt(view);
        assert(view->set_widget_portal(item->handle(), button_handle));
        assert(document.add_root(*view));
        document.layout_roots({10.0f, 20.0f, 300.0f, 200.0f});

        assert(button->parent_widget() == view->c_widget());
        assert(button->bounds().x == 0.0f);
        assert(button->bounds().y == 0.0f);
        assert(tc_widget_subtree_transform(button->c_widget()).translation.x == 25.0f);
        assert(tc_widget_subtree_transform(button->c_widget()).translation.y == 32.0f);
        assert(tc_widget_handle_eq(document.hit_test(30.0f, 40.0f), button_handle));

        view->set_zoom(2.0f, {10.0f, 20.0f});
        document.layout_roots({10.0f, 20.0f, 300.0f, 200.0f});
        assert(button->bounds().x == 0.0f);
        assert(button->bounds().width == 100.0f);
        assert(tc_widget_subtree_transform(button->c_widget()).scale == 2.0f);
        assert(tc_widget_handle_eq(document.hit_test(50.0f, 60.0f), button_handle));

        auto* draw_list = tc_ui_draw_list_create();
        auto* context = tc_ui_paint_context_create(draw_list);
        document.paint_roots(context);
        assert(commands_of_type(draw_list, TC_UI_DRAW_PUSH_UNIFORM_TRANSFORM).size() == 1);
        assert(commands_of_type(draw_list, TC_UI_DRAW_POP_TRANSFORM).size() == 1);
        tc_ui_paint_context_destroy(context);
        tc_ui_draw_list_destroy(draw_list);

        view->set_zoom(3.0f, {10.0f, 20.0f});
        assert(tc_widget_subtree_transform(button->c_widget()).scale == 3.0f);
        assert(tc_widget_handle_eq(document.hit_test(70.0f, 80.0f), button_handle));

        assert(tc_ui_document_set_pointer_capture(document.get(), button_handle));
        assert(view->clear_widget_portal(item->handle()));
        assert(button->parent_widget() == nullptr);
        assert(tc_widget_subtree_transform(button->c_widget()).scale == 1.0f);
        assert(tc_widget_handle_is_invalid(tc_ui_document_pointer_capture(document.get())));

        auto* replacement = new Button("Replacement");
        const auto replacement_handle = document.adopt(replacement);
        assert(view->set_widget_portal(item->handle(), button_handle));
        document.layout_roots({10.0f, 20.0f, 300.0f, 200.0f});
        assert(view->set_widget_portal(item->handle(), replacement_handle));
        assert(button->parent_widget() == nullptr);
        document.layout_roots({10.0f, 20.0f, 300.0f, 200.0f});
        assert(replacement->parent_widget() == view->c_widget());
        view->clear_widget_portals();
        assert(replacement->parent_widget() == nullptr);
        assert(view->set_widget_portal(item->handle(), button_handle));
        document.layout_roots({10.0f, 20.0f, 300.0f, 200.0f});

        auto* conflicting_item =
            adopt<RectItem2D>(scene, nullptr, termin::Rect2f{0.0f, 0.0f, 10.0f, 10.0f}, fill(0.3f, 0.2f, 0.2f));
        assert(!view->set_widget_portal(conflicting_item->handle(), button_handle));

        assert(tc_ui_document_set_pointer_capture(document.get(), button_handle));
        item->set_local_transform(termin::Affine2f::rotation(0.25f));
        document.layout_roots({10.0f, 20.0f, 300.0f, 200.0f});
        assert(button->parent_widget() == nullptr);
        assert(tc_widget_handle_is_invalid(tc_ui_document_pointer_capture(document.get())));
        item->set_local_transform(termin::Affine2f::translation({15.0f, 12.0f}));
        document.layout_roots({10.0f, 20.0f, 300.0f, 200.0f});
        assert(button->parent_widget() == view->c_widget());

        assert(scene.destroy(item->handle()));
        document.layout_roots({10.0f, 20.0f, 300.0f, 200.0f});
        assert(button->parent_widget() == nullptr);
        assert(tc_widget_subtree_transform(button->c_widget()).scale == 1.0f);
        assert(tc_ui_document_is_alive(document.get(), button_handle));

        assert(tc_ui_document_destroy_widget(document.get(), view_handle));
        assert(tc_ui_document_is_alive(document.get(), button_handle));
        assert(tc_ui_document_destroy_widget(document.get(), button_handle));
        assert(tc_ui_document_destroy_widget(document.get(), replacement_handle));
        assert(scene.destroy(conflicting_item->handle()));
        tc_ui_document_destroy(document_handle);
        tc_visual_scene_destroy(scene_handle);
    }

    void test_widget_portal_uses_scene_paint_and_hit_order() {
        const auto document_handle = tc_ui_document_create();
        TcDocument document(document_handle);
        const auto scene_handle = tc_visual_scene_create();
        TcVisualScene scene{scene_handle};
        auto* source =
            adopt<RectItem2D>(scene, nullptr, termin::Rect2f{0.0f, 0.0f, 120.0f, 40.0f}, fill(0.1f, 0.2f, 0.3f));
        auto* front =
            adopt<RectItem2D>(scene, nullptr, termin::Rect2f{0.0f, 0.0f, 120.0f, 40.0f}, fill(0.8f, 0.2f, 0.1f));
        source->set_z_order(0);
        front->set_z_order(1);

        auto* button = new Button("Portal layer");
        const auto button_handle = document.adopt(button);
        auto* view = new SceneView(scene);
        const auto view_handle = document.adopt(view);
        assert(view->set_widget_portal(source->handle(), button_handle));
        assert(document.add_root(*view));
        document.layout_roots({0.0f, 0.0f, 300.0f, 180.0f});

        auto* draw_list = tc_ui_draw_list_create();
        auto* context = tc_ui_paint_context_create(draw_list);
        document.paint_roots(context);
        const auto canvas = command_indices(draw_list, TC_UI_DRAW_CANVAS2D_LIST);
        const auto text = command_indices(draw_list, TC_UI_DRAW_TEXT);
        assert(canvas.size() == 2);
        assert(text.size() == 1);
        assert(canvas[0] < text[0] && text[0] < canvas[1]);

        assert(tc_widget_handle_eq(document.hit_test(20.0f, 20.0f), view_handle));
        front->set_enabled(false);
        assert(tc_widget_handle_eq(document.hit_test(20.0f, 20.0f), button_handle));

        front->set_enabled(true);
        front->set_z_order(-1);
        assert(tc_widget_handle_eq(document.hit_test(20.0f, 20.0f), button_handle));
        front->set_z_order(0);
        assert(tc_widget_handle_eq(document.hit_test(20.0f, 20.0f), view_handle));

        tc_ui_paint_context_destroy(context);
        tc_ui_draw_list_destroy(draw_list);
        assert(tc_ui_document_destroy_widget(document.get(), view_handle));
        assert(tc_ui_document_destroy_widget(document.get(), button_handle));
        tc_ui_document_destroy(document_handle);
        tc_visual_scene_destroy(scene_handle);
    }

    struct CallbackCounters {
        int calls = 0;
        int releases = 0;
        int wheels = 0;
        int cancels = 0;
        float x = 0.0f;
        float y = 0.0f;
    };

    void record_click(void* data) {
        ++static_cast<CallbackCounters*>(data)->calls;
    }

    void release_callback(void* data) {
        ++static_cast<CallbackCounters*>(data)->releases;
    }

    bool record_pointer(void* data, float x, float y, const tc_ui_pointer_event* event) {
        auto& counters = *static_cast<CallbackCounters*>(data);
        ++counters.calls;
        if (event->type == TC_UI_POINTER_CANCEL) {
            ++counters.cancels;
            return true;
        }
        if (event->type != TC_UI_POINTER_WHEEL)
            return event->type == TC_UI_POINTER_DOWN;
        ++counters.wheels;
        counters.x = x;
        counters.y = y;
        return true;
    }

    bool measure_text(void*, const char*, size_t length, float size, tc_ui_text_metrics* metrics) {
        *metrics = {static_cast<float>(length) * size * 0.5f, size, size * 0.8f, size * 0.2f, size * 1.2f};
        return true;
    }

    void test_typed_widget_bindings() {
        CallbackCounters clicks, pointer, replacement, rejected;
        const auto document = tc_ui_document_create();
        const auto metrics = tc_ui_presentation_metrics_identity({640, 320});
        assert(tc_ui_document_set_presentation_metrics(document, &metrics));
        tc_ui_document_set_text_measurer(document, measure_text, nullptr);
        const auto other_document = tc_ui_document_create();
        const auto scene = tc_visual_scene_create();
        const auto box = tc_ui_box_create(document, TC_UI_BOX_VERTICAL);
        const auto button = tc_ui_button_create(document, "Action");
        const auto label = tc_ui_label_create(document, "Value");
        const auto view = tc_ui_scene_view_create(document, scene);
        const auto foreign_button = tc_ui_button_create(other_document, "Other");
        assert(tc_ui_widget_ref_is_alive(box) && tc_ui_widget_ref_is_alive(button) &&
               tc_ui_widget_ref_is_alive(label) && tc_ui_widget_ref_is_alive(view));
        assert(!tc_ui_box_add_child(box, foreign_button, TC_UI_BOX_CHILD_FIXED, 40));
        assert(!tc_ui_box_add_child(box, box, TC_UI_BOX_CHILD_FIXED, 40));
        assert(!tc_ui_widget_ref_is_alive(tc_ui_scene_view_create(document, tc_visual_scene_handle_invalid())));
        assert(tc_ui_document_live_widget_count(document) == 4);
        assert(tc_ui_document_live_widget_count(other_document) == 1);
        assert(!tc_ui_button_set_text(label, "Wrong widget"));
        tc_widget custom{};
        tc_widget_init_unowned(&custom, nullptr, TC_LANGUAGE_CXX, &custom);
        const auto custom_handle = tc_ui_document_attach_borrowed_widget(document, &custom);
        assert(tc_ui_widget_ref_is_alive({document, custom_handle}));
        assert(!tc_ui_button_set_text({document, custom_handle}, "Incompatible C++ body"));
        assert(tc_ui_document_destroy_widget(document, custom_handle));
        tc_widget_deinit_unowned(&custom);
        assert(tc_ui_label_set_text(label, "Chart value"));
        assert(tc_ui_button_set_text(button, "Fit"));
        assert(tc_ui_box_set_spacing(box, 4));

        assert(tc_ui_box_add_child(box, button, TC_UI_BOX_CHILD_FIXED, 40));
        assert(tc_ui_box_add_child(box, label, TC_UI_BOX_CHILD_FIXED, 24));
        assert(tc_ui_box_add_child(box, view, TC_UI_BOX_CHILD_FLEX, 1));
        assert(tc_ui_widget_ref_remove_child(box, label));
        assert(tc_ui_widget_ref_is_alive(label));
        assert(tc_ui_box_add_child(box, label, TC_UI_BOX_CHILD_FIXED, 24));
        assert(tc_ui_document_add_root(document, box.handle));
        assert(tc_ui_widget_ref_set_enabled(button, false));
        bool flag = true;
        assert(tc_ui_widget_ref_get_enabled(button, &flag) && !flag);
        assert(tc_ui_widget_ref_set_enabled(button, true));
        assert(tc_ui_widget_ref_set_visible(label, false));
        assert(tc_ui_widget_ref_get_visible(label, &flag) && !flag);
        assert(tc_ui_widget_ref_set_visible(label, true));
        assert(tc_ui_scene_view_set_grid_visible(view, false));
        assert(tc_ui_scene_view_set_navigation_enabled(view, false));

        assert(tc_ui_button_connect_clicked(label, record_click, &rejected, release_callback) == 0);
        assert(rejected.releases == 1);
        const size_t connection = tc_ui_button_connect_clicked(button, record_click, &clicks, release_callback);
        assert(connection != 0 && clicks.releases == 0);
        assert(tc_ui_scene_view_set_pointer_handler(view, record_pointer, &pointer, release_callback));
        tc_ui_document_layout_roots(document, {0, 0, 640, 320});
        tc_ui_rect bounds{};
        assert(tc_ui_widget_ref_get_bounds(view, &bounds) && bounds.width == 640 && bounds.height > 200);
        auto* draw_list = tc_ui_draw_list_create();
        auto* context = tc_ui_paint_context_create(draw_list);
        tc_ui_document_paint_roots(document, context);
        assert(clicks.calls == 0 && pointer.calls == 0);
        tc_ui_paint_context_destroy(context);
        tc_ui_draw_list_destroy(draw_list);

        assert(tc_ui_document_set_focus(document, button.handle));
        tc_ui_key_event key{};
        key.key = TC_UI_KEY_SPACE;
        key.type = TC_UI_KEY_DOWN;
        assert(tc_ui_document_dispatch_key_event(document, &key) == TC_UI_EVENT_HANDLED);
        key.type = TC_UI_KEY_UP;
        assert(tc_ui_document_dispatch_key_event(document, &key) == TC_UI_EVENT_HANDLED);
        assert(clicks.calls == 1);
        assert(tc_ui_button_disconnect_clicked(button, connection));
        assert(clicks.releases == 1);

        tc_ui_pointer_event wheel{};
        wheel.type = TC_UI_POINTER_WHEEL;
        wheel.x = bounds.x + 20;
        wheel.y = bounds.y + 10;
        wheel.wheel_y = 1;
        assert(tc_ui_document_dispatch_pointer_event(document, &wheel) == TC_UI_EVENT_HANDLED);
        assert(pointer.wheels == 1 && pointer.x == 20 && pointer.y == 10);
        tc_ui_pointer_event down{};
        down.type = TC_UI_POINTER_DOWN;
        down.button = tcbase::mouse_button_value(tcbase::MouseButton::LEFT);
        down.x = wheel.x;
        down.y = wheel.y;
        assert(tc_ui_document_dispatch_pointer_event(document, &down) == TC_UI_EVENT_HANDLED);
        assert(tc_widget_handle_eq(tc_ui_document_pointer_capture(document), view.handle));
        assert(tc_ui_widget_ref_set_visible(view, false));
        assert(pointer.cancels == 1);
        assert(tc_widget_handle_is_invalid(tc_ui_document_pointer_capture(document)));
        assert(tc_ui_widget_ref_set_visible(view, true));
        assert(tc_ui_scene_view_set_pointer_handler(view, record_pointer, &replacement, release_callback));
        assert(pointer.releases == 1 && replacement.releases == 0);
        assert(tc_ui_scene_view_set_pointer_handler(view, nullptr, nullptr, nullptr));
        assert(replacement.releases == 1);
        assert(tc_ui_document_dispatch_pointer_event(document, &wheel) == TC_UI_EVENT_IGNORED);

        assert(tc_ui_scene_view_set_pointer_handler(view, record_pointer, &replacement, release_callback));
        assert(tc_ui_widget_ref_destroy(box));
        assert(replacement.releases == 2 && clicks.releases == 1);
        assert(!tc_ui_widget_ref_is_alive(view) && !tc_ui_widget_ref_is_alive(button));
        assert(tc_visual_scene_is_valid(scene));
        assert(!tc_ui_button_set_text(button, "Stale"));
        assert(tc_ui_button_connect_clicked(foreign_button, record_click, &clicks, release_callback) != 0);
        tc_ui_document_destroy(other_document);
        assert(clicks.releases == 2);
        tc_ui_document_destroy(document);
        tc_visual_scene_destroy(scene);
    }

} // namespace

int main() {
    test_scene_uses_generation_handles_and_canonical_hit_testing();
    test_view_transform_forwarding_pan_zoom_and_draw_list_bridge();
    test_widget_portal_has_separate_document_lifetime();
    test_widget_portal_uses_scene_paint_and_hit_order();
    test_typed_widget_bindings();
    return EXIT_SUCCESS;
}
