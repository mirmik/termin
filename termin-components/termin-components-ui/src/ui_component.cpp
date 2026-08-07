#include <termin/ui/ui_component.hpp>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/ui/tc_scene_ui_document_capability.h>

extern "C" {
#include <core/tc_input_capability.h>
#include <core/tc_input_platform_services.h>
#include <core/tc_input_source.h>
#include <tc_input_event.h>
#include <tc_value.h>
}

#include <vector>

namespace termin {
    namespace {

        bool get_ui_snapshot(tc_component* component, tc_scene_ui_document_snapshot* out_snapshot) {
            if (!component || !out_snapshot) {
                return false;
            }
            CxxComponent* base = CxxComponent::from_tc(component);
            UIComponent* self = dynamic_cast<UIComponent*>(base);
            if (!self) {
                tc::Log::error("[UIComponent] scene_ui_document capability attached to wrong type");
                return false;
            }
            const gui_native::TcDocument document = self->document();
            const gui_native::UiDocumentAssetHandle asset = self->ui_layout().handle();
            out_snapshot->document = document.handle();
            out_snapshot->asset_index = asset.index;
            out_snapshot->asset_generation = asset.generation;
            out_snapshot->priority = self->priority();
            out_snapshot->input_source_mask = self->input_source_mask();
            return document.valid();
        }

        const tc_scene_ui_document_vtable kUiDocumentVtable = {
            .get_snapshot = get_ui_snapshot,
        };

        tc_ui_pointer_event_type ui_pointer_phase(int phase) {
            switch (phase) {
            case TC_POINTER_DOWN:
                return TC_UI_POINTER_DOWN;
            case TC_POINTER_UP:
                return TC_UI_POINTER_UP;
            case TC_POINTER_CANCEL:
                return TC_UI_POINTER_CANCEL;
            case TC_POINTER_MOVE:
            default:
                return TC_UI_POINTER_MOVE;
            }
        }

        tc_input_cursor input_cursor(tc_ui_cursor_intent cursor) {
            switch (cursor) {
            case TC_UI_CURSOR_TEXT:
                return TC_INPUT_CURSOR_TEXT;
            case TC_UI_CURSOR_HAND:
                return TC_INPUT_CURSOR_HAND;
            case TC_UI_CURSOR_CROSSHAIR:
                return TC_INPUT_CURSOR_CROSSHAIR;
            case TC_UI_CURSOR_MOVE:
                return TC_INPUT_CURSOR_MOVE;
            case TC_UI_CURSOR_RESIZE_HORIZONTAL:
                return TC_INPUT_CURSOR_RESIZE_HORIZONTAL;
            case TC_UI_CURSOR_RESIZE_VERTICAL:
                return TC_INPUT_CURSOR_RESIZE_VERTICAL;
            case TC_UI_CURSOR_RESIZE_NWSE:
                return TC_INPUT_CURSOR_RESIZE_NWSE;
            case TC_UI_CURSOR_RESIZE_NESW:
                return TC_INPUT_CURSOR_RESIZE_NESW;
            case TC_UI_CURSOR_INHERIT:
            case TC_UI_CURSOR_DEFAULT:
            default:
                return TC_INPUT_CURSOR_DEFAULT;
            }
        }

    } // namespace

    UIComponent::UIComponent()
        : UIComponent(1000) {}

    UIComponent::UIComponent(int priority)
        : CxxComponent("UIComponent") {
        install_input_vtable(&_c);
        if (!tc_scene_ui_document_capability_attach(&_c, &kUiDocumentVtable, this)) {
            tc::Log::error("[UIComponent] failed to attach scene_ui_document capability");
        }
        set_priority(priority);
        set_input_source_mask_value(TC_INPUT_SOURCE_RUNTIME);
    }

    UIComponent::~UIComponent() {
        clear_document();
    }

