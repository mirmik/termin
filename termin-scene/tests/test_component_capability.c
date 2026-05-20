#include "guard_c.h"

#include "core/tc_component.h"
#include "core/tc_component_capability.h"
#include "core/tc_entity_pool.h"
#include "core/tc_entity_pool_registry.h"
#include "core/tc_scene.h"

static bool count_components(tc_component* c, void* user_data) {
    (void)c;
    int* count = (int*)user_data;
    (*count)++;
    return true;
}

GUARD_C_TEST(test_capability_register_and_attach) {
    tc_component_cap_id cap = tc_component_capability_register("test.capability");
    GUARD_C_REQUIRE(cap != TC_COMPONENT_CAPABILITY_INVALID_ID);
    GUARD_C_CHECK(tc_component_capability_valid(cap));
    GUARD_C_CHECK_EQ_UINT(cap, tc_component_capability_register("test.capability"));

    tc_component component;
    tc_component_init(&component, NULL);

    int marker = 42;
    GUARD_C_REQUIRE(tc_component_attach_capability(&component, cap, &marker));
    GUARD_C_CHECK(tc_component_has_capability(&component, cap));
    GUARD_C_CHECK_PTR_EQ(&marker, tc_component_get_capability(&component, cap));

    tc_component_detach_capability(&component, cap);
    GUARD_C_CHECK_FALSE(tc_component_has_capability(&component, cap));
    GUARD_C_CHECK_PTR_EQ(NULL, tc_component_get_capability(&component, cap));

    return 0;
}

GUARD_C_TEST(test_scene_capability_iteration) {
    tc_component_cap_id cap = tc_component_capability_register("test.scene_capability");
    GUARD_C_REQUIRE(cap != TC_COMPONENT_CAPABILITY_INVALID_ID);

    tc_scene_handle scene = tc_scene_new_named("capability-scene");
    GUARD_C_REQUIRE(tc_scene_alive(scene));

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    GUARD_C_REQUIRE(pool != NULL);

    tc_entity_id entity = tc_entity_pool_alloc(pool, "entity");
    GUARD_C_REQUIRE(tc_entity_id_valid(entity));

    tc_component component;
    tc_component_init(&component, NULL);

    int payload = 7;
    GUARD_C_REQUIRE(tc_component_attach_capability(&component, cap, &payload));

    tc_entity_pool_add_component(pool, entity, &component);
    GUARD_C_CHECK(tc_component_has_capability(&component, cap));
    GUARD_C_CHECK_EQ_INT(1, tc_scene_capability_count(scene, cap));

    int count = 0;
    tc_scene_foreach_with_capability(scene, cap, count_components, &count, TC_SCENE_FILTER_NONE);
    GUARD_C_CHECK_EQ_INT(1, count);

    tc_entity_pool_remove_component(pool, entity, &component);
    GUARD_C_CHECK_EQ_INT(0, tc_scene_capability_count(scene, cap));

    tc_scene_free(scene);

    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_capability_register_and_attach);
    GUARD_C_RUN(test_scene_capability_iteration);
    return GUARD_C_END();
}
