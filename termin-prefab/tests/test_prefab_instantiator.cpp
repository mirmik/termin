#include <iostream>
#include <string>

#include <inspect/tc_inspect_context.h>
#include <inspect/tc_inspect_init.h>
#include <trent/json.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>
#include <termin/prefab/prefab_document.hpp>
#include <termin/prefab/prefab_instance_state.hpp>
#include <termin/prefab/prefab_instantiator.hpp>
#include <termin/tc_scene.hpp>

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n"; \
            return 1; \
        } \
    } while (0)

namespace {

class PrefabRefProbe : public termin::CxxComponent {
public:
    PrefabRefProbe() : termin::CxxComponent("PrefabRefProbe") {}

    termin::Entity target;

    tc_value serialize_data() const override {
        tc_value data = tc_value_dict_new();
        tc_value_dict_set(&data, "target", target.serialize_to_value());
        return data;
    }

    void deserialize_data(const tc_value* data, tc_scene_handle scene) override {
        if (data == nullptr || data->type != TC_VALUE_DICT) return;
        tc_value* target_data = tc_value_dict_get(const_cast<tc_value*>(data), "target");
        tc_scene_inspect_context context = tc_scene_inspect_context_make(scene);
        target.deserialize_from(target_data, &context);
    }
};

static termin::ComponentRegistrar<PrefabRefProbe>
    prefab_ref_probe_registrar("PrefabRefProbe", "CxxComponent");

void register_inspect() {
    tc::register_cpp_handle_kind<termin::Entity>("entity");
    tc::InspectRegistry::instance().add_handle(
        "PrefabRefProbe",
        &PrefabRefProbe::target,
        "target",
        "Target",
        "entity"
    );
}

nos::trent source_hierarchy() {
    nos::trent root;
    root["uuid"] = "prefab-source-root";
    root["name"] = "PrefabRoot";
    root["components"].init(nos::trent::type::list);

    nos::trent component;
    component["source_id"] = "prefab-source-probe-component";
    component["type"] = "PrefabRefProbe";
    component["data"]["target"]["uuid"] = "prefab-source-child";
    root["components"].push_back(std::move(component));

    root["children"].init(nos::trent::type::list);
    nos::trent child;
    child["uuid"] = "prefab-source-child";
    child["name"] = "Child";
    child["components"].init(nos::trent::type::list);
    child["children"].init(nos::trent::type::list);

    nos::trent grandchild;
    grandchild["uuid"] = "prefab-source-grandchild";
    grandchild["name"] = "Grandchild";
    grandchild["components"].init(nos::trent::type::list);
    grandchild["children"].init(nos::trent::type::list);
    child["children"].push_back(std::move(grandchild));
    root["children"].push_back(std::move(child));
    return root;
}

} // namespace

