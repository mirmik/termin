#include <iostream>
#include <string>

#include <inspect/tc_inspect_context.h>
#include <inspect/tc_inspect_init.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>
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

    termin::prefab::PrefabInstantiateResult first =
        termin::prefab::PrefabInstantiator::instantiate(source, scene.handle(), parent);
    termin::prefab::PrefabInstantiateResult second =
        termin::prefab::PrefabInstantiator::instantiate(source, scene.handle(), parent);

    TEST_ASSERT(first.ok() && second.ok(), "two prefab instances should be created");
    TEST_ASSERT(first.root.parent() == parent && second.root.parent() == parent,
                "instances should attach to the requested parent");
    TEST_ASSERT(first.root.pool() == scene.entity_pool() && second.root.pool() == scene.entity_pool(),
                "instances should be allocated directly in the target scene");
    TEST_ASSERT(std::string(first.root.uuid()) != std::string(second.root.uuid()),
                "instance root UUIDs should differ");
    TEST_ASSERT(std::string(first.root.uuid()) != source["uuid"].as_string(),
                "instance UUID should differ from source UUID");

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

    return 0;
}
