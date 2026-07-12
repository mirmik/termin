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

typedef struct {
    tc_component* items[4];
    int count;
} component_order;

static bool collect_component_order(tc_component* c, void* user_data) {
    component_order* order = (component_order*)user_data;
    if (order->count < 4) {
        order->items[order->count++] = c;
    }
    return true;
}

typedef struct {
    tc_component component;
    int removed_count;
    int removed_from_entity_count;
    int last_event;
} lifecycle_probe_component;

static void lifecycle_probe_on_removed(tc_component* component) {
    lifecycle_probe_component* probe = (lifecycle_probe_component*)component;
    probe->removed_count++;
    probe->last_event = 1;
}

static void lifecycle_probe_on_removed_from_entity(tc_component* component) {
    lifecycle_probe_component* probe = (lifecycle_probe_component*)component;
    probe->removed_from_entity_count++;
    probe->last_event = 2;
}

static const tc_component_vtable lifecycle_probe_vtable = {
    .on_removed_from_entity = lifecycle_probe_on_removed_from_entity,
    .on_removed = lifecycle_probe_on_removed,
};

static void lifecycle_probe_init(lifecycle_probe_component* probe) {
    memset(probe, 0, sizeof(*probe));
    tc_component_init(&probe->component, &lifecycle_probe_vtable);
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

GUARD_C_TEST(test_scene_capability_priority_iteration) {
    tc_component_cap_id cap = tc_component_capability_register("test.scene_capability_priority");
    GUARD_C_REQUIRE(cap != TC_COMPONENT_CAPABILITY_INVALID_ID);

    tc_scene_handle scene = tc_scene_new_named("capability-priority-scene");
    GUARD_C_REQUIRE(tc_scene_alive(scene));

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    GUARD_C_REQUIRE(pool != NULL);

    tc_entity_id entity = tc_entity_pool_alloc(pool, "entity");
    GUARD_C_REQUIRE(tc_entity_id_valid(entity));

    tc_component low;
    tc_component high;
    tc_component mid;
    tc_component_init(&low, NULL);
    tc_component_init(&high, NULL);
    tc_component_init(&mid, NULL);

    int low_payload = 1;
    int high_payload = 2;
    int mid_payload = 3;
    GUARD_C_REQUIRE(tc_component_attach_capability(&low, cap, &low_payload));
    GUARD_C_REQUIRE(tc_component_attach_capability(&high, cap, &high_payload));
    GUARD_C_REQUIRE(tc_component_attach_capability(&mid, cap, &mid_payload));
    GUARD_C_REQUIRE(tc_component_set_capability_priority(&low, cap, 0));
    GUARD_C_REQUIRE(tc_component_set_capability_priority(&high, cap, 10));
    GUARD_C_REQUIRE(tc_component_set_capability_priority(&mid, cap, 5));

    tc_entity_pool_add_component(pool, entity, &low);
    tc_entity_pool_add_component(pool, entity, &high);
    tc_entity_pool_add_component(pool, entity, &mid);
    GUARD_C_CHECK_EQ_INT(3, tc_scene_capability_count(scene, cap));

    component_order order = {0};
    tc_scene_foreach_with_capability(scene, cap, collect_component_order, &order, TC_SCENE_FILTER_NONE);
    GUARD_C_CHECK_EQ_INT(3, order.count);
    GUARD_C_CHECK_PTR_EQ(&high, order.items[0]);
    GUARD_C_CHECK_PTR_EQ(&mid, order.items[1]);
    GUARD_C_CHECK_PTR_EQ(&low, order.items[2]);

    GUARD_C_REQUIRE(tc_component_set_capability_priority(&low, cap, 20));

    order = (component_order){0};
    tc_scene_foreach_with_capability(scene, cap, collect_component_order, &order, TC_SCENE_FILTER_NONE);
    GUARD_C_CHECK_EQ_INT(3, order.count);
    GUARD_C_CHECK_PTR_EQ(&low, order.items[0]);
    GUARD_C_CHECK_PTR_EQ(&high, order.items[1]);
    GUARD_C_CHECK_PTR_EQ(&mid, order.items[2]);

    tc_entity_pool_remove_component(pool, entity, &low);
    tc_entity_pool_remove_component(pool, entity, &high);
    tc_entity_pool_remove_component(pool, entity, &mid);

    tc_scene_free(scene);

    return 0;
}

GUARD_C_TEST(test_component_removal_lifecycle_runs_once_in_order) {
    tc_scene_handle scene = tc_scene_new_named("component-removal-lifecycle");
    GUARD_C_REQUIRE(tc_scene_alive(scene));

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    GUARD_C_REQUIRE(pool != NULL);

    tc_entity_id direct_remove_entity = tc_entity_pool_alloc(pool, "direct-remove");
    GUARD_C_REQUIRE(tc_entity_id_valid(direct_remove_entity));
    lifecycle_probe_component direct_probe;
    lifecycle_probe_init(&direct_probe);
    tc_entity_pool_add_component(pool, direct_remove_entity, &direct_probe.component);
    tc_entity_pool_remove_component(pool, direct_remove_entity, &direct_probe.component);
    GUARD_C_CHECK_EQ_INT(1, direct_probe.removed_count);
    GUARD_C_CHECK_EQ_INT(1, direct_probe.removed_from_entity_count);
    GUARD_C_CHECK_EQ_INT(2, direct_probe.last_event);

    tc_entity_id entity_remove_entity = tc_entity_pool_alloc(pool, "entity-remove");
    GUARD_C_REQUIRE(tc_entity_id_valid(entity_remove_entity));
    lifecycle_probe_component entity_probe;
    lifecycle_probe_init(&entity_probe);
    tc_entity_pool_add_component(pool, entity_remove_entity, &entity_probe.component);
    tc_entity_pool_free(pool, entity_remove_entity);
    GUARD_C_CHECK_EQ_INT(1, entity_probe.removed_count);
    GUARD_C_CHECK_EQ_INT(1, entity_probe.removed_from_entity_count);
    GUARD_C_CHECK_EQ_INT(2, entity_probe.last_event);

    tc_scene_free(scene);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_capability_register_and_attach);
    GUARD_C_RUN(test_scene_capability_iteration);
    GUARD_C_RUN(test_scene_capability_priority_iteration);
    GUARD_C_RUN(test_component_removal_lifecycle_runs_once_in_order);
    return GUARD_C_END();
}
