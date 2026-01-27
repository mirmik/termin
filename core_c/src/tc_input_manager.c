// tc_input_manager.c - Input manager implementation
#include "render/tc_input_manager.h"
#include "tc_log.h"
#include <stdlib.h>

// ============================================================================
// Input Manager Lifecycle
// ============================================================================

tc_input_manager* tc_input_manager_new(
    const tc_input_manager_vtable* vtable,
    void* body
) {
    if (!vtable) {
        tc_log(TC_LOG_ERROR, "[tc_input_manager_new] vtable is NULL");
        return NULL;
    }

    tc_input_manager* m = (tc_input_manager*)calloc(1, sizeof(tc_input_manager));
    if (!m) {
        tc_log(TC_LOG_ERROR, "[tc_input_manager_new] allocation failed");
        return NULL;
    }

    tc_input_manager_init(m, vtable);
    m->body = body;

    return m;
}

void tc_input_manager_free(tc_input_manager* m) {
    if (!m) return;
    tc_input_manager_destroy(m);
    free(m);
}
