// tc_pass.c - Pass registry and external pass support
#include "tc_pass.h"
#include "tc_pipeline.h"
#include "tc_pipeline_registry.h"
#include "tc_type_registry.h"
#include "termin_core.h"
#include "tc_log.h"
#include <stdlib.h>
#include <string.h>
#include <stddef.h>

// ============================================================================
// Pass Property Setters
// ============================================================================

void tc_pass_set_name(tc_pass* p, const char* name) {
    if (!p) return;
    if (p->pass_name) free(p->pass_name);
    p->pass_name = name ? strdup(name) : NULL;
}

void tc_pass_set_enabled(tc_pass* p, bool enabled) {
    if (p) p->enabled = enabled;
}

void tc_pass_set_passthrough(tc_pass* p, bool passthrough) {
    if (p) p->passthrough = passthrough;
}

// ============================================================================
// Pass Registry - uses tc_type_registry for storage
// ============================================================================

static tc_type_registry* g_pass_registry = NULL;

// Offset macros for intrusive list
#define PASS_REGISTRY_PREV_OFFSET offsetof(tc_pass, registry_prev)
#define PASS_REGISTRY_NEXT_OFFSET offsetof(tc_pass, registry_next)

static void ensure_pass_registry_initialized(void) {
    if (!g_pass_registry) {
        g_pass_registry = tc_type_registry_new();
    }
}

void tc_pass_registry_register(
    const char* type_name,
    tc_pass_factory factory,
    void* factory_userdata,
    tc_pass_kind kind
) {
    if (!type_name) return;

    ensure_pass_registry_initialized();

    tc_type_registry_register(
        g_pass_registry,
        type_name,
        (tc_type_factory_fn)factory,
        factory_userdata,
        (int)kind
    );
}

void tc_pass_registry_unregister(const char* type_name) {
    if (!type_name || !g_pass_registry) return;
    tc_type_registry_unregister(g_pass_registry, type_name);
}

bool tc_pass_registry_has(const char* type_name) {
    if (!g_pass_registry) return false;
    return tc_type_registry_has(g_pass_registry, type_name);
}

tc_pass* tc_pass_registry_create(const char* type_name) {
    if (!g_pass_registry) return NULL;

    tc_type_entry* entry = tc_type_registry_get(g_pass_registry, type_name);
    if (!entry || !entry->registered || !entry->factory) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Unknown type or no factory: %s", type_name);
        return NULL;
    }

    // Create via type entry's factory
    tc_pass* p = (tc_pass*)tc_type_entry_create(entry);
    if (p) {
        p->kind = (tc_pass_kind)entry->kind;

        // Link to type registry for instance tracking
        p->type_entry = entry;
        p->type_version = entry->version;
        tc_type_entry_link_instance(
            entry,
            p,
            PASS_REGISTRY_PREV_OFFSET,
            PASS_REGISTRY_NEXT_OFFSET
        );
    }
    return p;
}

size_t tc_pass_registry_type_count(void) {
    if (!g_pass_registry) return 0;
    return tc_type_registry_count(g_pass_registry);
}

const char* tc_pass_registry_type_at(size_t index) {
    if (!g_pass_registry) return NULL;
    return tc_type_registry_type_at(g_pass_registry, index);
}

tc_pass_kind tc_pass_registry_get_kind(const char* type_name) {
    if (!g_pass_registry) return TC_NATIVE_PASS;

    tc_type_entry* entry = tc_type_registry_get(g_pass_registry, type_name);
    return entry ? (tc_pass_kind)entry->kind : TC_NATIVE_PASS;
}

tc_type_entry* tc_pass_registry_get_entry(const char* type_name) {
    if (!type_name || !g_pass_registry) return NULL;
    return tc_type_registry_get(g_pass_registry, type_name);
}