    void UIComponent::register_type() {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<UIComponent>("UIComponent", "termin-components-ui", "CxxComponent");
        descriptor.category("UI");
        descriptor.capability(tc_scene_ui_document_capability_id());
        descriptor.capability(tc_input_capability_id());
        auto& inspect = descriptor.inspect();
        inspect.add_with_callbacks<UIComponent, gui_native::TcUiDocumentAsset>(
            "UIComponent",
            "ui_layout",
            "UI Layout",
            "ui_document",
            [](UIComponent* self) -> gui_native::TcUiDocumentAsset& { return self->ui_layout_; },
            [](UIComponent* self, const gui_native::TcUiDocumentAsset& value) {
                if (!value.valid()) {
                    self->set_ui_layout_uuid({});
                } else {
                    self->set_ui_layout_uuid(value.uuid());
                }
            });
        inspect.add_with_callbacks<UIComponent, int>(
            "UIComponent",
            "priority",
            "Priority",
            "int",
            [](UIComponent* self) -> int& { return self->priority_; },
            [](UIComponent* self, const int& value) { self->set_priority(value); });
        inspect.add_with_callbacks<UIComponent, int>(
            "UIComponent",
            "input_source_mask",
            "Input Source Mask",
            "int",
            [](UIComponent* self) -> int& { return self->input_source_mask_; },
            [](UIComponent* self, const int& value) {
                if (value < 0) {
                    tc::Log::error("[UIComponent] input source mask must not be negative");
                    return;
                }
                self->set_input_source_mask_value(static_cast<std::uint32_t>(value));
            });
        (void)descriptor.commit();
    }

    bool UIComponent::set_ui_layout_uuid(const std::string& uuid) {
        if (uuid.empty()) {
            ui_layout_ = {};
            clear_document();
            return true;
        }
        gui_native::TcUiDocumentAsset asset = gui_native::TcUiDocumentAsset::from_uuid(uuid);
        if (!asset.valid()) {
            tc::Log::error("[UIComponent] native UI document asset is not registered: uuid='%s'", uuid.c_str());
            return false;
        }

        try {
            tc_ui_presentation_metrics previous_metrics{};
            const gui_native::TcDocument previous = document();
            const bool preserve_metrics = previous.valid() && previous.has_presentation_metrics() &&
                                          previous.presentation_metrics(previous_metrics);
            gui_native::LoadedUiScript replacement = asset.instantiate();
            if (preserve_metrics && !replacement.document().set_presentation_metrics(previous_metrics)) {
                tc::Log::error("[UIComponent] failed to preserve presentation metrics while "
                               "replacing UI asset '%s'",
                               uuid.c_str());
                return false;
            }
            ui_layout_ = asset;
            loaded_ = std::move(replacement);
            bind_document_services();
        } catch (const std::exception& error) {
            tc::Log::error("[UIComponent] failed to instantiate UI asset '%s': %s", uuid.c_str(), error.what());
            return false;
        }
        return true;
    }

    void UIComponent::set_priority(int value) {
        priority_ = value;
        set_input_priority(&_c, value);
        tc_component_set_capability_priority(&_c, tc_scene_ui_document_capability_id(), value);
    }

    void UIComponent::set_input_source_mask_value(std::uint32_t value) {
        constexpr std::uint32_t supported = TC_INPUT_SOURCE_RUNTIME | TC_INPUT_SOURCE_EDITOR;
        if ((value & ~supported) != 0u) {
            tc::Log::error("[UIComponent] unsupported input source mask bits: 0x%x", value & ~supported);
            return;
        }
        input_source_mask_ = static_cast<int>(value);
        set_input_source_mask(&_c, value);
    }

    gui_native::TcDocument UIComponent::document() const {
        return loaded_ ? loaded_->document() : gui_native::TcDocument{};
    }

    bool UIComponent::has_document() const {
        return loaded_ && !loaded_->closed() && loaded_->document().valid();
    }

    bool UIComponent::reload_document() {
        if (!loaded_) {
            return false;
        }
        if (!ui_layout_.valid()) {
            tc::Log::error("[UIComponent] cannot reload a stale native UI asset handle");
            return false;
        }
        const gui_native::TcUiDocumentAsset asset = ui_layout();
        try {
            tc_ui_presentation_metrics previous_metrics{};
            const gui_native::TcDocument previous = document();
            const bool preserve_metrics = previous.valid() && previous.has_presentation_metrics() &&
                                          previous.presentation_metrics(previous_metrics);
            gui_native::LoadedUiScript replacement = asset.reload_instance(*loaded_);
            if (preserve_metrics && !replacement.document().set_presentation_metrics(previous_metrics)) {
                tc::Log::error("[UIComponent] failed to preserve presentation metrics while "
                               "reloading UI asset '%s'",
                               ui_layout_uuid().c_str());
                return false;
            }
            loaded_ = std::move(replacement);
            bind_document_services();
            return true;
        } catch (const std::exception& error) {
            tc::Log::error("[UIComponent] failed to reload UI asset '%s': %s", ui_layout_uuid().c_str(), error.what());
            return false;
        }
    }

    void UIComponent::clear_document() {
        cancel_interaction(TC_UI_POINTER_CANCEL_EXPLICIT, true);
        loaded_.reset();
    }

