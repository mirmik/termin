#include <iostream>
#include <string>
#include <vector>

#include <inspect/tc_inspect_context.h>
#include <inspect/tc_inspect_init.h>
#include <trent/json.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/unknown_component.hpp>
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

class TestResourceHandle {
public:
    TestResourceHandle() = default;
    explicit TestResourceHandle(std::string uuid) : _uuid(std::move(uuid)) {}

    static TestResourceHandle from_uuid(const std::string& uuid) {
        if (uuid == "resource-source" || uuid == "resource-local") {
            return TestResourceHandle(uuid);
        }
        return TestResourceHandle();
    }

    bool is_valid() const { return !_uuid.empty(); }
    const char* uuid() const { return _uuid.c_str(); }
    const char* name() const { return _uuid.c_str(); }
    bool operator==(const TestResourceHandle&) const = default;

private:
    std::string _uuid;
};

class PrefabRefProbe : public termin::CxxComponent {
public:
    PrefabRefProbe() : termin::CxxComponent("PrefabRefProbe") {}

    termin::Entity target;
    double weight = 0.0;
    std::vector<std::string> labels;
    TestResourceHandle resource;
};

class PrefabRefProbeV2 : public termin::CxxComponent {
public:
    PrefabRefProbeV2() : termin::CxxComponent("PrefabRefProbeV2") {}

    double gain = 0.0;
};

class TestOverrideResourceResolver final
    : public termin::prefab::PrefabOverrideResourceResolver {
public:
    bool resolve(
        std::string_view resource_type,
        std::string_view target_kind,
        std::string_view uuid,
        std::string_view display_name,
        tc::trent& result,
        std::string& error
    ) const override {
        if (resource_type != "test" || target_kind != "test_resource" ||
            uuid != "resource-local") {
            error = "test resource override does not resolve";
            return false;
        }
        result = tc::trent::dict();
        result.set("uuid", std::string(uuid));
        result.set("name", std::string(display_name));
        return true;
    }
};

int register_inspect() {
    tc::register_cpp_handle_kind<termin::Entity>("entity");
    tc::register_cpp_handle_kind<TestResourceHandle>("test_resource");

    auto probe = termin::ComponentTypeDescriptorBuilder::native<PrefabRefProbe>(
        "PrefabRefProbe", "termin-prefab-test");
    auto& probe_inspect = probe.inspect();
    TEST_ASSERT((probe_inspect.add<PrefabRefProbe, termin::Entity>(
        "PrefabRefProbe", &PrefabRefProbe::target, "target", "Target", "entity")),
        "target field should stage");
    TEST_ASSERT((probe_inspect.add<PrefabRefProbe, double>(
        "PrefabRefProbe", &PrefabRefProbe::weight, "weight", "Weight", "double")),
        "weight field should stage");
    TEST_ASSERT((probe_inspect.add<PrefabRefProbe, std::vector<std::string>>(
        "PrefabRefProbe", &PrefabRefProbe::labels, "labels", "Labels", "list[string]")),
        "labels field should stage");
    TEST_ASSERT((probe_inspect.add<PrefabRefProbe, TestResourceHandle>(
        "PrefabRefProbe", &PrefabRefProbe::resource, "resource", "Resource", "test_resource")),
        "resource field should stage");
    TEST_ASSERT(probe.commit(), "PrefabRefProbe descriptor should commit");

    auto probe_v2 = termin::ComponentTypeDescriptorBuilder::native<PrefabRefProbeV2>(
        "PrefabRefProbeV2", "termin-prefab-test");
    TEST_ASSERT((probe_v2.inspect().add<PrefabRefProbeV2, double>(
        "PrefabRefProbeV2", &PrefabRefProbeV2::gain, "gain", "Gain", "double")),
        "gain field should stage");
    TEST_ASSERT(probe_v2.commit(), "PrefabRefProbeV2 descriptor should commit");
    return 0;
}

