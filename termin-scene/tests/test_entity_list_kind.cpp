#include <any>
#include <iostream>
#include <string>
#include <vector>

#include <inspect/tc_inspect_context.h>
#include <termin/entity/entity.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>
#include <termin/tc_scene.hpp>

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n"; \
            return 1; \
        } \
    } while (0)

int main() {
    tc::register_cpp_handle_kind<termin::Entity>("entity");

    termin::TcSceneRef scene = termin::TcSceneRef::create("entity-list-kind-test");
    termin::Entity bone_a = scene.create_entity("bone_a");
    bone_a.set_uuid("bone-a-uuid");
    termin::Entity bone_b = scene.create_entity("bone_b");
    bone_b.set_uuid("bone-b-uuid");

    tc_value serialized = tc_value_list_new();

    tc_value bone_a_ref = tc_value_dict_new();
    tc_value_dict_set(&bone_a_ref, "uuid", tc_value_string("bone-a-uuid"));
    tc_value_list_push(&serialized, bone_a_ref);

    tc_value bone_b_ref = tc_value_dict_new();
    tc_value_dict_set(&bone_b_ref, "uuid", tc_value_string("bone-b-uuid"));
    tc_value_list_push(&serialized, bone_b_ref);

    tc_scene_inspect_context inspect_ctx = tc_scene_inspect_context_make(scene.handle());
    std::any deserialized = tc::KindRegistryCpp::instance().deserialize(
        "list[entity]",
        &serialized,
        &inspect_ctx
    );
    tc_value_free(&serialized);

    TEST_ASSERT(deserialized.has_value(), "list[entity] should deserialize to a value");

    std::vector<termin::Entity> entities;
    try {
        entities = std::any_cast<std::vector<termin::Entity>>(deserialized);
    } catch (const std::bad_any_cast&) {
        TEST_ASSERT(false, "list[entity] should deserialize to std::vector<termin::Entity>");
    }

    TEST_ASSERT(entities.size() == 2, "deserialized entity list size should match input");
    TEST_ASSERT(entities[0].valid(), "first entity ref should resolve in scene context");
    TEST_ASSERT(entities[1].valid(), "second entity ref should resolve in scene context");
    TEST_ASSERT(std::string(entities[0].uuid()) == std::string(bone_a.uuid()), "first uuid should match");
    TEST_ASSERT(std::string(entities[1].uuid()) == std::string(bone_b.uuid()), "second uuid should match");

    return 0;
}
