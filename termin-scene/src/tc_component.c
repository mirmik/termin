// tc_component.c - Component registry implementation
#include "core/tc_component.h"
#include "inspect/tc_runtime_type_registry.h"
#include "tc_type_registry.h"
#include <tcbase/tc_log.h>
#include <tcbase/tgfx_intern_string.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>

// ============================================================================
// Component Registry - uses tc_type_registry for storage
// ============================================================================

static tc_type_registry* g_component_registry = NULL;
static tc_component_prepare_unload_fn g_prepare_unload_callback = NULL;
static void* g_prepare_unload_user_data = NULL;

#if defined(_MSC_VER)
    #define TC_THREAD_LOCAL __declspec(thread)
#else
    #define TC_THREAD_LOCAL _Thread_local
#endif

static TC_THREAD_LOCAL const char* g_component_registration_owner = NULL;

#define TC_RUNTIME_TYPE_FACET_COMPONENT "termin.scene.component"

typedef struct tc_component_facet_payload {
    const char* type_name;
    tc_type_entry* entry;
    tc_component_factory factory;
    void* factory_userdata;
    tc_component_kind kind;
    bool is_abstract;
    uint64_t capability_mask;
    const char** requirements;
    size_t requirement_count;
    size_t requirement_capacity;
} tc_component_facet_payload;

void tc_component_registry_set_capability(
    const char* type_name,
    tc_component_cap_id cap_id,
    bool enabled
);

bool tc_component_registry_has_capability(
    const char* type_name,
    tc_component_cap_id cap_id
);

// ============================================================================
// Internal Helpers
// ============================================================================

static void ensure_registry_initialized(void) {
    if (!g_component_registry) {
        g_component_registry = tc_type_registry_new();
    }
}

static tc_component_facet_payload* component_facet(const char* type_name) {
    if (!type_name) return NULL;
    return (tc_component_facet_payload*)tc_runtime_type_registry_get_facet(
        type_name,
        TC_RUNTIME_TYPE_FACET_COMPONENT
    );
}

static bool component_facet_has_requirement(
    const tc_component_facet_payload* facet,
    const char* required_type_name
) {
    if (!facet || !required_type_name) return false;

    for (size_t i = 0; i < facet->requirement_count; ++i) {
        const char* current = facet->requirements[i];
        if (current && strcmp(current, required_type_name) == 0) {
            return true;
        }
    }

    return false;
}

static bool can_register_component_type(
    const char* type_name,
    const char* registration_kind
) {
    const char* current_owner = g_component_registration_owner;
    if (!current_owner) {
        return true;
    }

    tc_component_facet_payload* existing = component_facet(type_name);
    if (!existing || !existing->entry || !existing->entry->registered) {
        return true;
    }

    const char* existing_owner = tc_runtime_type_registry_get_owner(type_name);
    if (!existing_owner || !existing_owner[0]) {
        tc_log(
            TC_LOG_WARN,
            "[ComponentRegistry] Ignoring %s registration for existing unowned type '%s' from owner '%s'",
            registration_kind,
            type_name,
            current_owner
        );
        return false;
    }

    if (strcmp(existing_owner, current_owner) != 0) {
        tc_log(
            TC_LOG_WARN,
            "[ComponentRegistry] Ignoring %s registration for existing type '%s' owned by '%s' from owner '%s'",
            registration_kind,
            type_name,
            existing_owner,
            current_owner
        );
        return false;
    }

    return true;
}

static void destroy_component_facet(void* payload) {
    tc_component_facet_payload* facet = (tc_component_facet_payload*)payload;
    if (!facet) {
        return;
    }
    if (facet->entry && facet->entry->type_name && g_component_registry) {
        tc_type_registry_unregister(g_component_registry, facet->entry->type_name);
    }
    free(facet->requirements);
    free(facet);
}

