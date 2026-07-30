#include "guard_main.h"

GUARD_TEST_MAIN();

#include <string>

#include <core/tc_component.h>
#include <core/tc_input_capability.h>
#include <core/tc_input_source.h>
#include <core/tc_input_component.h>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <termin/entity/unknown_component.hpp>
#include <termin/gui_native/ui_document_asset.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>
#include <termin/ui/tc_scene_ui_document_capability.h>
#include <termin/ui/ui_component.hpp>
#include <tc_input_event.h>

namespace {

constexpr const char* kSource = R"(
uiscript: 2
root:
  type: termin.gui.Panel
  name: root
  background_color: [0.1, 0.2, 0.3, 1]
  children:
    - type: termin.gui.IconButton
      name: action
      icon: A
)";

constexpr const char* kInputSource = R"(
uiscript: 2
root:
  type: termin.gui.OverlayLayout
  name: root
  children:
    - type: termin.gui.IconButton
      name: action
      icon: A
      anchor: top-left
      size: 30
)";

termin::gui_native::TcUiDocumentAsset declare_asset(
    const char* uuid = "ui-component-test"
) {
    return termin::gui_native::TcUiDocumentAsset::declare_source(
        uuid, "Component UI", "UI/component.uiscript", kSource);
}

struct PlatformProbe {
    bool text_input_enabled = false;
    tc_input_cursor cursor = TC_INPUT_CURSOR_DEFAULT;
};

void set_cursor(void* userdata, tc_input_cursor cursor) {
    static_cast<PlatformProbe*>(userdata)->cursor = cursor;
}

void set_text_input_enabled(void* userdata, bool enabled) {
    static_cast<PlatformProbe*>(userdata)->text_input_enabled = enabled;
}

} // namespace

TEST_CASE("UIComponent publishes independent native document snapshots") {
    using namespace termin;
    using namespace termin::gui_native;

    TcUiDocumentAsset::clear_registry_for_tests();
    const TcUiDocumentAsset asset = declare_asset();
    REQUIRE(asset.valid());

    UIComponent first(7);
    UIComponent second(11);
    REQUIRE(first.set_ui_layout_uuid(asset.uuid()));
    REQUIRE(second.set_ui_layout_uuid(asset.uuid()));
    REQUIRE(first.has_document());
    REQUIRE(second.has_document());
    CHECK_FALSE(first.document() == second.document());
    CHECK_EQ(first.priority(), 7);
    CHECK_EQ(
        tc_component_get_input_priority(first.tc_component_ptr()), 7);
    CHECK_EQ(
        tc_component_get_input_source_mask(first.tc_component_ptr()),
        static_cast<uint32_t>(TC_INPUT_SOURCE_RUNTIME));

    tc_scene_ui_document_snapshot snapshot{};
    REQUIRE(tc_scene_ui_document_snapshot_get(
        first.tc_component_ptr(), &snapshot));
    CHECK(tc_ui_document_handle_eq(
        snapshot.document, first.document().handle()));
    CHECK_EQ(snapshot.asset_index, asset.handle().index);
    CHECK_EQ(snapshot.asset_generation, asset.handle().generation);
    CHECK_EQ(snapshot.priority, 7);

    first.set_priority(19);
    first.set_input_source_mask_value(
        TC_INPUT_SOURCE_RUNTIME | TC_INPUT_SOURCE_EDITOR);
    REQUIRE(tc_scene_ui_document_snapshot_get(
        first.tc_component_ptr(), &snapshot));
    CHECK_EQ(snapshot.priority, 19);
    CHECK_EQ(
        snapshot.input_source_mask,
        static_cast<uint32_t>(
            TC_INPUT_SOURCE_RUNTIME | TC_INPUT_SOURCE_EDITOR));
    CHECK_EQ(
        tc_component_get_capability_priority(
            first.tc_component_ptr(),
            tc_scene_ui_document_capability_id()),
        19);
    first.set_input_source_mask_value(1u << 12u);
    CHECK_EQ(
        first.input_source_mask(),
        static_cast<uint32_t>(
            TC_INPUT_SOURCE_RUNTIME | TC_INPUT_SOURCE_EDITOR));

    TcUiDocumentAsset::clear_registry_for_tests();
    CHECK_FALSE(first.ui_layout().valid());
    CHECK(first.has_document());
    CHECK_FALSE(first.reload_document());
}

