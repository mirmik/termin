#include <iostream>
#include <string>
#include <vector>

#include <inspect/tc_runtime_type_registry.h>
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
    ReloadableComponent()
        : termin::CxxComponent("ReloadableComponent") {}

    int value = 0;
};

class SecondaryComponent : public termin::CxxComponent {
public:
    SecondaryComponent()
        : termin::CxxComponent("SecondaryComponent") {}

    int amount = 0;
};

class RequiredBaseComponent : public termin::CxxComponent {
public:
    RequiredBaseComponent()
        : RequiredBaseComponent("RequiredBaseComponent") {}

protected:
    explicit RequiredBaseComponent(const char* type_name)
        : termin::CxxComponent(type_name) {}
};

class RequiredDerivedComponent : public RequiredBaseComponent {
public:
    RequiredDerivedComponent()
        : RequiredBaseComponent("RequiredDerivedComponent") {}
};

class NeedsBaseComponent : public termin::CxxComponent {
public:
    NeedsBaseComponent()
        : termin::CxxComponent("NeedsBaseComponent") {}
};

class CycleAComponent : public termin::CxxComponent {
public:
    CycleAComponent()
        : termin::CxxComponent("CycleAComponent") {}
};

class CycleBComponent : public termin::CxxComponent {
public:
    CycleBComponent()
        : termin::CxxComponent("CycleBComponent") {}
};

class OwnerScopedComponent : public termin::CxxComponent {
public:
    OwnerScopedComponent()
        : termin::CxxComponent("OwnerScopedComponent") {}

    int value = 0;
};

static ::termin::ComponentRegistrar<ReloadableComponent>
    reloadable_component_registrar("ReloadableComponent", "CxxComponent");
static ::termin::ComponentRegistrar<SecondaryComponent>
    secondary_component_registrar("SecondaryComponent", "CxxComponent");
static ::termin::ComponentRegistrar<RequiredBaseComponent>
    required_base_component_registrar("RequiredBaseComponent", "CxxComponent");
static ::termin::ComponentRegistrar<RequiredDerivedComponent>
    required_derived_component_registrar("RequiredDerivedComponent", "RequiredBaseComponent");
static ::termin::ComponentRegistrar<NeedsBaseComponent>
    needs_base_component_registrar("NeedsBaseComponent", "CxxComponent");
static ::termin::ComponentRegistrar<CycleAComponent>
    cycle_a_component_registrar("CycleAComponent", "CxxComponent");
static ::termin::ComponentRegistrar<CycleBComponent>
    cycle_b_component_registrar("CycleBComponent", "CxxComponent");
static ::termin::ComponentRequirementRegistrar
    needs_base_requirement_registrar("NeedsBaseComponent", "RequiredBaseComponent");
static ::termin::ComponentRequirementRegistrar
    cycle_a_requirement_registrar("CycleAComponent", "CycleBComponent");
static ::termin::ComponentRequirementRegistrar
    cycle_b_requirement_registrar("CycleBComponent", "CycleAComponent");

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

struct PrepareUnloadTestContext {
    std::vector<termin::TcSceneRef> scenes;
};

bool prepare_component_unload_for_test(
    const char* type_name,
    void* context,
    void*
) {
    auto* unload_context = static_cast<PrepareUnloadTestContext*>(context);
    if (!type_name || !unload_context) {
        return false;
    }

    for (const termin::TcSceneRef& scene : unload_context->scenes) {
        termin::UnknownComponentStats stats =
            termin::degrade_components_to_unknown(scene, {type_name});
        if (stats.failed > 0) {
            return false;
        }
    }

    return tc_component_registry_instance_count(type_name) == 0;
}

