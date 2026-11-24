#pragma once

#include <render/tc_display.h>

namespace termin::web {
    // Framebuffer coordinates use a top-left origin. The returned entity UUID
    // belongs to the scene and remains valid until the entity changes.
    const char* pick_mesh_entity(tc_display_handle display, float x, float y);
} // namespace termin::web