static bool prepare_component_facet_unload(
    const char* type_name,
    void* payload,
    void* context
) {
    (void)payload;
    if (!type_name || tc_runtime_type_registry_instance_count(type_name) == 0) {
        return true;
    }

    if (!g_prepare_unload_callback) {
        tc_log(
            TC_LOG_WARN,
            "[ComponentRegistry] unloading component type '%s' with %zu live instance(s) and no prepare-unload callback",
            type_name,
            tc_runtime_type_registry_instance_count(type_name)
        );
        return true;
    }

    return g_prepare_unload_callback(
        type_name,
        context,
        g_prepare_unload_user_data
    );
}

static tc_component_facet_payload* ensure_component_facet(
    const char* type_name,
    tc_type_entry* entry
) {
    tc_component_facet_payload* facet = component_facet(type_name);
    if (facet) {
        facet->entry = entry;
        tc_runtime_type_registry_set_facet_with_lifecycle(
            type_name,
            TC_RUNTIME_TYPE_FACET_COMPONENT,
            facet,
            destroy_component_facet,
            prepare_component_facet_unload,
            1
        );
        return facet;
    }

    facet = (tc_component_facet_payload*)calloc(1, sizeof(tc_component_facet_payload));
    if (!facet) {
        tc_log(TC_LOG_ERROR, "[ComponentRegistry] failed to allocate component facet for '%s'", type_name);
        return NULL;
    }
    facet->type_name = tgfx_intern_string(type_name);
    facet->entry = entry;
    facet->kind = TC_CXX_COMPONENT;

    if (!tc_runtime_type_registry_set_facet_with_lifecycle(
            type_name,
            TC_RUNTIME_TYPE_FACET_COMPONENT,
            facet,
            destroy_component_facet,
            prepare_component_facet_unload,
            1
        )) {
        free(facet);
        return NULL;
    }
    return facet;
}

static bool tc_component_link_runtime_type(
    tc_component* c,
    tc_type_entry* entry,
    const char* type_name
) {
    if (!c || !type_name) {
        return false;
    }

    if (!tc_runtime_type_registry_link_instance(
            type_name,
            &c->runtime_type_link,
            c
        )) {
        tc_log(
            TC_LOG_ERROR,
            "[ComponentRegistry] failed to link component instance to runtime type '%s'",
            type_name
        );
        return false;
    }

    c->type_entry = entry;
    c->type_version = entry ? entry->version : 0;
    return true;
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

    if (!can_register_component_type(type_name, "component")) {
        return;
    }

    tc_type_entry* entry = tc_type_registry_register_with_parent(
        g_component_registry,
        type_name,
        NULL,
        NULL,
        (int)kind,
        parent_type_name
    );
    if (entry) {
        tc_runtime_type_registry_ensure_type(type_name);
        if (g_component_registration_owner) {
            tc_runtime_type_registry_set_owner(
                type_name,
                g_component_registration_owner,
                true
            );
        }
        if (parent_type_name) {
            tc_runtime_type_registry_set_parent(type_name, parent_type_name);
        }
        tc_component_facet_payload* facet = ensure_component_facet(type_name, entry);
        if (facet) {
            facet->factory = factory;
            facet->factory_userdata = factory_userdata;
            facet->kind = kind;
            facet->is_abstract = false;
        }
        tc_type_entry_set_flag(entry, TC_TYPE_FLAG_ABSTRACT, false);
    }
}

void tc_component_registry_register_abstract(
    const char* type_name,
    tc_component_kind kind,
    const char* parent_type_name
) {
    if (!type_name) return;

    ensure_registry_initialized();

    if (!can_register_component_type(type_name, "abstract component")) {
        return;
    }

    tc_type_entry* entry = tc_type_registry_register_with_parent(
        g_component_registry,
        type_name,
        NULL,  // no factory
        NULL,
        (int)kind,
        parent_type_name
    );
    if (entry) {
        tc_type_entry_set_flag(entry, TC_TYPE_FLAG_ABSTRACT, true);
        tc_runtime_type_registry_ensure_type(type_name);
        if (g_component_registration_owner) {
            tc_runtime_type_registry_set_owner(
                type_name,
                g_component_registration_owner,
                true
            );
        }
        if (parent_type_name) {
            tc_runtime_type_registry_set_parent(type_name, parent_type_name);
        }
        tc_component_facet_payload* facet = ensure_component_facet(type_name, entry);
        if (facet) {
            facet->factory = NULL;
            facet->factory_userdata = NULL;
            facet->kind = kind;
            facet->is_abstract = true;
        }
    }
}

