#include "core/tc_input_entity_pool.h"

static bool foreach_input_handler_recursive(
    tc_entity_pool* pool,
    tc_entity_id entity_id,
    tc_component_iter_fn callback,
    void* user_data
) {
    if (!pool || !tc_entity_pool_alive(pool, entity_id)) return true;
    if (!tc_entity_pool_enabled(pool, entity_id)) return true;

    size_t comp_count = tc_entity_pool_component_count(pool, entity_id);
    for (size_t i = 0; i < comp_count; i++) {
        tc_component* c = tc_entity_pool_component_at(pool, entity_id, i);
        if (!c || !c->enabled) continue;

        if (tc_component_is_input_handler(c)) {
            if (!callback(c, user_data)) {
                return false;
            }
        }
    }

    size_t child_count = tc_entity_pool_children_count(pool, entity_id);
    for (size_t i = 0; i < child_count; i++) {
        tc_entity_id child_id = tc_entity_pool_child_at(pool, entity_id, i);
        if (!foreach_input_handler_recursive(pool, child_id, callback, user_data)) {
            return false;
        }
    }

    return true;
}

void tc_entity_pool_foreach_input_handler_subtree(
    tc_entity_pool* pool,
    tc_entity_id root_id,
    tc_component_iter_fn callback,
    void* user_data
) {
    if (!pool || !callback) return;
    foreach_input_handler_recursive(pool, root_id, callback, user_data);
}
