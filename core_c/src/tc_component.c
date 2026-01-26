// tc_component.c - Component registry implementation
#include "../include/tc_component.h"
#include "../include/tc_type_registry.h"
#include "../include/termin_core.h"
#include "../include/tc_log.h"
#include <stdlib.h>
#include <string.h>
#include <stddef.h>

// ============================================================================
// Component Registry - uses tc_type_registry for storage
// ============================================================================

static tc_type_registry* g_component_registry = NULL;

// Offset macros for intrusive list
#define COMPONENT_REGISTRY_PREV_OFFSET offsetof(tc_component, registry_prev)
#define COMPONENT_REGISTRY_NEXT_OFFSET offsetof(tc_component, registry_next)

// ============================================================================
// Internal Helpers
// ============================================================================

static void ensure_registry_initialized(void) {
    if (!g_component_registry) {
        g_component_registry = tc_type_registry_new();
    }
}

// ============================================================================
// Registry Implementation
// ============================================================================

void tc_component_registry_register(
    const char* type_name,
    tc_component_factory factory,
    void* factory_userdata,
    tc_component_kind kind
) {
    tc_component_registry_register_with_parent(type_name, factory, factory_userdata, kind, NULL);
}

void tc_component_registry_register_with_parent(
    const char* type_name,
    tc_component_factory factory,
    void* factory_userdata,
    tc_component_kind kind,
    const char* parent_type_name
) {
    if (!type_name) return;

    ensure_registry_initialized();

    tc_type_registry_register_with_parent(
        g_component_registry,
        type_name,
        (tc_type_factory_fn)factory,
        factory_userdata,
        (int)kind,
        parent_type_name
    );
}

void tc_component_registry_unregister(const char* type_name) {
    if (!type_name || !g_component_registry) return;
    tc_type_registry_unregister(g_component_registry, type_name);
}

bool tc_component_registry_has(const char* type_name) {
    if (!g_component_registry) return false;
    return tc_type_registry_has(g_component_registry, type_name);
}

tc_component* tc_component_registry_create(const char* type_name) {
    if (!type_name) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] type_name is NULL!");
        return NULL;
    }
    if (!g_component_registry) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] registry not initialized!");
        return NULL;
    }

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    if (!entry) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] type '%s' not registered!", type_name);
        return NULL;
    }
    if (!entry->registered) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] type '%s' was unregistered!", type_name);
        return NULL;
    }
    if (!entry->factory) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] type '%s' has no factory!", type_name);
        return NULL;
    }

    // Create via type entry's factory
    tc_component* c = (tc_component*)tc_type_entry_create(entry);
    if (!c) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] factory for '%s' returned NULL!", type_name);
        return NULL;
    }

    c->kind = (tc_component_kind)entry->kind;

    // Link to type registry for instance tracking
    c->type_entry = entry;
    c->type_version = entry->version;
    tc_type_entry_link_instance(
        entry,
        c,
        COMPONENT_REGISTRY_PREV_OFFSET,
        COMPONENT_REGISTRY_NEXT_OFFSET
    );

    return c;
}

size_t tc_component_registry_type_count(void) {
    if (!g_component_registry) return 0;
    return tc_type_registry_count(g_component_registry);
}

const char* tc_component_registry_type_at(size_t index) {
    if (!g_component_registry) return NULL;
    return tc_type_registry_type_at(g_component_registry, index);
}

size_t tc_component_registry_get_type_and_descendants(
    const char* type_name,
    const char** out_names,
    size_t max_count
) {
    if (!type_name || !out_names || max_count == 0 || !g_component_registry) return 0;

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    if (!entry) return 0;

    // Collect descendants
    tc_type_entry* entries[256];
    size_t count = tc_type_entry_get_descendants(entry, entries, 256);
    if (count > max_count) count = max_count;

    for (size_t i = 0; i < count; i++) {
        out_names[i] = entries[i]->type_name;
    }

    return count;
}

const char* tc_component_registry_get_parent(const char* type_name) {
    if (!type_name || !g_component_registry) return NULL;

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    if (!entry || !entry->parent) return NULL;

    return entry->parent->type_name;
}

tc_component_kind tc_component_registry_get_kind(const char* type_name) {
    if (!type_name || !g_component_registry) return TC_EXTERNAL_COMPONENT;

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    if (!entry) return TC_EXTERNAL_COMPONENT;

    return (tc_component_kind)entry->kind;
}

