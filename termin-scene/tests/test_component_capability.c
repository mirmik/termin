#include "guard_c.h"

#include "core/tc_component.h"
#include "core/tc_component_capability.h"
#include "core/tc_entity_pool.h"
#include "core/tc_entity_pool_registry.h"
#include "core/tc_scene.h"
#include <tc_profiler.h>

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

typedef struct {
    tc_component component;
    int start_count;
    int update_count;
    int fixed_update_count;
    int before_render_count;
} scheduler_probe_component;

static void scheduler_probe_start(tc_component* component) {
    ((scheduler_probe_component*)component)->start_count++;
}

static void scheduler_probe_update(tc_component* component, float dt) {
    (void)dt;
    ((scheduler_probe_component*)component)->update_count++;
}

static void scheduler_probe_fixed_update(tc_component* component, float dt) {
    (void)dt;
    ((scheduler_probe_component*)component)->fixed_update_count++;
}

static void scheduler_probe_before_render(tc_component* component) {
    ((scheduler_probe_component*)component)->before_render_count++;
}

static const tc_component_vtable scheduler_probe_vtable = {
    .start = scheduler_probe_start,
    .update = scheduler_probe_update,
    .fixed_update = scheduler_probe_fixed_update,
    .before_render = scheduler_probe_before_render,
};

static void scheduler_probe_init(scheduler_probe_component* probe) {
    memset(probe, 0, sizeof(*probe));
    tc_component_init(&probe->component, &scheduler_probe_vtable);
    tc_component_set_declared_type_name(&probe->component, "SchedulerProbe");
    tc_component_set_lifecycle_capabilities(&probe->component, false, false, false);
}

static const tc_section_timing* find_profile_section(
    const tc_frame_profile* frame,
    int parent_index,
    const char* name
) {
    for (int i = 0; i < frame->section_count; i++) {
        const tc_section_timing* section = &frame->sections[i];
        if (section->parent_index == parent_index &&
            strcmp(section->name, name) == 0) {
            return section;
        }
    }
    return NULL;
}