void tc_component_registry_unregister(const char* type_name) {
    if (!type_name || !g_component_registry) return;
    tc_runtime_type_registry_remove_facet(type_name, TC_RUNTIME_TYPE_FACET_COMPONENT);
}

bool tc_component_registry_has(const char* type_name) {
    tc_component_facet_payload* facet = component_facet(type_name);
    return facet && facet->entry && facet->entry->registered;
}

void tc_component_registry_set_registration_owner(const char* owner) {
    g_component_registration_owner = owner && owner[0] ? tgfx_intern_string(owner) : NULL;
    tc_runtime_type_registry_set_registration_owner(g_component_registration_owner);
}

const char* tc_component_registry_get_registration_owner(void) {
    return g_component_registration_owner;
}

const char* tc_component_registry_get_owner(const char* type_name) {
    return tc_runtime_type_registry_get_owner(type_name);
}

typedef struct {
    const char* owner;
    const char** names;
    size_t count;
    size_t capacity;
    const char* log_context;
} component_type_collect_ctx;

static bool collect_component_type(const char* type_name, void* user_data) {
    component_type_collect_ctx* ctx = (component_type_collect_ctx*)user_data;
    if (!type_name || !ctx) return true;

    if (ctx->owner) {
        const char* owner = tc_runtime_type_registry_get_owner(type_name);
        if (!owner || strcmp(owner, ctx->owner) != 0) return true;
    }

    if (ctx->count >= ctx->capacity) {
        size_t new_capacity = ctx->capacity == 0 ? 8 : ctx->capacity * 2;
        const char** names = (const char**)realloc(
            ctx->names,
            new_capacity * sizeof(const char*)
        );
        if (!names) {
            tc_log(
                TC_LOG_ERROR,
                "[ComponentRegistry] failed to grow component type list during %s",
                ctx->log_context ? ctx->log_context : "cleanup"
            );
            return false;
        }
        ctx->names = names;
        ctx->capacity = new_capacity;
    }

    ctx->names[ctx->count++] = type_name;
    return true;
}

size_t tc_component_registry_unregister_owner(const char* owner) {
    if (!owner || !owner[0] || !g_component_registry) return 0;

    component_type_collect_ctx ctx = {
        tgfx_intern_string(owner),
        NULL,
        0,
        0,
        "owner cleanup"
    };
    tc_runtime_type_registry_foreach_type_with_facet(
        TC_RUNTIME_TYPE_FACET_COMPONENT,
        collect_component_type,
        &ctx
    );

    for (size_t i = 0; i < ctx.count; ++i) {
        tc_component_registry_unregister(ctx.names[i]);
    }

    size_t removed = ctx.count;
    free(ctx.names);
    return removed;
}

void tc_component_registry_set_prepare_unload_callback(
    tc_component_prepare_unload_fn callback,
    void* user_data
) {
    g_prepare_unload_callback = callback;
    g_prepare_unload_user_data = user_data;
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
    tc_component_facet_payload* facet = component_facet(type_name);
    if (!facet || facet->entry != entry) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] type '%s' has no component facet!", type_name);
        return NULL;
    }
    if (facet->is_abstract) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] type '%s' is abstract!", type_name);
        return NULL;
    }
    if (!facet->factory) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] type '%s' has no factory!", type_name);
        return NULL;
    }

    tc_component* c = facet->factory(facet->factory_userdata);
    if (!c) {
        tc_log(TC_LOG_ERROR, "[tc_component_registry_create] factory for '%s' returned NULL!", type_name);
        return NULL;
    }

    c->kind = facet->kind;

    if (!tc_component_link_runtime_type(c, entry, type_name)) {
        tc_log(
            TC_LOG_ERROR,
            "[tc_component_registry_create] failed to link instance for type '%s'",
            type_name
        );
    }

    return c;
}