TEST_CASE("UIComponent asset replacement and failed reload are transactional") {
    using namespace termin;
    using namespace termin::gui_native;

    TcUiDocumentAsset::clear_registry_for_tests();
    TcUiDocumentAsset asset = declare_asset("ui-component-reload");
    REQUIRE(asset.valid());

    UIComponent component;
    REQUIRE(component.set_ui_layout_uuid(asset.uuid()));
    const TcDocument original = component.document();
    const tc_widget_handle original_root =
        tc_ui_document_root_at(original.handle(), 0);

    CHECK_FALSE(asset.reload_source(
        "uiscript: 2\nroot: {type: termin.gui.Missing}\n"));
    CHECK_EQ(asset.revision(), 1u);
    CHECK(component.document() == original);
    CHECK(tc_ui_document_resolve_widget(original.handle(), original_root));

    const std::string replacement =
        std::string(kSource).replace(
            std::string(kSource).find("name: action"),
            std::string("name: action").size(),
            "name: replacement");
    REQUIRE(asset.reload_source(replacement));
    REQUIRE(component.reload_document());
    CHECK(component.document() == original);
    const tc_widget_handle replacement_root =
        tc_ui_document_root_at(original.handle(), 0);
    CHECK_FALSE(tc_widget_handle_eq(original_root, replacement_root));

    component.on_removed_from_entity();
    CHECK_FALSE(component.has_document());
    component.on_added_to_entity();
    CHECK(component.has_document());

    component.clear_document();
    TcUiDocumentAsset::clear_registry_for_tests();
}

TEST_CASE("UIComponent native inspect serialization uses a typed asset ref") {
    using namespace termin;
    using namespace termin::gui_native;

    TcUiDocumentAsset::clear_registry_for_tests();
    const TcUiDocumentAsset asset = declare_asset("ui-component-serialize");
    REQUIRE(asset.valid());
    tc_inspect_kind_core_init();
    tc_inspect_component_adapter_init();
    tc::register_cpp_handle_kind<TcUiDocumentAsset>("ui_document");
    register_builtin_scene_component_types();
    UIComponent::register_type();
    CHECK(tc_component_registry_has_capability(
        "UIComponent", tc_scene_ui_document_capability_id()));
    CHECK(tc_component_registry_has_capability(
        "UIComponent", tc_input_capability_id()));

    tc_component* raw = tc_component_registry_create("UIComponent");
    REQUIRE(raw != nullptr);
    auto* component =
        dynamic_cast<UIComponent*>(CxxComponent::from_tc(raw));
    REQUIRE(component != nullptr);
    REQUIRE(component->set_ui_layout_uuid(asset.uuid()));
    component->set_priority(23);
    component->set_input_source_mask_value(TC_INPUT_SOURCE_EDITOR);

    tc_value data = component->serialize_data();
    REQUIRE(data.type == TC_VALUE_DICT);
    tc_value* ui_layout = tc_value_dict_get(&data, "ui_layout");
    REQUIRE(ui_layout != nullptr);
    REQUIRE(ui_layout->type == TC_VALUE_DICT);
    tc_value* kind = tc_value_dict_get(ui_layout, "kind");
    tc_value* uuid = tc_value_dict_get(ui_layout, "uuid");
    REQUIRE(kind != nullptr);
    REQUIRE(uuid != nullptr);
    CHECK_EQ(std::string(kind->data.s), "ui_document");
    CHECK_EQ(std::string(uuid->data.s), asset.uuid());
    tc_value* priority = tc_value_dict_get(&data, "priority");
    tc_value* input_source_mask =
        tc_value_dict_get(&data, "input_source_mask");
    REQUIRE(priority != nullptr);
    REQUIRE(input_source_mask != nullptr);
    CHECK_EQ(
        priority->data.i,
        static_cast<int64_t>(23));
    CHECK_EQ(
        input_source_mask->data.i,
        static_cast<int64_t>(TC_INPUT_SOURCE_EDITOR));

    UIComponent restored;
    restored.deserialize_data(&data);
    CHECK_EQ(restored.ui_layout_uuid(), asset.uuid());
    CHECK(restored.has_document());
    CHECK_EQ(restored.priority(), 23);
    CHECK_EQ(
        restored.input_source_mask(),
        static_cast<uint32_t>(TC_INPUT_SOURCE_EDITOR));

    tc_value_free(&data);
    delete component;
    TcUiDocumentAsset::clear_registry_for_tests();
}

