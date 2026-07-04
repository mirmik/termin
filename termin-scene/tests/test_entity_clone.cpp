#include <iostream>
#include <string>

#include <inspect/tc_inspect_context.h>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/tc_scene.hpp>

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

    tc_value serialize_data() const override {
        tc_value data = tc_value_dict_new();
        tc_value_dict_set(&data, "value", tc_value_int(value));
        tc_value target_value = target.serialize_to_value();
        tc_value_dict_set(&data, "target", target_value);
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
    }
};

static ::termin::ComponentRegistrar<CloneRefComponent>
    clone_ref_component_registrar("CloneRefComponent", "CxxComponent");

} // namespace

int main() {
    termin::TcSceneRef scene = termin::TcSceneRef::create("entity-clone-test");

    termin::Entity root = scene.create_entity("Root");
    root.set_pickable(true);
    root.set_selectable(true);
    double root_pos[3] = {1.0, 2.0, 3.0};
    root.set_local_position(root_pos);

    termin::Entity child = root.create_child("Child");
    child.set_pickable(false);
    child.set_selectable(false);
    child.set_serializable(false);
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
    root.add_component_ptr(raw_component);

    termin::Entity clone = root.clone("_ghost");
    TEST_ASSERT(clone.valid(), "clone root should be valid");
    TEST_ASSERT(clone != root, "clone root should be a different entity");
    TEST_ASSERT(std::string(clone.name()) == "Root_ghost", "clone root should use suffix");
    TEST_ASSERT(std::string(clone.uuid()) != std::string(root.uuid()), "clone root should have new uuid");
    TEST_ASSERT(clone.pickable() == root.pickable(), "clone should preserve pickable flag");
    TEST_ASSERT(clone.selectable() == root.selectable(), "clone should preserve selectable flag");

    termin::Entity cloned_child = clone.find_child("Child");
    TEST_ASSERT(cloned_child.valid(), "clone child should exist");
    TEST_ASSERT(cloned_child != child, "clone child should be a different entity");
    TEST_ASSERT(std::string(cloned_child.uuid()) != std::string(child.uuid()), "clone child should have new uuid");
    TEST_ASSERT(cloned_child.parent() == clone, "clone child parent should be cloned root");
    TEST_ASSERT(cloned_child.serializable() == child.serializable(), "clone child should preserve serializable flag");

    CloneRefComponent* cloned_component = clone.get_component<CloneRefComponent>();
    TEST_ASSERT(cloned_component != nullptr, "clone component should exist");
    TEST_ASSERT(cloned_component != component, "clone component should be a different instance");
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
    TEST_ASSERT(cloned_child_pos[0] == 4.0 && cloned_child_pos[1] == 5.0 && cloned_child_pos[2] == 6.0,
                "clone child should preserve local position");

    return 0;
}
