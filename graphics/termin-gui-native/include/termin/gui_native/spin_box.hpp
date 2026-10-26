#pragma once

#include <string>
#include <cstdint>
#include <limits>

#include <termin/gui_native/native_widget.hpp>
#include <termin/gui_native/signal.hpp>

namespace termin::gui_native {
    class SpinBox : public NativeWidget {
    private:
        double value_ = 0.0;
        double min_value_ = -1000000000.0;
        double max_value_ = 1000000000.0;
        double step_ = 1.0;
        bool integer_mode_ = false;
        int64_t integer_value_ = 0;
        int64_t integer_min_ = std::numeric_limits<int64_t>::min();
        int64_t integer_max_ = std::numeric_limits<int64_t>::max();
        int64_t integer_step_ = 1;
        int decimals_ = 2;
        bool editing_ = false;
        std::string edit_text_;
        size_t caret_ = 0;
        size_t selection_anchor_ = SIZE_MAX;
        bool selecting_ = false;
        float button_width_ = 18.0f;
        Signal<SpinBox&, double> changed_;
        Signal<SpinBox&, int64_t> integer_changed_;

    public:
        explicit SpinBox(double value = 0.0);
        double value() const {
            return integer_mode_ ? static_cast<double>(integer_value_) : value_;
        }
        double min_value() const {
            return integer_mode_ ? static_cast<double>(integer_min_) : min_value_;
        }
        double max_value() const {
            return integer_mode_ ? static_cast<double>(integer_max_) : max_value_;
        }
        double step() const {
            return integer_mode_ ? static_cast<double>(integer_step_) : step_;
        }
        int decimals() const {
            return decimals_;
        }
        bool editing() const {
            return editing_;
        }
        const std::string& edit_text() const {
            return edit_text_;
        }
        size_t caret() const {
            return caret_;
        }
        bool has_selection() const;
        size_t selection_start() const;
        size_t selection_end() const;
        std::string selected_text() const;
        void set_value(double value);
        void set_range(double min_value, double max_value);
        void set_step(double step);
        // Exact signed 64-bit mode. Integer edits use integer_changed() and never
        // travel through the floating-point signal or parsing/storage path.
        bool integer_mode() const { return integer_mode_; }
        int64_t integer_value() const { return integer_value_; }
        void set_integer_value(int64_t value);
        void set_integer_range(int64_t minimum, int64_t maximum);
        void set_integer_step(int64_t step);
        Signal<SpinBox&, int64_t>& integer_changed() { return integer_changed_; }
        void set_decimals(int decimals);
        Signal<SpinBox&, double>& changed() {
            return changed_;
        }
        const Signal<SpinBox&, double>& changed() const {
            return changed_;
        }
        tc_ui_size measure(tc_ui_document_handle document, tc_ui_constraints constraints) override;
        void paint(tc_ui_document_handle document, tc_ui_paint_context* context) override;
        tc_ui_event_result pointer_event(tc_ui_document_handle document, const tc_ui_pointer_event* event) override;
        tc_ui_event_result key_event(tc_ui_document_handle document, const tc_ui_key_event* event) override;
        tc_ui_event_result text_event(tc_ui_document_handle document, const tc_ui_text_event* event) override;
        void focus_event(tc_ui_document_handle document, bool focused) override;

    private:
        std::string formatted_value() const;
        std::string editable_value() const;
        void step_value(bool increase);
        void begin_edit();
        void commit_edit();
        void cancel_edit();
        tc_ui_rect up_button_rect() const;
        tc_ui_rect down_button_rect() const;
        tc_ui_rect text_clip_rect(tc_ui_document_handle document) const;
        size_t caret_from_content_x(tc_ui_document_handle document, float content_x) const;
        float prefix_width(tc_ui_document_handle document, size_t offset, float font_size) const;
        void move_caret(size_t next, bool extend_selection);
        bool delete_selection();
        void replace_selection(std::string_view text);
    };
} // namespace termin::gui_native
