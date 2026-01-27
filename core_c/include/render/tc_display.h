#ifndef TC_DISPLAY_H
#define TC_DISPLAY_H

#include <render/tc_render_surface.h>

typedef struct tc_viewport tc_viewport;

typedef struct tc_display {
    char* name;

    // Underlying render surface
    tc_render_surface* surface;

    // Linked list of viewports
    tc_viewport* first_viewport;
    tc_viewport* last_viewport;
} tc_display;

void tc_display_init(tc_display* display, const char* name);
void tc_display_shutdown(tc_display* display);

void tc_display_set_render_surface(tc_display* display, tc_render_surface* surface);

void tc_display_add_viewport(tc_display* display, tc_viewport* viewport);
void tc_display_remove_viewport(tc_display* display, tc_viewport* viewport);

#endif