int main() {
    tc_inspect_kind_core_init();
    register_inspect();

    termin::TcSceneRef scene = termin::TcSceneRef::create("prefab-instantiator-test");
    termin::Entity parent = scene.create_entity("Parent");
    const nos::trent source = source_hierarchy();

    nos::trent document_data;
    document_data["version"] = termin::prefab::PrefabDocument::CurrentVersion;
    document_data["uuid"] = "prefab-document-asset";
    document_data["root"] = source;
    termin::prefab::PrefabDocumentResult parsed_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(document_data));
    TEST_ASSERT(parsed_document.ok(), "valid v3 prefab document should parse");
    TEST_ASSERT(parsed_document.document.asset_uuid() == "prefab-document-asset",
                "parsed prefab document should retain asset UUID");

    nos::trent legacy_document = document_data;
    legacy_document["version"] = "2.0";
    termin::prefab::PrefabDocumentResult legacy_result =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(legacy_document));
    TEST_ASSERT(legacy_result.error == termin::prefab::PrefabDocumentError::UnsupportedVersion,
                "normal parser should explicitly reject legacy prefab versions");

    termin::TcSceneRef edit_scene = termin::TcSceneRef::create("prefab-source-edit-test");
    termin::prefab::PrefabDocumentResult editable =
        parsed_document.document.materialize_source(edit_scene.handle());
    TEST_ASSERT(editable.ok(), "v3 source should materialize directly into an edit scene");
    TEST_ASSERT(std::string(editable.root.uuid()) == source["uuid"].as_string(),
                "source materialization should preserve entity source identity");
    PrefabRefProbe* editable_probe = editable.root.get_component<PrefabRefProbe>();
    TEST_ASSERT(editable_probe != nullptr, "source materialization should restore components");
    TEST_ASSERT(editable_probe->source_id() == "prefab-source-probe-component",
                "source materialization should preserve component source identity");

    termin::prefab::PrefabDocumentResult captured =
        termin::prefab::PrefabDocument::capture(
            parsed_document.document.asset_uuid(),
            editable.root
        );
    TEST_ASSERT(captured.ok(), "editable hierarchy should capture into a v3 document");
    termin::prefab::PrefabDocumentResult reparsed =
        termin::prefab::PrefabDocument::parse_json(captured.document.to_json());
    TEST_ASSERT(reparsed.ok(), "captured v3 document should round-trip through JSON");

    termin::prefab::PrefabInstantiateResult first =
        termin::prefab::PrefabInstantiator::instantiate(source, scene.handle(), parent);
    termin::prefab::PrefabInstantiateResult second =
        termin::prefab::PrefabInstantiator::instantiate(source, scene.handle(), parent);
    termin::prefab::PrefabInstantiateResult document_instance =
        termin::prefab::PrefabInstantiator::instantiate(
            parsed_document.document,
            scene.handle(),
            parent
        );

    TEST_ASSERT(first.ok() && second.ok() && document_instance.ok(),
                "legacy adapter and canonical document instances should be created");
    TEST_ASSERT(first.root.parent() == parent && second.root.parent() == parent,
                "instances should attach to the requested parent");
    TEST_ASSERT(first.root.pool() == scene.entity_pool() && second.root.pool() == scene.entity_pool(),
                "instances should be allocated directly in the target scene");
    TEST_ASSERT(std::string(first.root.uuid()) != std::string(second.root.uuid()),
                "instance root UUIDs should differ");
    TEST_ASSERT(std::string(document_instance.root.uuid()) != source["uuid"].as_string(),
                "document instantiation should assign a fresh runtime UUID");
    TEST_ASSERT(std::string(first.root.uuid()) != source["uuid"].as_string(),
                "instance UUID should differ from source UUID");

    termin::prefab::PrefabInstanceState* document_state =
        document_instance.root.get_component<termin::prefab::PrefabInstanceState>();
    TEST_ASSERT(document_state != nullptr,
                "canonical document instance should publish native instance state");
    TEST_ASSERT(document_state->prefab_asset_uuid() == "prefab-document-asset",
                "instance state should retain prefab asset identity");
    TEST_ASSERT(document_state->source_revision() == parsed_document.document.source_revision(),
                "instance state should retain deterministic source revision");
    TEST_ASSERT(document_state->entity_mapping_count() == 3,
                "instance state should map every source entity");
    TEST_ASSERT(document_state->component_mapping_count() == 1,
                "instance state should map every source component owner");

    termin::Entity first_child = first.root.find_child("Child");
    termin::Entity second_child = second.root.find_child("Child");
    TEST_ASSERT(first_child.valid() && second_child.valid(), "instance children should exist");
    TEST_ASSERT(first_child.find_child("Grandchild").valid(), "nested hierarchy should be complete");
    TEST_ASSERT(std::string(first_child.uuid()) != std::string(second_child.uuid()),
                "child UUIDs should be unique per instance");

    PrefabRefProbe* first_probe = first.root.get_component<PrefabRefProbe>();
    PrefabRefProbe* second_probe = second.root.get_component<PrefabRefProbe>();
    TEST_ASSERT(first_probe != nullptr && second_probe != nullptr,
                "instance components should deserialize");
    TEST_ASSERT(first_probe->target == first_child,
                "first instance entity reference should point inside first instance");
    TEST_ASSERT(second_probe->target == second_child,
                "second instance entity reference should point inside second instance");
    TEST_ASSERT(document_state->entity_for_source("prefab-source-child") ==
                    document_instance.root.find_child("Child"),
                "source entity mapping should resolve the matching runtime child");
    TEST_ASSERT(document_state->component_owner_for_source(
                    "prefab-source-probe-component") == document_instance.root,
                "component source mapping should resolve its runtime owner");

    const size_t stable_count = scene.entity_count();
    nos::trent malformed = source;
    malformed["children"].push_back("not-an-entity");
    termin::prefab::PrefabInstantiateResult malformed_result =
        termin::prefab::PrefabInstantiator::instantiate(malformed, scene.handle(), parent);
    TEST_ASSERT(!malformed_result.ok(), "malformed hierarchy should be rejected");
    TEST_ASSERT(scene.entity_count() == stable_count,
                "malformed hierarchy should not modify the target scene");

    nos::trent duplicate = source;
    duplicate["children"].as_list()[0]["uuid"] = source["uuid"].as_string();
    termin::prefab::PrefabInstantiateResult duplicate_result =
        termin::prefab::PrefabInstantiator::instantiate(duplicate, scene.handle(), parent);
    TEST_ASSERT(duplicate_result.error == termin::prefab::PrefabInstantiateError::DuplicateSourceUuid,
                "duplicate source UUID should have a stable error code");
    TEST_ASSERT(scene.entity_count() == stable_count,
                "duplicate source UUID should not modify the target scene");

    nos::trent duplicate_component = source;
    nos::trent second_component = duplicate_component["components"].as_list()[0];
    duplicate_component["components"].push_back(std::move(second_component));
    termin::prefab::PrefabInstantiateResult duplicate_component_result =
        termin::prefab::PrefabInstantiator::instantiate(
            duplicate_component,
            scene.handle(),
            parent
        );
    TEST_ASSERT(duplicate_component_result.error == termin::prefab::PrefabInstantiateError::InvalidDocument,
                "duplicate component source ID should be rejected");
    TEST_ASSERT(scene.entity_count() == stable_count,
                "duplicate component source ID should not modify the target scene");

    termin::TcSceneRef other_scene = termin::TcSceneRef::create("prefab-other-scene");
    termin::Entity foreign_parent = other_scene.create_entity("ForeignParent");
    termin::prefab::PrefabInstantiateResult foreign_parent_result =
        termin::prefab::PrefabInstantiator::instantiate(source, scene.handle(), foreign_parent);
    TEST_ASSERT(foreign_parent_result.error == termin::prefab::PrefabInstantiateError::InvalidParent,
                "cross-pool parent should be rejected");
    TEST_ASSERT(scene.entity_count() == stable_count,
                "cross-pool parent should not modify the target scene");

    termin::TcSceneRef tracking_scene =
        termin::TcSceneRef::create("prefab-instance-tracking-test");
    termin::prefab::PrefabInstantiateResult tracked_first =
        termin::prefab::PrefabInstantiator::instantiate(
            parsed_document.document,
            tracking_scene.handle()
        );
    termin::prefab::PrefabInstantiateResult tracked_second =
        termin::prefab::PrefabInstantiator::instantiate(
            parsed_document.document,
            tracking_scene.handle()
        );
    TEST_ASSERT(tracked_first.ok() && tracked_second.ok(),
                "tracking fixtures should instantiate");
    TEST_ASSERT(
        termin::prefab::find_live_prefab_instances(
            tracking_scene.handle(),
            "prefab-document-asset"
        ).size() == 2,
        "scene-owned exact type index should find both live instances"
    );

    nos::trent other_document_data = document_data;
    other_document_data["uuid"] = "other-prefab-asset";
    termin::prefab::PrefabDocumentResult other_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(other_document_data));
    termin::prefab::PrefabInstantiateResult tracked_other =
        termin::prefab::PrefabInstantiator::instantiate(
            other_document.document,
            tracking_scene.handle()
        );
    TEST_ASSERT(tracked_other.ok(), "second prefab asset should instantiate");
    TEST_ASSERT(
        termin::prefab::find_live_prefab_instances(
            tracking_scene.handle(),
            "prefab-document-asset"
        ).size() == 2,
        "asset filtering should exclude instances of other prefabs"
    );

    auto* tracked_first_state =
        tracked_first.root.get_component<termin::prefab::PrefabInstanceState>();
    TEST_ASSERT(tracked_first_state != nullptr, "tracked instance should expose native state");
    std::string override_error;
    auto override_value = termin::prefab::PrefabOverrideValue::parse_json(
        R"({"schema":"termin.prefab.override-value","version":1,"value":{"tag":"float64","value":"42.5"}})",
        override_error
    );
    TEST_ASSERT(override_value.has_value(), "typed override fixture should parse");
    termin::prefab::PrefabPropertyOverride property_override;
    property_override.source_entity_id = "prefab-source-root";
    property_override.source_component_id = "prefab-source-probe-component";
    property_override.field_path = "weight";
    property_override.target_kind = "double";
    property_override.value = std::move(*override_value);
    TEST_ASSERT(
        tracked_first_state->set_property_override(
            std::move(property_override), override_error
        ),
        "native state should accept a valid typed property override"
    );
    TEST_ASSERT(tracked_first_state->property_override_count() == 1,
                "typed property override should be stored exactly once");

    termin::Entity cloned_instance = tracked_first.root.clone("_copy");
    TEST_ASSERT(cloned_instance.valid(), "generic entity clone should clone prefab state");
    auto* cloned_state =
        cloned_instance.get_component<termin::prefab::PrefabInstanceState>();
    TEST_ASSERT(cloned_state != nullptr, "generic clone should retain native prefab state");
    TEST_ASSERT(cloned_state->entity_for_source("prefab-source-child") ==
                    cloned_instance.find_child("Child"),
                "generic clone should remap serialized state entity references");
    TEST_ASSERT(cloned_state->component_owner_for_source(
                    "prefab-source-probe-component") == cloned_instance,
                "generic clone should remap component owner references");
    TEST_ASSERT(cloned_state->property_override_count() == 1,
                "generic clone should preserve typed property overrides");
    const auto* cloned_override = cloned_state->property_override(
        "prefab-source-root", "prefab-source-probe-component", "weight"
    );
    TEST_ASSERT(cloned_override != nullptr && cloned_override->value.tag() == "float64",
                "cloned typed override should retain its codec identity");

    nos::trent tracking_scene_data = tracking_scene.serialize();
    termin::TcSceneRef restored_tracking_scene =
        termin::TcSceneRef::create("prefab-instance-tracking-restored");
    TEST_ASSERT(restored_tracking_scene.load_from_data(tracking_scene_data) == 12,
                "serialized tracking scene should restore all instance hierarchies");
    std::vector<termin::Entity> restored_instances =
        termin::prefab::find_live_prefab_instances(
            restored_tracking_scene.handle(),
            "prefab-document-asset"
        );
    TEST_ASSERT(restored_instances.size() == 3,
                "scene load should restore all matching native instance states");
    size_t restored_override_count = 0;
    for (termin::Entity& restored_root : restored_instances) {
        auto* restored_state =
            restored_root.get_component<termin::prefab::PrefabInstanceState>();
        TEST_ASSERT(restored_state != nullptr,
                    "restored instance root should contain native state");
        TEST_ASSERT(restored_state->entity_for_source("prefab-source-child") ==
                        restored_root.find_child("Child"),
                    "scene load should rebuild mapping handles from serialized entity refs");
        restored_override_count += restored_state->property_override_count();
    }
    TEST_ASSERT(restored_override_count == 2,
                "scene load should round-trip overrides on original and cloned instances");

    nos::trent malformed_override_data = tracking_scene_data;
    bool corrupted_override = false;
    for (nos::trent& root_data : malformed_override_data["entities"].as_list()) {
        for (nos::trent& component_data : root_data["components"].as_list()) {
            if (component_data["type"].as_string_default("") !=
                termin::prefab::PrefabInstanceState::TypeName) {
                continue;
            }
            if (!component_data["data"]["property_overrides"].as_list().empty()) {
                component_data["data"]["property_overrides"].as_list()[0]
                    ["value"]["value"]["tag"] = "unknown-test-tag";
                corrupted_override = true;
                break;
            }
        }
        if (corrupted_override) break;
    }
    TEST_ASSERT(corrupted_override, "fixture should contain a serialized typed override");
    TEST_ASSERT(
        nos::json::dump(malformed_override_data).find("unknown-test-tag") != std::string::npos,
        "fixture mutation should replace the serialized override tag"
    );
    termin::TcSceneRef malformed_override_scene =
        termin::TcSceneRef::create("prefab-instance-override-malformed");
    TEST_ASSERT(malformed_override_scene.load_from_data(malformed_override_data) == 12,
                "malformed override metadata should not corrupt hierarchy loading");
    TEST_ASSERT(
        termin::prefab::find_live_prefab_instances(
            malformed_override_scene.handle(), "prefab-document-asset"
        ).size() == 2,
        "instance with malformed typed overrides should be excluded from live queries"
    );
    const std::string reserialized_malformed = nos::json::dump(
        malformed_override_scene.serialize()
    );
    TEST_ASSERT(reserialized_malformed.find("unknown-test-tag") != std::string::npos,
                "malformed override payload should remain visible for diagnosis and repair");

    nos::trent malformed_tracking_data = tracking_scene_data;
    bool malformed_state = false;
    for (nos::trent& root_data : malformed_tracking_data["entities"].as_list()) {
        for (nos::trent& component_data : root_data["components"].as_list()) {
            if (component_data["type"].as_string_default("") ==
                termin::prefab::PrefabInstanceState::TypeName) {
                component_data["data"]["runtime_entities"].as_list().pop_back();
                malformed_state = true;
                break;
            }
        }
        if (malformed_state) break;
    }
    TEST_ASSERT(malformed_state, "fixture should contain serialized prefab instance state");
    termin::TcSceneRef malformed_tracking_scene =
        termin::TcSceneRef::create("prefab-instance-tracking-malformed");
    TEST_ASSERT(malformed_tracking_scene.load_from_data(malformed_tracking_data) == 12,
                "malformed state should not corrupt hierarchy loading");
    TEST_ASSERT(
        termin::prefab::find_live_prefab_instances(
            malformed_tracking_scene.handle(),
            "prefab-document-asset"
        ).size() == 2,
        "malformed state should be diagnosed and excluded from live queries"
    );

    std::vector<termin::Entity> mutation_snapshot =
        termin::prefab::find_live_prefab_instances(
            tracking_scene.handle(),
            "prefab-document-asset"
        );
    TEST_ASSERT(mutation_snapshot.size() == 3,
                "query should return a complete pre-mutation snapshot");
    mutation_snapshot[0].destroy_children();
    tc_entity_free(mutation_snapshot[0].handle());
    TEST_ASSERT(!mutation_snapshot[0].valid(),
                "snapshot handles should invalidate after entity destruction");
    TEST_ASSERT(
        termin::prefab::find_live_prefab_instances(
            tracking_scene.handle(),
            "prefab-document-asset"
        ).size() == 2,
        "entity destruction should immediately remove native instance state from queries"
    );

    termin::TcSceneRef manual_scene =
        termin::TcSceneRef::create("prefab-instance-manual-lifecycle");
    termin::Entity manual_root = manual_scene.create_entity("ManualRoot");
    for (int iteration = 0; iteration < 3; ++iteration) {
        auto* manual_state =
            new termin::prefab::PrefabInstanceState("manual-prefab-asset");
        manual_root.add_component(manual_state);
        TEST_ASSERT(
            termin::prefab::count_live_prefab_instances("manual-prefab-asset") == 1,
            "repeated state attachment should register exactly one live instance"
        );
        manual_root.remove_component(manual_state);
        TEST_ASSERT(
            termin::prefab::count_live_prefab_instances("manual-prefab-asset") == 0,
            "component removal should unregister the instance immediately"
        );
    }

    std::vector<termin::Entity> scene_teardown_snapshot =
        termin::prefab::find_live_prefab_instances(
            tracking_scene.handle(),
            "prefab-document-asset"
        );
    tracking_scene.destroy();
    malformed_override_scene.destroy();
    for (const termin::Entity& stale : scene_teardown_snapshot) {
        TEST_ASSERT(!stale.valid(),
                    "scene teardown should invalidate every previously returned handle");
    }
    TEST_ASSERT(
        termin::prefab::count_live_prefab_instances("prefab-document-asset") == 6,
        "all-scenes query should retain only instances in still-live scenes"
    );

    manual_scene.destroy();
    malformed_tracking_scene.destroy();
    restored_tracking_scene.destroy();

    return 0;
}