nos::trent source_hierarchy() {
    nos::trent root;
    root["uuid"] = "prefab-source-root";
    root["name"] = "PrefabRoot";
    root["priority"] = int64_t{3};
    root["visible"] = true;
    root["enabled"] = true;
    root["pickable"] = true;
    root["selectable"] = true;
    root["layer"] = int64_t{1};
    root["flags"] = int64_t{2};
    root["pose"]["position"].init(nos::trent::type::list);
    root["pose"]["position"].push_back(1.0);
    root["pose"]["position"].push_back(2.0);
    root["pose"]["position"].push_back(3.0);
    root["pose"]["rotation"].init(nos::trent::type::list);
    root["pose"]["rotation"].push_back(0.0);
    root["pose"]["rotation"].push_back(0.0);
    root["pose"]["rotation"].push_back(0.0);
    root["pose"]["rotation"].push_back(1.0);
    root["scale"].init(nos::trent::type::list);
    root["scale"].push_back(1.0);
    root["scale"].push_back(1.0);
    root["scale"].push_back(1.0);
    root["components"].init(nos::trent::type::list);

    nos::trent component;
    component["source_id"] = "prefab-source-probe-component";
    component["type"] = "PrefabRefProbe";
    component["data"]["target"]["uuid"] = "prefab-source-child";
    component["data"]["weight"] = 2.5;
    component["data"]["labels"].init(nos::trent::type::list);
    component["data"]["labels"].push_back("source");
    component["data"]["labels"].push_back("values");
    component["data"]["resource"]["uuid"] = "resource-source";
    component["data"]["resource"]["name"] = "Source Resource";
    root["components"].push_back(std::move(component));

    root["children"].init(nos::trent::type::list);
    nos::trent child;
    child["uuid"] = "prefab-source-child";
    child["name"] = "Child";
    child["priority"] = int64_t{0};
    child["visible"] = true;
    child["enabled"] = true;
    child["pickable"] = true;
    child["selectable"] = true;
    child["layer"] = int64_t{0};
    child["flags"] = int64_t{0};
    child["pose"] = root["pose"];
    child["scale"] = root["scale"];
    child["components"].init(nos::trent::type::list);
    child["children"].init(nos::trent::type::list);

    nos::trent grandchild;
    grandchild["uuid"] = "prefab-source-grandchild";
    grandchild["name"] = "Grandchild";
    grandchild["priority"] = int64_t{0};
    grandchild["visible"] = true;
    grandchild["enabled"] = true;
    grandchild["pickable"] = true;
    grandchild["selectable"] = true;
    grandchild["layer"] = int64_t{0};
    grandchild["flags"] = int64_t{0};
    grandchild["pose"] = root["pose"];
    grandchild["scale"] = root["scale"];
    grandchild["components"].init(nos::trent::type::list);
    grandchild["children"].init(nos::trent::type::list);
    child["children"].push_back(std::move(grandchild));
    root["children"].push_back(std::move(child));
    return root;
}

} // namespace

