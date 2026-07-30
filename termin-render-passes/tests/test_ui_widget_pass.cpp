#include "guard_main.h"

GUARD_TEST_MAIN();

#include <cstdint>
#include <string>

#include <core/tc_component.h>
#include <termin/entity/entity.hpp>
#include <termin/gui_native/ui_document_asset.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/ui_widget_pass.hpp>
#include <termin/tc_scene.hpp>
#include <termin/ui/ui_component.hpp>

namespace {

constexpr const char* kSource = R"(
uiscript: 2
root:
  type: termin.gui.Panel
  name: root
  background_color: [0.2, 0.3, 0.4, 1]
)";

termin::UIComponent* make_component(
    termin::Entity entity,
    const termin::gui_native::TcUiDocumentAsset& asset,
    int priority,
    const char* source_id
) {
    auto* component = new termin::UIComponent(priority);
    tc_component_set_source_id(component->tc_component_ptr(), source_id);
    REQUIRE(component->set_ui_layout_uuid(asset.uuid()));
    entity.add_component(component);
    return component;
}

} // namespace

TEST_CASE("UIWidgetPass collects ordered enabled layer-filtered documents") {
    using namespace termin;
    using namespace termin::gui_native;

    TcUiDocumentAsset::clear_registry_for_tests();
    const TcUiDocumentAsset asset = TcUiDocumentAsset::declare_source(
        "ui-widget-pass-contract",
        "UIWidgetPass Contract",
        "UI/widget-pass.uiscript",
        kSource);
    REQUIRE(asset.valid());

    TcSceneRef scene = TcSceneRef::create("ui-widget-pass-contract");
    Entity back_entity = scene.create_entity("Back");
    back_entity.set_layer(0);
    UIComponent* back =
        make_component(back_entity, asset, 5, "ui-back");
    REQUIRE(back->document().set_presentation_metrics(
        tc_ui_presentation_metrics{
            2.0f,
            1.25f,
            tc_ui_size{640.0f, 480.0f},
            tc_ui_insets{0.0f, 24.0f, 0.0f, 16.0f},
        }));

    Entity front_entity = scene.create_entity("Front");
    front_entity.set_layer(1);
    UIComponent* front =
        make_component(front_entity, asset, 20, "ui-front");

    Entity disabled_component_entity =
        scene.create_entity("DisabledComponent");
    UIComponent* disabled_component =
        make_component(
            disabled_component_entity, asset, 1, "ui-disabled-component");
    tc_component_set_enabled(
        disabled_component->tc_component_ptr(), false);

    Entity disabled_entity = scene.create_entity("DisabledEntity");
    disabled_entity.set_enabled(false);
    make_component(disabled_entity, asset, 2, "ui-disabled-entity");

    ExecuteContext ctx;
    ctx.scene = scene;
    ctx.layer_mask = UINT64_C(1) << 0u;
    auto submissions =
        collect_ui_document_submissions(ctx, false);
    REQUIRE_EQ(submissions.size(), 1u);
    CHECK(submissions[0].document == back->document());
    CHECK_EQ(submissions[0].presentation_metrics.density_scale, 2.0f);
    CHECK_EQ(submissions[0].presentation_metrics.font_scale, 1.25f);
    CHECK_EQ(
        submissions[0].presentation_metrics.physical_safe_insets.top,
        24.0f);

    ctx.layer_mask = UINT64_MAX;
    submissions = collect_ui_document_submissions(ctx, false);
    REQUIRE_EQ(submissions.size(), 2u);
    CHECK_EQ(submissions[0].priority, 5);
    CHECK_EQ(submissions[1].priority, 20);
    CHECK(submissions[0].document == back->document());
    CHECK(submissions[1].document == front->document());
    CHECK_EQ(submissions[0].presentation_metrics.density_scale, 2.0f);
    CHECK_FALSE(tc_ui_presentation_metrics_is_valid(
        &submissions[1].presentation_metrics));

    const auto repeated =
        collect_ui_document_submissions(ctx, false);
    REQUIRE_EQ(repeated.size(), submissions.size());
    CHECK_EQ(
        repeated[0].stable_identity,
        submissions[0].stable_identity);
    CHECK_EQ(
        repeated[1].stable_identity,
        submissions[1].stable_identity);

    scene.destroy();
    TcUiDocumentAsset::clear_registry_for_tests();
}

TEST_CASE("UIWidgetPass includes internal hierarchy without duplicates") {
    using namespace termin;
    using namespace termin::gui_native;

    TcUiDocumentAsset::clear_registry_for_tests();
    const TcUiDocumentAsset asset = TcUiDocumentAsset::declare_source(
        "ui-widget-pass-internal",
        "UIWidgetPass Internal",
        "UI/widget-pass-internal.uiscript",
        kSource);
    REQUIRE(asset.valid());

    TcSceneRef scene = TcSceneRef::create("ui-widget-pass-internal");
    Entity scene_entity = scene.create_entity("Scene UI");
    UIComponent* scene_component =
        make_component(scene_entity, asset, 10, "scene-ui");

    Entity internal_root =
        Entity::create(Entity::standalone_pool_handle(), "Internal Root");
    Entity internal_child = internal_root.create_child("Internal Child");
    UIComponent* internal_component =
        make_component(internal_child, asset, 3, "internal-ui");

    ExecuteContext ctx;
    ctx.scene = scene;
    ctx.internal_entities = internal_root.handle();
    auto submissions =
        collect_ui_document_submissions(ctx, false);
    REQUIRE_EQ(submissions.size(), 1u);
    CHECK(submissions[0].document == scene_component->document());

    submissions = collect_ui_document_submissions(ctx, true);
    REQUIRE_EQ(submissions.size(), 2u);
    CHECK_EQ(submissions[0].priority, 3);
    CHECK(submissions[0].document == internal_component->document());

    internal_root.set_enabled(false);
    submissions = collect_ui_document_submissions(ctx, true);
    REQUIRE_EQ(submissions.size(), 1u);

    internal_root.set_enabled(true);
    ctx.internal_entities = scene_entity.handle();
    submissions = collect_ui_document_submissions(ctx, true);
    CHECK_EQ(submissions.size(), 1u);

    tc_entity_free(internal_child.handle());
    tc_entity_free(internal_root.handle());
    scene.destroy();
    TcUiDocumentAsset::clear_registry_for_tests();
}
