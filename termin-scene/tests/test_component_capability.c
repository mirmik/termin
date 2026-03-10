#include <stdio.h>
#include <string.h>

#include "core/tc_component.h"
#include "core/tc_component_capability.h"
#include "core/tc_drawable_capability.h"
#include "core/tc_input_capability.h"
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

static bool g_draw_called = false;

static bool test_drawable_has_phase(tc_component* self, const char* phase_mark) {
    (void)self;
    return phase_mark && strcmp(phase_mark, "opaque") == 0;
}

static void test_drawable_draw_geometry(tc_component* self, void* render_context, int geometry_id) {
    (void)self;
    (void)render_context;
    (void)geometry_id;
    g_draw_called = true;
}

static void* test_drawable_get_geometry_draws(tc_component* self, const char* phase_mark) {
    (void)self;
    (void)phase_mark;
    return (void*)0x1;
}

static tc_shader_handle test_drawable_override_shader(tc_component* self, const char* phase_mark, int geometry_id, tc_shader_handle original_shader) {
    (void)self;
    (void)phase_mark;
    (void)geometry_id;
    return original_shader;
}

static const tc_drawable_vtable g_test_drawable_vtable = {
    .has_phase = test_drawable_has_phase,
    .draw_geometry = test_drawable_draw_geometry,
    .get_geometry_draws = test_drawable_get_geometry_draws,
    .override_shader = test_drawable_override_shader,
};

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
    tc_scene_foreach_with_capability(scene, cap, count_components, &count, TC_DRAWABLE_FILTER_NONE);
    TEST_ASSERT(count == 1, "scene iteration sees one capability component");

    tc_entity_pool_remove_component(pool, entity, &component);
    TEST_ASSERT(tc_scene_capability_count(scene, cap) == 0, "scene capability index cleared on remove");

    tc_scene_free(scene);

    printf("  Scene Capability Iteration: PASS\n");
    return 0;
}

static int test_live_reindex_for_input_capability(void) {
    printf("Testing Live Reindex For Input Capability...\n");

    tc_component_cap_id input_cap = tc_input_capability_id();
    TEST_ASSERT(input_cap != TC_COMPONENT_CAPABILITY_INVALID_ID, "input capability id ok");

    tc_scene_handle scene = tc_scene_new_named("live-reindex-scene");
    TEST_ASSERT(tc_scene_alive(scene), "scene created");

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    tc_entity_id entity = tc_entity_pool_alloc(pool, "entity");
    TEST_ASSERT(tc_entity_id_valid(entity), "entity created");

    tc_component component;
    tc_component_init(&component, NULL);

    tc_entity_pool_add_component(pool, entity, &component);
    TEST_ASSERT(tc_scene_capability_count(scene, input_cap) == 0, "no input capability initially");

    int payload = 55;
    TEST_ASSERT(tc_component_attach_capability(&component, input_cap, &payload), "attach live capability");
    TEST_ASSERT(tc_scene_capability_count(scene, input_cap) == 1, "live reindex adds capability");

    tc_component_detach_capability(&component, input_cap);
    TEST_ASSERT(tc_scene_capability_count(scene, input_cap) == 0, "live reindex removes capability");

    tc_entity_pool_remove_component(pool, entity, &component);
    tc_scene_free(scene);

    printf("  Live Reindex For Input Capability: PASS\n");
    return 0;
}

static int test_live_reindex_for_drawable_capability(void) {
    printf("Testing Live Reindex For Drawable Capability...\n");

    tc_component_cap_id drawable_cap = tc_drawable_capability_id();
    TEST_ASSERT(drawable_cap != TC_COMPONENT_CAPABILITY_INVALID_ID, "drawable capability id ok");

    tc_scene_handle scene = tc_scene_new_named("drawable-reindex-scene");
    TEST_ASSERT(tc_scene_alive(scene), "scene created");

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    tc_entity_id entity = tc_entity_pool_alloc(pool, "entity");
    TEST_ASSERT(tc_entity_id_valid(entity), "entity created");

    tc_component component;
    tc_component_init(&component, NULL);

    tc_entity_pool_add_component(pool, entity, &component);
    TEST_ASSERT(tc_scene_capability_count(scene, drawable_cap) == 0, "no drawable capability initially");

    TEST_ASSERT(tc_drawable_capability_attach(&component, &g_test_drawable_vtable), "attach live drawable capability");
    TEST_ASSERT(tc_scene_capability_count(scene, drawable_cap) == 1, "live reindex adds drawable capability");
    TEST_ASSERT(tc_component_is_drawable(&component), "component is drawable");
    TEST_ASSERT(tc_component_has_phase(&component, "opaque"), "phase dispatch works");
    TEST_ASSERT(tc_component_get_geometry_draws(&component, "opaque") == (void*)0x1, "geometry draw retrieval works");

    g_draw_called = false;
    tc_component_draw_geometry(&component, NULL, 0);
    TEST_ASSERT(g_draw_called, "draw dispatch works");

    tc_component_detach_capability(&component, drawable_cap);
    TEST_ASSERT(tc_scene_capability_count(scene, drawable_cap) == 0, "live reindex removes drawable capability");

    tc_entity_pool_remove_component(pool, entity, &component);
    tc_scene_free(scene);

    printf("  Live Reindex For Drawable Capability: PASS\n");
    return 0;
}

int main(void) {
    int result = 0;

    result |= test_capability_register_and_attach();
    result |= test_scene_capability_iteration();
    result |= test_live_reindex_for_input_capability();
    result |= test_live_reindex_for_drawable_capability();

    if (result == 0) {
        printf("\nAll component capability tests PASSED\n");
    }

    return result;
}
