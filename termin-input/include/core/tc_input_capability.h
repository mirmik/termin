#ifndef TC_INPUT_CAPABILITY_H
#define TC_INPUT_CAPABILITY_H

#include "core/tc_component_capability.h"

#ifdef __cplusplus
extern "C" {
#endif

struct tc_component;
struct tc_input_vtable;

TC_API tc_component_cap_id tc_input_capability_id(void);
TC_API bool tc_input_capability_attach(struct tc_component* c, const struct tc_input_vtable* vtable);
TC_API const struct tc_input_vtable* tc_input_capability_get(const struct tc_component* c);
TC_API int tc_component_get_input_priority(const struct tc_component* c);
TC_API bool tc_component_set_input_priority(struct tc_component* c, int priority);

#ifdef __cplusplus
}
#endif

#endif