int test_module_owner_registration_cleanup() {
    std::cout << "Testing module-owned component and inspect cleanup...\n";

    constexpr const char* module_id = "owner_cleanup_test";
    auto& components = termin::ComponentRegistry::instance();
    auto& inspect = tc::InspectRegistry::instance();

    components.unregister("OwnerScopedComponent");
    inspect.unregister_type("OwnerScopedComponent");
    components.set_registration_owner(module_id);
    inspect.set_registration_owner(module_id);

    components.register_native(
        "OwnerScopedComponent",
        &termin::CxxComponentFactoryData<OwnerScopedComponent>::create,
        nullptr,
        "CxxComponent"
    );
    inspect.add<OwnerScopedComponent, int>(
        "OwnerScopedComponent",
        &OwnerScopedComponent::value,
        "value",
        "Value",
        "int"
    );

    TEST_ASSERT(components.owner_of("OwnerScopedComponent") == module_id,
                "component owner captured");
    TEST_ASSERT(inspect.owner_of("OwnerScopedComponent") == module_id,
                "inspect owner captured");
    TEST_ASSERT(components.has("OwnerScopedComponent"), "owned component registered");
    TEST_ASSERT(inspect.find_field("OwnerScopedComponent", "value") != nullptr,
                "owned inspect field registered");

    components.set_registration_owner("");
    inspect.set_registration_owner("");

    TEST_ASSERT(tc_runtime_type_registry_unregister_owner(module_id) == 1,
                "runtime owner cleanup count");
    TEST_ASSERT(!components.has("OwnerScopedComponent"), "owned component unregistered");
    TEST_ASSERT(inspect.find_field("OwnerScopedComponent", "value") == nullptr,
                "owned inspect field removed");
    TEST_ASSERT(tc_runtime_type_registry_unregister_owner(module_id) == 0,
                "runtime owner cleanup idempotent");

    components.register_native(
        "OwnerScopedComponent",
        &termin::CxxComponentFactoryData<OwnerScopedComponent>::create,
        nullptr,
        "CxxComponent"
    );
    TEST_ASSERT(components.owner_of("OwnerScopedComponent").empty(),
                "unowned component registration remains unowned");
    TEST_ASSERT(components.unregister_owner(module_id) == 0,
                "owner cleanup does not remove unowned component");
    TEST_ASSERT(components.has("OwnerScopedComponent"),
                "unowned component survives owner cleanup");
    components.unregister("OwnerScopedComponent");

    std::cout << "  Module owner cleanup: PASS\n";
    return 0;
}

