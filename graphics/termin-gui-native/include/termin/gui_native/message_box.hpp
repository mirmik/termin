#pragma once

#include <termin/gui_native/dialog.hpp>

namespace termin::gui_native {

    enum class MessageBoxKind {
        Information,
        Warning,
        Error,
        Question
    };

    class MessageBox final : public Dialog {
    private:
        std::string message_;
        MessageBoxKind kind_ = MessageBoxKind::Information;
        tc_widget_handle message_content_handle_ = tc_widget_handle_invalid();
        tc_widget_handle message_row_handle_ = tc_widget_handle_invalid();
        tc_widget_handle message_label_handle_ = tc_widget_handle_invalid();
        tc_ui_size viewport_max_size_{};

    public:
        MessageBox(std::string title, std::string message, MessageBoxKind kind = MessageBoxKind::Information);

        const std::string& message() const {
            return message_;
        }
        MessageBoxKind kind() const {
            return kind_;
        }
        bool show(tc_ui_document_handle document, tc_ui_rect viewport);
        tc_ui_size measure(tc_ui_document_handle document, tc_ui_constraints constraints) override;

    private:
        bool ensure_content(tc_ui_document_handle document);
        bool configure_content(tc_ui_document_handle document, tc_ui_rect viewport);
    };

} // namespace termin::gui_native