size_t tc_component_registry_type_count(void) {
    return tc_runtime_type_registry_types_with_facet_count(TC_RUNTIME_TYPE_FACET_COMPONENT);
}

const char* tc_component_registry_type_at(size_t index) {
    return tc_runtime_type_registry_type_with_facet_at(TC_RUNTIME_TYPE_FACET_COMPONENT, index);
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
    return tc_runtime_type_registry_get_parent(type_name);
}

bool tc_component_registry_is_a(
    const char* type_name,
    const char* base_type_name
) {
    if (!type_name || !base_type_name || !g_component_registry) return false;

    tc_type_entry* entry = tc_type_registry_get(g_component_registry, type_name);
    while (entry) {
        if (entry->type_name && strcmp(entry->type_name, base_type_name) == 0) {
            return true;
        }
        entry = entry->parent;
    }

    return false;
}

void tc_component_registry_add_requirement(
    const char* type_name,
    const char* required_type_name
) {
    if (!type_name || !required_type_name) return;

    ensure_registry_initialized();

    tc_component_facet_payload* facet = component_facet(type_name);
    if (!facet) return;

    if (component_facet_has_requirement(facet, required_type_name)) {
        return;
    }

    if (facet->requirement_count >= facet->requirement_capacity) {
        size_t new_cap = facet->requirement_capacity == 0 ? 4 : facet->requirement_capacity * 2;
        const char** new_arr = (const char**)realloc(
            facet->requirements,
            new_cap * sizeof(const char*)
        );
        if (!new_arr) return;
        facet->requirements = new_arr;
        facet->requirement_capacity = new_cap;
    }

    facet->requirements[facet->requirement_count++] = tgfx_intern_string(required_type_name);
}

size_t tc_component_registry_requirement_count(const char* type_name) {
    tc_component_facet_payload* facet = component_facet(type_name);
    return facet ? facet->requirement_count : 0;
}

const char* tc_component_registry_requirement_at(const char* type_name, size_t index) {
    tc_component_facet_payload* facet = component_facet(type_name);
    if (!facet || index >= facet->requirement_count) return NULL;

    return facet->requirements[index];
}

bool tc_component_registry_has_requirement(
    const char* type_name,
    const char* required_type_name
) {
    if (!type_name || !required_type_name || !g_component_registry) return false;

    return component_facet_has_requirement(component_facet(type_name), required_type_name);
}

tc_component_kind tc_component_registry_get_kind(const char* type_name) {
    tc_component_facet_payload* facet = component_facet(type_name);
    return facet ? facet->kind : TC_CXX_COMPONENT;
}

typedef struct {
    const char** out_names;
    size_t max_count;
    size_t count;
    uint64_t capability_mask;
} flagged_types_ctx;

static bool collect_component_type_with_capability(const char* type_name, void* user_data) {
    flagged_types_ctx* ctx = (flagged_types_ctx*)user_data;
    if (!type_name || ctx->count >= ctx->max_count) {
        return false;
    }

    tc_component_facet_payload* facet = component_facet(type_name);
    if (facet && facet->entry && facet->entry->registered &&
        (facet->capability_mask & ctx->capability_mask) != 0) {
        ctx->out_names[ctx->count++] = facet->type_name;
    }
    return true;
}

void tc_component_registry_set_capability(
    const char* type_name,
    tc_component_cap_id cap_id,
    bool enabled
) {
    if (!type_name || !g_component_registry) return;

    tc_component_facet_payload* facet = component_facet(type_name);
    if (!facet) return;

    uint32_t slot = 0;
    if (!tc_component_capability_slot(cap_id, &slot)) return;

    if (enabled) {
        facet->capability_mask |= (UINT64_C(1) << slot);
    } else {
        facet->capability_mask &= ~(UINT64_C(1) << slot);
    }
}

bool tc_component_registry_has_capability(
    const char* type_name,
    tc_component_cap_id cap_id
) {
    if (!type_name || !g_component_registry) return false;

    tc_component_facet_payload* facet = component_facet(type_name);
    if (!facet) return false;

    uint32_t slot = 0;
    if (!tc_component_capability_slot(cap_id, &slot)) return false;

    return (facet->capability_mask & (UINT64_C(1) << slot)) != 0;
}

