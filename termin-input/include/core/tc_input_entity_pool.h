#ifndef TC_INPUT_ENTITY_POOL_H
#define TC_INPUT_ENTITY_POOL_H

#include "core/tc_entity_pool.h"
#include "core/tc_scene.h"
#include "core/tc_input_component.h"

#ifdef __cplusplus
extern "C" {
#endif

TC_POOL_API void tc_entity_pool_foreach_input_handler_subtree(
    tc_entity_pool* pool,
    tc_entity_id root_id,
    tc_component_iter_fn callback,
    void* user_data
);

static inline void tc_entity_foreach_input_handler_subtree(
    tc_entity_handle h,
    tc_component_iter_fn callback,
    void* user_data)
{
    tc_entity_pool* pool = tc_entity_pool_registry_get(h.pool);
    if (!pool) return;
    tc_entity_pool_foreach_input_handler_subtree(pool, h.id, callback, user_data);
}

#ifdef __cplusplus
}
#endif

#endif