static int profile_section_index(
    const tc_frame_profile* frame,
    const tc_section_timing* section
) {
    return section ? (int)(section - frame->sections) : -1;
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

GUARD_C_TEST(test_attached_lifecycle_capabilities_reindex_scene_scheduler) {
    tc_scene_handle scene = tc_scene_new_named("lifecycle-reindex");
    GUARD_C_REQUIRE(tc_scene_alive(scene));
    tc_scene_set_fixed_timestep(scene, 1.0);

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    GUARD_C_REQUIRE(pool != NULL);
    tc_entity_id entity = tc_entity_pool_alloc(pool, "entity");
    GUARD_C_REQUIRE(tc_entity_id_valid(entity));

    scheduler_probe_component probe;
    scheduler_probe_init(&probe);
    tc_entity_pool_add_component(pool, entity, &probe.component);
    GUARD_C_CHECK_EQ_INT(0, tc_scene_update_list_count(scene));
    GUARD_C_CHECK_EQ_INT(0, tc_scene_fixed_update_list_count(scene));
    GUARD_C_CHECK_EQ_INT(0, tc_scene_before_render_list_count(scene));

    tc_component_set_lifecycle_capabilities(&probe.component, true, true, true);
    GUARD_C_CHECK_EQ_INT(1, tc_scene_update_list_count(scene));
    GUARD_C_CHECK_EQ_INT(1, tc_scene_fixed_update_list_count(scene));
    GUARD_C_CHECK_EQ_INT(1, tc_scene_before_render_list_count(scene));

    tc_scene_update(scene, 1.0);
    tc_scene_before_render(scene);
    GUARD_C_CHECK_EQ_INT(1, probe.update_count);
    GUARD_C_CHECK_EQ_INT(1, probe.fixed_update_count);
    GUARD_C_CHECK_EQ_INT(1, probe.before_render_count);

    tc_component_set_lifecycle_capabilities(&probe.component, false, false, false);
    GUARD_C_CHECK_EQ_INT(0, tc_scene_update_list_count(scene));
    GUARD_C_CHECK_EQ_INT(0, tc_scene_fixed_update_list_count(scene));
    GUARD_C_CHECK_EQ_INT(0, tc_scene_before_render_list_count(scene));

    tc_scene_update(scene, 1.0);
    tc_scene_before_render(scene);
    GUARD_C_CHECK_EQ_INT(1, probe.update_count);
    GUARD_C_CHECK_EQ_INT(1, probe.fixed_update_count);
    GUARD_C_CHECK_EQ_INT(1, probe.before_render_count);

    scheduler_probe_component direct_probe;
    scheduler_probe_init(&direct_probe);
    tc_scene_register_component(scene, &direct_probe.component);
    tc_component_set_lifecycle_capabilities(
        &direct_probe.component, true, false, true
    );
    GUARD_C_CHECK_EQ_INT(1, tc_scene_update_list_count(scene));
    GUARD_C_CHECK_EQ_INT(0, tc_scene_fixed_update_list_count(scene));
    GUARD_C_CHECK_EQ_INT(1, tc_scene_before_render_list_count(scene));
    tc_scene_unregister_component(scene, &direct_probe.component);
    GUARD_C_CHECK_EQ_INT(0, tc_scene_update_list_count(scene));
    GUARD_C_CHECK_EQ_INT(0, tc_scene_before_render_list_count(scene));

    tc_scene_free(scene);
    return 0;
}

GUARD_C_TEST(test_scene_update_profiles_lifecycle_phase_and_component_instance) {
    tc_scene_handle scene = tc_scene_new_named("profiled-lifecycle");
    GUARD_C_REQUIRE(tc_scene_alive(scene));
    tc_scene_set_fixed_timestep(scene, 1.0);

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    GUARD_C_REQUIRE(pool != NULL);
    tc_entity_id alpha = tc_entity_pool_alloc(pool, "alpha");
    tc_entity_id beta = tc_entity_pool_alloc(pool, "beta");
    GUARD_C_REQUIRE(tc_entity_id_valid(alpha));
    GUARD_C_REQUIRE(tc_entity_id_valid(beta));

    scheduler_probe_component alpha_probe;
    scheduler_probe_component beta_probe;
    scheduler_probe_init(&alpha_probe);
    scheduler_probe_init(&beta_probe);
    tc_component_set_lifecycle_capabilities(&alpha_probe.component, true, true, false);
    tc_component_set_lifecycle_capabilities(&beta_probe.component, true, true, false);
    tc_component_set_source_id(&alpha_probe.component, "source-a");
    tc_component_set_source_id(&beta_probe.component, "source-b");
    alpha_probe.component.active_in_editor = true;
    beta_probe.component.active_in_editor = true;
    tc_entity_pool_add_component(pool, alpha, &alpha_probe.component);
    tc_entity_pool_add_component(pool, beta, &beta_probe.component);

    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    tc_profiler_begin_frame();
    tc_scene_update(scene, 2.0);
    tc_profiler_end_frame();

    const tc_frame_profile* frame = tc_profiler_history_at(0);
    GUARD_C_REQUIRE(frame != NULL);
    const tc_section_timing* start = find_profile_section(frame, -1, "Start");
    const tc_section_timing* fixed = find_profile_section(frame, -1, "Fixed Update");
    const tc_section_timing* update = find_profile_section(frame, -1, "Update");
    const tc_section_timing* extensions = find_profile_section(frame, -1, "Extensions");
    GUARD_C_REQUIRE(start != NULL);
    GUARD_C_REQUIRE(fixed != NULL);
    GUARD_C_REQUIRE(update != NULL);
    GUARD_C_REQUIRE(extensions != NULL);

    const int start_index = profile_section_index(frame, start);
    const int fixed_index = profile_section_index(frame, fixed);
    const int update_index = profile_section_index(frame, update);
    const char* alpha_name = "SchedulerProbe @ alpha [source-a]";
    const char* beta_name = "SchedulerProbe @ beta [source-b]";
    const tc_section_timing* alpha_start = find_profile_section(frame, start_index, alpha_name);
    const tc_section_timing* beta_start = find_profile_section(frame, start_index, beta_name);
    const tc_section_timing* alpha_fixed = find_profile_section(frame, fixed_index, alpha_name);
    const tc_section_timing* beta_fixed = find_profile_section(frame, fixed_index, beta_name);
    const tc_section_timing* alpha_update = find_profile_section(frame, update_index, alpha_name);
    const tc_section_timing* beta_update = find_profile_section(frame, update_index, beta_name);
    GUARD_C_REQUIRE(alpha_start != NULL);
    GUARD_C_REQUIRE(beta_start != NULL);
    GUARD_C_REQUIRE(alpha_fixed != NULL);
    GUARD_C_REQUIRE(beta_fixed != NULL);
    GUARD_C_REQUIRE(alpha_update != NULL);
    GUARD_C_REQUIRE(beta_update != NULL);
    GUARD_C_CHECK_EQ_INT(1, alpha_start->call_count);
    GUARD_C_CHECK_EQ_INT(1, beta_start->call_count);
    GUARD_C_CHECK_EQ_INT(2, alpha_fixed->call_count);
    GUARD_C_CHECK_EQ_INT(2, beta_fixed->call_count);
    GUARD_C_CHECK_EQ_INT(1, alpha_update->call_count);
    GUARD_C_CHECK_EQ_INT(1, beta_update->call_count);

    tc_profiler_clear_history();
    tc_profiler_begin_frame();
    tc_scene_editor_update(scene, 1.0);
    tc_profiler_end_frame();
    frame = tc_profiler_history_at(0);
    GUARD_C_REQUIRE(frame != NULL);
    fixed = find_profile_section(frame, -1, "Fixed Update");
    update = find_profile_section(frame, -1, "Update");
    GUARD_C_REQUIRE(fixed != NULL);
    GUARD_C_REQUIRE(update != NULL);
    alpha_fixed = find_profile_section(
        frame, profile_section_index(frame, fixed), alpha_name);
    beta_fixed = find_profile_section(
        frame, profile_section_index(frame, fixed), beta_name);
    alpha_update = find_profile_section(
        frame, profile_section_index(frame, update), alpha_name);
    beta_update = find_profile_section(
        frame, profile_section_index(frame, update), beta_name);
    GUARD_C_REQUIRE(alpha_fixed != NULL);
    GUARD_C_REQUIRE(beta_fixed != NULL);
    GUARD_C_REQUIRE(alpha_update != NULL);
    GUARD_C_REQUIRE(beta_update != NULL);
    GUARD_C_CHECK_EQ_INT(1, alpha_fixed->call_count);
    GUARD_C_CHECK_EQ_INT(1, beta_fixed->call_count);
    GUARD_C_CHECK_EQ_INT(1, alpha_update->call_count);
    GUARD_C_CHECK_EQ_INT(1, beta_update->call_count);

    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    tc_scene_free(scene);
    return 0;
}

GUARD_C_TEST(test_component_reorder_preserves_attachment_and_lifecycle) {
    tc_scene_handle scene = tc_scene_new_named("component-reorder");
    GUARD_C_REQUIRE(tc_scene_alive(scene));
    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    GUARD_C_REQUIRE(pool != NULL);
    tc_entity_id entity = tc_entity_pool_alloc(pool, "entity");
    GUARD_C_REQUIRE(tc_entity_id_valid(entity));

    lifecycle_probe_component first;
    lifecycle_probe_component second;
    lifecycle_probe_component third;
    lifecycle_probe_init(&first);
    lifecycle_probe_init(&second);
    lifecycle_probe_init(&third);
    tc_entity_pool_add_component(pool, entity, &first.component);
    tc_entity_pool_add_component(pool, entity, &second.component);
    tc_entity_pool_add_component(pool, entity, &third.component);

    GUARD_C_CHECK_EQ_UINT(0, tc_entity_pool_component_index(
        pool, entity, &first.component));
    GUARD_C_REQUIRE(tc_entity_pool_set_component_index(
        pool, entity, &third.component, 0));
    GUARD_C_CHECK_PTR_EQ(&third.component,
                         tc_entity_pool_component_at(pool, entity, 0));
    GUARD_C_CHECK_PTR_EQ(&first.component,
                         tc_entity_pool_component_at(pool, entity, 1));
    GUARD_C_CHECK_PTR_EQ(&second.component,
                         tc_entity_pool_component_at(pool, entity, 2));
    GUARD_C_CHECK_EQ_INT(0, first.removed_count);
    GUARD_C_CHECK_EQ_INT(0, second.removed_count);
    GUARD_C_CHECK_EQ_INT(0, third.removed_count);
    GUARD_C_CHECK(tc_entity_handle_eq(first.component.owner,
                                      tc_entity_handle_make(
                                          tc_entity_pool_registry_find(pool), entity)));

    tc_entity_pool_remove_component(pool, entity, &first.component);
    GUARD_C_CHECK_PTR_EQ(&third.component,
                         tc_entity_pool_component_at(pool, entity, 0));
    GUARD_C_CHECK_PTR_EQ(&second.component,
                         tc_entity_pool_component_at(pool, entity, 1));

    tc_scene_free(scene);
    return 0;
}

GUARD_C_TEST(test_checked_parent_rejects_cycle) {
    tc_scene_handle scene = tc_scene_new_named("checked-parent");
    GUARD_C_REQUIRE(tc_scene_alive(scene));
    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    GUARD_C_REQUIRE(pool != NULL);
    tc_entity_id root = tc_entity_pool_alloc(pool, "root");
    tc_entity_id child = tc_entity_pool_alloc(pool, "child");
    tc_entity_id grandchild = tc_entity_pool_alloc(pool, "grandchild");
    GUARD_C_REQUIRE(tc_entity_pool_set_parent_checked(pool, child, root));
    GUARD_C_REQUIRE(tc_entity_pool_set_parent_checked(pool, grandchild, child));
    GUARD_C_CHECK_FALSE(tc_entity_pool_set_parent_checked(pool, root, grandchild));
    GUARD_C_CHECK_FALSE(tc_entity_id_valid(tc_entity_pool_parent(pool, root)));
    GUARD_C_CHECK(tc_entity_id_eq(root, tc_entity_pool_parent(pool, child)));
    GUARD_C_CHECK(tc_entity_id_eq(child, tc_entity_pool_parent(pool, grandchild)));
    tc_scene_free(scene);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_capability_register_and_attach);
    GUARD_C_RUN(test_scene_capability_iteration);
    GUARD_C_RUN(test_scene_capability_priority_iteration);
    GUARD_C_RUN(test_component_removal_lifecycle_runs_once_in_order);
    GUARD_C_RUN(test_attached_lifecycle_capabilities_reindex_scene_scheduler);
    GUARD_C_RUN(test_scene_update_profiles_lifecycle_phase_and_component_instance);
    GUARD_C_RUN(test_component_reorder_preserves_attachment_and_lifecycle);
    GUARD_C_RUN(test_checked_parent_rejects_cycle);
    return GUARD_C_END();
}