    tc_value UIComponent::serialize_data() const {
        tc_value data = CxxComponent::serialize_data();
        if (data.type == TC_VALUE_DICT && ui_layout_.valid()) {
            const std::string uuid = ui_layout_.uuid();
            tc_value reference = tc_value_dict_new();
            tc_value_dict_set(&reference, "type", tc_value_string("uuid"));
            tc_value_dict_set(&reference, "kind", tc_value_string("ui_document"));
            tc_value_dict_set(&reference, "role", tc_value_string("ui_document"));
            tc_value_dict_set(&reference, "uuid", tc_value_string(uuid.c_str()));
            const auto asset = ui_layout_.resolve();
            if (asset) {
                tc_value_dict_set(&reference, "name", tc_value_string(asset->name().c_str()));
            }
            tc_value_dict_set(&data, "ui_layout", reference);
        }
        return data;
    }

    void UIComponent::on_added_to_entity() {
        if (!loaded_ && ui_layout_.valid()) {
            try {
                loaded_.emplace(ui_layout_.instantiate());
                bind_document_services();
            } catch (const std::exception& error) {
                tc::Log::error("[UIComponent] failed to restore UI asset '%s' on attach: %s",
                               ui_layout_uuid().c_str(),
                               error.what());
            }
        }
    }

    void UIComponent::on_removed_from_entity() {
        clear_document();
    }

    void UIComponent::on_destroy() {
        clear_document();
    }

    void UIComponent::bind_document_services() {
        const gui_native::TcDocument current = document();
        if (!current.valid())
            return;
        current.set_clipboard(&UIComponent::clipboard_get_text, &UIComponent::clipboard_set_text, this);
        current.set_cursor_changed_callback(&UIComponent::cursor_changed, this);
        input_presentation_revision_ = current.presentation_revision();
        sync_platform_state();
    }

    void UIComponent::update_platform_services(const tc_input_platform_services* services) {
        platform_services_ = services ? *services : tc_input_platform_services{};
    }

    void UIComponent::sync_platform_state() {
        const gui_native::TcDocument current = document();
        const bool wants_text = current.valid() && !tc_widget_handle_is_invalid(current.focused_widget());
        if (platform_services_.set_text_input_enabled && wants_text != text_input_enabled_) {
            platform_services_.set_text_input_enabled(platform_services_.userdata, wants_text);
        }
        text_input_enabled_ = wants_text;

        if (platform_services_.set_cursor) {
            const tc_ui_cursor_intent cursor = current.valid() ? current.cursor_intent() : TC_UI_CURSOR_DEFAULT;
            platform_services_.set_cursor(platform_services_.userdata, input_cursor(cursor));
        }
    }

    void UIComponent::cancel_interaction(tc_ui_pointer_cancel_reason reason, bool clear_focus) {
        const gui_native::TcDocument current = document();
        if (current.valid()) {
            current.cancel_pointer_interaction(reason);
            if (clear_focus) {
                const tc_widget_handle focused = current.focused_widget();
                if (!tc_widget_handle_is_invalid(focused)) {
                    tc_ui_document_clear_focus(current.handle(), focused);
                }
            }
        }
        touch_capture_.reset();
        world_pointer_owner_.reset();
        sync_platform_state();
    }

    bool UIComponent::dispatch_ui_pointer(const tc_ui_pointer_event& event) {
        const gui_native::TcDocument current = document();
        if (!current.valid())
            return false;
        const bool handled = current.dispatch_pointer_event(event) == TC_UI_EVENT_HANDLED;
        sync_platform_state();
        return handled;
    }

    void UIComponent::synchronize_presentation_revision() {
        const gui_native::TcDocument current = document();
        if (!current.valid()) {
            input_presentation_revision_ = 0;
            touch_capture_.reset();
            world_pointer_owner_.reset();
            return;
        }
        const std::uint64_t revision = current.presentation_revision();
        if (revision != input_presentation_revision_) {
            touch_capture_.reset();
            world_pointer_owner_.reset();
            input_presentation_revision_ = revision;
        }
    }