size_t tc_pass_registry_instance_count(const char* type_name) {
    if (!type_name || !g_pass_registry) return 0;

    tc_type_entry* entry = tc_type_registry_get(g_pass_registry, type_name);
    return tc_type_entry_instance_count(entry);
}

void tc_pass_unlink_from_registry(tc_pass* p) {
    if (!p || !p->type_entry) return;

    tc_type_entry_unlink_instance(
        p->type_entry,
        p,
        PASS_REGISTRY_PREV_OFFSET,
        PASS_REGISTRY_NEXT_OFFSET
    );

    p->type_entry = NULL;
    p->type_version = 0;
}

// ============================================================================
// Pass Registry Cleanup (called by tc_shutdown)
// ============================================================================

void tc_pass_registry_cleanup(void) {
    if (g_pass_registry) {
        tc_type_registry_free(g_pass_registry);
        g_pass_registry = NULL;
    }
}

// ============================================================================
// External Pass Support
// ============================================================================

static tc_external_pass_callbacks g_external_callbacks = {0};

// External pass vtable callbacks
static void external_execute(tc_pass* p, tc_execute_context* ctx) {
    if (g_external_callbacks.execute && p->body) {
        g_external_callbacks.execute(p->body, ctx);
    }
}

static size_t external_get_reads(tc_pass* p, const char** out, size_t max) {
    if (g_external_callbacks.get_reads && p->body) {
        return g_external_callbacks.get_reads(p->body, out, max);
    }
    return 0;
}

static size_t external_get_writes(tc_pass* p, const char** out, size_t max) {
    if (g_external_callbacks.get_writes && p->body) {
        return g_external_callbacks.get_writes(p->body, out, max);
    }
    return 0;
}

static size_t external_get_inplace_aliases(tc_pass* p, const char** out, size_t max) {
    if (g_external_callbacks.get_inplace_aliases && p->body) {
        return g_external_callbacks.get_inplace_aliases(p->body, out, max);
    }
    return 0;
}

static size_t external_get_resource_specs(tc_pass* p, tc_resource_spec* out, size_t max) {
    if (g_external_callbacks.get_resource_specs && p->body) {
        return g_external_callbacks.get_resource_specs(p->body, out, max);
    }
    return 0;
}

static size_t external_get_internal_symbols(tc_pass* p, const char** out, size_t max) {
    if (g_external_callbacks.get_internal_symbols && p->body) {
        return g_external_callbacks.get_internal_symbols(p->body, out, max);
    }
    return 0;
}

static void external_destroy(tc_pass* p) {
    if (g_external_callbacks.destroy && p->body) {
        g_external_callbacks.destroy(p->body);
    }
}

static void external_retain(tc_pass* p) {
    if (g_external_callbacks.incref && p->body) {
        g_external_callbacks.incref(p->body);
    }
}

static void external_release(tc_pass* p) {
    if (g_external_callbacks.decref && p->body) {
        g_external_callbacks.decref(p->body);
    }
}

static void external_drop(tc_pass* p) {
    if (!p) return;

    // Unlink from registry
    tc_pass_unlink_from_registry(p);

    // Decrement Python refcount
    if (g_external_callbacks.decref && p->body) {
        g_external_callbacks.decref(p->body);
        p->body = NULL;
    }

    // Free pass_name
    if (p->pass_name) {
        free(p->pass_name);
        p->pass_name = NULL;
    }

    // Free the tc_pass struct itself
    free(p);
}

static const tc_pass_vtable g_external_vtable = {
    .execute = external_execute,
    .get_reads = external_get_reads,
    .get_writes = external_get_writes,
    .get_inplace_aliases = external_get_inplace_aliases,
    .get_resource_specs = external_get_resource_specs,
    .get_internal_symbols = external_get_internal_symbols,
    .destroy = external_destroy,
    .drop = external_drop,
    .retain = external_retain,
    .release = external_release,
    .serialize = NULL,
    .deserialize = NULL,
};

