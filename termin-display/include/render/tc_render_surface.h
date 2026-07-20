// tc_render_surface.h - Backend-neutral texture output for one tc_display.
#ifndef TC_RENDER_SURFACE_H
#define TC_RENDER_SURFACE_H

#include "tc_types.h"
#include "render/termin_display_api.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tc_display tc_display;
typedef struct tc_render_surface tc_render_surface;
typedef struct tc_render_surface_vtable tc_render_surface_vtable;

#define TC_RENDER_SURFACE_ABI_VERSION 1u

typedef void (*tc_render_surface_resize_fn)(
    tc_render_surface* surface,
    int width,
    int height,
    void* userdata
);

// Every callback is mandatory. A surface is a pixel-sized texture output; it
// deliberately has no window, input, presentation, raw-FBO or context API.
struct tc_render_surface_vtable {
    void (*get_size)(tc_render_surface* self, int* width, int* height);
    uint32_t (*get_color_texture_id)(tc_render_surface* self);
    // Opaque identity of the IRenderDevice domain that minted the texture
    // handle. It is compared only for equality and is never dereferenced.
    uintptr_t (*get_graphics_domain_key)(tc_render_surface* self);
    void (*destroy)(tc_render_surface* self);
};

struct tc_render_surface {
    const tc_render_surface_vtable* vtable;
    void* body;
    tc_render_surface_resize_fn on_resize;
    void* on_resize_userdata;
    // Enforces the one-surface-to-one-display contract and protects the sole
    // resize subscription from accidental overwrite.
    tc_display* attached_display;
};

static inline void tc_render_surface_init(
    tc_render_surface* surface,
    const tc_render_surface_vtable* vtable
) {
    surface->vtable = vtable;
    surface->body = NULL;
    surface->on_resize = NULL;
    surface->on_resize_userdata = NULL;
    surface->attached_display = NULL;
}

static inline void tc_render_surface_get_size(
    tc_render_surface* surface,
    int* width,
    int* height
) {
    if (surface && surface->vtable && surface->vtable->get_size) {
        surface->vtable->get_size(surface, width, height);
        return;
    }
    if (width) *width = 0;
    if (height) *height = 0;
}

static inline uint32_t tc_render_surface_get_color_texture_id(
    tc_render_surface* surface
) {
    return surface && surface->vtable && surface->vtable->get_color_texture_id
        ? surface->vtable->get_color_texture_id(surface)
        : 0;
}

static inline uintptr_t tc_render_surface_get_graphics_domain_key(
    tc_render_surface* surface
) {
    return surface && surface->vtable && surface->vtable->get_graphics_domain_key
        ? surface->vtable->get_graphics_domain_key(surface)
        : 0;
}

// Resolve and validate the mandatory output before any GPU operation. The
// caller supplies its opaque graphics-domain key (normally the IRenderDevice
// address). On success, color_texture_id receives a non-zero handle id.
TERMIN_DISPLAY_API bool tc_render_surface_validate_output(
    tc_render_surface* surface,
    uintptr_t expected_graphics_domain_key,
    uint32_t* color_texture_id
);

static inline void tc_render_surface_notify_resize(
    tc_render_surface* surface,
    int width,
    int height
) {
    if (surface && surface->on_resize) {
        surface->on_resize(surface, width, height, surface->on_resize_userdata);
    }
}

// Attachment functions diagnose invalid ownership transitions. Detach succeeds
// only for the display that currently owns the attachment.
TERMIN_DISPLAY_API bool tc_render_surface_attach(
    tc_render_surface* surface,
    tc_display* display
);
TERMIN_DISPLAY_API bool tc_render_surface_detach(
    tc_render_surface* surface,
    tc_display* display
);

// External adapters pass size and version explicitly, so stale managed/native
// layouts fail before the vtable is copied or invoked.
TERMIN_DISPLAY_API tc_render_surface* tc_render_surface_new_external(
    void* body,
    const tc_render_surface_vtable* vtable,
    size_t vtable_size,
    uint32_t abi_version
);
TERMIN_DISPLAY_API bool tc_render_surface_free_external(tc_render_surface* surface);

#ifdef __cplusplus
}
#endif

#endif // TC_RENDER_SURFACE_H