TEST_CASE("UIComponent handles viewport-local pointer streams and focus teardown") {
    using namespace termin;
    using namespace termin::gui_native;

    TcUiDocumentAsset::clear_registry_for_tests();
    const TcUiDocumentAsset asset = TcUiDocumentAsset::declare_source(
        "ui-component-input",
        "Component Input UI",
        "UI/component-input.uiscript",
        kInputSource);
    UIComponent component;
    REQUIRE(component.set_ui_layout_uuid(asset.uuid()));
    const TcDocument document = component.document();
    document.layout_roots({0.0f, 0.0f, 200.0f, 100.0f});

    tc_widget* root = tc_ui_document_resolve_widget(
        document.handle(), tc_ui_document_root_at(document.handle(), 0));
    REQUIRE(root != nullptr);
    REQUIRE_EQ(tc_widget_child_count(root), 1u);
    tc_widget* button = tc_widget_child_at(root, 0);
    REQUIRE(button != nullptr);
    const tc_ui_rect bounds = tc_widget_bounds(button);
    const double x = bounds.x + bounds.width * 0.5;
    const double y = bounds.y + bounds.height * 0.5;

    PlatformProbe platform;
    const tc_input_platform_services services = {
        .userdata = &platform,
        .clipboard_text = nullptr,
        .set_clipboard_text = nullptr,
        .set_cursor = set_cursor,
        .set_text_input_enabled = set_text_input_enabled,
    };

    tc_pointer_event down;
    tc_pointer_event_init_source(
        &down, TC_VIEWPORT_HANDLE_INVALID,
        17, TC_POINTER_DEVICE_TOUCH, TC_POINTER_DOWN,
        x, y, 0.0, 0.0, 1.0f, TC_INPUT_SOURCE_RUNTIME);
    down.platform_services = &services;
    tc_component_on_pointer(component.tc_component_ptr(), &down);
    REQUIRE(down.handled);
    CHECK_FALSE(tc_widget_handle_is_invalid(document.pointer_capture()));

    tc_pointer_event secondary;
    tc_pointer_event_init_source(
        &secondary, TC_VIEWPORT_HANDLE_INVALID,
        18, TC_POINTER_DEVICE_TOUCH, TC_POINTER_MOVE,
        x, y, 0.0, 0.0, 1.0f, TC_INPUT_SOURCE_RUNTIME);
    secondary.platform_services = &services;
    tc_component_on_pointer(component.tc_component_ptr(), &secondary);
    CHECK_FALSE(secondary.handled);

    tc_pointer_event primary_move;
    tc_pointer_event_init_source(
        &primary_move, TC_VIEWPORT_HANDLE_INVALID,
        17, TC_POINTER_DEVICE_TOUCH, TC_POINTER_MOVE,
        500.0, 500.0, 0.0, 0.0, 1.0f, TC_INPUT_SOURCE_RUNTIME);
    primary_move.platform_services = &services;
    tc_component_on_pointer(component.tc_component_ptr(), &primary_move);
    CHECK(primary_move.handled);

    tc_input_focus_event focus_lost;
    tc_input_focus_event_init_source(
        &focus_lost, TC_VIEWPORT_HANDLE_INVALID, TC_INPUT_SOURCE_RUNTIME);
    focus_lost.platform_services = &services;
    tc_component_on_focus_lost(component.tc_component_ptr(), &focus_lost);
    CHECK(tc_widget_handle_is_invalid(document.pointer_capture()));
    CHECK(tc_widget_handle_is_invalid(document.focused_widget()));
    CHECK_FALSE(platform.text_input_enabled);
    CHECK_EQ(platform.cursor, TC_INPUT_CURSOR_DEFAULT);

    primary_move.handled = false;
    tc_component_on_pointer(component.tc_component_ptr(), &primary_move);
    CHECK_FALSE(primary_move.handled);

    component.clear_document();
    TcUiDocumentAsset::clear_registry_for_tests();
}