void tc_pass_set_external_callbacks(const tc_external_pass_callbacks* callbacks) {
    if (callbacks) {
        g_external_callbacks = *callbacks;
    }
}

tc_pass* tc_pass_new_external(void* body, const char* type_name) {
    tc_pass* p = (tc_pass*)calloc(1, sizeof(tc_pass));
    if (!p) return NULL;

    tc_pass_init(p, &g_external_vtable);
    p->body = body;
    p->externally_managed = true;
    p->kind = TC_EXTERNAL_PASS;

    // Link to type registry for type name and instance tracking
    if (!type_name) {
        tc_log(TC_LOG_ERROR, "[tc_pass_new_external] type_name is NULL!");
        free(p);
        return NULL;
    }

    ensure_pass_registry_initialized();
    tc_type_entry* entry = tc_type_registry_get(g_pass_registry, type_name);
    if (!entry) {
        tc_log(TC_LOG_ERROR, "[tc_pass_new_external] type '%s' not registered! Call tc_pass_registry_register() first.", type_name);
        free(p);
        return NULL;
    }

    p->type_entry = entry;
    p->type_version = entry->version;
    tc_type_entry_link_instance(
        entry,
        p,
        PASS_REGISTRY_PREV_OFFSET,
        PASS_REGISTRY_NEXT_OFFSET
    );

    return p;
}

void tc_pass_free_external(tc_pass* p) {
    if (p) {
        // Unlink from registry
        tc_pass_unlink_from_registry(p);

        if (p->pass_name) free(p->pass_name);
        if (p->viewport_name) free(p->viewport_name);
        if (p->debug_internal_symbol) free(p->debug_internal_symbol);
        free(p);
    }
}

void tc_pass_body_incref(void* body) {
    if (g_external_callbacks.incref && body) {
        g_external_callbacks.incref(body);
    }
}

void tc_pass_body_decref(void* body) {
    if (g_external_callbacks.decref && body) {
        g_external_callbacks.decref(body);
    }
}

// ============================================================================
// Pipeline Implementation
// ============================================================================

tc_pipeline* tc_pipeline_create(const char* name) {
    tc_pipeline* p = (tc_pipeline*)calloc(1, sizeof(tc_pipeline));
    if (!p) return NULL;

    p->name = name ? strdup(name) : strdup("default");
    p->first_pass = NULL;
    p->last_pass = NULL;
    p->pass_count = 0;
    p->specs = NULL;
    p->spec_count = 0;
    p->spec_capacity = 0;

    // Register in global registry
    tc_pipeline_registry_add(p);

    return p;
}

void tc_pipeline_destroy(tc_pipeline* p) {
    if (!p) return;

    // Remove from global registry
    tc_pipeline_registry_remove(p);

    // Release all passes (may drop if ref_count reaches 0)
    tc_pass* pass = p->first_pass;
    while (pass) {
        tc_pass* next = pass->next;
        tc_pass_destroy(pass);
        tc_pass_release(pass);
        pass = next;
    }

    // Free specs
    if (p->specs) {
        free(p->specs);
    }

    free(p->name);
    free(p);
}

void tc_pipeline_add_pass(tc_pipeline* p, tc_pass* pass) {
    if (!p || !pass) return;

    // Retain pass to prevent deletion while in pipeline
    tc_pass_retain(pass);

    pass->prev = p->last_pass;
    pass->next = NULL;

    if (p->last_pass) {
        p->last_pass->next = pass;
    } else {
        p->first_pass = pass;
    }
    p->last_pass = pass;
    p->pass_count++;
}

void tc_pipeline_insert_pass_before(tc_pipeline* p, tc_pass* pass, tc_pass* before) {
    if (!p || !pass) return;

    // Retain pass to prevent deletion while in pipeline
    tc_pass_retain(pass);

    if (!before || before == p->first_pass) {
        // Insert at beginning
        pass->prev = NULL;
        pass->next = p->first_pass;
        if (p->first_pass) {
            p->first_pass->prev = pass;
        }
        p->first_pass = pass;
        if (!p->last_pass) {
            p->last_pass = pass;
        }
    } else {
        pass->prev = before->prev;
        pass->next = before;
        if (before->prev) {
            before->prev->next = pass;
        }
        before->prev = pass;
    }
    p->pass_count++;
}

