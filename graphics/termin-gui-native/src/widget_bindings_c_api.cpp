#include <termin/gui_native/widget_bindings_c_api.h>

#include <cmath>
#include <exception>
#include <memory>
#include <utility>

#include <tcbase/tc_log.h>
#include <termin/gui_native/box_layout.hpp>
#include <termin/gui_native/button.hpp>
#include <termin/gui_native/document_builder.hpp>
#include <termin/gui_native/label.hpp>
#include <termin/gui_native/scene_view.hpp>

namespace {
    using namespace termin::gui_native;

    tc_widget_ref invalid_widget() {
        return {tc_ui_document_handle_invalid(), tc_widget_handle_invalid()};
    }

    bool report_error(const char* operation, const char* message) {
        tc_log_error("[termin-gui-native] %s: %s", operation, message);
        return false;
    }

    template <typename Result, typename Function>
    Result guard(const char* operation, Result failure, Function&& function) noexcept {
        try {
            return function();
        } catch (const std::exception& error) {
            report_error(operation, error.what());
        } catch (...) {
            report_error(operation, "unexpected exception");
        }
        return failure;
    }

    tc_widget* resolve(tc_widget_ref ref, const char* operation) {
        tc_widget* widget = tc_ui_document_resolve_widget(ref.document, ref.handle);
        if (!widget)
            report_error(operation, "widget reference is stale or invalid");
        return widget;
    }

    template <typename T> T* resolve(tc_widget_ref ref, const char* operation) {
        tc_widget* widget = resolve(ref, operation);
        if (!widget)
            return nullptr;
        T* typed = dynamic_cast<T*>(NativeWidget::from_widget(widget));
        if (!typed)
            report_error(operation, "widget has the wrong native type");
        return typed;
    }

    template <typename T, typename... Args>
    tc_widget_ref make_widget(tc_ui_document_handle document, const char* operation, Args&&... args) {
        return guard(operation, invalid_widget(), [&] {
            DocumentBuilder builder{TcDocument{document}};
            auto& widget = builder.make<T>(std::forward<Args>(args)...);
            return tc_widget_ref{document, widget.handle()};
        });
    }

    template <typename T> bool set_text(tc_widget_ref ref, const char* operation, const char* text) {
        return guard(operation, false, [&] {
            if (!text)
                return report_error(operation, "text must not be null");
            T* widget = resolve<T>(ref, operation);
            if (!widget)
                return false;
            widget->set_text(text);
            return true;
        });
    }

    template <typename Value, typename Getter>
    bool get_widget_value(tc_widget_ref ref, const char* operation, Value* out, Getter getter) {
        if (!out)
            return report_error(operation, "output must not be null");
        tc_widget* widget = resolve(ref, operation);
        if (!widget)
            return false;
        *out = getter(widget);
        return true;
    }

    template <typename Setter>
    bool set_widget_flag(tc_widget_ref ref, const char* operation, bool value, Setter setter) {
        tc_widget* widget = resolve(ref, operation);
        if (!widget)
            return false;
        setter(widget, value);
        return true;
    }

    std::shared_ptr<void> hold_userdata(void* userdata, tc_ui_widget_callback_destroy_fn destroy) {
        return std::shared_ptr<void>(userdata, [destroy](void* data) {
            if (destroy)
                destroy(data);
        });
    }
} // namespace

tc_widget_ref tc_ui_box_create(tc_ui_document_handle document, tc_ui_box_orientation orientation) {
    if (orientation != TC_UI_BOX_HORIZONTAL && orientation != TC_UI_BOX_VERTICAL) {
        report_error(__func__, "invalid box orientation");
        return invalid_widget();
    }
    return make_widget<BoxLayout>(
        document, __func__, orientation == TC_UI_BOX_HORIZONTAL ? Orientation::Horizontal : Orientation::Vertical);
}

tc_widget_ref tc_ui_button_create(tc_ui_document_handle document, const char* text) {
    if (!text) {
        report_error(__func__, "text must not be null");
        return invalid_widget();
    }
    return make_widget<Button>(document, __func__, text);
}

tc_widget_ref tc_ui_label_create(tc_ui_document_handle document, const char* text) {
    if (!text) {
        report_error(__func__, "text must not be null");
        return invalid_widget();
    }
    return make_widget<Label>(document, __func__, text);
}

tc_widget_ref tc_ui_scene_view_create(tc_ui_document_handle document, tc_visual_scene_handle scene) {
    if (!tc_visual_scene_is_valid(scene)) {
        report_error(__func__, "view requires a live borrowed scene");
        return invalid_widget();
    }
    return make_widget<SceneView>(document, __func__, termin::visual::TcVisualScene{scene});
}

bool tc_ui_widget_ref_is_alive(tc_widget_ref widget) {
    return tc_ui_document_is_alive(widget.document, widget.handle);
}

bool tc_ui_widget_ref_get_bounds(tc_widget_ref widget, tc_ui_rect* out_bounds) {
    return get_widget_value(widget, __func__, out_bounds, tc_widget_bounds_in_document);
}

bool tc_ui_widget_ref_get_visible(tc_widget_ref widget, bool* out_visible) {
    return get_widget_value(widget, __func__, out_visible, tc_widget_is_visible);
}

bool tc_ui_widget_ref_set_visible(tc_widget_ref widget, bool visible) {
    return set_widget_flag(widget, __func__, visible, tc_widget_set_visible);
}