int test_module_owner_cleanup_prepares_live_components() {
    std::cout << "Testing module owner cleanup prepares live components...\n";

    constexpr const char* module_id = "owner_prepare_unload_test";
    auto& components = termin::ComponentRegistry::instance();
    auto& inspect = tc::InspectRegistry::instance();

    components.unregister("OwnerScopedComponent");
    inspect.unregister_type("OwnerScopedComponent");
    components.set_registration_owner(module_id);
    inspect.set_registration_owner(module_id);

    components.register_native(
        "OwnerScopedComponent",
        &termin::CxxComponentFactoryData<OwnerScopedComponent>::create,
        nullptr,
        "CxxComponent"
    );
    inspect.add<OwnerScopedComponent, int>(
        "OwnerScopedComponent",
        &OwnerScopedComponent::value,
        "value",
        "Value",
        "int"
    );

    components.set_registration_owner("");
    inspect.set_registration_owner("");

    termin::TcSceneRef scene = termin::TcSceneRef::create("owner_prepare_unload");
    termin::Entity entity = scene.create_entity("entity");
    tc_component* component = tc_component_registry_create("OwnerScopedComponent");
    TEST_ASSERT(component != nullptr, "owned component instance created");
    auto* owner_scoped =
        dynamic_cast<OwnerScopedComponent*>(termin::CxxComponent::from_tc(component));
    TEST_ASSERT(owner_scoped != nullptr, "owned component instance cast succeeds");
    owner_scoped->value = 77;
    entity.add_component_ptr(component);
    TEST_ASSERT(tc_component_registry_instance_count("OwnerScopedComponent") == 1,
                "owned component live instance linked");

    PrepareUnloadTestContext context{{scene}};
    tc_component_registry_set_prepare_unload_callback(
        prepare_component_unload_for_test,
        nullptr
    );
    const size_t removed =
        tc_runtime_type_registry_unregister_owner_with_context(module_id, &context);
    tc_component_registry_set_prepare_unload_callback(nullptr, nullptr);

    TEST_ASSERT(removed == 1, "runtime owner cleanup removed prepared type");
    TEST_ASSERT(!components.has("OwnerScopedComponent"),
                "owned component registration removed after prepare");
    TEST_ASSERT(inspect.find_field("OwnerScopedComponent", "value") == nullptr,
                "owned inspect field removed after prepare");
    TEST_ASSERT(tc_component_registry_instance_count("OwnerScopedComponent") == 0,
                "owned component live instance unlinked by prepare");
    TEST_ASSERT(entity.get_component_by_type_name("OwnerScopedComponent") == nullptr,
                "original component removed from entity");

    tc_component* unknown_tc = entity.get_component_by_type_name("UnknownComponent");
    TEST_ASSERT(unknown_tc != nullptr, "UnknownComponent created by prepare");
    auto* unknown =
        static_cast<termin::UnknownComponent*>(termin::CxxComponent::from_tc(unknown_tc));
    TEST_ASSERT(unknown != nullptr, "UnknownComponent cast succeeds");
    TEST_ASSERT(unknown->original_type == "OwnerScopedComponent",
                "UnknownComponent preserves original type");
    tc_value* stored_value = tc_value_dict_get(&unknown->original_data, "value");
    TEST_ASSERT(stored_value != nullptr, "UnknownComponent stores owned value");
    TEST_ASSERT(stored_value->type == TC_VALUE_INT, "UnknownComponent value is int");
    TEST_ASSERT(stored_value->data.i == 77, "UnknownComponent value preserved");

    scene.destroy();
    std::cout << "  Module owner cleanup prepare: PASS\n";
    return 0;
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
    TEST_ASSERT(component->type_name() != nullptr, "manual component has declared type entry");
    size_t before_count = tc_component_registry_instance_count("ReloadableComponent");
    component->value = 123;
    component->set_display_name("Reloadable Label");
    entity.add_component(component);
    TEST_ASSERT(component->type_name() != nullptr, "type entry linked on add");
    TEST_ASSERT(tc_component_registry_instance_count("ReloadableComponent") == before_count + 1,
                "manual component instance is linked on add");

    termin::UnknownComponentStats degraded =
        termin::degrade_components_to_unknown(scene, {"ReloadableComponent"});

    TEST_ASSERT(degraded.degraded == 1, "one component degraded");
    TEST_ASSERT(entity.get_component_by_type_name("ReloadableComponent") == nullptr, "original component removed");
    TEST_ASSERT(tc_component_registry_instance_count("ReloadableComponent") == before_count,
                "original component instance is unlinked after degrade");

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
    TEST_ASSERT(std::string(tc_component_get_display_name(unknown_tc)) == "Reloadable Label",
                "display_name preserved on degrade");

    termin::UnknownComponentStats upgraded = termin::upgrade_unknown_components(scene);
    TEST_ASSERT(upgraded.upgraded == 1, "one component upgraded");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") == nullptr, "unknown component removed");

    auto* restored = dynamic_cast<ReloadableComponent*>(entity.get_component<ReloadableComponent>());
    TEST_ASSERT(restored != nullptr, "reloadable component restored");
    TEST_ASSERT(restored->value == 123, "restored value matches");
    TEST_ASSERT(restored->display_name() == "Reloadable Label", "display_name preserved on upgrade");

    tc_value restored_data = restored->serialize_data();
    tc_value* display_name = tc_value_dict_get(&restored_data, "display_name");
    TEST_ASSERT(display_name != nullptr, "display_name serialized when non-empty");
    TEST_ASSERT(display_name->type == TC_VALUE_STRING, "serialized display_name is string");
    TEST_ASSERT(std::string(display_name->data.s) == "Reloadable Label", "serialized display_name matches");
    tc_value_free(&restored_data);

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

int test_auto_add_required_component() {
    std::cout << "Testing automatic required component creation...\n";

    termin::TcSceneRef scene = termin::TcSceneRef::create("requirements");
    termin::Entity entity = scene.create_entity("entity");

    auto* needs = create_registered_component<NeedsBaseComponent>("NeedsBaseComponent");
    TEST_ASSERT(needs != nullptr, "dependent component created");
    entity.add_component(needs);

    TEST_ASSERT(entity.get_component_by_type_name("NeedsBaseComponent") != nullptr,
                "dependent component added");
    TEST_ASSERT(entity.get_component_by_type_name("RequiredBaseComponent") != nullptr,
                "required component auto-created");

    scene.destroy();
    std::cout << "  Automatic requirements: PASS\n";
    return 0;
}

int test_requirement_satisfied_by_derived_component() {
    std::cout << "Testing requirement satisfied by derived component...\n";

    termin::TcSceneRef scene = termin::TcSceneRef::create("requirements_derived");
    termin::Entity entity = scene.create_entity("entity");

    auto* derived = create_registered_component<RequiredDerivedComponent>("RequiredDerivedComponent");
    TEST_ASSERT(derived != nullptr, "derived required component created");
    entity.add_component(derived);

    auto* needs = create_registered_component<NeedsBaseComponent>("NeedsBaseComponent");
    TEST_ASSERT(needs != nullptr, "dependent component created");
    entity.add_component(needs);

    size_t base_like_count = 0;
    for (size_t i = 0; i < entity.component_count(); ++i) {
        tc_component* tc = entity.component_at(i);
        if (!tc) continue;
        if (termin::ComponentRegistry::instance().is_a(
                tc_component_type_name(tc), "RequiredBaseComponent")) {
            base_like_count++;
        }
    }

    TEST_ASSERT(base_like_count == 1,
                "derived component satisfies requirement without duplicate");

    scene.destroy();
    std::cout << "  Derived requirement satisfaction: PASS\n";
    return 0;
}

int test_requirement_cycle_blocks_add() {
    std::cout << "Testing component dependency cycle detection...\n";

    termin::TcSceneRef scene = termin::TcSceneRef::create("requirements_cycle");
    termin::Entity entity = scene.create_entity("entity");

    auto* cycle_a = create_registered_component<CycleAComponent>("CycleAComponent");
    TEST_ASSERT(cycle_a != nullptr, "cycle component created");
    entity.add_component(cycle_a);

    TEST_ASSERT(entity.get_component_by_type_name("CycleAComponent") == nullptr,
                "cycle root component not added");
    TEST_ASSERT(entity.get_component_by_type_name("CycleBComponent") == nullptr,
                "cycle dependency component not added");

    scene.destroy();
    std::cout << "  Dependency cycle detection: PASS\n";
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
    termin::register_builtin_scene_component_types();

    int result = 0;
    result |= test_cpp_inspect_registry_roundtrip();
    result |= test_degrade_upgrade_roundtrip();
    result |= test_degrade_filtering();
    result |= test_upgrade_requires_registered_type();
    result |= test_auto_add_required_component();
    result |= test_requirement_satisfied_by_derived_component();
    result |= test_requirement_cycle_blocks_add();
    result |= test_unknown_only_deserialization();
    result |= test_custom_upgrade_strategy();
    result |= test_custom_upgrade_from_unregistered_source_type();
    result |= test_module_owner_registration_cleanup();
    result |= test_module_owner_cleanup_prepares_live_components();

    if (result == 0) {
        std::cout << "\nAll UnknownComponent tests passed.\n";
    }

    return result;
}
