#ifndef TC_WORLD_POINTER_SURFACE_H
#define TC_WORLD_POINTER_SURFACE_H

#include <core/tc_component.h>
#include <termin_input/export.hpp>

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_world_pointer_ray {
    double origin_x;
    double origin_y;
    double origin_z;
    double direction_x;
    double direction_y;
    double direction_z;
    double max_distance;
} tc_world_pointer_ray;

typedef struct tc_world_pointer_hit {
    double distance;
    double u;
    double v;
    bool inside;
} tc_world_pointer_hit;

typedef enum tc_world_pointer_phase {
    TC_WORLD_POINTER_MOVE = 0,
    TC_WORLD_POINTER_DOWN = 1,
    TC_WORLD_POINTER_UP = 2,
    TC_WORLD_POINTER_LEAVE = 3,
    TC_WORLD_POINTER_CANCEL = 4,
} tc_world_pointer_phase;

typedef struct tc_world_pointer_event {
    uint64_t pointer_id;
    tc_world_pointer_phase phase;
    double u;
    double v;
    float pressure;
} tc_world_pointer_event;

typedef struct tc_world_pointer_surface_vtable {
    bool (*project_ray)(
        tc_component* component,
        const tc_world_pointer_ray* ray,
        tc_world_pointer_hit* out_hit);
    bool (*dispatch_pointer)(
        tc_component* component,
        const tc_world_pointer_event* event);
} tc_world_pointer_surface_vtable;

typedef struct tc_world_pointer_surface_capability {
    const tc_world_pointer_surface_vtable* vtable;
    void* userdata;
} tc_world_pointer_surface_capability;

TERMIN_INPUT_API tc_component_cap_id tc_world_pointer_surface_capability_id(void);

TERMIN_INPUT_API bool tc_world_pointer_surface_capability_attach(
    tc_component* component,
    const tc_world_pointer_surface_vtable* vtable,
    void* userdata);

TERMIN_INPUT_API const tc_world_pointer_surface_capability*
tc_world_pointer_surface_capability_get(const tc_component* component);

TERMIN_INPUT_API bool tc_world_pointer_surface_project_ray(
    tc_component* component,
    const tc_world_pointer_ray* ray,
    tc_world_pointer_hit* out_hit);

TERMIN_INPUT_API bool tc_world_pointer_surface_dispatch_pointer(
    tc_component* component,
    const tc_world_pointer_event* event);

#ifdef __cplusplus
}
#endif

#endif