bool tc_ui_widget_ref_get_enabled(tc_widget_ref widget, bool* out_enabled) {
    return get_widget_value(widget, __func__, out_enabled, tc_widget_is_enabled);
}

bool tc_ui_widget_ref_set_enabled(tc_widget_ref widget, bool enabled) {
    return set_widget_flag(widget, __func__, enabled, tc_widget_set_enabled);
}

bool tc_ui_widget_ref_remove_child(tc_widget_ref parent, tc_widget_ref child) {
    if (!tc_ui_document_handle_eq(parent.document, child.document))
        return report_error(__func__, "parent and child belong to different documents");
    tc_widget* parent_widget = resolve(parent, __func__);
    tc_widget* child_widget = resolve(child, __func__);
    if (!parent_widget || !child_widget)
        return false;
    return tc_widget_remove_child(parent_widget, child_widget) || report_error(__func__, "no such child");
}

bool tc_ui_widget_ref_destroy(tc_widget_ref widget) {
    return tc_ui_document_destroy_widget_recursive(widget.document, widget.handle);
}

bool tc_ui_box_add_child(tc_widget_ref box, tc_widget_ref child, tc_ui_box_child_policy policy, float value) {
    if (!tc_ui_document_handle_eq(box.document, child.document))
        return report_error(__func__, "parent and child belong to different documents");
    if (!std::isfinite(value) || value < 0.0f)
        return report_error(__func__, "child extent or flex must be finite and nonnegative");
    LayoutPolicy placement;
    switch (policy) {
    case TC_UI_BOX_CHILD_FIXED:
        placement = LayoutPolicy::Fixed;
        break;
    case TC_UI_BOX_CHILD_PREFERRED:
        placement = LayoutPolicy::Preferred;
        break;
    case TC_UI_BOX_CHILD_FLEX:
        placement = LayoutPolicy::Flex;
        break;
    case TC_UI_BOX_CHILD_STRETCH:
        placement = LayoutPolicy::Stretch;
        break;
    default:
        return report_error(__func__, "invalid child layout policy");
    }
    BoxLayout* parent = resolve<BoxLayout>(box, __func__);
    tc_widget* body = resolve(child, __func__);
    if (!parent || !body)
        return false;
    return guard(__func__, false, [&] {
        parent->add_child(child.handle, placement, value);
        return tc_widget_parent(body) == parent->c_widget();
    });
}

bool tc_ui_box_set_spacing(tc_widget_ref box, float spacing) {
    if (!std::isfinite(spacing) || spacing < 0.0f)
        return report_error(__func__, "spacing must be finite and nonnegative");
    BoxLayout* widget = resolve<BoxLayout>(box, __func__);
    if (!widget)
        return false;
    widget->set_spacing(spacing);
    return true;
}

bool tc_ui_button_set_text(tc_widget_ref button, const char* text) {
    return set_text<Button>(button, __func__, text);
}

bool tc_ui_label_set_text(tc_widget_ref label, const char* text) {
    return set_text<Label>(label, __func__, text);
}

size_t tc_ui_button_connect_clicked(tc_widget_ref button,
                                    tc_ui_button_clicked_fn callback,
                                    void* userdata,
                                    tc_ui_widget_callback_destroy_fn destroy) {
    return guard(__func__, size_t{0}, [&] {
        auto data = hold_userdata(userdata, destroy);
        if (!callback) {
            report_error("tc_ui_button_connect_clicked", "callback must not be null");
            return size_t{0};
        }
        Button* widget = resolve<Button>(button, "tc_ui_button_connect_clicked");
        if (!widget)
            return size_t{0};
        return widget->clicked().connect([callback, data = std::move(data)](Button&) { callback(data.get()); });
    });
}

bool tc_ui_button_disconnect_clicked(tc_widget_ref button, size_t connection) {
    Button* widget = resolve<Button>(button, __func__);
    return widget &&
           (widget->clicked().disconnect(connection) || report_error(__func__, "no such callback connection"));
}

bool tc_ui_scene_view_set_pointer_handler(tc_widget_ref view,
                                          tc_ui_scene_view_pointer_fn callback,
                                          void* userdata,
                                          tc_ui_widget_callback_destroy_fn destroy) {
    return guard(__func__, false, [&] {
        auto data = hold_userdata(userdata, destroy);
        SceneView* widget = resolve<SceneView>(view, "tc_ui_scene_view_set_pointer_handler");
        if (!widget)
            return false;
        if (callback) {
            widget->set_pointer_handler(
                [callback, data = std::move(data)](SceneView&, tc_ui_point world, const tc_ui_pointer_event& event) {
                    auto active = data;
                    return callback(active.get(), world.x, world.y, &event);
                });
        } else {
            widget->set_pointer_handler({});
        }
        return true;
    });
}

bool tc_ui_scene_view_set_navigation_enabled(tc_widget_ref view, bool enabled) {
    SceneView* widget = resolve<SceneView>(view, __func__);
    if (!widget)
        return false;
    widget->set_navigation_enabled(enabled);
    return true;
}

bool tc_ui_scene_view_set_grid_visible(tc_widget_ref view, bool visible) {
    SceneView* widget = resolve<SceneView>(view, __func__);
    if (!widget)
        return false;
    widget->set_show_grid(visible);
    return true;
}
