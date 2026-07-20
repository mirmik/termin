#include <iostream>
#include <string>
#include <unordered_map>

#include <inspect/tc_inspect_context.h>
#include <tcbase/tc_value_trent.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/unknown_component.hpp>
#include <termin/tc_scene.hpp>
#include <inspect/tc_inspect_init.h>

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n"; \
            return 1; \
        } \
    } while (0)

namespace {

class CloneRefComponent : public termin::CxxComponent {
public:
    CloneRefComponent()
        : termin::CxxComponent("CloneRefComponent") {}

    int value = 0;
    termin::Entity target;
    std::string plain_uuid_string;

    tc_value serialize_data() const override {
        tc_value data = tc_value_dict_new();
        tc_value_dict_set(&data, "value", tc_value_int(value));
        tc_value target_value = target.serialize_to_value();
        tc_value_dict_set(&data, "target", target_value);
        tc_value_dict_set(&data, "plain_uuid", tc_value_string(plain_uuid_string.c_str()));
        return data;
    }

    void deserialize_data(const tc_value* data, tc_scene_handle scene = TC_SCENE_HANDLE_INVALID) override {
        if (data == nullptr || data->type != TC_VALUE_DICT) {
            return;
        }

        tc_value* value_data = tc_value_dict_get(const_cast<tc_value*>(data), "value");
        if (value_data != nullptr && value_data->type == TC_VALUE_INT) {
            value = static_cast<int>(value_data->data.i);
        }

        tc_value* target_data = tc_value_dict_get(const_cast<tc_value*>(data), "target");
        tc_scene_inspect_context inspect_ctx = tc_scene_inspect_context_make(scene);
        target.deserialize_from(target_data, &inspect_ctx);

        tc_value* plain_uuid_data = tc_value_dict_get(const_cast<tc_value*>(data), "plain_uuid");
        if (plain_uuid_data != nullptr && plain_uuid_data->type == TC_VALUE_STRING && plain_uuid_data->data.s) {
            plain_uuid_string = plain_uuid_data->data.s;
        }
    }
};

int register_clone_ref_inspect_fields() {
    tc::register_cpp_handle_kind<termin::Entity>("entity");

    auto descriptor = termin::ComponentTypeDescriptorBuilder::native<CloneRefComponent>(
        "CloneRefComponent", "termin-scene-test");
    auto& inspect = descriptor.inspect();
    TEST_ASSERT((inspect.add<CloneRefComponent, int>(
        "CloneRefComponent", &CloneRefComponent::value, "value", "Value", "int")),
        "value field should stage");
    TEST_ASSERT((inspect.add<CloneRefComponent, termin::Entity>(
        "CloneRefComponent", &CloneRefComponent::target, "target", "Target", "entity")),
        "target field should stage");
    TEST_ASSERT((inspect.add<CloneRefComponent, std::string>(
        "CloneRefComponent", &CloneRefComponent::plain_uuid_string,
        "plain_uuid", "Plain UUID", "string")),
        "plain UUID field should stage");
    TEST_ASSERT(descriptor.commit(), "CloneRefComponent descriptor should commit");
    return 0;
}

} // namespace

