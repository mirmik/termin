#include <termin/ui/ui_component.hpp>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/ui/tc_scene_ui_document_capability.h>

extern "C" {
#include <core/tc_input_source.h>
#include <core/tc_input_capability.h>
#include <tc_value.h>
}

namespace termin {
namespace {

bool get_ui_snapshot(
    tc_component* component,
    tc_scene_ui_document_snapshot* out_snapshot
) {
    if (!component || !out_snapshot) {
        return false;
    }
    CxxComponent* base = CxxComponent::from_tc(component);
    UIComponent* self = dynamic_cast<UIComponent*>(base);
    if (!self) {
        tc::Log::error(
            "[UIComponent] scene_ui_document capability attached to wrong type");
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

} // namespace

UIComponent::UIComponent()
    : UIComponent(1000) {}

UIComponent::UIComponent(int priority)
    : CxxComponent("UIComponent") {
    install_input_vtable(&_c);
    if (!tc_scene_ui_document_capability_attach(
            &_c, &kUiDocumentVtable, this)) {
        tc::Log::error(
            "[UIComponent] failed to attach scene_ui_document capability");
    }
    set_priority(priority);
    set_input_source_mask_value(TC_INPUT_SOURCE_RUNTIME);
}

UIComponent::~UIComponent() {
    clear_document();
}

void UIComponent::register_type() {
    auto descriptor = ComponentTypeDescriptorBuilder::native<UIComponent>(
        "UIComponent", "termin-components-ui", "CxxComponent");
    descriptor.category("UI");
    descriptor.capability(tc_scene_ui_document_capability_id());
    descriptor.capability(tc_input_capability_id());
    auto& inspect = descriptor.inspect();
    inspect.add_with_callbacks<
        UIComponent, gui_native::TcUiDocumentAsset>(
        "UIComponent", "ui_layout", "UI Layout", "ui_document",
        [](UIComponent* self) -> gui_native::TcUiDocumentAsset& {
            return self->ui_layout_;
        },
        [](UIComponent* self,
           const gui_native::TcUiDocumentAsset& value) {
            if (!value.valid()) {
                self->set_ui_layout_uuid({});
            } else {
                self->set_ui_layout_uuid(value.uuid());
            }
        });
    inspect.add_with_callbacks<UIComponent, int>(
        "UIComponent", "priority", "Priority", "int",
        [](UIComponent* self) -> int& { return self->priority_; },
        [](UIComponent* self, const int& value) {
            self->set_priority(value);
        });
    inspect.add_with_callbacks<UIComponent, int>(
        "UIComponent", "input_source_mask", "Input Source Mask", "int",
        [](UIComponent* self) -> int& { return self->input_source_mask_; },
        [](UIComponent* self, const int& value) {
            if (value < 0) {
                tc::Log::error(
                    "[UIComponent] input source mask must not be negative");
                return;
            }
            self->set_input_source_mask_value(
                static_cast<std::uint32_t>(value));
        });
    (void)descriptor.commit();
}

bool UIComponent::set_ui_layout_uuid(const std::string& uuid) {
    if (uuid.empty()) {
        ui_layout_ = {};
        clear_document();
        return true;
    }
    gui_native::TcUiDocumentAsset asset =
        gui_native::TcUiDocumentAsset::from_uuid(uuid);
    if (!asset.valid()) {
        tc::Log::error(
            "[UIComponent] native UI document asset is not registered: uuid='%s'",
            uuid.c_str());
        return false;
    }

    try {
        gui_native::LoadedUiScript replacement = asset.instantiate();
        ui_layout_ = asset;
        loaded_ = std::move(replacement);
    } catch (const std::exception& error) {
        tc::Log::error(
            "[UIComponent] failed to instantiate UI asset '%s': %s",
            uuid.c_str(), error.what());
        return false;
    }
    return true;
}

void UIComponent::set_priority(int value) {
    priority_ = value;
    set_input_priority(&_c, value);
    tc_component_set_capability_priority(
        &_c, tc_scene_ui_document_capability_id(), value);
}

void UIComponent::set_input_source_mask_value(std::uint32_t value) {
    constexpr std::uint32_t supported =
        TC_INPUT_SOURCE_RUNTIME | TC_INPUT_SOURCE_EDITOR;
    if ((value & ~supported) != 0u) {
        tc::Log::error(
            "[UIComponent] unsupported input source mask bits: 0x%x",
            value & ~supported);
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
        tc::Log::error(
            "[UIComponent] cannot reload a stale native UI asset handle");
        return false;
    }
    const gui_native::TcUiDocumentAsset asset = ui_layout();
    try {
        gui_native::LoadedUiScript replacement =
            asset.reload_instance(*loaded_);
        loaded_ = std::move(replacement);
        return true;
    } catch (const std::exception& error) {
        tc::Log::error(
            "[UIComponent] failed to reload UI asset '%s': %s",
            ui_layout_uuid().c_str(), error.what());
        return false;
    }
}

void UIComponent::clear_document() {
    loaded_.reset();
}

tc_value UIComponent::serialize_data() const {
    tc_value data = CxxComponent::serialize_data();
    if (data.type == TC_VALUE_DICT && ui_layout_.valid()) {
        const std::string uuid = ui_layout_.uuid();
        tc_value reference = tc_value_dict_new();
        tc_value_dict_set(&reference, "type", tc_value_string("uuid"));
        tc_value_dict_set(
            &reference, "kind", tc_value_string("ui_document"));
        tc_value_dict_set(
            &reference, "role", tc_value_string("ui_document"));
        tc_value_dict_set(
            &reference, "uuid", tc_value_string(uuid.c_str()));
        const auto asset = ui_layout_.resolve();
        if (asset) {
            tc_value_dict_set(
                &reference, "name", tc_value_string(asset->name().c_str()));
        }
        tc_value_dict_set(&data, "ui_layout", reference);
    }
    return data;
}

void UIComponent::on_added_to_entity() {
    if (!loaded_ && ui_layout_.valid()) {
        try {
            loaded_.emplace(ui_layout_.instantiate());
        } catch (const std::exception& error) {
            tc::Log::error(
                "[UIComponent] failed to restore UI asset '%s' on attach: %s",
                ui_layout_uuid().c_str(), error.what());
        }
    }
}

void UIComponent::on_removed_from_entity() {
    clear_document();
}

void UIComponent::on_destroy() {
    clear_document();
}

} // namespace termin