size_t tc_component_registry_get_types_with_capability(
    tc_component_cap_id cap_id,
    const char** out_names,
    size_t max_count
) {
    if (!out_names || max_count == 0 || !g_component_registry) return 0;

    uint32_t slot = 0;
    if (!tc_component_capability_slot(cap_id, &slot)) return 0;

    flagged_types_ctx ctx = {
        out_names,
        max_count,
        0,
        (UINT64_C(1) << slot)
    };

    tc_runtime_type_registry_foreach_type_with_facet(
        TC_RUNTIME_TYPE_FACET_COMPONENT,
        collect_component_type_with_capability,
        &ctx);
    return ctx.count;
}

tc_type_entry* tc_component_registry_get_entry(const char* type_name) {
    if (!type_name || !g_component_registry) return NULL;
    return tc_type_registry_get(g_component_registry, type_name);
}

void tc_component_set_declared_type_name(tc_component* c, const char* type_name) {
    if (!c) return;
    c->declared_type_name = type_name;
}

void tc_component_try_link_declared_type(tc_component* c) {
    if (!c || !c->declared_type_name || !g_component_registry) return;
    if (c->runtime_type_link.type_name) return;

    tc_type_entry* entry = c->type_entry
        ? c->type_entry
        : tc_type_registry_get(g_component_registry, c->declared_type_name);
    if (!entry || !entry->registered) return;

    tc_component_link_runtime_type(c, entry, c->declared_type_name);
}

size_t tc_component_registry_instance_count(const char* type_name) {
    if (!type_name) return 0;
    return tc_runtime_type_registry_instance_count(type_name);
}

// ============================================================================
// Instance Unlink (called when component is destroyed)
// ============================================================================

void tc_component_unlink_from_registry(tc_component* c) {
    if (!c) return;

    tc_runtime_type_registry_unlink_instance(&c->runtime_type_link);
    c->type_entry = NULL;
    c->type_version = 0;
}

// ============================================================================
// Registry cleanup (called by tc_shutdown)
// ============================================================================

void tc_component_registry_cleanup(void) {
    component_type_collect_ctx ctx = { NULL, NULL, 0, 0, "registry cleanup" };
    tc_runtime_type_registry_foreach_type_with_facet(
        TC_RUNTIME_TYPE_FACET_COMPONENT,
        collect_component_type,
        &ctx
    );
    for (size_t i = 0; i < ctx.count; ++i) {
        tc_runtime_type_registry_remove_facet(ctx.names[i], TC_RUNTIME_TYPE_FACET_COMPONENT);
    }
    free(ctx.names);

    if (g_component_registry) {
        tc_type_registry_free(g_component_registry);
        g_component_registry = NULL;
    }
}

// ============================================================================
// Component property accessors (for FFI bindings)
// ============================================================================

const char* tc_component_get_type_name(const tc_component* c) {
    return tc_component_type_name(c);
}

const char* tc_component_get_display_name(const tc_component* c) {
    return (c && c->display_name) ? c->display_name : "";
}

void tc_component_set_display_name(tc_component* c, const char* display_name) {
    if (!c) return;
    if (!display_name || display_name[0] == '\0') {
        c->display_name = NULL;
        return;
    }
    c->display_name = tgfx_intern_string(display_name);
}

bool tc_component_get_enabled(const tc_component* c) {
    return c ? c->enabled : false;
}

void tc_component_set_enabled(tc_component* c, bool enabled) {
    if (c) c->enabled = enabled;
}

bool tc_component_get_active_in_editor(const tc_component* c) {
    return c ? c->active_in_editor : false;
}

void tc_component_set_active_in_editor(tc_component* c, bool active) {
    if (c) c->active_in_editor = active;
}

tc_component_kind tc_component_get_kind(const tc_component* c) {
    return c ? c->kind : TC_CXX_COMPONENT;
}

tc_entity_handle tc_component_get_owner(const tc_component* c) {
    if (c) return c->owner;
    return TC_ENTITY_HANDLE_INVALID;
}