int main() {
    tc_inspect_kind_core_init();
    termin::register_builtin_scene_component_types();
    TEST_ASSERT(register_clone_ref_inspect_fields() == 0,
                "CloneRefComponent descriptor should register");

    termin::TcSceneRef migration_scene = termin::TcSceneRef::create("entity-migration-test");
    termin::Entity standalone = termin::Entity::create_with_uuid(
        termin::Entity::standalone_pool(),
        "Standalone",
        "entity-migration-stable-uuid");
    TEST_ASSERT(standalone.valid(), "standalone entity with explicit UUID should be created");
    standalone.set_priority(17);
    const std::string standalone_uuid = standalone.uuid();
    termin::Entity migrated = migration_scene.migrate_entity(standalone);
    TEST_ASSERT(migrated.valid(), "scene migration should succeed");
    TEST_ASSERT(std::string(migrated.uuid()) == standalone_uuid,
                "scene migration should preserve UUID");
    TEST_ASSERT(migrated.priority() == 17, "scene migration should preserve stable fields");
    TEST_ASSERT(!standalone.valid(), "successful migration should invalidate the source handle");
    TEST_ASSERT(migration_scene.get_entity(standalone_uuid) == migrated,
                "destination UUID map should resolve the migrated entity");

    termin::Entity collision_source = termin::Entity::create_with_uuid(
        termin::Entity::standalone_pool(),
        "CollisionSource",
        "entity-migration-collision-uuid");
    termin::Entity collision_destination = termin::Entity::create_with_uuid(
        migration_scene.entity_pool(),
        "CollisionDestination",
        "entity-migration-collision-uuid");
    TEST_ASSERT(collision_source.valid() && collision_destination.valid(),
                "cross-pool UUID collision setup should succeed");
    TEST_ASSERT(!migration_scene.migrate_entity(collision_source).valid(),
                "migration should reject destination UUID collision");
    TEST_ASSERT(collision_source.valid(), "failed migration must preserve source entity");
    TEST_ASSERT(migration_scene.get_entity("entity-migration-collision-uuid") == collision_destination,
                "failed migration must preserve destination UUID map");

    termin::TcSceneRef scene = termin::TcSceneRef::create("entity-clone-test");

    termin::Entity parent = scene.create_entity("Parent");

    termin::Entity root = scene.create_entity("Root");
    root.set_parent(parent);
    root.set_pickable(true);
    root.set_selectable(true);
    double root_pos[3] = {1.0, 2.0, 3.0};
    root.set_local_position(root_pos);

    termin::Entity child = root.create_child("Child");
    child.set_pickable(false);
    child.set_selectable(false);
    double child_pos[3] = {4.0, 5.0, 6.0};
    child.set_local_position(child_pos);

    tc_component* raw_component = tc_component_registry_create("CloneRefComponent");
    TEST_ASSERT(raw_component != nullptr, "test component should be creatable");
    CloneRefComponent* component = dynamic_cast<CloneRefComponent*>(
        termin::CxxComponent::from_tc(raw_component)
    );
    TEST_ASSERT(component != nullptr, "test component should be a C++ component");
    component->value = 42;
    component->target = child;
    component->plain_uuid_string = child.uuid();
    root.add_component_ptr(raw_component);
    const std::string component_source_id = component->source_id();
    TEST_ASSERT(!component_source_id.empty(), "attached component should receive a source ID");

    nos::trent source_data = root.serialize_hierarchy();
    TEST_ASSERT(source_data.is_dict(), "hierarchy serialization should return a dict");
    TEST_ASSERT(source_data["uuid"].as_string() == std::string(root.uuid()),
                "hierarchy serialization should keep source root uuid");
    TEST_ASSERT(source_data["children"].as_list()[0]["uuid"].as_string() == std::string(child.uuid()),
                "hierarchy serialization should keep source child uuid");
    TEST_ASSERT(source_data["components"].as_list()[0]["data"]["target"]["uuid"].as_string() == std::string(child.uuid()),
                "hierarchy serialization should keep source entity refs");
    TEST_ASSERT(source_data["components"].as_list()[0]["source_id"].as_string() == component_source_id,
                "hierarchy serialization should keep component source identity");

    std::unordered_map<std::string, std::string> uuid_remap;
    nos::trent clone_data = termin::Entity::make_clone_payload(source_data, "_ghost", uuid_remap);
    TEST_ASSERT(clone_data.is_dict(), "clone payload should return a dict");
    TEST_ASSERT(clone_data.contains("children"), "clone payload should include children");
    const std::string cloned_child_uuid =
        clone_data["children"].as_list()[0]["uuid"].as_string();
    TEST_ASSERT(clone_data["components"].as_list()[0]["data"]["target"]["uuid"].as_string() == std::string(child.uuid()),
                "clone payload creation should not remap component entity refs");

    termin::Entity::remap_entity_refs(clone_data, uuid_remap);
    const std::string component_target_uuid =
        clone_data["components"].as_list()[0]["data"]["target"]["uuid"].as_string();
    TEST_ASSERT(component_target_uuid == cloned_child_uuid,
                "explicit entity ref remap should remap string entity refs to cloned entities");
    const std::string component_plain_uuid =
        clone_data["components"].as_list()[0]["data"]["plain_uuid"].as_string();
    TEST_ASSERT(component_plain_uuid == std::string(child.uuid()),
                "clone serialization should not remap untyped uuid-looking strings");

    termin::Entity clone = termin::Entity::deserialize_hierarchy(
        clone_data,
        scene.handle(),
        parent
    );
    TEST_ASSERT(clone.valid(), "clone root should be valid");
    TEST_ASSERT(clone != root, "clone root should be a different entity");
    TEST_ASSERT(std::string(clone.name()) == "Root_ghost", "clone root should use suffix");
    TEST_ASSERT(std::string(clone.uuid()) != std::string(root.uuid()), "clone root should have new uuid");
    TEST_ASSERT(clone.parent() == parent, "clone root should preserve original parent");
    TEST_ASSERT(clone.pickable() == root.pickable(), "clone should preserve pickable flag");
    TEST_ASSERT(clone.selectable() == root.selectable(), "clone should preserve selectable flag");

    termin::Entity cloned_child = clone.find_child("Child");
    TEST_ASSERT(cloned_child.valid(), "clone child should exist");
    TEST_ASSERT(cloned_child != child, "clone child should be a different entity");
    TEST_ASSERT(std::string(cloned_child.uuid()) != std::string(child.uuid()), "clone child should have new uuid");
    TEST_ASSERT(cloned_child.parent() == clone, "clone child parent should be cloned root");

    CloneRefComponent* cloned_component = clone.get_component<CloneRefComponent>();
    TEST_ASSERT(cloned_component != nullptr, "clone component should exist");
    TEST_ASSERT(cloned_component != component, "clone component should be a different instance");
    TEST_ASSERT(cloned_component->source_id() == component_source_id,
                "runtime clone should retain the component source identity");
    TEST_ASSERT(cloned_component->value == 42, "clone component should preserve scalar data");
    TEST_ASSERT(cloned_component->target.valid(), "clone component entity ref should resolve");
    TEST_ASSERT(cloned_component->target == cloned_child, "clone component entity ref should be remapped to cloned child");
    TEST_ASSERT(cloned_component->target != child, "clone component entity ref should not point to original child");

    double cloned_pos[3] = {};
    clone.get_local_position(cloned_pos);
    TEST_ASSERT(cloned_pos[0] == 1.0 && cloned_pos[1] == 2.0 && cloned_pos[2] == 3.0,
                "clone root should preserve local position");

    double cloned_child_pos[3] = {};
    cloned_child.get_local_position(cloned_child_pos);
    TEST_ASSERT(cloned_child_pos[0] == 4.0 && cloned_child_pos[1] == 5.0 &&
                    cloned_child_pos[2] == 6.0,
                "clone child should preserve local position");

    termin::TcSceneRef order_scene = termin::TcSceneRef::create("sibling-order-test");
    termin::Entity first = order_scene.create_entity("First");
    termin::Entity second = order_scene.create_entity("Second");
    termin::Entity third = order_scene.create_entity("Third");
    TEST_ASSERT(third.set_sibling_index(0), "root sibling reorder should report a change");
    std::vector<termin::Entity> roots = order_scene.get_root_entities();
    TEST_ASSERT(roots.size() == 3, "ordered scene should have three roots");
    TEST_ASSERT(roots[0] == third && roots[1] == first && roots[2] == second,
                "root entities should expose explicit sibling order");

    termin::Entity child_a = first.create_child("ChildA");
    termin::Entity child_b = first.create_child("ChildB");
    termin::Entity child_c = first.create_child("ChildC");
    TEST_ASSERT(child_c.set_sibling_index(1), "child sibling reorder should report a change");
    std::vector<termin::Entity> ordered_children = first.children();
    TEST_ASSERT(ordered_children[0] == child_a && ordered_children[1] == child_c &&
                    ordered_children[2] == child_b,
                "children should expose explicit sibling order");

    nos::trent order_data = order_scene.serialize();
    TEST_ASSERT(order_data["entities"].as_list()[0]["name"].as_string() == "Third",
                "scene serialization should preserve root order");
    TEST_ASSERT(order_data["entities"].as_list()[1]["children"].as_list()[1]["name"].as_string() ==
                    "ChildC",
                "scene serialization should preserve child order");

    termin::TcSceneRef restored_order_scene =
        termin::TcSceneRef::create("sibling-order-restored-test");
    TEST_ASSERT(restored_order_scene.load_from_data(order_data) == 6,
                "ordered scene should deserialize every entity");
    std::vector<termin::Entity> restored_roots = restored_order_scene.get_root_entities();
    TEST_ASSERT(std::string(restored_roots[0].name()) == "Third" &&
                    std::string(restored_roots[1].name()) == "First" &&
                    std::string(restored_roots[2].name()) == "Second",
                "scene roundtrip should preserve root order");
    std::vector<termin::Entity> restored_children = restored_roots[1].children();
    TEST_ASSERT(std::string(restored_children[0].name()) == "ChildA" &&
                    std::string(restored_children[1].name()) == "ChildC" &&
                    std::string(restored_children[2].name()) == "ChildB",
                "scene roundtrip should preserve child order");

    return 0;
}
