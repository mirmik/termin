#pragma once

#include "render/tc_display_pool.h"
#include "render/termin_display_api.h"

namespace termin {

    class BackendWindow;
    struct WindowEvent;

    TERMIN_DISPLAY_API void dispatch_window_input_event(tc_display_handle display, const WindowEvent& event);

    TERMIN_DISPLAY_API void attach_window_input_display(BackendWindow& window, tc_display_handle display);

} // namespace termin