    bool UIComponent::dispatch_world_pointer(const tc_world_pointer_event& event) {
        if (!has_document())
            return false;
        synchronize_presentation_revision();

        if (world_pointer_owner_ && *world_pointer_owner_ != event.pointer_id) {
            return false;
        }
        if (!world_pointer_owner_) {
            if (event.phase == TC_WORLD_POINTER_LEAVE || event.phase == TC_WORLD_POINTER_CANCEL) {
                return false;
            }
            world_pointer_owner_ = event.pointer_id;
        }

        tc_ui_pointer_event ui_event{};
        switch (event.phase) {
        case TC_WORLD_POINTER_DOWN:
            ui_event.type = TC_UI_POINTER_DOWN;
            ui_event.click_count = 1u;
            break;
        case TC_WORLD_POINTER_UP:
            ui_event.type = TC_UI_POINTER_UP;
            break;
        case TC_WORLD_POINTER_LEAVE:
            ui_event.type = TC_UI_POINTER_LEAVE;
            break;
        case TC_WORLD_POINTER_CANCEL:
            ui_event.type = TC_UI_POINTER_CANCEL;
            ui_event.cancel_reason = TC_UI_POINTER_CANCEL_HOST_CAPTURE_LOST;
            break;
        case TC_WORLD_POINTER_MOVE:
        default:
            ui_event.type = TC_UI_POINTER_MOVE;
            break;
        }
        ui_event.button = TC_MOUSE_BUTTON_LEFT;

        if (ui_event.type != TC_UI_POINTER_CANCEL && ui_event.type != TC_UI_POINTER_LEAVE) {
            tc_ui_presentation_metrics metrics{};
            const gui_native::TcDocument current = document();
            if (!current.presentation_metrics(metrics)) {
                tc::Log::error("[UIComponent] cannot dispatch world pointer before "
                               "presentation metrics are published");
                return false;
            }
            tc_ui_point logical{};
            if (!physical_to_logical(static_cast<float>(event.u * metrics.physical_extent.width),
                                     static_cast<float>(event.v * metrics.physical_extent.height),
                                     logical)) {
                return false;
            }
            ui_event.x = logical.x;
            ui_event.y = logical.y;
        }

        const bool handled = dispatch_ui_pointer(ui_event);
        if (event.phase == TC_WORLD_POINTER_UP || event.phase == TC_WORLD_POINTER_LEAVE ||
            event.phase == TC_WORLD_POINTER_CANCEL) {
            world_pointer_owner_.reset();
        }
        return handled;
    }

    bool UIComponent::physical_to_logical(float physical_x, float physical_y, tc_ui_point& logical) {
        const gui_native::TcDocument current = document();
        synchronize_presentation_revision();
        tc_ui_presentation_metrics metrics{};
        if (!current.valid() || !current.presentation_metrics(metrics)) {
            tc::Log::error("[UIComponent] cannot dispatch pointer input before presentation "
                           "metrics are published");
            return false;
        }
        return tc_ui_presentation_metrics_physical_to_logical_point(
            &metrics, tc_ui_point{physical_x, physical_y}, &logical);
    }

    void UIComponent::on_pointer(tc_pointer_event* event) {
        if (!event || !has_document())
            return;
        update_platform_services(event->platform_services);
        synchronize_presentation_revision();

        const bool is_touch = event->device == TC_POINTER_DEVICE_TOUCH;
        if (is_touch && touch_capture_ &&
            (touch_capture_->pointer_id != event->pointer_id || touch_capture_->device != event->device)) {
            return;
        }

        tc_ui_pointer_event ui_event{};
        ui_event.type = ui_pointer_phase(event->phase);
        tc_ui_point logical{};
        if (!physical_to_logical(static_cast<float>(event->x), static_cast<float>(event->y), logical)) {
            return;
        }
        ui_event.x = logical.x;
        ui_event.y = logical.y;
        ui_event.button = TC_MOUSE_BUTTON_LEFT;
        ui_event.click_count = event->phase == TC_POINTER_DOWN ? 1u : 0u;
        ui_event.cancel_reason = TC_UI_POINTER_CANCEL_EXPLICIT;

        const bool handled = dispatch_ui_pointer(ui_event);
        if (is_touch && event->phase == TC_POINTER_DOWN && handled) {
            touch_capture_ = TouchCapture{event->pointer_id, event->device};
        }
        const bool claimed = is_touch && touch_capture_ && touch_capture_->pointer_id == event->pointer_id &&
                             touch_capture_->device == event->device;
        event->handled = event->handled || handled || claimed;
        if (claimed && (event->phase == TC_POINTER_UP || event->phase == TC_POINTER_CANCEL)) {
            touch_capture_.reset();
        }
    }

    void UIComponent::on_mouse_button(tc_mouse_button_event* event) {
        if (!event || !has_document())
            return;
        update_platform_services(event->platform_services);
        tc_ui_pointer_event ui_event{};
        ui_event.type = event->action == TC_ACTION_RELEASE ? TC_UI_POINTER_UP : TC_UI_POINTER_DOWN;
        tc_ui_point logical{};
        if (!physical_to_logical(static_cast<float>(event->x), static_cast<float>(event->y), logical)) {
            return;
        }
        ui_event.x = logical.x;
        ui_event.y = logical.y;
        ui_event.button = event->button;
        ui_event.click_count = event->click_count;
        ui_event.modifiers = event->mods;
        event->handled = event->handled || dispatch_ui_pointer(ui_event);
    }

