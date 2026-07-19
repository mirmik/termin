// tc_component.c - Component registry implementation
#include "core/tc_component.h"
#include <tcbase/tc_uuid.h>
#include "inspect/tc_runtime_type_registry.h"
#include <tcbase/tc_log.h>
#include <tcbase/tc_string.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>

// ============================================================================
// Component Registry - stored as facets on common runtime type records
// ============================================================================

static tc_component_prepare_unload_fn g_prepare_unload_callback = NULL;
static void* g_prepare_unload_user_data = NULL;

#define TC_RUNTIME_TYPE_FACET_COMPONENT "termin.scene.component"

typedef struct tc_component_facet_payload {
    const char* type_name;
    tc_component_factory factory;
    void* factory_userdata;
    tc_component_kind kind;
    bool is_abstract;
    const char* display_name;
    const char* category;
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

static bool prepare_component_facet_unload(
    const char* type_name,
    void* payload,
    void* context
);

// ============================================================================
// Internal Helpers
// ============================================================================

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
    tc_component_facet_payload* existing = component_facet(type_name);
    if (!existing) {
        return true;
    }

    const char* existing_owner = tc_runtime_type_registry_get_owner(type_name);
    tc_log(
        TC_LOG_DEBUG,
        "[ComponentRegistry] Ignoring legacy %s registration for existing type '%s' owned by '%s'",
        registration_kind,
        type_name,
        existing_owner ? existing_owner : "<none>"
    );
    return false;
}

static void destroy_component_facet(void* payload) {
    tc_component_facet_payload* facet = (tc_component_facet_payload*)payload;
    if (!facet) {
        return;
    }
    free(facet->requirements);
    free(facet);
}

