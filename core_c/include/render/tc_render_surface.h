#ifndef TC_RENDER_SURFACE_H
#define TC_RENDER_SURFACE_H

typedef struct tc_render_surface_ops {
    void (*swap_buffers)(tc_render_surface* surface);
    void (*make_current)(tc_render_surface* surface);
    void (*pool_events)(tc_render_surface* surface);
} tc_render_surface_ops;

typedef struct tc_render_surface {
    // Operations
    tc_render_surface_ops* ops;

    // Callbacks
    void (*on_resize)(tc_render_surface* surface, int width, int height);

} tc_render_surface;

#endif // TC_RENDER_SURFACE_H