void tc_pipeline_remove_pass(tc_pipeline* p, tc_pass* pass) {
    if (!p || !pass) return;

    if (pass->prev) {
        pass->prev->next = pass->next;
    } else {
        p->first_pass = pass->next;
    }

    if (pass->next) {
        pass->next->prev = pass->prev;
    } else {
        p->last_pass = pass->prev;
    }

    pass->prev = NULL;
    pass->next = NULL;
    p->pass_count--;

    // Release pass - may drop if ref_count reaches 0
    tc_pass_release(pass);
}

tc_pass* tc_pipeline_get_pass(tc_pipeline* p, const char* name) {
    if (!p || !name) return NULL;

    tc_pass* pass = p->first_pass;
    while (pass) {
        if (pass->pass_name && strcmp(pass->pass_name, name) == 0) {
            return pass;
        }
        pass = pass->next;
    }
    return NULL;
}

tc_pass* tc_pipeline_get_pass_at(tc_pipeline* p, size_t index) {
    if (!p || index >= p->pass_count) return NULL;

    tc_pass* pass = p->first_pass;
    for (size_t i = 0; i < index && pass; i++) {
        pass = pass->next;
    }
    return pass;
}

size_t tc_pipeline_pass_count(tc_pipeline* p) {
    return p ? p->pass_count : 0;
}

void tc_pipeline_add_spec(tc_pipeline* p, const tc_resource_spec* spec) {
    if (!p || !spec) return;

    if (p->spec_count >= p->spec_capacity) {
        size_t new_capacity = p->spec_capacity ? p->spec_capacity * 2 : 8;
        tc_resource_spec* new_specs = (tc_resource_spec*)realloc(
            p->specs, new_capacity * sizeof(tc_resource_spec)
        );
        if (!new_specs) return;
        p->specs = new_specs;
        p->spec_capacity = new_capacity;
    }

    p->specs[p->spec_count++] = *spec;
}

void tc_pipeline_clear_specs(tc_pipeline* p) {
    if (p) {
        p->spec_count = 0;
    }
}

size_t tc_pipeline_collect_specs(
    tc_pipeline* p,
    tc_resource_spec* out_specs,
    size_t max_count
) {
    if (!p || !out_specs) return 0;

    size_t count = 0;

    // Pipeline-level specs
    for (size_t i = 0; i < p->spec_count && count < max_count; i++) {
        out_specs[count++] = p->specs[i];
    }

    // Pass specs
    tc_pass* pass = p->first_pass;
    while (pass && count < max_count) {
        if (pass->enabled) {
            tc_resource_spec pass_specs[16];
            size_t pass_spec_count = tc_pass_get_resource_specs(pass, pass_specs, 16);
            for (size_t i = 0; i < pass_spec_count && count < max_count; i++) {
                out_specs[count++] = pass_specs[i];
            }
        }
        pass = pass->next;
    }

    return count;
}

// ============================================================================
// Pipeline Registry Implementation
// ============================================================================

#define MAX_PIPELINES 64

static tc_pipeline* g_pipelines[MAX_PIPELINES];
static size_t g_pipeline_count = 0;
static bool g_pipeline_registry_initialized = false;

void tc_pipeline_registry_init(void) {
    if (g_pipeline_registry_initialized) return;
    memset(g_pipelines, 0, sizeof(g_pipelines));
    g_pipeline_count = 0;
    g_pipeline_registry_initialized = true;
}

void tc_pipeline_registry_shutdown(void) {
    if (!g_pipeline_registry_initialized) return;
    memset(g_pipelines, 0, sizeof(g_pipelines));
    g_pipeline_count = 0;
    g_pipeline_registry_initialized = false;
}

