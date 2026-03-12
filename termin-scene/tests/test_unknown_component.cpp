#include <iostream>
#include <string>
#include <vector>

#include <tc_inspect_cpp.hpp>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/unknown_component.hpp>
#include <termin/entity/unknown_component_ops.hpp>
#include <termin/tc_scene.hpp>

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n"; \
            return 1; \
        } \
    } while (0)

namespace {

class ReloadableComponent : public termin::CxxComponent {
public:
    ReloadableComponent() {
        declare_type_name("ReloadableComponent");
    }

    int value = 0;
};

class SecondaryComponent : public termin::CxxComponent {
public:
    SecondaryComponent() {
        declare_type_name("SecondaryComponent");
    }

    int amount = 0;
};

static ::termin::ComponentRegistrar<ReloadableComponent>
    reloadable_component_registrar("ReloadableComponent", "CxxComponent");
static ::termin::ComponentRegistrar<SecondaryComponent>
    secondary_component_registrar("SecondaryComponent", "CxxComponent");

struct InspectFieldRegistration {
    InspectFieldRegistration() {
        tc::InspectRegistry::instance().add<ReloadableComponent, int>(
            "ReloadableComponent",
            &ReloadableComponent::value,
            "value",
            "Value",
            "int"
        );

        tc::InspectRegistry::instance().add<SecondaryComponent, int>(
            "SecondaryComponent",
            &SecondaryComponent::amount,
            "amount",
            "Amount",
            "int"
        );
    }
} inspect_field_registration;

template<typename T>
T* create_registered_component(const char* type_name) {
    tc_component* component = tc_component_registry_create(type_name);
    if (component == nullptr) {
        return nullptr;
    }

    return dynamic_cast<T*>(termin::CxxComponent::from_tc(component));
}

void reregister_reloadable_component() {
    termin::ComponentRegistry::instance().register_native(
        "ReloadableComponent",
        &termin::CxxComponentFactoryData<ReloadableComponent>::create,
        nullptr,
        "CxxComponent"
    );
}

int test_cpp_inspect_registry_roundtrip() {
    std::cout << "Testing InspectRegistry roundtrip for test components...\n";

    auto& reg = tc::InspectRegistry::instance();
    TEST_ASSERT(reg.all_fields_count("ReloadableComponent") == 1, "ReloadableComponent fields registered");
    TEST_ASSERT(reg.find_field("ReloadableComponent", "value") != nullptr, "ReloadableComponent.value field registered");

    ReloadableComponent component;
    component.value = 321;

    tc_value serialized = reg.serialize_all(&component, "ReloadableComponent");
    TEST_ASSERT(serialized.type == TC_VALUE_DICT, "registry serialize returns dict");

    tc_value* value = tc_value_dict_get(&serialized, "value");
    TEST_ASSERT(value != nullptr, "serialized value present");
    TEST_ASSERT(value->type == TC_VALUE_INT, "serialized value is int");
    TEST_ASSERT(value->data.i == 321, "serialized value matches");

    tc_value update = tc_value_dict_new();
    tc_value_dict_set(&update, "value", tc_value_int(654));
    reg.deserialize_all(&component, "ReloadableComponent", &update, nullptr);
    TEST_ASSERT(component.value == 654, "registry deserialize restores value");

    tc_value_free(&update);
    tc_value_free(&serialized);

    std::cout << "  InspectRegistry roundtrip: PASS\n";
    return 0;
}

int test_degrade_upgrade_roundtrip() {
    std::cout << "Testing UnknownComponent degrade/upgrade roundtrip...\n";

    termin::TcSceneRef scene = termin::TcSceneRef::create("roundtrip");
    termin::Entity entity = scene.create_entity("entity");

    auto* component = new ReloadableComponent();
    TEST_ASSERT(component != nullptr, "reloadable component created manually");
    TEST_ASSERT(component->type_name() == nullptr, "type entry is not linked before add");
    component->value = 123;
    entity.add_component(component);
    TEST_ASSERT(component->type_name() != nullptr, "type entry linked on add");

    termin::UnknownComponentStats degraded =
        termin::degrade_components_to_unknown(scene, {"ReloadableComponent"});

    TEST_ASSERT(degraded.degraded == 1, "one component degraded");
    TEST_ASSERT(entity.get_component_by_type_name("ReloadableComponent") == nullptr, "original component removed");

    tc_component* unknown_tc = entity.get_component_by_type_name("UnknownComponent");
    TEST_ASSERT(unknown_tc != nullptr, "unknown component created");

    auto* unknown = static_cast<termin::UnknownComponent*>(termin::CxxComponent::from_tc(unknown_tc));
    TEST_ASSERT(unknown != nullptr, "unknown component cast succeeds");
    TEST_ASSERT(unknown->original_type == "ReloadableComponent", "original type preserved");

    TEST_ASSERT(unknown->original_data.type == TC_VALUE_DICT, "original data stored as dict");
    tc_value* stored_value = tc_value_dict_get(&unknown->original_data, "value");
    TEST_ASSERT(stored_value != nullptr, "stored value exists");
    TEST_ASSERT(stored_value->type == TC_VALUE_INT, "stored value is int");
    TEST_ASSERT(stored_value->data.i == 123, "stored value matches");

    termin::UnknownComponentStats upgraded = termin::upgrade_unknown_components(scene);
    TEST_ASSERT(upgraded.upgraded == 1, "one component upgraded");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") == nullptr, "unknown component removed");

    auto* restored = dynamic_cast<ReloadableComponent*>(entity.get_component<ReloadableComponent>());
    TEST_ASSERT(restored != nullptr, "reloadable component restored");
    TEST_ASSERT(restored->value == 123, "restored value matches");

    scene.destroy();
    std::cout << "  UnknownComponent roundtrip: PASS\n";
    return 0;
}

int test_degrade_filtering() {
    std::cout << "Testing UnknownComponent degrade filtering...\n";

    termin::TcSceneRef scene = termin::TcSceneRef::create("filtering");
    termin::Entity entity = scene.create_entity("entity");

    auto* reloadable = create_registered_component<ReloadableComponent>("ReloadableComponent");
    TEST_ASSERT(reloadable != nullptr, "reloadable component created from registry");
    reloadable->value = 10;
    entity.add_component(reloadable);

    auto* secondary = create_registered_component<SecondaryComponent>("SecondaryComponent");
    TEST_ASSERT(secondary != nullptr, "secondary component created from registry");
    secondary->amount = 77;
    entity.add_component(secondary);

    termin::UnknownComponentStats degraded =
        termin::degrade_components_to_unknown(scene, {"ReloadableComponent"});

    TEST_ASSERT(degraded.degraded == 1, "only one component degraded");
    TEST_ASSERT(entity.get_component_by_type_name("ReloadableComponent") == nullptr, "target component degraded");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") != nullptr, "unknown component present");

    auto* secondary_after = dynamic_cast<SecondaryComponent*>(entity.get_component<SecondaryComponent>());
    TEST_ASSERT(secondary_after != nullptr, "secondary component still present");
    TEST_ASSERT(secondary_after->amount == 77, "secondary component data preserved");

    termin::UnknownComponentStats upgraded =
        termin::upgrade_unknown_components(scene, {"ReloadableComponent"});

    TEST_ASSERT(upgraded.upgraded == 1, "filtered upgrade restored one component");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") == nullptr, "unknown component removed after upgrade");

    auto* reloadable_after = dynamic_cast<ReloadableComponent*>(entity.get_component<ReloadableComponent>());
    TEST_ASSERT(reloadable_after != nullptr, "reloadable component restored");
    TEST_ASSERT(reloadable_after->value == 10, "reloadable component data preserved");

    scene.destroy();
    std::cout << "  UnknownComponent filtering: PASS\n";
    return 0;
}

int test_upgrade_requires_registered_type() {
    std::cout << "Testing UnknownComponent upgrade after unregister/register...\n";

    termin::TcSceneRef scene = termin::TcSceneRef::create("reregister");
    termin::Entity entity = scene.create_entity("entity");

    auto* component = create_registered_component<ReloadableComponent>("ReloadableComponent");
    TEST_ASSERT(component != nullptr, "reloadable component created from registry");
    component->value = 456;
    entity.add_component(component);

    termin::UnknownComponentStats degraded =
        termin::degrade_components_to_unknown(scene, {"ReloadableComponent"});
    TEST_ASSERT(degraded.degraded == 1, "component degraded before unregister");

    termin::ComponentRegistry::instance().unregister("ReloadableComponent");

    termin::UnknownComponentStats failed_upgrade =
        termin::upgrade_unknown_components(scene, {"ReloadableComponent"});
    TEST_ASSERT(failed_upgrade.upgraded == 0, "upgrade blocked while type is unregistered");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") != nullptr, "unknown component remains after blocked upgrade");

    reregister_reloadable_component();

    termin::UnknownComponentStats upgraded =
        termin::upgrade_unknown_components(scene, {"ReloadableComponent"});
    TEST_ASSERT(upgraded.upgraded == 1, "upgrade succeeds after re-register");

    auto* restored = dynamic_cast<ReloadableComponent*>(entity.get_component<ReloadableComponent>());
    TEST_ASSERT(restored != nullptr, "reloadable component restored after re-register");
    TEST_ASSERT(restored->value == 456, "restored value preserved after re-register");

    scene.destroy();
    std::cout << "  UnknownComponent unregister/register: PASS\n";
    return 0;
}

int test_unknown_only_deserialization() {
    std::cout << "Testing UnknownOnly component deserialization...\n";

    termin::TcSceneRef scene = termin::TcSceneRef::create("unknown_only");
    const std::string json = R"({
        "entities": [{
            "uuid": "11111111-1111-1111-1111-111111111111",
            "name": "entity",
            "components": [{
                "type": "ReloadableComponent",
                "data": { "value": 987 }
            }]
        }]
    })";

    scene.from_json_string(
        json,
        termin::ComponentDeserializationMode::UnknownOnly);

    const auto entities = scene.get_all_entities();
    TEST_ASSERT(entities.size() == 1, "single entity created");
    termin::Entity entity = entities.front();
    TEST_ASSERT(entity.valid(), "entity created");
    TEST_ASSERT(entity.get_component_by_type_name("ReloadableComponent") == nullptr,
                "registered component not instantiated in UnknownOnly");

    tc_component* unknown_tc = entity.get_component_by_type_name("UnknownComponent");
    TEST_ASSERT(unknown_tc != nullptr, "UnknownComponent created");

    auto* unknown =
        static_cast<termin::UnknownComponent*>(termin::CxxComponent::from_tc(unknown_tc));
    TEST_ASSERT(unknown != nullptr, "UnknownComponent cast succeeds");
    TEST_ASSERT(unknown->original_type == "ReloadableComponent",
                "original type preserved in UnknownOnly");
    TEST_ASSERT(unknown->original_data.type == TC_VALUE_DICT,
                "original data stored as dict");

    tc_value* stored_value = tc_value_dict_get(&unknown->original_data, "value");
    TEST_ASSERT(stored_value != nullptr, "stored value present");
    TEST_ASSERT(stored_value->type == TC_VALUE_INT, "stored value is int");
    TEST_ASSERT(stored_value->data.i == 987, "stored value preserved");

    scene.destroy();
    std::cout << "  UnknownOnly deserialization: PASS\n";
    return 0;
}

