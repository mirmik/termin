// tc_component_csharp.h - C# component support
// Analogous to tc_component_python.h, provides callback-based component
// lifecycle for components defined in C#.
#ifndef TC_COMPONENT_CSHARP_H
#define TC_COMPONENT_CSHARP_H

#include "core/tc_component.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Callback typedefs
// Each callback receives void* cs_self — a GCHandle IntPtr to the C# object.
// ============================================================================

typedef void (*tc_cs_start_fn)(void* cs_self);
typedef void (*tc_cs_update_fn)(void* cs_self, float dt);
typedef void (*tc_cs_fixed_update_fn)(void* cs_self, float dt);
typedef void (*tc_cs_before_render_fn)(void* cs_self);
typedef void (*tc_cs_on_destroy_fn)(void* cs_self);
typedef void (*tc_cs_on_added_to_entity_fn)(void* cs_self);
typedef void (*tc_cs_on_removed_from_entity_fn)(void* cs_self);
typedef void (*tc_cs_on_added_fn)(void* cs_self);
typedef void (*tc_cs_on_removed_fn)(void* cs_self);
typedef void (*tc_cs_on_scene_inactive_fn)(void* cs_self);
typedef void (*tc_cs_on_scene_active_fn)(void* cs_self);

// Reference counting: prevent GC from collecting the C# object
typedef void (*tc_cs_ref_add_fn)(void* cs_self);
typedef void (*tc_cs_ref_release_fn)(void* cs_self);

// ============================================================================
// Global C# callback table — set once at initialization
// ============================================================================

typedef struct {
    tc_cs_start_fn start;
    tc_cs_update_fn update;
    tc_cs_fixed_update_fn fixed_update;
    tc_cs_before_render_fn before_render;
    tc_cs_on_destroy_fn on_destroy;
    tc_cs_on_added_to_entity_fn on_added_to_entity;
    tc_cs_on_removed_from_entity_fn on_removed_from_entity;
    tc_cs_on_added_fn on_added;
    tc_cs_on_removed_fn on_removed;
    tc_cs_on_scene_inactive_fn on_scene_inactive;
    tc_cs_on_scene_active_fn on_scene_active;
    // Reference counting
    tc_cs_ref_add_fn ref_add;
    tc_cs_ref_release_fn ref_release;
} tc_csharp_callbacks;

// Set the global C# callbacks.
// Must be called once from C# before any C# components are created.
TC_API void tc_component_set_csharp_callbacks(const tc_csharp_callbacks* callbacks);

// Create a new C# component.
// cs_self is a GCHandle (IntPtr) to the C# object.
// The caller must ensure cs_self stays alive for the component's lifetime.
TC_API tc_component* tc_component_new_csharp(void* cs_self, const char* type_name);

// Free a C# component.
// Does NOT release the GCHandle — caller is responsible for C# object lifetime.
TC_API void tc_component_free_csharp(tc_component* c);

#ifdef __cplusplus
}
#endif

#endif // TC_COMPONENT_CSHARP_H
