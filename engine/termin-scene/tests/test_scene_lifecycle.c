#include "guard_c.h"

#include "core/tc_entity_pool_registry.h"
#include "core/tc_scene.h"
#include "core/tc_scene_pool.h"
#include "core/tc_component.h"
#include "core/tc_scene_extension.h"
#include "termin_scene/internal/tc_scene_extension_registry.h"

static void work_changed(void* userdata) { ++*(int*)userdata; }
static void demand_update(tc_component* component, float dt) { (void)component; (void)dt; }

typedef struct extension_demand { int updates; bool continuous; } extension_demand;
static void* demand_extension_create(tc_scene_handle scene, void* userdata) { (void)scene; return userdata; }
static void demand_extension_update(void* ext, double dt, void* userdata) {
    (void)dt; (void)userdata; ++((extension_demand*)ext)->updates;
}
static bool demand_extension_continuous(void* ext, void* userdata) {
    (void)userdata; return ((extension_demand*)ext)->continuous;
}

GUARD_C_TEST(test_extension_demand_preserves_periodic_hooks_and_allows_synchronization_only_hooks) {
    tc_scene_ext_registry_init();
    extension_demand regular = {0}, conditional = {0};
    tc_scene_ext_vtable regular_vtable = {0};
    regular_vtable.create = demand_extension_create;
    regular_vtable.on_scene_update = demand_extension_update;
    tc_scene_ext_vtable conditional_vtable = regular_vtable;
    conditional_vtable.requires_continuous_update = demand_extension_continuous;
    GUARD_C_REQUIRE(tc_scene_ext_register(TC_SCENE_EXT_TYPE_RENDER_MOUNT, "regular", "regular", &regular_vtable, &regular));
    GUARD_C_REQUIRE(tc_scene_ext_register(TC_SCENE_EXT_TYPE_RENDER_STATE, "conditional", "conditional", &conditional_vtable, &conditional));
    tc_scene_handle scene = tc_scene_new_named("extension-demand");
    tc_scene_set_mode(scene, TC_SCENE_MODE_STOP);
    GUARD_C_REQUIRE(tc_scene_ext_attach(scene, TC_SCENE_EXT_TYPE_RENDER_MOUNT));
    GUARD_C_REQUIRE(tc_scene_ext_attach(scene, TC_SCENE_EXT_TYPE_RENDER_STATE));
    GUARD_C_CHECK(tc_scene_get_work_state(scene).continuous_update);
    tc_scene_ext_detach(scene, TC_SCENE_EXT_TYPE_RENDER_MOUNT);
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).continuous_update);
    tc_scene_editor_update(scene, 0);
    GUARD_C_CHECK_EQ_INT(conditional.updates, 1);
    conditional.continuous = true;
    tc_scene_notify_work_changed(scene);
    GUARD_C_CHECK(tc_scene_get_work_state(scene).continuous_update);
    tc_scene_free(scene);
    tc_scene_pool_shutdown();
    tc_scene_ext_registry_shutdown();
    return 0;
}

GUARD_C_TEST(test_scene_work_state_preserves_requests_and_tracks_editor_callbacks) {
    tc_scene_handle scene = tc_scene_new_named("work-demand");
    tc_scene_set_mode(scene, TC_SCENE_MODE_STOP);
    int notifications = 0;
    tc_scene_set_work_callback(scene, work_changed, &notifications);
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).continuous_update);
    tc_scene_request_render(scene);
    GUARD_C_CHECK(tc_scene_get_work_state(scene).render_requested);
    GUARD_C_CHECK(tc_scene_get_work_state(scene).render_requested);
    GUARD_C_CHECK(tc_scene_consume_render_request(scene));
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).render_requested);

    tc_component_vtable vtable = {0};
    vtable.update = demand_update;
    tc_component component;
    tc_component_init(&component, &vtable);
    tc_scene_register_component(scene, &component);
    GUARD_C_CHECK(tc_scene_get_work_state(scene).pending_update);
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).continuous_update);
    tc_scene_editor_update(scene, 0);
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).pending_update);

    tc_component_set_active_in_editor(&component, true);
    GUARD_C_CHECK(tc_scene_get_work_state(scene).pending_update);
    GUARD_C_CHECK(tc_scene_get_work_state(scene).continuous_update);
    tc_scene_editor_update(scene, 0);
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).pending_update);
    tc_component_set_enabled(&component, false);
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).continuous_update);
    tc_component_set_enabled(&component, true);
    GUARD_C_CHECK(tc_scene_get_work_state(scene).continuous_update);
    tc_component_set_lifecycle_capabilities(&component, false, false, false);
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).continuous_update);
    tc_component_set_lifecycle_capabilities(&component, false, true, false);
    GUARD_C_CHECK(tc_scene_get_work_state(scene).continuous_update);
    tc_scene_unregister_component(scene, &component);
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).continuous_update);
    tc_scene_set_mode(scene, TC_SCENE_MODE_PLAY);
    GUARD_C_CHECK(tc_scene_get_work_state(scene).continuous_update);
    tc_scene_set_mode(scene, TC_SCENE_MODE_INACTIVE);
    GUARD_C_CHECK_FALSE(tc_scene_get_work_state(scene).continuous_update);
    GUARD_C_CHECK(notifications >= 8);
    tc_scene_set_work_callback(scene, NULL, NULL);
    tc_scene_free(scene);
    tc_scene_pool_shutdown();
    return 0;
}

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
    GUARD_C_RUN(test_scene_work_state_preserves_requests_and_tracks_editor_callbacks);
    GUARD_C_RUN(test_extension_demand_preserves_periodic_hooks_and_allows_synchronization_only_hooks);
    return GUARD_C_END();
}