int test_custom_upgrade_strategy() {
    std::cout << "Testing UnknownOnly custom upgrade strategy...\n";

    termin::TcSceneRef scene = termin::TcSceneRef::create("custom_upgrade");
    const std::string json = R"({
        "entities": [{
            "uuid": "22222222-2222-2222-2222-222222222222",
            "name": "entity",
            "components": [{
                "type": "ReloadableComponent",
                "data": { "value": 654 }
            }]
        }]
    })";

    termin::UnknownUpgradeStrategy strategy =
        [](const termin::UnknownComponent& unknown,
           const termin::Entity&,
           const termin::TcSceneRef&) -> termin::UnknownUpgradeDecision {
            if (unknown.original_type != "ReloadableComponent") {
                return termin::UnknownUpgradeDecision::default_upgrade();
            }

            tc_value* value = tc_value_dict_get(
                const_cast<tc_value*>(&unknown.original_data), "value");
            if (value == nullptr || value->type != TC_VALUE_INT) {
                return termin::UnknownUpgradeDecision::skip();
            }

            tc_value target_data = tc_value_dict_new();
            tc_value_dict_set(&target_data, "amount", tc_value_int(value->data.i + 1));
            auto decision = termin::UnknownUpgradeDecision::custom(
                "SecondaryComponent", &target_data);
            tc_value_free(&target_data);
            return decision;
        };

    scene.from_json_string(
        json,
        termin::ComponentDeserializationMode::UnknownOnly,
        strategy,
        true);

    const auto entities = scene.get_all_entities();
    TEST_ASSERT(entities.size() == 1, "single entity created");
    termin::Entity entity = entities.front();
    TEST_ASSERT(entity.valid(), "entity created");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") == nullptr,
                "UnknownComponent upgraded away");

    auto* upgraded =
        dynamic_cast<SecondaryComponent*>(entity.get_component<SecondaryComponent>());
    TEST_ASSERT(upgraded != nullptr, "custom target component created");
    TEST_ASSERT(upgraded->amount == 655, "custom payload applied");

    scene.destroy();
    std::cout << "  UnknownOnly custom upgrade: PASS\n";
    return 0;
}

