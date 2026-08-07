#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include <termin/entity/component.hpp>
#include <termin/entity/input_handler.hpp>
#include <termin/export.hpp>
#include <termin/gui_native/ui_document_asset.hpp>
#include <termin/input/tc_world_pointer_surface.h>

extern "C" {
#include <core/tc_input_platform_services.h>
}

namespace termin {

class ENTITY_API UIComponent final : public CxxComponent, public InputHandler {
public:
    UIComponent();
    explicit UIComponent(int priority);
    ~UIComponent() override;

    UIComponent(const UIComponent&) = delete;
    UIComponent& operator=(const UIComponent&) = delete;

    static void register_type();

    std::string ui_layout_uuid() const { return ui_layout_.uuid(); }
    bool set_ui_layout_uuid(const std::string& uuid);
    gui_native::TcUiDocumentAsset ui_layout() const { return ui_layout_; }

    int priority() const { return priority_; }
    void set_priority(int value);

    std::uint32_t input_source_mask() const {
        return static_cast<std::uint32_t>(input_source_mask_);
    }
    void set_input_source_mask_value(std::uint32_t value);

    gui_native::TcDocument document() const;
    bool has_document() const;
    bool reload_document();
    void clear_document();
    bool dispatch_world_pointer(const tc_world_pointer_event& event);

    tc_value serialize_data() const override;

    void on_added_to_entity() override;
    void on_removed_from_entity() override;
    void on_destroy() override;
    void on_pointer(tc_pointer_event* event) override;
    void on_mouse_button(tc_mouse_button_event* event) override;
    void on_mouse_move(tc_mouse_move_event* event) override;
    void on_scroll(tc_scroll_event* event) override;
    void on_key(tc_key_event* event) override;
    void on_text(tc_text_event* event) override;
    void on_focus_lost(tc_input_focus_event* event) override;

private:
    struct TouchCapture {
        std::uint64_t pointer_id = 0;
        int device = 0;
    };

    void bind_document_services();
    void update_platform_services(
        const tc_input_platform_services* services);
    void sync_platform_state();
    void cancel_interaction(
        tc_ui_pointer_cancel_reason reason,
        bool clear_focus);
    bool physical_to_logical(
        float physical_x,
        float physical_y,
        tc_ui_point& logical);
    void synchronize_presentation_revision();
    bool dispatch_ui_pointer(const tc_ui_pointer_event& event);
    static const char* clipboard_get_text(void* user_data);
    static bool clipboard_set_text(
        void* user_data,
        const char* text,
        size_t byte_length);
    static void cursor_changed(
        void* user_data,
        tc_ui_cursor_intent cursor);

    gui_native::TcUiDocumentAsset ui_layout_;
    int priority_ = 1000;
    int input_source_mask_ = 1;
    std::optional<gui_native::LoadedUiScript> loaded_;
    std::optional<TouchCapture> touch_capture_;
    std::optional<std::uint64_t> world_pointer_owner_;
    tc_input_platform_services platform_services_{};
    std::string clipboard_cache_;
    std::uint64_t input_presentation_revision_ = 0;
    bool text_input_enabled_ = false;
};

} // namespace termin
