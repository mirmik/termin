#ifndef TC_COMPONENT_CAPABILITY_H
#define TC_COMPONENT_CAPABILITY_H

#include "tc_types.h"
#include "core/tc_scene_pool.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TC_COMPONENT_MAX_CAPABILITIES 16
#define TC_COMPONENT_CAPABILITY_INVALID_ID UINT32_C(0)

typedef uint32_t tc_component_cap_id;

struct tc_component;
typedef struct tc_component tc_component;

TC_API tc_component_cap_id tc_component_capability_register(const char* debug_name);
TC_API const char* tc_component_capability_name(tc_component_cap_id id);
TC_API bool tc_component_capability_valid(tc_component_cap_id id);
TC_API size_t tc_component_capability_count(void);
TC_API bool tc_component_capability_slot(tc_component_cap_id id, uint32_t* out_slot);

TC_API bool tc_component_has_capability(const tc_component* c, tc_component_cap_id id);
TC_API void* tc_component_get_capability(const tc_component* c, tc_component_cap_id id);
TC_API bool tc_component_attach_capability(tc_component* c, tc_component_cap_id id, void* cap_ptr);
TC_API void tc_component_detach_capability(tc_component* c, tc_component_cap_id id);

#ifdef __cplusplus
}
#endif

#endif
