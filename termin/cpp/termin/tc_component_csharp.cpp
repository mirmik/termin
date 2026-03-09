// tc_component_csharp.cpp - C# component implementation
// Analogous to tc_component_python.cpp
#include "tc_component_csharp.h"
#include <stdlib.h>
#include <string.h>

// Global C# callbacks (set once at initialization)
static tc_csharp_callbacks g_cs_callbacks = {0};

// ============================================================================
// C# vtable callbacks - dispatch to global C# callbacks
// ============================================================================

static void cs_vtable_start(tc_component* c) {
    if (g_cs_callbacks.start && c->body)
        g_cs_callbacks.start(c->body);
}

static void cs_vtable_update(tc_component* c, float dt) {
    if (g_cs_callbacks.update && c->body)
        g_cs_callbacks.update(c->body, dt);
}

static void cs_vtable_fixed_update(tc_component* c, float dt) {
    if (g_cs_callbacks.fixed_update && c->body)
        g_cs_callbacks.fixed_update(c->body, dt);
}

static void cs_vtable_before_render(tc_component* c) {
    if (g_cs_callbacks.before_render && c->body)
        g_cs_callbacks.before_render(c->body);
}

static void cs_vtable_on_destroy(tc_component* c) {
    if (g_cs_callbacks.on_destroy && c->body)
        g_cs_callbacks.on_destroy(c->body);
}

static void cs_vtable_on_added_to_entity(tc_component* c) {
    if (g_cs_callbacks.on_added_to_entity && c->body)
        g_cs_callbacks.on_added_to_entity(c->body);
}

static void cs_vtable_on_removed_from_entity(tc_component* c) {
    if (g_cs_callbacks.on_removed_from_entity && c->body)
        g_cs_callbacks.on_removed_from_entity(c->body);
}

static void cs_vtable_on_added(tc_component* c) {
    if (g_cs_callbacks.on_added && c->body)
        g_cs_callbacks.on_added(c->body);
}

static void cs_vtable_on_removed(tc_component* c) {
    if (g_cs_callbacks.on_removed && c->body)
        g_cs_callbacks.on_removed(c->body);
}

static void cs_vtable_on_scene_inactive(tc_component* c) {
    if (g_cs_callbacks.on_scene_inactive && c->body)
        g_cs_callbacks.on_scene_inactive(c->body);
}

static void cs_vtable_on_scene_active(tc_component* c) {
    if (g_cs_callbacks.on_scene_active && c->body)
        g_cs_callbacks.on_scene_active(c->body);
}

// ============================================================================
// C# ref_vtable — prevent GC collection
// ============================================================================

static void cs_ref_retain(tc_component* c) {
    if (g_cs_callbacks.ref_add && c->body)
        g_cs_callbacks.ref_add(c->body);
}

static void cs_ref_release(tc_component* c) {
    if (g_cs_callbacks.ref_release && c->body)
        g_cs_callbacks.ref_release(c->body);
}

static const tc_component_ref_vtable g_cs_ref_vtable = {
    cs_ref_retain,
    cs_ref_release,
    NULL,  // drop: C# GC owns the object
};

// ============================================================================
// C# component vtable (shared by all C# components)
// ============================================================================

static const tc_component_vtable g_csharp_vtable = {
    .start = cs_vtable_start,
    .update = cs_vtable_update,
    .fixed_update = cs_vtable_fixed_update,
    .before_render = cs_vtable_before_render,
    .on_destroy = cs_vtable_on_destroy,
    .on_added_to_entity = cs_vtable_on_added_to_entity,
    .on_removed_from_entity = cs_vtable_on_removed_from_entity,
    .on_added = cs_vtable_on_added,
    .on_removed = cs_vtable_on_removed,
    .on_scene_inactive = cs_vtable_on_scene_inactive,
    .on_scene_active = cs_vtable_on_scene_active,
    .on_editor_start = NULL,
    .setup_editor_defaults = NULL,
    .serialize = NULL,
    .deserialize = NULL,
};

// ============================================================================
// Public API
// ============================================================================

void tc_component_set_csharp_callbacks(const tc_csharp_callbacks* callbacks) {
    if (callbacks) {
        g_cs_callbacks = *callbacks;
    }
}

tc_component* tc_component_new_csharp(void* cs_self, const char* type_name) {
    tc_component* c = (tc_component*)calloc(1, sizeof(tc_component));
    if (!c) return NULL;

    tc_component_init(c, &g_csharp_vtable);
    c->ref_vtable = &g_cs_ref_vtable;

    // Store C# GCHandle pointer as body
    c->body = cs_self;
    c->native_language = TC_LANGUAGE_CSHARP;
    c->kind = TC_CSHARP_COMPONENT;

    // Link to type registry
    if (type_name) {
        tc_type_entry* entry = tc_component_registry_get_entry(type_name);
        if (entry) {
            c->type_entry = entry;
            c->type_version = entry->version;
        }
    }

    return c;
}

void tc_component_free_csharp(tc_component* c) {
    if (c) {
        tc_component_unlink_from_registry(c);
        free(c);
    }
}
