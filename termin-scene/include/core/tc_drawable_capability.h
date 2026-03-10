#ifndef TC_DRAWABLE_CAPABILITY_H
#define TC_DRAWABLE_CAPABILITY_H

#include "core/tc_component_capability.h"

#ifdef __cplusplus
extern "C" {
#endif

struct tc_component;
struct tc_drawable_vtable;

TC_API tc_component_cap_id tc_drawable_capability_id(void);
TC_API bool tc_drawable_capability_attach(struct tc_component* c, const struct tc_drawable_vtable* vtable);
TC_API const struct tc_drawable_vtable* tc_drawable_capability_get(const struct tc_component* c);

#ifdef __cplusplus
}
#endif

#endif