    void UIComponent::on_mouse_move(tc_mouse_move_event* event) {
        if (!event || !has_document())
            return;
        update_platform_services(event->platform_services);
        tc_ui_pointer_event ui_event{};
        ui_event.type = TC_UI_POINTER_MOVE;
        tc_ui_point logical{};
        if (!physical_to_logical(static_cast<float>(event->x), static_cast<float>(event->y), logical)) {
            return;
        }
        ui_event.x = logical.x;
        ui_event.y = logical.y;
        event->handled = event->handled || dispatch_ui_pointer(ui_event);
    }

    void UIComponent::on_scroll(tc_scroll_event* event) {
        if (!event || !has_document())
            return;
        update_platform_services(event->platform_services);
        tc_ui_pointer_event ui_event{};
        ui_event.type = TC_UI_POINTER_WHEEL;
        tc_ui_point logical{};
        if (!physical_to_logical(static_cast<float>(event->x), static_cast<float>(event->y), logical)) {
            return;
        }
        ui_event.x = logical.x;
        ui_event.y = logical.y;
        ui_event.wheel_x = static_cast<float>(event->xoffset);
        ui_event.wheel_y = static_cast<float>(event->yoffset);
        ui_event.modifiers = event->mods;
        event->handled = event->handled || dispatch_ui_pointer(ui_event);
    }

    void UIComponent::on_key(tc_key_event* event) {
        if (!event || !has_document())
            return;
        update_platform_services(event->platform_services);
        tc_ui_key_event ui_event{};
        ui_event.type = event->action == TC_ACTION_RELEASE ? TC_UI_KEY_UP : TC_UI_KEY_DOWN;
        ui_event.key = event->key;
        ui_event.scancode = event->scancode;
        ui_event.modifiers = event->mods;
        ui_event.repeat = event->action == TC_ACTION_REPEAT;
        event->handled = event->handled || document().dispatch_key_event(ui_event) == TC_UI_EVENT_HANDLED;
        sync_platform_state();
    }

    void UIComponent::on_text(tc_text_event* event) {
        if (!event || !event->text_utf8 || !has_document())
            return;
        update_platform_services(event->platform_services);
        const tc_ui_text_event ui_event{event->text_utf8};
        event->handled = event->handled || document().dispatch_text_event(ui_event) == TC_UI_EVENT_HANDLED;
        sync_platform_state();
    }

    void UIComponent::on_focus_lost(tc_input_focus_event* event) {
        if (event)
            update_platform_services(event->platform_services);
        cancel_interaction(TC_UI_POINTER_CANCEL_WINDOW_FOCUS_LOST, true);
    }

    const char* UIComponent::clipboard_get_text(void* user_data) {
        UIComponent* self = static_cast<UIComponent*>(user_data);
        if (!self)
            return "";
        const auto callback = self->platform_services_.clipboard_text;
        if (!callback)
            return self->clipboard_cache_.c_str();
        const size_t required = callback(self->platform_services_.userdata, nullptr, 0);
        std::vector<char> buffer(required + 1, '\0');
        const size_t actual = callback(self->platform_services_.userdata, buffer.data(), buffer.size());
        if (actual > required) {
            tc::Log::error("[UIComponent] clipboard grew during synchronous read");
            return self->clipboard_cache_.c_str();
        }
        self->clipboard_cache_.assign(buffer.data(), actual);
        return self->clipboard_cache_.c_str();
    }

    bool UIComponent::clipboard_set_text(void* user_data, const char* text, size_t byte_length) {
        UIComponent* self = static_cast<UIComponent*>(user_data);
        if (!self || (!text && byte_length != 0))
            return false;
        self->clipboard_cache_.assign(text ? text : "", byte_length);
        const auto callback = self->platform_services_.set_clipboard_text;
        return !callback || callback(self->platform_services_.userdata,
                                     self->clipboard_cache_.data(),
                                     self->clipboard_cache_.size());
    }

    void UIComponent::cursor_changed(void* user_data, tc_ui_cursor_intent cursor) {
        UIComponent* self = static_cast<UIComponent*>(user_data);
        if (!self || !self->platform_services_.set_cursor)
            return;
        self->platform_services_.set_cursor(self->platform_services_.userdata, input_cursor(cursor));
    }

} // namespace termin