int test_custom_upgrade_from_unregistered_source_type() {
    std::cout << "Testing custom upgrade from unregistered source type...\n";

    termin::TcSceneRef scene = termin::TcSceneRef::create("custom_upgrade_foreign");
    const std::string json = R"({
        "entities": [{
            "uuid": "33333333-3333-3333-3333-333333333333",
            "name": "entity",
            "components": [{
                "type": "ForeignComponent",
                "data": { "value": 700 }
            }]
        }]
    })";

    termin::UnknownUpgradeStrategy strategy =
        [](const termin::UnknownComponent& unknown,
           const termin::Entity&,
           const termin::TcSceneRef&) -> termin::UnknownUpgradeDecision {
            if (unknown.original_type != "ForeignComponent") {
                return termin::UnknownUpgradeDecision::default_upgrade();
            }

            tc_value* value = tc_value_dict_get(
                const_cast<tc_value*>(&unknown.original_data), "value");
            if (value == nullptr || value->type != TC_VALUE_INT) {
                return termin::UnknownUpgradeDecision::skip();
            }

            tc_value target_data = tc_value_dict_new();
            tc_value_dict_set(&target_data, "amount", tc_value_int(value->data.i + 2));
            auto decision = termin::UnknownUpgradeDecision::custom(
                "SecondaryComponent", &target_data);
            tc_value_free(&target_data);
            return decision;
        };

    scene.from_json_string(
        json,
        termin::ComponentDeserializationMode::UnknownOnly,
        strategy,
        true);

    const auto entities = scene.get_all_entities();
    TEST_ASSERT(entities.size() == 1, "single entity created");
    termin::Entity entity = entities.front();
    TEST_ASSERT(entity.valid(), "entity created");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") == nullptr,
                "UnknownComponent upgraded away");

    auto* upgraded =
        dynamic_cast<SecondaryComponent*>(entity.get_component<SecondaryComponent>());
    TEST_ASSERT(upgraded != nullptr, "target component created from foreign source");
    TEST_ASSERT(upgraded->amount == 702, "custom payload applied from foreign source");

    scene.destroy();
    std::cout << "  Custom upgrade from unregistered source: PASS\n";
    return 0;
}

} // namespace

int main() {
    tc::init_cpp_inspect_vtable();
    tc::register_builtin_cpp_kinds();

    int result = 0;
    result |= test_cpp_inspect_registry_roundtrip();
    result |= test_degrade_upgrade_roundtrip();
    result |= test_degrade_filtering();
    result |= test_upgrade_requires_registered_type();
    result |= test_unknown_only_deserialization();
    result |= test_custom_upgrade_strategy();
    result |= test_custom_upgrade_from_unregistered_source_type();

    if (result == 0) {
        std::cout << "\nAll UnknownComponent tests passed.\n";
    }

    return result;
}