void tc_pipeline_registry_add(tc_pipeline* p) {
    if (!p) return;
    if (!g_pipeline_registry_initialized) {
        tc_pipeline_registry_init();
    }

    // Check if already registered
    for (size_t i = 0; i < g_pipeline_count; i++) {
        if (g_pipelines[i] == p) return;
    }

    if (g_pipeline_count >= MAX_PIPELINES) {
        tc_log(TC_LOG_ERROR, "[tc_pipeline_registry] Registry full, cannot add pipeline");
        return;
    }

    g_pipelines[g_pipeline_count++] = p;
}

void tc_pipeline_registry_remove(tc_pipeline* p) {
    if (!p || !g_pipeline_registry_initialized) return;

    for (size_t i = 0; i < g_pipeline_count; i++) {
        if (g_pipelines[i] == p) {
            // Shift remaining entries
            for (size_t j = i; j < g_pipeline_count - 1; j++) {
                g_pipelines[j] = g_pipelines[j + 1];
            }
            g_pipeline_count--;
            return;
        }
    }
}

size_t tc_pipeline_registry_count(void) {
    return g_pipeline_count;
}

tc_pipeline* tc_pipeline_registry_get_at(size_t index) {
    if (index >= g_pipeline_count) return NULL;
    return g_pipelines[index];
}

tc_pipeline* tc_pipeline_registry_find_by_name(const char* name) {
    if (!name) return NULL;

    for (size_t i = 0; i < g_pipeline_count; i++) {
        if (g_pipelines[i] && g_pipelines[i]->name &&
            strcmp(g_pipelines[i]->name, name) == 0) {
            return g_pipelines[i];
        }
    }
    return NULL;
}

tc_pipeline_info* tc_pipeline_registry_get_all_info(size_t* count) {
    if (!count) return NULL;
    *count = 0;

    if (g_pipeline_count == 0) return NULL;

    tc_pipeline_info* infos = (tc_pipeline_info*)malloc(
        g_pipeline_count * sizeof(tc_pipeline_info)
    );
    if (!infos) return NULL;

    for (size_t i = 0; i < g_pipeline_count; i++) {
        tc_pipeline* p = g_pipelines[i];
        infos[i].ptr = p;
        infos[i].name = p ? p->name : NULL;
        infos[i].pass_count = p ? p->pass_count : 0;
    }

    *count = g_pipeline_count;
    return infos;
}

tc_pass_info* tc_pass_registry_get_all_instance_info(size_t* count) {
    if (!count) return NULL;
    *count = 0;

    // Count total passes
    size_t total_passes = 0;
    for (size_t i = 0; i < g_pipeline_count; i++) {
        if (g_pipelines[i]) {
            total_passes += g_pipelines[i]->pass_count;
        }
    }

    if (total_passes == 0) return NULL;

    tc_pass_info* infos = (tc_pass_info*)malloc(total_passes * sizeof(tc_pass_info));
    if (!infos) return NULL;

    size_t idx = 0;
    for (size_t i = 0; i < g_pipeline_count; i++) {
        tc_pipeline* pipeline = g_pipelines[i];
        if (!pipeline) continue;

        tc_pass* pass = pipeline->first_pass;
        while (pass && idx < total_passes) {
            infos[idx].ptr = pass;
            infos[idx].pass_name = pass->pass_name;
            infos[idx].type_name = tc_pass_type_name(pass);
            infos[idx].pipeline_ptr = pipeline;
            infos[idx].pipeline_name = pipeline->name;
            infos[idx].enabled = pass->enabled;
            infos[idx].passthrough = pass->passthrough;
            infos[idx].is_inplace = tc_pass_is_inplace(pass);
            infos[idx].kind = (int)pass->kind;
            idx++;
            pass = pass->next;
        }
    }

    *count = idx;
    return infos;
}
