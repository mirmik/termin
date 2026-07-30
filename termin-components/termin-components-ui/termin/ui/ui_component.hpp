#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include <termin/entity/component.hpp>
#include <termin/entity/input_handler.hpp>
#include <termin/export.hpp>
#include <termin/gui_native/ui_document_asset.hpp>

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

    tc_value serialize_data() const override;

    void on_added_to_entity() override;
    void on_removed_from_entity() override;
    void on_destroy() override;

private:
    gui_native::TcUiDocumentAsset ui_layout_;
    int priority_ = 1000;
    int input_source_mask_ = 1;
    std::optional<gui_native::LoadedUiScript> loaded_;
};

} // namespace termin
