#include "guard_c.h"

#include "core/tc_entity_pool_registry.h"
#include "core/tc_scene.h"
#include "core/tc_scene_pool.h"

GUARD_C_TEST(test_scene_slot_reuse_resets_metadata_and_pool_generation) {
    tc_scene_handle first = tc_scene_new_named("first");
    GUARD_C_REQUIRE(tc_scene_alive(first));

    tc_entity_pool_handle first_pool = tc_scene_entity_pool_handle(first);
    GUARD_C_REQUIRE(tc_entity_pool_registry_alive(first_pool));
    GUARD_C_CHECK_PTR_EQ(tc_entity_pool_registry_get(first_pool), tc_scene_entity_pool(first));

    tc_scene_set_uuid(first, "scene-generation-one");
    tc_scene_set_source_path(first, "/tmp/generation-one.scene");
    tc_scene_set_fixed_timestep(first, 0.25);
    tc_scene_set_time_scale(first, 0.25);

    tc_scene_free(first);
    GUARD_C_CHECK_FALSE(tc_scene_alive(first));
    GUARD_C_CHECK_FALSE(tc_entity_pool_registry_alive(first_pool));

    tc_scene_handle second = tc_scene_new_named("second");
    GUARD_C_REQUIRE(tc_scene_alive(second));
    GUARD_C_CHECK_EQ_UINT(first.index, second.index);
    GUARD_C_CHECK_EQ_UINT(first.generation + 1, second.generation);

    tc_entity_pool_handle second_pool = tc_scene_entity_pool_handle(second);
    GUARD_C_REQUIRE(tc_entity_pool_registry_alive(second_pool));
    GUARD_C_CHECK_EQ_UINT(first_pool.index, second_pool.index);
    GUARD_C_CHECK_EQ_UINT(first_pool.generation + 1, second_pool.generation);
    GUARD_C_CHECK_PTR_EQ(tc_entity_pool_registry_get(second_pool), tc_scene_entity_pool(second));

    GUARD_C_CHECK_PTR_EQ(NULL, tc_scene_get_uuid(second));
    GUARD_C_CHECK_PTR_EQ(NULL, tc_scene_get_source_path(second));
    GUARD_C_CHECK(tc_scene_fixed_timestep(second) == 1.0 / 60.0);
    GUARD_C_CHECK(tc_scene_time_scale(second) == 1.0);
    tc_scene_free(second);
    tc_scene_pool_shutdown();
    return 0;
}

GUARD_C_TEST(test_entity_layer_rejects_values_outside_mask_range) {
    tc_entity_pool* pool = tc_entity_pool_create(1);
    GUARD_C_REQUIRE(pool != NULL);
    tc_entity_id entity = tc_entity_pool_alloc(pool, "classified");
    GUARD_C_REQUIRE(tc_entity_id_valid(entity));

    tc_entity_pool_set_layer(pool, entity, 63);
    GUARD_C_CHECK_EQ_UINT(63, tc_entity_pool_layer(pool, entity));
    tc_entity_pool_set_layer(pool, entity, 64);
    GUARD_C_CHECK_EQ_UINT(63, tc_entity_pool_layer(pool, entity));
    tc_entity_pool_set_layer(pool, entity, UINT64_MAX);
    GUARD_C_CHECK_EQ_UINT(63, tc_entity_pool_layer(pool, entity));

    tc_entity_pool_destroy(pool);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_scene_slot_reuse_resets_metadata_and_pool_generation);
    GUARD_C_RUN(test_entity_layer_rejects_values_outside_mask_range);
    return GUARD_C_END();
}
