#pragma once

#include "render/termin_display_api.h"

struct tc_input_manager;

namespace termin {

class SDLBackendWindow;

// Attach engine input routing to a lightweight termin-window instance.
// Passing nullptr removes the bridge. The input manager must outlive the
// attachment.
TERMIN_DISPLAY_API void attach_sdl_input_manager(
    SDLBackendWindow& window,
    tc_input_manager* input_manager);

} // namespace termin
