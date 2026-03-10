#include <stdio.h>
#include <string.h>

#include "core/tc_component.h"
#include "core/tc_component_capability.h"
#include "core/tc_entity_pool.h"
#include "core/tc_entity_pool_registry.h"
#include "core/tc_scene.h"

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            printf("FAIL: %s (line %d)\n", msg, __LINE__); \
            return 1; \
        } \
    } while (0)

static bool count_components(tc_component* c, void* user_data) {
    (void)c;
    int* count = (int*)user_data;
    (*count)++;
    return true;
}

static int test_capability_register_and_attach(void) {
    printf("Testing Component Capability Register/Attach...\n");

    tc_component_cap_id cap = tc_component_capability_register("test.capability");
    TEST_ASSERT(cap != TC_COMPONENT_CAPABILITY_INVALID_ID, "capability registered");
    TEST_ASSERT(tc_component_capability_valid(cap), "capability valid");
    TEST_ASSERT(tc_component_capability_register("test.capability") == cap, "duplicate returns same id");

    tc_component component;
    tc_component_init(&component, NULL);

    int marker = 42;
    TEST_ASSERT(tc_component_attach_capability(&component, cap, &marker), "attach capability");
    TEST_ASSERT(tc_component_has_capability(&component, cap), "component has capability");
    TEST_ASSERT(tc_component_get_capability(&component, cap) == &marker, "capability pointer stored");

    tc_component_detach_capability(&component, cap);
    TEST_ASSERT(!tc_component_has_capability(&component, cap), "capability detached");
    TEST_ASSERT(tc_component_get_capability(&component, cap) == NULL, "capability pointer cleared");

    printf("  Component Capability Register/Attach: PASS\n");
    return 0;
}

static int test_scene_capability_iteration(void) {
    printf("Testing Scene Capability Iteration...\n");

    tc_component_cap_id cap = tc_component_capability_register("test.scene_capability");
    TEST_ASSERT(cap != TC_COMPONENT_CAPABILITY_INVALID_ID, "scene capability registered");

    tc_scene_handle scene = tc_scene_new_named("capability-scene");
    TEST_ASSERT(tc_scene_alive(scene), "scene created");

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    TEST_ASSERT(pool != NULL, "scene pool exists");

    tc_entity_id entity = tc_entity_pool_alloc(pool, "entity");
    TEST_ASSERT(tc_entity_id_valid(entity), "entity created");

    tc_component component;
    tc_component_init(&component, NULL);

    int payload = 7;
    TEST_ASSERT(tc_component_attach_capability(&component, cap, &payload), "attach before add");

    tc_entity_pool_add_component(pool, entity, &component);
    TEST_ASSERT(tc_component_has_capability(&component, cap), "component still has capability");
    TEST_ASSERT(tc_scene_capability_count(scene, cap) == 1, "scene indexed capability");

    int count = 0;
    tc_scene_foreach_with_capability(scene, cap, count_components, &count, TC_SCENE_FILTER_NONE);
    TEST_ASSERT(count == 1, "scene iteration sees one capability component");

    tc_entity_pool_remove_component(pool, entity, &component);
    TEST_ASSERT(tc_scene_capability_count(scene, cap) == 0, "scene capability index cleared on remove");

    tc_scene_free(scene);

    printf("  Scene Capability Iteration: PASS\n");
    return 0;
}

int main(void) {
    int result = 0;

    result |= test_capability_register_and_attach();
    result |= test_scene_capability_iteration();

    if (result == 0) {
        printf("\nAll component capability tests PASSED\n");
    }

    return result;
}
