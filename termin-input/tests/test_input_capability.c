#include "guard_c.h"

#include "core/tc_component.h"
#include "core/tc_input_component.h"
#include <termin/input/tc_world_pointer_surface.h>

static const tc_input_vtable g_test_input_vtable = {0};

typedef struct world_surface_probe {
    unsigned project_count;
    unsigned dispatch_count;
    tc_world_pointer_event last_event;
} world_surface_probe;

static bool project_world_surface(
    tc_component* component,
    const tc_world_pointer_ray* ray,
    tc_world_pointer_hit* out_hit
) {
    const tc_world_pointer_surface_capability* capability =
        tc_world_pointer_surface_capability_get(component);
    world_surface_probe* probe =
        capability ? (world_surface_probe*)capability->userdata : NULL;
    if (!probe || !ray || !out_hit) return false;
    probe->project_count += 1;
    out_hit->distance = ray->max_distance * 0.5;
    out_hit->u = 0.25;
    out_hit->v = 0.75;
    out_hit->inside = true;
    return true;
}

static bool dispatch_world_pointer(
    tc_component* component,
    const tc_world_pointer_event* event
) {
    const tc_world_pointer_surface_capability* capability =
        tc_world_pointer_surface_capability_get(component);
    world_surface_probe* probe =
        capability ? (world_surface_probe*)capability->userdata : NULL;
    if (!probe || !event) return false;
    probe->dispatch_count += 1;
    probe->last_event = *event;
    return true;
}

static const tc_world_pointer_surface_vtable g_world_surface_vtable = {
    project_world_surface,
    dispatch_world_pointer,
};

GUARD_C_TEST(test_input_source_mask_defaults_and_updates) {
    tc_component component;
    tc_component_init(&component, NULL);
    GUARD_C_REQUIRE(tc_input_capability_attach(&component, &g_test_input_vtable));
    GUARD_C_CHECK_EQ_UINT(TC_INPUT_SOURCE_RUNTIME, tc_component_get_input_source_mask(&component));
    GUARD_C_CHECK(tc_component_accepts_input_source(&component, TC_INPUT_SOURCE_RUNTIME));
    GUARD_C_CHECK_FALSE(tc_component_accepts_input_source(&component, TC_INPUT_SOURCE_EDITOR));

    GUARD_C_REQUIRE(tc_component_set_input_source_mask(
        &component,
        TC_INPUT_SOURCE_RUNTIME | TC_INPUT_SOURCE_EDITOR
    ));
    GUARD_C_CHECK(tc_component_accepts_input_source(&component, TC_INPUT_SOURCE_EDITOR));

    tc_component_clear_capabilities(&component);
    return 0;
}

GUARD_C_TEST(test_world_pointer_surface_capability_routes_projection_and_events) {
    tc_component component;
    tc_component_init(&component, NULL);
    world_surface_probe probe = {0};
    GUARD_C_REQUIRE(tc_world_pointer_surface_capability_attach(
        &component, &g_world_surface_vtable, &probe));

    const tc_world_pointer_ray ray = {
        .direction_y = 1.0,
        .max_distance = 4.0,
    };
    tc_world_pointer_hit hit = {0};
    GUARD_C_REQUIRE(tc_world_pointer_surface_project_ray(
        &component, &ray, &hit));
    GUARD_C_CHECK_EQ_UINT(1, probe.project_count);
    GUARD_C_CHECK(hit.inside);
    GUARD_C_CHECK(hit.distance == 2.0);
    GUARD_C_CHECK(hit.u == 0.25);
    GUARD_C_CHECK(hit.v == 0.75);

    const tc_world_pointer_event event = {
        .pointer_id = 42,
        .phase = TC_WORLD_POINTER_DOWN,
        .u = hit.u,
        .v = hit.v,
        .pressure = 1.0f,
    };
    GUARD_C_REQUIRE(tc_world_pointer_surface_dispatch_pointer(
        &component, &event));
    GUARD_C_CHECK_EQ_UINT(1, probe.dispatch_count);
    GUARD_C_CHECK_EQ_UINT(42, probe.last_event.pointer_id);
    GUARD_C_CHECK_EQ_INT(TC_WORLD_POINTER_DOWN, probe.last_event.phase);

    tc_component_clear_capabilities(&component);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_input_source_mask_defaults_and_updates);
    GUARD_C_RUN(test_world_pointer_surface_capability_routes_projection_and_events);
    return GUARD_C_END();
}