bool tc_component_type_descriptor_add_facet(
    tc_runtime_type_descriptor* descriptor,
    tc_component_factory factory,
    void* factory_userdata,
    tc_component_kind kind,
    bool is_abstract,
    const char* display_name,
    const char* category,
    const char* const* requirements,
    size_t requirement_count,
    const tc_component_cap_id* capabilities,
    size_t capability_count
) {
    if (!descriptor) {
        tc_log(TC_LOG_ERROR, "[ComponentRegistry] cannot attach component facet to null descriptor");
        return false;
    }
    if (!is_abstract && !factory) {
        tc_log(TC_LOG_ERROR, "[ComponentRegistry] concrete component descriptor requires a factory");
        return false;
    }
    if ((requirement_count > 0 && !requirements) ||
        (capability_count > 0 && !capabilities)) {
        tc_log(TC_LOG_ERROR, "[ComponentRegistry] staged component arrays must not be null");
        return false;
    }
    tc_component_facet_payload* facet =
        (tc_component_facet_payload*)calloc(1, sizeof(*facet));
    if (!facet) {
        tc_log(TC_LOG_ERROR, "[ComponentRegistry] failed to allocate staged component facet");
        return false;
    }
    facet->factory = factory;
    facet->factory_userdata = factory_userdata;
    facet->kind = kind;
    facet->is_abstract = is_abstract;
    facet->display_name = display_name && display_name[0] ? tc_intern_string(display_name) : NULL;
    facet->category = category && category[0] ? tc_intern_string(category) : NULL;
    if ((display_name && display_name[0] && !facet->display_name) ||
        (category && category[0] && !facet->category)) {
        destroy_component_facet(facet);
        tc_log(TC_LOG_ERROR, "[ComponentRegistry] failed to intern staged component metadata");
        return false;
    }
    if (requirement_count > 0) {
        facet->requirements = (const char**)calloc(requirement_count, sizeof(const char*));
        if (!facet->requirements) {
            destroy_component_facet(facet);
            tc_log(TC_LOG_ERROR, "[ComponentRegistry] failed to allocate staged requirements");
            return false;
        }
        facet->requirement_capacity = requirement_count;
        for (size_t i = 0; i < requirement_count; ++i) {
            if (!requirements[i] || !requirements[i][0]) {
                destroy_component_facet(facet);
                tc_log(TC_LOG_ERROR, "[ComponentRegistry] staged requirement must be non-empty");
                return false;
            }
            const char* requirement = tc_intern_string(requirements[i]);
            if (!requirement) {
                destroy_component_facet(facet);
                tc_log(TC_LOG_ERROR, "[ComponentRegistry] failed to intern staged requirement");
                return false;
            }
            facet->requirements[facet->requirement_count++] = requirement;
        }
    }
    for (size_t i = 0; i < capability_count; ++i) {
        uint32_t slot = 0;
        if (!tc_component_capability_slot(capabilities[i], &slot)) {
            destroy_component_facet(facet);
            tc_log(TC_LOG_ERROR, "[ComponentRegistry] invalid staged capability id");
            return false;
        }
        facet->capability_mask |= UINT64_C(1) << slot;
    }
    if (!tc_runtime_type_descriptor_add_facet(
            descriptor,
            TC_RUNTIME_TYPE_FACET_COMPONENT,
            facet,
            destroy_component_facet,
            prepare_component_facet_unload,
            1)) {
        return false;
    }
    return true;
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
    const char* type_name
) {
    tc_component_facet_payload* facet = component_facet(type_name);
    if (facet) {
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
    facet->type_name = tc_intern_string(type_name);
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

bool tc_component_registry_register_with_parent(
    const char* type_name,
    tc_component_factory factory,
    void* factory_userdata,
    tc_component_kind kind,
    const char* parent_type_name
) {
    if (!type_name) return false;

    if (!can_register_component_type(type_name, "component")) {
        return false;
    }

    if (tc_runtime_type_registry_ensure_type(type_name)) {
        if (parent_type_name) {
            tc_runtime_type_registry_set_parent(type_name, parent_type_name);
        }
        tc_component_facet_payload* facet = ensure_component_facet(type_name);
        if (facet) {
            facet->factory = factory;
            facet->factory_userdata = factory_userdata;
            facet->kind = kind;
            facet->is_abstract = false;
            return true;
        }
        tc_log(TC_LOG_ERROR,
               "[ComponentRegistry] failed to create component facet for '%s'",
               type_name);
        return false;
    }

    tc_log(TC_LOG_ERROR,
           "[ComponentRegistry] failed to register component type '%s'",
           type_name);
    return false;
}

void tc_component_registry_register_abstract(
    const char* type_name,
    tc_component_kind kind,
    const char* parent_type_name
) {
    if (!type_name) return;

    if (!can_register_component_type(type_name, "abstract component")) {
        return;
    }

    if (tc_runtime_type_registry_ensure_type(type_name)) {
        if (parent_type_name) {
            tc_runtime_type_registry_set_parent(type_name, parent_type_name);
        }
        tc_component_facet_payload* facet = ensure_component_facet(type_name);
        if (facet) {
            facet->factory = NULL;
            facet->factory_userdata = NULL;
            facet->kind = kind;
            facet->is_abstract = true;
        }
    }
}

void tc_component_registry_unregister(const char* type_name) {
    if (!type_name) return;
    if (!tc_runtime_type_registry_unregister_type_with_context(type_name, NULL)) {
        tc_log(TC_LOG_ERROR, "[ComponentRegistry] failed to unregister component type '%s'", type_name);
    }
}

bool tc_component_registry_has(const char* type_name) {
    tc_component_facet_payload* facet = component_facet(type_name);
    return facet != NULL;
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
    if (!owner || !owner[0]) return 0;

    component_type_collect_ctx ctx = {
        tc_intern_string(owner),
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
    tc_component_facet_payload* facet = component_facet(type_name);
    if (!facet) {
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

    if (!tc_component_link_runtime_type(c, type_name)) {
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

typedef struct component_descendant_ctx {
    const char* base_type_name;
    const char** out_names;
    size_t max_count;
    size_t count;
} component_descendant_ctx;

static bool collect_component_type_and_descendants(
    const char* candidate,
    void* user_data
) {
    component_descendant_ctx* ctx = (component_descendant_ctx*)user_data;
    if (!candidate || !ctx || ctx->count >= ctx->max_count) return false;
    if (tc_component_registry_is_a(candidate, ctx->base_type_name)) {
        ctx->out_names[ctx->count++] = candidate;
    }
    return ctx->count < ctx->max_count;
}

size_t tc_component_registry_get_type_and_descendants(
    const char* type_name,
    const char** out_names,
    size_t max_count
) {
    if (!type_name || !out_names || max_count == 0 || !component_facet(type_name)) return 0;
    component_descendant_ctx ctx = { type_name, out_names, max_count, 0 };
    tc_runtime_type_registry_foreach_type_with_facet(
        TC_RUNTIME_TYPE_FACET_COMPONENT,
        collect_component_type_and_descendants,
        &ctx
    );
    return ctx.count;
}

const char* tc_component_registry_get_parent(const char* type_name) {
    return tc_runtime_type_registry_get_parent(type_name);
}

bool tc_component_registry_is_a(
    const char* type_name,
    const char* base_type_name
) {
    if (!type_name || !base_type_name) return false;

    const char* current = type_name;
    for (size_t depth = 0; current && depth < 256; ++depth) {
        if (strcmp(current, base_type_name) == 0) {
            return true;
        }
        current = tc_runtime_type_registry_get_parent(current);
    }

    return false;
}

void tc_component_registry_add_requirement(
    const char* type_name,
    const char* required_type_name
) {
    if (!type_name || !required_type_name) return;

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

    facet->requirements[facet->requirement_count++] = tc_intern_string(required_type_name);
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
    if (!type_name || !required_type_name) return false;

    return component_facet_has_requirement(component_facet(type_name), required_type_name);
}

tc_component_kind tc_component_registry_get_kind(const char* type_name) {
    tc_component_facet_payload* facet = component_facet(type_name);
    return facet ? facet->kind : TC_CXX_COMPONENT;
}

bool tc_component_registry_is_abstract(const char* type_name) {
    tc_component_facet_payload* facet = component_facet(type_name);
    return facet ? facet->is_abstract : false;
}

void tc_component_registry_set_display_name(
    const char* type_name,
    const char* display_name
) {
    if (!type_name) return;

    tc_component_facet_payload* facet = component_facet(type_name);
    if (!facet) return;

    facet->display_name = (display_name && display_name[0])
        ? tc_intern_string(display_name)
        : NULL;
}

const char* tc_component_registry_get_display_name(const char* type_name) {
    tc_component_facet_payload* facet = component_facet(type_name);
    if (facet && facet->display_name && facet->display_name[0]) {
        return facet->display_name;
    }
    return type_name ? type_name : "";
}

void tc_component_registry_set_category(
    const char* type_name,
    const char* category
) {
    if (!type_name) return;

    tc_component_facet_payload* facet = component_facet(type_name);
    if (!facet) return;

    facet->category = (category && category[0])
        ? tc_intern_string(category)
        : NULL;
}

const char* tc_component_registry_get_category(const char* type_name) {
    const char* current = type_name;
    for (size_t depth = 0; current && depth < 64; ++depth) {
        tc_component_facet_payload* facet = component_facet(current);
        if (facet && facet->category && facet->category[0]) {
            return facet->category;
        }
        current = tc_runtime_type_registry_get_parent(current);
    }
    return "Other";
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
    if (facet &&
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
    if (!type_name) return;

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
    if (!type_name) return false;

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
    if (!out_names || max_count == 0) return 0;

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

void tc_component_set_declared_type_name(tc_component* c, const char* type_name) {
    if (!c) return;
    c->declared_type_name = type_name && type_name[0]
        ? tc_intern_string(type_name)
        : NULL;
}

void tc_component_try_link_declared_type(tc_component* c) {
    if (!c || !c->declared_type_name) return;
    if (c->runtime_type_link.type_name) return;

    if (!component_facet(c->declared_type_name)) return;

    tc_component_link_runtime_type(c, c->declared_type_name);
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
        if (!tc_runtime_type_registry_unregister_type_with_context(ctx.names[i], NULL)) {
            tc_log(TC_LOG_ERROR, "[ComponentRegistry] failed to clean up component type '%s'", ctx.names[i]);
        }
    }
    free(ctx.names);

}

// ============================================================================
// Component property accessors (for FFI bindings)
// ============================================================================

const char* tc_component_get_type_name(const tc_component* c) {
    return tc_component_type_name(c);
}

const char* tc_component_get_source_id(const tc_component* c) {
    return (c && c->source_id) ? c->source_id : "";
}

void tc_component_set_source_id(tc_component* c, const char* source_id) {
    if (!c) return;
    c->source_id = (source_id && source_id[0] != '\0')
        ? tc_intern_string(source_id)
        : NULL;
}

const char* tc_component_ensure_source_id(tc_component* c) {
    if (!c) return "";
    if (!c->source_id || c->source_id[0] == '\0') {
        char uuid[64] = {0};
        tc_generate_uuid(uuid);
        c->source_id = tc_intern_string(uuid);
    }
    return c->source_id;
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
    c->display_name = tc_intern_string(display_name);
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
