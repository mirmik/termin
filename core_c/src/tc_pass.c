// tc_pass.c - Pass registry and external pass support
#include "tc_pass.h"
#include "tc_pipeline.h"
#include "tc_log.h"
#include <stdlib.h>
#include <string.h>

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
// Pass Registry
// ============================================================================

#define MAX_PASS_TYPES 128

typedef struct {
    char* type_name;
    tc_pass_factory factory;
    tc_pass_kind kind;
} tc_pass_registry_entry;

static tc_pass_registry_entry g_pass_registry[MAX_PASS_TYPES];
static size_t g_pass_registry_count = 0;

static tc_pass_registry_entry* find_registry_entry(const char* type_name) {
    for (size_t i = 0; i < g_pass_registry_count; i++) {
        if (strcmp(g_pass_registry[i].type_name, type_name) == 0) {
            return &g_pass_registry[i];
        }
    }
    return NULL;
}

void tc_pass_registry_register(
    const char* type_name,
    tc_pass_factory factory,
    tc_pass_kind kind
) {
    if (!type_name || !factory) return;
    if (g_pass_registry_count >= MAX_PASS_TYPES) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Registry full, cannot register %s", type_name);
        return;
    }

    // Check if already registered
    if (find_registry_entry(type_name)) {
        tc_log(TC_LOG_WARN, "[tc_pass] Type %s already registered, skipping", type_name);
        return;
    }

    tc_pass_registry_entry* entry = &g_pass_registry[g_pass_registry_count++];
    entry->type_name = strdup(type_name);
    entry->factory = factory;
    entry->kind = kind;
}

void tc_pass_registry_unregister(const char* type_name) {
    for (size_t i = 0; i < g_pass_registry_count; i++) {
        if (strcmp(g_pass_registry[i].type_name, type_name) == 0) {
            free(g_pass_registry[i].type_name);
            // Shift remaining entries
            for (size_t j = i; j < g_pass_registry_count - 1; j++) {
                g_pass_registry[j] = g_pass_registry[j + 1];
            }
            g_pass_registry_count--;
            return;
        }
    }
}

bool tc_pass_registry_has(const char* type_name) {
    return find_registry_entry(type_name) != NULL;
}

tc_pass* tc_pass_registry_create(const char* type_name) {
    tc_pass_registry_entry* entry = find_registry_entry(type_name);
    if (!entry) {
        tc_log(TC_LOG_ERROR, "[tc_pass] Unknown type: %s", type_name);
        return NULL;
    }
    return entry->factory();
}

size_t tc_pass_registry_type_count(void) {
    return g_pass_registry_count;
}

const char* tc_pass_registry_type_at(size_t index) {
    if (index >= g_pass_registry_count) return NULL;
    return g_pass_registry[index].type_name;
}

tc_pass_kind tc_pass_registry_get_kind(const char* type_name) {
    tc_pass_registry_entry* entry = find_registry_entry(type_name);
    return entry ? entry->kind : TC_NATIVE_PASS;
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
    tc_log(TC_LOG_DEBUG, "[external_retain] p=%p body=%p has_incref=%d",
           (void*)p, p->body, g_external_callbacks.incref != NULL);
    if (g_external_callbacks.incref && p->body) {
        g_external_callbacks.incref(p->body);
    }
}

static void external_release(tc_pass* p) {
    tc_log(TC_LOG_DEBUG, "[external_release] p=%p body=%p has_decref=%d",
           (void*)p, p->body, g_external_callbacks.decref != NULL);
    if (g_external_callbacks.decref && p->body) {
        g_external_callbacks.decref(p->body);
    }
}

static void external_drop(tc_pass* p) {
    if (!p) return;

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
    .type_name = "ExternalPass",
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
    p->pass_name = type_name ? strdup(type_name) : NULL;

    tc_log(TC_LOG_DEBUG, "[tc_pass_new_external] created p=%p kind=%d name=%s body=%p",
           (void*)p, (int)p->kind, p->pass_name ? p->pass_name : "(null)", body);

    return p;
}

void tc_pass_free_external(tc_pass* p) {
    if (p) {
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

    return p;
}

void tc_pipeline_destroy(tc_pipeline* p) {
    if (!p) return;

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
        for (size_t i = 0; i < p->spec_count; i++) {
            // resource strings are not owned, don't free
        }
        free(p->specs);
    }

    free(p->name);
    free(p);
}

void tc_pipeline_add_pass(tc_pipeline* p, tc_pass* pass) {
    if (!p || !pass) return;

    tc_log(TC_LOG_DEBUG, "[tc_pipeline_add_pass] pipeline=%s pass=%p kind=%d name=%s body=%p",
           p->name, (void*)pass, (int)pass->kind,
           pass->pass_name ? pass->pass_name : "(null)",
           pass->body);

    // Retain pass to prevent deletion while in pipeline
    tc_pass_retain(pass);

    tc_log(TC_LOG_DEBUG, "[tc_pipeline_add_pass] after retain, pass=%p", (void*)pass);

    pass->prev = p->last_pass;
    pass->next = NULL;

    if (p->last_pass) {
        p->last_pass->next = pass;
    } else {
        p->first_pass = pass;
    }
    p->last_pass = pass;
    p->pass_count++;

    tc_log(TC_LOG_DEBUG, "[tc_pipeline_add_pass] done, count=%zu", p->pass_count);
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
