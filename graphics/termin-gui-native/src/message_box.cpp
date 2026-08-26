#include "widgets_internal.hpp"

#include <algorithm>

namespace termin::gui_native {

    namespace {

        constexpr float kViewportMargin = 16.0f;
        constexpr float kMaximumDialogWidth = 720.0f;
        constexpr float kDialogHorizontalPadding = 32.0f;
        constexpr float kMessageRowReservedWidth = 54.0f;
        constexpr float kDialogNonContentHeight = 106.0f;

    } // namespace

    MessageBox::MessageBox(std::string title, std::string message, MessageBoxKind kind)
        : Dialog(std::move(title)),
          message_(std::move(message)),
          kind_(kind) {
        if (kind_ == MessageBoxKind::Question) {
            set_actions({
                DialogAction{"yes", "Yes", true, false},
                DialogAction{"no", "No", false, true},
            });
        } else {
            set_actions({DialogAction{"ok", "OK", true, false}});
        }
    }

    bool MessageBox::ensure_content(tc_ui_document_handle document) {
        if (!tc_widget_handle_is_invalid(message_content_handle_) &&
            tc_ui_document_is_alive(document, message_content_handle_)) {
            return true;
        }
        const char* icon = "ℹ";
        SrgbColor color{0.30f, 0.60f, 0.90f, 1.0f};
        if (kind_ == MessageBoxKind::Warning) {
            icon = "⚠";
            color = SrgbColor{0.90f, 0.70f, 0.20f, 1.0f};
        } else if (kind_ == MessageBoxKind::Error) {
            icon = "✖";
            color = SrgbColor{0.90f, 0.30f, 0.30f, 1.0f};
        } else if (kind_ == MessageBoxKind::Question) {
            icon = "?";
            color = SrgbColor{0.30f, 0.80f, 0.50f, 1.0f};
        }
        auto row = std::make_unique<HStack>("message-box-content");
        row->set_spacing(14.0f);
        auto scroll = std::make_unique<ScrollArea>("message-box-scroll");
        scroll->set_scroll_axes(false, true);
        scroll->set_scrollbar_policy(ScrollBarPolicy::Hidden, ScrollBarPolicy::Auto);
        auto icon_label = std::make_unique<Label>(icon, 28.0f, color);
        auto message_label = std::make_unique<Label>(message_);
        message_label->set_wrap_mode(TextWrapMode::Character);
        const tc_widget_handle scroll_handle =
            tc_ui_document_adopt_widget(document, scroll->c_widget(), &Widget::delete_owned_widget);
        const tc_widget_handle row_handle =
            tc_ui_document_adopt_widget(document, row->c_widget(), &Widget::delete_owned_widget);
        const tc_widget_handle icon_handle =
            tc_ui_document_adopt_widget(document, icon_label->c_widget(), &Widget::delete_owned_widget);
        const tc_widget_handle message_handle =
            tc_ui_document_adopt_widget(document, message_label->c_widget(), &Widget::delete_owned_widget);
        if (tc_widget_handle_is_invalid(scroll_handle) || tc_widget_handle_is_invalid(row_handle) ||
            tc_widget_handle_is_invalid(icon_handle) ||
            tc_widget_handle_is_invalid(message_handle)) {
            tc_log_error("[termin-gui-native] MessageBox failed to adopt content widgets");
            if (!tc_widget_handle_is_invalid(scroll_handle))
                tc_ui_document_destroy_widget_recursive(document, scroll_handle);
            if (!tc_widget_handle_is_invalid(row_handle))
                tc_ui_document_destroy_widget_recursive(document, row_handle);
            if (!tc_widget_handle_is_invalid(icon_handle))
                tc_ui_document_destroy_widget_recursive(document, icon_handle);
            if (!tc_widget_handle_is_invalid(message_handle))
                tc_ui_document_destroy_widget_recursive(document, message_handle);
            return false;
        }
        ScrollArea* scroll_body = scroll.release();
        HStack* row_body = row.release();
        Label* icon_body = icon_label.release();
        Label* message_body = message_label.release();
        row_body->add_preferred_child(*icon_body);
        row_body->add_child(*message_body);
        scroll_body->set_content(*row_body);
        message_content_handle_ = scroll_handle;
        message_row_handle_ = row_handle;
        message_label_handle_ = message_handle;
        set_content(*scroll_body);
        return true;
    }

    bool MessageBox::configure_content(tc_ui_document_handle document, tc_ui_rect viewport) {
        auto* scroll = dynamic_cast<ScrollArea*>(
            detail::native_widget_body(tc_ui_document_resolve_widget(document, message_content_handle_)));
        auto* message_label = dynamic_cast<Label*>(
            detail::native_widget_body(tc_ui_document_resolve_widget(document, message_label_handle_)));
        tc_widget* row = tc_ui_document_resolve_widget(document, message_row_handle_);
        if (!scroll || !message_label || !row) {
            tc_log_error("[termin-gui-native] MessageBox content is incomplete");
            return false;
        }

        viewport_max_size_ = tc_ui_size{
            std::min(kMaximumDialogWidth, std::max(0.0f, viewport.width - kViewportMargin * 2.0f)),
            std::max(0.0f, viewport.height - kViewportMargin * 2.0f),
        };
        const float content_width = std::max(0.0f, viewport_max_size_.width - kDialogHorizontalPadding);
        const float message_width = std::max(1.0f, content_width - kMessageRowReservedWidth);
        const float content_height = std::max(0.0f, viewport_max_size_.height - kDialogNonContentHeight);
        message_label->set_max_size(tc_ui_size{message_width, 0.0f});

        tc_ui_constraints row_constraints{};
        row_constraints.max_size = tc_ui_size{content_width, detail::kHuge};
        const tc_ui_size row_size = detail::measure_widget(row, document, row_constraints);
        scroll->set_preferred_size(tc_ui_size{
            std::min(content_width, row_size.width),
            std::min(content_height, row_size.height),
        });
        scroll->set_max_size(tc_ui_size{content_width, content_height});
        return true;
    }

    bool MessageBox::show(tc_ui_document_handle document, tc_ui_rect viewport) {
        return ensure_content(document) && configure_content(document, viewport) && Dialog::show(document, viewport);
    }

    tc_ui_size MessageBox::measure(tc_ui_document_handle document, tc_ui_constraints constraints) {
        if (viewport_max_size_.width > 0.0f)
            constraints.max_size.width = std::min(constraints.max_size.width, viewport_max_size_.width);
        if (viewport_max_size_.height > 0.0f)
            constraints.max_size.height = std::min(constraints.max_size.height, viewport_max_size_.height);
        return Dialog::measure(document, constraints);
    }

} // namespace termin::gui_native