int main() {
    tc_inspect_kind_core_init();
    termin::register_builtin_scene_component_types();
    TEST_ASSERT(register_inspect() == 0, "test descriptors should register");

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

    auto record_override = [](
        termin::prefab::PrefabInstanceState& state,
        const std::string& source_entity_id,
        const std::string& source_component_id,
        const std::string& field_path,
        const std::string& target_kind
    ) {
        std::string error;
        auto value = termin::prefab::PrefabOverrideValue::parse_json(
            R"({"schema":"termin.prefab.override-value","version":1,"value":{"tag":"none"}})",
            error
        );
        if (!value) return false;
        termin::prefab::PrefabPropertyOverride item;
        item.source_entity_id = source_entity_id;
        item.source_component_id = source_component_id;
        item.field_path = field_path;
        item.target_kind = target_kind;
        item.value = std::move(*value);
        return state.set_property_override(std::move(item), error);
    };

    PrefabRefProbe* document_probe =
        document_instance.root.get_component<PrefabRefProbe>();
    termin::Entity document_child = document_instance.root.find_child("Child");
    TEST_ASSERT(document_probe != nullptr && document_child.valid(),
                "restore fixture should expose component and mapped child");
    termin::Entity local_extra = document_instance.root.create_child("LocalExtra");
    document_instance.root.set_visible(false);
    document_instance.root.set_name("LocallyRenamed");
    double local_position[3] = {9.0, 8.0, 7.0};
    document_instance.root.set_local_position(local_position);
    document_probe->labels = {"local"};
    document_probe->target = document_instance.root;
    document_probe->resource = TestResourceHandle::from_uuid("resource-local");
    TEST_ASSERT(record_override(*document_state, "prefab-source-root", "", "name", "string") &&
                record_override(*document_state, "prefab-source-root", "", "transform.position", "vec3") &&
                record_override(*document_state, "prefab-source-root",
                                "prefab-source-probe-component", "labels", "list[string]") &&
                record_override(*document_state, "prefab-source-root",
                                "prefab-source-probe-component", "target", "entity") &&
                record_override(*document_state, "prefab-source-root",
                                "prefab-source-probe-component", "resource", "test_resource") &&
                record_override(*document_state, "prefab-source-root",
                                "prefab-source-probe-component", "missing", "double"),
                "restore fixture overrides should be accepted");

    const std::string original_revision = document_state->source_revision();
    termin::prefab::PrefabOverrideRestoreResult batch_restore =
        document_state->clear_all_property_overrides(parsed_document.document);
    TEST_ASSERT(batch_restore.requested_count == 6 && batch_restore.restored_count == 5,
                "clear-all should restore every independently resolvable override");
    TEST_ASSERT(batch_restore.failures.size() == 1 &&
                    batch_restore.failures[0].error ==
                        termin::prefab::PrefabOverrideRestoreError::FieldNotFound,
                "clear-all should retain and diagnose an unresolvable field");
    TEST_ASSERT(document_state->property_override_count() == 1,
                "failed clear-all entries should remain visible in native state");
    TEST_ASSERT(std::string(document_instance.root.name()) == "PrefabRoot",
                "entity property clear should restore the current source name");
    double restored_position[3] = {};
    document_instance.root.get_local_position(restored_position);
    TEST_ASSERT(restored_position[0] == 1.0 && restored_position[1] == 2.0 &&
                    restored_position[2] == 3.0,
                "transform clear should restore the current source position");
    TEST_ASSERT(document_probe->labels == std::vector<std::string>({"source", "values"}),
                "container clear should restore the serialized source container");
    TEST_ASSERT(document_probe->target == document_child,
                "entity-reference clear should remap source identity into this instance");
    TEST_ASSERT(document_probe->resource == TestResourceHandle::from_uuid("resource-source"),
                "resource clear should restore a resolvable native runtime handle");
    TEST_ASSERT(local_extra.valid() && document_instance.root.find_child("LocalExtra") == local_extra,
                "field reconciliation should preserve unrelated local structure");
    TEST_ASSERT(!document_instance.root.visible(),
                "field reconciliation should preserve unrelated local property changes");
    TEST_ASSERT(document_state->source_revision() == original_revision,
                "partial property reconciliation must not claim a fully refreshed revision");
    document_state->discard_all_property_overrides();

    nos::trent newer_document_data = document_data;
    newer_document_data["root"]["components"].as_list()[0]["data"]["weight"] = 7.0;
    termin::prefab::PrefabDocumentResult newer_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(newer_document_data));
    TEST_ASSERT(newer_document.ok(), "newer source fixture should parse");
    document_probe->weight = 99.0;
    TEST_ASSERT(record_override(*document_state, "prefab-source-root",
                                "prefab-source-probe-component", "weight", "double"),
                "scalar restore fixture should be accepted");
    termin::prefab::PrefabOverrideRestoreResult scalar_restore =
        document_state->clear_property_override(
            newer_document.document,
            "prefab-source-root", "prefab-source-probe-component", "weight");
    TEST_ASSERT(scalar_restore.ok() && scalar_restore.restored_count == 1 &&
                    document_probe->weight == 7.0,
                "clear-one should use the current document even when its revision is newer");
    TEST_ASSERT(document_state->source_revision() == original_revision,
                "clear-one against a newer document should not rewrite instance revision");

    termin::prefab::PrefabInstantiateResult reconcile_instance =
        termin::prefab::PrefabInstantiator::instantiate(
            parsed_document.document, scene.handle(), parent);
    TEST_ASSERT(reconcile_instance.ok(), "property reconcile fixture should instantiate");
    auto* reconcile_state = reconcile_instance.root.get_component<
        termin::prefab::PrefabInstanceState>();
    auto* reconcile_probe = reconcile_instance.root.get_component<PrefabRefProbe>();
    TEST_ASSERT(reconcile_state != nullptr && reconcile_probe != nullptr,
                "property reconcile fixture should expose state and source component");
    termin::Entity reconcile_local = reconcile_instance.root.create_child("ReconcileLocal");
    reconcile_instance.root.set_name("stale-name");
    reconcile_probe->weight = 42.5;
    reconcile_probe->labels = {"stale"};
    std::string reconcile_override_error;
    auto reconcile_override_value = termin::prefab::PrefabOverrideValue::parse_json(
        R"({"schema":"termin.prefab.override-value","version":1,"value":{"tag":"float64","value":"42.5"}})",
        reconcile_override_error);
    TEST_ASSERT(reconcile_override_value.has_value(),
                "reconcile typed override fixture should parse");
    termin::prefab::PrefabPropertyOverride reconcile_override;
    reconcile_override.source_entity_id = "prefab-source-root";
    reconcile_override.source_component_id = "prefab-source-probe-component";
    reconcile_override.field_path = "weight";
    reconcile_override.target_kind = "double";
    reconcile_override.value = std::move(*reconcile_override_value);
    TEST_ASSERT(reconcile_state->set_property_override(
                    std::move(reconcile_override), reconcile_override_error),
                "reconcile typed override should be stored");
    auto reconcile_resource_value = termin::prefab::PrefabOverrideValue::parse_json(
        R"({"schema":"termin.prefab.override-value","version":1,"value":{"tag":"resource","resource_type":"test","kind":"test_resource","uuid":"resource-local","name":"Local Resource"}})",
        reconcile_override_error);
    TEST_ASSERT(reconcile_resource_value.has_value(),
                "reconcile resource override fixture should parse");
    termin::prefab::PrefabPropertyOverride reconcile_resource_override;
    reconcile_resource_override.source_entity_id = "prefab-source-root";
    reconcile_resource_override.source_component_id = "prefab-source-probe-component";
    reconcile_resource_override.field_path = "resource";
    reconcile_resource_override.target_kind = "test_resource";
    reconcile_resource_override.value = std::move(*reconcile_resource_value);
    reconcile_probe->resource = TestResourceHandle::from_uuid("resource-local");
    TEST_ASSERT(reconcile_state->set_property_override(
                    std::move(reconcile_resource_override), reconcile_override_error),
                "reconcile resource override should be stored");
    auto reconcile_layer_value = termin::prefab::PrefabOverrideValue::parse_json(
        R"({"schema":"termin.prefab.override-value","version":1,"value":{"tag":"uint64","value":"18446744073709551615"}})",
        reconcile_override_error);
    TEST_ASSERT(reconcile_layer_value.has_value(),
                "reconcile uint64 override fixture should parse");
    termin::prefab::PrefabPropertyOverride reconcile_layer_override;
    reconcile_layer_override.source_entity_id = "prefab-source-root";
    reconcile_layer_override.field_path = "layer";
    reconcile_layer_override.target_kind = "uint64";
    reconcile_layer_override.value = std::move(*reconcile_layer_value);
    reconcile_instance.root.set_layer(std::numeric_limits<uint64_t>::max());
    TEST_ASSERT(reconcile_state->set_property_override(
                    std::move(reconcile_layer_override), reconcile_override_error),
                "reconcile uint64 override should be stored");
    const TestOverrideResourceResolver reconcile_resource_resolver;

    nos::trent refreshed_data = document_data;
    refreshed_data["root"]["name"] = "RefreshedRoot";
    refreshed_data["root"]["components"].as_list()[0]["data"]["weight"] = 7.25;
    refreshed_data["root"]["components"].as_list()[0]["data"]["labels"].as_list().clear();
    refreshed_data["root"]["components"].as_list()[0]["data"]["labels"].push_back("fresh");
    termin::prefab::PrefabDocumentResult refreshed_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(refreshed_data));
    TEST_ASSERT(refreshed_document.ok(), "refreshed reconcile document should parse");
    const std::string revision_before_resource_failure = reconcile_state->source_revision();
    termin::prefab::PrefabReconcileResult unresolved_override_reconcile =
        reconcile_state->reconcile_properties(refreshed_document.document);
    TEST_ASSERT(!unresolved_override_reconcile.ok() &&
                    !unresolved_override_reconcile.revision_updated &&
                    unresolved_override_reconcile.failures.size() == 1 &&
                    unresolved_override_reconcile.failures[0].phase ==
                        termin::prefab::PrefabReconcilePhase::OverrideValue &&
                    unresolved_override_reconcile.failures[0].error ==
                        termin::prefab::PrefabPropertyApplyError::ResourceResolutionFailed &&
                    reconcile_state->source_revision() == revision_before_resource_failure &&
                    reconcile_state->property_override_count() == 3 &&
                    reconcile_probe->resource ==
                        TestResourceHandle::from_uuid("resource-local"),
                "missing explicit resource resolver should retain live value, metadata, and revision");
    termin::prefab::PrefabReconcileResult reconcile_result =
        reconcile_state->reconcile_properties(
            refreshed_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(reconcile_result.ok() && reconcile_result.revision_updated,
                "complete property reconcile should advance the source revision");
    TEST_ASSERT(reconcile_result.override_count == 3 &&
                    reconcile_result.overrides_applied == 3 &&
                    reconcile_state->property_override_count() == 3,
                "reconcile should reapply and retain typed override metadata");
    TEST_ASSERT(std::string(reconcile_instance.root.name()) == "RefreshedRoot" &&
                    reconcile_probe->weight == 42.5 &&
                    reconcile_probe->resource ==
                        TestResourceHandle::from_uuid("resource-local") &&
                    reconcile_instance.root.layer() ==
                        std::numeric_limits<uint64_t>::max() &&
                    reconcile_probe->labels == std::vector<std::string>({"fresh"}),
                "source values should refresh while the exact override wins");
    TEST_ASSERT(reconcile_local.valid() &&
                    reconcile_instance.root.find_child("ReconcileLocal") == reconcile_local,
                "property reconcile should preserve unrelated local structure");
    TEST_ASSERT(reconcile_state->source_revision() ==
                    refreshed_document.document.source_revision(),
                "successful reconcile should publish the exact target revision");

    nos::trent broken_refresh_data = refreshed_data;
    broken_refresh_data["root"]["components"].as_list()[0]["data"]["unknown_field"] = 1;
    broken_refresh_data["root"]["visible"] = false;
    termin::prefab::PrefabDocumentResult broken_refresh_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(broken_refresh_data));
    TEST_ASSERT(broken_refresh_document.ok(), "field drift fixture should parse");
    const std::string completed_revision = reconcile_state->source_revision();
    termin::prefab::PrefabReconcileResult broken_reconcile =
        reconcile_state->reconcile_properties(
            broken_refresh_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(!broken_reconcile.ok() && !broken_reconcile.revision_updated &&
                    reconcile_state->source_revision() == completed_revision,
                "partial property reconciliation must retain the previous revision");
    TEST_ASSERT(!reconcile_instance.root.visible(),
                "independent source fields should still apply during best-effort reconciliation");
    TEST_ASSERT(broken_reconcile.failures.size() == 1 &&
                    broken_reconcile.failures[0].phase ==
                        termin::prefab::PrefabReconcilePhase::SourceValue &&
                    broken_reconcile.failures[0].field_path == "unknown_field",
                "field drift should produce one deterministic source diagnostic");
    TEST_ASSERT(reconcile_state->property_override_count() == 3 &&
                    reconcile_probe->weight == 42.5,
                "partial reconcile should retain and reapply stored overrides");

    nos::trent structural_refresh_data = refreshed_data;
    nos::trent added_source_child =
        structural_refresh_data["root"]["children"].as_list()[0];
    added_source_child["uuid"] = "prefab-source-added-later";
    added_source_child["name"] = "AddedLater";
    added_source_child["components"].as_list().clear();
    added_source_child["children"].as_list().clear();
    structural_refresh_data["root"]["children"].push_back(
        std::move(added_source_child));
    termin::prefab::PrefabDocumentResult structural_refresh_document =
        termin::prefab::PrefabDocument::parse_json(
            nos::json::dump(structural_refresh_data));
    TEST_ASSERT(structural_refresh_document.ok(), "source addition fixture should parse");
    termin::prefab::PrefabReconcileResult structural_reconcile =
        reconcile_state->reconcile(
            structural_refresh_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(structural_reconcile.ok() && structural_reconcile.revision_updated &&
                    structural_reconcile.structure_operation_count >= 1 &&
                    structural_reconcile.structure_operations_applied ==
                        structural_reconcile.structure_operation_count,
                "source additions should converge through native structural mutation");
    TEST_ASSERT(reconcile_instance.root.find_child("AddedLater").valid() &&
                    reconcile_instance.root.find_child("ReconcileLocal") == reconcile_local,
                "structural reconciliation should create source structure and preserve local structure");
    const size_t converged_entity_mapping_count = reconcile_state->entity_mapping_count();
    termin::prefab::PrefabReconcileResult idempotent_structural_reconcile =
        reconcile_state->reconcile(
            structural_refresh_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(idempotent_structural_reconcile.ok() &&
                    idempotent_structural_reconcile.structure_operation_count == 0 &&
                    reconcile_state->entity_mapping_count() ==
                        converged_entity_mapping_count,
                "repeated structural reconciliation should be idempotent");
    termin::prefab::PrefabReconcileResult repaired_reconcile =
        reconcile_state->reconcile(
            refreshed_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(repaired_reconcile.ok() && repaired_reconcile.revision_updated &&
                    !reconcile_instance.root.find_child("AddedLater").valid() &&
                    reconcile_state->source_revision() ==
                        refreshed_document.document.source_revision(),
                "source removal should delete the source-owned runtime entity");

    nos::trent reparent_data = refreshed_data;
    nos::trent reparent_child = reparent_data["root"]["children"].as_list()[0];
    nos::trent reparent_grandchild = reparent_child["children"].as_list()[0];
    reparent_child["children"].as_list().clear();
    reparent_data["root"]["children"].as_list().clear();
    reparent_data["root"]["children"].push_back(std::move(reparent_grandchild));
    reparent_data["root"]["children"].push_back(std::move(reparent_child));
    termin::prefab::PrefabDocumentResult reparent_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(reparent_data));
    TEST_ASSERT(reparent_document.ok(), "reparent fixture should parse");
    termin::prefab::PrefabReconcileResult reparent_result = reconcile_state->reconcile(
        reparent_document.document, &reconcile_resource_resolver);
    termin::Entity reparented_grandchild =
        reconcile_state->entity_for_source("prefab-source-grandchild");
    termin::Entity reordered_child =
        reconcile_state->entity_for_source("prefab-source-child");
    TEST_ASSERT(reparent_result.ok() && reparented_grandchild.parent() == reconcile_instance.root &&
                    reparented_grandchild.sibling_index() == 0 &&
                    reconcile_local.sibling_index() == 1 &&
                    reordered_child.sibling_index() == 2,
                "source reparent and reorder should converge while local sibling keeps its slot");
    TEST_ASSERT(reconcile_state->reconcile(
                    refreshed_document.document, &reconcile_resource_resolver).ok() &&
                    reparented_grandchild.parent() == reordered_child,
                "reversing a source reparent should converge idempotently");

    auto* local_component = new PrefabRefProbeV2();
    reconcile_instance.root.add_component(local_component);
    TEST_ASSERT(local_component->entity() == reconcile_instance.root,
                "local component fixture should attach");
    nos::trent component_add_data = refreshed_data;
    nos::trent added_component;
    added_component["source_id"] = "prefab-source-added-component";
    added_component["type"] = "PrefabRefProbeV2";
    added_component["data"]["gain"] = 9.5;
    component_add_data["root"]["components"].as_list().insert(
        component_add_data["root"]["components"].as_list().begin(),
        std::move(added_component)
    );
    termin::prefab::PrefabDocumentResult component_add_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(component_add_data));
    TEST_ASSERT(component_add_document.ok(), "component addition fixture should parse");
    termin::prefab::PrefabReconcileResult component_add_result = reconcile_state->reconcile(
        component_add_document.document, &reconcile_resource_resolver);
    PrefabRefProbeV2* added_runtime_component = nullptr;
    for (size_t index = 0; index < reconcile_instance.root.component_count(); ++index) {
        tc_component* candidate = reconcile_instance.root.component_at(index);
        if (candidate != nullptr &&
            std::string(tc_component_get_source_id(candidate)) ==
                "prefab-source-added-component") {
            added_runtime_component = dynamic_cast<PrefabRefProbeV2*>(
                termin::CxxComponent::from_tc(candidate));
        }
    }
    TEST_ASSERT(component_add_result.ok() && added_runtime_component != nullptr &&
                    added_runtime_component->gain == 9.5 &&
                    local_component->entity() == reconcile_instance.root,
                "source component addition should attach checked data and preserve local components");
    TEST_ASSERT(reconcile_state->reconcile(
                    refreshed_document.document, &reconcile_resource_resolver).ok() &&
                    local_component->entity() == reconcile_instance.root,
                "source component removal should preserve unrelated local components");

    nos::trent incompatible_type_data = refreshed_data;
    incompatible_type_data["root"]["components"].as_list()[0]["type"] =
        "PrefabRefProbeV2";
    incompatible_type_data["root"]["components"].as_list()[0]["data"] = nos::trent();
    incompatible_type_data["root"]["components"].as_list()[0]["data"]["gain"] = 4.0;
    termin::prefab::PrefabDocumentResult incompatible_type_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(incompatible_type_data));
    TEST_ASSERT(incompatible_type_document.ok(), "component type-change fixture should parse");
    termin::prefab::PrefabReconcileResult incompatible_type_result =
        reconcile_state->reconcile(
            incompatible_type_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(!incompatible_type_result.ok() && reconcile_probe->entity().valid() &&
                    reconcile_instance.root.get_component<PrefabRefProbe>() == reconcile_probe,
                "incompatible typed overrides should retain the old component during type change");

    termin::prefab::PrefabInstantiateResult structural_instance =
        termin::prefab::PrefabInstantiator::instantiate(
            refreshed_document.document, scene.handle(), parent);
    TEST_ASSERT(structural_instance.ok(), "structural policy instance should instantiate");
    auto* structural_state = structural_instance.root.get_component<
        termin::prefab::PrefabInstanceState>();
    TEST_ASSERT(structural_state != nullptr, "structural policy state should exist");
    TEST_ASSERT(structural_state->reconcile(
                    incompatible_type_document.document,
                    &reconcile_resource_resolver).ok() &&
                    structural_instance.root.get_component<PrefabRefProbeV2>() != nullptr &&
                    structural_instance.root.get_component<PrefabRefProbeV2>()->gain == 4.0,
                "component type change without incompatible overrides should replace checked data");
    TEST_ASSERT(structural_state->reconcile(
                    refreshed_document.document, &reconcile_resource_resolver).ok() &&
                    structural_instance.root.get_component<PrefabRefProbe>() != nullptr,
                "component type replacement should converge in both directions");
    nos::trent unavailable_component_data = refreshed_data;
    nos::trent unavailable_component;
    unavailable_component["source_id"] = "prefab-source-unavailable-component";
    unavailable_component["type"] = "MissingPrefabComponentFactory";
    unavailable_component["data"].init(nos::trent::type::dict);
    unavailable_component_data["root"]["components"].push_back(
        std::move(unavailable_component));
    termin::prefab::PrefabDocumentResult unavailable_component_document =
        termin::prefab::PrefabDocument::parse_json(
            nos::json::dump(unavailable_component_data));
    TEST_ASSERT(unavailable_component_document.ok(),
                "unavailable component factory fixture should parse");
    const std::string structural_revision_before_failure =
        structural_state->source_revision();
    termin::prefab::PrefabReconcileResult unavailable_component_result =
        structural_state->reconcile(
            unavailable_component_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(!unavailable_component_result.ok() &&
                    !unavailable_component_result.revision_updated &&
                    structural_state->source_revision() ==
                        structural_revision_before_failure,
                "unavailable component factory should leave the revision retryable");
    TEST_ASSERT(structural_state->reconcile(
                    refreshed_document.document, &reconcile_resource_resolver).ok(),
                "retry after removing an unavailable source component should converge");
    termin::Entity structural_child =
        structural_state->entity_for_source("prefab-source-child");
    termin::Entity surviving_local = structural_child.create_child("SurvivingLocal");
    auto dormant_name_value = termin::prefab::PrefabOverrideValue::parse_json(
        R"({"schema":"termin.prefab.override-value","version":1,"value":{"tag":"string","value":"LocalChildName"}})",
        reconcile_override_error);
    TEST_ASSERT(dormant_name_value.has_value(),
                "dormant property override fixture should parse");
    termin::prefab::PrefabPropertyOverride dormant_name_override;
    dormant_name_override.source_entity_id = "prefab-source-child";
    dormant_name_override.field_path = "name";
    dormant_name_override.target_kind = "string";
    dormant_name_override.value = std::move(*dormant_name_value);
    structural_child.set_name("LocalChildName");
    TEST_ASSERT(structural_state->set_property_override(
                    std::move(dormant_name_override), reconcile_override_error),
                "property intent below a future tombstone should be accepted");
    termin::prefab::PrefabStructuralOverride suppress_child;
    suppress_child.kind = termin::prefab::PrefabStructuralOverrideKind::SuppressEntity;
    suppress_child.source_entity_id = "prefab-source-child";
    TEST_ASSERT(structural_state->set_structural_override(
                    std::move(suppress_child), reconcile_override_error),
                "entity tombstone should be accepted");
    termin::prefab::PrefabReconcileResult suppress_result = structural_state->reconcile(
        refreshed_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(suppress_result.ok() && suppress_result.dormant_override_count == 1 &&
                    structural_state->property_override_count() == 1 &&
                    !structural_state->entity_for_source("prefab-source-child").valid() &&
                    !structural_state->entity_for_source("prefab-source-grandchild").valid() &&
                    surviving_local.valid() && surviving_local.parent() == structural_instance.root,
                "entity tombstone should suppress its source subtree and splice local children");
    TEST_ASSERT(structural_state->discard_structural_override(
                    termin::prefab::PrefabStructuralOverrideKind::SuppressEntity,
                    "prefab-source-child") &&
                    structural_state->reconcile(
                        refreshed_document.document, &reconcile_resource_resolver).ok() &&
                    structural_state->entity_for_source("prefab-source-child").valid() &&
                    structural_state->entity_for_source("prefab-source-grandchild").valid() &&
                    std::string(structural_state->entity_for_source(
                        "prefab-source-child").name()) == "LocalChildName" &&
                    surviving_local.valid(),
                "clearing a tombstone should recreate source structure without consuming locals");

    termin::prefab::PrefabStructuralOverride place_grandchild;
    place_grandchild.kind = termin::prefab::PrefabStructuralOverrideKind::PlaceEntity;
    place_grandchild.source_entity_id = "prefab-source-grandchild";
    place_grandchild.parent.kind = termin::prefab::PrefabStructureReferenceKind::Source;
    place_grandchild.parent.source_id = "prefab-source-root";
    place_grandchild.before.kind = termin::prefab::PrefabStructureReferenceKind::Source;
    place_grandchild.before.source_id = "prefab-source-child";
    TEST_ASSERT(structural_state->set_structural_override(
                    std::move(place_grandchild), reconcile_override_error) &&
                    structural_state->reconcile(
                        refreshed_document.document, &reconcile_resource_resolver).ok(),
                "explicit entity placement should reconcile");
    termin::Entity placed_grandchild =
        structural_state->entity_for_source("prefab-source-grandchild");
    TEST_ASSERT(placed_grandchild.parent() == structural_instance.root &&
                    placed_grandchild.sibling_index() <
                        structural_state->entity_for_source("prefab-source-child").sibling_index(),
                "explicit placement should win over canonical source parent and order");
    termin::Entity structural_clone = structural_instance.root.clone("_clone");
    auto* cloned_structural_state = structural_clone.get_component<
        termin::prefab::PrefabInstanceState>();
    TEST_ASSERT(cloned_structural_state != nullptr &&
                    cloned_structural_state->structural_override_count() == 1,
                "clone serialization should retain structural override metadata");
    TEST_ASSERT(structural_state->discard_structural_override(
                    termin::prefab::PrefabStructuralOverrideKind::PlaceEntity,
                    "prefab-source-grandchild") &&
                    structural_state->reconcile(
                        refreshed_document.document, &reconcile_resource_resolver).ok() &&
                    placed_grandchild.parent() ==
                        structural_state->entity_for_source("prefab-source-child"),
                "clearing placement should restore canonical source structure");
    termin::prefab::PrefabStructuralOverride cyclic_placement;
    cyclic_placement.kind = termin::prefab::PrefabStructuralOverrideKind::PlaceEntity;
    cyclic_placement.source_entity_id = "prefab-source-child";
    cyclic_placement.parent.kind = termin::prefab::PrefabStructureReferenceKind::Source;
    cyclic_placement.parent.source_id = "prefab-source-grandchild";
    TEST_ASSERT(structural_state->set_structural_override(
                    std::move(cyclic_placement), reconcile_override_error),
                "cyclic placement fixture should be stored for reconcile validation");
    termin::Entity canonical_child =
        structural_state->entity_for_source("prefab-source-child");
    termin::Entity canonical_grandchild =
        structural_state->entity_for_source("prefab-source-grandchild");
    termin::prefab::PrefabReconcileResult cyclic_placement_result =
        structural_state->reconcile(
            refreshed_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(!cyclic_placement_result.ok() &&
                    canonical_child.parent() == structural_instance.root &&
                    canonical_grandchild.parent() == canonical_child,
                "placement cycle preflight should reject the graph without structural mutation");
    TEST_ASSERT(structural_state->discard_structural_override(
                    termin::prefab::PrefabStructuralOverrideKind::PlaceEntity,
                    "prefab-source-child"),
                "cyclic placement fixture should be removable");
    auto* duplicate_runtime_component = new PrefabRefProbe();
    duplicate_runtime_component->set_source_id("prefab-source-probe-component");
    structural_instance.root.add_component(duplicate_runtime_component);
    termin::prefab::PrefabReconcileResult duplicate_runtime_component_result =
        structural_state->reconcile(
            refreshed_document.document, &reconcile_resource_resolver);
    TEST_ASSERT(!duplicate_runtime_component_result.ok() &&
                    !duplicate_runtime_component_result.revision_updated,
                "duplicate runtime component identities should be diagnosed without remapping");
    structural_instance.root.remove_component(duplicate_runtime_component);
    TEST_ASSERT(structural_state->reconcile(
                    refreshed_document.document, &reconcile_resource_resolver).ok(),
                "retry after removing a duplicate runtime identity should converge");
    structural_clone.destroy_children();
    tc_entity_free(structural_clone.handle());
    structural_instance.root.destroy_children();
    tc_entity_free(structural_instance.root.handle());

    termin::prefab::PrefabInstantiateOptions customized_options;
    customized_options.root_name = "CustomizedRoot";
    customized_options.has_position = true;
    customized_options.position[0] = 10.0;
    customized_options.position[1] = 11.0;
    customized_options.position[2] = 12.0;
    termin::prefab::PrefabInstantiateResult customized_instance =
        termin::prefab::PrefabInstantiator::instantiate(
            parsed_document.document, scene.handle(), parent, customized_options);
    TEST_ASSERT(customized_instance.ok(), "customized prefab instance should instantiate");
    auto* customized_state = customized_instance.root.get_component<
        termin::prefab::PrefabInstanceState>();
    TEST_ASSERT(customized_state != nullptr &&
                    customized_state->property_override_count() == 2,
                "canonical instantiation options should publish typed overrides");
    termin::prefab::PrefabReconcileResult customized_reconcile =
        customized_state->reconcile_properties(refreshed_document.document);
    double customized_position[3] = {};
    customized_instance.root.get_local_position(customized_position);
    TEST_ASSERT(customized_reconcile.ok() && customized_reconcile.revision_updated &&
                    std::string(customized_instance.root.name()) == "CustomizedRoot" &&
                    customized_position[0] == 10.0 && customized_position[1] == 11.0 &&
                    customized_position[2] == 12.0,
                "reconcile should preserve explicit root name and position options as overrides");

    nos::trent missing_resource_data = document_data;
    missing_resource_data["root"]["components"].as_list()[0]
        ["data"]["resource"]["uuid"] = "resource-missing";
    termin::prefab::PrefabDocumentResult missing_resource_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(missing_resource_data));
    TEST_ASSERT(missing_resource_document.ok(), "missing resource source fixture should parse");
    document_probe->resource = TestResourceHandle::from_uuid("resource-local");
    TEST_ASSERT(record_override(*document_state, "prefab-source-root",
                                "prefab-source-probe-component", "resource", "test_resource"),
                "missing resource restore fixture should be accepted");
    termin::prefab::PrefabOverrideRestoreResult missing_resource_restore =
        document_state->clear_property_override(
            missing_resource_document.document,
            "prefab-source-root", "prefab-source-probe-component", "resource");
    TEST_ASSERT(!missing_resource_restore.ok() &&
                    missing_resource_restore.failures[0].error ==
                        termin::prefab::PrefabOverrideRestoreError::ResourceResolutionFailed &&
                    document_probe->resource ==
                        TestResourceHandle::from_uuid("resource-local") &&
                    document_state->property_override_count() == 1,
                "unresolved resource UUID should retain both live value and override metadata");
    document_state->discard_all_property_overrides();

    nos::trent foreign_document_data = document_data;
    foreign_document_data["uuid"] = "foreign-prefab-document";
    termin::prefab::PrefabDocumentResult foreign_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(foreign_document_data));
    document_probe->weight = 101.0;
    TEST_ASSERT(record_override(*document_state, "prefab-source-root",
                                "prefab-source-probe-component", "weight", "double"),
                "asset mismatch fixture should be accepted");
    termin::prefab::PrefabOverrideRestoreResult mismatch_restore =
        document_state->clear_property_override(
            foreign_document.document,
            "prefab-source-root", "prefab-source-probe-component", "weight");
    TEST_ASSERT(!mismatch_restore.ok() &&
                    mismatch_restore.failures[0].error ==
                        termin::prefab::PrefabOverrideRestoreError::DocumentMismatch &&
                    document_probe->weight == 101.0 &&
                    document_state->property_override_count() == 1,
                "asset mismatch should leave both live value and override metadata intact");
    document_state->discard_all_property_overrides();

    termin::prefab::PrefabOverrideRestoreResult absent_restore =
        document_state->clear_property_override(
            parsed_document.document, "prefab-source-root", "", "name");
    TEST_ASSERT(!absent_restore.ok() && absent_restore.failures[0].error ==
                    termin::prefab::PrefabOverrideRestoreError::OverrideNotFound,
                "clear-one should diagnose a missing override without mutating the instance");

    nos::trent malformed_transform_data = document_data;
    malformed_transform_data["root"]["pose"]["position"].as_list().pop_back();
    termin::prefab::PrefabDocumentResult malformed_transform_document =
        termin::prefab::PrefabDocument::parse_json(nos::json::dump(malformed_transform_data));
    TEST_ASSERT(!malformed_transform_document.ok() &&
                    malformed_transform_document.message.find("root.pose.position") !=
                        std::string::npos,
                "v3 parsing should reject malformed transforms at the document boundary");

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

    nos::trent malformed_structural_data = tracking_scene_data;
    bool corrupted_structural_override = false;
    for (nos::trent& root_data : malformed_structural_data["entities"].as_list()) {
        for (nos::trent& component_data : root_data["components"].as_list()) {
            if (component_data["type"].as_string_default("") !=
                termin::prefab::PrefabInstanceState::TypeName) {
                continue;
            }
            nos::trent malformed;
            malformed["kind"] = "unknown-structural-kind";
            malformed["source_entity_id"] = "prefab-source-child";
            malformed["source_component_id"] = "";
            component_data["data"]["structural_overrides"].push_back(
                std::move(malformed));
            corrupted_structural_override = true;
            break;
        }
        if (corrupted_structural_override) break;
    }
    TEST_ASSERT(corrupted_structural_override,
                "fixture should contain serialized structural metadata");
    termin::TcSceneRef malformed_structural_scene =
        termin::TcSceneRef::create("prefab-instance-structural-malformed");
    TEST_ASSERT(malformed_structural_scene.load_from_data(
                    malformed_structural_data) == 12,
                "malformed structural metadata should not corrupt hierarchy loading");
    TEST_ASSERT(
        termin::prefab::find_live_prefab_instances(
            malformed_structural_scene.handle(), "prefab-document-asset"
        ).size() == 2,
        "instance with malformed structural intent should be excluded from live queries"
    );
    TEST_ASSERT(
        nos::json::dump(malformed_structural_scene.serialize()).find(
            "unknown-structural-kind") != std::string::npos,
        "malformed structural payload should remain visible for repair"
    );

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
    malformed_structural_scene.destroy();
    for (const termin::Entity& stale : scene_teardown_snapshot) {
        TEST_ASSERT(!stale.valid(),
                    "scene teardown should invalidate every previously returned handle");
    }
    TEST_ASSERT(
        termin::prefab::count_live_prefab_instances("prefab-document-asset") == 8,
        "all-scenes query should retain only instances in still-live scenes"
    );

    manual_scene.destroy();
    malformed_tracking_scene.destroy();
    restored_tracking_scene.destroy();

    return 0;
}