void tc_component_registry_set_drawable(const char* type_name, bool is_drawable) {
    if (!type_name || !g_component_registry) return;

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    if (!entry) return;

    tc_type_entry_set_flag(entry, TC_TYPE_FLAG_DRAWABLE, is_drawable);
}

bool tc_component_registry_is_drawable(const char* type_name) {
    if (!type_name || !g_component_registry) return false;

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    return tc_type_entry_has_flag(entry, TC_TYPE_FLAG_DRAWABLE);
}

typedef struct {
    const char** out_names;
    size_t max_count;
    size_t count;
    uint32_t flag;
} flagged_types_ctx;

static bool collect_flagged_types(tc_type_entry* entry, void* user_data) {
    flagged_types_ctx* ctx = (flagged_types_ctx*)user_data;

    if (ctx->count >= ctx->max_count) return false;

    if (tc_type_entry_has_flag(entry, ctx->flag)) {
        ctx->out_names[ctx->count++] = entry->type_name;
    }

    return true;
}

size_t tc_component_registry_get_drawable_types(const char** out_names, size_t max_count) {
    if (!out_names || max_count == 0 || !g_component_registry) return 0;

    flagged_types_ctx ctx = { out_names, max_count, 0, TC_TYPE_FLAG_DRAWABLE };
    tc_type_registry_foreach(g_component_registry, collect_flagged_types, &ctx);
    return ctx.count;
}

void tc_component_registry_set_input_handler(const char* type_name, bool is_input_handler) {
    if (!type_name || !g_component_registry) return;

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    if (!entry) return;

    tc_type_entry_set_flag(entry, TC_TYPE_FLAG_INPUT_HANDLER, is_input_handler);
}

bool tc_component_registry_is_input_handler(const char* type_name) {
    if (!type_name || !g_component_registry) return false;

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    return tc_type_entry_has_flag(entry, TC_TYPE_FLAG_INPUT_HANDLER);
}

size_t tc_component_registry_get_input_handler_types(const char** out_names, size_t max_count) {
    if (!out_names || max_count == 0 || !g_component_registry) return 0;

    flagged_types_ctx ctx = { out_names, max_count, 0, TC_TYPE_FLAG_INPUT_HANDLER };
    tc_type_registry_foreach(g_component_registry, collect_flagged_types, &ctx);
    return ctx.count;
}

tc_type_entry* tc_component_registry_get_entry(const char* type_name) {
    if (!type_name || !g_component_registry) return NULL;
    return tc_type_registry_get(g_component_registry, type_name);
}

size_t tc_component_registry_instance_count(const char* type_name) {
    if (!type_name || !g_component_registry) return 0;

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    return tc_type_entry_instance_count(entry);
}

// ============================================================================
// Instance Unlink (called when component is destroyed)
// ============================================================================

void tc_component_unlink_from_registry(tc_component* c) {
    if (!c || !c->type_entry) return;

    tc_type_entry_unlink_instance(
        c->type_entry,
        c,
        COMPONENT_REGISTRY_PREV_OFFSET,
        COMPONENT_REGISTRY_NEXT_OFFSET
    );

    c->type_entry = NULL;
    c->type_version = 0;
}

// ============================================================================
// Registry cleanup (called by tc_shutdown)
// ============================================================================

void tc_component_registry_cleanup(void) {
    if (g_component_registry) {
        tc_type_registry_free(g_component_registry);
        g_component_registry = NULL;
    }
}

// ============================================================================
// External body management (for C#, Rust, etc.)
// ============================================================================

static tc_component_external_callbacks g_external_callbacks = {NULL, NULL};

void tc_component_set_external_callbacks(const tc_component_external_callbacks* callbacks) {
    if (callbacks) {
        g_external_callbacks = *callbacks;
    } else {
        g_external_callbacks.incref = NULL;
        g_external_callbacks.decref = NULL;
    }
}

void tc_component_body_incref(void* body) {
    if (body && g_external_callbacks.incref) {
        g_external_callbacks.incref(body);
    }
}

void tc_component_body_decref(void* body) {
    if (body && g_external_callbacks.decref) {
        g_external_callbacks.decref(body);
    }
}
